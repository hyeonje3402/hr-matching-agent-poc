from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas import ResumeData


Interviewer = Literal["hr", "team_leader", "technical", "executive"]


class InterviewCreateRequest(BaseModel):
    resume_data: Optional[ResumeData] = None
    job_id: Optional[str] = None
    company_name: str = Field(default="", max_length=120)
    position: str = Field(default="", max_length=160)
    job_description: str = Field(default="", max_length=12000)
    interview_type: Literal["comprehensive", "hr", "job", "technical", "executive"] = "comprehensive"
    interviewers: List[Interviewer] = Field(default_factory=lambda: ["hr", "team_leader", "technical"])
    difficulty: Literal["basic", "practical", "advanced"] = "practical"
    max_questions: int = Field(default=8, ge=2, le=15)
    mode: Literal["text", "voice"] = "text"
    practice_question: Optional[str] = Field(default=None, max_length=2000)
    job_material_id: Optional[str] = None
    job_analysis: Optional[Dict[str, Any]] = None
    candidate_fit: Optional[Dict[str, Any]] = None
    job_question_ratio: int = Field(default=50, ge=0, le=100)
    use_prior_results: bool = True
    supporting_materials: str = Field(default="", max_length=12000)
    resume_material_ids: List[str] = Field(default_factory=list, max_length=10)

    @field_validator("interviewers")
    @classmethod
    def ensure_interviewer_selection(cls, value: List[str]) -> List[str]:
        unique = list(dict.fromkeys(value))
        if not unique or len(unique) > 4:
            raise ValueError("면접관을 1명 이상 선택해 주세요.")
        return unique

    @field_validator("job_description")
    @classmethod
    def trim_job_description(cls, value: str) -> str:
        return value.strip()


class InterviewAnswerRequest(BaseModel):
    question_id: str = Field(min_length=1, max_length=80)
    answer: str = Field(min_length=1, max_length=8000)

    @field_validator("answer")
    @classmethod
    def require_nonblank_answer(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("답변 내용을 입력해 주세요.")
        return cleaned


class InterviewSkipRequest(BaseModel):
    question_id: str = Field(min_length=1, max_length=80)
    reason: Optional[str] = Field(default=None, max_length=300)


class InterviewSession(BaseModel):
    session_id: str
    company_name: str
    position: str
    job_description: str
    job_id: Optional[str] = None
    interview_type: str
    interviewers: List[Interviewer]
    difficulty: str
    max_questions: int
    mode: str
    resume_data: Optional[ResumeData] = None
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    status: Literal["ready", "in_progress", "completed"]
    current_question: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    practice_question: Optional[str] = None
    job_material_id: Optional[str] = None
    job_analysis: Optional[Dict[str, Any]] = None
    candidate_fit: Optional[Dict[str, Any]] = None
    job_question_ratio: int = 50
    prior_weaknesses: List[Dict[str, Any]] = Field(default_factory=list)
    supporting_materials: str = ""
    resume_material_ids: List[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class InterviewFeedback(BaseModel):
    score: int = Field(ge=0, le=100)
    rationale: str
    strengths: List[str] = Field(default_factory=list)
    improvements: List[str] = Field(default_factory=list)
    suggested_answer: str
    correct_concept: str = ""
    category_tags: List[str] = Field(default_factory=list)
    topic_tags: List[str] = Field(default_factory=list)


class QuestionOutput(BaseModel):
    question: str
    area: str
    intent: str
    source_type: Literal["job", "resume", "both", "general"] = "general"
    rationale: str = ""
    related_requirement: str = ""
    candidate_evidence: str = ""


class AnswerAssessment(BaseModel):
    feedback: InterviewFeedback
    answer_quality: Literal["abstract", "inaccurate", "specific", "unknown", "adequate"]
    follow_up_needed: bool
    follow_up_reason: str


class SupervisorDecision(BaseModel):
    action: Literal["follow_up", "next_interviewer", "finish"]
    interviewer: Optional[Interviewer] = None
    area: str
    reason: str
