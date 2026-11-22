import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services import extractor
from app.api import interview_routes
from app.interview_schemas import InterviewCreateRequest
from app.services.openai_client import OpenAIServiceError, public_openai_error
from app.schemas import ResumeData
from app.services import matcher
from app.services.interview_store import InterviewStore


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (SimpleNamespace(status_code=401, code="invalid_api_key"), "인증에 실패"),
        (SimpleNamespace(status_code=404, code="model_not_found"), "OPENAI_MODEL"),
        (SimpleNamespace(status_code=429, code="insufficient_quota"), "결제 잔액"),
        (TimeoutError(), "시간이 초과"),
        (ConnectionError(), "네트워크 연결"),
    ],
)
def test_openai_failures_map_to_safe_actionable_messages(error, expected):
    mapped = public_openai_error(error, "테스트")
    assert isinstance(mapped, OpenAIServiceError)
    assert expected in str(mapped)


def test_resume_extraction_does_not_return_fake_fallback_when_openai_fails(monkeypatch):
    def fail_before_request(**_kwargs):
        raise OpenAIServiceError("OpenAI API 키 설정이 필요합니다.", 503)

    monkeypatch.setattr(extractor, "create_chat_model", fail_before_request)

    with pytest.raises(OpenAIServiceError, match="API 키 설정"):
        asyncio.run(extractor.parse_resume_to_json("지원자 이력서 내용"))


def test_job_evaluation_does_not_return_rule_based_ai_score_on_failure(monkeypatch):
    def fail_before_request(**_kwargs):
        raise OpenAIServiceError("OpenAI 사용 한도를 확인해 주세요.", 503)

    monkeypatch.setattr(matcher, "create_chat_model", fail_before_request)
    resume = ResumeData(
        candidate_name="테스트 지원자",
        total_experience_years=2,
        core_skills=["Python"],
        projects=[],
        educations=[],
        overall_summary="Python API 개발 경험",
    )
    engine = matcher.HRMatchingEngine()

    with pytest.raises(OpenAIServiceError, match="사용 한도"):
        asyncio.run(
            engine.evaluate_candidate_with_llm(
                resume, matcher.SAMPLE_JDS["jd_backend"], semantic_score=75
            )
        )


def test_job_recommendation_does_not_return_keyword_fallback_on_embedding_failure(monkeypatch):
    resume = ResumeData(
        candidate_name="테스트 지원자",
        total_experience_years=2,
        core_skills=["Python"],
        projects=[],
        educations=[],
        overall_summary="Python API 개발 경험",
    )
    engine = matcher.HRMatchingEngine()

    def fail_embedding():
        raise OpenAIServiceError("OpenAI 임베딩을 사용할 수 없습니다.", 503)

    monkeypatch.setattr(engine, "_get_vectorstore", fail_embedding)
    with pytest.raises(OpenAIServiceError, match="임베딩"):
        engine.recommend_jobs(resume, top_k=3)


def test_failed_interview_start_removes_only_new_session_and_preserves_history(monkeypatch, tmp_path):
    store = InterviewStore(tmp_path / "interviews.sqlite3")
    store.save(
        {
            "session_id": "existing-session",
            "company_name": "기존 기업",
            "position": "기존 직무",
            "status": "completed",
            "created_at": "2026-11-22T00:00:00+00:00",
            "updated_at": "2026-11-22T00:00:00+00:00",
            "messages": [],
        }
    )
    monkeypatch.setattr(interview_routes, "store", store)

    async def fail_advance(*_args, **_kwargs):
        raise HTTPException(status_code=503, detail="OpenAI 사용 한도 확인")

    monkeypatch.setattr(interview_routes, "_advance", fail_advance)
    request = InterviewCreateRequest(position="테스트 직무", interviewers=["hr"])

    with pytest.raises(HTTPException) as error:
        asyncio.run(interview_routes.create_interview(request))

    assert error.value.status_code == 503
    assert [item["session_id"] for item in store.list()] == ["existing-session"]
