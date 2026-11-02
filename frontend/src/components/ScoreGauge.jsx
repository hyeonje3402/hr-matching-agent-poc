import React from "react";

export default function ScoreGauge({ matchResult }) {
  if (!matchResult) return null;

  const getScoreBarClass = (score) => {
    if (score >= 80) return "bg-emerald-500";
    if (score >= 60) return "bg-indigo-600";
    return "bg-amber-500";
  };

  return (
    <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-indigo-600">
            Target Position Matching
          </span>
          <h2 className="text-xl font-bold text-slate-900 mt-0.5">
            {matchResult.job_title} 적합도 점수
          </h2>
        </div>
        <div className="text-right">
          <span className="text-3xl font-extrabold text-indigo-600">
            {matchResult.final_matching_score}
          </span>
          <span className="text-sm text-slate-500 font-medium"> / 100점</span>
        </div>
      </div>

      {/* 메인 Progress Bar */}
      <div className="w-full bg-slate-100 h-4 rounded-full overflow-hidden mb-4">
        <div
          className={`h-full transition-all duration-700 ${getScoreBarClass(
            matchResult.final_matching_score
          )}`}
          style={{ width: `${matchResult.final_matching_score}%` }}
        />
      </div>

      {/* 세부 점수 (임베딩 유사도 vs LLM 평가) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-100 text-xs text-slate-600">
        <div className="flex justify-between items-center bg-slate-50 px-3 py-2 rounded-lg">
          <span>ChromaDB 시맨틱 유사도 (30%)</span>
          <strong className="text-slate-900">{matchResult.semantic_similarity_score}점</strong>
        </div>
        <div className="flex justify-between items-center bg-slate-50 px-3 py-2 rounded-lg">
          <span>LLM 직무 역량 정밀 평가 (70%)</span>
          <strong className="text-slate-900">{matchResult.llm_evaluation_score}점</strong>
        </div>
      </div>
    </div>
  );
}

