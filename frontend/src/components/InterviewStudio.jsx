import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft, AudioLines, Building2, Check, ChevronRight, CircleHelp,
  FileText, Loader2, Mic, MicOff, Pause, Play, Send, SkipForward,
  Sparkles, Square, Volume2, VolumeX,
} from "lucide-react";
import {
  analyzeJobFile, analyzeJobText, analyzeJobUrl, answerInterview, compareResumeToJob,
  createInterview, finishInterview, getSavedResumes, skipInterviewQuestion,
  updateJobMaterial, uploadResumePdf,
} from "../api/resumeApi";

const panel = [
  ["hr", "인사 담당자", "동기 · 협업 · 조직생활", "인"],
  ["team_leader", "실무 팀장", "프로젝트 · 문제 해결 · 우선순위", "실"],
  ["technical", "기술 담당자", "기술 이해 · 설계 · 검증", "기"],
  ["executive", "임원 면접관", "성장 · 목표 · 조직 기여", "임"],
];
const typeLabels = { comprehensive: "종합 면접", hr: "인성 및 인사", job: "실무 및 직무", technical: "기술 면접", executive: "임원 면접" };
const names = Object.fromEntries(panel.map(([id, name]) => [id, name]));
const card = "rounded-2xl border border-slate-200 bg-white shadow-sm";

