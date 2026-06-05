<script lang="ts">
	import { onMount } from "svelte";
	import {
		fetchMyResumes,
		type MatchHistoryDetail,
		type MyResumeSummary,
	} from "@/lib/api/match";
	import MatchHistoryModal from "@components/match/MatchHistoryModal.svelte";
	import ManualTargetSearchModal from "@components/report/ManualTargetSearchModal.svelte";
	import ReportHistoryModal from "@components/report/ReportHistoryModal.svelte";
	import {
		fetchCareerReportDetail,
		fetchReportReviews,
		exportCareerReportPdf,
		fetchTrackPublicInfo,
		enrichCareerReport,
		generateCareerReport,
		importTargetsFromMatch,
		type CareerReportGenerateResponse,
		type CareerReportPayload,
		type ReportTargetInsight,
		type ReportTrackProfile,
		type TrackPublicInfo,
		type ReportReviewItem,
		type ReportTargetItem,
		type TimelinePoint,
		submitReportReviewCycle,
		setReportPlanActionDone,
	} from "@/lib/api/report";
	import { portal } from "@/lib/portal";
	import {
		loadReportWorkspace,
		persistReportWorkspace,
		readWorkspaceBootstrap,
		type ReportWorkspaceCacheV1,
	} from "@/lib/report-workspace-cache";
	import {
		collectActionDoneMap,
		mergeActionDoneMaps,
		mergeReportActionProgress,
		nextMonthActionKey,
		nextMonthItemKey,
		cloneReportPayload,
	} from "@/lib/report-action-progress";

	const workspaceBoot = readWorkspaceBootstrap();

	function bootActiveJobId(boot: typeof workspaceBoot): string {
		const targets = boot?.reportSnapshot?.targets || [];
		if (!targets.length) return boot?.activeJobId ?? "";
		const ids = new Set(targets.map((t) => t.id));
		if (boot?.activeJobId && ids.has(boot.activeJobId)) return boot.activeJobId;
		return targets[0]?.id ?? "";
	}

	function bootFocusLineId(boot: typeof workspaceBoot): string {
		const lines = boot?.reportSnapshot?.development_lines?.lines || [];
		if (!lines.length) return boot?.focusLineId ?? "";
		const ids = new Set(lines.map((l) => l.line_id));
		if (boot?.focusLineId && ids.has(boot.focusLineId)) return boot.focusLineId;
		return (
			boot?.reportSnapshot?.plans_by_target?.[0]?.line_id ||
			lines[0]?.line_id ||
			""
		);
	}

	const DIMENSION_LABELS: Record<string, string> = {
		cap_req_theory: "理论",
		cap_req_cross: "交叉",
		cap_req_practice: "实践",
		cap_req_digital: "数字",
		cap_req_innovation: "创新",
		cap_req_teamwork: "协作",
		cap_req_social: "社会",
		cap_req_growth: "成长",
	};

	const STAGE_LABELS: Record<string, string> = {
		current: "当前画像",
		short_term: "前期",
		mid_term: "中期",
		late: "后期",
		target: "目标岗位",
		early: "前期",
		mid: "中期",
	};

	function phaseLabelFromKey(key: string | undefined): string {
		if (!key) return "";
		return STAGE_LABELS[key] || key;
	}

	const ACTION_KIND_LABELS: Record<string, string> = {
		learn: "学习",
		practice: "实践",
		deliverable: "成果",
	};

	function actionKindLabel(kind: string | undefined): string {
		return ACTION_KIND_LABELS[String(kind || "").toLowerCase()] || "实践";
	}

	const ACTION_KIND_COLORS: Record<string, string> = {
		learn: "#3b82f6",
		practice: "#f59e0b",
		deliverable: "#10b981",
	};

	const bootActionDone = mergeActionDoneMaps(
		workspaceBoot?.nextMonthActionDone,
		collectActionDoneMap(workspaceBoot?.reportSnapshot ?? null),
	);

	let nextMonthSectionOpen = $state(workspaceBoot?.nextMonthSectionOpen ?? true);
	let nextMonthItemOpen = $state<Record<string, boolean>>({ ...(workspaceBoot?.nextMonthItemOpen || {}) });
	let nextMonthActionDone = $state<Record<string, boolean>>(bootActionDone);

	function isNextMonthItemOpen(itemKey: string, defaultOpen: boolean): boolean {
		if (itemKey in nextMonthItemOpen) return !!nextMonthItemOpen[itemKey];
		return defaultOpen;
	}

	function toggleNextMonthItem(itemKey: string, defaultOpen: boolean): void {
		const open = isNextMonthItemOpen(itemKey, defaultOpen);
		nextMonthItemOpen = { ...nextMonthItemOpen, [itemKey]: !open };
		persistReportWorkspaceState();
	}

	function isNextMonthActionDone(
		act: { done?: boolean },
		actionKey: string,
	): boolean {
		if (act.done != null) return !!act.done;
		return !!nextMonthActionDone[actionKey];
	}

	async function toggleNextMonthAction(
		jobId: string,
		itemIndex: number,
		focusDimension: string,
		actionIndex: number,
	): Promise<void> {
		if (!generatedReportId || !generatedReport) return;
		const itemKey = nextMonthItemKey(jobId, itemIndex, focusDimension);
		const actionKey = nextMonthActionKey(itemKey, actionIndex);
		const plan = generatedReport.plans_by_target?.find((p) => p.job_id === jobId);
		const item = plan?.next_month_plan?.items?.[itemIndex];
		const action = item?.custom_actions?.[actionIndex];
		if (!action) return;

		const prevDone = isNextMonthActionDone(action, actionKey);
		const newDone = !prevDone;

		action.done = newDone;
		if (newDone) {
			action.done_at = new Date().toISOString().slice(0, 19).replace("T", " ");
		} else {
			delete action.done_at;
		}
		generatedReport = cloneReportPayload(generatedReport);
		nextMonthActionDone = { ...nextMonthActionDone, [actionKey]: newDone };
		persistReportWorkspaceState();

		try {
			const saved = await setReportPlanActionDone(generatedReportId, {
				job_id: jobId,
				item_index: itemIndex,
				action_index: actionIndex,
				done: newDone,
			});
			const savedPlan = generatedReport.plans_by_target?.find((p) => p.job_id === jobId);
			const savedAction = savedPlan?.next_month_plan?.items?.[itemIndex]?.custom_actions?.[actionIndex];
			if (savedAction) {
				savedAction.done = saved.done;
				if (saved.done_at) savedAction.done_at = saved.done_at;
				else delete savedAction.done_at;
				generatedReport = cloneReportPayload(generatedReport);
			}
			persistReportWorkspaceState();
		} catch {
			const rollbackPlan = generatedReport.plans_by_target?.find((p) => p.job_id === jobId);
			const rollbackAction =
				rollbackPlan?.next_month_plan?.items?.[itemIndex]?.custom_actions?.[actionIndex];
			if (rollbackAction) {
				rollbackAction.done = prevDone;
				if (prevDone) {
					/* keep prior done_at if any */
				} else {
					delete rollbackAction.done_at;
				}
				generatedReport = cloneReportPayload(generatedReport);
			}
			nextMonthActionDone = { ...nextMonthActionDone, [actionKey]: prevDone };
			error = "任务完成状态保存失败，请稍后重试。";
		}
	}

	function countActionKinds(actions: { kind?: string }[] | undefined): {
		learn: number;
		practice: number;
		deliverable: number;
		total: number;
	} {
		const c = { learn: 0, practice: 0, deliverable: 0, total: 0 };
		for (const a of actions || []) {
			const k = String(a.kind || "practice").toLowerCase();
			if (k === "learn" || k === "practice" || k === "deliverable") {
				c[k]++;
				c.total++;
			}
		}
		return c;
	}

	function replanModeMeta(mode: string | undefined): { label: string; tone: "warn" | "ok" | "neutral" } {
		if (mode === "strong") return { label: "加强模式", tone: "warn" };
		if (mode === "continue") return { label: "稳步延续", tone: "ok" };
		if (mode === "light") return { label: "微调补强", tone: "neutral" };
		if (mode === "initial") return { label: "起步安排", tone: "neutral" };
		return { label: "下月重点", tone: "neutral" };
	}
	const LINE_COLORS = ["#3b82f6", "#8b5cf6", "#10b981", "#f59e0b", "#ef4444"];

	const PHASE_PERIOD_DEFAULTS: Record<"early" | "mid" | "late", string> = {
		early: "0-3个月",
		mid: "3-9个月",
		late: "9-12个月",
	};

	function phasePeriodDisplay(key: "early" | "mid" | "late", period?: string): string {
		const p = (period || "").trim();
		if (!p) return PHASE_PERIOD_DEFAULTS[key];
		if (key === "mid" && (p.includes("3-12") || p === "3-12个月")) return PHASE_PERIOD_DEFAULTS.mid;
		if (key === "late" && (p.includes("12个月+") || /^12/.test(p))) return PHASE_PERIOD_DEFAULTS.late;
		return p;
	}

	/** 一键填充：覆盖常见复盘维度，便于 DeepSeek 量化 */
	const REVIEW_TEMPLATE = `本周期（写一下具体日期或第几周）：

【做过的事】
（学习、实习、项目、比赛、课程等，尽量写清做了什么、做到哪一步）

【能力短板】
（哪块变强了、哪块还弱；如果估得出来，写「大概好了百分之几」）

【和目标岗位】
（简历/匹配感受：更好、差不多、还是更难了；能写「感觉多了 X 分」更好）

【能拿得出手的成果】
（例如：上线项目 1 个、比赛名次、技术文章、证书等，写数量）

【卡点与下周打算】
（当前最卡的一件事 + 下周最想推进的一件事）`;

	const METRIC_FRIENDLY_LABELS: Record<string, string> = {
		dim_gap_reduction: "能力短板补上了多少",
		project_completion: "本期计划做完了多少",
		match_score_change: "和目标岗位的贴合度变化",
		delivery_output: "可拿出来展示的成果有多少",
	};

	const METRIC_CODE_DISPLAY: Record<string, string> = {
		dim_gap_reduction: "能力短板缩小",
		project_completion: "计划完成",
		match_score_change: "岗位贴合度",
		delivery_output: "可展示成果",
		cap_req_theory: "专业理论知识",
		cap_req_cross: "交叉学科广度",
		cap_req_practice: "专业实践技能",
		cap_req_digital: "数字素养技能",
		cap_req_innovation: "创新创业能力",
		cap_req_teamwork: "团队协作能力",
		cap_req_social: "社会实践网络",
		cap_req_growth: "学习与发展潜力",
	};

	const METRIC_QUESTION_TO_SHORT: Record<string, string> = {
		能力短板补上了多少: "能力短板缩小",
		本期计划做完了多少: "计划完成",
		和目标岗位的贴合度变化: "岗位贴合度",
		可拿出来展示的成果有多少: "可展示成果",
	};

	/** 展示用：去掉英文 code 与开发向表述（兼容历史报告 JSON） */
	function sanitizePlanDisplayText(text: string | undefined): string {
		let out = String(text ?? "").trim();
		if (!out) return out;
		for (const [phrase, short] of Object.entries(METRIC_QUESTION_TO_SHORT)) {
			out = out.replaceAll(phrase, short);
		}
		for (const [code, label] of Object.entries(METRIC_CODE_DISPLAY).sort(
			(a, b) => b[0].length - a[0].length,
		)) {
			if (!label || !out.includes(code)) continue;
			out = out.replaceAll(`\`${code}\``, label);
			out = out.replace(new RegExp(`\\b${code}\\b`, "gi"), label);
		}
		out = out.replace(/当前匹配约\s*\d+(?:\.\d+)?\s*分[,，]?\s*/g, "");
		out = out.replace(/[,，]\s*拉动[^。；！？\n]+/g, "");
		out = out.replace(/以拉动[^。；！？\n]+/g, "");
		out = out.replace(/拉动(?:完成率|贴合度|成果|短板)[^。；！？\n]*/g, "");
		out = out.replace(/四项评估指标/g, "月度目标");
		out = out.replace(/短板收敛/g, "能力短板缩小");
		out = out.replace(/\s{2,}/g, " ");
		out = out.replace(/[,，]{2,}/g, "，");
		out = out.replace(/^[，,；;·\s]+/, "");
		return out.trim();
	}

	const METRIC_FRIENDLY_DESCRIPTIONS: Record<string, string> = {
		dim_gap_reduction: "主目标岗位上的能力短板，比生成报告时缩小了多少。",
		project_completion: "本期成长计划里的任务，你完成了多少。",
		match_score_change: "你与目标岗位的匹配程度，比生成报告时提高了多少。",
		delivery_output: "本期新增的可验证成果（项目、证书、作品等）有多少。",
	};

	let resumes = $state<MyResumeSummary[]>([]);
	let selectedResumeId = $state<number | "">(workspaceBoot?.selectedResumeId ?? "");
	let matchImportModalOpen = $state(false);
	let reportHistoryModalOpen = $state(false);
	let manualSearchModalOpen = $state(false);
	let loadingImport = $state(false);
	let loadingGenerate = $state(false);
	let loadingEnrich = $state(false);
	let generateProgress = $state("");
	let error = $state("");
	let info = $state(workspaceBoot?.infoMessage ?? "");

	let selectedTargets = $state<ReportTargetItem[]>(
		(workspaceBoot?.selectedTargets || []).slice(0, 5),
	);
	let generatedReportId = $state<number | null>(workspaceBoot?.reportId ?? null);
	let generatedReport = $state<CareerReportPayload | null>(
		workspaceBoot?.reportSnapshot
			? mergeReportActionProgress(workspaceBoot.reportSnapshot, [], bootActionDone)
			: null,
	);
	let reviewHistory = $state<ReportReviewItem[]>([]);
	let focusLineId = $state(bootFocusLineId(workspaceBoot));
	let selectedAdjustmentId = $state(workspaceBoot?.selectedAdjustmentId ?? "");
	let highlightedMetricCode = $state("");
	let selectedTimelineReviewId = $state<number | null>(
		typeof workspaceBoot?.selectedTimelineReviewId === "number"
			? workspaceBoot.selectedTimelineReviewId
			: null,
	);
	let selectedCanvasMonth = $state<number | null>(
		typeof workspaceBoot?.selectedCanvasMonth === "number" ? workspaceBoot.selectedCanvasMonth : null,
	);
	let submittingReview = $state(false);
	let reviewError = $state("");
	let reviewInfo = $state("");
	let reviewText = $state("");
	let exportingPdf = $state(false);
	let activeJobId = $state(bootActiveJobId(workspaceBoot));
	let activePhase = $state<"early" | "mid" | "late">(
		workspaceBoot?.activePhase === "mid" || workspaceBoot?.activePhase === "late"
			? workspaceBoot.activePhase
			: "early",
	);
	let configRailCollapsed = $state(!!workspaceBoot?.configRailCollapsed);
	/** 与人岗匹配导入一致，影响报告缺口容差（fit=6 / stretch=10） */
	let reportMatchGoal = $state<"fit" | "stretch">(
		workspaceBoot?.reportMatchGoal === "stretch" ? "stretch" : "fit",
	);

	let canvasZoomOpen = $state(false);

	const CHART_INLINE = { w: 700, h: 300, l: 50, r: 18, t: 26, b: 46 };
	const CHART_WORKBENCH = { w: 920, h: 360, l: 52, r: 22, t: 28, b: 50 };
	const CHART_LARGE = { w: 960, h: 440, l: 56, r: 28, t: 32, b: 52 };
	const GAP_BAR_SCALE = 30;

	const plansByTarget = $derived.by(() => generatedReport?.plans_by_target ?? []);
	const usePerJobPlan = $derived.by(() => plansByTarget.length > 0);
	const activePlan = $derived.by(
		() => plansByTarget.find((p) => p.job_id === activeJobId) ?? plansByTarget[0] ?? null,
	);
	const activePhaseBlock = $derived.by(() => {
		const p = activePlan;
		if (!p?.phases) return null;
		return p.phases[activePhase] ?? null;
	});
	const activeTargetRow = $derived.by(() => {
		if (!generatedReport?.targets?.length) return null;
		return (
			generatedReport.targets.find((t) => t.id === activeJobId) ?? generatedReport.targets[0] ?? null
		);
	});

	const focusTarget = $derived.by(() => {
		if (!generatedReport?.targets?.length) return null;
		if (!focusLineId) return generatedReport.targets[0] || null;
		const line = generatedReport.development_lines.lines.find((x) => x.line_id === focusLineId);
		if (!line) return generatedReport.targets[0] || null;
		return generatedReport.targets.find((x) => x.id === line.target_job_id) || generatedReport.targets[0] || null;
	});

	const trackRows = $derived.by(() => generatedReport?.targets || []);

	type PublicInfoState = {
		loading: boolean;
		error: string;
		data: TrackPublicInfo | null;
	};

	let publicInfoByJobId = $state<Record<string, PublicInfoState>>({});

	function resolveTrackProfile(row: ReportTargetInsight): ReportTrackProfile | null {
		if (row.track_profile) return row.track_profile;
		const t = row.trend;
		if (!t) return null;
		return {
			job_title: row.title || "未知岗位",
			hiring_visibility_0_100: Number(t.demand_index_0_100 || 0),
			path_breadth_0_100: Number(t.growth_signal_0_100 || 0),
			resource_density_0_100: Number(t.volatility_0_100 || 0),
			summary_text: t.analysis_text,
			source: "legacy_trend",
		};
	}

	function trackBarWidth(score: number): string {
		return `${Math.max(0, Math.min(100, Number(score || 0)))}%`;
	}

	function trackLevelLabel(score: number): string {
		const v = Number(score || 0);
		if (v >= 70) return "偏高";
		if (v >= 40) return "中等";
		return "偏低";
	}

	function trackInsightLine(tp: import("$lib/api/report").ReportTrackProfile): string {
		const hiring = trackLevelLabel(tp.hiring_visibility_0_100);
		const path = trackLevelLabel(tp.path_breadth_0_100);
		const res = trackLevelLabel(tp.resource_density_0_100);
		const rc = Number(tp.hiring?.record_count || 0);
		const rank = tp.hiring?.rank;
		let heat = "招聘热度一般";
		if (rank != null && rank <= 3) heat = "招聘热度在本库排名靠前";
		else if (rank != null) heat = `招聘热度在本库约第 ${rank} 名`;
		else if (rc >= 50) heat = `系统收录 ${rc} 条相关招聘信息，较活跃`;
		return `整体上招聘${hiring}、发展路径${path}、学习资源${res}。${heat}。`;
	}

	async function loadPublicInfo(row: ReportTargetInsight, force = false): Promise<void> {
		const jid = row.id;
		publicInfoByJobId = {
			...publicInfoByJobId,
			[jid]: { loading: true, error: "", data: publicInfoByJobId[jid]?.data ?? null },
		};
		try {
			const data = await fetchTrackPublicInfo({
				job_id: jid,
				job_title: row.track_profile?.job_title || row.title,
				force_refresh: force,
			});
			publicInfoByJobId = {
				...publicInfoByJobId,
				[jid]: { loading: false, error: "", data },
			};
		} catch (e) {
			publicInfoByJobId = {
				...publicInfoByJobId,
				[jid]: {
					loading: false,
					error: e instanceof Error ? e.message : "获取失败",
					data: null,
				},
			};
		}
	}

	function dimensionGapsOf(t: { match_preview?: { dimension_gaps?: Record<string, number> } }) {
		return t.match_preview?.dimension_gaps || {};
	}

	const heatmapDimensions = $derived.by(() => {
		if (!generatedReport?.targets?.length) return [];
		const sum: Record<string, number> = {};
		for (const t of generatedReport.targets) {
			const gaps = dimensionGapsOf(t);
			for (const [k, v] of Object.entries(gaps)) {
				sum[k] = (sum[k] || 0) + Number(v || 0);
			}
		}
		return Object.entries(sum)
			.sort((a, b) => b[1] - a[1])
			.slice(0, 5)
			.map(([k]) => k);
	});

	const maxGapValue = $derived.by(() => {
		if (!generatedReport?.targets?.length) return 1;
		let max = 1;
		for (const t of generatedReport.targets) {
			for (const v of Object.values(dimensionGapsOf(t))) {
				max = Math.max(max, Number(v || 0));
			}
		}
		return max;
	});

	const lineNodes = $derived.by(() => generatedReport?.development_lines.lines || []);
	const activeLineId = $derived.by(() => {
		if (activePlan?.line_id) return activePlan.line_id;
		return focusLineId || lineNodes[0]?.line_id || "";
	});

	$effect(() => {
		const plans = plansByTarget;
		if (!plans.length) return;
		if (!plans.some((p) => p.job_id === activeJobId)) {
			activeJobId = plans[0]?.job_id ?? "";
		}
		const plan = plans.find((p) => p.job_id === activeJobId) ?? plans[0];
		if (plan?.line_id && focusLineId !== plan.line_id) {
			focusLineId = plan.line_id;
		}
	});

	function selectActiveJob(jobId: string): void {
		activeJobId = jobId;
		const plan = plansByTarget.find((p) => p.job_id === jobId);
		if (plan?.line_id) {
			focusLineId = plan.line_id;
		}
		selectedTimelineReviewId = null;
		selectedCanvasMonth = null;
		const adjs = (generatedReport?.development_lines?.adjustments || []).filter(
			(a) => a.line_id === (plan?.line_id || focusLineId),
		);
		selectedAdjustmentId = adjs[0]?.id || "";
		if (adjs.length) {
			selectCanvasMonth(adjustmentBucketMonth(adjs[0]));
		} else {
			selectedCanvasMonth = 0;
		}
	}

	type GapInsightRow = {
		key: string;
		label: string;
		student: number;
		jobReq: number;
		rawDelta: number;
		gapJob: number;
		status: "deficit" | "met" | "lead";
	};

	function gapRowsFromPreview(
		mp: ReportTargetInsight["match_preview"] | undefined,
		legacy?: Record<string, number>,
	): GapInsightRow[] {
		if (!mp && legacy) {
			return Object.entries(legacy)
				.sort((a, b) => Number(b[1] || 0) - Number(a[1] || 0))
				.slice(0, 8)
				.map(([k, v]) => ({
					key: k,
					label: DIMENSION_LABELS[k] || k,
					student: 0,
					jobReq: 0,
					rawDelta: Number(v || 0),
					gapJob: Number(v || 0),
					status: Number(v || 0) > 0 ? "deficit" : "met",
				}));
		}
		if (!mp) return [];
		const student = mp.student_scores || {};
		const jobReq = mp.job_requirement_scores || {};
		const rawDelta = mp.dimension_raw_delta || {};
		const gapsJob = mp.dimension_gaps || {};
		const surplus = mp.dimension_surplus || {};
		const keys = new Set([...Object.keys(gapsJob), ...Object.keys(student)]);
		const rows: GapInsightRow[] = [];
		for (const k of keys) {
			const gapJob = Number(gapsJob[k] || 0);
			if (gapJob <= 0 && Number(surplus[k] || 0) <= 0) continue;
			let status: GapInsightRow["status"] = "met";
			if (gapJob > 0) status = "deficit";
			else if (Number(surplus[k] || 0) > 0) status = "lead";
			rows.push({
				key: k,
				label: DIMENSION_LABELS[k] || k,
				student: Number(student[k] ?? 0),
				jobReq: Number(jobReq[k] ?? 0),
				rawDelta: Number(rawDelta[k] ?? jobReq[k] - student[k]),
				gapJob,
				status,
			});
		}
		return rows.sort((a, b) => b.gapJob - a.gapJob).slice(0, 8);
	}

	const activeGapRows = $derived.by(() =>
		gapRowsFromPreview(
			activeTargetRow?.match_preview,
			activePlan?.dimension_gaps,
		),
	);

	const activeGapMeta = $derived.by(() => {
		const mp = activeTargetRow?.match_preview;
		if (!mp) return null;
		return {
			margin: mp.soft_margin ?? 6,
			goal: mp.match_goal ?? generatedReport?.match_goal ?? reportMatchGoal,
			note: mp.reference_note ?? "",
			wJob: mp.weighted_gap,
		};
	});

	function gapBarWidth(points: number): string {
		return `${Math.min(100, (Math.max(0, points) / GAP_BAR_SCALE) * 100)}%`;
	}

	function gapStatusLabel(status: GapInsightRow["status"]): string {
		if (status === "deficit") return "需补足";
		if (status === "lead") return "已领先";
		return "已达标";
	}

	function chartAxis(): {
		xMin: number;
		xMax: number;
		yMin: number;
		yMax: number;
		xLabel: string;
		yLabel: string;
	} {
		const ax = generatedReport?.development_lines?.axis;
		return {
			xMin: Number(ax?.x_min ?? 0),
			xMax: Number(ax?.x_max ?? 12),
			yMin: Number(ax?.y_min ?? 0),
			yMax: Number(ax?.y_max ?? 100),
			xLabel: ax?.x_label ?? "时间（月）",
			yLabel: ax?.y_label ?? "复盘进步度",
		};
	}

	function chartLayoutFor(chart: typeof CHART_INLINE) {
		const ax = chartAxis();
		const pw = chart.w - chart.l - chart.r;
		const ph = chart.h - chart.t - chart.b;
		return { ax, pw, ph, chart };
	}

	function scalePoint(
		month: number,
		progress: number,
		chart: typeof CHART_INLINE = CHART_INLINE,
	): { x: number; y: number } {
		const ax = chartAxis();
		const pw = chart.w - chart.l - chart.r;
		const ph = chart.h - chart.t - chart.b;
		const xr = ax.xMax - ax.xMin || 1;
		const yr = ax.yMax - ax.yMin || 1;
		const monthInt = Math.max(ax.xMin, Math.min(ax.xMax, Math.round(Number(month))));
		const x = chart.l + ((monthInt - ax.xMin) / xr) * pw;
		const y = chart.t + ph - ((Number(progress) - ax.yMin) / yr) * ph;
		return { x, y };
	}

	function xAxisTicks(dense: boolean): number[] {
		if (dense) return Array.from({ length: 13 }, (_, i) => i);
		return [0, 3, 6, 9, 12];
	}

	function stageToMonth(stage: string): number {
		const m: Record<string, number> = {
			current: 0,
			short_term: 2.5,
			mid_term: 7,
			target: 12,
		};
		return m[stage] ?? 6;
	}

	function fallbackTimeline(
		_line: (typeof lineNodes)[number],
	): Array<{ month: number; progress: number; label?: string; kind: TimelinePoint["kind"] }> {
		return [{ month: 0, progress: 0, label: "起点", kind: "origin" as const }];
	}

	const activeTimeline = $derived.by(() => {
		const line = lineNodes.find((x) => x.line_id === activeLineId);
		if (!line) return [] as TimelinePoint[];
		const tl = line.timeline;
		if (tl && tl.length > 0) return tl;
		return fallbackTimeline(line) as TimelinePoint[];
	});

	const activeLineIndex = $derived.by(() => {
		const i = lineNodes.findIndex((x) => x.line_id === activeLineId);
		return i < 0 ? 0 : i;
	});

	const selectedTimelinePoint = $derived.by((): TimelinePoint | null => {
		const rid = selectedTimelineReviewId;
		if (rid == null) return null;
		return activeTimeline.find((x) => x.kind === "review" && x.review_id === rid) || null;
	});

	const adjustmentNodes = $derived.by(
		() =>
			generatedReport?.development_lines.adjustments?.filter(
				(x) => x && x.id && x.line_id && x.stage && x.label,
			) || [],
	);

	const adjustmentsForActiveLine = $derived.by(() =>
		adjustmentNodes
			.filter((x) => x.line_id === activeLineId)
			.slice()
			.sort(
				(a, b) =>
					(Number(a.month) || 0) - (Number(b.month) || 0) ||
					(Number(a.priority) || 0) - (Number(b.priority) || 0),
			),
	);

	type CanvasMonthBundle = {
		monthKey: number;
		month: number;
		progress: number;
		label: string;
		review?: TimelinePoint;
		adjustments: (typeof adjustmentNodes)[number][];
	};

	function adjustmentBucketMonth(adj: (typeof adjustmentNodes)[number]): number {
		const anchor = adj.anchor_review_month;
		if (anchor != null && anchor !== undefined && !Number.isNaN(Number(anchor))) {
			return Math.max(0, Math.round(Number(anchor)));
		}
		return Math.max(0, Math.round(Number(adj.month) || 0));
	}

	const monthlyCanvasPoints = $derived.by((): CanvasMonthBundle[] => {
		const buckets = new Map<number, CanvasMonthBundle>();

		const touch = (key: number, progress: number, label?: string) => {
			const existing = buckets.get(key);
			if (!existing) {
				buckets.set(key, {
					monthKey: key,
					month: key,
					progress,
					label: label || (key === 0 ? "起点" : `第${key}月`),
					adjustments: [],
				});
				return buckets.get(key)!;
			}
			if (progress > existing.progress) {
				existing.progress = progress;
			}
			if (label) existing.label = label;
			return existing;
		};

		for (const t of activeTimeline) {
			if (t.kind === "review" && t.review_id != null) {
				const key = Math.round(Number(t.month) || 0);
				const b = touch(key, Number(t.progress) || 0, t.label || `第${key}月`);
				b.review = t;
			}
		}

		for (const adj of adjustmentsForActiveLine) {
			const key = adjustmentBucketMonth(adj);
			const prog =
				typeof adj.progress === "number"
					? adj.progress
					: key === 0
						? 0
						: Math.min(100, key * 10);
			const b = touch(key, prog);
			b.adjustments.push(adj);
			if (!b.review && key === 0) {
				b.progress = 0;
				b.label = "起点";
			}
		}

		if (buckets.size === 0) {
			touch(0, 0, "起点");
		}

		return [...buckets.values()].sort((a, b) => a.monthKey - b.monthKey);
	});

	function canvasPolylineString(chart: typeof CHART_INLINE = CHART_INLINE): string {
		return monthlyCanvasPoints
			.map((b) => {
				const p = scalePoint(b.monthKey, b.progress, chart);
				return `${p.x},${p.y}`;
			})
			.join(" ");
	}

	const selectedCanvasBundle = $derived.by(() => {
		if (selectedCanvasMonth == null) return null;
		return monthlyCanvasPoints.find((b) => b.monthKey === selectedCanvasMonth) || null;
	});

	const selectedCanvasDetail = $derived.by(() => {
		const bundle = selectedCanvasBundle;
		if (!bundle) return null;
		const line = lineNodes.find((x) => x.line_id === activeLineId);
		const latestReview = generatedReport?.evaluation?.latest_review;
		const evalRows = latestReview?.evaluation?.rows || [];
		const failedCodes = new Set(latestReview?.evaluation?.failed_codes || []);
		const relatedRows = evalRows.filter((x) => failedCodes.has(x.code));
		const primaryAdj = bundle.adjustments[0];
		const allHints = bundle.adjustments.flatMap((a) => a.execution_hints || []);
		const planItems = bundle.adjustments.flatMap(
			(a) => a.plan_items || (a.plan_item ? [a.plan_item] : []),
		);
		return {
			bundle,
			line_name: line?.line_name || activeLineId,
			primaryAdj,
			allHints: [...new Set(allHints)],
			planItems,
			failed_rows: primaryAdj?.kind === "initial_plan" ? [] : relatedRows,
			review_created_at: latestReview?.created_at || "",
		};
	});

	function selectCanvasMonth(monthKey: number): void {
		selectedCanvasMonth = monthKey;
		const bundle = monthlyCanvasPoints.find((b) => b.monthKey === monthKey);
		selectedTimelineReviewId = bundle?.review?.review_id ?? null;
		selectedAdjustmentId = bundle?.adjustments[0]?.id ?? "";
	}

	const selectedAdjustment = $derived.by(() => {
		if (!selectedAdjustmentId) return null;
		return adjustmentNodes.find((x) => x.id === selectedAdjustmentId) || null;
	});

	const selectedAdjustmentDetail = $derived.by(() => {
		const adj = selectedAdjustment;
		if (!adj) return null;
		const line = lineNodes.find((x) => x.line_id === adj.line_id);
		const latestReview = generatedReport?.evaluation?.latest_review;
		const evalRows = latestReview?.evaluation?.rows || [];
		const failedCodes = new Set(latestReview?.evaluation?.failed_codes || []);
		const relatedRows = evalRows.filter((x) => failedCodes.has(x.code));
		return {
			...adj,
			line_name: line?.line_name || adj.line_id,
			failed_rows: relatedRows,
			review_created_at: latestReview?.created_at || "",
		};
	});

	const narrativeBlocks = $derived.by(() => {
		const text = String(generatedReport?.narrative?.text || "").trim();
		if (!text) return [];
		return text
			.split(/\n+/)
			.map((x) => x.trim())
			.filter((x) => x.length > 0);
	});

	const shortPlanItems = $derived.by(() => (generatedReport?.growth_plan.short_term || []).slice(0, 6));
	const midPlanItems = $derived.by(() => (generatedReport?.growth_plan.mid_term || []).slice(0, 6));

	const linePlanSummary = $derived.by(() => {
		const lines = generatedReport?.development_lines?.lines || [];
		if (!lines.length) return { shared: [], split: [] as Array<{ line_name: string; overlay_group: string }> };
		const grouped: Record<string, Array<{ line_name: string; overlay_group: string }>> = {};
		for (const l of lines) {
			const g = String(l.overlay_group || "default");
			grouped[g] = grouped[g] || [];
			grouped[g].push({ line_name: l.line_name, overlay_group: g });
		}
		const shared: Array<{ group: string; lines: string[] }> = [];
		const split: Array<{ line_name: string; overlay_group: string }> = [];
		for (const [group, arr] of Object.entries(grouped)) {
			if (arr.length >= 2) {
				shared.push({ group, lines: arr.map((x) => x.line_name) });
			} else {
				split.push(arr[0]);
			}
		}
		return { shared, split };
	});

	const reviewTrend = $derived.by(() => {
		const ordered = [...reviewHistory].reverse();
		const points = ordered.map((item, idx) => {
			const passRate = Number(item.metrics?.evaluation?.pass_rate || 0);
			return {
				x: 24 + idx * 52,
				y: 84 - Math.max(0, Math.min(1, passRate)) * 64,
				passRate,
				reviewId: item.review_id,
			};
		});
		return points;
	});

	const trackOverview = $derived.by(() => {
		if (!trackRows.length) return null;
		const profiles = trackRows.map((r) => resolveTrackProfile(r)).filter(Boolean) as ReportTrackProfile[];
		if (!profiles.length) return null;
		const avg = (key: keyof ReportTrackProfile) =>
			profiles.reduce((acc, p) => acc + Number(p[key] || 0), 0) / profiles.length;
		return {
			hiringAvg: Math.round(avg("hiring_visibility_0_100") * 10) / 10,
			pathAvg: Math.round(avg("path_breadth_0_100") * 10) / 10,
			resAvg: Math.round(avg("resource_density_0_100") * 10) / 10,
		};
	});

