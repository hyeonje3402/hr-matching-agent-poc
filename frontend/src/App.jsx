import React, { useState, useEffect } from "react";
import { Briefcase, Sparkles } from "lucide-react";
import {
  fetchJobs,
  scrapeJobKorea,
  uploadResumePdf,
  matchResumeWithJob,
  recommendJobsForResume,
} from "./api/resumeApi";
import FileUpload from "./components/FileUpload";
import ScoreGauge from "./components/ScoreGauge";
import ReportCard from "./components/ReportCard";
import SpecCard from "./components/SpecCard";
import JobRecommendations from "./components/JobRecommendations";

export default function App() {
  const [jobs, setJobs] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState("jd_ai_vision");
  const [file, setFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);

  const [resumeData, setResumeData] = useState(null);
  const [matchResult, setMatchResult] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [loadingStep, setLoadingStep] = useState(""); // "", "extracting", "matching", "recommending"
  const [errorMsg, setErrorMsg] = useState("");

  const [isScraping, setIsScraping] = useState(false);
  const [scrapeStatusMsg, setScrapeStatusMsg] = useState("");

  // 초기 채용 공고 목록 로드
  useEffect(() => {
    fetchJobs()
      .then((data) => {
        setJobs(data);
        if (data.length > 0) setSelectedJobId(data[0].job_id);
      })
      .catch(() =>
        setErrorMsg("백엔드 서버와 연결할 수 없습니다. (FastAPI 포트 8000 실행 여부를 확인하세요)")
      );
  }, []);

  // 좌측에서 잡코리아 & 사람인 키워드 수동 스크랩 & ChromaDB 적재
  const handleScrapeKeyword = async (keyword) => {
    setIsScraping(true);
    setScrapeStatusMsg("");
    setErrorMsg("");
    try {
      const res = await scrapeJobKorea(keyword, 5);
      setJobs(res.all_jobs);
      const dualNote =
        res.dual_posted_pairs > 0
          ? ` (동일 공고 중복 게재 ${res.dual_posted_pairs}쌍 발견 · 동시 추천 적용)`
          : "";
      setScrapeStatusMsg(
        `'${keyword}' 키워드로 잡코리아 ${res.jobkorea_count ?? 0}건, 사람인 ${
          res.saramin_count ?? 0
        }건(총 ${res.scraped_count}건)을 스크랩하여 적재했습니다!${dualNote}`
      );
      if (res.scraped_jobs && res.scraped_jobs.length > 0) {
        setSelectedJobId(res.scraped_jobs[0].job_id);
      }
      // 이미 분석된 이력서가 있다면 추천 목록도 즉시 갱신
      if (resumeData) {
        const recs = await recommendJobsForResume(resumeData, 6, false);
        setRecommendations(recs);
      }
    } catch (err) {
      setErrorMsg("잡코리아·사람인 공고 스크래핑 중 오류가 발생했습니다.");
    } finally {
      setIsScraping(false);
    }
  };

  // 이력서 업로드 -> 정형 추출 -> JD 매칭 -> 잡코리아·사람인 스크랩 & 맞춤 공고 추천 파이프라인 실행
  const handleAnalyze = async () => {
    if (!file) {
      setErrorMsg("먼저 지원자의 PDF 이력서를 업로드해주세요.");
      return;
    }
    setErrorMsg("");
    setMatchResult(null);

    try {
      // Step 1: PDF 업로드 및 JSON 추출
      setLoadingStep("extracting");
      const extractedData = await uploadResumePdf(file);
      setResumeData(extractedData);

      // Step 2: 선택된 JD와 시맨틱 매칭 및 LLM 평가
      setLoadingStep("matching");
      const matchedData = await matchResumeWithJob(selectedJobId, extractedData);
      setMatchResult(matchedData);

      // Step 3: 지원자 스킬 기반 잡코리아·사람인 실시간 스크랩 + ChromaDB 맞춤 공고 추천
      setLoadingStep("recommending");
      const recs = await recommendJobsForResume(extractedData, 6, true);
      setRecommendations(recs);

      // 새로 스크랩된 잡코리아·사람인 공고들을 좌측 드롭다운 목록에도 동기화
      const updatedJobs = await fetchJobs();
      setJobs(updatedJobs);
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || "분석 중 오류가 발생했습니다.");
    } finally {
      setLoadingStep("");
    }
  };

  // 특정 공고(드롭다운 또는 추천 카드 클릭)로 정밀 매칭 전환
  const handleJobChange = async (newJobId) => {
    setSelectedJobId(newJobId);
    if (resumeData) {
      setLoadingStep("matching");
      setErrorMsg("");
      try {
        const matchedData = await matchResumeWithJob(newJobId, resumeData);
        setMatchResult(matchedData);
      } catch (err) {
        setErrorMsg(err.response?.data?.detail || "직무 재매칭 중 오류가 발생했습니다.");
      } finally {
        setLoadingStep("");
      }
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      {/* 상단 헤더 */}
      <header className="bg-white border-b border-slate-200 px-8 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="bg-indigo-600 text-white p-2 rounded-lg">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-900">AI Talent Matcher Pro</h1>
            <p className="text-xs text-slate-500">
              LLM Structured Output · ChromaDB Semantic Search · 잡코리아 & 사람인 실시간 공고 추천
            </p>
          </div>
        </div>
      </header>

      {/* 메인 대시보드 그리드 (좌측 4 : 우측 8) */}
      <main className="max-w-7xl mx-auto p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* 좌측: 잡코리아 스크랩 + 채용 공고 선택 + PDF 업로드 */}
        <section className="lg:col-span-4">
          <FileUpload
            jobs={jobs}
            selectedJobId={selectedJobId}
            onJobChange={handleJobChange}
            file={file}
            onFileSelect={setFile}
            isDragging={isDragging}
            setIsDragging={setIsDragging}
            errorMsg={errorMsg}
            setErrorMsg={setErrorMsg}
            loadingStep={loadingStep}
            onAnalyze={handleAnalyze}
            onScrapeKeyword={handleScrapeKeyword}
            isScraping={isScraping}
            scrapeStatusMsg={scrapeStatusMsg}
          />
        </section>

        {/* 우측: 분석 결과 대시보드 (맞춤 공고 추천 + 매칭 점수 Progress Bar + 3줄 요약 리포트 + 스펙 요약) */}
        <section className="lg:col-span-8 space-y-6">
          {!resumeData && loadingStep === "" ? (
            <div className="bg-white rounded-xl border border-slate-200 p-16 text-center text-slate-400">
              <Briefcase className="w-12 h-12 mx-auto mb-3 stroke-1" />
              <p className="text-base font-medium text-slate-600">분석된 이력서가 없습니다</p>
              <p className="text-xs mt-1">
                좌측에서 잡코리아 공고를 스크랩하거나 PDF 이력서를 업로드해 맞춤형 공고 추천을 받아보세요.
              </p>
            </div>
          ) : (
            <>
              <JobRecommendations
                recommendations={recommendations}
                selectedJobId={selectedJobId}
                onSelectRecommendedJob={handleJobChange}
              />
              <ScoreGauge matchResult={matchResult} />
              <ReportCard matchResult={matchResult} />
              <SpecCard resumeData={resumeData} />
            </>
          )}
        </section>
      </main>
    </div>
  );
}

