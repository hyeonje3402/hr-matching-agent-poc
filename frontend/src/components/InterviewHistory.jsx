import React, { useEffect, useState } from "react";
import {
  ArrowLeft,
  CalendarClock,
  ChevronDown,
  ChevronRight,
  Clock3,
  Loader2,
  MessageSquareText,
  Play,
  RotateCcw,
  Trash2,
} from "lucide-react";
import { deleteInterview, getInterviews } from "../api/resumeApi";

const interviewNames = {
  comprehensive: "종합 면접",
  hr: "인성 및 인사",
  job: "실무 및 직무",
  technical: "기술 면접",
  executive: "임원 면접",
};

const statusLabels = {
  completed: "완료",
  in_progress: "진행 중",
  ready: "준비",
};

const statusStyles = {
  completed: "bg-emerald-50 text-emerald-700",
  in_progress: "bg-indigo-50 text-indigo-700",
  ready: "bg-slate-100 text-slate-500",
};

function Metric({ label, children, emphasis = false }) {
  return (
    <div className="min-w-0 rounded-xl bg-slate-50 px-3 py-2.5">
      <p className="text-[10px] font-semibold text-slate-500">{label}</p>
      <p
        className={`mt-1 min-w-0 break-words text-xs font-bold ${
          emphasis ? "text-indigo-700" : "text-slate-800"
        }`}
      >
        {children}
      </p>
    </div>
  );
}

