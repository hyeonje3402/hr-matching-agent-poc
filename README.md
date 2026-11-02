# B2B HR 채용 매칭 에이전트 PoC (AI Talent Matcher Pro)

지원자의 자유 양식 이력서(PDF)를 업로드하면 LLM의 **Structured Output** 기능으로 핵심 역량을 정형화된 JSON으로 추출하고, **ChromaDB 벡터 유사도 검색(Semantic Search)** 과 **LLM 심층 평가**를 결합하여 사내 채용 공고(JD) 및 **잡코리아(JobKorea) · 사람인(Saramin) 실시간 채용 공고**와의 적합도 점수, 마감일(D-Day) 카운트다운, 동일 공고 중복 게재 시 동시 추천, 3줄 평가 리포트를 제공하는 B2B HR 솔루션 PoC 프로젝트입니다.

---

## 1. 기술 스택
- **Backend**: Python 3.10+, FastAPI, LangChain (`langchain-openai`, `langchain-chroma`), OpenAI API (`gpt-4o-mini` / `text-embedding-3-small`) & Google Gemini API (`gemini-3.8-flash` / `gemini-embedding-001`), `pdfplumber`, ChromaDB, `httpx`
- **Frontend**: React 18, Vite, Axios, Tailwind CSS, Lucide Icons

---

## 2. 실행 방법

### 2.1 Backend 서버 실행
```bash
cd backend
python -m venv venv

# Windows PowerShell
.\venv\Scripts\Activate.ps1
# Windows CMD
.\venv\Scripts\activate.bat

pip install -r requirements.txt

# 환경변수 파일(.env) 확인
# FastAPI 서버 기동 (http://localhost:8000)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- Swagger API 문서 확인: http://localhost:8000/docs

### 2.2 Frontend 개발 서버 실행
```bash
cd frontend
npm install
npm run dev
```
- 브라우저 접속: http://localhost:5173

