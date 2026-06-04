import { apiJson } from "./http";
import { getBearerToken } from "./bearer";

// ============================================================
// 类型定义
// ============================================================

export interface GraphStats {
	job_count: number;
	company_count: number;
	skill_count: number;
	certificate_count: number;
	softskill_count: number;
	careerlevel_count: number;
	belongs_to_count: number;
	requires_count: number;
	vertical_up_count: number;
}

export interface ImportResult {
	total_jobs: number;
	batches_completed: number;
	batches_failed: number;
	core_templates: string[];
	errors: string[];
}

// ============================================================
// 内部响应类型
// ============================================================

type StatsResponse = { ok: boolean; data?: GraphStats; message?: string };
type ImportResponse = { ok: boolean; data?: ImportResult; message?: string };
type ClearResponse = { ok: boolean; message?: string; data?: { deleted_nodes: number } };

// ============================================================
// 认证辅助
// ============================================================

function authHeaders(): HeadersInit {
	const token = getBearerToken();
	if (!token) {
		throw new Error("请先登录后再操作");
	}
	return {
		Authorization: `Bearer ${token}`,
		"Content-Type": "application/json",
	};
}

// ============================================================
// API 函数
// ============================================================

export async function fetchGraphStats(): Promise<GraphStats> {
	const res = await apiJson<StatsResponse>("/api/graph/stats", {
		method: "GET",
		headers: authHeaders(),
	});
	if (!res.ok || !res.data) {
		throw new Error(res.message || "获取图谱统计失败");
	}
	return res.data;
}

export async function importJobs(
	file: File,
	batchSize: number = 128,
	clearAll: boolean = false,
): Promise<ImportResult> {
	const formData = new FormData();
	formData.append("file", file);
	formData.append("batch_size", String(batchSize));
	formData.append("clear_all", clearAll ? "true" : "false");

	const token = getBearerToken();
	if (!token) {
		throw new Error("请先登录后再操作");
	}

	const baseUrl = import.meta.env.PUBLIC_API_BASE || "";
	const resp = await fetch(`${baseUrl}/api/graph/import-jobs`, {
		method: "POST",
		headers: { Authorization: `Bearer ${token}` },
		body: formData,
	});

	if (!resp.ok) {
		let msg = `请求失败（${resp.status}）`;
		try {
			const body = await resp.json();
			if (body?.message) msg = body.message;
		} catch { /* ignore */ }
		throw new Error(msg);
	}

	const res: ImportResponse = await resp.json();
	if (!res.ok || !res.data) {
		throw new Error(res.message || "导入岗位失败");
	}
	return res.data;
}

export async function clearGraph(): Promise<void> {
	const res = await apiJson<ClearResponse>("/api/graph/clear", {
		method: "POST",
		headers: authHeaders(),
		body: JSON.stringify({ confirmed: true }),
	});
	if (!res.ok) {
		throw new Error(res.message || "清空图谱失败");
	}
}

// ============================================================
// QC 报告 & 岗位名称
// ============================================================

export interface JobTitleItem {
	id: number;
	title: string;
	record_count: number;
	company_count: number;
	job_code_count: number;
	updated_at: string;
}

export interface QCReportResult {
	total: number;
	success: number;
	failed: number;
	success_rate: number;
	low_confidence_count: number;
	avg_scores: Record<string, number>;
	distribution: Record<string, Record<string, number>>;
	top_low_confidence: Array<{ job_id: string; min_conf_key: string; min_conf_value: number; low_conf_dims: string }>;
	top_failures: Array<{ reason: string; count: number }>;
	report_path: string;
	csv_path: string;
}

type JobTitlesResponse = { ok: boolean; data?: { total: number; titles: JobTitleItem[] }; message?: string };
type QCReportResponse = { ok: boolean; data?: QCReportResult; message?: string };

export async function fetchJobTitles(): Promise<{ total: number; titles: JobTitleItem[] }> {
	const res = await apiJson<JobTitlesResponse>("/api/graph/job-titles", {
		method: "GET",
		headers: authHeaders(),
	});
	if (!res.ok || !res.data) {
		throw new Error(res.message || "获取岗位名称列表失败");
	}
	return res.data;
}

export async function generateQCReport(inputFile?: string, threshold?: number): Promise<QCReportResult> {
	const res = await apiJson<QCReportResponse>("/api/graph/qc-report", {
		method: "POST",
		headers: authHeaders(),
		body: JSON.stringify({
			input_file: inputFile || "",
			threshold: threshold ?? 0.60,
		}),
	});
	if (!res.ok || !res.data) {
		throw new Error(res.message || "生成质检报告失败");
	}
	return res.data;
}

// ============================================================
// 图谱智能生成
// ============================================================

export interface SyncResult {
	dry_run: boolean;
	[key: string]: any;
}

type SyncResponse = { ok: boolean; data?: SyncResult; message?: string };

export async function syncJobTitles(dryRun: boolean = false): Promise<SyncResult> {
	const res = await apiJson<SyncResponse>("/api/graph/sync/job-titles", {
		method: "POST",
		headers: authHeaders(),
		body: JSON.stringify({ dry_run: dryRun }),
	});
	if (!res.ok || !res.data) throw new Error(res.message || "同步岗位名称失败");
	return res.data;
}

export async function generatePromotionPaths(dryRun: boolean = false): Promise<SyncResult> {
	const res = await apiJson<SyncResponse>("/api/graph/generate/promotion-paths", {
		method: "POST",
		headers: authHeaders(),
		body: JSON.stringify({ dry_run: dryRun }),
	});
	if (!res.ok || !res.data) throw new Error(res.message || "生成晋升路径失败");
	return res.data;
}

export async function generateLateralTransfers(dryRun: boolean = false): Promise<SyncResult> {
	const res = await apiJson<SyncResponse>("/api/graph/generate/lateral-transfers", {
		method: "POST",
		headers: authHeaders(),
		body: JSON.stringify({ dry_run: dryRun }),
	});
	if (!res.ok || !res.data) throw new Error(res.message || "生成换岗关系失败");
	return res.data;
}

export async function generateLearningResources(dryRun: boolean = false): Promise<SyncResult> {
	const res = await apiJson<SyncResponse>("/api/graph/generate/learning-resources", {
		method: "POST",
		headers: authHeaders(),
		body: JSON.stringify({ dry_run: dryRun }),
	});
	if (!res.ok || !res.data) throw new Error(res.message || "生成学习资源失败");
	return res.data;
}

export async function generateCompetitions(dryRun: boolean = false): Promise<SyncResult> {
	const res = await apiJson<SyncResponse>("/api/graph/generate/competitions", {
		method: "POST",
		headers: authHeaders(),
		body: JSON.stringify({ dry_run: dryRun }),
	});
	if (!res.ok || !res.data) throw new Error(res.message || "生成竞赛失败");
	return res.data;
}
