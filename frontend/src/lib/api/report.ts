import { getBearerToken } from "./bearer";
import { apiFetch, apiJson } from "./http";

export type ReportTargetItem = {
	job_id: string;
	title?: string;
	company?: string;
	location?: string;
	salary?: string;
	score_avg?: number;
	reason?: string;
	source?: string;
	scores?: Record<string, number>;
};

export type ImportTargetsRequest = {
	/** 人岗匹配历史记录 id（match_runs.id）；画像由记录自动带出 */
	run_id: number;
	limit?: number;
};

export type ImportTargetsResponse = {
	ok: boolean;
	data?: {
		run_id: number;
		resume_id: number;
		match_goal: "fit" | "stretch";
		source: string;
		targets: ReportTargetItem[];
	};
	message?: string;
};

export type ManualSearchTargetsRequest = {
	q: string;
	location_q?: string;
	limit?: number;
};

export type ManualSearchTargetsResponse = {
	ok: boolean;
	data?: {
		targets: ReportTargetItem[];
		count: number;
	};
	message?: string;
};

export type RandomBrowseTargetsResponse = {
	ok: boolean;
	data?: {
		seed: string;
		targets: ReportTargetItem[];
		count: number;
		total: number;
		page: number;
		page_size: number;
		total_pages: number;
	};
	message?: string;
};

export type CareerReportGenerateRequest = {
	resume_id: number;
	target_job_ids: string[];
	primary_job_id?: string;
	title?: string;
};

export type ReportTrend = {
	demand_index_0_100: number;
	growth_signal_0_100: number;
	volatility_0_100: number;
	analysis_text?: string;
	evidence?: string;
	source?: string;
	model?: string;
};

export type ReportMatchPreview = {
	match_score: number;
	weighted_gap: number;
	dimension_gaps: Record<string, number>;
	shape_correlation?: number;
};

export type ReportTargetInsight = {
	id: string;
	title: string;
	display_title?: string;
	company: string;
	location: string;
	salary: string;
	scores: Record<string, number>;
	score_avg?: number;
	trend: ReportTrend;
	match_preview: ReportMatchPreview;
};

export type DevelopmentLineNode = {
	id: string;
	label: string;
	stage: "current" | "short_term" | "mid_term" | "target";
};

/** 复盘节点展开用（由后端写入 timeline[].detail） */
export type TimelinePointDetail = {
	review_text?: string;
	submitted?: Record<string, number>;
	llm_summary?: string;
	pass_rate?: number;
	all_passed?: boolean;
};

/** 时间轴上的点：month 为月（0–12），progress 为进步度 0–100 */
export type TimelinePoint = {
	month: number;
	progress: number;
	label?: string;
	kind?: "origin" | "stage" | "review" | "adjust";
	review_id?: number;
	detail?: TimelinePointDetail;
};

export type DevelopmentLine = {
	line_id: string;
	line_name: string;
	target_job_id: string;
	overlay_group?: string;
	nodes: DevelopmentLineNode[];
	timeline?: TimelinePoint[];
};

export type DevelopmentLines = {
	display_mode?: "single";
	display_mode_default?: "overlay" | "split";
	supported_modes?: Array<"overlay" | "split">;
	axis?: {
		x_unit?: string;
		x_min?: number;
		x_max?: number;
		x_label?: string;
		y_min?: number;
		y_max?: number;
		y_label?: string;
	};
	lines: DevelopmentLine[];
	adjustments?: Array<{
		id: string;
		line_id: string;
		stage: "current" | "short_term" | "mid_term" | "target";
		label: string;
		focus_label?: string;
		priority?: number;
		created_at?: string;
		month?: number;
		progress?: number;
		/** 本条安排对应的执行目标月（1–12） */
		plan_month?: number;
		/** 触发本条安排的复盘锚点月（0 表示报告起点） */
		anchor_review_month?: number;
		kind?: "initial_plan" | "replan";
		execution_hints?: string[];
	}>;
};

export type GrowthPlanRef = {
	kind: "learning_resource" | "competition";
	id: string;
	label?: string;
	url?: string;
	rationale?: string;
	resource_type?: string;
	difficulty?: string;
	skill_tag?: string;
};

