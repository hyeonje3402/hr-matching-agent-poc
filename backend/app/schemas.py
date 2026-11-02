from typing import List, Optional
from pydantic import BaseModel, Field


# ==========================================
# 1. 이력서 추출용 스키마 (Information Extraction)
# ==========================================
class ProjectExperience(BaseModel):
    project_name: str = Field(description="프로젝트 명칭 또는 주요 담당 업무명")
    role: str = Field(description="프로젝트 내 담당 역할 (예: 백엔드 리드, AI 모델링 등)")
    period: Optional[str] = Field(default=None, description="수행 기간 (예: 2023.03 - 2024.01)")
    tech_stack: List[str] = Field(default_factory=list, description="해당 프로젝트에 사용된 기술 스택")
    summary: str = Field(description="주요 성과 및 담당 업무 핵심 요약 (1~2문장)")


class EducationInfo(BaseModel):
    school_name: str = Field(description="학교명 (대학교/대학원)")
    major: str = Field(description="전공명")
    degree: str = Field(description="학위 (학사, 석사, 박사, 졸업예정 등)")
    graduation_status: Optional[str] = Field(default=None, description="졸업 여부 또는 졸업 연도")


class ResumeData(BaseModel):
    candidate_name: Optional[str] = Field(default="이름 미상", description="지원자 성명")
    total_experience_years: float = Field(
        description="총 경력 년수 (숫자만 반환. 신입은 0.0, 예: 3년 6개월 -> 3.5)"
    )
    core_skills: List[str] = Field(
        description="이력서에서 확인되는 핵심 기술 스택 및 도구 리스트 (예: Python, PyTorch, FastAPI, Docker)"
    )
    projects: List[ProjectExperience] = Field(
        description="주요 프로젝트 및 실무 경력 사항 리스트"
    )
    educations: List[EducationInfo] = Field(
        description="학력 사항 리스트"
    )
    overall_summary: str = Field(
        description="지원자의 직무 정체성 및 핵심 역량 한 줄 요약"
    )


# ==========================================
# 2. 채용 공고(JD) 매칭 및 평가용 스키마
# ==========================================
class LLMMatchEvaluation(BaseModel):
    llm_score: int = Field(
        description="지원자의 기술 스택, 프로젝트 깊이, 경력 년수를 JD 요구사항과 비교한 적합도 점수 (0~100 사이 정수)",
        ge=0,
        le=100,
    )
    three_line_summary: List[str] = Field(
        description="인사담당자를 위한 지원자 종합 평가 3줄 요약 (반드시 핵심만 3개의 문장 원소로 작성)",
        min_length=3,
        max_length=3,
    )
    matched_strengths: List[str] = Field(
        description="채용 공고(JD) 요구사항과 부합하는 지원자의 핵심 강점 리스트"
    )
    missing_gaps: List[str] = Field(
        description="채용 공고(JD) 대비 아쉽거나 보완/면접 확인이 필요한 역량 리스트"
    )


class MatchRequest(BaseModel):
    job_id: str = Field(description="매칭할 채용 공고 ID (예: jd_ai_vision, jk_50177130 등)")
    resume_data: ResumeData = Field(description="추출된 지원자 이력서 JSON 데이터")


class MatchResponse(BaseModel):
    job_id: str
    job_title: str
    semantic_similarity_score: float = Field(description="ChromaDB 임베딩 코사인 유사도 점수 (0~100)")
    llm_evaluation_score: int = Field(description="LLM 정밀 평가 점수 (0~100)")
    final_matching_score: float = Field(description="가중 평균 최종 매칭 점수 (0~100)")
    three_line_summary: List[str]
    matched_strengths: List[str]
    missing_gaps: List[str]


# ==========================================
# 3. 잡코리아·사람인 스크래핑 및 맞춤형 공고 추천 스키마
# ==========================================
class ScrapeJobKoreaRequest(BaseModel):
    keyword: str = Field(default="Python 백엔드", description="잡코리아 및 사람인에서 검색할 직무/기술 키워드")
    max_items: int = Field(default=6, ge=1, le=15, description="플랫폼별 스크래핑하여 ChromaDB에 적재할 최대 공고 수")
    include_saramin: bool = Field(default=True, description="사람인(Saramin) 공고도 함께 스크래핑할지 여부")


class RecommendedJobItem(BaseModel):
    job_id: str
    title: str
    department: str
    min_experience: float
    description: str
    url: Optional[str] = None
    source: str = "Internal"
    # 직관적인 채용 기간 및 조건 메타데이터
    start_date: Optional[str] = Field(default="상시", description="모집 시작일 (예: 2026.10.15)")
    end_date: Optional[str] = Field(default="상시채용", description="모집 마감일 (예: 2026.11.15 23:59)")
    d_day_label: Optional[str] = Field(default="상시채용", description="남은 시간/일수 직관적 표시 (예: D-12 · 12일 남음)")
    urgency_level: Optional[str] = Field(default="normal", description="마감 임박도 (urgent | normal | relaxed | closed)")
    remaining_ratio: Optional[float] = Field(default=70.0, description="남은 기간 비율 (0~100%)")
    location: Optional[str] = Field(default="서울/수도권", description="근무지역")
    experience_label: Optional[str] = Field(default="신입/경력", description="경력 요건 표기")
    job_keywords: List[str] = Field(default_factory=list, description="직무/기술 핵심 태그")
    is_dual_posted: bool = Field(default=False, description="잡코리아와 사람인에 동일 공고가 동시 게재되었는지 여부")
    paired_job_id: Optional[str] = Field(default=None, description="동일 공고로 매칭된 타 플랫폼 공고 ID")
    similarity_score: float = Field(description="ChromaDB 시맨틱 매칭 적합도 점수 (0~100)")
    match_reason: str = Field(description="이 지원자에게 해당 공고를 추천하는 핵심 사유")


class RecommendRequest(BaseModel):
    resume_data: ResumeData
    top_k: int = Field(default=6, ge=1, le=12)
    auto_scrape_jobkorea: bool = Field(
        default=True,
        description="지원자 핵심 기술 스택 기반으로 잡코리아 및 사람인 실시간 공고를 자동 스크래핑하여 DB에 추가할지 여부",
    )
    custom_keyword: Optional[str] = Field(
        default=None,
        description="특정 검색어로 잡코리아·사람인 공고를 스크랩하고 싶을 때 지정",
    )

