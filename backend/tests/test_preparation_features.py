import asyncio

import pytest

from app.job_schemas import JobPostingAnalysis
from app.services import job_materials
from app.services.material_store import MaterialStore
from app.services import matcher
from app.services.interview_graph import InterviewGraphService
from app.interview_schemas import InterviewSession, QuestionOutput
from app.api import routes, interview_routes


def test_material_hash_and_revision_storage_preserve_each_source(tmp_path):
    store = MaterialStore(tmp_path / "materials.sqlite3")
    first = store.save(kind="job", source="text", title="Backend", raw_text="공고 원문 A" * 10,
                       analysis={"position": "백엔드"}, company_name="회사")
    second = store.save(kind="job", source="text", title="Backend v2", raw_text="공고 원문 B" * 10,
                        analysis={"position": "백엔드"}, company_name="회사")

    assert first["material_id"] != second["material_id"]
    assert len(store.list("job")) == 2
    assert store.get(first["material_id"])["raw_text"].startswith("공고 원문 A")


def test_duplicate_manual_job_reuses_analysis_and_saved_record(monkeypatch, tmp_path):
    store = MaterialStore(tmp_path / "materials.sqlite3")
    monkeypatch.setattr(routes, "material_store", store)
    calls = []

    async def fake_analysis(_raw, _images=None):
        calls.append(1)
        return JobPostingAnalysis(company_name="예시", position="백엔드", required_skills=["Python"])

    monkeypatch.setattr(routes, "analyze_job_material", fake_analysis)

    async def run():
        from app.job_schemas import MaterialInput
        request = MaterialInput(source="manual", company_name="예시", position="백엔드",
                                job_description="Python 백엔드 API를 구축하고 운영하는 팀원을 찾습니다." * 2)
        first = await routes.create_job_material(request)
        second = await routes.create_job_material(request)
        return first, second

    first, second = asyncio.run(run())
    assert first["material_id"] == second["material_id"]
    assert len(calls) == 1
    assert len(store.list("job")) == 1


@pytest.mark.parametrize("url", ["http://127.0.0.1", "http://localhost/admin", "https://192.168.1.10/posting"])
def test_url_ingestion_blocks_private_network_addresses(url):
    with pytest.raises(job_materials.JobMaterialError, match="내부|사설"):
        job_materials._validate_public_url(url)


def test_job_text_file_extracts_without_network_or_llm():
    content, images = job_materials.extract_material_file("opening.txt", "text/plain", "백엔드 개발 채용 공고".encode())
    assert content == "백엔드 개발 채용 공고"
    assert images == []


def test_job_image_upload_checks_real_signature():
    with pytest.raises(job_materials.JobMaterialError, match="확장자"):
        job_materials.extract_material_file("opening.png", "image/png", b"not an image")


def test_saved_job_matching_accepts_material_store_record(monkeypatch):
    engine = matcher.HRMatchingEngine(persist_directory="unused")
    resume = matcher.ResumeData(
        candidate_name="테스트", total_experience_years=1, core_skills=["Python"],
        projects=[], educations=[], overall_summary="백엔드 API 개발",
    )
    captured = {}
    monkeypatch.setattr(engine, "_get_vectorstore", lambda: None)

    async def fake_match(_resume, job_id, job_info):
        captured.update(job_id=job_id, job_info=job_info)
        return "matched"

    monkeypatch.setattr(engine, "_match_resume_to_job", fake_match)
    result = asyncio.run(engine.match_saved_job(resume, {
        "material_id": "saved-material-123", "position": "백엔드 개발자",
        "company_name": "가상기업", "raw_text": "Python API 개발 채용 공고 내용",
        "analysis": {"required_skills": ["Python"]},
    }))
    assert result == "matched"
    assert captured["job_id"] == "saved-material-123"
    assert captured["job_info"]["title"] == "백엔드 개발자"


