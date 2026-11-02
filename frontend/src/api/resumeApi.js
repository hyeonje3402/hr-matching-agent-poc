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

