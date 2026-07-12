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
	/** 与人岗匹配一致：fit=容差6，stretch=容差10 */
	match_goal?: "fit" | "stretch";
	/** true：先快速生成画布（规则推荐），再调 enrich */
	skip_llm_enrich?: boolean;
};

/** @deprecated 旧版伪趋势，仅兼容历史报告 */
export type ReportTrend = {
	demand_index_0_100: number;
	growth_signal_0_100: number;
	volatility_0_100: number;
	analysis_text?: string;
	evidence?: string;
	source?: string;
	model?: string;
};

export type ReportTrackProfile = {
	job_title: string;
	hiring_visibility_0_100: number;
	path_breadth_0_100: number;
	resource_density_0_100: number;
	hiring?: {
		record_count?: number;
		rank?: number | null;
		pct_of_total?: number;
		company_count?: number;
		percentile?: number;
		note?: string;
	};
	paths?: {
		promotion_route_count?: number;
		lateral_similar_count?: number;
	};
	resources?: {
		learning_resource_count?: number;
		competition_count?: number;
	};
	summary_text?: string;
	evidence?: string;
	source?: string;
	data_as_of?: string;
	graph_available?: boolean;
};

export type TrackPublicInfo = {
	job_title: string;
	summary: string;
	sources?: Array<{ title?: string; url?: string }>;
	fetched_at?: string;
	expires_at?: string;
	from_cache?: boolean;
	search_provider?: string;
	disclaimer?: string;
};

export type ReportMatchPreview = {
	match_score: number;
	weighted_gap: number;
	dimension_gaps: Record<string, number>;
	dimension_raw_delta?: Record<string, number>;
	dimension_surplus?: Record<string, number>;
	student_scores?: Record<string, number>;
	job_requirement_scores?: Record<string, number>;
	soft_margin?: number;
	match_goal?: "fit" | "stretch";
	reference_note?: string;
	shape_correlation?: number;
};

export type ReportGapBaseline = {
	resume_id?: number;
	primary_job_id?: string;
	captured_at?: string;
	match_goal?: string;
	soft_margin?: number;
	match_score?: number;
	weighted_gap_job?: number;
	dimension_gaps_job?: Record<string, number>;
	by_job_id?: Record<
		string,
		{ match_score?: number; weighted_gap?: number; dimension_gaps?: Record<string, number> }
	>;
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
	track_profile?: ReportTrackProfile;
	/** @deprecated */
	trend?: ReportTrend;
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
		phase_key?: "early" | "mid" | "late";
		replan_mode?: string;
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
		kind?: "initial_plan" | "replan" | "monthly_plan";
		replan_mode?: string;
		execution_hints?: string[];
		plan_items?: GrowthPlanItem[];
		plan_item?: GrowthPlanItem;
		failed_rows?: Array<{ code: string; label: string; actual_value?: number; target_raw?: string }>;
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

export type PlanCustomAction = {
	kind: "learn" | "practice" | "deliverable";
	text: string;
	done?: boolean;
	done_at?: string;
};

export type GrowthPlanItem = {
	phase: "short_term" | "mid_term" | "late";
	order: number;
	focus_dimension: string;
	focus_label: string;
	period: string;
	learning_path: string[];
	practice_plan: string[];
	learning_path_refs?: GrowthPlanRef[];
	practice_plan_refs?: GrowthPlanRef[];
	milestone: string;
	custom_actions?: PlanCustomAction[];
	/** 下月/本项任务的成长性说明（与评估指标对齐） */
	growth_rationale?: string;
	/** 关联未达标的评估指标（中文，面向用户） */
	metric_target_labels?: string[];
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
	line_one_liner?: string;
	items: GrowthPlanItem[];
};

export type NextMonthPlan = {
	plan_month?: number;
	phase_key?: "early" | "mid" | "late";
	phase_label?: string;
	replan_mode?: string;
	items?: GrowthPlanItem[];
	updated_at?: string;
	review_anchor_month?: number;
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
	customization?: {
		provider?: string;
		model?: string;
		mode?: string;
		ok?: boolean;
	};
	current_plan_month?: number;
	next_month_plan?: NextMonthPlan;
};

export type ReportMetric = {
	code: string;
	label: string;
	description?: string;
	cycle: string;
	target: string;
};

export type CareerReportPayload = {
	generated_at: string;
	match_goal?: "fit" | "stretch";
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
		gap_baseline?: ReportGapBaseline;
		gap_metric_help?: string;
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
	track_profile_meta?: {
		ok?: boolean;
		source?: string;
		note?: string;
	};
	/** @deprecated */
	trend_meta?: {
		ok?: boolean;
		updated?: number;
		model?: string;
		reason?: string;
	};
	recommendations?: ReportRecommendations;
	plans_by_target?: PlanByTarget[];
	generation_timing_ms?: Record<string, number>;
	llm_enrich_pending?: boolean;
	enrichment?: { completed_at?: string; timing_ms?: Record<string, number> };
};

export type CareerReportGenerateResponse = {
	ok: boolean;
	data?: {
		report_id: number;
		title: string;
		primary_job_id: string;
		target_job_ids: string[];
		report: CareerReportPayload;
		generation_timing_ms?: Record<string, number>;
		llm_enrich_pending?: boolean;
	};
	message?: string;
};

export type CareerReportEnrichResponse = {
	ok: boolean;
	data?: {
		report_id: number;
		report: CareerReportPayload;
		enrichment_timing_ms?: Record<string, number>;
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

export async function enrichCareerReport(
	reportId: number,
): Promise<NonNullable<CareerReportEnrichResponse["data"]>> {
	const res = await apiJson<CareerReportEnrichResponse>(`/api/report/${reportId}/enrich`, {
		method: "POST",
		headers: withAuthHeaders(),
		body: JSON.stringify({}),
	});
	if (!res.ok || !res.data) {
		throw new Error(res.message || "报告 AI 增强失败");
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

export async function fetchTrackPublicInfo(body: {
	job_title?: string;
	job_id?: string;
	force_refresh?: boolean;
}): Promise<TrackPublicInfo> {
	const res = await apiJson<{ ok: boolean; data?: TrackPublicInfo; message?: string }>(
		"/api/report/track-public-info",
		{
			method: "POST",
			headers: withAuthHeaders(),
			body: JSON.stringify(body),
		},
	);
	if (!res.ok || !res.data) {
		throw new Error(res.message || "获取公开信息失败");
	}
	return res.data;
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

export async function setReportPlanActionDone(
	reportId: number,
	body: {
		job_id: string;
		item_index: number;
		action_index: number;
		done: boolean;
	},
): Promise<{
	report_id: number;
	job_id: string;
	item_index: number;
	action_index: number;
	done: boolean;
	done_at?: string;
}> {
	const res = await apiJson<{
		ok: boolean;
		data?: {
			report_id: number;
			job_id: string;
			item_index: number;
			action_index: number;
			done: boolean;
			done_at?: string;
		};
		message?: string;
	}>(`/api/report/${reportId}/plan-actions/done`, {
		method: "POST",
		headers: withAuthHeaders(),
		body: JSON.stringify(body),
	});
	if (!res.ok || !res.data) {
		throw new Error(res.message || "保存任务状态失败");
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
