from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.schemas import (
    ResumeData,
    MatchRequest,
    MatchResponse,
    ScrapeJobKoreaRequest,
    RecommendRequest,
    RecommendedJobItem,
)
from app.services.pdf_parser import extract_text_from_pdf
from app.services.extractor import parse_resume_to_json
from app.services.matcher import HRMatchingEngine, SAMPLE_JDS
from app.services.jobkorea_scraper import scrape_jobkorea_postings

router = APIRouter(prefix="/api", tags=["Resume & Matching"])

# 싱글톤 매칭 엔진 인스턴스
matching_engine = HRMatchingEngine()


@router.get("/jobs")
async def get_job_list():
    """현재 등록된 전체 채용 공고(사내 공고 + 잡코리아 스크래핑 공고) 목록을 반환합니다."""
    return [
        {
            "job_id": k,
            "title": v["title"],
            "department": v["department"],
            "min_experience": v["min_experience"],
            "description": v["description"],
            "url": v.get("url"),
            "source": v.get("source", "Internal"),
            "start_date": v.get("start_date", "상시"),
            "end_date": v.get("end_date", "상시채용"),
            "d_day_label": v.get("d_day_label", "상시채용"),
            "urgency_level": v.get("urgency_level", "normal"),
            "remaining_ratio": v.get("remaining_ratio", 70.0),
            "location": v.get("location", "서울/수도권"),
            "experience_label": v.get("experience_label", f"경력 {v['min_experience']}년+"),
            "job_keywords": v.get("job_keywords", []),
        }
        for k, v in SAMPLE_JDS.items()
    ]


@router.post("/jobs/scrape-jobkorea")
async def scrape_and_ingest_jobkorea(request: ScrapeJobKoreaRequest):
    """
    잡코리아(JobKorea)에서 키워드로 실시간 채용 공고를 스크래핑하여
    ChromaDB 벡터 데이터베이스에 임베딩 적재하고 업데이트된 공고 목록을 반환합니다.
    """
    scraped = await scrape_jobkorea_postings(
        keyword=request.keyword, max_items=request.max_items
    )
    ingested_count = matching_engine.ingest_scraped_jobs(scraped)
    return {
        "keyword": request.keyword,
        "scraped_count": ingested_count,
        "scraped_jobs": scraped,
        "all_jobs": await get_job_list(),
    }


@router.post("/resume/upload", response_model=ResumeData)
async def upload_and_extract_resume(file: UploadFile = File(...)):
    """
    [1단계 API] PDF 이력서를 업로드받아 텍스트를 추출하고 정형화된 JSON 데이터로 반환합니다.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일(.pdf)만 업로드 가능합니다.")

    try:
        file_bytes = await file.read()
        raw_text = extract_text_from_pdf(file_bytes)
        structured_resume = await parse_resume_to_json(raw_text)
        return structured_resume
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"이력서 분석 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/resume/match", response_model=MatchResponse)
async def match_resume_with_jd(request: MatchRequest):
    """
    [2단계 API] 추출된 지원자 JSON 데이터와 특정 직무(JD)를 비교하여
    매칭 점수와 3줄 요약 평가 코멘트를 반환합니다.
    """
    try:
        match_result = await matching_engine.match(
            resume=request.resume_data,
            job_id=request.job_id,
        )
        return match_result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"직무 매칭 평가 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/resume/recommend", response_model=List[RecommendedJobItem])
async def recommend_jobs_for_candidate(request: RecommendRequest):
    """
    [3단계 API] 지원자의 이력서 스킬을 기반으로 잡코리아 실시간 공고를 스크랩해 ChromaDB에 적재한 뒤,
    벡터 유사도가 가장 높은 맞춤형 추천 공고 Top-K 리스트를 반환합니다.
    """
    try:
        if request.auto_scrape_jobkorea:
            # 지원자의 상위 핵심 기술 키워드로 잡코리아 실시간 공고 자동 수집
            if request.custom_keyword and request.custom_keyword.strip():
                search_kw = request.custom_keyword.strip()
            elif request.resume_data.core_skills:
                search_kw = " ".join(request.resume_data.core_skills[:2])
            else:
                search_kw = "개발자"

            scraped = await scrape_jobkorea_postings(keyword=search_kw, max_items=6)
            if scraped:
                matching_engine.ingest_scraped_jobs(scraped)

        recommendations = matching_engine.recommend_jobs(
            resume=request.resume_data,
            top_k=request.top_k,
        )
        return recommendations
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"맞춤 공고 추천 중 오류가 발생했습니다: {str(e)}"
        )

