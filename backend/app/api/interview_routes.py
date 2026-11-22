from datetime import datetime, timezone
import asyncio
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from app.interview_schemas import (
    InterviewAnswerRequest,
    InterviewCreateRequest,
    InterviewSession,
    InterviewSkipRequest,
)
from app.services.interview_graph import AGENTS, interview_graph
from app.services.interview_store import InterviewStore
from app.services.material_store import MaterialStore
from app.services.matcher import SAMPLE_JDS
from app.services.openai_client import OpenAIServiceError


router = APIRouter(prefix="/api/interviews", tags=["AI Interview"])
store = InterviewStore()
materials = MaterialStore()
session_locks: dict[str, asyncio.Lock] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _save(session: InterviewSession) -> InterviewSession:
    session.updated_at = _now()
    store.save(session.model_dump(mode="json"))
    return session


def _get_session(session_id: str) -> InterviewSession:
    data = store.get(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="면접 기록을 찾을 수 없습니다.")
    return InterviewSession.model_validate(data)


def _next_question(session: InterviewSession, state):
    if state.get("status") == "completed":
        session.status = "completed"
        session.result = state.get("result")
        session.current_question = None
        return
    question = state.get("current_question")
    if question:
        actor = state.get("current_interviewer", session.interviewers[0])
        session.current_question = {**question, "interviewer_id": actor, "interviewer_name": AGENTS[actor]["name"]}
        session.messages.append({
            "message_id": str(uuid4()), "speaker": "면접관", "interviewer_id": actor,
            "interviewer_name": AGENTS[actor]["name"], "text": question["question"],
            "area": question["area"], "intent": question["intent"],
            "source_type": question.get("source_type", "general"),
            "rationale": question.get("rationale", ""),
            "related_requirement": question.get("related_requirement", ""),
            "candidate_evidence": question.get("candidate_evidence", ""),
            "follow_up": bool(state.get("decision", {}).get("action") == "follow_up"),
            "created_at": _now(),
        })
        session.status = "in_progress"


def _session_lock(session_id: str) -> asyncio.Lock:
    return session_locks.setdefault(session_id, asyncio.Lock())


def _prior_weakness_summary(company_name: str, position: str) -> list[dict]:
    target_company = company_name.strip().casefold()
    target_position = position.strip().casefold()
    counts: dict[str, dict] = {}
    for saved in store.list(200):
        if saved.get("status") != "completed":
            continue
        saved_position = saved.get("position", "").strip().casefold()
        same_role = bool(target_position and saved_position and (
            saved_position == target_position
            or (min(len(saved_position), len(target_position)) >= 3
                and (saved_position in target_position or target_position in saved_position))
        ))
        same_company = bool(target_company and saved.get("company_name", "").strip().casefold() == target_company)
        if not (same_role or same_company):
            continue
        messages = saved.get("messages", [])
        questions = {m.get("message_id"): m for m in messages if m.get("speaker") == "면접관"}
        for answer in messages:
            feedback = ((answer.get("assessment") or {}).get("feedback") or {})
            score = feedback.get("score")
            tags = feedback.get("category_tags") or []
            if not isinstance(score, int) or score >= 65 or not tags:
                continue
            question = questions.get(answer.get("question_id"), {})
            for tag in dict.fromkeys(tags[:5]):
                key = str(tag).strip()[:80]
                if not key:
                    continue
                entry = counts.setdefault(key, {"topic": key, "count": 0, "scores": [], "latest_question": "", "latest_advice": ""})
                entry["count"] += 1
                entry["scores"].append(score)
                entry["latest_question"] = question.get("text", "")[:300]
                improvements = feedback.get("improvements") or []
                entry["latest_advice"] = str(improvements[0])[:240] if improvements else ""
    ranked = sorted((item for item in counts.values() if item["count"] >= 2),
                    key=lambda item: (item["count"], -sum(item["scores"]) / max(1, len(item["scores"]))), reverse=True)
    return [{"topic": item["topic"], "occurrences": item["count"],
             "average_score": round(sum(item["scores"]) / len(item["scores"])),
             "previous_question": item["latest_question"], "practice_hint": item["latest_advice"]}
            for item in ranked[:6]]


