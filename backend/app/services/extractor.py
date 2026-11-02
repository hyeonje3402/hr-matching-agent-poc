import re
from typing import List
import httpx
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.config import settings
from app.schemas import ResumeData, ProjectExperience, EducationInfo


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


def _extract_educations_from_text(text: str) -> List[EducationInfo]:
    """PDF 원문 텍스트에서 실제 학교명(연암공대, 연암공과대학교, OO대학교 등), 전공, 학위, 졸업여부를 추출합니다."""
    educations: List[EducationInfo] = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    school_pattern = re.compile(
        r"([가-힣A-Za-z0-9·\s]{1,20}?(?:대학교|대학원|공과대학|공대|전문대학|대학|고등학교|University|Institute|College|KAIST|POSTECH|UNIST|GIST|DGIST))"
    )
    degree_pattern = re.compile(
        r"(박사|석사|학사|전문학사|학부|졸업예정|재학|휴학|졸업|수료|B\.S\.|M\.S\.|Ph\.D\.)"
    )
    major_pattern = re.compile(
        r"([가-힣A-Za-z·/&\s]{2,22}?(?:공학과|공학부|공학|학과|학부|전공|과학과|소프트웨어|인공지능|컴퓨터|전자|전기|기계|정보통신|시스템|데이터|스마트|AI|Computer\s*Science))"
    )

    seen_schools = set()

    for idx, line in enumerate(lines):
        if line.startswith("--- [Page"):
            continue

        school_match = school_pattern.search(line)
        if not school_match:
            continue

        raw_school = school_match.group(1).strip()
        raw_school = re.sub(
            r"^(?:학력사항|학력|최종학력|학교명|학교|졸업학교|출신학교|\d{4}[\.\-/]\d{1,2})\s*[:：\-]?\s*",
            "",
            raw_school,
        ).strip()

        if raw_school in ("대학교", "대학", "대학원", "고등학교", "공대") or len(raw_school) < 2:
            continue

        context_window = " | ".join(lines[max(0, idx - 1) : min(len(lines), idx + 3)])

        major = "전공/학과"
        context_without_school = context_window.replace(raw_school, " ")
        major_matches = major_pattern.findall(context_without_school)
        for m in major_matches:
            cleaned_m = re.sub(r"^(?:전공|학과|학부|계열)\s*[:：\-]?\s*", "", m).strip()
            if cleaned_m and cleaned_m not in raw_school and len(cleaned_m) >= 2:
                major = cleaned_m
                break

        degree_matches = degree_pattern.findall(context_window)
        degree = "학사/전문학사"
        grad_status = None
        for d in degree_matches:
            if d in ("박사", "석사", "학사", "전문학사", "B.S.", "M.S.", "Ph.D."):
                degree = d
            elif d in ("졸업예정", "재학", "휴학", "졸업", "수료"):
                grad_status = d

        if raw_school not in seen_schools:
            seen_schools.add(raw_school)
            educations.append(
                EducationInfo(
                    school_name=raw_school,
                    major=major,
                    degree=degree,
                    graduation_status=grad_status or "졸업/재학",
                )
            )

    if not educations:
        educations.append(
            EducationInfo(
                school_name="이력서 내 학력 텍스트 미감지",
                major="전공 미상",
                degree="학위 미상",
                graduation_status="-",
            )
        )
    return educations