export type GrowthPlanItem = {
	phase: "short_term" | "mid_term";
	order: number;
	focus_dimension: string;
	focus_label: string;
	period: string;
	learning_path: string[];
	practice_plan: string[];
	learning_path_refs?: GrowthPlanRef[];
	practice_plan_refs?: GrowthPlanRef[];
	milestone: string;
};

export type GraphLearningResource = {
	resource_id: string;
	resource_name: string;
	resource_desc?: string;
	resource_url: string;
	resource_type?: string;
	difficulty?: string;
	source?: string;
	skill_tag?: string;
	score?: number;
	phase?: string;
	rationale?: string;
	origin?: string;
};

export type GraphCompetition = {
	competition_id: string;
	competition_name: string;
	competition_desc?: string;
	official_url: string;
	competition_type?: string;
	difficulty?: string;
	cap_tags?: string[];
	award_level?: string;
	score?: number;
	phase?: string;
	rationale?: string;
	origin?: string;
};

export type ReportRecommendationsByTarget = {
	job_id: string;
	job_title_name: string;
	match_score?: number;
	top_gaps?: string[];
	top_gap_labels?: string[];
	learning_resources: GraphLearningResource[];
	competitions: GraphCompetition[];
};

export type ReportRecommendations = {
	schema_version?: number;
	enabled?: boolean;
	by_target: ReportRecommendationsByTarget[];
	shared?: {
		learning_resources?: GraphLearningResource[];
		competitions?: GraphCompetition[];
	};
	meta?: Record<string, unknown>;
};

export type PlanPhaseBlock = {
	key: string;
	label: string;
	period: string;
	summary?: string;
	items: GrowthPlanItem[];
};

export type PlanByTarget = {
	job_id: string;
	line_id?: string;
	display_title: string;
	job_title_name?: string;
	company?: string;
	location?: string;
	match_score?: number;
	top_gaps?: string[];
	top_gap_labels?: string[];
	dimension_gaps?: Record<string, number>;
	phases: {
		early: PlanPhaseBlock;
		mid: PlanPhaseBlock;
		late: PlanPhaseBlock;
	};
	recommendations?: {
		learning_resources?: GraphLearningResource[];
		competitions?: GraphCompetition[];
	};
	narrative?: {
		path_advice?: string;
		execution_reminder?: string;
		provider?: string;
		model?: string;
	};
};

export type ReportMetric = {
	code: string;
	label: string;
	cycle: string;
	target: string;
};

export type CareerReportPayload = {
	generated_at: string;
	student: {
		id?: string;
		display_name?: string;
		scores?: Record<string, number>;
		confidences?: Record<string, number>;
		score_avg?: number;
		education?: string;
	};
	targets: ReportTargetInsight[];
	path_relations: Record<
		string,
		Array<{
			relation_type: string;
			target_id: string;
			target_title?: string;
			target_company?: string;
			target_location?: string;
		}>
	>;
	development_lines: DevelopmentLines;
	growth_plan: {
		short_term: GrowthPlanItem[];
		mid_term: GrowthPlanItem[];
	};
	evaluation: {
		cycle: {
			default: string;
			recommended: string[];
		};
		metrics: ReportMetric[];
		adjust_rule: string;
		latest_review?: {
			review_id: number;
			review_cycle: string;
			submitted_metrics: Record<string, number>;
			review_text?: string;
			llm_extract?: {
				ok?: boolean;
				source?: string;
				model?: string;
				summary?: string;
				error?: string;
			};
			evaluation: {
				rows: Array<{
					code: string;
					label: string;
					cycle: string;
					target_raw: string;
					target_value: number;
					actual_value: number;
					passed: boolean;
					missing: boolean;
				}>;
				failed_codes: string[];
				pass_rate: number;
				all_passed: boolean;
			};
			adjustment: {
				all_passed: boolean;
				pass_rate: number;
				failed_codes: string[];
				auto_adjustment: {
					triggered: boolean;
					reason?: string;
					failed_metric_codes?: string[];
					focus_dimensions?: string[];
					focus_labels?: string[];
					extra_actions?: string[];
				};
			};
			created_at: string;
		};
		adjust_rule_effective?: boolean;
		latest_adjustment_actions?: string[];
	};
	narrative?: {
		provider?: string;
		text?: string;
		error?: string;
	};
	trend_meta?: {
		ok?: boolean;
		updated?: number;
		model?: string;
		reason?: string;
	};
	recommendations?: ReportRecommendations;
	plans_by_target?: PlanByTarget[];
};

