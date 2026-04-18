import { apiJson } from "./api";
import type { JobCardItem } from "./jobs";

export type MockProfileSummary = {
	id: string;
	display_name: string;
	education?: string;
	city_pref?: string;
	score_avg: number;
	conf_avg: number;
};

export type MatchPreviewJob = JobCardItem & {
	match_preview: {
		match_score: number;
		weighted_gap: number;
		dimension_gaps: Record<string, number>;
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
	filters: { q: string; location_q: string };
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

type MocksListResponse = {
	ok: boolean;
	data?: { profiles: MockProfileSummary[]; note?: string };
	message?: string;
};

export async function fetchMockProfiles(): Promise<MockProfileSummary[]> {
	const res = await apiJson<MocksListResponse>("/api/profile/mocks");
	if (!res.ok || !res.data?.profiles) {
		throw new Error(res.message || "无法加载虚构画像列表");
	}
	return res.data.profiles;
}

export type MatchPreviewRequest = {
	profile_id: string;
	q?: string;
	location_q?: string;
	refine_with_llm?: boolean;
};

export async function postMatchPreview(body: MatchPreviewRequest): Promise<MatchPreviewData> {
	const res = await apiJson<MatchPreviewResponse>("/api/match/preview", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(body),
	});
	if (!res.ok || !res.data) {
		throw new Error((res as { message?: string }).message || "匹配请求失败");
	}
	return res.data;
}