export default function InterviewHistory({ onBack, onOpen, onPractice }) {
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");

  const reload = async () => {
    setBusy(true);
    setError("");
    try {
      setItems(await getInterviews());
    } catch (e) {
      setError(e.response?.data?.detail || "면접 기록을 불러오지 못했습니다.");
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    reload();
  }, []);

  const remove = async (id) => {
    if (!window.confirm("이 면접 기록을 삭제할까요? 삭제한 기록은 복구할 수 없습니다.")) return;
    try {
      await deleteInterview(id);
      setItems((prev) => prev.filter((item) => item.session_id !== id));
    } catch (e) {
      setError(e.response?.data?.detail || "기록을 삭제하지 못했습니다.");
    }
  };

  return (
    <section className="w-full min-w-0 space-y-5">
      <div className="flex min-w-0 items-center gap-3">
        <button
          onClick={onBack}
          className="shrink-0 rounded-lg border border-slate-200 p-2 text-slate-500 hover:bg-slate-100"
          aria-label="채용 매칭으로 돌아가기"
        >
          <ArrowLeft size={18} />
        </button>
        <div className="min-w-0">
          <p className="text-xs font-bold uppercase tracking-[.16em] text-indigo-600">LOCAL HISTORY</p>
          <h2 className="text-2xl font-bold text-slate-900">면접 기록</h2>
        </div>
      </div>

      <div className="w-full min-w-0 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
        <div className="flex min-w-0 flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
          <div className="min-w-0">
            <h3 className="text-sm font-bold text-slate-900">내 모의 면접</h3>
            <p className="mt-1 text-xs text-slate-500">이 PC의 로컬 SQLite에 저장된 기록이에요.</p>
          </div>
          <span className="shrink-0 rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-700">
            {items.length}건
          </span>
        </div>

        {busy ? (
          <div className="flex items-center justify-center gap-2 py-16 text-sm text-slate-500">
            <Loader2 size={18} className="animate-spin" /> 기록 불러오는 중
          </div>
        ) : error ? (
          <div role="alert" className="mt-4 rounded-xl bg-rose-50 p-4 text-sm text-rose-700">
            {error}
            <button onClick={reload} className="ml-3 underline">다시 시도</button>
          </div>
        ) : items.length === 0 ? (
          <div className="py-16 text-center">
            <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-indigo-50 text-indigo-600">
              <MessageSquareText size={22} />
            </div>
            <p className="mt-3 text-sm font-semibold text-slate-700">아직 면접 기록이 없어요</p>
            <p className="mt-1 text-xs text-slate-400">면접을 마치면 결과와 답변 기록이 여기에 저장됩니다.</p>
          </div>
        ) : (
          <div className="grid min-w-0 gap-4 pt-4">
            {items.map((item) => {
              const answered = item.messages.filter(
                (message) => message.speaker === "지원자" && !message.skipped,
              ).length;
              const questions = item.messages.filter((message) => message.speaker === "면접관");
              const statusStyle = statusStyles[item.status] || statusStyles.ready;

              return (
                <article
                  key={item.session_id}
                  className="grid w-full min-w-0 gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-indigo-200 sm:p-5"
                >
                  <div className="flex min-w-0 flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div className="flex min-w-0 items-start gap-3">
                      <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-slate-100 text-slate-500">
                        <CalendarClock size={18} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex min-w-0 flex-wrap items-center gap-2">
                          <h4 className="min-w-0 break-words text-sm font-bold leading-relaxed text-slate-900 [overflow-wrap:anywhere] sm:text-base">
                            {item.company_name}
                          </h4>
                          <span className={`shrink-0 whitespace-nowrap rounded-full px-2.5 py-1 text-[10px] font-bold ${statusStyle}`}>
                            {statusLabels[item.status] || "준비"}
                          </span>
                        </div>
                        <p className="mt-1 break-words text-xs text-slate-600 [overflow-wrap:anywhere]">
                          {item.position}
                        </p>
                      </div>
                    </div>

                    <div className="flex min-w-0 flex-wrap items-center gap-2 sm:shrink-0 sm:justify-end">
                      <button
                        onClick={() => onOpen(item)}
                        className="inline-flex shrink-0 items-center justify-center gap-1 whitespace-nowrap rounded-lg bg-slate-950 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-700"
                      >
                        {item.status === "in_progress" ? <Play size={13} /> : <ChevronRight size={14} />}
                        {item.status === "in_progress" ? "계속하기" : "결과 보기"}
                      </button>
                      {item.status === "completed" && (
                        <button
                          onClick={() => onPractice(item)}
                          className="inline-flex shrink-0 items-center justify-center gap-1 whitespace-nowrap rounded-lg border border-indigo-200 px-3 py-2 text-xs font-semibold text-indigo-700 hover:bg-indigo-50"
                        >
                          <RotateCcw size={13} /> 다시 연습
                        </button>
                      )}
                      <button
                        onClick={() => remove(item.session_id)}
                        aria-label="면접 기록 삭제"
                        className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-200 text-slate-500 hover:border-rose-200 hover:bg-rose-50 hover:text-rose-600"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>

                  <div className="grid min-w-0 grid-cols-2 gap-2 lg:grid-cols-4">
                    <Metric label="면접 일시">
                      <time dateTime={item.created_at}>
                        {new Date(item.created_at).toLocaleString("ko-KR")}
                      </time>
                    </Metric>
                    <Metric label="면접 유형">{interviewNames[item.interview_type] || "면접"}</Metric>
                    <Metric label="질문 · 답변">{questions.length}개 · {answered}개</Metric>
                    <Metric label="종합 점수" emphasis>
                      {item.result ? `${item.result.overall_score}점` : "미완료"}
                    </Metric>
                  </div>

                  {item.status === "completed" && questions.length > 0 && (
                    <details className="group min-w-0 rounded-xl border border-slate-200 bg-slate-50">
                      <summary className="flex min-w-0 cursor-pointer list-none items-center gap-2 rounded-xl p-3 text-xs font-bold text-slate-600 hover:bg-slate-100 [&::-webkit-details-marker]:hidden">
                        <Clock3 size={14} className="shrink-0 text-indigo-600" />
                        <span className="min-w-0">질문별 다시 연습</span>
                        <span className="shrink-0 rounded-full bg-white px-2 py-0.5 text-[10px] text-slate-500">
                          {questions.length}개
                        </span>
                        <ChevronDown size={15} className="ml-auto shrink-0 transition-transform group-open:rotate-180" />
                      </summary>
                      <div className="grid min-w-0 gap-2 p-3 pt-0 md:grid-cols-2">
                        {questions.map((question) => (
                          <button
                            key={question.message_id}
                            onClick={() => onPractice(item, question)}
                            title={question.text}
                            className="flex min-w-0 w-full items-start gap-2 rounded-lg border border-slate-200 bg-white p-3 text-left text-xs text-slate-600 transition hover:border-indigo-300 hover:text-indigo-700"
                          >
                            <span className="shrink-0 font-semibold text-indigo-700">
                              {question.interviewer_name || "면접관"}
                            </span>
                            <span className="min-w-0 whitespace-normal break-words leading-relaxed [overflow-wrap:anywhere]">
                              {question.text}
                            </span>
                          </button>
                        ))}
                      </div>
                    </details>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