def _extract_projects_from_text(text: str, found_skills: List[str]) -> List[ProjectExperience]:
    """PDF 원문 텍스트에서 프로젝트/경력 단락을 동적으로 추출합니다."""
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.startswith("--- [Page")
    ]
    projects: List[ProjectExperience] = []

    date_range_re = re.compile(
        r"(\d{4}\s*[\.\-/년]\s*\d{1,2}\s*(?:[\.\-/월]?\s*[~\-–—]\s*(?:\d{4}\s*[\.\-/년]\s*\d{1,2}|현재|재직중|진행중))?)"
    )
    proj_header_re = re.compile(
        r"(?:프로젝트|Project|경력|수행업무|연구|개발|포트폴리오)\s*\d*\s*[:：\-]?\s*(.+)",
        re.IGNORECASE,
    )

    for idx, line in enumerate(lines):
        if len(projects) >= 4:
            break

        header_m = proj_header_re.match(line)
        date_m = date_range_re.search(line)

        if header_m or (date_m and len(line) < 90):
            title = header_m.group(1).strip() if header_m else line
            period = date_m.group(1).strip() if date_m else None
            if period and period in title:
                title = title.replace(period, "").strip(" ()[]-:")

            if len(title) < 3 or any(
                k in title for k in ("학력", "연암", "대학교", "고등학교", "자격증", "어학", "생년월일")
            ):
                continue

            desc_lines = []
            for sub in lines[idx + 1 : min(len(lines), idx + 4)]:
                if date_range_re.search(sub) or proj_header_re.match(sub):
                    break
                desc_lines.append(sub.lstrip("-•·* "))

            summary_text = " ".join(desc_lines).strip() if desc_lines else line
            block_text = f"{title} {summary_text}"
            proj_skills = [
                s
                for s in found_skills
                if re.search(rf"(?<![A-Za-z]){re.escape(s)}(?![A-Za-z])", block_text, re.IGNORECASE)
            ]

            projects.append(
                ProjectExperience(
                    project_name=title[:60],
                    role="담당 엔지니어 / 개발자",
                    period=period,
                    tech_stack=proj_skills[:6] if proj_skills else found_skills[:4],
                    summary=summary_text[:180] if summary_text else "이력서 기반 프로젝트 수행",
                )
            )

    if not projects:
        bullet_lines = [
            l.lstrip("-•·* ")
            for l in lines
            if len(l) >= 12
            and not any(w in l for w in ("학력", "학교", "연락처", "이메일", "주소", "생년월일"))
        ]
        if bullet_lines:
            projects.append(
                ProjectExperience(
                    project_name="이력서 주요 프로젝트 및 실무 경험",
                    role="개발 / 엔지니어링",
                    period=None,
                    tech_stack=found_skills[:5],
                    summary=" / ".join(bullet_lines[:3])[:220],
                )
            )

    return projects


def _fallback_parse_resume(raw_resume_text: str) -> ResumeData:
    """
    업로드된 PDF의 원문 텍스트에서 이름, 학력(연암공대 등), 기술 스택, 경력, 프로젝트를 직접 추출합니다.
    """
    known_skills = [
        "Python", "PyTorch", "TensorFlow", "OpenCV", "YOLO", "YOLOv8", "ViT", "TensorRT", "ONNX",
        "FastAPI", "Django", "Flask", "Spring", "Spring Boot", "Node.js", "Express",
        "LangChain", "LlamaIndex", "OpenAI API", "LLM", "RAG", "ChromaDB", "Pinecone",
        "Java", "C", "C++", "C#", "JavaScript", "TypeScript", "React", "Vue", "Next.js", "HTML", "CSS", "Tailwind",
        "PostgreSQL", "MySQL", "MariaDB", "Oracle", "MongoDB", "Redis", "SQLite",
        "Docker", "Kubernetes", "AWS", "GCP", "Azure", "Linux", "Git", "GitHub",
        "Arduino", "Raspberry Pi", "PLC", "LabVIEW", "MATLAB", "AutoCAD", "SolidWorks", "Catia",
    ]
    found_skills = []
    for skill in known_skills:
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(skill)}(?![A-Za-z0-9])", raw_resume_text, re.IGNORECASE):
            found_skills.append(skill)

    if not found_skills:
        found_skills = ["Python", "소프트웨어 개발", "엔지니어링"]

    candidate_name = "지원자"
    name_patterns = [
        r"(?:이\s*름|성\s*명|지원자|Name)\s*[:：\-]\s*([가-힣]{2,5}|[A-Za-z\s]{3,25})",
        r"^([가-힣]{2,4})\s*(?:이력서|자기소개서|포트폴리오)",
    ]
    for pat in name_patterns:
        m = re.search(pat, raw_resume_text, re.MULTILINE)
        if m:
            candidate_name = m.group(1).strip()
            break
    if candidate_name == "지원자":
        first_lines = [
            l.strip()
            for l in raw_resume_text.splitlines()
            if l.strip() and not l.startswith("--- [Page")
        ][:6]
        for fl in first_lines:
            if re.fullmatch(r"[가-힣]{2,4}", fl) and fl not in (
                "이력서", "지원서", "자소서", "학력사항", "경력사항", "연암공대"
            ):
                candidate_name = fl
                break

    exp_years = 0.0
    if re.search(r"총\s*경력\s*[:：]?\s*(\d+(?:\.\d+)?)\s*년", raw_resume_text):
        m = re.search(r"총\s*경력\s*[:：]?\s*(\d+(?:\.\d+)?)\s*년", raw_resume_text)
        exp_years = float(m.group(1))
    elif re.search(
        r"Total\s*Experience\s*[:：]?\s*(\d+(?:\.\d+)?)\s*years?", raw_resume_text, re.IGNORECASE
    ):
        m = re.search(
            r"Total\s*Experience\s*[:：]?\s*(\d+(?:\.\d+)?)\s*years?", raw_resume_text, re.IGNORECASE
        )
        exp_years = float(m.group(1))
    elif "신입" in raw_resume_text:
        exp_years = 0.0

    educations = _extract_educations_from_text(raw_resume_text)
    projects = _extract_projects_from_text(raw_resume_text, found_skills)

    school_summary = educations[0].school_name if educations else ""
    overall_summary = (
        f"{school_summary} 출신 · {', '.join(found_skills[:5])} 역량을 보유한 "
        f"{'신입' if exp_years == 0 else f'{exp_years}년차'} 인재"
    )

    return ResumeData(
        candidate_name=candidate_name,
        total_experience_years=exp_years,
        core_skills=found_skills,
        projects=projects,
        educations=educations,
        overall_summary=overall_summary,
    )


