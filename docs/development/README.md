# 설치·환경 변수·실행 방법

[Windows 설치와 실행 절차](../../README.md#로컬-실행--windows-powershell)

서비스는 `backend/.env`의 `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_EMBEDDING_MODEL`, `CHROMA_PERSIST_DIR`를 사용합니다.

| 주요 API | 설명 |
| --- | --- |
| GET /api/jobs | 기본·수집·직접 저장 공고 목록 |
| POST /api/jobs/scrape-jobkorea | 잡코리아·사람인 공고 수집 |
| POST /api/resume/upload | PDF 이력서 구조화 |
| POST /api/resume/match | 지정 공고 매칭 |
| POST /api/resume/recommend | 공고 추천 |
| POST /api/materials/job/text, /url, /file | 공고 분석 및 등록 |
| POST /api/materials/fit | 직무 요구사항과 지원자 근거 비교 |
| POST /api/interviews | 면접 시작 |
| GET /api/interviews | 면접 기록 조회 |
| GET /api/interviews/analytics | 성장·훈련 지표 |

요청 및 응답 스키마는 실행 중인 [Swagger UI](http://127.0.0.1:8000/docs)를 참고하세요.
