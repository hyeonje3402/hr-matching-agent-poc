from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field


class JobRequirement(BaseModel):
    name: str = Field(description="공고에 명시된 요구 역량 또는 책임")
    category: str = Field(description="기술, 실무, 협업, 지식 등")
    importance: Literal["required", "preferred", "inferred"]
    source_quote: str = Field(description="원문 근거. 원문에 없으면 빈 문자열")


class JobPostingAnalysis(BaseModel):
    company_name: Optional[str] = None
    position: Optional[str] = None
    field: Optional[str] = None
    responsibilities: List[str] = Field(default_factory=list)
    required_qualifications: List[str] = Field(default_factory=list)
    preferred_qualifications: List[str] = Field(default_factory=list)
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    experience: Optional[str] = None
    location: Optional[str] = None
    deadline: Optional[str] = None
    hiring_process: List[str] = Field(default_factory=list)
    requirements: List[JobRequirement] = Field(default_factory=list)
    interview_focus: List[str] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)


class RequirementFit(BaseModel):
    requirement: str
    status: Literal["supported", "needs_confirmation", "not_found"]
    candidate_evidence: List[str] = Field(default_factory=list)
    projects: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    rationale: str
    interview_probe: str


class CandidateFitAnalysis(BaseModel):
    items: List[RequirementFit] = Field(default_factory=list)
    overall_note: str
    additional_questions: List[str] = Field(default_factory=list)


class MaterialInput(BaseModel):
    source: Literal["text", "manual"] = "text"
    company_name: str = Field(default="", max_length=120)
    position: str = Field(default="", max_length=160)
    job_description: str = Field(min_length=30, max_length=30000)
    source_url: Optional[str] = Field(default=None, max_length=2000)


class MaterialUpdate(BaseModel):
    company_name: str = Field(default="", max_length=120)
    position: str = Field(default="", max_length=160)
    analysis: JobPostingAnalysis


class MaterialResponse(BaseModel):
    material_id: str
    kind: str
    source: str
    title: str
    company_name: str
    position: str
    source_url: Optional[str] = None
    content_hash: str
    analysis: Any
    raw_text: str = ""
    created_at: str
    updated_at: str
