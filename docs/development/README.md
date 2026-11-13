# 설치·환경 변수·실행 방법

[메인 README](../../README.md)

## 준비물

- Python 3.10 이상 권장
- Node.js 18 이상
- OpenAI API 키 또는 코드가 지원하는 Google Gemini API 키

## 환경 변수

저장소 루트의 .env.example을 참고해 backend/.env를 만들고 값을 설정합니다. 현재 Settings는 backend/.env에서 **OPENAI_API_KEY**, **OPENAI_MODEL**, **EMBEDDING_MODEL**, **CHROMA_PERSIST_DIR**를 읽습니다.

OPENAI_API_KEY 값은 코드에서 접두어로 OpenAI 키와 Google 키를 판별합니다. Google Gemini 키를 쓸 때도 변수 이름이 OPENAI_API_KEY인 구조라 혼란을 줄 수 있습니다. 채팅 모델 평가 경로는 OpenAI용 ChatOpenAI를 사용하며, Google 키 사용 시 해당 경로가 규칙 기반 폴백을 반환할 수 있습니다.

예시:

~~~env
OPENAI_API_KEY=실제_제공자_API_키
OPENAI_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
CHROMA_PERSIST_DIR=./chroma_db
~~~

키를 Git에 커밋하지 말고, 이력서 PDF 원문에는 개인정보가 포함될 수 있으므로 신뢰할 수 있는 환경에서만 테스트하세요.

## 백엔드

저장소 루트에서:

~~~bash
cd backend
python -m venv .venv
~~~

Windows PowerShell에서 가상환경을 켜고:

~~~powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
~~~

Swagger UI: **http://127.0.0.1:8000/docs**

## 프런트엔드

새 터미널에서:

~~~bash
cd frontend
npm install
npm run dev
~~~

Vite 개발 서버는 기본 **http://localhost:5173**에서 실행됩니다.

## 주요 API

| 경로 | 설명 |
|---|---|
| GET /api/jobs | 메모리 기반 현재 공고 목록 |
| POST /api/jobs/scrape-jobkorea | JobKorea/Saramin 공고 수집 후 목록·색인 반영 |
| POST /api/resume/upload | PDF 이력서 텍스트 추출 및 구조화 |
| POST /api/resume/match | 이력서와 지정 JD 매칭 평가 |
| POST /api/resume/recommend | 추천 공고 목록 |

요청 필드와 응답 모델은 **http://127.0.0.1:8000/docs**에서 확인하세요.