export default function InterviewStudio({ jobs, resumeData, onResumeReady, initialSession, initialJobId, onSessionChange, onBack }) {
  const [session, setSession] = useState(initialSession || null);
  const [resume, setResume] = useState(initialSession?.resume_data || resumeData || null);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [company, setCompany] = useState("");
  const [position, setPosition] = useState("");
  const [description, setDescription] = useState("");
  const [interviewType, setInterviewType] = useState("comprehensive");
  const [interviewers, setInterviewers] = useState(["hr", "team_leader", "technical"]);
  const [difficulty, setDifficulty] = useState("practical");
  const [maxQuestions, setMaxQuestions] = useState(8);
  const [mode, setMode] = useState("text");
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [elapsed, setElapsed] = useState("00:00");
  const [listening, setListening] = useState(false);
  const [muted, setMuted] = useState(false);
  const [speechPaused, setSpeechPaused] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(false);
  const [savedResumes, setSavedResumes] = useState([]);
  const [resumeMaterialIds, setResumeMaterialIds] = useState(initialSession?.resume_material_ids || []);
  const [jobSource, setJobSource] = useState("select");
  const [jobUrl, setJobUrl] = useState("");
  const [jobMaterialId, setJobMaterialId] = useState(initialSession?.job_material_id || null);
  const [jobAnalysis, setJobAnalysis] = useState(initialSession?.job_analysis || null);
  const [candidateFit, setCandidateFit] = useState(initialSession?.candidate_fit || null);
  const [fitBusy, setFitBusy] = useState(false);
  const [jobRatio, setJobRatio] = useState(initialSession?.job_question_ratio ?? 50);
  const [priorEnabled, setPriorEnabled] = useState(true);
  const [supportingMaterials, setSupportingMaterials] = useState(initialSession?.supporting_materials || "");
  const [analyzedJobOption, setAnalyzedJobOption] = useState(null);
  const speechRef = useRef(null);
  const lastSpokenQuestion = useRef("");
  const recognitionRef = useRef(null);
  const answerRef = useRef(answer);
  const speechBaseRef = useRef("");
  const transcriptEndRef = useRef(null);
  answerRef.current = answer;

  useEffect(() => { getSavedResumes().then(setSavedResumes).catch(() => {}); }, []);

  useEffect(() => {
    if (initialJobId && jobs.some((job) => job.job_id === initialJobId)) toggleJob(initialJobId);
  }, [initialJobId, jobs]);

  useEffect(() => {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    setSpeechSupported(Boolean(Recognition && window.speechSynthesis));
    if (!Recognition) return;
    const recognition = new Recognition();
    recognition.lang = "ko-KR";
    recognition.interimResults = true;
    recognition.continuous = true;
    recognition.onresult = (event) => {
      const recognized = Array.from(event.results).map((item) => item[0].transcript).join("");
      setAnswer(`${speechBaseRef.current} ${recognized}`.trim());
    };
    recognition.onerror = () => {
      setListening(false);
      setNotice("음성 인식에 문제가 생겼어요. 아래 입력창에서 답변을 직접 수정해 주세요.");
    };
    recognition.onend = () => setListening(false);
    recognitionRef.current = recognition;
    return () => recognition.stop();
  }, []);

  useEffect(() => {
    if (!session?.created_at || session.status !== "in_progress") return undefined;
    const update = () => {
      const seconds = Math.max(0, Math.floor((Date.now() - new Date(session.created_at).getTime()) / 1000));
      setElapsed(`${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`);
    };
    update();
    const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, [session?.created_at, session?.status]);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [session?.messages?.length]);

  useEffect(() => {
    const q = session?.current_question;
    if (!q || session.mode !== "voice" || muted || !window.speechSynthesis) return;
    const key = `${session.session_id}:${session.messages?.at(-1)?.message_id || q.question}`;
    if (lastSpokenQuestion.current === key) return;
    lastSpokenQuestion.current = key;
    const timer = window.setTimeout(() => {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(q.question);
      utterance.lang = "ko-KR";
      const actor = q.interviewer_id;
      utterance.rate = actor === "hr" ? 0.97 : actor === "executive" ? 0.91 : 0.94;
      utterance.pitch = actor === "hr" ? 1.08 : actor === "executive" ? 0.88 : actor === "technical" ? 0.96 : 1.0;
      utterance.onend = () => setSpeechPaused(false);
      utterance.onerror = () => setSpeechPaused(false);
      const voices = window.speechSynthesis.getVoices();
      utterance.voice = voices.find((voice) => voice.lang.toLowerCase().startsWith("ko")) || null;
      speechRef.current = utterance;
      window.speechSynthesis.speak(utterance);
    }, 80);
    return () => { window.clearTimeout(timer); window.speechSynthesis.cancel(); };
  }, [session?.session_id, session?.current_question?.question, session?.messages?.length, session?.mode, muted]);

  const questionCount = useMemo(() => session?.messages?.filter((m) => m.speaker === "면접관").length || 0, [session]);

  const toggleJob = (id) => {
    setSelectedJobId(id);
    setJobSource("select");
    const job = [...jobs, ...(analyzedJobOption ? [analyzedJobOption] : [])].find((item) => item.job_id === id);
    if (!job) { setJobMaterialId(null); setJobAnalysis(null); setCandidateFit(null); return; }
    setCompany(job.company_name || job.department?.split(" (")[0] || "");
    setPosition(job.title || "");
    setDescription(job.description || "");
    setJobMaterialId(job.material_id || (job.source === "Saved" ? job.job_id : null));
    setJobAnalysis(job.analysis || null);
    setCandidateFit(null);
  };

  const chooseJobSource = (source) => {
    setJobSource(source);
    if (source !== "select") {
      setSelectedJobId(""); setJobMaterialId(null); setJobAnalysis(null); setCandidateFit(null);
    }
  };

  const mergeResumeData = (items) => {
    if (!items.length) return null;
    const first = items[0];
    const unique = (values, key) => [...new Map(values.map((value) => [key(value), value])).values()];
    return {
      ...first,
      total_experience_years: Math.max(...items.map((item) => item.total_experience_years || 0)),
      core_skills: unique(items.flatMap((item) => item.core_skills || []), (value) => value.toLowerCase()),
      projects: unique(items.flatMap((item) => item.projects || []), (item) => item.project_name.toLowerCase()),
      educations: unique(items.flatMap((item) => item.educations || []), (item) => `${item.school_name}-${item.major}`.toLowerCase()),
      overall_summary: items.map((item) => item.overall_summary).filter(Boolean).join("\n"),
    };
  };

  const loadResumeFiles = async (files) => {
    if (!files?.length) return;
    const invalid = [...files].find((file) => !file.name.toLowerCase().endsWith(".pdf"));
    if (invalid) { setError("지원자 자료는 PDF 형식만 등록할 수 있습니다."); return; }
    setBusy(true); setError(""); setNotice("PDF 자료를 확인하고 있어요. 이미 분석한 파일은 저장된 결과를 재사용합니다.");
    try {
      const parsedItems = [];
      for (const file of files) parsedItems.push(await uploadResumePdf(file));
      const merged = mergeResumeData(parsedItems);
      setResume(merged); onResumeReady?.(merged);
      const saved = await getSavedResumes(); setSavedResumes(saved);
      const names = new Set([...files].map((file) => file.name));
      setResumeMaterialIds(saved.filter((item) => names.has(item.title)).map((item) => item.material_id));
      setNotice(`${files.length}개 PDF의 확인된 내용을 면접 컨텍스트에 연결했어요.`);
    } catch (e) { setError(e.response?.data?.detail || "PDF 자료를 분석하지 못했습니다."); setNotice(""); }
    finally { setBusy(false); }
  };

  const selectSavedResumes = (event) => {
    const selected = [...event.target.selectedOptions].map((option) => option.value);
    setResumeMaterialIds(selected);
    const items = savedResumes.filter((item) => selected.includes(item.material_id)).map((item) => item.resume_data);
    const merged = mergeResumeData(items);
    setResume(merged); onResumeReady?.(merged);
  };

  const acceptJobMaterial = (item, rawText) => {
    setJobMaterialId(item.material_id); setJobAnalysis(item.analysis);
    setCompany(item.company_name || item.analysis?.company_name || "");
    setPosition(item.position || item.analysis?.position || "");
    setDescription(rawText || item.raw_text || "");
    setSelectedJobId(item.material_id); setCandidateFit(null); setNotice("공고 분석을 저장했습니다. 구조화 결과를 확인하고 필요한 부분을 고쳐 주세요.");
    setAnalyzedJobOption({ job_id: item.material_id, material_id: item.material_id, title: item.position || item.analysis?.position || item.title,
      department: item.company_name || item.analysis?.company_name || "저장 공고", company_name: item.company_name,
      description: rawText || item.raw_text || "", source: "Saved", analysis: item.analysis });
  };

  const analyzeManualJob = async () => {
    setBusy(true); setError(""); setNotice("공고 내용을 분석하고 있어요…");
    try { const item = await analyzeJobText({ source: "manual", company_name: company, position, job_description: description }); acceptJobMaterial(item, description); }
    catch (e) { setError(e.response?.data?.detail || "공고를 분석하지 못했습니다."); setNotice(""); }
    finally { setBusy(false); }
  };

  const analyzeUrl = async () => {
    setBusy(true); setError(""); setNotice("공개 공고 페이지의 본문을 확인하고 있어요…");
    try { const item = await analyzeJobUrl(jobUrl); acceptJobMaterial(item, item.raw_text); }
    catch (e) { setError(e.response?.data?.detail || "공고 URL을 가져오지 못했습니다. 직접 입력 또는 파일 업로드를 이용해 주세요."); setNotice(""); }
    finally { setBusy(false); }
  };

  const analyzeJobUpload = async (file) => {
    if (!file) return;
    setBusy(true); setError(""); setNotice("채용 자료에서 텍스트와 필요한 경우 이미지 내용을 읽고 있어요…");
    try { const item = await analyzeJobFile(file); acceptJobMaterial(item, item.raw_text); }
    catch (e) { setError(e.response?.data?.detail || "채용 자료를 분석하지 못했습니다."); setNotice(""); }
    finally { setBusy(false); }
  };

  const analyzeFit = async () => {
    if (!resume || !jobMaterialId) return;
    setFitBusy(true); setError("");
    try { setCandidateFit(await compareResumeToJob(jobMaterialId, resume)); }
    catch (e) { setError(e.response?.data?.detail || "이력서와 공고를 비교하지 못했습니다."); }
    finally { setFitBusy(false); }
  };

  const saveEditedAnalysis = async () => {
    if (!jobMaterialId || !jobAnalysis) return;
    setBusy(true); setError("");
    try {
      const updated = await updateJobMaterial(jobMaterialId, { company_name: company, position,
        analysis: { ...jobAnalysis, required_skills: (jobAnalysis.required_skills || []), interview_focus: (jobAnalysis.interview_focus || []) } });
      setJobAnalysis(updated.analysis); setNotice("검토한 기업·직무 정보를 저장했습니다.");
    } catch (e) { setError(e.response?.data?.detail || "공고 검토 내용을 저장하지 못했습니다."); }
    finally { setBusy(false); }
  };

  const start = async () => {
    setBusy(true); setError(""); setNotice("");
    try {
      const created = await createInterview({
        resume_data: resume || null,
        job_id: selectedJobId || null,
        company_name: company,
        position,
        job_description: description,
        interview_type: interviewType,
        interviewers,
        difficulty,
        max_questions: Number(maxQuestions),
        mode,
        job_material_id: jobMaterialId,
        job_analysis: jobAnalysis,
        candidate_fit: candidateFit,
        job_question_ratio: Number(jobRatio),
        use_prior_results: priorEnabled,
        supporting_materials: supportingMaterials,
        resume_material_ids: resumeMaterialIds,
      });
      setSession(created); onSessionChange?.(created);
    } catch (e) {
      setError(e.response?.data?.detail || "면접을 시작하지 못했습니다. 백엔드와 API 설정을 확인해 주세요.");
    } finally { setBusy(false); }
  };

  const updateSession = (next) => { setSession(next); onSessionChange?.(next); };
  const submitAnswer = async () => {
    if (!answer.trim() || busy || !session) return;
    recognitionRef.current?.stop(); setListening(false); setBusy(true); setError(""); setNotice("");
    const questionId = [...session.messages].reverse().find((message) => message.speaker === "면접관")?.message_id;
    try { updateSession(await answerInterview(session.session_id, questionId, answer.trim())); setAnswer(""); }
    catch (e) { setError(e.response?.data?.detail || "답변 평가에 실패했습니다. 입력 내용은 유지했습니다."); }
    finally { setBusy(false); }
  };
  const skip = async () => {
    setBusy(true); setError("");
    const questionId = [...session.messages].reverse().find((message) => message.speaker === "면접관")?.message_id;
    try { updateSession(await skipInterviewQuestion(session.session_id, questionId)); setNotice("질문을 건너뛰었어요."); }
    catch (e) { setError(e.response?.data?.detail || "질문을 건너뛰지 못했습니다."); }
    finally { setBusy(false); }
  };
  const finish = async () => {
    recognitionRef.current?.stop(); window.speechSynthesis?.cancel(); setListening(false); setBusy(true); setError("");
    try { updateSession(await finishInterview(session.session_id)); }
    catch (e) { setError(e.response?.data?.detail || "평가를 마치지 못했습니다. 기록은 저장되어 있습니다."); }
    finally { setBusy(false); }
  };
  const replay = () => {
    if (!session?.current_question?.question || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(session.current_question.question);
    utterance.lang = "ko-KR";
    const actor = session.current_question.interviewer_id;
    utterance.rate = actor === "hr" ? 0.97 : actor === "executive" ? 0.91 : 0.94;
    utterance.pitch = actor === "hr" ? 1.08 : actor === "executive" ? 0.88 : actor === "technical" ? 0.96 : 1.0;
    utterance.onend = () => setSpeechPaused(false);
    utterance.onerror = () => setSpeechPaused(false);
    utterance.voice = window.speechSynthesis.getVoices().find((v) => v.lang.toLowerCase().startsWith("ko")) || null;
    speechRef.current = utterance; window.speechSynthesis.speak(utterance);
  };
  const toggleSpeechPause = () => {
    if (!window.speechSynthesis) return;
    if (window.speechSynthesis.paused) {
      window.speechSynthesis.resume();
      setSpeechPaused(false);
    } else if (window.speechSynthesis.speaking) {
      window.speechSynthesis.pause();
      setSpeechPaused(true);
    }
  };
  const stopSpeech = () => {
    window.speechSynthesis?.cancel();
    setSpeechPaused(false);
  };
  const toggleMic = () => {
    if (!recognitionRef.current) {
      setNotice("이 브라우저는 음성 인식을 지원하지 않아요. 텍스트로 답변해 주세요.");
      return;
    }
    if (listening) recognitionRef.current.stop();
    else {
      try { speechBaseRef.current = answerRef.current.trim(); recognitionRef.current.start(); setListening(true); setNotice("말씀하신 내용을 듣고 있어요. 인식된 텍스트를 확인한 뒤 제출해 주세요."); }
      catch { setListening(false); setNotice("마이크를 시작하지 못했습니다. 브라우저 권한을 확인하거나 텍스트로 답변해 주세요."); }
    }
  };

  if (!session) return <section className="space-y-5">
    <div className="flex items-center gap-3"><button onClick={onBack} className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:bg-slate-100"><ArrowLeft size={18}/></button><div><p className="text-xs font-bold uppercase tracking-[.16em] text-indigo-600">AI INTERVIEW STUDIO</p><h2 className="text-2xl font-bold text-slate-900">모의 면접 준비</h2></div></div>
    <div className="grid gap-5 xl:grid-cols-[1.05fr_.95fr]">
      <div className={`${card} p-6 space-y-5`}>
        <div><p className="text-sm font-bold text-slate-900">지원 정보</p><p className="mt-1 text-xs text-slate-500">분석된 이력서를 재사용하거나, 공고 없이 기업과 직무를 직접 입력할 수 있어요.</p></div>
        <label className="block text-xs font-semibold text-slate-700">기존 공고 재사용
          <select value={selectedJobId} onChange={(e) => toggleJob(e.target.value)} className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm"><option value="">직접 입력</option>{[...jobs, ...(analyzedJobOption && !jobs.some((job) => job.job_id === analyzedJobOption.job_id) ? [analyzedJobOption] : [])].map((job) => <option key={job.job_id} value={job.job_id}>{job.title} · {job.department}</option>)}</select>
        </label>
        <div className="grid gap-3 sm:grid-cols-2"><label className="text-xs font-semibold text-slate-700">기업명<input value={company} onChange={(e) => setCompany(e.target.value)} placeholder="예: 지원 기업" className="mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm"/></label><label className="text-xs font-semibold text-slate-700">지원 직무<input value={position} onChange={(e) => setPosition(e.target.value)} placeholder="예: 백엔드 엔지니어" className="mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm"/></label></div>
        <div className="rounded-xl border border-slate-200 p-4"><div className="flex flex-wrap gap-2">{[["select","공고 재사용"],["url","URL"],["text","직접 붙여넣기"],["file","파일"]].map(([id,label])=><button key={id} onClick={()=>chooseJobSource(id)} className={`rounded-lg px-3 py-2 text-xs font-semibold ${jobSource===id?"bg-indigo-600 text-white":"bg-slate-100 text-slate-600"}`}>{label}</button>)}</div>
          {jobSource==="url"&&<div className="mt-3 flex flex-col gap-2 sm:flex-row"><input value={jobUrl} onChange={(e)=>setJobUrl(e.target.value)} placeholder="https://기업 채용 공고 URL" className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2.5 text-sm"/><button onClick={analyzeUrl} disabled={busy||!jobUrl.trim()} className="rounded-lg bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white disabled:bg-slate-300">URL 수집·분석</button></div>}
          {jobSource==="text"&&<><label className="mt-3 block text-xs font-semibold text-slate-600">공고 원문<textarea value={description} onChange={(e)=>setDescription(e.target.value)} rows={6} maxLength={30000} placeholder="주요 업무, 필수 요건, 우대 사항 등을 붙여 넣으세요." className="mt-1.5 w-full resize-y rounded-xl border border-slate-300 px-3 py-2.5 text-sm leading-relaxed"/></label><div className="mt-2 flex items-center justify-between gap-2"><span className="text-[10px] text-slate-400">30자 이상 · {description.length.toLocaleString()} / 30,000</span><button onClick={analyzeManualJob} disabled={busy||description.trim().length<30} className="rounded-lg bg-indigo-600 px-3 py-2 text-xs font-bold text-white disabled:bg-slate-300">분석·저장</button></div></>}
          {jobSource==="file"&&<label className="mt-3 flex cursor-pointer flex-col items-center rounded-xl border border-dashed border-slate-300 bg-slate-50 p-5 text-center"><FileText className="text-indigo-600"/><span className="mt-2 text-xs font-bold text-slate-700">PDF · PNG · JPG · TXT</span><span className="mt-1 text-[10px] text-slate-500">10MB 이하. 스캔 PDF와 이미지 공고는 이미지 분석을 시도합니다.</span><input type="file" accept=".pdf,.png,.jpg,.jpeg,.txt,application/pdf,image/png,image/jpeg,text/plain" className="sr-only" onChange={(e)=>analyzeJobUpload(e.target.files?.[0])}/></label>}
          {jobAnalysis&&<div className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50/50 p-4"><div className="flex flex-wrap items-center justify-between gap-2"><div><p className="text-xs font-bold text-indigo-900">공고 구조화 결과 · 수정 가능</p><p className="mt-1 text-[10px] text-indigo-800/70">원문에 명시되지 않은 정보는 추론하지 않습니다.</p></div><button onClick={saveEditedAnalysis} disabled={busy} className="rounded-lg border border-indigo-200 bg-white px-3 py-2 text-[11px] font-bold text-indigo-700">검토 내용 저장</button></div><label className="mt-3 block text-[11px] font-semibold text-slate-700">필수 기술 · 한 줄에 하나<textarea rows={2} value={(jobAnalysis.required_skills||[]).join("\n")} onChange={(e)=>setJobAnalysis({...jobAnalysis,required_skills:e.target.value.split("\n").map((x)=>x.trim()).filter(Boolean)})} className="mt-1 w-full rounded-lg border border-indigo-100 bg-white px-2.5 py-2 text-xs"/></label><label className="mt-2 block text-[11px] font-semibold text-slate-700">면접 검증 영역<textarea rows={2} value={(jobAnalysis.interview_focus||[]).join("\n")} onChange={(e)=>setJobAnalysis({...jobAnalysis,interview_focus:e.target.value.split("\n").map((x)=>x.trim()).filter(Boolean)})} className="mt-1 w-full rounded-lg border border-indigo-100 bg-white px-2.5 py-2 text-xs"/></label>{jobAnalysis.unknowns?.length>0&&<p className="mt-2 text-[11px] text-amber-800">추가 확인 필요: {jobAnalysis.unknowns.join(" · ")}</p>}
            {resume&&jobMaterialId&&<button onClick={analyzeFit} disabled={fitBusy||busy} className="mt-3 rounded-lg bg-white px-3 py-2 text-[11px] font-bold text-indigo-700 disabled:opacity-50">{fitBusy?"요구사항 비교 중…":"이력서와 요구사항 비교"}</button>}
            {candidateFit&&<div className="mt-3 space-y-2"><p className="text-xs font-bold text-slate-800">지원자 근거 비교</p>{candidateFit.items?.slice(0,6).map((item,index)=><div key={`${item.requirement}-${index}`} className="rounded-lg bg-white p-3"><p className="text-xs font-semibold text-slate-800">{item.requirement} · {item.status==="supported"?"근거 확인":item.status==="not_found"?"이력서에서 찾지 못함":"면접에서 확인 필요"}</p><p className="mt-1 text-[11px] leading-relaxed text-slate-600">{item.rationale}</p>{item.interview_probe&&<p className="mt-1 text-[11px] text-indigo-700">추천 질문 영역 · {item.interview_probe}</p>}</div>)}<p className="text-[10px] text-slate-500">{candidateFit.overall_note}</p></div>}</div>}
        </div>
        <div className="rounded-xl border border-indigo-100 bg-indigo-50/70 p-4"><div className="flex items-center gap-2 text-sm font-bold text-indigo-950"><FileText size={16}/>지원자 자료</div><p className="mt-1 text-xs leading-relaxed text-indigo-900/75">{resume ? `${resume.candidate_name || "지원자"} · 경력 ${resume.total_experience_years}년 · ${(resume.core_skills || []).slice(0, 6).join(", ") || "기술 정보 없음"}` : "이력서·포트폴리오 PDF를 함께 선택하거나 저장 자료를 재사용하세요."}</p><label className="mt-3 inline-flex cursor-pointer items-center gap-2 rounded-lg border border-indigo-200 bg-white px-3 py-2 text-xs font-semibold text-indigo-700 hover:bg-indigo-50"><FileText size={14}/>PDF 여러 개 선택<input type="file" multiple accept="application/pdf,.pdf" className="hidden" onChange={(e)=>loadResumeFiles(e.target.files)}/></label>{savedResumes.length>0&&<label className="mt-3 block text-xs font-semibold text-indigo-900">저장된 이력서·포트폴리오 다중 선택<select multiple onChange={selectSavedResumes} className="mt-1.5 min-h-20 w-full rounded-lg border border-indigo-200 bg-white px-2 py-2 text-xs">{savedResumes.map((item)=><option key={item.material_id} value={item.material_id}>{item.title} · {new Date(item.created_at).toLocaleDateString("ko-KR")}</option>)}</select><span className="mt-1 block text-[10px] font-normal text-indigo-800">Ctrl 키를 누르고 여러 자료를 선택할 수 있습니다.</span></label>}<label className="mt-3 block text-xs font-semibold text-indigo-900">추가 프로젝트·자기소개 메모<textarea value={supportingMaterials} onChange={(e)=>setSupportingMaterials(e.target.value)} maxLength={12000} rows={3} placeholder="포트폴리오 설명이나 면접에서 참고할 실제 경험을 입력하세요." className="mt-1.5 w-full rounded-lg border border-indigo-200 px-3 py-2 text-xs"/></label></div>
      </div>
      <div className={`${card} p-6 space-y-5`}>
        <div><p className="text-sm font-bold text-slate-900">면접 진행 방식</p><p className="mt-1 text-xs text-slate-500">Supervisor가 답변을 보고 다음 질문과 면접관을 선택합니다.</p></div>
        <div className="grid grid-cols-2 gap-2">{Object.entries(typeLabels).map(([id, label]) => <button key={id} onClick={() => setInterviewType(id)} className={`rounded-xl border px-3 py-2.5 text-xs font-semibold ${interviewType === id ? "border-indigo-500 bg-indigo-50 text-indigo-700" : "border-slate-200 text-slate-600 hover:bg-slate-50"}`}>{label}</button>)}</div>
        <div><p className="mb-2 text-xs font-semibold text-slate-700">참여 면접관</p><div className="grid grid-cols-2 gap-2">{panel.map(([id, name, focus, initials]) => { const checked = interviewers.includes(id); return <button key={id} onClick={() => setInterviewers((items) => checked ? items.filter((item) => item !== id) : [...items, id])} className={`rounded-xl border p-3 text-left ${checked ? "border-indigo-400 bg-indigo-50/70" : "border-slate-200 bg-white"}`}><span className="flex items-center justify-between"><span className="text-sm font-bold text-slate-800">{initials} · {name}</span>{checked && <Check size={15} className="text-indigo-600"/>}</span><span className="mt-1 block text-[10px] leading-relaxed text-slate-500">{focus}</span></button>; })}</div></div>
        <div className="grid gap-3 sm:grid-cols-2"><label className="text-xs font-semibold text-slate-700">난이도<select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm"><option value="basic">기본</option><option value="practical">실무</option><option value="advanced">심화</option></select></label><label className="text-xs font-semibold text-slate-700">최대 질문 수<select value={maxQuestions} onChange={(e) => setMaxQuestions(e.target.value)} className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm">{[4,6,8,10,12,15].map((n)=><option key={n} value={n}>{n}개 (꼬리 질문 포함)</option>)}</select></label></div>
        <div><p className="mb-2 text-xs font-semibold text-slate-700">면접 응답 방식</p><div className="grid grid-cols-2 gap-2"><button onClick={() => setMode("text")} className={`rounded-xl border p-3 text-left ${mode === "text" ? "border-indigo-400 bg-indigo-50" : "border-slate-200"}`}><span className="flex items-center gap-2 text-sm font-bold"><FileText size={16}/>텍스트</span><span className="mt-1 block text-[10px] text-slate-500">작성 후 제출</span></button><button onClick={() => setMode("voice")} className={`rounded-xl border p-3 text-left ${mode === "voice" ? "border-indigo-400 bg-indigo-50" : "border-slate-200"}`}><span className="flex items-center gap-2 text-sm font-bold"><AudioLines size={16}/>음성 + 텍스트</span><span className="mt-1 block text-[10px] text-slate-500">질문 음성 출력 및 브라우저 음성 인식</span></button></div></div>
        <div className="rounded-xl border border-slate-200 p-4"><div className="flex items-center justify-between gap-2"><label htmlFor="job-ratio" className="text-xs font-bold text-slate-700">공고 {jobRatio}% · 지원자 자료 {100-jobRatio}%</label><span className="text-xs font-bold text-indigo-700">{jobRatio}:{100-jobRatio}</span></div><input id="job-ratio" type="range" min="0" max="100" step="10" value={jobRatio} onChange={(e)=>setJobRatio(e.target.value)} className="mt-3 w-full accent-indigo-600"/><label className="mt-3 flex items-start gap-2 text-xs text-slate-600"><input type="checkbox" checked={priorEnabled} onChange={(e)=>setPriorEnabled(e.target.checked)} className="mt-0.5 accent-indigo-600"/>같은 기업 또는 직무의 면접 기록에서 구조화된 보완점을 반영</label></div>
        {mode === "voice" && !speechSupported && <p className="rounded-lg bg-amber-50 p-2.5 text-xs text-amber-800">현재 브라우저가 Web Speech API 일부 기능을 지원하지 않을 수 있어요. 면접은 텍스트로 계속할 수 있습니다.</p>}
        {error && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">{error}</p>}{notice && <p className="rounded-xl border border-indigo-100 bg-indigo-50 p-3 text-xs text-indigo-800">{notice}</p>}
        <button onClick={start} disabled={busy || interviewers.length === 0 || (!position.trim() && !description.trim())} className="flex w-full items-center justify-center gap-2 rounded-xl bg-slate-950 px-4 py-3.5 text-sm font-bold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300">{busy ? <Loader2 size={17} className="animate-spin"/> : <Sparkles size={17}/>}면접 시작</button>
      </div>
    </div>
  </section>;

  if (session.status === "completed") return <section className="space-y-5">
    <div className="flex items-center gap-3"><button onClick={() => { setSession(null); onSessionChange?.(null); }} className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:bg-slate-100"><ArrowLeft size={18}/></button><div><p className="text-xs font-bold uppercase tracking-[.16em] text-indigo-600">INTERVIEW REPORT</p><h2 className="text-2xl font-bold text-slate-900">면접 결과 분석</h2></div></div>
    <div className={`${card} overflow-hidden`}><div className="grid gap-5 border-b border-slate-100 bg-gradient-to-r from-slate-950 to-indigo-950 p-6 text-white sm:grid-cols-[1fr_auto] sm:items-center"><div><p className="flex items-center gap-2 text-sm text-indigo-200"><Building2 size={16}/>{session.company_name} · {session.position}</p><h3 className="mt-2 text-xl font-bold">{session.result?.summary || "답변을 검토해 주세요."}</h3><p className="mt-2 text-xs text-indigo-100/70">모의 면접 연습용 참고 결과입니다. 실제 채용 평가나 합격 가능성을 뜻하지 않습니다.</p></div><div className="rounded-2xl border border-white/15 bg-white/10 px-6 py-4 text-center"><span className="block text-[10px] font-bold uppercase tracking-widest text-indigo-200">연습 점수</span><strong className="text-4xl">{session.result?.overall_score ?? 0}</strong><span className="text-sm"> / 100</span></div></div>
      <div className="grid grid-cols-2 gap-3 border-b border-slate-100 px-6 pt-5 sm:grid-cols-4">{[["진행 시간",session.result?.duration_note], ["총 질문",`${session.result?.question_count ?? 0}개`], ["답변 완료",`${session.result?.answered_count ?? 0}개`], ["건너뜀",`${session.result?.skipped_count ?? 0}개`]].map(([label,value])=><div key={label} className="rounded-xl bg-slate-50 p-3"><p className="text-[10px] font-semibold text-slate-500">{label}</p><p className="mt-1 text-sm font-bold text-slate-800">{value || "-"}</p></div>)}</div>
      <div className="grid gap-4 p-6 lg:grid-cols-3">{[["주요 강점",session.result?.strengths], ["보완할 점",session.result?.improvements], ["우선 실천 과제",session.result?.priority_actions]].map(([title, items])=><div key={title} className="rounded-xl border border-slate-200 p-4"><h4 className="text-sm font-bold">{title}</h4><ul className="mt-3 space-y-2">{(items || []).map((item,i)=><li key={i} className="flex gap-2 text-xs leading-relaxed text-slate-600"><ChevronRight size={14} className="mt-0.5 shrink-0 text-indigo-500"/>{item}</li>)}</ul></div>)}</div>
      <div className="border-t border-slate-100 p-6"><h4 className="text-sm font-bold">면접관별 평가</h4><div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">{Object.entries(session.result?.interviewer_scores || {}).map(([id, score])=><div key={id} className="rounded-xl bg-slate-50 p-3"><p className="text-xs font-semibold text-slate-600">{names[id] || id}</p><p className="mt-1 text-xl font-bold text-indigo-700">{score}<span className="ml-1 text-xs font-normal text-slate-400">/ 100</span></p></div>)}</div><p className="mt-2 text-[10px] text-slate-400">참여하지 않았거나 답변 근거가 없는 면접관 평가는 표시하지 않습니다.</p></div>
      <div className="border-t border-slate-100 p-6"><h4 className="text-sm font-bold">질문별 답변과 피드백</h4><div className="mt-4 space-y-3">{session.messages.filter((m)=>m.speaker === "면접관").map((q)=>{const a=session.messages.find((m)=>m.speaker === "지원자"&&m.question_id===q.message_id); return <article key={q.message_id} className="rounded-xl border border-slate-200 p-4"><p className="text-[10px] font-bold text-indigo-600">{q.interviewer_name} · {q.area}{q.follow_up ? " · 꼬리 질문" : ""}</p><p className="mt-1 text-sm font-semibold text-slate-900">{q.text}</p><details className="mt-2 rounded-lg bg-indigo-50/70 px-3 py-2 text-xs"><summary className="cursor-pointer font-semibold text-indigo-800">질문 출제 근거 보기 · {q.source_type==="job"?"채용 공고":q.source_type==="resume"?"지원자 자료":q.source_type==="both"?"공고·지원자 자료":"일반 직무 정보"}</summary><p className="mt-2 leading-relaxed text-slate-700">{q.rationale||"저장된 출제 근거 없음"}</p>{q.related_requirement&&<p className="mt-1 text-slate-600">공고 요건 · {q.related_requirement}</p>}{q.candidate_evidence&&<p className="mt-1 text-slate-600">지원자 자료 · {q.candidate_evidence}</p>}</details><p className="mt-3 rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-slate-700">{a?.skipped ? "질문을 건너뛰었습니다." : a?.text || "답변 기록 없음"}</p>{a?.assessment?.feedback && <div className="mt-3 grid gap-3 text-xs sm:grid-cols-[auto_1fr]"><p className="font-bold text-indigo-700">{a.assessment.feedback.score}점</p><div><p className="text-slate-600">{a.assessment.feedback.rationale}</p>{a.assessment.feedback.correct_concept&&<p className="mt-2 rounded-lg bg-blue-50 p-2.5 text-blue-800">개념 확인 · {a.assessment.feedback.correct_concept}</p>}{a.assessment.feedback.strengths?.length>0&&<p className="mt-2 text-emerald-700">잘한 점 · {a.assessment.feedback.strengths.join(" / ")}</p>}{a.assessment.feedback.improvements?.length>0&&<p className="mt-1 text-amber-700">보완 · {a.assessment.feedback.improvements.join(" / ")}</p>}<p className="mt-2 text-slate-500">답변 개선 예시 · {a.assessment.feedback.suggested_answer}</p></div></div>}</article>;})}</div></div>
    </div><button onClick={() => { setSession(null); onSessionChange?.(null); }} className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50">다른 면접 준비</button>
  </section>;

  const activeId = session.current_question?.interviewer_id;
  return <section className="space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-3"><button onClick={onBack} className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:bg-slate-100"><ArrowLeft size={18}/></button><div><p className="text-xs font-bold uppercase tracking-[.16em] text-indigo-600">LIVE INTERVIEW</p><h2 className="text-xl font-bold text-slate-900">{session.company_name} · {session.position}</h2></div></div><div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-2"><span className="flex items-center gap-1.5 text-xs font-semibold text-rose-600"><span className="h-2 w-2 animate-pulse rounded-full bg-rose-500"/>진행 중</span><span className="h-4 w-px bg-slate-200"/><span className="font-mono text-sm font-bold text-slate-700">{elapsed}</span><span className="h-4 w-px bg-slate-200"/><span className="text-xs font-semibold text-slate-500">질문 {questionCount}/{session.max_questions}</span></div></div>
    <div className="grid gap-5 xl:grid-cols-[300px_1fr]"><aside className={`${card} p-5`}><p className="mb-4 text-xs font-bold uppercase tracking-wider text-slate-400">면접 패널</p><div className="space-y-2">{session.interviewers.map((id)=>{const [,,focus,initials]=panel.find((item)=>item[0]===id)||[]; const active=id===activeId;return <div key={id} className={`rounded-xl border p-3 transition ${active?"border-indigo-500 bg-indigo-50 ring-2 ring-indigo-100":"border-slate-100 bg-slate-50/70"}`}><div className="flex items-center gap-3"><span className={`grid h-10 w-10 place-items-center rounded-xl text-sm font-bold ${active?"bg-indigo-600 text-white":"bg-white text-slate-500 shadow-sm"}`}>{initials}</span><div className="min-w-0 flex-1"><p className="text-xs font-bold text-slate-800">{names[id]}</p><p className="mt-0.5 truncate text-[10px] text-slate-500">{focus}</p></div></div><p className={`mt-2 text-[10px] font-semibold ${active?"text-indigo-700":"text-slate-400"}`}>{active?busy?"답변 분석 중":"현재 질문 중":"대기 중"}</p></div>})}</div><div className="mt-5 rounded-xl bg-slate-50 p-3"><p className="text-[10px] font-bold text-slate-500">면접 조건</p><p className="mt-1 text-xs text-slate-700">{typeLabels[session.interview_type]} · {session.difficulty === "advanced"?"심화":session.difficulty === "basic"?"기본":"실무"} · {session.mode === "voice"?"음성":"텍스트"}</p></div><button onClick={finish} disabled={busy} className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl border border-rose-200 px-3 py-2.5 text-xs font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-50"><Square size={13} fill="currentColor"/>면접 종료 및 결과 보기</button></aside>
      <div className={`${card} flex min-h-[640px] flex-col overflow-hidden`}><div className="border-b border-slate-100 bg-slate-50/70 px-5 py-4"><div className="flex items-center justify-between"><div><p className="text-[10px] font-bold uppercase tracking-widest text-indigo-600">INTERVIEW ROOM</p><p className="mt-1 text-xs text-slate-500">{session.company_name} · {session.position}</p></div><span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[10px] font-semibold text-slate-500">{typeLabels[session.interview_type]}</span></div></div>
        <div className="flex-1 space-y-4 overflow-y-auto p-5 sm:p-7">{session.messages.map((m)=>m.speaker==="면접관"?<div key={m.message_id} className="flex max-w-[90%] gap-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-slate-900 text-xs font-bold text-white">{panel.find((p)=>p[0]===m.interviewer_id)?.[3]}</span><div className="rounded-2xl rounded-tl-md border border-slate-200 bg-white p-4 shadow-sm"><p className="mb-1 text-[10px] font-bold text-indigo-600">{m.interviewer_name} · {m.area}{m.follow_up?" · 추가 질문":""}</p><p className="text-sm leading-relaxed text-slate-800">{m.text}</p></div></div>:<div key={m.message_id} className="ml-auto max-w-[86%]"><p className="mb-1 text-right text-[10px] font-semibold text-slate-400">지원자{m.skipped?" · 건너뜀":""}</p><div className="rounded-2xl rounded-tr-md bg-indigo-600 p-4 text-sm leading-relaxed text-white">{m.text}</div></div>)}{busy&&<div className="flex items-center gap-2 text-xs text-slate-400"><Loader2 size={14} className="animate-spin"/>답변을 검토하고 다음 질문을 준비하고 있어요</div>}<div ref={transcriptEndRef}/></div>
        {notice&&<div className="mx-5 mb-2 rounded-lg bg-indigo-50 px-3 py-2 text-xs text-indigo-800">{notice}</div>}{error&&<div role="alert" className="mx-5 mb-2 rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</div>}
        {session.current_question&&<div className="border-t border-slate-100 p-4 sm:p-5"><div className="mb-3 flex flex-wrap items-center justify-between gap-2"><span className="flex items-center gap-2 text-xs font-bold text-slate-700"><CircleHelp size={15} className="text-indigo-600"/>답변을 입력해 주세요</span><div className="flex gap-2">{session.mode==="voice"&&<><button onClick={replay} title="질문 다시 듣기" className="rounded-lg border border-slate-200 p-2 text-slate-600 hover:bg-slate-50"><Volume2 size={15}/></button><button onClick={toggleSpeechPause} title={speechPaused?"음성 이어 듣기":"음성 일시 정지"} className="rounded-lg border border-slate-200 p-2 text-slate-600 hover:bg-slate-50">{speechPaused?<Play size={15}/>:<Pause size={15}/>}</button><button onClick={stopSpeech} title="음성 재생 중단" className="rounded-lg border border-slate-200 p-2 text-slate-600 hover:bg-slate-50"><Square size={13}/></button><button onClick={()=>setMuted((v)=>!v)} title={muted?"음소거 해제":"질문 음성 음소거"} className="rounded-lg border border-slate-200 p-2 text-slate-600 hover:bg-slate-50">{muted?<VolumeX size={15}/>:<Volume2 size={15}/>}</button><button onClick={toggleMic} className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-2 text-[11px] font-semibold ${listening?"border-rose-300 bg-rose-50 text-rose-700":"border-slate-200 text-slate-600 hover:bg-slate-50"}`}>{listening?<MicOff size={14}/>:<Mic size={14}/>} {listening?"듣기 중지":"말하기"}</button></>}</div></div><textarea value={answer} onChange={(e)=>setAnswer(e.target.value)} disabled={busy} rows={4} placeholder={listening?"말씀하시면 여기에 음성 인식 결과가 표시됩니다…":"답변을 입력하세요. 음성 인식 결과도 이곳에서 수정할 수 있어요."} className="w-full resize-y rounded-xl border border-slate-300 px-3.5 py-3 text-sm leading-relaxed focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100 disabled:bg-slate-50"/><div className="mt-3 flex flex-wrap justify-between gap-2"><button onClick={skip} disabled={busy} className="flex items-center gap-1.5 rounded-xl border border-slate-200 px-3.5 py-2.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50"><SkipForward size={14}/>질문 건너뛰기</button><button onClick={submitAnswer} disabled={busy||!answer.trim()} className="flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-2.5 text-xs font-bold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300">{busy?<Loader2 size={14} className="animate-spin"/>:<Send size={14}/>}답변 제출</button></div><p className="mt-2 text-[10px] text-slate-400">면접 진행 중에는 점수와 평가를 숨기고, 종료 후 답변 근거와 함께 보여줍니다.</p></div>}
      </div></div>
  </section>;
}
