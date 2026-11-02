import React, { useState } from "react";
import {
  UploadCloud,
  FileText,
  Loader2,
  Search,
  Globe,
  Calendar,
  Clock,
  MapPin,
  Briefcase,
  ExternalLink,
} from "lucide-react";

export default function FileUpload({
  jobs,
  selectedJobId,
  onJobChange,
  file,
  onFileSelect,
  isDragging,
  setIsDragging,
  errorMsg,
  setErrorMsg,
  loadingStep,
  onAnalyze,
  onScrapeKeyword,
  isScraping,
  scrapeStatusMsg,
}) {
  const [keyword, setKeyword] = useState("Python 백엔드");
  const selectedJobObj = jobs.find((j) => j.job_id === selectedJobId);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => setIsDragging(false);

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && droppedFile.type === "application/pdf") {
      onFileSelect(droppedFile);
      setErrorMsg("");
    } else {
      setErrorMsg("PDF 파일(.pdf)만 업로드할 수 있습니다.");
    }
  };

  const handleScrapeSubmit = (e) => {
    e.preventDefault();
    if (!keyword.trim()) return;
    onScrapeKeyword(keyword.trim());
  };

  return (
    <div className="space-y-6">
      {/* 0. 잡코리아 & 사람인 실시간 스크래핑 & ChromaDB 적재 카드 */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-blue-200">
        <div className="flex items-center gap-2 mb-2">
          <Globe className="w-4 h-4 text-blue-600" />
          <label className="block text-sm font-bold text-slate-800">
            잡코리아 & 사람인 실시간 공고 스크랩 · DB 적재
          </label>
        </div>
        <p className="text-xs text-slate-500 mb-3">
          직무 키워드로 잡코리아(JobKorea)와 사람인(Saramin) 공고를 동시에 수집합니다. 동일 공고가 두 사이트에 올라와 있으면 두 개 모두 추천합니다.
        </p>
        <form onSubmit={handleScrapeSubmit} className="flex gap-2">
          <input
            type="text"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="예: Python, AI 비전, 임베디드, 백엔드"
            className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="submit"
            disabled={isScraping}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white text-xs font-semibold px-3.5 py-2 rounded-lg flex items-center gap-1.5 shrink-0 transition"
          >
            {isScraping ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                스크랩 중...
              </>
            ) : (
              <>
                <Search className="w-3.5 h-3.5" />
                공고 스크랩
              </>
            )}
          </button>
        </form>
        {scrapeStatusMsg && (
          <p className="mt-2 text-[11px] font-medium text-blue-700 bg-blue-50 px-2.5 py-1.5 rounded border border-blue-100">
            {scrapeStatusMsg}
          </p>
        )}
      </div>

      {/* 1. 채용 공고(JD) 선택 카드 */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200">
        <label className="block text-sm font-semibold text-slate-700 mb-2">
          1. 평가 대상 채용 공고 (JD) 선택 ({jobs.length}개 적재됨)
        </label>
        <select
          value={selectedJobId}
          onChange={(e) => onJobChange(e.target.value)}
          className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          {jobs.map((job) => (
            <option key={job.job_id} value={job.job_id}>
              [{job.d_day_label || "상시"}] {job.title} - {job.department}
            </option>
          ))}
        </select>

        {selectedJobObj && (
          <div className="mt-3 p-3.5 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-600 space-y-2.5">
            {/* 선택된 공고의 D-Day 및 마감일 하이라이트 */}
            <div className="flex items-center justify-between gap-2 pb-2 border-b border-slate-200/80">
              <span
                className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold flex items-center gap-1 ${
                  selectedJobObj.urgency_level === "urgent"
                    ? "bg-rose-600 text-white"
                    : selectedJobObj.urgency_level === "relaxed"
                    ? "bg-emerald-600 text-white"
                    : "bg-indigo-600 text-white"
                }`}
              >
                <Clock className="w-3 h-3" />
                {selectedJobObj.d_day_label || "상시채용"}
              </span>

              {selectedJobObj.url && (
                <a
                  href={selectedJobObj.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[11px] font-semibold text-blue-600 hover:underline flex items-center gap-1"
                >
                  {selectedJobObj.source === "Saramin" ? "사람인 원문 보기" : "잡코리아 원문 보기"}
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>

            {selectedJobObj.is_dual_posted && (
              <div className="bg-purple-50 border border-purple-200 text-purple-800 px-2.5 py-1.5 rounded-lg text-[11px] font-semibold">
                ⚡ 잡코리아 · 사람인 동일 공고 중복 게재 (두 공고 모두 추천 대상)
              </div>
            )}

            <div className="space-y-1 text-[11px] text-slate-700">
              <p className="flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
                <span className="text-slate-500">접수기간:</span>
                <strong>
                  {selectedJobObj.start_date || "상시"} ~ {selectedJobObj.end_date || "채용시 마감"}
                </strong>
              </p>
              <p className="flex items-center gap-1.5">
                <MapPin className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
                <span className="text-slate-500">근무지역:</span>
                <span>{selectedJobObj.location || "서울/수도권"}</span>
              </p>
              <p className="flex items-center gap-1.5">
                <Briefcase className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
                <span className="text-slate-500">자격경력:</span>
                <span>
                  {selectedJobObj.experience_label ||
                    `경력 ${selectedJobObj.min_experience}년 이상`}
                </span>
              </p>
            </div>

            <div className="pt-2 border-t border-slate-200/80 leading-relaxed">
              <p className="font-semibold text-slate-700 mb-0.5">상세 요건:</p>
              {selectedJobObj.description}
            </div>
          </div>
        )}
      </div>

      {/* 2. 이력서 드래그 앤 드롭 업로드 카드 */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200">
        <label className="block text-sm font-semibold text-slate-700 mb-2">
          2. 지원자 이력서 (PDF) 업로드
        </label>
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer ${
            isDragging
              ? "border-indigo-500 bg-indigo-50"
              : "border-slate-300 hover:border-indigo-400 bg-slate-50/50"
          }`}
        >
          <input
            type="file"
            accept="application/pdf"
            id="resume-upload"
            className="hidden"
            onChange={(e) => {
              if (e.target.files[0]) {
                onFileSelect(e.target.files[0]);
                setErrorMsg("");
              }
            }}
          />
          <label htmlFor="resume-upload" className="cursor-pointer flex flex-col items-center">
            <UploadCloud className="w-10 h-10 text-indigo-500 mb-3" />
            <span className="text-sm font-medium text-slate-700">
              PDF 이력서를 이곳에 드래그하거나 클릭하여 선택
            </span>
            <span className="text-xs text-slate-400 mt-1">자유 양식 PDF 지원</span>
          </label>
        </div>

        {file && (
          <div className="mt-4 flex items-center justify-between bg-indigo-50/70 px-3 py-2 rounded-lg border border-indigo-100">
            <div className="flex items-center gap-2 truncate">
              <FileText className="w-4 h-4 text-indigo-600 shrink-0" />
              <span className="text-xs font-medium text-indigo-950 truncate">{file.name}</span>
            </div>
            <span className="text-[11px] text-indigo-600 font-semibold">
              {(file.size / 1024).toFixed(1)} KB
            </span>
          </div>
        )}

        {errorMsg && (
          <div className="mt-3 p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-600">
            {errorMsg}
          </div>
        )}

        <button
          onClick={onAnalyze}
          disabled={!file || loadingStep !== ""}
          className="mt-4 w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white font-semibold py-2.5 rounded-lg text-sm transition flex items-center justify-center gap-2"
        >
          {loadingStep === "extracting" && (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              1/3 이력서 구조화 추출 중...
            </>
          )}
          {loadingStep === "matching" && (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              2/3 ChromaDB 유사도 및 적합도 평가 중...
            </>
          )}
          {loadingStep === "recommending" && (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              3/3 잡코리아·사람인 실시간 공고 스크랩 및 맞춤 추천 중...
            </>
          )}
          {loadingStep === "" && "AI 이력서 분석 & 잡코리아·사람인 맞춤 공고 추천"}
        </button>
      </div>
    </div>
  );
}

