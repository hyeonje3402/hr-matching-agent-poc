from typing import Dict, Any, Optional, List
import httpx
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from app.config import settings
from app.schemas import (
    ResumeData,
    LLMMatchEvaluation,
    MatchResponse,
    RecommendedJobItem,
)
from app.services.jobkorea_scraper import link_cross_platform_duplicates


def _is_openai_key(key: str) -> bool:
    return bool(
        key
        and key.startswith("sk-")
        and not key.startswith("sk-proj-your")
    )


def _is_google_key(key: str) -> bool:
    return bool(
        key
        and (key.startswith("AQ.") or key.startswith("AIza"))
    )


class GeminiRestEmbeddings(Embeddings):
    """
    사용자가 제공한 Google API 키(AQ.... / AIza...)를 사용하여
    gemini-embedding-001 모델로 실제 3072차원 임베딩 벡터를 생성하는 클래스입니다.
    """

    def __init__(self, api_key: str, model: str = "gemini-embedding-001"):
        self.api_key = api_key
        self.model = model

    def embed_query(self, text: str) -> List[float]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:embedContent?key={self.api_key}"
        payload = {"content": {"parts": [{"text": text}]}}
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()["embedding"]["values"]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_query(t) for t in texts]


# 사내 기본 채용 공고 및 잡코리아 스크랩 공고가 통합 저장되는 인메모리 레지스트리 (ChromaDB와 동기화)
SAMPLE_JDS: Dict[str, Dict[str, Any]] = {
    "jd_ai_vision": {
        "job_id": "jd_ai_vision",
        "title": "AI 비전 엔지니어 (Computer Vision)",
        "department": "AI Research Lab (사내공고)",
        "min_experience": 2.0,
        "description": (
            "자율주행 및 스마트 팩토리용 실시간 객체 탐지(Object Detection), 세그멘테이션(Segmentation) 모델을 연구/개발합니다. "
            "필수 역량: Python, PyTorch, OpenCV, 딥러닝 비전 모델(YOLO, ViT, DETR 등) 학습 및 최적화 경험. "
            "우대 사항: TensorRT/ONNX 경량화 및 엣지 디바이스 배포 경험, C++, Docker, MLOps 파이프라인 구축 경험, 관련 석/박사 학위."
        ),
        "url": None,
        "source": "Internal",
        "start_date": "2026.10.20(화)",
        "end_date": "2026.11.15(일) 23:59",
        "d_day_label": "D-13 (13일 남음)",
        "urgency_level": "normal",
        "remaining_ratio": 52.0,
        "location": "서울 강남구",
        "experience_label": "경력 2년↑",
        "job_keywords": ["Python", "PyTorch", "OpenCV", "YOLO", "Computer Vision"],
    },
    "jd_backend": {
        "job_id": "jd_backend",
        "title": "시니어 백엔드 엔지니어 (Python/FastAPI)",
        "department": "SaaS Platform Team (사내공고)",
        "min_experience": 3.0,
        "description": (
            "B2B 엔터프라이즈 SaaS 플랫폼의 고성능 API 서버 및 비동기 데이터 파이프라인을 설계/개발합니다. "
            "필수 역량: Python, FastAPI 또는 Django, RDBMS(PostgreSQL/MySQL) 설계 및 쿼리 튜닝, Redis, AWS 클라우드 인프라 운영 경험. "
            "우대 사항: MSA 아키텍처 설계, Docker/Kubernetes 기반 CI/CD 운영, 대용량 트래픽 처리, LLM API 연동 서비스 개발 경험."
        ),
        "url": None,
        "source": "Internal",
        "start_date": "2026.10.25(일)",
        "end_date": "2026.11.05(목) 18:00",
        "d_day_label": "D-3 (마감 임박 · 3일 남음)",
        "urgency_level": "urgent",
        "remaining_ratio": 25.0,
        "location": "경기 성남시 분당구",
        "experience_label": "경력 3년↑",
        "job_keywords": ["Python", "FastAPI", "PostgreSQL", "AWS", "Docker"],
    },
    "jd_ai_agent": {
        "job_id": "jd_ai_agent",
        "title": "LLM 애플리케이션 / AI 에이전트 엔지니어",
        "department": "GenAI Solution Team (사내공고)",
        "min_experience": 1.0,
        "description": (
            "기업용 RAG(검색 증강 생성) 시스템 및 자율형 AI 에이전트 워크플로우를 설계하고 프로덕션에 배포합니다. "
            "필수 역량: Python, LangChain 또는 LlamaIndex, OpenAI API, Vector DB(Chroma, Pinecone, Milvus 등) 활용 능력, FastAPI. "
            "우대 사항: 프롬프트 엔지니어링 최적화, Structured Output 설계, LLM 평가(RAGAS 등) 파이프라인 구축 경험."
        ),
        "url": None,
        "source": "Internal",
        "start_date": "2026.10.01(목)",
        "end_date": "상시채용 (채용 시 마감)",
        "d_day_label": "상시채용 (여유)",
        "urgency_level": "relaxed",
        "remaining_ratio": 90.0,
        "location": "서울 서초구",
        "experience_label": "신입·경력 1년↑",
        "job_keywords": ["Python", "LangChain", "ChromaDB", "RAG", "FastAPI"],
    },
}


