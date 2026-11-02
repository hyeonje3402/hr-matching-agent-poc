import React from "react";
import { Sparkles, CheckCircle2, AlertCircle } from "lucide-react";

export default function ReportCard({ matchResult }) {
  if (!matchResult) return null;

  return (
    <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 space-y-5">
      <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
        <Sparkles className="w-5 h-5 text-indigo-600" />
        AI 면접관 3줄 요약 평가 리포트
      </h3>

      <ol className="space-y-2.5 bg-indigo-50/50 p-4 rounded-xl border border-indigo-100">
        {matchResult.three_line_summary.map((line, idx) => (
          <li
            key={idx}
            className="text-sm text-slate-800 flex items-start gap-2.5 leading-relaxed"
          >
            <span className="bg-indigo-600 text-white text-xs font-bold w-5 h-5 rounded-full flex items-center justify-center shrink-0 mt-0.5">
              {idx + 1}
            </span>
            <span>{line}</span>
          </li>
        ))}
      </ol>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-4 rounded-lg bg-emerald-50/60 border border-emerald-200">
          <h4 className="text-xs font-bold text-emerald-800 flex items-center gap-1.5 mb-2">
            <CheckCircle2 className="w-4 h-4" /> JD 부합 핵심 강점
          </h4>
          <ul className="space-y-1 text-xs text-emerald-900 list-disc list-inside">
            {matchResult.matched_strengths.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>

        <div className="p-4 rounded-lg bg-amber-50/60 border border-amber-200">
          <h4 className="text-xs font-bold text-amber-800 flex items-center gap-1.5 mb-2">
            <AlertCircle className="w-4 h-4" /> 보완 필요 역량 및 면접 확인 포인트
          </h4>
          <ul className="space-y-1 text-xs text-amber-900 list-disc list-inside">
            {matchResult.missing_gaps.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