export type CareerReportGenerateResponse = {
	ok: boolean;
	data?: {
		report_id: number;
		title: string;
		primary_job_id: string;
		target_job_ids: string[];
		report: CareerReportPayload;
	};
	message?: string;
};

export type CareerReportHistoryItem = {
	report_id: number;
	title: string;
	resume_id: number;
	primary_job_id?: string;
	target_job_ids: string[];
	target_titles?: string[];
	created_at: string;
	updated_at: string;
};

export type ReportReviewItem = {
	review_id: number;
	review_cycle: string;
	metrics: {
		submitted?: Record<string, number>;
		evaluation?: {
			rows?: Array<{
				code: string;
				label: string;
				target_value: number;
				actual_value: number;
				passed: boolean;
			}>;
			pass_rate?: number;
			all_passed?: boolean;
			failed_codes?: string[];
		};
	};
	adjustment: {
		all_passed?: boolean;
		pass_rate?: number;
		failed_codes?: string[];
		auto_adjustment?: {
			triggered?: boolean;
			reason?: string;
			focus_labels?: string[];
			extra_actions?: string[];
		};
	};
	created_at: string;
};

function withAuthHeaders(): Record<string, string> {
	const headers: Record<string, string> = { "Content-Type": "application/json" };
	const token = getBearerToken();
	if (token) headers.Authorization = `Bearer ${token}`;
	return headers;
}

export async function importTargetsFromMatch(
	body: ImportTargetsRequest,
): Promise<ImportTargetsResponse["data"]> {
	const res = await apiJson<ImportTargetsResponse>("/api/report/targets/import-from-match", {
		method: "POST",
		headers: withAuthHeaders(),
		body: JSON.stringify(body),
	});
	if (!res.ok || !res.data) {
		throw new Error(res.message || "导入匹配数据失败");
	}
	return res.data;
}

export async function manualSearchTargets(
	body: ManualSearchTargetsRequest,
): Promise<ManualSearchTargetsResponse["data"]> {
	const res = await apiJson<ManualSearchTargetsResponse>("/api/report/targets/manual-search", {
		method: "POST",
		headers: withAuthHeaders(),
		body: JSON.stringify(body),
	});
	if (!res.ok || !res.data) {
		throw new Error(res.message || "手动搜索目标职业失败");
	}
	return res.data;
}

export async function fetchRandomBrowseTargets(params: {
	seed: string;
	page?: number;
	page_size?: number;
}): Promise<NonNullable<RandomBrowseTargetsResponse["data"]>> {
	const seed = params.seed.trim();
	const page = Math.max(1, params.page ?? 1);
	const pageSize = Math.max(1, Math.min(50, params.page_size ?? 20));
	const qs = new URLSearchParams({
		seed,
		page: String(page),
		page_size: String(pageSize),
	});
	const res = await apiJson<RandomBrowseTargetsResponse>(
		`/api/report/targets/random-browse?${qs.toString()}`,
		{
			method: "GET",
			headers: withAuthHeaders(),
		},
	);
	if (!res.ok || !res.data) {
		throw new Error(res.message || "加载随机岗位失败");
	}
	return res.data;
}

export async function generateCareerReport(
	body: CareerReportGenerateRequest,
): Promise<CareerReportGenerateResponse["data"]> {
	const res = await apiJson<CareerReportGenerateResponse>("/api/report/generate", {
		method: "POST",
		headers: withAuthHeaders(),
		body: JSON.stringify(body),
	});
	if (!res.ok || !res.data) {
		throw new Error(res.message || "生成生涯报告失败");
	}
	return res.data;
}

export async function fetchMyCareerReports(limit = 20): Promise<CareerReportHistoryItem[]> {
	const res = await apiJson<{
		ok: boolean;
		data?: { items: CareerReportHistoryItem[] };
		message?: string;
	}>(`/api/report/my/list?limit=${Math.max(1, Math.min(50, limit))}`, {
		method: "GET",
		headers: withAuthHeaders(),
	});
	if (!res.ok || !res.data) {
		throw new Error(res.message || "获取报告历史失败");
	}
	return res.data.items || [];
}

