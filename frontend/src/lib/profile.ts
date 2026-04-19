import { getToken } from "./auth";
import { apiFetch } from "./api";

export interface PortraitScores {
  cap_req_theory: number;
  cap_req_cross: number;
  cap_req_practice: number;
  cap_req_digital: number;
  cap_req_innovation: number;
  cap_req_teamwork: number;
  cap_req_social: number;
  cap_req_growth: number;
}

export interface PortraitConfidences {
  cap_conf_theory: number;
  cap_conf_cross: number;
  cap_conf_practice: number;
  cap_conf_digital: number;
  cap_conf_innovation: number;
  cap_conf_teamwork: number;
  cap_conf_social: number;
  cap_conf_growth: number;
}

export interface PortraitResult {
  resume_id: number;
  scores: PortraitScores;
  confidences?: PortraitConfidences;
  completeness: number;
  competitiveness: number;
  detailed_analysis?: any;
}

export async function uploadResume(data: FormData) {
  const headers: HeadersInit = {};
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const res = await apiFetch("/api/profile/upload", {
    method: "POST",
    headers,
    body: data,
  });

  const json = await res.json();
  if (json.code !== 200) throw new Error(json.msg || '分析失败');
  return json.data as PortraitResult;
}

/** 拉取单条简历画像完整行（含 detailed_analysis），供刷新后恢复下方报告区 */
export async function fetchResumePortraitResult(
  resumeId: number,
): Promise<Record<string, unknown> | null> {
  const token = getToken();
  if (!token) return null;
  const res = await apiFetch(`/api/profile/result/${resumeId}`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return null;
  const json = (await res.json()) as {
    code?: number;
    data?: Record<string, unknown>;
  };
  if (json.code !== 200 || !json.data) return null;
  const data = { ...json.data };
  const da = data.detailed_analysis;
  if (typeof da === "string") {
    try {
      data.detailed_analysis = JSON.parse(da);
    } catch {
      data.detailed_analysis = null;
    }
  }
  return data;
}