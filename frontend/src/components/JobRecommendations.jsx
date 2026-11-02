import React from "react";
import {
  Compass,
  ExternalLink,
  Target,
  Building2,
  Clock,
  Calendar,
  MapPin,
  Briefcase,
  Flame,
} from "lucide-react";

export default function JobRecommendations({
  recommendations,
  selectedJobId,
  onSelectRecommendedJob,
}) {
  if (!recommendations || recommendations.length === 0) return null;

  const getUrgencyStyle = (urgency) => {
    switch (urgency) {
      case "urgent":
        return {
          badge: "bg-rose-600 text-white animate-pulse",
          border: "border-rose-200 bg-rose-50/40",
          bar: "bg-rose-500",
          text: "text-rose-700",
        };
      case "relaxed":
        return {
          badge: "bg-emerald-600 text-white",
          border: "border-emerald-200 bg-emerald-50/30",
          bar: "bg-emerald-500",
          text: "text-emerald-700",
        };
      case "closed":
        return {
          badge: "bg-slate-400 text-white",
          border: "border-slate-200 bg-slate-100",
          bar: "bg-slate-400",
          text: "text-slate-500",
        };
      default:
        return {
          badge: "bg-indigo-600 text-white",
          border: "border-indigo-100 bg-indigo-50/30",
          bar: "bg-indigo-500",
          text: "text-indigo-700",
        };
    }
  };

  return (
    <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
        <div>
          <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <Compass className="w-5 h-5 text-indigo-600" />
            AI 맞춤 채용 공고 추천 (잡코리아 & 사람인 실시간 연동)
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            지원자 스펙과 유사도가 높은 공고를 추천하며, 잡코리아와 사람인에 같은 공고가 올라와 있으면 두 개를 함께 추천합니다.
          </p>
        </div>
        <span className="bg-indigo-50 text-indigo-700 text-xs font-bold px-2.5 py-1 rounded-full">
          TOP {recommendations.length} 추천
        </span>
      </div>

      <div className="space-y-4">
        {recommendations.map((item, idx) => {
          const isSelected = item.job_id === selectedJobId;
          const isJobKorea = item.source === "JobKorea";
          const isSaramin = item.source === "Saramin";
          const uStyle = getUrgencyStyle(item.urgency_level);

          const sourceBadgeClass = isJobKorea
            ? "bg-blue-100 text-blue-800 border border-blue-200"
            : isSaramin
            ? "bg-amber-100 text-amber-800 border border-amber-200"
            : "bg-slate-200 text-slate-700";

          const sourceLabel = isJobKorea
            ? "잡코리아 실시간"
            : isSaramin
            ? "사람인 실시간"
            : "사내 공고";

          return (
            <div
              key={item.job_id}
              className={`p-4 rounded-xl border transition-all ${
                isSelected
                  ? "border-indigo-600 bg-indigo-50/30 ring-2 ring-indigo-500/20"
                  : item.is_dual_posted
                  ? "border-purple-300 bg-purple-50/15 hover:border-purple-400"
                  : "border-slate-200 hover:border-indigo-300 bg-white"
              }`}
            >
              {/* 상단: 순위 + 출처 + 중복게재 배지 + 기업명 + D-Day 남은시간 배지 + 유사도 점수 */}
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-1.5 flex-1 min-w-[240px]">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="bg-slate-900 text-white text-[11px] font-bold px-2 py-0.5 rounded">
                      #{idx + 1} 추천
                    </span>
                    <span
                      className={`text-[11px] font-semibold px-2 py-0.5 rounded ${sourceBadgeClass}`}
                    >
                      {sourceLabel}
                    </span>

                    {item.is_dual_posted && (
                      <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-purple-100 text-purple-800 border border-purple-300">
                        ⚡ 잡코리아·사람인 중복 공고 (2개 동시 추천)
                      </span>
                    )}

                    {/* 직관적 D-Day 남은 시간 배지 */}
                    <span
                      className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full flex items-center gap-1 shadow-sm ${uStyle.badge}`}
                    >
                      {item.urgency_level === "urgent" ? (
                        <Flame className="w-3 h-3" />
                      ) : (
                        <Clock className="w-3 h-3" />
                      )}
                      {item.d_day_label || "상시채용"}
                    </span>
                  </div>

                  <h4 className="text-base font-bold text-slate-900 pt-0.5 leading-snug">
                    {item.title}
                  </h4>

                  <div className="flex flex-wrap items-center gap-3 text-xs text-slate-600 pt-0.5">
                    <span className="font-semibold text-slate-800 flex items-center gap-1">
                      <Building2 className="w-3.5 h-3.5 text-indigo-500" />
                      {item.department}
                    </span>
                    {item.location && (
                      <span className="flex items-center gap-1 text-slate-600">
                        <MapPin className="w-3.5 h-3.5 text-slate-400" />
                        {item.location}
                      </span>
                    )}
                    <span className="flex items-center gap-1 text-slate-600">
                      <Briefcase className="w-3.5 h-3.5 text-slate-400" />
                      {item.experience_label ||
                        (item.min_experience === 0
                          ? "신입/경력무관"
                          : `경력 ${item.min_experience}년↑`)}
                    </span>
                  </div>
                </div>

                {/* 우측 상단: ChromaDB 유사도 점수 박스 */}
                <div className="bg-indigo-50/80 border border-indigo-100 px-3.5 py-2 rounded-xl text-right shrink-0">
                  <span className="text-[10px] font-semibold text-indigo-600 uppercase block">
                    시맨틱 적합도
                  </span>
                  <span className="text-xl font-extrabold text-indigo-700">
                    {item.similarity_score}%
                  </span>
                </div>
              </div>

              {/* 중단 1: 채용 접수 기간 타임라인 및 남은 시간 프로그레스 바 */}
              <div className={`mt-3 p-3 rounded-lg border ${uStyle.border}`}>
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs mb-1.5">
                  <span className="font-semibold text-slate-700 flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-indigo-600" />
                    접수 기간:{" "}
                    <span className="font-normal text-slate-600">
                      {item.start_date || "모집중"}
                    </span>{" "}
                    ~{" "}
                    <strong className="text-slate-900 underline decoration-indigo-300">
                      {item.end_date || "채용 시 마감"}
                    </strong>
                  </span>
                  <span className={`text-[11px] font-bold ${uStyle.text}`}>
                    남은 시간 여유도 {item.remaining_ratio ?? 70}%
                  </span>
                </div>

                {/* 남은 시간 게이지 바 */}
                <div className="w-full bg-white/80 h-2 rounded-full overflow-hidden border border-slate-200/60">
                  <div
                    className={`h-full transition-all duration-500 ${uStyle.bar}`}
                    style={{ width: `${item.remaining_ratio ?? 70}%` }}
                  />
                </div>
              </div>

              {/* 중단 2: 직무/기술 키워드 태그 */}
              {item.job_keywords && item.job_keywords.length > 0 && (
                <div className="mt-2.5 flex flex-wrap gap-1.5">
                  {item.job_keywords.map((kw, i) => (
                    <span
                      key={i}
                      className="text-[11px] bg-slate-100 text-slate-700 px-2 py-0.5 rounded font-medium"
                    >
                      #{kw}
                    </span>
                  ))}
                </div>
              )}

              {/* 중단 3: AI 추천 사유 */}
              <p className="text-xs text-slate-600 mt-2.5 bg-slate-50 p-2.5 rounded-lg border border-slate-200/80 leading-relaxed">
                <strong className="text-indigo-700">AI 추천 사유: </strong>
                {item.match_reason}
              </p>

              {/* 하단 액션 버튼 */}
              <div className="mt-3 flex flex-wrap items-center justify-end gap-2 pt-2.5 border-t border-slate-100">
                <button
                  onClick={() => onSelectRecommendedJob(item.job_id)}
                  className={`text-xs font-semibold px-3.5 py-1.5 rounded-lg flex items-center gap-1.5 transition ${
                    isSelected
                      ? "bg-indigo-600 text-white shadow-sm"
                      : "bg-white border border-indigo-200 text-indigo-700 hover:bg-indigo-50"
                  }`}
                >
                  <Target className="w-3.5 h-3.5" />
                  {isSelected ? "현재 정밀 분석 중" : "이 공고로 정밀 매칭 보기"}
                </button>

                {item.url && (
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`text-xs font-semibold px-3.5 py-1.5 rounded-lg text-white flex items-center gap-1.5 transition shadow-sm ${
                      isSaramin
                        ? "bg-amber-600 hover:bg-amber-700"
                        : "bg-blue-600 hover:bg-blue-700"
                    }`}
                  >
                    {isSaramin ? "사람인 공고 바로가기" : "잡코리아 공고 바로가기"}
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