async def _parse_with_gemini_api(raw_resume_text: str, api_key: str) -> ResumeData:
    """Google Gemini REST API (Structured JSON Output)를 호출하여 이력서를 추출합니다."""
    prompt_text = f"""당신은 IT/테크 기업의 수석 테크니컬 리크루터입니다.
아래 이력서 원문 텍스트를 정밀하게 분석하여 다음 JSON 형식에 맞춰 반환하세요.
이력서에 적힌 실제 학교명(예: 연암공대, 연암공과대학교 등), 전공, 프로젝트, 기술 스택만 정확히 추출하고 절대 없는 사실을 지어내지 마세요.

JSON 스키마 예시:
{{
  "candidate_name": "이름",
  "total_experience_years": 0.0,
  "core_skills": ["기술1", "기술2"],
  "projects": [
    {{
      "project_name": "프로젝트명",
      "role": "담당 역할",
      "period": "기간",
      "tech_stack": ["사용기술"],
      "summary": "핵심 성과 요약"
    }}
  ],
  "educations": [
    {{
      "school_name": "실제 학교명",
      "major": "전공명",
      "degree": "학사/전문학사/석사 등",
      "graduation_status": "졸업/재학/졸업예정"
    }}
  ],
  "overall_summary": "지원자 핵심 역량 한 줄 요약"
}}

[이력서 원문 텍스트]
{raw_resume_text}"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.0},
    }
    async with httpx.AsyncClient(timeout=4.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        json_str = data["candidates"][0]["content"]["parts"][0]["text"]
        return ResumeData.model_validate_json(json_str)


async def parse_resume_to_json(raw_resume_text: str) -> ResumeData:
    """
    자유 양식의 이력서 텍스트를 분석하여 정형화된 ResumeData(JSON)로 변환합니다.
    - OpenAI 키(sk-...)인 경우: LangChain ChatOpenAI.with_structured_output 사용
    - Google Gemini 키(AQ.... / AIza...)인 경우: Gemini Structured JSON API 호출
    - API 호출 제한/실패 시: 원문 기반 정밀 정규식 파서(_fallback_parse_resume)로 안전하게 폴백
    """
    api_key = settings.OPENAI_API_KEY

    if _is_openai_key(api_key):
        try:
            llm = ChatOpenAI(
                model=settings.OPENAI_MODEL,
                temperature=0,
                api_key=api_key,
            )
            structured_llm = llm.with_structured_output(ResumeData)
            system_prompt = """당신은 IT/테크 기업의 수석 테크니컬 리크루터입니다.
주어진 지원자의 이력서 원문 텍스트를 정밀하게 분석하여 지정된 JSON 스키마에 맞게 정보를 추출하세요.
이력서에 명시된 실제 학교명(예: 연암공대 등), 전공, 기술 스택만 추출하고 절대 지어내지 마세요."""
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "다음 이력서 텍스트를 분석해 정형 데이터(JSON)로 추출해 주세요:\n\n{resume_text}"),
            ])
            extraction_chain = prompt | structured_llm
            return await extraction_chain.ainvoke({"resume_text": raw_resume_text})
        except Exception:
            return _fallback_parse_resume(raw_resume_text)

    if _is_google_key(api_key):
        try:
            return await _parse_with_gemini_api(raw_resume_text, api_key)
        except Exception:
            return _fallback_parse_resume(raw_resume_text)

    return _fallback_parse_resume(raw_resume_text)