def _ensure_unanswered(session: InterviewSession, expected_question_id: str):
    if session.status != "in_progress" or not session.current_question:
        raise HTTPException(status_code=409, detail="현재 답변할 질문이 없습니다.")
    question_id = next((m.get("message_id") for m in reversed(session.messages) if m.get("speaker") == "면접관"), None)
    if question_id != expected_question_id:
        raise HTTPException(status_code=409, detail="이미 진행된 질문입니다. 최신 면접 상태를 새로고침해 주세요.")
    last_index = max((i for i, m in enumerate(session.messages) if m.get("message_id") == question_id), default=-1)
    if last_index < 0 or any(m.get("speaker") == "지원자" for m in session.messages[last_index + 1:]):
        raise HTTPException(status_code=409, detail="이미 답변했거나 건너뛴 질문입니다.")


async def _advance(session: InterviewSession, input_type: str, answer: str = "", assessment=None):
    try:
        state = await interview_graph.advance(session, input_type, answer=answer, assessment=assessment)
        _next_question(session, state)
        _save(session)
        return session
    except OpenAIServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail="면접 AI 처리에 실패했습니다. OpenAI 설정과 API 상태를 확인해 주세요.") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="면접 AI 응답을 처리하지 못했습니다. 답변은 기록되지 않았습니다.") from exc


@router.post("", response_model=InterviewSession, status_code=201)
async def create_interview(request: InterviewCreateRequest):
    job = SAMPLE_JDS.get(request.job_id) if request.job_id else None
    material_id = request.job_material_id or (request.job_id if request.job_id and request.job_id not in SAMPLE_JDS else None)
    saved_job = materials.get(material_id) if material_id else None
    if request.job_id and not job and not saved_job:
        raise HTTPException(status_code=404, detail="선택한 채용 공고를 찾을 수 없습니다.")
    source_job = saved_job or job or {}
    analysis = (saved_job or {}).get("analysis") or request.job_analysis
    company = request.company_name.strip() or source_job.get("company_name") or source_job.get("department", "").split(" (")[0] or (analysis or {}).get("company_name", "")
    position = request.position.strip() or source_job.get("position") or source_job.get("title", "") or (analysis or {}).get("position", "")
    description = request.job_description.strip() or source_job.get("raw_text") or source_job.get("description", "")
    if not position and not description:
        raise HTTPException(status_code=422, detail="지원 직무 또는 채용 공고 내용을 입력해 주세요.")

    now = _now()
    session = InterviewSession(
        session_id=str(uuid4()), company_name=company or "미지정 기업", position=position or "공고 기반 직무",
        job_description=description, job_id=request.job_id, interview_type=request.interview_type,
        interviewers=request.interviewers, difficulty=request.difficulty,
        max_questions=request.max_questions, mode=request.mode, resume_data=request.resume_data,
        practice_question=request.practice_question,
        job_material_id=(saved_job or {}).get("material_id") or request.job_material_id,
        job_analysis=analysis,
        candidate_fit=request.candidate_fit,
        job_question_ratio=request.job_question_ratio,
        prior_weaknesses=_prior_weakness_summary(company, position) if request.use_prior_results else [],
        supporting_materials=request.supporting_materials,
        resume_material_ids=request.resume_material_ids,
        status="ready", current_question=None, created_at=now, updated_at=now,
    )
    _save(session)
    try:
        return await _advance(session, "start")
    except HTTPException:
        store.delete(session.session_id)
        raise


@router.get("", response_model=list[InterviewSession])
async def list_interviews(limit: int = Query(default=100, ge=1, le=200)):
    return [InterviewSession.model_validate(item) for item in store.list(limit)]