export async function fetchCareerReportDetail(reportId: number): Promise<CareerReportGenerateResponse["data"]> {
	const res = await apiJson<CareerReportGenerateResponse>(`/api/report/${reportId}`, {
		method: "GET",
		headers: withAuthHeaders(),
	});
	if (!res.ok || !res.data) {
		throw new Error(res.message || "获取报告详情失败");
	}
	return res.data;
}

export async function submitReportReviewCycle(body: {
	report_id: number;
	/** 已固定为按月，可省略；传了也会被后端视为 monthly */
	review_cycle?: "biweekly" | "monthly";
	metrics?: Record<string, number>;
	review_text?: string;
}): Promise<{
	review_id: number;
	report_id: number;
	review_cycle: string;
	submitted_metrics: Record<string, number>;
	review_text?: string;
	llm_extract?: {
		ok?: boolean;
		source?: string;
		model?: string;
		summary?: string;
		error?: string;
	};
	evaluation: {
		rows: Array<{
			code: string;
			label: string;
			cycle: string;
			target_raw: string;
			target_value: number;
			actual_value: number;
			passed: boolean;
			missing: boolean;
		}>;
		failed_codes: string[];
		pass_rate: number;
		all_passed: boolean;
	};
	adjustment: {
		all_passed: boolean;
		pass_rate: number;
		failed_codes: string[];
		auto_adjustment: {
			triggered: boolean;
			reason?: string;
			focus_labels?: string[];
			extra_actions?: string[];
		};
	};
}> {
	const res = await apiJson<{
		ok: boolean;
		data?: {
			review_id: number;
			report_id: number;
			review_cycle: string;
			submitted_metrics: Record<string, number>;
			review_text?: string;
			llm_extract?: {
				ok?: boolean;
				source?: string;
				model?: string;
				summary?: string;
				error?: string;
			};
			evaluation: {
				rows: Array<{
					code: string;
					label: string;
					cycle: string;
					target_raw: string;
					target_value: number;
					actual_value: number;
					passed: boolean;
					missing: boolean;
				}>;
				failed_codes: string[];
				pass_rate: number;
				all_passed: boolean;
			};
			adjustment: {
				all_passed: boolean;
				pass_rate: number;
				failed_codes: string[];
				auto_adjustment: {
					triggered: boolean;
					reason?: string;
					focus_labels?: string[];
					extra_actions?: string[];
				};
			};
		};
		message?: string;
	}>("/api/report/review-cycle", {
		method: "POST",
		headers: withAuthHeaders(),
		body: JSON.stringify(body),
	});
	if (!res.ok || !res.data) {
		throw new Error(res.message || "提交评估周期失败");
	}
	return res.data;
}

export async function fetchReportReviews(reportId: number): Promise<ReportReviewItem[]> {
	const res = await apiJson<{
		ok: boolean;
		data?: { items: ReportReviewItem[] };
		message?: string;
	}>(`/api/report/${reportId}/reviews`, {
		method: "GET",
		headers: withAuthHeaders(),
	});
	if (!res.ok || !res.data) {
		throw new Error(res.message || "获取评估历史失败");
	}
	return res.data.items || [];
}

export async function exportCareerReportPdf(reportId: number): Promise<void> {
	const token = getBearerToken();
	const headers: Record<string, string> = { Accept: "application/pdf" };
	if (token) headers.Authorization = `Bearer ${token}`;

	const res = await apiFetch(`/api/report/${reportId}/export/pdf`, {
		method: "GET",
		headers,
	});
	if (!res.ok) {
		const text = await res.text().catch(() => "");
		throw new Error(text || "导出 PDF 失败");
	}

	const blob = await res.blob();
	const url = URL.createObjectURL(blob);
	const a = document.createElement("a");
	a.href = url;
	a.download = `career_report_${reportId}.pdf`;
	document.body.appendChild(a);
	a.click();
	a.remove();
	URL.revokeObjectURL(url);
}