def test_question_generation_receives_saved_job_fit_and_source_mix(monkeypatch):
    graph = InterviewGraphService()
    captured = {}

    async def fake_structured(_schema, _system, _human, values):
        captured.update(values)
        return QuestionOutput(question="프로젝트에서 API를 설계한 이유가 무엇인가요?", area="설계", intent="경험 근거", source_type="resume", rationale="이력서 프로젝트를 검증", candidate_evidence="HireSync")

    monkeypatch.setattr(graph, "_structured", fake_structured)
    session = InterviewSession(
        session_id="focus-test", company_name="예시", position="백엔드",
        job_description="Python, FastAPI 기반 API 설계 및 운영" * 5,
        job_analysis={"requirements": [{"name": "API 설계", "source_quote": "API 설계"}]},
        candidate_fit={"items": [{"requirement": "API 설계", "status": "supported", "interview_probe": "설계 이유"}]},
        job_question_ratio=50, prior_weaknesses=[{"topic": "답변 구체성", "occurrences": 2}],
        resume_data={"candidate_name": "테스트", "total_experience_years": 2, "core_skills": ["Python"], "projects": [], "educations": [], "overall_summary": "API 개발"},
        interview_type="comprehensive", interviewers=["technical"], difficulty="practical", max_questions=4,
        mode="text", status="in_progress", created_at="2026-11-22T00:00:00+00:00", updated_at="2026-11-22T00:00:00+00:00",
        messages=[{"speaker": "면접관", "message_id": "q1", "text": "공고 기반 질문", "source_type": "job"}],
    )

    result = asyncio.run(graph._ask({"session": session.model_dump(mode="json"), "messages": session.messages,
                                     "current_interviewer": "technical", "questions_count": 1,
                                     "decision": {"area": "설계"}}))
    assert captured["desired_source"] == "resume"
    assert "API 설계" in captured["requirements"]
    assert "답변 구체성" in captured["weaknesses"]
    assert result["current_question"]["candidate_evidence"] == "HireSync"


def test_prior_weaknesses_only_use_related_saved_sessions(monkeypatch):
    class FakeStore:
        def list(self, _limit):
            def session(session_id, position, score):
                return {"session_id": session_id, "status": "completed", "company_name": "예시", "position": position,
                        "messages": [{"message_id": "q", "speaker": "면접관", "text": "설계 근거는?"},
                                    {"speaker": "지원자", "question_id": "q", "text": "짧은 답변", "assessment": {"feedback": {"score": score, "category_tags": ["답변 구체성"], "improvements": ["사례를 덧붙이기"]}}}]}
            return [session("one", "백엔드", 50), session("two", "백엔드", 55), session("other", "디자인", 20)]

    monkeypatch.setattr(interview_routes, "store", FakeStore())
    summary = interview_routes._prior_weakness_summary("다른 회사", "백엔드")
    assert len(summary) == 1
    assert summary[0]["topic"] == "답변 구체성"
    assert summary[0]["occurrences"] == 2
    assert summary[0]["average_score"] == 52


def test_analytics_uses_real_records_and_empty_state_has_no_fake_scores(monkeypatch):
    class FakeStore:
        def __init__(self, values): self.values = values
        def list(self, _limit): return self.values

    monkeypatch.setattr(interview_routes, "store", FakeStore([]))
    empty = asyncio.run(interview_routes.get_interview_analytics())
    assert empty["completed_interviews"] == 0
    assert empty["average_score"] is None
    assert empty["recent"] == []

    monkeypatch.setattr(interview_routes, "store", FakeStore([{
        "session_id": "analytics-1", "status": "completed", "company_name": "예시", "position": "백엔드",
        "created_at": "2026-11-22T00:00:00+00:00", "updated_at": "2026-11-22T01:00:00+00:00",
        "result": {"overall_score": 72},
        "messages": [{"message_id": "q", "speaker": "면접관", "area": "API 설계", "text": "이유?"},
                     {"speaker": "지원자", "question_id": "q", "assessment": {"feedback": {"score": 60, "category_tags": ["기술 선택 근거"], "improvements": ["대안을 설명"]}}}],
    }]))
    data = asyncio.run(interview_routes.get_interview_analytics())
    assert data["completed_interviews"] == 1
    assert data["average_score"] == 72
    assert data["weaknesses"][0]["topic"] == "기술 선택 근거"
    assert data["area_scores"][0]["area"] == "API 설계"