function readableCycleText(cycle: string): string {
	const c = String(cycle || "").toLowerCase();
	if (c === "biweekly") return "每两周看一次";
	if (c === "monthly") return "每月看一次";
	return "定期复盘";
}

function readableTargetText(target: string): string {
	const t = String(target || "").trim();
	if (!t) return "按计划推进";
	return t
		.replaceAll(">=", "不少于 ")
		.replaceAll("<=", "不高于 ")
		.replaceAll(">", "高于 ")
		.replaceAll("<", "低于 ");
}

function metricDisplayLabel(metric: { code?: string; label?: string }): string {
	const code = String(metric?.code || "");
	if (METRIC_FRIENDLY_LABELS[code]) return METRIC_FRIENDLY_LABELS[code];
	return String(metric?.label || code || "复盘项");
}

function metricDisplayDescription(metric: { code?: string; description?: string }): string {
	const code = String(metric?.code || "");
	if (METRIC_FRIENDLY_DESCRIPTIONS[code]) return METRIC_FRIENDLY_DESCRIPTIONS[code];
	const raw = String(metric?.description || "").trim();
	if (!raw) return "";
	if (/加权|基线|容差|JD要求|dim_|Neo4j|分位|系统自动/i.test(raw)) {
		return `${metricDisplayLabel(metric)}：结合上方成长计划与每月复盘，看是否在变好。`;
	}
	return raw;
}

	function snapshotWorkspaceCache(infoMessage = info): ReportWorkspaceCacheV1 {
		return {
			v: 1,
			reportId: generatedReportId,
			reportSnapshot: generatedReport,
			infoMessage: infoMessage || "",
			selectedTargets: [...selectedTargets],
			selectedResumeId,
			reportMatchGoal,
			activeJobId,
			activePhase,
			focusLineId,
			selectedAdjustmentId,
			selectedCanvasMonth,
			selectedTimelineReviewId,
			configRailCollapsed,
			nextMonthSectionOpen,
			nextMonthItemOpen: { ...nextMonthItemOpen },
			nextMonthActionDone: { ...nextMonthActionDone },
		};
	}

	function persistReportWorkspaceState(infoMessage?: string): void {
		if (!generatedReportId && selectedTargets.length === 0) return;
		persistReportWorkspace(snapshotWorkspaceCache(infoMessage ?? info));
	}

	function applyReportWithActionProgress(
		remote: CareerReportPayload,
		...localSources: Array<CareerReportPayload | null | undefined>
	): CareerReportPayload {
		const merged = mergeReportActionProgress(remote, [generatedReport, ...localSources], nextMonthActionDone);
		nextMonthActionDone = mergeActionDoneMaps(nextMonthActionDone, collectActionDoneMap(merged));
		return merged;
	}

	async function refreshWorkspaceReportQuiet(reportId: number): Promise<void> {
		try {
			const latest = await fetchCareerReportDetail(reportId);
			if (latest?.report) {
				generatedReport = applyReportWithActionProgress(latest.report, workspaceBoot?.reportSnapshot ?? null);
				persistReportWorkspaceState();
			}
			await loadReviewsForReport(reportId);
		} catch {
			/* 保留本地快照 */
		}
	}

	async function restoreReportFromServer(cached: ReportWorkspaceCacheV1): Promise<boolean> {
		if (!cached.reportId) return false;
		try {
			const latest = await fetchCareerReportDetail(cached.reportId);
			if (!latest?.report) return false;
			generatedReportId = cached.reportId;
			generatedReport = applyReportWithActionProgress(latest.report, cached.reportSnapshot ?? null);
			if (generatedReport.match_goal === "stretch" || generatedReport.match_goal === "fit") {
				reportMatchGoal = generatedReport.match_goal;
			}
			activeJobId = bootActiveJobId({ ...cached, reportSnapshot: latest.report });
			focusLineId = bootFocusLineId({ ...cached, reportSnapshot: latest.report });
			activePhase =
				cached.activePhase === "mid" || cached.activePhase === "late" ? cached.activePhase : "early";
			const adjIds = new Set((generatedReport.development_lines?.adjustments || []).map((a) => a.id));
			selectedAdjustmentId =
				cached.selectedAdjustmentId && adjIds.has(cached.selectedAdjustmentId)
					? cached.selectedAdjustmentId
					: generatedReport.development_lines?.adjustments?.[0]?.id || "";
			selectedCanvasMonth =
				typeof cached.selectedCanvasMonth === "number" ? cached.selectedCanvasMonth : null;
			selectedTimelineReviewId =
				typeof cached.selectedTimelineReviewId === "number" ? cached.selectedTimelineReviewId : null;
			await loadReviewsForReport(cached.reportId);
			info = cached.infoMessage || `已恢复报告 #${cached.reportId} 的工作区。`;
			persistReportWorkspaceState(info);
			return true;
		} catch {
			return false;
		}
	}

	async function syncWorkspaceAfterMount(): Promise<void> {
		const cached = loadReportWorkspace();
		if (cached?.selectedResumeId !== "" && resumes.some((r) => r.id === cached.selectedResumeId)) {
			selectedResumeId = cached.selectedResumeId;
		}

		if (!cached?.reportId) return;

		if (generatedReport) {
			void refreshWorkspaceReportQuiet(cached.reportId);
			return;
		}

		selectedTargets = (cached.selectedTargets || []).slice(0, 5);
		reportMatchGoal = cached.reportMatchGoal === "stretch" ? "stretch" : "fit";
		configRailCollapsed = !!cached.configRailCollapsed;
		nextMonthSectionOpen = cached.nextMonthSectionOpen ?? true;
		nextMonthItemOpen = { ...(cached.nextMonthItemOpen || {}) };
		nextMonthActionDone = { ...(cached.nextMonthActionDone || {}) };
		await restoreReportFromServer(cached);
	}

	onMount(async () => {
		resumes = await fetchMyResumes().catch(() => []);
		if (resumes.length && selectedResumeId === "") {
			selectedResumeId = resumes[0].id;
		}
		await syncWorkspaceAfterMount();
	});

	async function loadReviewsForReport(reportId: number): Promise<void> {
		reviewHistory = await fetchReportReviews(reportId).catch(() => []);
	}

	function upsertTarget(target: ReportTargetItem): void {
		const jobId = String(target.job_id || "").trim();
		if (!jobId) return;
		if (selectedTargets.some((x) => x.job_id === jobId)) return;
		if (selectedTargets.length >= 5) {
			error = "最多选择 5 个目标职业。";
			return;
		}
		error = "";
		selectedTargets = [...selectedTargets, target];
		persistReportWorkspaceState();
	}

	function removeTarget(jobId: string): void {
		selectedTargets = selectedTargets.filter((x) => x.job_id !== jobId);
		persistReportWorkspaceState();
	}

	function barWidth(value: number, max = 100): string {
		const pct = Math.max(0, Math.min(100, (value / Math.max(max, 1)) * 100));
		return `${pct}%`;
	}

	function heatColor(value: number): string {
		const alpha = Math.max(0.08, Math.min(0.88, Number(value) / Math.max(maxGapValue, 1)));
		return `background-color: rgba(59,130,246,${alpha.toFixed(3)});`;
	}

	function selectAdjustment(adjustId: string): void {
		selectedAdjustmentId = adjustId;
		const adj = adjustmentNodes.find((x) => x.id === adjustId);
		if (adj?.line_id) {
			focusLineId = adj.line_id;
		}
		if (adj) {
			selectCanvasMonth(adjustmentBucketMonth(adj));
		}
	}

	function selectTimelineReview(rid: number | undefined): void {
		if (rid == null || Number.isNaN(Number(rid))) return;
		const n = Number(rid);
		const pt = activeTimeline.find((x) => x.kind === "review" && x.review_id === n);
		if (pt) {
			selectCanvasMonth(Math.round(Number(pt.month) || 0));
			selectedTimelineReviewId = n;
		}
	}

	function focusMetric(code: string): void {
		const metricCode = String(code || "").trim();
		if (!metricCode) return;
		highlightedMetricCode = metricCode;
		const node = document.querySelector(
			`[data-metric-code="${metricCode}"]`,
		) as HTMLElement | null;
		if (node) {
			node.scrollIntoView({ behavior: "smooth", block: "nearest" });
		}
	}

	function matchGoalRemark(goal: string): string {
		return goal === "stretch" ? "冲刺目标" : "稳妥目标";
	}

	function gapTableIntro(meta: NonNullable<typeof activeGapMeta>): string {
		const w = meta.wJob;
		const wText =
			w != null && Number.isFinite(Number(w))
				? `综合缺口约 ${Number(w).toFixed(1)} 分，数值越小表示离「能稳投」越近。`
				: "";
		const goalText =
			meta.goal === "stretch"
				? "按「冲刺目标」评估：部分维度略低于要求时，仍可能值得尝试。"
				: "按「稳妥目标」评估：更贴近常规投递时常见的门槛。";
		return [wText, goalText].filter(Boolean).join(" ");
	}

	async function handleMatchImportSelect(detail: MatchHistoryDetail): Promise<void> {
		error = "";
		info = "";
		loadingImport = true;
		try {
			const data = await importTargetsFromMatch({
				run_id: detail.run_id,
				limit: 5,
			});
			selectedTargets = (data?.targets || []).slice(0, 5);
			reportMatchGoal = data?.match_goal === "stretch" ? "stretch" : "fit";
			const rid = data?.resume_id;
			if (rid && resumes.some((x) => x.id === rid)) {
				selectedResumeId = rid;
			} else if (rid) {
				error = "匹配记录关联的画像已不可用，请改用手动导入选择其他画像。";
			}
			const ts = detail.created_at?.replace("T", " ").slice(0, 19) || "";
			const student = detail.student?.display_name || "该画像";
			if (!error) {
				info = `已从 ${ts} 的匹配记录导入 ${selectedTargets.length} 个目标（${student} · ${matchGoalRemark(data?.match_goal || "fit")}）。`;
			}
		} catch (e) {
			error = e instanceof Error ? e.message : "导入匹配数据失败";
		} finally {
			loadingImport = false;
			persistReportWorkspaceState();
		}
	}

	async function generate(): Promise<void> {
		if (selectedResumeId === "") {
			error = "请先选择画像记录。";
			return;
		}
		if (!selectedTargets.length) {
			error = "请先添加至少 1 个目标职业。";
			return;
		}
		error = "";
		info = "";
		generatedReportId = null;
		generatedReport = null;
		loadingGenerate = true;
		generateProgress = "正在生成报告骨架（画像、缺口、计划、规则推荐）…";
		try {
			const data = await generateCareerReport({
				resume_id: Number(selectedResumeId),
				target_job_ids: selectedTargets.map((x) => x.job_id),
				primary_job_id: selectedTargets[0].job_id,
				match_goal: reportMatchGoal,
				skip_llm_enrich: true,
			});
			generatedReportId = data?.report_id || null;
			generatedReport = data?.report || null;
			if (generatedReport?.match_goal === "stretch" || generatedReport?.match_goal === "fit") {
				reportMatchGoal = generatedReport.match_goal;
			}
			selectedTimelineReviewId = null;
			activeJobId = generatedReport?.targets?.[0]?.id || "";
			activePhase = "early";
			focusLineId =
				generatedReport?.plans_by_target?.[0]?.line_id ||
				generatedReport?.development_lines?.lines?.[0]?.line_id ||
				"";
			configRailCollapsed = true;
			const firstLineId = focusLineId;
			const firstAdjG = (generatedReport?.development_lines?.adjustments || []).find(
				(a) => a.line_id === firstLineId,
			);
			selectedAdjustmentId = firstAdjG?.id || generatedReport?.development_lines?.adjustments?.[0]?.id || "";
			selectedCanvasMonth = firstAdjG ? adjustmentBucketMonth(firstAdjG) : 0;
			if (generatedReportId) {
				await loadReviewsForReport(generatedReportId);
			}
			const coreMs = data?.generation_timing_ms?.total;
			info = generatedReportId
				? `报告骨架已生成${coreMs != null ? `（${coreMs}ms）` : ""}，正在后台 AI 增强…`
				: "报告骨架已生成。";

			if (generatedReportId && generatedReport?.llm_enrich_pending !== false) {
				loadingEnrich = true;
				generateProgress = "正在 AI 精选图谱资源并生成叙事文案（约 10～30 秒）…";
				try {
					const enriched = await enrichCareerReport(generatedReportId);
					generatedReport = enriched.report || generatedReport;
					const enrichMs = enriched.enrichment_timing_ms?.total;
					info = `报告已就绪${enrichMs != null ? `（AI 增强 ${enrichMs}ms）` : ""}。`;
				} catch (enrichErr) {
					error =
						enrichErr instanceof Error
							? `骨架已生成，但 AI 增强失败：${enrichErr.message}`
							: "骨架已生成，但 AI 增强失败";
				} finally {
					loadingEnrich = false;
					generateProgress = "";
				}
			}
		} catch (e) {
			error = e instanceof Error ? e.message : "生成报告失败";
			generateProgress = "";
		} finally {
			loadingGenerate = false;
			persistReportWorkspaceState();
		}
	}

	function applyHistoryReportDetail(data: NonNullable<CareerReportGenerateResponse["data"]>): void {
		error = "";
		info = "";
		generatedReportId = data?.report_id || null;
		if (data?.report) {
			generatedReport = applyReportWithActionProgress(data.report);
		} else {
			generatedReport = null;
		}
		selectedTimelineReviewId = null;
		activeJobId = generatedReport?.targets?.[0]?.id || "";
		activePhase = "early";
		focusLineId =
			generatedReport?.plans_by_target?.[0]?.line_id ||
			generatedReport?.development_lines?.lines?.[0]?.line_id ||
			"";
		configRailCollapsed = true;
		const firstAdjH = generatedReport?.development_lines?.adjustments?.find(
			(a) => a.line_id === focusLineId,
		);
		selectedAdjustmentId = firstAdjH?.id || generatedReport?.development_lines?.adjustments?.[0]?.id || "";
		selectedCanvasMonth = firstAdjH ? adjustmentBucketMonth(firstAdjH) : 0;
		if (generatedReportId) {
			void loadReviewsForReport(generatedReportId);
		}
		const title = data?.title?.trim();
		info = title ? `已加载历史报告「${title}」` : "历史报告加载成功。";
		if (generatedReport) {
			nextMonthActionDone = mergeActionDoneMaps(nextMonthActionDone, collectActionDoneMap(generatedReport));
		}
		persistReportWorkspaceState(info);
	}

	async function submitReview(): Promise<void> {
		if (!generatedReportId) {
			reviewError = "请先生成或加载报告。";
			return;
		}
		if (!reviewText.trim()) {
			reviewError = "请先输入本周期变化与复盘情况。";
			return;
		}
		reviewError = "";
		reviewInfo = "";
		submittingReview = true;
		try {
			const res = await submitReportReviewCycle({
				report_id: generatedReportId,
				review_text: reviewText.trim(),
			});
			const mode = res.adjustment?.replan_mode || res.adjustment?.auto_adjustment?.replan_mode;
			if (res.adjustment?.auto_adjustment?.triggered) {
				if (mode === "continue") {
					reviewInfo = "评估已提交。本月达标，已按分岗阶段计划延续下月任务。";
				} else if (mode === "strong") {
					reviewInfo = "评估已提交。连续未达标，已加强下月任务（见本岗「下月执行」与曲线菱形）。";
				} else {
					reviewInfo = "评估已提交。已根据本月表现更新下月任务。";
				}
			} else {
				reviewInfo = "评估已提交。";
			}
			if (res.llm_extract?.source === "deepseek") {
				reviewInfo += " DeepSeek 已完成复盘量化。";
			}
			const autoGap = (res.llm_extract as { auto_gap_metrics?: Record<string, number> } | undefined)
				?.auto_gap_metrics;
			if (autoGap?.dim_gap_reduction != null) {
				reviewInfo += ` 相较生成报告时，能力短板已缩小约 ${autoGap.dim_gap_reduction}%。`;
			}
			if (autoGap?.match_score_change != null) {
				reviewInfo += ` 主目标匹配分变化 ${autoGap.match_score_change} 分。`;
			}
			if (generatedReportId) {
				await loadReviewsForReport(generatedReportId);
				const latest = await fetchCareerReportDetail(generatedReportId);
				if (latest?.report) {
					generatedReport = applyReportWithActionProgress(latest.report);
				}
				const lid = focusLineId || generatedReport?.development_lines?.lines?.[0]?.line_id || "";
				const adjsForLine = (generatedReport?.development_lines?.adjustments || []).filter((a) => a.line_id === lid);
				const fa = adjsForLine[adjsForLine.length - 1];
				selectedAdjustmentId = fa?.id || "";
				if (typeof res.review_id === "number") {
					selectTimelineReview(res.review_id);
				} else if (fa) {
					selectCanvasMonth(adjustmentBucketMonth(fa));
				}
			}
			reviewText = "";
			persistReportWorkspaceState(reviewInfo || info);
		} catch (e) {
			reviewError = e instanceof Error ? e.message : "评估提交失败";
		} finally {
			submittingReview = false;
		}
	}

	async function exportPdf(): Promise<void> {
		if (!generatedReportId) {
			error = "请先生成或加载报告。";
			return;
		}
		error = "";
		info = "";
		exportingPdf = true;
		try {
			await exportCareerReportPdf(generatedReportId);
			info = `报告 #${generatedReportId} PDF 导出成功。`;
		} catch (e) {
			error = e instanceof Error ? e.message : "导出 PDF 失败";
		} finally {
			exportingPdf = false;
		}
	}

	function applyReviewTemplate(): void {
		const t = REVIEW_TEMPLATE.trim();
		if (!reviewText.trim()) {
			reviewText = t;
			return;
		}
		reviewText = `${reviewText.trim()}\n\n────────\n\n${t}`;
	}
