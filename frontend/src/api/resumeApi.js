import axios from "axios";

const apiClient = axios.create({
  baseURL: "http://localhost:8000/api",
  timeout: 90000,
});

export const fetchJobs = async () => {
  const response = await apiClient.get("/jobs");
  return response.data;
};

export const scrapeJobKorea = async (keyword, maxItems = 6) => {
  const response = await apiClient.post("/jobs/scrape-jobkorea", {
    keyword,
    max_items: maxItems,
  });
  return response.data;
};

export const uploadResumePdf = async (file) => {
  const formData = new FormData();
  formData.append("file", file);
  const response = await apiClient.post("/resume/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
};

export const getSavedResumes = async () => (await apiClient.get("/materials/resumes")).data;
export const getSavedJobMaterials = async () => (await apiClient.get("/materials/jobs")).data;
export const analyzeJobText = async (payload) => (await apiClient.post("/materials/job/text", payload)).data;
export const analyzeJobUrl = async (url) => {
  const form = new FormData(); form.append("url", url);
  return (await apiClient.post("/materials/job/url", form)).data;
};
export const analyzeJobFile = async (file) => {
  const form = new FormData(); form.append("file", file);
  return (await apiClient.post("/materials/job/file", form)).data;
};
export const compareResumeToJob = async (materialId, resumeData) =>
  (await apiClient.post("/materials/fit", { material_id: materialId, resume_data: resumeData }, { timeout: 120000 })).data;
export const updateJobMaterial = async (materialId, payload) =>
  (await apiClient.put(`/materials/jobs/${materialId}`, payload)).data;
export const getInterviewAnalytics = async () => (await apiClient.get("/interviews/analytics")).data;

export const matchResumeWithJob = async (jobId, resumeData) => {
  const response = await apiClient.post("/resume/match", {
    job_id: jobId,
    resume_data: resumeData,
  });
  return response.data;
};

export const recommendJobsForResume = async (
  resumeData,
  topK = 5,
  autoScrapeJobkorea = true,
  customKeyword = null
) => {
  const response = await apiClient.post("/resume/recommend", {
    resume_data: resumeData,
    top_k: topK,
    auto_scrape_jobkorea: autoScrapeJobkorea,
    custom_keyword: customKeyword,
  });
  return response.data;
};

export const createInterview = async (payload) => {
  const response = await apiClient.post("/interviews", payload, { timeout: 120000 });
  return response.data;
};

export const getInterviews = async () => {
  const response = await apiClient.get("/interviews");
  return response.data;
};

export const getInterview = async (sessionId) => {
  const response = await apiClient.get(`/interviews/${sessionId}`);
  return response.data;
};

export const answerInterview = async (sessionId, questionId, answer) => {
  const response = await apiClient.post(`/interviews/${sessionId}/answer`, { question_id: questionId, answer }, { timeout: 120000 });
  return response.data;
};

export const skipInterviewQuestion = async (sessionId, questionId) => {
  const response = await apiClient.post(`/interviews/${sessionId}/skip`, { question_id: questionId }, { timeout: 120000 });
  return response.data;
};

export const finishInterview = async (sessionId) => {
  const response = await apiClient.post(`/interviews/${sessionId}/finish`, {}, { timeout: 120000 });
  return response.data;
};

export const repracticeInterviewQuestion = async (sessionId, questionId) => {
  const response = await apiClient.post(`/interviews/${sessionId}/repractice`, null, {
    params: { question_id: questionId }, timeout: 120000,
  });
  return response.data;
};

export const deleteInterview = async (sessionId) => {
  await apiClient.delete(`/interviews/${sessionId}`);
};

