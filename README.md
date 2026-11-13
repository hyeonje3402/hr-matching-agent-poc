# AI Talent Matcher Pro — HR 채용 매칭 PoC

PDF 이력서를 구조화하고, 채용 공고와의 의미 유사도 및 LLM 평가를 결합해 적합도 리포트와 추천 공고를 제공하는 웹 PoC입니다.

## 프로젝트 개요

| 항목 | 내용 |
|---|---|
| 주요 기능 | PDF 이력서 추출, JD 점수화, 강점·보완점 리포트, 공고 추천, 외부 공고 수집 |
| Frontend | React 18, Vite 5, Axios, Tailwind CSS, Lucide |
| Backend | Python, FastAPI, Pydantic v2 |
| 문서 처리 | pdfplumber, PyPDF2 |
| 의미 검색 | ChromaDB 로컬 저장, OpenAI 또는 Gemini 임베딩 코드 |
| LLM 평가 | OpenAI Chat API, Structured Output; 제한 시 규칙 기반 폴백 |
| 공고 수집 | httpx 기반 JobKorea/Saramin 수집 및 중복 공고 연결 |
| 저장·배포 | 공고 예시는 메모리 기반, 벡터 데이터는 로컬 ChromaDB. CI/CD·클라우드 설정은 확인되지 않음 |

## 전체 아키텍처

~~~mermaid
flowchart LR
    U[채용 담당자] --> F[React 웹 화면]
    F --> A[FastAPI]
    PDF[이력서 PDF] --> P[pdfplumber/PyPDF2]
    P --> X[ResumeData 구조화]
    X --> E[임베딩·JD 유사도]
    J[사내 샘플 JD·스크랩 공고] --> V[(ChromaDB)]
    E --> V
    V --> M[LLM 심층 평가·점수 결합]
    M --> F
    S[JobKorea·Saramin] --> A
~~~

## 문서

- [아키텍처·매칭 흐름](docs/architecture/README.md)
- [설치·환경 변수·실행 방법](docs/development/README.md)
- [운영·데이터 처리 한계](docs/operations/README.md)
- [로드맵 제안](docs/roadmap/README.md)

## 빠른 시작

백엔드 실행:

~~~bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
~~~

프런트엔드 실행:

~~~bash
cd frontend
npm install
npm run dev
~~~

AI 제공자 키 설정과 Swagger 주소는 [개발 문서](docs/development/README.md)를 확인하세요.

> 이 프로젝트는 PoC입니다. 제공자 키가 없거나 LLM 호출이 실패하면 일부 기능은 규칙 기반 응답으로 동작할 수 있습니다. 채용 판단은 담당자가 원문 이력서와 공고를 확인한 뒤 내려야 합니다.