</script>

{#snippet lineCanvasSvg(chart: typeof CHART_INLINE, denseX: boolean)}
	{@const layout = chartLayoutFor(chart)}
	<svg
		viewBox="0 0 {chart.w} {chart.h}"
		class="line-canvas"
		class:line-canvas--dense={denseX}
		aria-label="进步度时间曲线"
	>
		{#each [3, 6, 9] as gx}
			{@const gx1 = scalePoint(gx, layout.ax.yMin, chart).x}
			<line x1={gx1} y1={chart.t} x2={gx1} y2={chart.t + layout.ph} class="grid-line" />
		{/each}
		{#each [25, 50, 75] as gy}
			{@const gy1 = chart.t + layout.ph - (gy / 100) * layout.ph}
			<line x1={chart.l} y1={gy1} x2={chart.l + layout.pw} y2={gy1} class="grid-line" />
		{/each}
		<line
			x1={chart.l}
			y1={chart.t + layout.ph}
			x2={chart.l + layout.pw}
			y2={chart.t + layout.ph}
			class="axis-main"
		/>
		<line x1={chart.l} y1={chart.t} x2={chart.l} y2={chart.t + layout.ph} class="axis-main" />
		{#each [0, 25, 50, 75, 100] as tick}
			{@const yy = chart.t + layout.ph - (tick / 100) * layout.ph}
			<line x1={chart.l - 5} y1={yy} x2={chart.l} y2={yy} class="axis-tick" />
			<text x={chart.l - 8} y={yy + 3} text-anchor="end" class="axis-num">{tick}</text>
		{/each}
		{#each xAxisTicks(denseX) as xm}
			{@const xx = scalePoint(xm, 0, chart).x}
			<line
				x1={xx}
				y1={chart.t + layout.ph}
				x2={xx}
				y2={chart.t + layout.ph + 6}
				class="axis-tick"
			/>
			<text x={xx} y={chart.t + layout.ph + 18} text-anchor="middle" class="axis-num">{xm}</text>
		{/each}
		<text x={chart.l + layout.pw / 2} y={chart.h - 4} text-anchor="middle" class="axis-title">
			{layout.ax.xLabel}
		</text>
		<text
			x="16"
			y={chart.t + layout.ph / 2}
			text-anchor="middle"
			class="axis-title"
			transform={`rotate(-90,16,${chart.t + layout.ph / 2})`}
		>
			{layout.ax.yLabel}
		</text>

		{#if monthlyCanvasPoints.length >= 2}
			<polyline
				points={canvasPolylineString(chart)}
				fill="none"
				stroke={LINE_COLORS[activeLineIndex % LINE_COLORS.length]}
				stroke-width="3"
				stroke-linejoin="round"
				stroke-linecap="round"
			/>
		{/if}
		{#each monthlyCanvasPoints as pt (`cm-${pt.monthKey}`)}
			{@const p = scalePoint(pt.monthKey, pt.progress, chart)}
			{@const hasReview = !!pt.review}
			{@const isSelected = selectedCanvasMonth === pt.monthKey}
			<g
				class="hit-month-point"
				class:selected={isSelected}
				role="button"
				tabindex="0"
				aria-label={`查看第${pt.monthKey}月详情`}
				onclick={() => selectCanvasMonth(pt.monthKey)}
				onkeydown={(e) => {
					if (e.key === "Enter" || e.key === " ") {
						e.preventDefault();
						selectCanvasMonth(pt.monthKey);
					}
				}}
			>
				<circle cx={p.x} cy={p.y} r="12" fill="transparent" class="hit-pad" />
				<circle
					cx={p.x}
					cy={p.y}
					r={hasReview ? "5.4" : "5"}
					fill={hasReview ? LINE_COLORS[activeLineIndex % LINE_COLORS.length] : "#f59e0b"}
					stroke={isSelected ? "#111827" : "#ffffff"}
					stroke-width={isSelected ? "2.2" : "1.4"}
				/>
				{#if pt.label}
					<text x={p.x} y={p.y - 11} text-anchor="middle" class="point-label">{pt.label}</text>
				{/if}
			</g>
		{/each}
	</svg>
{/snippet}

{#snippet canvasMonthDetail(embedded)}
	{#if selectedCanvasDetail}
		<div class="canvas-side-cards" class:compact={embedded} class:full-width={embedded}>
			<article class="insight-mini-card insight-mini-card--adjust">
				<h4 class="insight-mini-card-title">
					{#if selectedCanvasDetail.bundle.monthKey === 0}
						第 0 月 · 起步安排
					{:else if selectedCanvasDetail.bundle.review}
						第 {selectedCanvasDetail.bundle.monthKey} 月 · 复盘与下步
					{:else}
						第 {selectedCanvasDetail.bundle.monthKey} 月 · 执行安排
					{/if}
				</h4>
				<div class="adjustment-detail">
					{#if selectedCanvasDetail.bundle.review?.detail}
						{@const rd = selectedCanvasDetail.bundle.review.detail}
						<p class="subhead">本月复盘</p>
						<p class="detail-pass">
							通过率 {Math.round((rd.pass_rate ?? 0) * 100)}% · {rd.all_passed ? "全部达标" : "存在未达标项"}
						</p>
						{#if rd.llm_summary}
							<p class="detail-block"><span class="sub">DeepSeek 小结</span>{rd.llm_summary}</p>
						{/if}
						{#if rd.review_text}
							<p class="detail-block">
								<span class="sub">复盘原文</span><span class="pre">{rd.review_text}</span>
							</p>
						{/if}
						{#if rd.submitted}
							<p class="detail-block">
								<span class="sub">量化结果</span>
								短板缩小 {Number(rd.submitted.dim_gap_reduction ?? 0).toFixed(1)}% · 计划完成
								{Number(rd.submitted.project_completion ?? 0).toFixed(1)}% · 贴合度变化
								{Number(rd.submitted.match_score_change ?? 0).toFixed(1)} 分 · 成果
								{Math.round(Number(rd.submitted.delivery_output ?? 0))} 项
							</p>
						{/if}
					{/if}

					{#if selectedCanvasDetail.primaryAdj}
						<p class="subhead">{selectedCanvasDetail.bundle.review ? "下月任务" : "细化落地"}</p>
						<p class="title">
							{selectedCanvasDetail.primaryAdj.focus_label || "能力补齐"} · {selectedCanvasDetail.primaryAdj.label}
						</p>
						<p>所属发展线：{selectedCanvasDetail.line_name}</p>
						<p>
							目标执行<strong
								>第 {selectedCanvasDetail.primaryAdj.plan_month ??
									Math.max(1, selectedCanvasDetail.bundle.monthKey + 1)} 月</strong
							>
							{#if selectedCanvasDetail.primaryAdj.anchor_review_month != null}
								（复盘锚点：第 {Math.round(Number(selectedCanvasDetail.primaryAdj.anchor_review_month))} 月）
							{/if}
							· 阶段 {phaseLabelFromKey(selectedCanvasDetail.primaryAdj.phase_key) ||
								STAGE_LABELS[selectedCanvasDetail.primaryAdj.stage] ||
								selectedCanvasDetail.primaryAdj.stage}
						</p>
					{/if}

					{#if selectedCanvasDetail.planItems.length}
						<ul class="adjustment-hint-list plan-items-merge">
							{#each selectedCanvasDetail.planItems as pi, pii (`mpi-${pii}-${pi.focus_dimension}`)}
								<li>
									<strong>{pi.focus_label}</strong>：{sanitizePlanDisplayText(pi.milestone)}
									{#if pi.growth_rationale}
										<p class="growth-rationale">{sanitizePlanDisplayText(pi.growth_rationale)}</p>
									{/if}
									{#if pi.custom_actions?.length}
										<ul class="action-checklist">
											{#each pi.custom_actions as ca, cai (`ca-${pii}-${cai}`)}
												<li>
													<span class="action-kind">{actionKindLabel(ca.kind)}</span>
													{sanitizePlanDisplayText(ca.text)}
												</li>
											{/each}
										</ul>
									{/if}
									{#if pi.learning_path_refs?.length}
										{#each pi.learning_path_refs as ref (`lr-${pii}-${ref.id}`)}
											<div class="hint-ref">
												{#if ref.url}
													<a href={ref.url} target="_blank" rel="noopener noreferrer">{ref.label || ref.id}</a>
												{:else}
													{ref.label || ref.id}
												{/if}
											</div>
										{/each}
									{/if}
								</li>
							{/each}
						</ul>
					{:else if selectedCanvasDetail.allHints.length}
						<ul class="adjustment-hint-list">
							{#each selectedCanvasDetail.allHints as hint, hi (`h-${hi}`)}
								<li>{sanitizePlanDisplayText(hint)}</li>
							{/each}
						</ul>
					{/if}

					{#if selectedCanvasDetail.failed_rows?.length}
						<p class="subhead">关联未达标指标</p>
						<ul>
							{#each selectedCanvasDetail.failed_rows as r (r.code)}
								<li>
									<button type="button" class="metric-link" onclick={() => focusMetric(r.code)}>
										{r.label}：实际 {r.actual_value} / 目标 {r.target_raw}
									</button>
								</li>
							{/each}
						</ul>
					{/if}
					{#if selectedCanvasDetail.primaryAdj?.created_at}
						<p class="meta">更新时间：{selectedCanvasDetail.primaryAdj.created_at}</p>
					{/if}
				</div>
			</article>
		</div>
	{/if}
{/snippet}

{#snippet developmentCanvas(embedded)}
	{@const chart = embedded ? CHART_WORKBENCH : CHART_INLINE}
	<div class="line-canvas-wrap" class:embedded={embedded} class:workbench={embedded}>
		<button
			type="button"
			class="canvas-zoom-btn"
			aria-label="放大查看发展线画布"
			title="放大查看"
			onclick={() => (canvasZoomOpen = true)}
		>
			<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
				<circle cx="10" cy="10" r="6.5" fill="none" stroke="currentColor" stroke-width="1.8" />
				<line x1="15" y1="15" x2="21" y2="21" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
				<line x1="10" y1="7.5" x2="10" y2="12.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
				<line x1="7.5" y1="10" x2="12.5" y2="10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
			</svg>
		</button>
		{@render lineCanvasSvg(chart, false)}
	</div>

	{#if !embedded}
		{@render canvasMonthDetail(false)}
	{/if}
{/snippet}
{#snippet insightPanel()}
			{#if generatedReport}
				{#if usePerJobPlan && activeGapRows.length}
					<div class="mini-title">当前岗位能力缺口</div>
					{#if activeGapMeta}
						<p class="gap-legend">
							对照你选中的这一条岗位，看你的能力与招聘要求差在哪里。{gapTableIntro(activeGapMeta)}
						</p>
						<ul class="gap-legend-keys">
							<li><strong>你的水平</strong>：简历画像在该维度的得分</li>
							<li><strong>岗位期望</strong>：该岗位在此维度的要求得分</li>
							<li><strong>差距</strong>：比岗位期望低多少（正数表示尚未达到）</li>
							<li><strong>待提升</strong>：建议优先补强的程度，条越长越要紧</li>
						</ul>
					{/if}
					<div class="gap-table">
						<div class="gap-table-head" aria-hidden="true">
							<span class="col-dim">维度</span>
							<span class="col-num">你的水平</span>
							<span class="col-num">岗位期望</span>
							<span class="col-num">差距</span>
							<span class="col-gap">待提升</span>
						</div>
						{#each activeGapRows as g (g.key)}
							<div class="gap-table-row">
								<span class="col-dim">{g.label}</span>
								<span class="col-num">{g.student.toFixed(0)}</span>
								<span class="col-num">{g.jobReq.toFixed(0)}</span>
								<span
									class="col-num"
									title={g.rawDelta > 0 ? "比岗位期望低 " + g.rawDelta.toFixed(0) + " 分" : "已达到或超过岗位期望"}
								>{g.rawDelta > 0 ? `+${g.rawDelta.toFixed(0)}` : g.rawDelta.toFixed(0)}</span>
								<div
									class="col-gap gap-gap-cell"
									title={g.gapJob > 0 ? `该维度建议优先补强，约 ${g.gapJob} 分` : "该维度已达标或领先"}
								>
									<div class="bar-track">
										<div
											class="bar gap job"
											style={`width:${gapBarWidth(g.gapJob)}`}
										></div>
									</div>
									<span class="pts">{g.gapJob > 0 ? `${g.gapJob}分` : "—"}</span>
									<span class="status-tag status-{g.status}">{gapStatusLabel(g.status)}</span>
								</div>
							</div>
						{/each}
					</div>
				{/if}
				<div class="mini-title">赛道画像{usePerJobPlan ? "（当前岗）" : ""}</div>
				{#if trackOverview && !usePerJobPlan}
					<div class="track-overview">
						<p class="meta">
							平均招聘可见度 {trackOverview.hiringAvg} · 路径宽度 {trackOverview.pathAvg} · 资源密度
							{trackOverview.resAvg}（分数越高，在本系统里相对越突出）
						</p>
					</div>
				{/if}
				<p class="track-meta-note">
					帮你看这个方向「招人多不多、路宽不宽、资源丰不富」。分数越高，在本系统岗位库里相对越突出；想了解市场近况可点下方按钮。
				</p>
				<ul class="track-legend-keys">
					<li><strong>招聘可见度</strong>：同类岗位在系统里的招聘活跃程度</li>
					<li><strong>路径宽度</strong>：晋升、转岗等发展路线是否丰富</li>
					<li><strong>资源密度</strong>：可关联的学习课程与竞赛是否充足</li>
				</ul>
				<div class="track-chart">
					{#each usePerJobPlan && activeTargetRow ? [activeTargetRow] : trackRows as row (row.id)}
						{@const tp = resolveTrackProfile(row)}
						<div class="track-row">
							<div class="track-name">{row.display_title || `${row.title} · ${row.company || "未知公司"}`}</div>
							{#if tp}
								<div class="track-bars">
									<div class="bar-item">
										<span>招聘可见度</span>
										<div class="bar-track">
											<div
												class="bar hiring"
												style={`width:${trackBarWidth(tp.hiring_visibility_0_100)}`}
											></div>
										</div>
										<span class="bar-score">{tp.hiring_visibility_0_100}</span>
									</div>
									<div class="bar-item">
										<span>路径宽度</span>
										<div class="bar-track">
											<div class="bar path" style={`width:${trackBarWidth(tp.path_breadth_0_100)}`}></div>
										</div>
										<span class="bar-score">{tp.path_breadth_0_100}</span>
									</div>
									<div class="bar-item">
										<span>资源密度</span>
										<div class="bar-track">
											<div
												class="bar resource"
												style={`width:${trackBarWidth(tp.resource_density_0_100)}`}
											></div>
										</div>
										<span class="bar-score">{tp.resource_density_0_100}</span>
									</div>
								</div>
								<p class="track-text">{trackInsightLine(tp)}</p>
								{#if tp.resources?.learning_resource_count || tp.resources?.competition_count}
									<p class="track-detail meta">
										可引用 {tp.resources?.learning_resource_count ?? 0} 条学习资源、
										{tp.resources?.competition_count ?? 0} 项竞赛来制定成长计划。
									</p>
								{/if}
							{:else}
								<p class="hint">暂无赛道画像数据</p>
							{/if}
							<div class="public-info-block">
								<button
									type="button"
									class="ghost public-info-btn"
									disabled={publicInfoByJobId[row.id]?.loading}
									onclick={() => loadPublicInfo(row)}
								>
									{publicInfoByJobId[row.id]?.loading ? "检索中…" : "查看近期公开信息"}
								</button>
								{#if publicInfoByJobId[row.id]?.data}
									<p class="public-info-summary">{publicInfoByJobId[row.id].data?.summary}</p>
									{#if publicInfoByJobId[row.id].data?.sources?.length}
										<ul class="public-info-sources">
											{#each publicInfoByJobId[row.id].data?.sources || [] as s, i (i)}
												<li>
													{#if s.url}
														<a href={s.url} target="_blank" rel="noopener noreferrer">{s.title || s.url}</a>
													{:else}
														{s.title}
													{/if}
												</li>
											{/each}
										</ul>
									{/if}
									<p class="meta public-info-meta">
										{publicInfoByJobId[row.id].data?.disclaimer || ""}
										{#if publicInfoByJobId[row.id].data?.fetched_at}
											· 检索 {publicInfoByJobId[row.id].data?.fetched_at}
											{publicInfoByJobId[row.id].data?.from_cache ? "（缓存）" : ""}
										{/if}
									</p>
								{/if}
								{#if publicInfoByJobId[row.id]?.error}
									<p class="msg error">{publicInfoByJobId[row.id].error}</p>
								{/if}
							</div>
						</div>
					{/each}
				</div>

				{#if !usePerJobPlan}
					<div class="mini-title">能力缺口热力矩阵</div>
					<div class="heatmap">
						<div class="heat-header">
							<span>职业</span>
							{#each heatmapDimensions as dim (dim)}
								<span>{DIMENSION_LABELS[dim] || dim}</span>
							{/each}
						</div>
						{#each generatedReport.targets as t (t.id)}
							<div class="heat-row">
								<span class="job-cell">{t.display_title || `${t.title} · ${t.company || "未知公司"}`}</span>
								{#each heatmapDimensions as dim (dim)}
									{@const value = Number(dimensionGapsOf(t)[dim] || 0)}
									<span class="gap-cell" style={heatColor(value)}>{value.toFixed(1)}</span>
								{/each}
							</div>
						{/each}
					</div>
				{/if}

				<div class="mini-title">这段时间重点看什么</div>
				<div class="metric-list">
					{#each generatedReport.evaluation.metrics as metric (metric.code)}
						{@const metricDesc = metricDisplayDescription(metric)}
						<div
							class="metric-item"
							class:metric-highlight={highlightedMetricCode === metric.code}
							data-metric-code={metric.code}
						>
							<p>{metricDisplayLabel(metric)}</p>
							{#if metricDesc}
								<p class="meta metric-desc">{metricDesc}</p>
							{/if}
							<p class="meta">{readableCycleText(metric.cycle)} · 希望达到 {readableTargetText(metric.target)}</p>
							{#if metric.code === "dim_gap_reduction" && generatedReport.evaluation.gap_baseline}
								<p class="meta baseline-hint">
									已记录生成报告时的能力差距起点；每月复盘时，看这一项是否在变好。
								</p>
							{/if}
						</div>
					{/each}
				</div>

				{#if reviewTrend.length}
					<div class="mini-title">评估趋势（通过率）</div>
					<div class="review-trend">
						<svg viewBox="0 0 320 98" aria-label="评估趋势折线图">
							<line x1="18" y1="84" x2="305" y2="84" class="axis" />
							<line x1="18" y1="20" x2="18" y2="84" class="axis" />
							<polyline
								points={reviewTrend.map((p) => `${p.x},${p.y}`).join(" ")}
								fill="none"
								stroke="var(--primary)"
								stroke-width="2.4"
							/>
							{#each reviewTrend as p (p.reviewId)}
								<circle cx={p.x} cy={p.y} r="3.2" fill="var(--primary)" />
								<text x={p.x} y={p.y - 6} text-anchor="middle" class="pt">
									{Math.round(p.passRate * 100)}%
								</text>
							{/each}
						</svg>
					</div>
				{/if}

				{#if generatedReport.evaluation.latest_review}
					<div class="mini-title">最近一次评估结果</div>
					<div class="latest-review">
						<p>
							通过率 {Math.round((generatedReport.evaluation.latest_review.evaluation.pass_rate || 0) * 100)}%
							· {generatedReport.evaluation.latest_review.evaluation.all_passed ? "全部达标" : "存在未达标项"}
						</p>
						{#if generatedReport.evaluation.latest_review.llm_extract?.summary}
							<p>
								自动复盘结论：{generatedReport.evaluation.latest_review.llm_extract.summary}
							</p>
						{/if}
						{#if generatedReport.evaluation.latest_review.review_text}
							<p class="review-text">
								复盘输入：{generatedReport.evaluation.latest_review.review_text}
							</p>
						{/if}
						<p class="meta-line">
							本期进展：短板缩小 {Number(generatedReport.evaluation.latest_review.submitted_metrics?.dim_gap_reduction ?? 0).toFixed(1)}% ·
							计划完成 {Number(generatedReport.evaluation.latest_review.submitted_metrics?.project_completion ?? 0).toFixed(1)}% ·
							贴合度变化 {Number(generatedReport.evaluation.latest_review.submitted_metrics?.match_score_change ?? 0).toFixed(1)} 分 ·
							可展示成果 {Math.round(Number(generatedReport.evaluation.latest_review.submitted_metrics?.delivery_output ?? 0))} 项
						</p>
						{#if generatedReport.evaluation.latest_review.adjustment.auto_adjustment.triggered}
							<div class="auto-adjust">
								<p class="font-medium">已触发自动重规划</p>
								<p>{generatedReport.evaluation.latest_review.adjustment.auto_adjustment.reason}</p>
								{#if generatedReport.evaluation.latest_review.adjustment.auto_adjustment.focus_labels?.length}
									<p>
										聚焦维度：
										{generatedReport.evaluation.latest_review.adjustment.auto_adjustment.focus_labels.join("、")}
									</p>
								{/if}
								{#if generatedReport.evaluation.latest_review.adjustment.auto_adjustment.extra_actions?.length}
									<ul>
										{#each generatedReport.evaluation.latest_review.adjustment.auto_adjustment.extra_actions as act (act)}
											<li>{act}</li>
										{/each}
									</ul>
								{/if}
							</div>
						{/if}
					</div>
				{/if}
			{:else}
				<div class="empty-side">
					<p>生成报告后，这里会显示趋势图、热力矩阵与评估指标。</p>
				</div>
			{/if}
{/snippet}



<section class="report-workbench">
	<div class="report-grid">
		<aside class="control-rail" class:collapsed={configRailCollapsed && !!generatedReport}>
			<div class="rail-card">
				<div class="rail-head">
					<h3>目标职业配置</h3>
					<p>智能导入或手动选岗，最多 5 个目标。</p>
				</div>

				<div class="config-module">
					<div class="config-module-head">
						<h4>1. 智能导入</h4>
						<p>从人岗匹配云端记录导入 Top5，画像与策略随记录自动关联。</p>
					</div>
					<button
						type="button"
						class="primary config-module-btn"
						disabled={loadingImport}
						onclick={() => {
							matchImportModalOpen = true;
						}}
					>
						{loadingImport ? "导入中..." : "导入匹配数据"}
					</button>
				</div>

				<div class="config-module">
					<div class="config-module-head">
						<h4>2. 手动导入</h4>
						<p>选择画像记录，点击「搜索候选」从岗位库挑选并加入列表。</p>
					</div>

					<label class="field">
						<span>画像记录</span>
						<select bind:value={selectedResumeId} disabled={!resumes.length}>
							{#each resumes as r (r.id)}
								<option value={r.id}>{r.name} · {r.major}</option>
							{/each}
						</select>
					</label>

					<button
						type="button"
						class="ghost config-module-btn"
						onclick={() => {
							manualSearchModalOpen = true;
						}}
					>
						搜索候选
					</button>
				</div>

				<div class="config-module">
					<div class="config-module-head">
						<h4>历史报告</h4>
						<p>加载已生成的生涯报告，继续查看画布或提交复盘。</p>
					</div>
					<button
						type="button"
						class="ghost config-module-btn"
						onclick={() => {
							reportHistoryModalOpen = true;
						}}
					>
						加载历史报告
					</button>
				</div>

				<div class="selected-area">
					<div class="selected-head">
						<strong>已选职业 {selectedTargets.length}/5</strong>
						<button
							type="button"
							class="text-btn"
							onclick={() => {
								selectedTargets = [];
							}}>清空</button
						>
					</div>
					{#if selectedTargets.length}
						{#each selectedTargets as t (t.job_id)}
							<div class="selected-item">
								<div class="selected-item-body">
									<p class="selected-title">{t.title || t.job_id}</p>
									<p class="selected-sub">{t.company || "未知公司"} · {t.location || "未知地点"}</p>
								</div>
								<button type="button" class="text-btn danger remove-btn" onclick={() => removeTarget(t.job_id)}>移除</button>
							</div>
						{/each}
					{:else}
						<p class="text-sm text-50">暂未添加目标职业。</p>
					{/if}
				</div>

				<label class="match-goal-row">
					<span>匹配期望</span>
					<select bind:value={reportMatchGoal} disabled={loadingGenerate}>
						<option value="fit">稳妥目标（更贴近常规投递门槛）</option>
						<option value="stretch">冲刺目标（允许部分维度略低，仍可尝试）</option>
					</select>
				</label>

				<button
					type="button"
					class="primary generate-btn"
					disabled={loadingGenerate || loadingEnrich || selectedResumeId === "" || !selectedTargets.length}
					onclick={() => void generate()}
				>
					{loadingGenerate || loadingEnrich ? "生成中..." : "生成 M2 生涯报告画布"}
				</button>
				{#if generateProgress}
					<p class="generate-progress" role="status">{generateProgress}</p>
				{/if}
			</div>

			<div class="m3-card">
				<div class="rail-head">
					<h3>M3 动态复盘</h3>
					<p>输入本周期变化，调用 DeepSeek 自动量化并触发调计划。</p>
				</div>
				{#if generatedReport}
					<div class="review-form">
						<p class="m3-rhythm-note">复盘节奏固定为<strong>每月</strong>一次；提交后曲线在横轴第 1、2、3…月处依次标点。</p>
						<div class="review-textarea-block">
							<div class="review-textarea-head">
								<label class="review-textarea-label" for="m3-review-text">本周期变化与复盘</label>
								<button type="button" class="template-btn" onclick={() => applyReviewTemplate()}>
									一键复盘模板
								</button>
							</div>
							<p class="review-textarea-hint">按模板写几句即可，提交后会用 DeepSeek 帮你整理成可评估的数字。</p>
							<div class="review-textarea-shell">
								<textarea
									id="m3-review-text"
									class="review-textarea-input"
									rows="8"
									bind:value={reviewText}
									placeholder="点「一键复盘模板」快速开始，或直接写：本月完成了什么、能力哪里进步、和目标岗位比感觉如何、有没有新成果。"
								></textarea>
							</div>
						</div>
						<button type="button" class="primary" disabled={submittingReview} onclick={() => void submitReview()}>
							{submittingReview ? "提交中..." : "提交评估并动态调整"}
						</button>
						{#if reviewError}
							<p class="msg error">{reviewError}</p>
						{/if}
						{#if reviewInfo}
							<p class="msg ok">{reviewInfo}</p>
						{/if}
					</div>
				{:else}
					<p class="text-sm text-50">请先生成或加载一份报告，再提交动态复盘。</p>
				{/if}
			</div>
		</aside>

		<div class="canvas-main">
			<div class="canvas-head">
				<div>
					<h3>发展线画布</h3>
					<p>
						先在上排卡片选择要看的岗位。横轴为<strong>第 n 月</strong>（每月一次复盘），纵轴为<strong>复盘进步度</strong>（0–100）。每月<strong>一个圆点</strong>：未复盘为橙色、已复盘为蓝色；点击可查看当月复盘与任务。提交复盘后折线连至该月点位。
					</p>
				</div>
				<div class="canvas-head-actions">
					{#if generatedReport}
						<button
							type="button"
							class="ghost"
							onclick={() => {
								configRailCollapsed = !configRailCollapsed;
							}}
						>
							{configRailCollapsed ? "展开配置" : "收起配置"}
						</button>
					{/if}
					{#if generatedReportId}
						<button
							type="button"
							class="ghost"
							disabled={exportingPdf}
							onclick={() => void exportPdf()}
						>
							{exportingPdf ? "导出中..." : "导出 PDF"}
						</button>
					{/if}
				</div>
			</div>

			{#if generatedReport}
				<div class="report-badges">
					<span>报告 #{generatedReportId}</span>
					<span>{generatedReport.generated_at}</span>
					<span>目标职业 {generatedReport.targets.length}</span>
					<span>复盘节奏 {generatedReport.evaluation.cycle.default === "monthly" ? "每月" : generatedReport.evaluation.cycle.default}</span>
				</div>

				{#if error}
					<div class="generate-error" role="alert">{error}</div>
				{/if}
				{#if info}
					<div class="generate-info">{info}</div>
				{/if}

				{#if usePerJobPlan && activePlan}
					<div class="job-workspace">
						<div class="job-tabs" role="tablist" aria-label="目标岗位切换">
							{#each plansByTarget as plan, idx (plan.job_id)}
								<button
									type="button"
									role="tab"
									class="job-tab"
									class:active={activeJobId === plan.job_id}
									aria-selected={activeJobId === plan.job_id}
									onclick={() => selectActiveJob(plan.job_id)}
								>
									<span class="swatch" style={`background:${LINE_COLORS[idx % LINE_COLORS.length]};`}></span>
									<span class="job-tab-text">
										<strong>{plan.job_title_name || "岗位"}</strong>
										<small>{plan.company || "未知公司"}</small>
									</span>
									<span class="job-tab-score">{Math.round(plan.match_score ?? 0)}分</span>
								</button>
							{/each}
						</div>

						<div class="job-hero">
							<div>
								<h4>{activePlan.display_title}</h4>
								<p class="hero-meta">
									{activePlan.location || "未知地点"} · 岗位名 {activePlan.job_title_name} · 匹配分
									<strong>{Math.round(activePlan.match_score ?? 0)}</strong>
								</p>
								{#if activePlan.top_gap_labels?.length}
									<p class="hero-gaps">重点缺口：{activePlan.top_gap_labels.join("、")}</p>
								{/if}
							</div>
							{#if activePlan.narrative}
								<div class="hero-narrative">
									{#if activePlan.narrative.provider === "doubao"}
										<span class="narrative-badge">豆包 · 本岗叙事</span>
									{/if}
									<p>{activePlan.narrative.path_advice}</p>
									<p class="meta">{activePlan.narrative.execution_reminder}</p>
								</div>
							{/if}
						</div>

						{#if activePlan.next_month_plan?.items?.length}
							{@const nmp = activePlan.next_month_plan}
							{@const planMonth = nmp.plan_month ?? activePlan.current_plan_month ?? 1}
							{@const replanMeta = replanModeMeta(nmp.replan_mode)}
							{@const allActions = nmp.items.flatMap((it) => it.custom_actions || [])}
							{@const kindStats = countActionKinds(allActions)}
							<section class="next-month-plan-banner" class:collapsed={!nextMonthSectionOpen}>
								<button
									type="button"
									class="nmp-head"
									aria-expanded={nextMonthSectionOpen}
									onclick={() => {
										nextMonthSectionOpen = !nextMonthSectionOpen;
									}}
								>
									<div class="nmp-head-main">
										<div
											class="month-ring"
											style={`--ring-pct: ${Math.round((planMonth / 12) * 100)}%;`}
											aria-hidden="true"
										>
											<span>{planMonth}<small>月</small></span>
										</div>
										<div class="nmp-head-text">
											<h5>
												下月执行 · {nmp.phase_label || phaseLabelFromKey(nmp.phase_key)}
											</h5>
											<div class="nmp-chips">
												<span class="nmp-chip nmp-chip--phase">{nmp.phase_label || "前期"}</span>
												<span class="nmp-chip nmp-chip--{replanMeta.tone}">{replanMeta.label}</span>
												<span class="nmp-chip">{nmp.items.length} 项聚焦</span>
												<span class="nmp-chip">{kindStats.total} 条行动</span>
											</div>
										</div>
									</div>
									<span class="nmp-chevron" class:open={nextMonthSectionOpen} aria-hidden="true"></span>
								</button>

								{#if nextMonthSectionOpen}
									<div class="nmp-body">
										{#if nmp.replan_mode === "strong"}
											<p class="nmp-alert warn">连续未达标，下月任务密度已加强，请优先完成带图谱链接的事项。</p>
										{:else if nmp.replan_mode === "continue"}
											<p class="nmp-alert ok">本月评估达标，按总体规划继续推进即可。</p>
										{/if}

										{#if kindStats.total > 0}
											<div class="nmp-mix-bar" aria-label="行动类型分布">
												{#if kindStats.learn > 0}
													<span
														class="mix-seg mix-learn"
														style={`flex: ${kindStats.learn}`}
														title={`学习 ${kindStats.learn} 条`}
													></span>
												{/if}
												{#if kindStats.practice > 0}
													<span
														class="mix-seg mix-practice"
														style={`flex: ${kindStats.practice}`}
														title={`实践 ${kindStats.practice} 条`}
													></span>
												{/if}
												{#if kindStats.deliverable > 0}
													<span
														class="mix-seg mix-deliverable"
														style={`flex: ${kindStats.deliverable}`}
														title={`成果 ${kindStats.deliverable} 条`}
													></span>
												{/if}
											</div>
											<div class="nmp-mix-legend">
												<span><i class="dot learn"></i>学习 {kindStats.learn}</span>
												<span><i class="dot practice"></i>实践 {kindStats.practice}</span>
												<span><i class="dot deliverable"></i>成果 {kindStats.deliverable}</span>
											</div>
										{/if}

										<div class="nmp-cards">
											{#each nmp.items as nm, ni (`nm-${ni}-${nm.focus_dimension}`)}
												{@const itemKey = nextMonthItemKey(activePlan.job_id, ni, nm.focus_dimension)}
												{@const itemOpen = isNextMonthItemOpen(itemKey, ni === 0)}
												{@const itemKinds = countActionKinds(nm.custom_actions)}
												<article class="nmp-card" class:open={itemOpen}>
													<button
														type="button"
														class="nmp-card-head"
														aria-expanded={itemOpen}
														onclick={() => toggleNextMonthItem(itemKey, ni === 0)}
													>
														<span
															class="nmp-focus-icon"
															style={`background: color-mix(in oklch, ${LINE_COLORS[ni % LINE_COLORS.length]} 18%, transparent); color: ${LINE_COLORS[ni % LINE_COLORS.length]};`}
														>
															{ni + 1}
														</span>
														<span class="nmp-card-title-wrap">
															<strong>{nm.focus_label}</strong>
															<small>{itemKinds.total} 条行动 · 点击{itemOpen ? "收起" : "展开"}</small>
														</span>
														<span class="nmp-card-chevron" class:open={itemOpen} aria-hidden="true"></span>
													</button>

													{#if itemOpen}
														<div class="nmp-card-body">
															<div class="nmp-milestone-box">
																<span class="nmp-milestone-tag">里程碑</span>
																<p>{sanitizePlanDisplayText(nm.milestone)}</p>
															</div>

															{#if nm.growth_rationale}
																<p class="growth-rationale nmp-growth">{sanitizePlanDisplayText(nm.growth_rationale)}</p>
															{/if}

															{#if nm.custom_actions?.length}
																<ul class="nmp-action-list">
																	{#each nm.custom_actions as act, ai (`nma-${ni}-${ai}`)}
																		{@const actionKey = nextMonthActionKey(itemKey, ai)}
																		{@const done = isNextMonthActionDone(act, actionKey)}
																		{@const kind = String(act.kind || "practice").toLowerCase()}
																		<li>
																			<button
																				type="button"
																				class="nmp-action-row"
																				class:done
																				onclick={() =>
																					void toggleNextMonthAction(
																						activePlan.job_id,
																						ni,
																						nm.focus_dimension,
																						ai,
																					)}
																			>
																				<span class="nmp-check" class:checked={done} aria-hidden="true">
																					{#if done}✓{/if}
																				</span>
																				<span
																					class="action-kind kind-{kind}"
																					style={`--kind-color: ${ACTION_KIND_COLORS[kind] || ACTION_KIND_COLORS.practice}`}
																				>
																					{actionKindLabel(act.kind)}
																				</span>
																				<span class="nmp-action-text">{sanitizePlanDisplayText(act.text)}</span>
																			</button>
																		</li>
																	{/each}
																</ul>
															{/if}

															{#if nm.learning_path_refs?.length}
																<div class="nmp-ref-deck">
																	<span class="nmp-ref-label">图谱资源</span>
																	{#each nm.learning_path_refs as ref (`nm-lr-${ni}-${ref.id}`)}
																		{#if ref.url}
																			<a
																				class="nmp-ref-pill"
																				href={ref.url}
																				target="_blank"
																				rel="noopener noreferrer"
																			>
																				{ref.label || ref.id} ↗
																			</a>
																		{:else}
																			<span class="nmp-ref-pill muted">{ref.label || ref.id}</span>
																		{/if}
																	{/each}
																</div>
															{/if}
														</div>
													{/if}
												</article>
											{/each}
										</div>
									</div>
								{/if}
							</section>
						{/if}

						<div class="phase-stepper" role="tablist" aria-label="成长阶段">
							{#each ["early", "mid", "late"] as ph}
								{@const pb = activePlan.phases[ph as "early" | "mid" | "late"]}
								<button
									type="button"
									role="tab"
									class="phase-step"
									class:active={activePhase === ph}
									onclick={() => {
										activePhase = ph as "early" | "mid" | "late";
									}}
								>
									<span class="phase-label">{pb?.label || ph}</span>
									<span class="phase-period">{phasePeriodDisplay(ph as "early" | "mid" | "late", pb?.period)}</span>
								</button>
							{/each}
						</div>

						<div class="job-body-grid">
							<div class="job-main-stack">
								<section class="phase-detail-panel">
									{#if activePhaseBlock}
										<h5>{activePhaseBlock.label} · {phasePeriodDisplay(activePhase, activePhaseBlock.period)}</h5>
										{#if activePhaseBlock.line_one_liner}
											<p class="phase-liner">{activePhaseBlock.line_one_liner}</p>
										{:else if activePhaseBlock.summary}
											<p class="phase-summary">{activePhaseBlock.summary}</p>
										{/if}
										<div class="plan-items spacious">
											{#each activePhaseBlock.items as item (`${activePhase}-${item.order}-${item.focus_dimension}`)}
												<article class="plan-item rich">
													<p class="title">{item.focus_label}</p>
													<p class="milestone">里程碑：{item.milestone}</p>
													{#if item.learning_path_refs?.length}
														<div class="plan-block-section">
															<p class="section-label">图谱推荐</p>
															<ul class="ref-links">
																{#each item.learning_path_refs as ref (`ph-lr-${ref.id}`)}
																	<li>
																		{#if ref.url}
																			<a href={ref.url} target="_blank" rel="noopener noreferrer">{ref.label || ref.id}</a>
																		{:else}
																			{ref.label || ref.id}
																		{/if}
																		{#if ref.rationale}<span class="ref-why">{ref.rationale}</span>{/if}
																	</li>
																{/each}
															</ul>
														</div>
													{/if}
													{#if item.practice_plan_refs?.length}
														<div class="plan-block-section">
															<p class="section-label">竞赛实践</p>
															<ul class="ref-links practice">
																{#each item.practice_plan_refs as ref (`ph-cp-${ref.id}`)}
																	<li>
																		{#if ref.url}
																			<a href={ref.url} target="_blank" rel="noopener noreferrer">{ref.label || ref.id}</a>
																		{:else}
																			{ref.label || ref.id}
																		{/if}
																	</li>
																{/each}
															</ul>
														</div>
													{/if}
													{#if item.growth_rationale}
														<p class="growth-rationale phase-growth">{sanitizePlanDisplayText(item.growth_rationale)}</p>
													{/if}
													{#if item.custom_actions?.length}
														<div class="plan-block-section custom">
															<p class="section-label">
																定制行动（本岗 JD）
																{#if activePlan.customization?.provider === "deepseek"}
																	<span class="ref-tag">DeepSeek</span>
																{/if}
															</p>
															<ul class="custom-actions action-checklist">
																{#each item.custom_actions as act, ai (`ph-ca-${item.focus_dimension}-${ai}`)}
																	<li class="kind-{act.kind}">
																		<span class="action-kind">{actionKindLabel(act.kind)}</span>
																		{sanitizePlanDisplayText(act.text)}
																	</li>
																{/each}
															</ul>
														</div>
													{:else if item.learning_path?.length && !item.learning_path_refs?.length}
														<p class="meta">学习：{item.learning_path.join("；")}</p>
													{/if}
												</article>
											{/each}
										</div>
									{/if}
								</section>

								<section class="canvas-panel canvas-panel--stacked">
									<h5>本岗位发展线</h5>
									<p class="canvas-panel-hint">
										横轴为月份复盘，纵轴为复盘进步度。每月<strong>一个圆点</strong>：橙色为计划节点、蓝色为已复盘；点击可查看当月复盘与任务详情。
									</p>
									{@render developmentCanvas(true)}
								</section>

								{@render canvasMonthDetail(true)}

								{#if activePlan.recommendations}
									<section class="resource-deck">
										<h5>图谱推荐资源（本岗位）</h5>
										<div class="rec-grid">
											<div class="rec-col">
												<h6>学习资源</h6>
												{#each activePlan.recommendations.learning_resources || [] as lr (`deck-lr-${lr.resource_id}`)}
													<article class="rec-card rich">
														<p class="rec-title">
															<a href={lr.resource_url} target="_blank" rel="noopener noreferrer">{lr.resource_name}</a>
														</p>
														<p class="rec-meta">
															{lr.resource_type} · {lr.difficulty} · {lr.skill_tag}
														</p>
														{#if lr.resource_desc}
															<p class="rec-desc">{lr.resource_desc.slice(0, 120)}{lr.resource_desc.length > 120 ? "…" : ""}</p>
														{/if}
														{#if lr.rationale}<p class="rec-why">{lr.rationale}</p>{/if}
													</article>
												{:else}
													<p class="meta">暂无</p>
												{/each}
											</div>
											<div class="rec-col">
												<h6>竞赛</h6>
												{#each activePlan.recommendations.competitions || [] as cp (`deck-cp-${cp.competition_id}`)}
													<article class="rec-card rich">
														<p class="rec-title">
															<a href={cp.official_url} target="_blank" rel="noopener noreferrer">{cp.competition_name}</a>
														</p>
														<p class="rec-meta">
															{cp.competition_type} · {cp.difficulty} · {cp.award_level}
														</p>
														{#if cp.rationale}<p class="rec-why">{cp.rationale}</p>{/if}
													</article>
												{:else}
													<p class="meta">暂无</p>
												{/each}
											</div>
										</div>
									</section>
								{/if}
							</div>

							<section class="insight-embed-panel">
								<h5>趋势与评估</h5>
								<p class="insight-embed-hint">
									当前选中岗位的趋势、缺口与评估指标。
								</p>
								{@render insightPanel()}
							</section>
						</div>
					</div>
				{:else}
				<div class="planning-main legacy-plan">
					<div class="planning-head">
						<h4>个性化成长规划（汇总版 · 旧报告）</h4>
						<p>本报告无分岗计划数据，显示多岗汇总规划。请重新生成报告以启用分岗三阶段视图。</p>
					</div>

					<div class="planning-grid">
						<section class="plan-block strategy">
							<h5>总体策略</h5>
							{#if narrativeBlocks.length}
								{#each narrativeBlocks as b, i (`nb-${i}`)}
									<p>{b}</p>
								{/each}
							{:else}
								<p>围绕目标职业缺口，先完成短期能力补齐，再在中期积累岗位化项目与可展示成果。</p>
							{/if}
						</section>

						<section class="plan-block">
							<h5>短期（0-3个月）</h5>
							{#if shortPlanItems.length}
								<div class="plan-items">
									{#each shortPlanItems as item (`sp-${item.order}-${item.focus_dimension}`)}
										<article class="plan-item">
											<p class="title">{item.focus_label} · 里程碑：{item.milestone}</p>
											{#if item.learning_path_refs?.length}
												<ul class="ref-links">
													{#each item.learning_path_refs as ref (`sp-lr-${ref.id}`)}
														<li>
															{#if ref.url}
																<a href={ref.url} target="_blank" rel="noopener noreferrer">{ref.label || ref.id}</a>
															{:else}
																{ref.label || ref.id}
															{/if}
															<span class="ref-tag">图谱</span>
														</li>
													{/each}
												</ul>
											{:else if item.learning_path?.length}
												<p class="meta">学习路径：{item.learning_path.join("；")}</p>
											{/if}
											{#if item.practice_plan_refs?.length}
												<ul class="ref-links">
													{#each item.practice_plan_refs as ref (`sp-cp-${ref.id}`)}
														<li>
															{#if ref.url}
																<a href={ref.url} target="_blank" rel="noopener noreferrer">{ref.label || ref.id}</a>
															{:else}
																{ref.label || ref.id}
															{/if}
															<span class="ref-tag">竞赛</span>
														</li>
													{/each}
												</ul>
											{:else if item.practice_plan?.length}
												<p class="meta">实践安排：{item.practice_plan.join("；")}</p>
											{/if}
										</article>
									{/each}
								</div>
							{:else}
								<p>暂无短期计划数据。</p>
							{/if}
						</section>

						<section class="plan-block">
							<h5>中后期（3-12个月）</h5>
							{#if midPlanItems.length}
								<div class="plan-items">
									{#each midPlanItems as item (`mp-${item.order}-${item.focus_dimension}`)}
										<article class="plan-item">
											<p class="title">{item.focus_label} · 里程碑：{item.milestone}</p>
											{#if item.learning_path_refs?.length}
												<ul class="ref-links">
													{#each item.learning_path_refs as ref (`mp-lr-${ref.id}`)}
														<li>
															{#if ref.url}
																<a href={ref.url} target="_blank" rel="noopener noreferrer">{ref.label || ref.id}</a>
															{:else}
																{ref.label || ref.id}
															{/if}
															<span class="ref-tag">图谱</span>
														</li>
													{/each}
												</ul>
											{:else if item.learning_path?.length}
												<p class="meta">学习路径：{item.learning_path.join("；")}</p>
											{/if}
											{#if item.practice_plan_refs?.length}
												<ul class="ref-links">
													{#each item.practice_plan_refs as ref (`mp-cp-${ref.id}`)}
														<li>
															{#if ref.url}
																<a href={ref.url} target="_blank" rel="noopener noreferrer">{ref.label || ref.id}</a>
															{:else}
																{ref.label || ref.id}
															{/if}
															<span class="ref-tag">竞赛</span>
														</li>
													{/each}
												</ul>
											{:else if item.practice_plan?.length}
												<p class="meta">实践安排：{item.practice_plan.join("；")}</p>
											{/if}
										</article>
									{/each}
								</div>
							{:else}
								<p>暂无中期计划数据。</p>
							{/if}
						</section>

					</div>
				</div>
				{/if}

				{#if !usePerJobPlan && generatedReport}
					<section class="insight-embed-wide">
						<h5>趋势与评估</h5>
						<p class="insight-embed-hint">
							聚合展示目标职业趋势、能力缺口与评估指标。
						</p>
						{@render insightPanel()}
					</section>
					{@render developmentCanvas(false)}
				{/if}

				{#if !usePerJobPlan}
					<div class="line-picker">
						{#each lineNodes as line, idx (line.line_id)}
							<button
								type="button"
								class="line-card"
								class:active={activeLineId === line.line_id}
								onclick={() => {
									focusLineId = line.line_id;
									selectedTimelineReviewId = null;
									const adjs = (generatedReport?.development_lines?.adjustments || []).filter(
										(a) => a.line_id === line.line_id,
									);
									selectedAdjustmentId = adjs[0]?.id || "";
								}}
							>
								<span class="swatch" style={`background:${LINE_COLORS[idx % LINE_COLORS.length]};`}></span>
								<span class="line-card-name">{line.line_name}</span>
							</button>
						{/each}
					</div>
				{/if}

			{:else}
				<div class="empty-canvas">
					<p>先在左侧配置目标职业并生成报告，发展线画布会在这里显示。</p>
				</div>
			{/if}
		</div>

	</div>

	{#if focusTarget}
		<div class="focus-strip">
			<strong>{focusTarget.title}</strong>
			<span>{focusTarget.company} · {focusTarget.location}</span>
			<span>匹配度 {focusTarget.match_preview.match_score}</span>
			<span>招聘可见度 {resolveTrackProfile(focusTarget)?.hiring_visibility_0_100 ?? "—"}</span>
		</div>
	{/if}

	{#if error}
		<p class="msg error">{error}</p>
	{/if}
	{#if info}
		<p class="msg ok">{info}</p>
	{/if}

	<MatchHistoryModal
		open={matchImportModalOpen}
		modalTitle="选择匹配记录"
		confirmLabel="导入"
		emptyHint="暂无匹配记录，请先到「人岗匹配」完成一次匹配。"
		onClose={() => {
			matchImportModalOpen = false;
		}}
		onLoad={(detail) => void handleMatchImportSelect(detail)}
	/>

	<ReportHistoryModal
		open={reportHistoryModalOpen}
		resumeNames={Object.fromEntries(resumes.map((r) => [r.id, r.name]))}
		onClose={() => {
			reportHistoryModalOpen = false;
		}}
		onLoad={(detail) => applyHistoryReportDetail(detail)}
	/>

	<ManualTargetSearchModal
		open={manualSearchModalOpen}
		selectedTargets={selectedTargets}
		onClose={() => {
			manualSearchModalOpen = false;
		}}
		onSelect={(target) => upsertTarget(target)}
		onRemove={(jobId) => removeTarget(jobId)}
	/>

	{#if canvasZoomOpen}
		<div
			use:portal
			class="canvas-zoom-backdrop"
			role="dialog"
			aria-modal="true"
			aria-labelledby="canvas-zoom-title"
			tabindex="-1"
			onkeydown={(event) => {
				if (event.key === "Escape") {
					event.preventDefault();
					canvasZoomOpen = false;
				}
			}}
		>
			<button
				type="button"
				class="canvas-zoom-backdrop-hit"
				aria-label="关闭"
				onclick={() => (canvasZoomOpen = false)}
			></button>
			<div class="canvas-zoom-panel">
				<div class="canvas-zoom-head">
					<h3 id="canvas-zoom-title">本岗位发展线</h3>
					<button type="button" class="canvas-zoom-close" onclick={() => (canvasZoomOpen = false)}>
						关闭
					</button>
				</div>
				<p class="canvas-panel-hint canvas-zoom-hint">
					横轴为复盘月份，纵轴为复盘进步度；橙点为计划节点，蓝点为已完成复盘。
				</p>
				<div class="line-canvas-wrap line-canvas-wrap--zoom">
					{@render lineCanvasSvg(CHART_LARGE, true)}
				</div>
			</div>
		</div>
	{/if}
</section>

<style>
	.report-workbench {
		display: grid;
		gap: 1rem;
	}
	.report-grid {
		display: grid;
		gap: 0.9rem;
		grid-template-columns: 320px minmax(0, 1fr);
		align-items: start;
	}
	.control-rail {
		display: grid;
		gap: 0.9rem;
		min-width: 0;
		max-width: 100%;
		position: sticky;
		top: 1rem;
		align-self: start;
		max-height: calc(100vh - 2rem);
		overflow-y: auto;
		scrollbar-gutter: stable;
	}
	.rail-card,
	.m3-card,
	.canvas-main {
		border: 1px solid color-mix(in oklch, currentColor 12%, transparent);
		background: color-mix(in oklch, var(--card-bg) 94%, transparent);
		border-radius: 1rem;
		padding: 1rem;
		min-width: 0;
		max-width: 100%;
		box-sizing: border-box;
	}
	.rail-head h3,
	.canvas-head h3 {
		font-size: 1rem;
		font-weight: 700;
	}
	.rail-head p,
	.canvas-head p {
		font-size: 0.78rem;
		color: color-mix(in oklch, currentColor 55%, transparent);
	}
	.canvas-head-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		align-items: flex-start;
	}
	.config-module {
		margin-top: 0.85rem;
		padding: 0.75rem;
		border-radius: 0.85rem;
		border: 1px solid color-mix(in oklch, currentColor 10%, transparent);
		background: color-mix(in oklch, var(--btn-regular-bg) 45%, transparent);
		min-width: 0;
		max-width: 100%;
		box-sizing: border-box;
	}
	.config-module-head h4 {
		font-size: 0.88rem;
		font-weight: 700;
	}
	.config-module-head p {
		margin-top: 0.25rem;
		font-size: 0.74rem;
		color: color-mix(in oklch, currentColor 52%, transparent);
	}
	.config-module-btn {
		margin-top: 0.65rem;
		width: 100%;
	}
	.config-module .field {
		margin-top: 0.65rem;
	}
	.field {
		margin-top: 0.8rem;
		display: grid;
		gap: 0.4rem;
	}
	.field span {
		font-size: 0.78rem;
		color: color-mix(in oklch, currentColor 60%, transparent);
	}
	select,
	input,
	textarea {
		width: 100%;
		border-radius: 0.75rem;
		border: 1px solid color-mix(in oklch, currentColor 12%, transparent);
		background: var(--btn-regular-bg);
		padding: 0.55rem 0.65rem;
		font-size: 0.82rem;
	}
	.mode-switch {
		display: flex;
		flex-wrap: wrap;
		gap: 0.8rem;
		font-size: 0.82rem;
	}
	.primary,
	.ghost {
		border-radius: 0.75rem;
		padding: 0.58rem 0.8rem;
		font-size: 0.82rem;
		font-weight: 600;
	}
	.primary {
		background: var(--primary);
		color: white;
	}
	.primary:disabled,
	.ghost:disabled {
		opacity: 0.5;
	}
	.ghost {
		border: 1px solid color-mix(in oklch, currentColor 15%, transparent);
	}
	.selected-area {
		margin-top: 0.8rem;
		display: grid;
		gap: 0.5rem;
		min-width: 0;
		width: 100%;
	}
	.selected-head,
	.selected-item {
		display: flex;
		gap: 0.6rem;
		align-items: center;
		justify-content: space-between;
		min-width: 0;
		width: 100%;
		box-sizing: border-box;
	}
	.selected-item {
		padding: 0.45rem 0.5rem;
		border-radius: 0.6rem;
		background: color-mix(in oklch, var(--btn-regular-bg) 70%, transparent);
	}
	.selected-item-body {
		flex: 1 1 auto;
		min-width: 0;
		overflow: hidden;
	}
	.selected-title {
		margin: 0;
		font-size: 0.82rem;
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.selected-sub {
		margin: 0.12rem 0 0;
		font-size: 0.73rem;
		color: color-mix(in oklch, currentColor 55%, transparent);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.remove-btn {
		flex: 0 0 auto;
		white-space: nowrap;
	}
	.text-btn {
		font-size: 0.74rem;
		color: color-mix(in oklch, currentColor 55%, transparent);
	}
	.text-btn.danger {
		color: #ef4444;
	}
	.match-goal-row {
		display: grid;
		gap: 0.35rem;
		margin-top: 0.65rem;
		font-size: 0.78rem;
	}
	.match-goal-row select {
		width: 100%;
		border-radius: 8px;
		border: 1px solid color-mix(in oklch, currentColor 12%, transparent);
		padding: 0.4rem 0.5rem;
		background: var(--btn-regular-bg);
		font-size: 0.78rem;
	}
	.generate-progress {
		margin: 0.35rem 0 0;
		font-size: 0.72rem;
		color: color-mix(in oklch, var(--primary) 75%, currentColor);
		line-height: 1.4;
	}
	.generate-btn {
		margin-top: 0.55rem;
		width: 100%;
	}
	.canvas-head {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		align-items: flex-start;
	}
	.canvas-tools {
		display: inline-flex;
		gap: 0.35rem;
	}
	.canvas-tools button {
		border: 1px solid color-mix(in oklch, currentColor 14%, transparent);
		padding: 0.3rem 0.55rem;
		border-radius: 0.55rem;
		font-size: 0.74rem;
	}
	.canvas-tools button.active {
		background: var(--primary);
		color: white;
		border-color: transparent;
	}
	.report-badges {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin-top: 0.7rem;
	}
	.report-badges span {
		font-size: 0.72rem;
		padding: 0.2rem 0.45rem;
		border-radius: 999px;
		background: color-mix(in oklch, var(--primary) 12%, transparent);
		color: color-mix(in oklch, var(--primary) 80%, black);
	}
	.planning-main {
		margin-top: 0.8rem;
		padding: 0.75rem;
		border-radius: 0.9rem;
		border: 1px solid color-mix(in oklch, currentColor 14%, transparent);
		background: color-mix(in oklch, var(--btn-regular-bg) 72%, transparent);
	}
	.planning-head h4 {
		font-size: 0.95rem;
		font-weight: 700;
	}
	.planning-head p {
		font-size: 0.74rem;
		color: color-mix(in oklch, currentColor 56%, transparent);
	}
	.planning-grid {
		margin-top: 0.6rem;
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.55rem;
	}
	.plan-block {
		padding: 0.55rem 0.6rem;
		border-radius: 0.7rem;
		background: color-mix(in oklch, var(--card-bg) 92%, transparent);
		border: 1px solid color-mix(in oklch, currentColor 10%, transparent);
		display: grid;
		gap: 0.3rem;
	}
	.plan-block h5 {
		font-size: 0.8rem;
		font-weight: 700;
	}
	.plan-block p {
		font-size: 0.72rem;
		line-height: 1.5;
	}
	.plan-items {
		display: grid;
		gap: 0.35rem;
	}
	.plan-item {
		padding: 0.35rem 0.42rem;
		border-left: 2px solid color-mix(in oklch, var(--primary) 62%, white);
		background: color-mix(in oklch, var(--btn-regular-bg) 68%, transparent);
		border-radius: 0.45rem;
	}
	.plan-item .title {
		font-size: 0.72rem;
		font-weight: 600;
	}
	.ref-links {
		margin: 6px 0 0;
		padding-left: 18px;
		font-size: 12px;
	}
	.ref-links a {
		color: #1d4ed8;
		text-decoration: none;
	}
	.ref-links a:hover {
		text-decoration: underline;
	}
	.ref-tag {
		display: inline-block;
		margin-left: 6px;
		padding: 1px 6px;
		font-size: 10px;
		border-radius: 4px;
		background: #e0e7ff;
		color: #3730a3;
		vertical-align: middle;
	}
	.rec-block .rec-hint {
		font-size: 12px;
		color: #64748b;
		margin: 0 0 10px;
	}
	.rec-tabs {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		margin-bottom: 10px;
	}
	.rec-tab {
		border: 1px solid #cbd5e1;
		background: #fff;
		border-radius: 6px;
		padding: 4px 10px;
		font-size: 12px;
		cursor: pointer;
	}
	.rec-tab.active {
		border-color: #3b82f6;
		background: #eff6ff;
		color: #1d4ed8;
	}
	.rec-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
	}
	@media (max-width: 900px) {
		.rec-grid {
			grid-template-columns: 1fr;
		}
	}
	.rec-col h6 {
		margin: 0 0 8px;
		font-size: 13px;
		color: #334155;
	}
	.rec-card {
		border: 1px solid #e2e8f0;
		border-radius: 8px;
		padding: 8px 10px;
		margin-bottom: 8px;
		background: #fafbff;
	}
	.rec-title {
		margin: 0;
		font-size: 13px;
		font-weight: 600;
	}
	.rec-title a {
		color: #1d4ed8;
		text-decoration: none;
	}
	.rec-meta,
	.rec-why {
		margin: 4px 0 0;
		font-size: 11px;
		color: #64748b;
	}
	.generate-error {
		margin: 0.75rem 0;
		padding: 0.65rem 0.85rem;
		border-radius: 0.65rem;
		background: color-mix(in oklch, #ef4444 12%, transparent);
		color: #b91c1c;
		font-size: 0.85rem;
	}
	.generate-info {
		margin: 0.5rem 0;
		font-size: 0.82rem;
		color: color-mix(in oklch, #16a34a 80%, currentColor);
	}
	.control-rail.collapsed .config-module:not(:last-child),
	.control-rail.collapsed .selected-area {
		display: none;
	}
	.job-workspace {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		margin-top: 0.75rem;
	}
	.job-tabs {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}
	.job-tab {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.45rem 0.65rem;
		border: 1px solid color-mix(in oklch, currentColor 14%, transparent);
		border-radius: 0.65rem;
		background: var(--btn-regular-bg);
		cursor: pointer;
		max-width: 100%;
	}
	.job-tab.active {
		border-color: #3b82f6;
		background: color-mix(in oklch, #3b82f6 10%, var(--btn-regular-bg));
	}
	.job-tab-text {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		min-width: 0;
		text-align: left;
	}
	.job-tab-text strong {
		font-size: 0.82rem;
	}
	.job-tab-text small {
		font-size: 0.72rem;
		color: color-mix(in oklch, currentColor 55%, transparent);
	}
	.job-tab-score {
		font-size: 0.78rem;
		font-weight: 700;
		color: #1d4ed8;
		white-space: nowrap;
	}
	.job-hero {
		display: grid;
		gap: 0.75rem;
		padding: 1rem;
		border-radius: 0.85rem;
		border: 1px solid color-mix(in oklch, currentColor 10%, transparent);
		background: color-mix(in oklch, var(--btn-regular-bg) 50%, transparent);
	}
	.job-hero h4 {
		margin: 0;
		font-size: 1rem;
	}
	.hero-meta,
	.hero-gaps {
		margin: 0.35rem 0 0;
		font-size: 0.8rem;
		color: color-mix(in oklch, currentColor 58%, transparent);
	}
	.hero-narrative p {
		margin: 0.25rem 0;
		font-size: 0.82rem;
		line-height: 1.55;
	}
	.phase-stepper {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 0.5rem;
	}
	.phase-step {
		padding: 0.65rem 0.5rem;
		border: 1px solid color-mix(in oklch, currentColor 12%, transparent);
		border-radius: 0.65rem;
		background: var(--btn-regular-bg);
		cursor: pointer;
		text-align: center;
	}
	.phase-step.active {
		border-color: #2563eb;
		background: color-mix(in oklch, #2563eb 12%, var(--btn-regular-bg));
	}
	.phase-step .phase-label {
		display: block;
		font-weight: 700;
		font-size: 0.9rem;
	}
	.phase-step .phase-period {
		display: block;
		font-size: 0.72rem;
		color: color-mix(in oklch, currentColor 55%, transparent);
		margin-top: 0.15rem;
	}
	.job-body-grid {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(240px, 320px);
		gap: 1rem;
		align-items: start;
	}
	.job-main-stack {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		min-width: 0;
	}
	@media (max-width: 1200px) {
		.job-body-grid {
			grid-template-columns: minmax(0, 1fr) minmax(220px, 280px);
		}
	}
	@media (max-width: 960px) {
		.job-body-grid {
			grid-template-columns: 1fr;
		}
		.insight-embed-panel {
			position: static;
			max-height: none;
			overflow: visible;
		}
	}
	.phase-detail-panel,
	.canvas-panel {
		padding: 0.85rem;
		border-radius: 0.85rem;
		border: 1px solid color-mix(in oklch, currentColor 10%, transparent);
		background: color-mix(in oklch, var(--card-bg) 96%, transparent);
		min-width: 0;
		overflow: hidden;
	}
	.canvas-panel--stacked .line-canvas-wrap.workbench {
		margin-top: 0.35rem;
		padding: 0.55rem 0.65rem 0.7rem;
	}
	.canvas-panel--stacked .line-canvas {
		min-height: 280px;
	}
	.insight-embed-panel {
		padding: 0.85rem;
		border-radius: 0.85rem;
		border: 1px solid color-mix(in oklch, currentColor 10%, transparent);
		background: color-mix(in oklch, var(--card-bg) 96%, transparent);
		min-width: 0;
		overflow-x: hidden;
		overflow-y: auto;
		position: sticky;
		top: 0.75rem;
		max-height: calc(100vh - 1.5rem);
		scrollbar-gutter: stable;
	}
	.insight-embed-hint {
		font-size: 0.72rem;
		color: color-mix(in oklch, currentColor 55%, transparent);
		margin: 0.2rem 0 0.65rem;
		line-height: 1.4;
	}
	.insight-embed-panel h5,
	.insight-embed-wide h5 {
		font-size: 0.88rem;
		font-weight: 700;
		margin: 0;
	}
	.insight-embed-panel .mini-title:first-of-type,
	.insight-embed-wide .mini-title:first-of-type {
		margin-top: 0.35rem;
	}
	.insight-embed-panel .trend-chart,
	.insight-embed-wide .trend-chart {
		max-height: none;
	}
	.insight-embed-wide {
		margin-top: 1rem;
		padding: 0.85rem;
		border-radius: 0.85rem;
		border: 1px solid color-mix(in oklch, currentColor 10%, transparent);
		background: color-mix(in oklch, var(--card-bg) 96%, transparent);
	}
	.insight-embed-wide .heatmap {
		overflow-x: auto;
	}
	.phase-summary {
		font-size: 0.8rem;
		color: color-mix(in oklch, currentColor 58%, transparent);
		margin: 0.35rem 0 0.75rem;
	}
	.plan-items.spacious {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.plan-item.rich {
		padding: 0.75rem;
		border-radius: 0.65rem;
		background: color-mix(in oklch, var(--btn-regular-bg) 55%, transparent);
	}
	.plan-item.rich .milestone {
		font-size: 0.78rem;
		color: color-mix(in oklch, currentColor 62%, transparent);
		margin: 0.25rem 0;
	}
	.next-month-plan-banner {
		margin: 0.75rem 0 1rem;
		border-radius: 0.85rem;
		border: 1px solid color-mix(in oklch, var(--color-primary) 35%, transparent);
		background: linear-gradient(
			145deg,
			color-mix(in oklch, var(--color-primary) 10%, var(--card-bg)),
			color-mix(in oklch, var(--color-primary) 4%, var(--card-bg))
		);
		overflow: hidden;
	}
	.nmp-head {
		width: 100%;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		padding: 0.75rem 0.85rem;
		border: none;
		background: transparent;
		cursor: pointer;
		text-align: left;
		color: inherit;
	}
	.nmp-head-main {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		min-width: 0;
	}
	.nmp-head-text h5 {
		margin: 0;
		font-size: 0.92rem;
		font-weight: 700;
	}
	.nmp-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		margin-top: 0.35rem;
	}
	.nmp-chip {
		font-size: 0.68rem;
		padding: 0.12rem 0.45rem;
		border-radius: 999px;
		background: color-mix(in oklch, currentColor 8%, transparent);
		border: 1px solid color-mix(in oklch, currentColor 12%, transparent);
	}
	.nmp-chip--warn {
		background: color-mix(in oklch, #f59e0b 15%, transparent);
		border-color: color-mix(in oklch, #f59e0b 35%, transparent);
		color: color-mix(in oklch, #b45309 90%, currentColor);
	}
	.nmp-chip--ok {
		background: color-mix(in oklch, #10b981 12%, transparent);
		border-color: color-mix(in oklch, #10b981 30%, transparent);
		color: color-mix(in oklch, #047857 90%, currentColor);
	}
	.nmp-chip--phase {
		background: color-mix(in oklch, var(--color-primary) 12%, transparent);
		border-color: color-mix(in oklch, var(--color-primary) 28%, transparent);
	}
	.month-ring {
		--ring-pct: 8%;
		flex-shrink: 0;
		width: 2.75rem;
		height: 2.75rem;
		border-radius: 50%;
		background: conic-gradient(
			var(--color-primary) calc(var(--ring-pct) * 1%),
			color-mix(in oklch, currentColor 10%, transparent) 0
		);
		display: grid;
		place-items: center;
	}
	.month-ring > span {
		width: 2.05rem;
		height: 2.05rem;
		border-radius: 50%;
		background: var(--card-bg);
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		font-size: 0.82rem;
		font-weight: 800;
		line-height: 1;
	}
	.month-ring small {
		font-size: 0.55rem;
		font-weight: 600;
		opacity: 0.65;
	}
	.nmp-chevron,
	.nmp-card-chevron {
		width: 0.55rem;
		height: 0.55rem;
		border-right: 2px solid color-mix(in oklch, currentColor 55%, transparent);
		border-bottom: 2px solid color-mix(in oklch, currentColor 55%, transparent);
		transform: rotate(45deg);
		transition: transform 0.2s ease;
		flex-shrink: 0;
	}
	.nmp-chevron.open,
	.nmp-card-chevron.open {
		transform: rotate(-135deg);
	}
	.nmp-body {
		padding: 0 0.85rem 0.85rem;
		border-top: 1px solid color-mix(in oklch, var(--color-primary) 15%, transparent);
	}
	.nmp-alert {
		margin: 0.65rem 0 0;
		padding: 0.45rem 0.6rem;
		border-radius: 0.5rem;
		font-size: 0.76rem;
		line-height: 1.45;
	}
	.nmp-alert.warn {
		background: color-mix(in oklch, #f59e0b 12%, transparent);
		color: color-mix(in oklch, #b45309 85%, currentColor);
	}
	.nmp-alert.ok {
		background: color-mix(in oklch, #10b981 10%, transparent);
		color: color-mix(in oklch, #047857 85%, currentColor);
	}
	.nmp-mix-bar {
		display: flex;
		height: 0.35rem;
		border-radius: 999px;
		overflow: hidden;
		margin-top: 0.65rem;
		background: color-mix(in oklch, currentColor 8%, transparent);
	}
	.mix-seg {
		min-width: 4px;
		transition: flex 0.3s ease;
	}
	.mix-learn {
		background: #3b82f6;
	}
	.mix-practice {
		background: #f59e0b;
	}
	.mix-deliverable {
		background: #10b981;
	}
	.nmp-mix-legend {
		display: flex;
		flex-wrap: wrap;
		gap: 0.65rem;
		margin: 0.35rem 0 0.65rem;
		font-size: 0.68rem;
		color: color-mix(in oklch, currentColor 58%, transparent);
	}
	.nmp-mix-legend .dot {
		display: inline-block;
		width: 0.45rem;
		height: 0.45rem;
		border-radius: 50%;
		margin-right: 0.2rem;
		vertical-align: middle;
	}
	.nmp-mix-legend .dot.learn {
		background: #3b82f6;
	}
	.nmp-mix-legend .dot.practice {
		background: #f59e0b;
	}
	.nmp-mix-legend .dot.deliverable {
		background: #10b981;
	}
	.nmp-cards {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.nmp-card {
		border-radius: 0.65rem;
		border: 1px solid color-mix(in oklch, currentColor 10%, transparent);
		background: color-mix(in oklch, var(--card-bg) 92%, transparent);
		overflow: hidden;
		transition: box-shadow 0.2s ease;
	}
	.nmp-card.open {
		box-shadow: 0 4px 14px color-mix(in oklch, var(--color-primary) 12%, transparent);
	}
	.nmp-card-head {
		width: 100%;
		display: flex;
		align-items: center;
		gap: 0.55rem;
		padding: 0.55rem 0.65rem;
		border: none;
		background: transparent;
		cursor: pointer;
		text-align: left;
		color: inherit;
	}
	.nmp-focus-icon {
		flex-shrink: 0;
		width: 1.65rem;
		height: 1.65rem;
		border-radius: 0.45rem;
		display: grid;
		place-items: center;
		font-size: 0.78rem;
		font-weight: 800;
	}
	.nmp-card-title-wrap {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
	}
	.nmp-card-title-wrap strong {
		font-size: 0.84rem;
	}
	.nmp-card-title-wrap small {
		font-size: 0.68rem;
		color: color-mix(in oklch, currentColor 52%, transparent);
	}
	.nmp-card-body {
		padding: 0 0.65rem 0.65rem;
		border-top: 1px dashed color-mix(in oklch, currentColor 12%, transparent);
	}
	.nmp-milestone-box {
		margin-top: 0.55rem;
		padding: 0.5rem 0.6rem;
		border-radius: 0.5rem;
		background: color-mix(in oklch, var(--color-primary) 6%, transparent);
	}
	.nmp-milestone-tag {
		display: inline-block;
		font-size: 0.65rem;
		font-weight: 700;
		padding: 0.08rem 0.35rem;
		border-radius: 0.3rem;
		background: color-mix(in oklch, var(--color-primary) 18%, transparent);
		color: color-mix(in oklch, var(--color-primary) 90%, currentColor);
		margin-bottom: 0.25rem;
	}
	.nmp-milestone-box p {
		margin: 0;
		font-size: 0.78rem;
		line-height: 1.45;
	}
	.nmp-growth {
		margin-top: 0.5rem;
	}
	.nmp-action-list {
		list-style: none;
		margin: 0.55rem 0 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}
	.nmp-action-row {
		width: 100%;
		display: flex;
		align-items: flex-start;
		gap: 0.45rem;
		padding: 0.45rem 0.5rem;
		border-radius: 0.5rem;
		border: 1px solid color-mix(in oklch, currentColor 8%, transparent);
		background: color-mix(in oklch, var(--btn-regular-bg) 40%, transparent);
		cursor: pointer;
		text-align: left;
		color: inherit;
		transition:
			background 0.15s ease,
			opacity 0.15s ease;
	}
	.nmp-action-row:hover {
		background: color-mix(in oklch, var(--color-primary) 8%, var(--btn-regular-bg));
	}
	.nmp-action-row.done {
		opacity: 0.62;
	}
	.nmp-action-row.done .nmp-action-text {
		text-decoration: line-through;
	}
	.nmp-check {
		flex-shrink: 0;
		width: 1.1rem;
		height: 1.1rem;
		border-radius: 0.3rem;
		border: 1.5px solid color-mix(in oklch, var(--color-primary) 45%, transparent);
		display: grid;
		place-items: center;
		font-size: 0.65rem;
		font-weight: 800;
		color: white;
		margin-top: 0.1rem;
		transition:
			background 0.15s ease,
			border-color 0.15s ease;
	}
	.nmp-check.checked {
		background: var(--color-primary);
		border-color: var(--color-primary);
	}
	.nmp-action-text {
		flex: 1;
		font-size: 0.76rem;
		line-height: 1.45;
	}
	.action-kind.kind-learn,
	.action-kind.kind-practice,
	.action-kind.kind-deliverable {
		background: color-mix(in oklch, var(--kind-color) 14%, transparent);
		color: color-mix(in oklch, var(--kind-color) 88%, currentColor);
	}
	.nmp-ref-deck {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.35rem;
		margin-top: 0.55rem;
	}
	.nmp-ref-label {
		font-size: 0.68rem;
		font-weight: 600;
		color: color-mix(in oklch, currentColor 55%, transparent);
	}
	.nmp-ref-pill {
		font-size: 0.72rem;
		padding: 0.2rem 0.55rem;
		border-radius: 999px;
		border: 1px solid color-mix(in oklch, var(--color-primary) 30%, transparent);
		background: color-mix(in oklch, var(--color-primary) 8%, transparent);
		color: color-mix(in oklch, var(--color-primary) 90%, currentColor);
		text-decoration: none;
	}
	.nmp-ref-pill.muted {
		border-color: color-mix(in oklch, currentColor 12%, transparent);
		background: color-mix(in oklch, currentColor 6%, transparent);
		color: color-mix(in oklch, currentColor 70%, transparent);
	}
	.next-month-plan-banner h5 {
		margin: 0 0 0.5rem;
		font-size: 0.88rem;
	}
	.next-month-plan-banner .meta.warn {
		color: color-mix(in oklch, #d97706 85%, currentColor);
	}
	.next-month-plan-banner .meta.ok-hint {
		color: color-mix(in oklch, #059669 75%, currentColor);
	}
	.plan-items.compact {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.phase-liner {
		font-size: 0.82rem;
		color: color-mix(in oklch, var(--color-primary) 75%, currentColor);
		margin: 0.2rem 0 0.75rem;
		line-height: 1.45;
	}
	.plan-block-section {
		margin-top: 0.45rem;
	}
	.plan-block-section .section-label {
		font-size: 0.72rem;
		font-weight: 600;
		margin: 0 0 0.25rem;
		color: color-mix(in oklch, currentColor 70%, transparent);
	}
	.plan-block-section.custom .section-label {
		color: color-mix(in oklch, var(--color-primary) 80%, currentColor);
	}
	ul.custom-actions {
		margin: 0;
		padding-left: 1.1rem;
		font-size: 0.78rem;
		line-height: 1.45;
	}
	.growth-rationale {
		margin: 0.45rem 0 0.35rem;
		padding: 0.5rem 0.65rem;
		border-radius: 0.55rem;
		font-size: 0.76rem;
		line-height: 1.5;
		color: color-mix(in oklch, currentColor 72%, transparent);
		background: color-mix(in oklch, var(--color-primary) 8%, var(--card-bg));
		border-left: 3px solid color-mix(in oklch, var(--color-primary) 55%, transparent);
	}
	.action-checklist li {
		margin-bottom: 0.35rem;
		list-style: none;
		padding-left: 0;
	}
	ul.action-checklist {
		padding-left: 0;
	}
	.action-kind {
		display: inline-block;
		min-width: 2.2rem;
		margin-right: 0.35rem;
		padding: 0.1rem 0.35rem;
		border-radius: 0.35rem;
		font-size: 0.68rem;
		font-weight: 700;
		color: color-mix(in oklch, var(--color-primary) 90%, currentColor);
		background: color-mix(in oklch, var(--color-primary) 12%, transparent);
		vertical-align: baseline;
	}
	.ref-why {
		display: block;
		font-size: 0.72rem;
		color: color-mix(in oklch, currentColor 52%, transparent);
		margin-top: 0.15rem;
	}
	.resource-deck {
		padding: 0.85rem;
		border-radius: 0.85rem;
		border: 1px solid color-mix(in oklch, currentColor 10%, transparent);
		background: color-mix(in oklch, var(--card-bg) 96%, transparent);
	}
	.resource-deck h5 {
		margin: 0 0 0.65rem;
		font-size: 0.88rem;
		font-weight: 700;
	}
	.rec-card.rich .rec-desc {
		font-size: 0.76rem;
		color: color-mix(in oklch, currentColor 58%, transparent);
		margin: 0.35rem 0;
		line-height: 1.45;
	}
	.gap-legend {
		font-size: 0.78rem;
		color: color-mix(in oklch, currentColor 72%, transparent);
		line-height: 1.5;
		margin: 0 0 0.4rem;
	}
	.gap-legend-keys {
		margin: 0 0 0.55rem;
		padding-left: 1.1rem;
		font-size: 0.72rem;
		color: color-mix(in oklch, currentColor 58%, transparent);
		line-height: 1.45;
	}
	.gap-legend-keys li {
		margin: 0.12rem 0;
	}
	.gap-table {
		--gap-cols: minmax(2rem, 1.1fr) repeat(3, minmax(1.55rem, 0.82fr)) minmax(0, 1.6fr);
		width: 100%;
		max-width: 100%;
		min-width: 0;
		margin-bottom: 0.85rem;
		font-size: 0.72rem;
	}
	.gap-table-head,
	.gap-table-row {
		display: grid;
		grid-template-columns: var(--gap-cols);
		column-gap: 0.35rem;
		align-items: center;
		min-width: 0;
		width: 100%;
		box-sizing: border-box;
	}
	.gap-table-head {
		font-size: 0.65rem;
		font-weight: 600;
		color: color-mix(in oklch, currentColor 55%, transparent);
		padding-bottom: 0.3rem;
		margin-bottom: 0.15rem;
		border-bottom: 1px solid color-mix(in oklch, currentColor 10%, transparent);
	}
	.gap-table-row {
		padding: 0.4rem 0;
		border-bottom: 1px solid color-mix(in oklch, currentColor 8%, transparent);
	}
	.gap-table-head > *,
	.gap-table-row > * {
		min-width: 0;
	}
	.gap-table .col-dim {
		text-align: left;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.gap-table .col-num {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}
	.gap-table-head .col-num,
	.gap-table-head .col-gap {
		text-align: right;
	}
	.gap-gap-cell {
		display: flex;
		flex-direction: row;
		align-items: center;
		gap: 0.3rem;
		min-width: 0;
		overflow: hidden;
	}
	.gap-gap-cell .bar-track {
		flex: 1 1 0;
		min-width: 0;
	}
	.gap-gap-cell .pts {
		flex: 0 0 auto;
		font-size: 0.65rem;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
	.gap-gap-cell .status-tag {
		flex: 0 0 auto;
		margin-top: 0;
		max-width: 3.2rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.insight-embed-panel .gap-table {
		--gap-cols: 2rem 1.5rem 1.5rem 1.65rem minmax(0, 1fr);
		font-size: 0.68rem;
	}
	.insight-embed-panel .gap-gap-cell .status-tag {
		font-size: 0.58rem;
		padding: 0.05rem 0.25rem;
		max-width: 2.6rem;
	}
	.gap-bars {
		display: flex;
		flex-direction: column;
		gap: 0.45rem;
		margin-bottom: 0.85rem;
	}
	.bar-track {
		height: 0.45rem;
		background: color-mix(in oklch, currentColor 10%, transparent);
		border-radius: 4px;
		overflow: hidden;
	}
	.bar.gap {
		height: 100%;
		border-radius: 4px;
		min-width: 2px;
	}
	.bar.gap.job {
		background: linear-gradient(90deg, #f59e0b, #ef4444);
	}
	.status-tag {
		font-size: 0.62rem;
		align-self: flex-start;
		padding: 0.1rem 0.35rem;
		border-radius: 4px;
		margin-top: 0.1rem;
	}
	.status-deficit {
		background: color-mix(in oklch, #ef4444 18%, transparent);
		color: #b91c1c;
	}
	.status-met {
		background: color-mix(in oklch, #22c55e 15%, transparent);
		color: #15803d;
	}
	.status-lead {
		background: color-mix(in oklch, var(--primary) 18%, transparent);
		color: var(--primary);
	}
	.metric-desc {
		margin-bottom: 0.15rem;
	}
	.baseline-hint {
		color: color-mix(in oklch, var(--primary) 75%, transparent);
	}
	.plan-item .meta {
		font-size: 0.68rem;
		color: color-mix(in oklch, currentColor 58%, transparent);
	}
	.stack-desc {
		display: grid;
		gap: 0.22rem;
	}
	.stack-desc .sub {
		font-size: 0.7rem;
		font-weight: 600;
	}
	.stack-desc .meta {
		font-size: 0.68rem;
		color: color-mix(in oklch, currentColor 58%, transparent);
	}
	.line-picker {
		margin-top: 0.75rem;
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}
	.line-card {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		border: 1px solid color-mix(in oklch, currentColor 14%, transparent);
		padding: 0.38rem 0.62rem;
		border-radius: 0.75rem;
		font-size: 0.76rem;
		text-align: left;
		max-width: 100%;
		cursor: pointer;
		background: color-mix(in oklch, var(--btn-regular-bg) 82%, transparent);
		transition:
			border-color 0.15s ease,
			background 0.15s ease;
	}
	.line-card:hover {
		border-color: color-mix(in oklch, var(--primary) 45%, transparent);
	}
	.line-card.active {
		border-color: color-mix(in oklch, var(--primary) 72%, white);
		background: color-mix(in oklch, var(--primary) 14%, transparent);
	}
	.line-card-name {
		max-width: 14rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.swatch {
		width: 0.55rem;
		height: 0.55rem;
		border-radius: 999px;
	}
	.line-canvas-wrap {
		position: relative;
		margin-top: 0.8rem;
		border-radius: 0.9rem;
		padding: 0.65rem;
		background: color-mix(in oklch, var(--btn-regular-bg) 78%, transparent);
	}
	.line-canvas-wrap.embedded {
		margin-top: 0.5rem;
		padding: 0.45rem;
	}
	.line-canvas-wrap--zoom {
		margin-top: 0.65rem;
		padding: 0.85rem 1rem 1rem;
	}
	.canvas-zoom-btn {
		position: absolute;
		top: 0.45rem;
		right: 0.45rem;
		z-index: 2;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 2rem;
		height: 2rem;
		border: 1px solid color-mix(in oklch, currentColor 14%, transparent);
		border-radius: 0.55rem;
		background: color-mix(in oklch, var(--card-bg) 92%, transparent);
		color: color-mix(in oklch, currentColor 72%, transparent);
		cursor: pointer;
		transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
	}
	.canvas-zoom-btn:hover {
		background: color-mix(in oklch, var(--primary) 12%, var(--card-bg));
		color: color-mix(in oklch, var(--primary) 85%, black);
		border-color: color-mix(in oklch, var(--primary) 28%, transparent);
	}
	.canvas-zoom-backdrop {
		position: fixed;
		inset: 0;
		z-index: 220;
		display: flex;
		align-items: flex-start;
		justify-content: center;
		overflow-y: auto;
		padding: 4rem 1rem 1.5rem;
		background: color-mix(in oklch, black 45%, transparent);
	}
	.canvas-zoom-backdrop-hit {
		position: absolute;
		inset: 0;
		border: none;
		background: transparent;
		cursor: default;
	}
	.canvas-zoom-panel {
		position: relative;
		z-index: 1;
		width: min(100%, 980px);
		border-radius: 1rem;
		border: 1px solid color-mix(in oklch, currentColor 12%, transparent);
		background: var(--page-bg);
		padding: 1rem 1.1rem 1.15rem;
		box-shadow: 0 24px 48px color-mix(in oklch, black 22%, transparent);
	}
	.canvas-zoom-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
	}
	.canvas-zoom-head h3 {
		margin: 0;
		font-size: 1rem;
		font-weight: 700;
	}
	.canvas-zoom-close {
		border: 1px solid color-mix(in oklch, currentColor 14%, transparent);
		border-radius: 0.55rem;
		background: color-mix(in oklch, var(--btn-regular-bg) 88%, transparent);
		padding: 0.28rem 0.65rem;
		font-size: 0.78rem;
		cursor: pointer;
	}
	.canvas-zoom-hint {
		margin-top: 0.45rem;
	}
	.line-canvas--dense .axis-num {
		font-size: 9px;
	}
	.canvas-panel .line-canvas-wrap.embedded {
		margin-top: 0.35rem;
	}
	.canvas-panel-hint {
		font-size: 0.72rem;
		color: color-mix(in oklch, currentColor 55%, transparent);
		margin: 0.25rem 0 0;
		line-height: 1.4;
	}
	.timeline-detail-panel.compact,
	.canvas-side-cards.compact {
		margin-top: 0.55rem;
		font-size: 0.78rem;
	}
	.timeline-detail-panel.compact .timeline-detail-head h4 {
		font-size: 0.82rem;
	}
	.narrative-badge {
		display: inline-block;
		font-size: 0.68rem;
		font-weight: 600;
		padding: 0.12rem 0.45rem;
		border-radius: 999px;
		margin-bottom: 0.35rem;
		background: color-mix(in oklch, var(--primary) 18%, transparent);
		color: color-mix(in oklch, var(--primary) 85%, black);
	}
	.line-canvas {
		width: 100%;
		height: auto;
		display: block;
	}
	.canvas-side-cards {
		margin-top: 0.85rem;
		display: grid;
		gap: 0.65rem;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr));
		align-items: start;
	}
	.canvas-side-cards.full-width {
		margin-top: 0;
		grid-template-columns: 1fr;
	}
	.insight-mini-card {
		min-width: 0;
		border: 1px solid color-mix(in oklch, currentColor 12%, transparent);
		border-radius: 0.85rem;
		padding: 0.65rem 0.72rem;
		background: color-mix(in oklch, var(--card-bg) 96%, transparent);
		display: grid;
		gap: 0.45rem;
	}
	.insight-mini-card-title {
		margin: 0;
		font-size: 0.84rem;
		font-weight: 700;
	}
	.grid-line {
		stroke: color-mix(in oklch, currentColor 10%, transparent);
		stroke-width: 1;
	}
	.axis-main {
		stroke: color-mix(in oklch, currentColor 22%, transparent);
		stroke-width: 1.2;
	}
	.axis-tick {
		stroke: color-mix(in oklch, currentColor 18%, transparent);
		stroke-width: 1;
	}
	.axis-num {
		font-size: 10px;
		fill: color-mix(in oklch, currentColor 52%, transparent);
	}
	.axis-title {
		font-size: 11px;
		font-weight: 600;
		fill: color-mix(in oklch, currentColor 55%, transparent);
	}
	.point-label {
		font-size: 9px;
		fill: color-mix(in oklch, currentColor 48%, transparent);
	}
	.adjust-node {
		cursor: pointer;
	}
	.adjustment-detail {
		padding: 0.48rem 0.55rem;
		border-radius: 0.62rem;
		border-left: 3px solid #d97706;
		background: color-mix(in oklch, #f59e0b 12%, transparent);
		display: grid;
		gap: 0.28rem;
		font-size: 0.75rem;
	}
	.adjustment-detail .title {
		font-weight: 700;
	}
	.adjustment-detail .subhead {
		margin-top: 0.2rem;
		font-weight: 600;
	}
	.adjustment-detail ul {
		list-style: disc;
		padding-left: 1rem;
	}
	.adjustment-hint-list li {
		margin-bottom: 0.25rem;
	}
	.plan-items-merge ul {
		margin: 0.25rem 0 0 1rem;
		padding: 0;
	}
	.hint-ref {
		margin-top: 0.2rem;
		font-size: 0.78rem;
	}
	.hint-ref a {
		color: var(--color-primary);
	}
	.metric-link {
		text-align: left;
		font-size: 0.74rem;
		color: color-mix(in oklch, var(--primary) 78%, black);
		text-decoration: underline;
		text-decoration-style: dotted;
		text-underline-offset: 2px;
	}
	.adjustment-detail .hint {
		font-size: 0.68rem;
		color: color-mix(in oklch, currentColor 58%, transparent);
	}
	.mini-title {
		margin-top: 0.7rem;
		margin-bottom: 0.35rem;
		font-size: 0.78rem;
		font-weight: 700;
	}
	.track-chart,
	.trend-chart {
		display: grid;
		gap: 0.5rem;
	}
	.track-overview,
	.trend-overview {
		margin-bottom: 0.45rem;
		padding: 0.45rem 0.55rem;
		border-radius: 0.62rem;
		background: color-mix(in oklch, var(--btn-regular-bg) 72%, transparent);
		border-left: 3px solid color-mix(in oklch, var(--primary) 70%, white);
		display: grid;
		gap: 0.2rem;
	}
	.trend-overview .summary {
		font-size: 0.75rem;
		font-weight: 600;
	}
	.trend-overview .meta {
		font-size: 0.68rem;
		color: color-mix(in oklch, currentColor 58%, transparent);
	}
	.track-meta-note,
	.trend-meta-note {
		margin-bottom: 0.35rem;
		font-size: 0.68rem;
		color: color-mix(in oklch, currentColor 58%, transparent);
	}
	.track-row,
	.trend-row {
		padding: 0.45rem 0.5rem;
		border-radius: 0.65rem;
		background: color-mix(in oklch, var(--btn-regular-bg) 70%, transparent);
	}
	.track-name,
	.trend-name {
		font-size: 0.75rem;
		font-weight: 600;
		margin-bottom: 0.25rem;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.track-bars,
	.trend-bars {
		display: grid;
		gap: 0.2rem;
	}
	.track-text,
	.trend-text {
		margin-top: 0.25rem;
		font-size: 0.68rem;
		color: color-mix(in oklch, currentColor 60%, transparent);
		line-height: 1.4;
	}
	.bar-item {
		display: grid;
		grid-template-columns: 2.2rem minmax(0, 1fr);
		gap: 0.35rem;
		align-items: center;
		font-size: 0.68rem;
	}
	.track-bars .bar-item {
		grid-template-columns: 4.5rem minmax(0, 1fr) 1.8rem;
	}
	.bar-score {
		text-align: right;
		font-variant-numeric: tabular-nums;
		font-size: 0.65rem;
		color: color-mix(in oklch, currentColor 55%, transparent);
	}
	.track-detail.meta {
		margin-top: 0.15rem;
		font-size: 0.65rem;
	}
	.track-legend-keys {
		margin: 0 0 0.65rem;
		padding-left: 1.1rem;
		font-size: 0.72rem;
		color: color-mix(in oklch, currentColor 58%, transparent);
		line-height: 1.45;
	}
	.track-legend-keys li {
		margin: 0.12rem 0;
	}
	.track-meta-note {
		font-size: 0.68rem;
		color: color-mix(in oklch, currentColor 55%, transparent);
		margin: 0 0 0.45rem;
		line-height: 1.4;
	}
	.public-info-block {
		margin-top: 0.45rem;
		padding-top: 0.4rem;
		border-top: 1px dashed color-mix(in oklch, currentColor 12%, transparent);
	}
	.public-info-btn {
		font-size: 0.72rem;
		padding: 0.35rem 0.55rem;
	}
	.public-info-summary {
		margin: 0.35rem 0 0;
		font-size: 0.72rem;
		line-height: 1.45;
	}
	.public-info-sources {
		margin: 0.25rem 0 0;
		padding-left: 1rem;
		font-size: 0.68rem;
	}
	.public-info-sources a {
		color: color-mix(in oklch, var(--primary) 85%, currentColor);
		word-break: break-all;
	}
	.public-info-meta {
		margin-top: 0.2rem;
		font-size: 0.62rem;
	}
	.bar.hiring {
		background: #3b82f6;
	}
	.bar.path {
		background: #10b981;
	}
	.bar.resource {
		background: #8b5cf6;
	}
	.bar-track {
		height: 0.45rem;
		border-radius: 999px;
		background: color-mix(in oklch, currentColor 8%, transparent);
		overflow: hidden;
	}
	.bar {
		height: 100%;
		border-radius: 999px;
	}
	.bar.demand {
		background: #3b82f6;
	}
	.bar.growth {
		background: #10b981;
	}
	.bar.risk {
		background: #f59e0b;
	}
	.heatmap {
		overflow: auto;
		display: grid;
		gap: 0.24rem;
	}
	.heat-header,
	.heat-row {
		display: grid;
		grid-template-columns: 6.4rem repeat(5, minmax(2.5rem, 1fr));
		gap: 0.2rem;
	}
	.heat-header span {
		font-size: 0.68rem;
		color: color-mix(in oklch, currentColor 55%, transparent);
	}
	.job-cell,
	.gap-cell {
		padding: 0.22rem 0.3rem;
		border-radius: 0.42rem;
		font-size: 0.68rem;
	}
	.job-cell {
		background: color-mix(in oklch, currentColor 8%, transparent);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.gap-cell {
		text-align: center;
		font-variant-numeric: tabular-nums;
	}
	.metric-list {
		display: grid;
		gap: 0.36rem;
	}
	.metric-item {
		padding: 0.38rem 0.45rem;
		border-radius: 0.58rem;
		background: color-mix(in oklch, var(--btn-regular-bg) 70%, transparent);
	}
	.metric-item.metric-highlight {
		outline: 1px solid color-mix(in oklch, var(--primary) 70%, transparent);
		background: color-mix(in oklch, var(--primary) 14%, transparent);
	}
	.metric-item p {
		font-size: 0.74rem;
	}
	.metric-item .meta {
		font-size: 0.68rem;
		color: color-mix(in oklch, currentColor 55%, transparent);
	}
	.review-form {
		display: grid;
		gap: 0.45rem;
	}
	.review-form label {
		display: grid;
		gap: 0.2rem;
	}
	.review-form label span {
		font-size: 0.7rem;
		color: color-mix(in oklch, currentColor 55%, transparent);
	}
	.review-textarea-block {
		display: grid;
		gap: 0.35rem;
	}
	.review-textarea-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.review-textarea-label {
		font-size: 0.72rem;
		font-weight: 600;
		color: color-mix(in oklch, currentColor 72%, transparent);
	}
	.review-textarea-hint {
		margin: 0;
		font-size: 0.66rem;
		line-height: 1.45;
		color: color-mix(in oklch, currentColor 52%, transparent);
	}
	.template-btn {
		flex-shrink: 0;
		border-radius: 999px;
		padding: 0.28rem 0.65rem;
		font-size: 0.68rem;
		font-weight: 600;
		border: 1px solid color-mix(in oklch, var(--primary) 45%, transparent);
		background: color-mix(in oklch, var(--primary) 12%, transparent);
		color: color-mix(in oklch, var(--primary) 85%, black);
		cursor: pointer;
		transition:
			background 0.15s ease,
			border-color 0.15s ease;
	}
	.template-btn:hover {
		background: color-mix(in oklch, var(--primary) 20%, transparent);
		border-color: color-mix(in oklch, var(--primary) 55%, transparent);
	}
	.review-textarea-shell {
		border-radius: 0.85rem;
		padding: 1px;
		background: linear-gradient(
			135deg,
			color-mix(in oklch, var(--primary) 55%, transparent),
			color-mix(in oklch, currentColor 14%, transparent)
		);
		box-shadow:
			0 1px 2px color-mix(in oklch, currentColor 8%, transparent),
			0 8px 24px -12px color-mix(in oklch, var(--primary) 35%, transparent);
	}
	.review-textarea-input {
		display: block;
		width: 100%;
		min-height: 7.5rem;
		resize: vertical;
		border: none;
		border-radius: calc(0.85rem - 1px);
		padding: 0.65rem 0.72rem;
		font-size: 0.8rem;
		line-height: 1.65;
		background: color-mix(in oklch, var(--card-bg) 96%, var(--btn-regular-bg));
		color: inherit;
		transition:
			box-shadow 0.18s ease,
			background 0.18s ease;
	}
	.review-textarea-input::placeholder {
		color: color-mix(in oklch, currentColor 48%, transparent);
		font-size: 0.76rem;
		line-height: 1.55;
	}
	.review-textarea-input:hover {
		background: color-mix(in oklch, var(--card-bg) 92%, var(--btn-regular-bg));
	}
	.review-textarea-input:focus {
		outline: none;
		box-shadow: inset 0 0 0 1px color-mix(in oklch, var(--primary) 35%, transparent);
		background: var(--btn-regular-bg);
	}
	.m3-rhythm-note {
		margin: 0 0 0.35rem;
		font-size: 0.68rem;
		line-height: 1.45;
		color: color-mix(in oklch, currentColor 58%, transparent);
	}
	.m3-rhythm-note strong {
		color: color-mix(in oklch, var(--primary) 78%, currentColor);
		font-weight: 700;
	}
	.hit-review-point {
		cursor: pointer;
	}
	.hit-review-point:focus {
		outline: none;
	}
	.hit-review-point.selected circle:last-of-type {
		stroke: color-mix(in oklch, currentColor 35%, white);
		stroke-width: 2.5;
	}
	.timeline-detail-panel {
		margin-top: 0.55rem;
		padding: 0.55rem 0.62rem;
		border-radius: 0.65rem;
		border-left: 3px solid color-mix(in oklch, var(--primary) 65%, white);
		background: color-mix(in oklch, var(--btn-regular-bg) 78%, transparent);
		display: grid;
		gap: 0.35rem;
		font-size: 0.76rem;
	}
	.timeline-detail-head {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 0.5rem;
		font-weight: 700;
		font-size: 0.78rem;
	}
	.timeline-detail-head h4 {
		margin: 0;
		font-size: inherit;
		font-weight: inherit;
		line-height: 1.35;
		flex: 1;
		min-width: 0;
	}
	.detail-pass {
		margin: 0;
		font-variant-numeric: tabular-nums;
		color: color-mix(in oklch, currentColor 78%, transparent);
	}
	.detail-block {
		margin: 0;
		line-height: 1.55;
	}
	.detail-block .sub {
		display: block;
		font-size: 0.66rem;
		font-weight: 600;
		color: color-mix(in oklch, currentColor 55%, transparent);
		margin-bottom: 0.15rem;
	}
	.detail-block .pre {
		display: block;
		white-space: pre-wrap;
		font-size: 0.72rem;
		color: color-mix(in oklch, currentColor 82%, transparent);
	}
	.review-trend {
		border: 1px dashed color-mix(in oklch, currentColor 14%, transparent);
		border-radius: 0.65rem;
		padding: 0.3rem;
	}
	.review-trend svg {
		width: 100%;
		height: auto;
		display: block;
	}
	.review-trend .axis {
		stroke: color-mix(in oklch, currentColor 20%, transparent);
		stroke-width: 1;
	}
	.review-trend .pt {
		font-size: 9px;
		fill: color-mix(in oklch, currentColor 60%, transparent);
	}
	.latest-review {
		padding: 0.45rem 0.55rem;
		border-radius: 0.62rem;
		background: color-mix(in oklch, var(--btn-regular-bg) 70%, transparent);
		display: grid;
		gap: 0.28rem;
		font-size: 0.75rem;
	}
	.review-text {
		white-space: pre-wrap;
		line-height: 1.5;
		color: color-mix(in oklch, currentColor 82%, transparent);
	}
	.meta-line {
		font-size: 0.72rem;
		color: color-mix(in oklch, currentColor 60%, transparent);
	}
	.auto-adjust {
		border-left: 3px solid color-mix(in oklch, #f59e0b 68%, white);
		padding-left: 0.45rem;
		display: grid;
		gap: 0.2rem;
	}
	.auto-adjust ul {
		list-style: disc;
		padding-left: 1rem;
	}
	.empty-canvas,
	.empty-side {
		min-height: 13rem;
		display: grid;
		place-items: center;
		border-radius: 0.8rem;
		border: 1px dashed color-mix(in oklch, currentColor 16%, transparent);
		color: color-mix(in oklch, currentColor 56%, transparent);
		font-size: 0.82rem;
	}
	.focus-strip {
		display: flex;
		flex-wrap: wrap;
		gap: 0.7rem;
		padding: 0.55rem 0.8rem;
		border-radius: 0.8rem;
		background: color-mix(in oklch, var(--primary) 10%, transparent);
		font-size: 0.78rem;
	}
	.msg {
		font-size: 0.84rem;
	}
	.msg.error {
		color: #dc2626;
	}
	.msg.ok {
		color: #059669;
	}
	@media (max-width: 1280px) {
		.report-grid {
			grid-template-columns: 300px minmax(0, 1fr);
		}
	}
	@media (max-width: 900px) {
		.report-grid {
			grid-template-columns: 1fr;
		}
		.control-rail {
			position: static;
			max-height: none;
			overflow: visible;
		}
		.heat-header,
		.heat-row {
			grid-template-columns: 5.3rem repeat(5, minmax(2.1rem, 1fr));
		}
		.planning-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