class HRMatchingEngine:
    def __init__(self, persist_directory: Optional[str] = None):
        self.persist_directory = persist_directory or settings.CHROMA_PERSIST_DIR
        self._vectorstore: Optional[Chroma] = None
        self._active_provider: Optional[str] = None
        self._is_seeded: bool = False

    def _get_vectorstore(self) -> Chroma:
        """
        API 키 종류(OpenAI 또는 Google Gemini)에 맞는 임베딩 모델을 바인딩하여
        ChromaDB 컬렉션을 초기화하고 채용 공고(JD)를 적재합니다.
        """
        api_key = settings.OPENAI_API_KEY
        provider = (
            "openai"
            if _is_openai_key(api_key)
            else ("google" if _is_google_key(api_key) else "none")
        )

        if provider == "none":
            raise ValueError("API 키가 설정되지 않았습니다.")

        if self._vectorstore is None or self._active_provider != provider:
            if provider == "openai":
                embeddings: Embeddings = OpenAIEmbeddings(
                    model=settings.EMBEDDING_MODEL,
                    api_key=api_key,
                )
                collection_name = "company_jds_openai"
            else:
                embeddings = GeminiRestEmbeddings(
                    api_key=api_key,
                    model="gemini-embedding-001",
                )
                collection_name = "company_jds_gemini"

            self._vectorstore = Chroma(
                collection_name=collection_name,
                embedding_function=embeddings,
                persist_directory=self.persist_directory,
                collection_metadata={"hnsw:space": "cosine"},
            )
            self._active_provider = provider
            self._is_seeded = False

        if not self._is_seeded:
            self._seed_job_descriptions(list(SAMPLE_JDS.values()))
            self._is_seeded = True

        return self._vectorstore

    def _seed_job_descriptions(self, jobs_to_upsert: List[Dict[str, Any]]):
        """채용 공고(JD) 리스트를 ChromaDB에 적재(Upsert)합니다."""
        if self._vectorstore is None or not jobs_to_upsert:
            return

        documents = []
        ids = []
        for jd in jobs_to_upsert:
            job_id = jd["job_id"]
            doc_text = (
                f"직무명: {jd['title']}\n"
                f"채용기업/부서: {jd['department']}\n"
                f"최소 요구 경력: {jd['min_experience']}년 이상\n"
                f"상세 요구 역량 및 직무 기술서: {jd['description']}"
            )
            documents.append(
                Document(
                    page_content=doc_text,
                    metadata={
                        "job_id": job_id,
                        "title": jd["title"],
                        "department": jd["department"],
                        "min_exp": float(jd["min_experience"]),
                        "source": jd.get("source", "Internal"),
                        "url": jd.get("url") or "",
                    },
                )
            )
            ids.append(job_id)

        self._vectorstore.add_documents(documents=documents, ids=ids)

    def ingest_scraped_jobs(self, scraped_jobs: List[Dict[str, Any]]) -> int:
        """
        잡코리아 및 사람인에서 스크랩한 채용 공고를 인메모리 레지스트리(SAMPLE_JDS)와
        ChromaDB 벡터 데이터베이스에 실시간으로 임베딩하여 저장하고,
        두 플랫폼에 동시 게재된 동일 공고 쌍을 자동으로 연결합니다.
        """
        if not scraped_jobs:
            return 0

        new_or_updated = []
        for job in scraped_jobs:
            SAMPLE_JDS[job["job_id"]] = job
            new_or_updated.append(job)

        link_cross_platform_duplicates(SAMPLE_JDS)

        try:
            vectorstore = self._get_vectorstore()
            self._seed_job_descriptions(new_or_updated)
        except Exception:
            pass

        return len(new_or_updated)

    @staticmethod
    def _resume_to_semantic_text(resume: ResumeData) -> str:
        """지원자의 정형 JSON 데이터를 의미 기반 임베딩에 최적화된 서술형 텍스트로 변환합니다."""
        projects_desc = "\n".join(
            [
                f"- {p.project_name} ({p.role}): {p.summary} [사용기술: {', '.join(p.tech_stack)}]"
                for p in resume.projects
            ]
        )
        edu_desc = ", ".join(
            [f"{e.school_name} {e.major} ({e.degree})" for e in resume.educations]
        )

        return (
            f"지원자 요약: {resume.overall_summary}\n"
            f"총 경력: {resume.total_experience_years}년\n"
            f"핵심 보유 기술: {', '.join(resume.core_skills)}\n"
            f"주요 프로젝트 경험:\n{projects_desc}\n"
            f"학력 사항: {edu_desc}"
        )

    def _build_recommended_item(
        self, resume: ResumeData, jid: str, sim_score: float
    ) -> RecommendedJobItem:
        jd = SAMPLE_JDS[jid]
        jd_text_lower = f"{jd['title']} {jd['description']}".lower()
        matched_skills = [
            s for s in resume.core_skills if s.lower() in jd_text_lower
        ]
        skill_note = (
            f"지원자의 보유 기술({', '.join(matched_skills[:4])})이 공고 핵심 키워드와 직접 부합하며, "
            if matched_skills
            else f"지원자의 {', '.join(resume.core_skills[:3])} 기반 프로젝트 경험이 직무 도메인과 시맨틱 유사도가 높으며, "
        )
        exp_note = (
            f"요구 경력({jd['min_experience']}년 이상) 조건에 지원 가능하여 추천합니다."
            if resume.total_experience_years >= jd["min_experience"]
            else f"요구 경력은 {jd['min_experience']}년이나 보유 기술 적합도가 높아 도전 추천합니다."
        )
        is_dual = bool(jd.get("is_dual_posted") and jd.get("paired_job_id"))
        dual_prefix = (
            "[잡코리아·사람인 동일 공고 동시 게재 — 두 플랫폼 공고 모두 추천] "
            if is_dual
            else ""
        )

        return RecommendedJobItem(
            job_id=jid,
            title=jd["title"],
            department=jd["department"],
            min_experience=jd["min_experience"],
            description=jd["description"],
            url=jd.get("url"),
            source=jd.get("source", "Internal"),
            start_date=jd.get("start_date", "상시"),
            end_date=jd.get("end_date", "상시채용"),
            d_day_label=jd.get("d_day_label", "상시채용"),
            urgency_level=jd.get("urgency_level", "normal"),
            remaining_ratio=jd.get("remaining_ratio", 70.0),
            location=jd.get("location", "서울/수도권"),
            experience_label=jd.get("experience_label", f"경력 {jd['min_experience']}년+"),
            job_keywords=jd.get("job_keywords", []),
            is_dual_posted=is_dual,
            paired_job_id=jd.get("paired_job_id"),
            similarity_score=sim_score,
            match_reason=dual_prefix + skill_note + exp_note,
        )

    def recommend_jobs(self, resume: ResumeData, top_k: int = 6) -> List[RecommendedJobItem]:
        """
        ChromaDB에 저장된 전체 채용 공고(사내 공고 + 잡코리아 + 사람인 스크랩 공고) 중에서
        지원자의 이력서 벡터와 코사인 유사도가 가장 높은 맞춤형 공고를 추천합니다.
        만약 동일한 공고가 잡코리아와 사람인 양쪽에 올라와 있는 경우, 두 공고를 함께 묶어 둘 다 추천합니다.
        """
        link_cross_platform_duplicates(SAMPLE_JDS)
        candidate_text = self._resume_to_semantic_text(resume)
        score_map: Dict[str, float] = {}
        ordered_jids: List[str] = []

        try:
            vectorstore = self._get_vectorstore()
            total_available = max(top_k * 2, len(SAMPLE_JDS))
            results = vectorstore.similarity_search_with_score(
                query=candidate_text,
                k=total_available,
            )

            for doc, cosine_distance in results:
                jid = doc.metadata.get("job_id")
                if not jid or jid in score_map or jid not in SAMPLE_JDS:
                    continue
                cosine_similarity = max(0.0, 1.0 - float(cosine_distance))
                sim_score = round(
                    min(100.0, max(0.0, (cosine_similarity - 0.30) / (0.82 - 0.30) * 100.0)),
                    1,
                )
                score_map[jid] = sim_score
                ordered_jids.append(jid)
        except Exception:
            pass

        # 벡터 검색에서 누락되었거나 폴백인 경우 키워드 기반 유사도 보완
        for jid, jd in SAMPLE_JDS.items():
            if jid not in score_map:
                jd_desc = f"{jd['title']} {jd['description']}".lower()
                matched_cnt = sum(1 for s in resume.core_skills if s.lower() in jd_desc)
                ratio = matched_cnt / max(1, len(resume.core_skills))
                score_map[jid] = round(min(95.0, 62.0 + ratio * 33.0), 1)
                ordered_jids.append(jid)

        ordered_jids.sort(key=lambda x: score_map.get(x, 0.0), reverse=True)

        recommendations: List[RecommendedJobItem] = []
        included_ids = set()

        for jid in ordered_jids:
            if jid in included_ids:
                continue
            if len(recommendations) >= top_k:
                break

            jd = SAMPLE_JDS[jid]
            paired_id = jd.get("paired_job_id")

            # 동일 공고가 잡코리아와 사람인에 둘 다 올라와 있으면 두 개를 나란히 추천
            if jd.get("is_dual_posted") and paired_id and paired_id in SAMPLE_JDS and paired_id not in included_ids:
                pair_score = max(score_map.get(jid, 78.0), score_map.get(paired_id, 78.0))
                first_item = self._build_recommended_item(resume, jid, pair_score)
                second_item = self._build_recommended_item(
                    resume, paired_id, round(max(0.0, pair_score - 0.2), 1)
                )
                recommendations.append(first_item)
                recommendations.append(second_item)
                included_ids.add(jid)
                included_ids.add(paired_id)
            else:
                recommendations.append(
                    self._build_recommended_item(resume, jid, score_map.get(jid, 78.0))
                )
                included_ids.add(jid)

        # 만약 SAMPLE_JDS 내에 동시 게재(잡코리아+사람인) 쌍이 존재하는데 아직 추천 목록에 없다면
        # 가장 점수가 높은 동시 게재 쌍 2개를 추천 리스트에 포함하여 두 플랫폼 공고를 모두 보여줌
        has_dual_in_recs = any(r.is_dual_posted for r in recommendations)
        if not has_dual_in_recs:
            dual_candidates = [
                jid for jid in ordered_jids
                if SAMPLE_JDS[jid].get("is_dual_posted")
                and SAMPLE_JDS[jid].get("paired_job_id") in SAMPLE_JDS
            ]
            if dual_candidates:
                best_jid = dual_candidates[0]
                paired_id = SAMPLE_JDS[best_jid]["paired_job_id"]
                pair_score = max(score_map.get(best_jid, 80.0), score_map.get(paired_id, 80.0))
                first_item = self._build_recommended_item(resume, best_jid, pair_score)
                second_item = self._build_recommended_item(
                    resume, paired_id, round(max(0.0, pair_score - 0.2), 1)
                )
                if len(recommendations) >= 2:
                    recommendations = recommendations[:-2]
                recommendations.append(first_item)
                recommendations.append(second_item)

        return recommendations

    def calculate_semantic_similarity(self, resume: ResumeData, target_job_id: str) -> float:
        """
        1단계: 지원자 역량 텍스트와 특정 JD 벡터 간의 ChromaDB 코사인 유사도를 계산해 0~100점으로 환산합니다.
        """
        try:
            vectorstore = self._get_vectorstore()
            candidate_text = self._resume_to_semantic_text(resume)

            results = vectorstore.similarity_search_with_score(
                query=candidate_text,
                k=1,
                filter={"job_id": target_job_id},
            )

            if results:
                _, cosine_distance = results[0]
                cosine_similarity = max(0.0, 1.0 - float(cosine_distance))
                normalized_score = min(
                    100.0, max(0.0, (cosine_similarity - 0.30) / (0.82 - 0.30) * 100.0)
                )
                return round(normalized_score, 1)
        except Exception:
            pass

        jd_desc = SAMPLE_JDS[target_job_id]["description"].lower()
        matched_cnt = sum(1 for s in resume.core_skills if s.lower() in jd_desc)
        ratio = matched_cnt / max(1, len(resume.core_skills))
        return round(min(96.0, 58.0 + ratio * 38.0), 1)

    def _fallback_evaluate(
        self, resume: ResumeData, jd_info: Dict[str, Any], semantic_score: float
    ) -> LLMMatchEvaluation:
        jd_desc_lower = f"{jd_info['title']} {jd_info['description']}".lower()
        matched = [s for s in resume.core_skills if s.lower() in jd_desc_lower]
        unmatched = [
            s
            for s in ["TensorRT", "Kubernetes", "MSA 아키텍처", "대용량 트래픽 처리", "MLOps"]
            if s.lower() not in [k.lower() for k in resume.core_skills]
        ]
        exp_diff = resume.total_experience_years - jd_info["min_experience"]
        school_str = resume.educations[0].school_name if resume.educations else "해당 학력"
        base_score = int(min(95, max(50, semantic_score + (6 if exp_diff >= 0 else -8))))

        return LLMMatchEvaluation(
            llm_score=base_score,
            three_line_summary=[
                f"{resume.candidate_name} 지원자({school_str})는 총 {resume.total_experience_years}년의 경력을 보유하고 있으며, '{jd_info['title']}' 포지션과 ChromaDB 벡터 유사도 {semantic_score}점을 기록했습니다.",
                f"보유 기술 중 {', '.join(matched[:4]) if matched else ', '.join(resume.core_skills[:3])} 역량 및 수행 프로젝트 경험이 해당 직무의 요구사항과 높은 연관성을 보입니다.",
                f"실무 면접에서는 {', '.join(unmatched[:2])} 관련 심화 활용 경험과 프로젝트 문제 해결 과정을 중점적으로 검증하는 것을 권장합니다.",
            ],
            matched_strengths=[
                f"핵심 보유 기술({', '.join(matched[:4]) if matched else ', '.join(resume.core_skills[:3])})이 채용 공고 요구사항과 부합함",
                f"{school_str} 전공 기반 엔지니어링 역량 및 관련 프로젝트 수행 경험 보유",
                f"ChromaDB 임베딩 시맨틱 매칭 점수 {semantic_score}점으로 직무 도메인 적합성 확인",
            ],
            missing_gaps=[
                f"{', '.join(unmatched[:2])} 등 우대 기술 스택의 실무 적용 경험 확인 필요",
                f"공고 최소 요구 경력({jd_info['min_experience']}년) 대비 실무 프로젝트 기여도 심층 검증 권장",
            ],
        )

    async def evaluate_candidate_with_llm(
        self, resume: ResumeData, jd_info: Dict[str, Any], semantic_score: float
    ) -> LLMMatchEvaluation:
        """
        2단계: LLM을 활용하여 JD 요구사항 대비 지원자의 적합도 점수와 3줄 요약 리포트를 생성합니다.
        """
        api_key = settings.OPENAI_API_KEY

        if _is_openai_key(api_key):
            try:
                llm = ChatOpenAI(
                    model=settings.OPENAI_MODEL,
                    temperature=0.1,
                    api_key=api_key,
                )
                structured_evaluator = llm.with_structured_output(LLMMatchEvaluation)

                system_prompt = """당신은 객관적이고 냉철한 시니어 기술 면접관이자 HR 채용 전문가입니다.
채용 공고(JD)의 요구사항과 지원자의 정형화된 이력서 데이터(JSON)를 심층 비교하여 적합도를 평가하세요.
반드시 인사담당자가 한눈에 파악할 수 있도록 정확히 3개의 핵심 문장으로 three_line_summary를 작성하세요."""

                human_prompt = """[채용 공고 (JD) 정보]
- 포지션명: {job_title}
- 최소 요구 경력: {min_exp}년
- 상세 설명 및 자격요건: {jd_desc}

[참고 지표]
- 벡터 임베딩 의미 유사도 점수: {semantic_score}점 / 100점

[지원자 이력서 정형 데이터]
{resume_json}"""

                prompt = ChatPromptTemplate.from_messages([
                    ("system", system_prompt),
                    ("human", human_prompt),
                ])

                chain = prompt | structured_evaluator
                return await chain.ainvoke(
                    {
                        "job_title": jd_info["title"],
                        "min_exp": jd_info["min_experience"],
                        "jd_desc": jd_info["description"],
                        "semantic_score": semantic_score,
                        "resume_json": resume.model_dump_json(indent=2),
                    }
                )
            except Exception:
                return self._fallback_evaluate(resume, jd_info, semantic_score)

        return self._fallback_evaluate(resume, jd_info, semantic_score)

    async def match(self, resume: ResumeData, job_id: str) -> MatchResponse:
        """임베딩 유사도(30% 가중치)와 LLM 심층 평가 점수(70% 가중치)를 결합하여 최종 결과를 반환합니다."""
        if job_id not in SAMPLE_JDS:
            raise ValueError(f"존재하지 않는 채용 공고 ID입니다: {job_id}")

        jd_info = SAMPLE_JDS[job_id]

        # 1. ChromaDB 의미 기반 코사인 유사도 계산
        semantic_score = self.calculate_semantic_similarity(resume, job_id)

        # 2. LLM 정밀 평가 및 3줄 요약 리포트 생성
        llm_eval = await self.evaluate_candidate_with_llm(resume, jd_info, semantic_score)

        # 3. 하이브리드 최종 점수 산출 (LLM 평가 70% + 임베딩 유사도 30%)
        final_score = round((llm_eval.llm_score * 0.7) + (semantic_score * 0.3), 1)

        return MatchResponse(
            job_id=job_id,
            job_title=jd_info["title"],
            semantic_similarity_score=semantic_score,
            llm_evaluation_score=llm_eval.llm_score,
            final_matching_score=final_score,
            three_line_summary=llm_eval.three_line_summary,
            matched_strengths=llm_eval.matched_strengths,
            missing_gaps=llm_eval.missing_gaps,
        )