@router.get("/analytics")
async def get_interview_analytics():
    sessions = [item for item in store.list(200) if item.get("status") == "completed"]
    ordered = sorted(sessions, key=lambda item: item.get("created_at", ""))
    score_history = [
        {"session_id": item["session_id"], "date": item.get("created_at", ""),
         "company_name": item.get("company_name", ""), "position": item.get("position", ""),
         "score": item.get("result", {}).get("overall_score")}
        for item in ordered if isinstance(item.get("result", {}).get("overall_score"), int)
    ]
    categories: dict[str, dict] = {}
    area_scores: dict[str, list[int]] = {}
    for session in sessions:
        questions = {m.get("message_id"): m for m in session.get("messages", []) if m.get("speaker") == "면접관"}
        for message in session.get("messages", []):
            if message.get("speaker") != "지원자" or message.get("skipped"):
                continue
            feedback = ((message.get("assessment") or {}).get("feedback") or {})
            score = feedback.get("score")
            question = questions.get(message.get("question_id"), {})
            area = question.get("area")
            if isinstance(score, int) and area:
                area_scores.setdefault(str(area), []).append(score)
            for tag in feedback.get("category_tags", [])[:5]:
                name = str(tag).strip()[:80]
                if not name:
                    continue
                entry = categories.setdefault(name, {"topic": name, "occurrences": 0, "scores": [], "last_seen": session.get("updated_at", "")})
                entry["occurrences"] += 1
                if isinstance(score, int):
                    entry["scores"].append(score)
                if session.get("updated_at", "") >= entry["last_seen"]:
                    entry["last_seen"] = session.get("updated_at", "")
                    entry["question"] = question.get("text", "")[:260]
                    improvements = feedback.get("improvements") or []
                    entry["practice_hint"] = str(improvements[0])[:220] if improvements else ""
    weaknesses = []
    for item in categories.values():
        scores = item.pop("scores")
        item["average_score"] = round(sum(scores) / len(scores)) if scores else None
        item["priority"] = "반복 확인" if item["occurrences"] >= 2 else "추가 확인"
        weaknesses.append(item)
    weaknesses.sort(key=lambda item: (item["occurrences"], -(item["average_score"] or 0)), reverse=True)
    by_role: dict[str, int] = {}
    for session in sessions:
        role = session.get("position") or "미지정 직무"
        by_role[role] = by_role.get(role, 0) + 1
    return {
        "completed_interviews": len(sessions),
        "average_score": round(sum(row["score"] for row in score_history) / len(score_history)) if score_history else None,
        "recent": score_history[-8:][::-1],
        "by_role": [{"position": role, "count": count} for role, count in sorted(by_role.items(), key=lambda pair: pair[1], reverse=True)],
        "area_scores": [{"area": area, "average_score": round(sum(scores) / len(scores)), "count": len(scores)} for area, scores in sorted(area_scores.items())],
        "weaknesses": weaknesses[:12],
        "practice_questions": [
            {"session_id": session["session_id"], "company_name": session.get("company_name", ""),
             "position": session.get("position", ""), "question_id": question.get("message_id"),
             "question": question.get("text", ""), "score": ((answer.get("assessment") or {}).get("feedback") or {}).get("score")}
            for session in sorted(sessions, key=lambda item: item.get("updated_at", ""), reverse=True)
            for question in session.get("messages", []) if question.get("speaker") == "면접관"
            for answer in session.get("messages", []) if answer.get("speaker") == "지원자" and answer.get("question_id") == question.get("message_id")
            if isinstance(((answer.get("assessment") or {}).get("feedback") or {}).get("score"), int)
        ][:12],
        "note": "연습 기록을 요약한 참고 지표이며 실제 기업의 채용 평가나 합격 가능성을 나타내지 않습니다.",
    }


@router.get("/{session_id}", response_model=InterviewSession)
async def get_interview(session_id: str):
    return _get_session(session_id)


