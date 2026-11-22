import asyncio

from app.interview_schemas import (
    AnswerAssessment,
    InterviewFeedback,
    InterviewSession,
    QuestionOutput,
    SupervisorDecision,
)
from app.services.interview_graph import InterviewReport, InterviewerScores, interview_graph
from app.services.interview_store import InterviewStore


def test_graph_handoff_question_limit_and_final_report(monkeypatch):
    async def fake_structured(schema, _system, _human, values):
        if schema is QuestionOutput:
            return QuestionOutput(question=f"{values['area']}를 설명해 주세요.", area=values["area"], intent="근거 확인")
        if schema is AnswerAssessment:
            return AnswerAssessment(
                feedback=InterviewFeedback(
                    score=80, rationale="답변 근거 확인", strengths=["경험 언급"],
                    improvements=["결과 수치 보강"], suggested_answer=values["answer"],
                ),
                answer_quality="specific", follow_up_needed=False, follow_up_reason="",
            )
        if schema is SupervisorDecision:
            actor = "hr" if values.get("count") == 0 else "team_leader"
            return SupervisorDecision(action="next_interviewer", interviewer=actor, area="협업 경험", reason="질문 영역 분배")
        if schema is InterviewReport:
            return InterviewReport(
                overall_score=80, summary="응답 근거가 있습니다.", strengths=["경험 기반 답변"],
                improvements=["결과를 구체화"], priority_actions=["STAR로 정리"],
                interviewer_scores=InterviewerScores(
                    hr=80, team_leader=80, technical=None, executive=None
                ), duration_note="기록 기반",
            )
        raise AssertionError(schema)

    monkeypatch.setattr(interview_graph, "_structured", fake_structured)

    async def run_flow():
        session = InterviewSession(
            session_id="workflow-test", company_name="예시회사", position="플랫폼 엔지니어",
            job_description="API 개발", interview_type="comprehensive",
            interviewers=["hr", "team_leader"], difficulty="practical", max_questions=2,
            mode="text", status="ready", created_at="2026-11-22T00:00:00+00:00",
            updated_at="2026-11-22T00:00:00+00:00",
        )
        first = await interview_graph.advance(session, "start")
        assert first["current_interviewer"] == "hr"
        assert first["questions_count"] == 1

        session = session.model_copy(update={
            "status": "in_progress",
            "current_question": {**first["current_question"], "interviewer_id": "hr"},
            "messages": [
                {"message_id": "q1", "speaker": "면접관", "interviewer_id": "hr", "text": first["current_question"]["question"], "area": first["current_question"]["area"]},
                {"message_id": "a1", "speaker": "지원자", "question_id": "q1", "text": "팀과 배포 문제를 해결했습니다."},
            ],
        })
        second = await interview_graph.advance(session, "answer", answer="팀과 배포 문제를 해결했습니다.")
        assert second["current_interviewer"] == "team_leader"
        assert second["questions_count"] == 2
        assert second["messages"][1]["assessment"]["feedback"]["score"] == 80

        session = session.model_copy(update={
            "current_question": {**second["current_question"], "interviewer_id": "team_leader"},
            "messages": session.messages + [
                {"message_id": "q2", "speaker": "면접관", "interviewer_id": "team_leader", "text": second["current_question"]["question"], "area": second["current_question"]["area"]},
                {"message_id": "a2", "speaker": "지원자", "question_id": "q2", "text": "로그 확인 후 설정을 되돌렸습니다."},
            ],
        })
        final = await interview_graph.advance(session, "answer", answer="로그 확인 후 설정을 되돌렸습니다.")
        assert final["status"] == "completed"
        assert final["result"]["overall_score"] == 80

    asyncio.run(run_flow())


def test_interview_store_survives_reopen_and_supports_history(tmp_path):
    database = tmp_path / "interviews.sqlite3"
    session = {
        "session_id": "persistence-test", "company_name": "테스트 기업", "position": "테스트 직무",
        "status": "completed", "created_at": "2026-11-22T00:00:00+00:00",
        "updated_at": "2026-11-22T00:01:00+00:00", "messages": [],
    }
    InterviewStore(database).save(session)

    reopened = InterviewStore(database)
    assert reopened.get("persistence-test")["position"] == "테스트 직무"
    assert len(reopened.list()) == 1
    assert reopened.delete("persistence-test") is True
    assert reopened.get("persistence-test") is None
