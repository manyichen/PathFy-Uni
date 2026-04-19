import { getToken } from "./auth";
import { apiFetch, apiJson } from "./api";
import type { JobCardItem } from "./jobs";

export type MatchPreviewJob = JobCardItem & {
	match_preview: {
		match_score: number;
		weighted_gap: number;
		dimension_gaps: Record<string, number>;
		/** 八维得分 Pearson 相关，粗排形状项用 */
		shape_correlation?: number;
	};
};

export type MatchStudentPayload = {
	id?: string;
	display_name?: string;
	vector_kind?: string;
	scores: JobCardItem["scores"];
	confidences: JobCardItem["confidences"];
	score_avg?: number;
	conf_avg?: number;
	education?: string;
	city_pref?: string;
	skills_hint?: string[];
	resume_excerpt?: string;
};

export type LlmTop5Item = {
	job_id: string;
	rank: number;
	overall_fit_0_100: number;
	one_line: string;
	strengths: string[];
	gaps: string[];
	risks: string[];
	llm_fallback?: boolean;
	title?: string;
	company?: string;
	location?: string;
	salary?: string;
	/** 岗位八维需求分（后端精排装饰字段，便于前端雷达） */
	scores?: JobCardItem["scores"];
	coarse_match_score?: number;
};

export type MatchLlmBlock = {
	ok: boolean;
	error?: string;
	model?: string;
	pool_size?: number;
	top5?: LlmTop5Item[];
	raw_snippet?: string;
};

export type MatchPreviewData = {
	student: MatchStudentPayload;
	filters: { q: string; location_q: string; match_goal?: "fit" | "stretch" };
	scoring: Record<string, unknown>;
	stats: {
		scanned: number;
		scan_cap: number;
		returned: number;
		match_top_k_return?: number;
		match_llm_pool_k?: number;
		llm_pool_size?: number;
	};
	jobs: MatchPreviewJob[];
	llm?: MatchLlmBlock;
};

export type MatchPreviewResponse = {
	ok: boolean;
	data?: MatchPreviewData;
	message?: string;
};

export type MyResumeSummary = {
	id: number;
	name: string;
	major: string;
	create_time: string | null;
	completeness?: number;
	competitiveness?: number;
	score_avg: number;
	scores: JobCardItem["scores"];
};

/** 当前登录用户在库中的能力画像列表（需 Bearer）；未登录返回空数组。 */
export async function fetchMyResumes(): Promise<MyResumeSummary[]> {
	const token = getToken();
	if (!token) return [];
	const res = await apiFetch("/api/profile/resumes", {
		method: "GET",
		headers: { Authorization: `Bearer ${token}` },
	});
	if (!res.ok) return [];
	const json = (await res.json()) as {
		code?: number;
		data?: MyResumeSummary[];
	};
	if (json.code !== 200 || !Array.isArray(json.data)) return [];
	return json.data;
}

export type MatchPreviewRequest = {
	/** 能力画像记录 id；需登录并在请求头携带 Bearer */
	resume_id?: number;
	q?: string;
	location_q?: string;
	refine_with_llm?: boolean;
	/** fit=按吻合度粗排；stretch=冲刺高质（粗排抬高岗位需求强度） */
	match_goal?: "fit" | "stretch";
};

export async function postMatchPreview(body: MatchPreviewRequest): Promise<MatchPreviewData> {
	const headers: Record<string, string> = { "Content-Type": "application/json" };
	const token = getToken();
	if (token) {
		headers.Authorization = `Bearer ${token}`;
	}
	const res = await apiJson<MatchPreviewResponse>("/api/match/preview", {
		method: "POST",
		headers,
		body: JSON.stringify(body),
	});
	if (!res.ok || !res.data) {
		throw new Error((res as { message?: string }).message || "匹配请求失败");
	}
	return res.data;
}