@router.post("/{session_id}/answer", response_model=InterviewSession)
async def submit_interview_answer(session_id: str, request: InterviewAnswerRequest):
    async with _session_lock(session_id):
        session = _get_session(session_id)
        _ensure_unanswered(session, request.question_id)
        question_index = max(i for i, m in enumerate(session.messages) if m.get("speaker") == "면접관")
        answer_message = {
            "message_id": str(uuid4()), "speaker": "지원자", "text": request.answer.strip(),
            "created_at": _now(), "question_id": session.messages[question_index]["message_id"],
        }
        session.messages.append(answer_message)
        before_advance = session.model_copy(deep=True)
        try:
            state = await interview_graph.advance(session, "answer", answer=request.answer.strip())
            answer_message["assessment"] = state.get("assessment")
            _next_question(session, state)
            return _save(session)
        except OpenAIServiceError as exc:
            session.messages = before_advance.messages
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        except RuntimeError as exc:
            session.messages = before_advance.messages
            raise HTTPException(status_code=502, detail="답변 평가에 실패했습니다. OpenAI 설정과 API 상태를 확인해 주세요.") from exc
        except Exception as exc:
            session.messages = before_advance.messages
            raise HTTPException(status_code=502, detail="답변 평가에 실패했습니다. 잠시 후 다시 제출해 주세요.") from exc


@router.post("/{session_id}/skip", response_model=InterviewSession)
async def skip_interview_question(session_id: str, request: InterviewSkipRequest):
    async with _session_lock(session_id):
        session = _get_session(session_id)
        _ensure_unanswered(session, request.question_id)
        question_index = max(i for i, m in enumerate(session.messages) if m.get("speaker") == "면접관")
        session.messages.append({
            "message_id": str(uuid4()), "speaker": "지원자", "text": "질문 건너뜀" + (f": {request.reason}" if request.reason else ""),
            "created_at": _now(), "question_id": session.messages[question_index]["message_id"], "skipped": True,
        })
        return await _advance(session, "skip")


@router.post("/{session_id}/finish", response_model=InterviewSession)
async def finish_interview(session_id: str):
    async with _session_lock(session_id):
        session = _get_session(session_id)
        if session.status == "completed":
            return session
        if session.status != "in_progress":
            raise HTTPException(status_code=409, detail="진행 중인 면접이 없습니다.")
        return await _advance(session, "finish")


@router.delete("/{session_id}", status_code=204)
async def delete_interview(session_id: str):
    if not store.delete(session_id):
        raise HTTPException(status_code=404, detail="면접 기록을 찾을 수 없습니다.")
    session_locks.pop(session_id, None)


@router.post("/{session_id}/repractice", response_model=InterviewSession, status_code=201)
async def create_question_repractice(session_id: str, question_id: str = Query(..., min_length=1)):
    original = _get_session(session_id)
    question = next((m for m in original.messages if m.get("message_id") == question_id and m.get("speaker") == "면접관"), None)
    if not question:
        raise HTTPException(status_code=404, detail="재연습할 질문을 찾을 수 없습니다.")
    now = _now()
    practice = original.model_copy(deep=True, update={
        "session_id": str(uuid4()), "interview_type": "job",
        "interviewers": [question["interviewer_id"]], "max_questions": 2,
        "mode": "text", "messages": [], "status": "ready", "current_question": None,
        "result": None, "practice_question": question["text"],
        "job_material_id": original.job_material_id, "job_analysis": original.job_analysis,
        "candidate_fit": original.candidate_fit, "job_question_ratio": original.job_question_ratio,
        "prior_weaknesses": original.prior_weaknesses,
        "supporting_materials": original.supporting_materials,
        "resume_material_ids": original.resume_material_ids,
        "created_at": now, "updated_at": now,
    })
    _save(practice)
    try:
        return await _advance(practice, "start")
    except HTTPException:
        store.delete(practice.session_id)
        raise
