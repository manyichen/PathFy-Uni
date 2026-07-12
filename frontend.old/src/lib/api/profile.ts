import { getBearerToken } from "./bearer";
import { apiFetch } from "./http";

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
  materials?: Array<{
    name: string;
    kind: string;
    status: string;
    chars?: number;
    extension?: string;
    error?: string;
    elapsed_ms?: number;
  }>;
}

async function readProfileUploadJson(res: Response): Promise<any> {
  const text = await res.text().catch(() => "");
  const trimmed = text.trim();
  if (!trimmed) {
    throw new Error(`材料解析失败：后端返回空响应（HTTP ${res.status} ${res.statusText || ""}）`);
  }
  try {
    return JSON.parse(trimmed);
  } catch {
    const preview = trimmed.length > 180 ? `${trimmed.slice(0, 180)}...` : trimmed;
    throw new Error(`材料解析失败：后端返回非 JSON 响应（HTTP ${res.status}）：${preview}`);
  }
}

export async function uploadResume(data: FormData) {
  const token = getBearerToken();
  if (!token) {
    throw new Error('请先登录');
  }
  const res = await apiFetch("/api/profile/upload", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: data,
  });

  const json = await readProfileUploadJson(res);
  if (json.code !== 200) {
    const materials = Array.isArray(json.data?.materials)
      ? json.data.materials as Array<{ name?: string; status?: string; error?: string }>
      : [];
    const materialErrors = materials
      .filter((item) => item.status && item.status !== "ok")
      .map((item) => `${item.name || "材料"}：${item.error || item.status}`)
      .join("；");
    throw new Error([json.msg || '分析失败', materialErrors].filter(Boolean).join("；"));
  }
  return json.data as PortraitResult;
}

/** 拉取单条能力画像完整行（含 detailed_analysis），供刷新后恢复下方报告区 */
export async function fetchResumePortraitResult(
  resumeId: number,
): Promise<Record<string, unknown> | null> {
  const token = getBearerToken();
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
