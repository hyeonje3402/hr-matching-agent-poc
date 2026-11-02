import React from "react";
import { Award, Briefcase, GraduationCap } from "lucide-react";

export default function SpecCard({ resumeData }) {
  if (!resumeData) return null;

  return (
    <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 space-y-5">
      <div className="flex items-center justify-between border-b border-slate-100 pb-4">
        <div>
          <h3 className="text-lg font-bold text-slate-900">
            {resumeData.candidate_name}{" "}
            <span className="text-sm font-normal text-slate-500">지원자 스펙 요약</span>
          </h3>
          <p className="text-xs text-slate-600 mt-1">{resumeData.overall_summary}</p>
        </div>
        <span className="bg-slate-900 text-white text-xs font-bold px-3 py-1.5 rounded-full shrink-0">
          총 경력 {resumeData.total_experience_years}년
        </span>
      </div>

      {/* 핵심 기술 스택 */}
      <div>
        <h4 className="text-xs font-semibold text-slate-500 uppercase mb-2 flex items-center gap-1.5">
          <Award className="w-4 h-4 text-indigo-500" /> 추출된 핵심 기술 스택
        </h4>
        <div className="flex flex-wrap gap-1.5">
          {resumeData.core_skills.map((skill, idx) => (
            <span
              key={idx}
              className="px-2.5 py-1 bg-slate-100 text-slate-800 rounded-md text-xs font-medium"
            >
              {skill}
            </span>
          ))}
        </div>
      </div>

      {/* 주요 프로젝트 경험 */}
      <div>
        <h4 className="text-xs font-semibold text-slate-500 uppercase mb-2.5 flex items-center gap-1.5">
          <Briefcase className="w-4 h-4 text-indigo-500" /> 주요 프로젝트 및 경력 사항
        </h4>
        <div className="space-y-3">
          {resumeData.projects.map((proj, idx) => (
            <div key={idx} className="p-3.5 rounded-lg bg-slate-50 border border-slate-200/80">
              <div className="flex justify-between items-start">
                <span className="text-sm font-bold text-slate-900">{proj.project_name}</span>
                {proj.period && (
                  <span className="text-[11px] text-slate-400">{proj.period}</span>
                )}
              </div>
              <p className="text-xs font-medium text-indigo-600 mt-0.5">{proj.role}</p>
              <p className="text-xs text-slate-600 mt-1.5 leading-relaxed">{proj.summary}</p>
              {proj.tech_stack?.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {proj.tech_stack.map((t, i) => (
                    <span
                      key={i}
                      className="text-[10px] bg-white border border-slate-200 px-1.5 py-0.5 rounded text-slate-600"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 학력 사항 */}
      <div>
        <h4 className="text-xs font-semibold text-slate-500 uppercase mb-2 flex items-center gap-1.5">
          <GraduationCap className="w-4 h-4 text-indigo-500" /> 학력 사항
        </h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {resumeData.educations.map((edu, idx) => (
            <div
              key={idx}
              className="p-3 rounded-lg bg-slate-50 border border-slate-200/80 text-xs"
            >
              <p className="font-bold text-slate-800">{edu.school_name}</p>
              <p className="text-slate-600">
                {edu.major} · {edu.degree}{" "}
                {edu.graduation_status ? `(${edu.graduation_status})` : ""}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

