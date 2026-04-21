<script lang="ts">
	import { onMount } from "svelte";
	import { fetchMyResumes, type MyResumeSummary } from "@/lib/match";
	import {
		fetchCareerReportDetail,
		fetchMyCareerReports,
		fetchReportReviews,
		generateCareerReport,
		importTargetsFromMatch,
		manualSearchTargets,
		type CareerReportPayload,
		type CareerReportHistoryItem,
		type ReportReviewItem,
		type ReportTargetItem,
		type TimelinePoint,
		submitReportReviewCycle,
	} from "@/lib/report";

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
		short_term: "短期",
		mid_term: "中期",
		target: "目标岗位",
	};
	const LINE_COLORS = ["#3b82f6", "#8b5cf6", "#10b981", "#f59e0b", "#ef4444"];

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

	let resumes = $state<MyResumeSummary[]>([]);
	let selectedResumeId = $state<number | "">("");
	let matchGoal = $state<"fit" | "stretch">("fit");
	let loadingImport = $state(false);
	let loadingSearch = $state(false);
	let loadingGenerate = $state(false);
	let error = $state("");
	let info = $state("");

	let searchQ = $state("");
	let searchLocation = $state("");

	let selectedTargets = $state<ReportTargetItem[]>([]);
	let searchedTargets = $state<ReportTargetItem[]>([]);
	let generatedReportId = $state<number | null>(null);
	let generatedReport = $state<CareerReportPayload | null>(null);
	let reportHistory = $state<CareerReportHistoryItem[]>([]);
	let reviewHistory = $state<ReportReviewItem[]>([]);
	let selectedHistoryReportId = $state<number | "">("");
	let focusLineId = $state("");
	let selectedAdjustmentId = $state("");
	let highlightedMetricCode = $state("");
	let selectedTimelineReviewId = $state<number | null>(null);
	let submittingReview = $state(false);
	let reviewError = $state("");
	let reviewInfo = $state("");
	let reviewText = $state("");

	const focusTarget = $derived.by(() => {
		if (!generatedReport?.targets?.length) return null;
		if (!focusLineId) return generatedReport.targets[0] || null;
		const line = generatedReport.development_lines.lines.find((x) => x.line_id === focusLineId);
		if (!line) return generatedReport.targets[0] || null;
		return generatedReport.targets.find((x) => x.id === line.target_job_id) || generatedReport.targets[0] || null;
	});

	const trendRows = $derived.by(() => generatedReport?.targets || []);
	const maxTrend = $derived.by(() => {
		const values = trendRows.flatMap((row) => [
			row.trend.demand_index_0_100,
			row.trend.growth_signal_0_100,
			row.trend.volatility_0_100,
		]);
		return values.length ? Math.max(...values) : 100;
	});

	const heatmapDimensions = $derived.by(() => {
		if (!generatedReport?.targets?.length) return [];
		const sum: Record<string, number> = {};
		for (const t of generatedReport.targets) {
			const gaps = t.match_preview.dimension_gaps || {};
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
			for (const v of Object.values(t.match_preview.dimension_gaps || {})) {
				max = Math.max(max, Number(v || 0));
			}
		}
		return max;
	});

	const lineNodes = $derived.by(() => generatedReport?.development_lines.lines || []);
	const activeLineId = $derived.by(() => focusLineId || lineNodes[0]?.line_id || "");

	const CHART = { w: 700, h: 300, l: 50, r: 18, t: 26, b: 46 };

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
			yLabel: ax?.y_label ?? "进步度",
		};
	}

	function scalePoint(month: number, progress: number): { x: number; y: number } {
		const ax = chartAxis();
		const pw = CHART.w - CHART.l - CHART.r;
		const ph = CHART.h - CHART.t - CHART.b;
		const xr = ax.xMax - ax.xMin || 1;
		const yr = ax.yMax - ax.yMin || 1;
		const x = CHART.l + ((Number(month) - ax.xMin) / xr) * pw;
		const y = CHART.t + ph - ((Number(progress) - ax.yMin) / yr) * ph;
		return { x, y };
	}

	const chartLayout = $derived.by(() => {
		const ax = chartAxis();
		const pw = CHART.w - CHART.l - CHART.r;
		const ph = CHART.h - CHART.t - CHART.b;
		return { ax, pw, ph };
	});

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

	function adjChartPoint(adj: (typeof adjustmentNodes)[number]): { x: number; y: number } {
		const m = typeof adj.month === "number" ? adj.month : stageToMonth(String(adj.stage));
		const p = typeof adj.progress === "number" ? adj.progress : 52;
		return scalePoint(m, p);
	}

	function timelinePolylineString(): string {
		return activeTimeline
			.map((t) => {
				const p = scalePoint(t.month, t.progress);
				return `${p.x},${p.y}`;
			})
			.join(" ");
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

	const trendOverview = $derived.by(() => {
		if (!trendRows.length) return null;
		const demandAvg = trendRows.reduce((acc, row) => acc + Number(row.trend.demand_index_0_100 || 0), 0) / trendRows.length;
		const growthAvg = trendRows.reduce((acc, row) => acc + Number(row.trend.growth_signal_0_100 || 0), 0) / trendRows.length;
		const volatilityAvg =
			trendRows.reduce((acc, row) => acc + Number(row.trend.volatility_0_100 || 0), 0) / trendRows.length;
		const stable = volatilityAvg <= 45 ? "较稳" : volatilityAvg <= 65 ? "中等波动" : "波动偏高";
		const tone =
			demandAvg >= 70 && growthAvg >= 70
				? "整体处于高需求+高增长区间，可优先推进投递与项目沉淀。"
				: demandAvg >= 60
					? "整体需求尚可，建议优先选择增长信号更高的方向集中投入。"
					: "需求强度一般，建议强化差异化成果并动态调整主攻目标。";
		return {
			demandAvg: Math.round(demandAvg * 10) / 10,
			growthAvg: Math.round(growthAvg * 10) / 10,
			volatilityAvg: Math.round(volatilityAvg * 10) / 10,
			stable,
			tone,
		};
	});

	function trendLevelText(v: number): string {
		if (v >= 80) return "高";
		if (v >= 60) return "中";
		return "低";
	}

	function trendInterpretation(row: (typeof trendRows)[number]): string {
		if (row?.trend?.analysis_text) return String(row.trend.analysis_text);
		const d = Number(row.trend.demand_index_0_100 || 0);
		const g = Number(row.trend.growth_signal_0_100 || 0);
		const v = Number(row.trend.volatility_0_100 || 0);
		const core =
			d >= 70 && g >= 70
				? "岗位机会充足且成长空间较好"
				: d >= 60
					? "岗位机会尚可"
					: "岗位机会偏有限";
		const risk = v >= 70 ? "但波动较高，建议保留备选路径" : v >= 50 ? "，需持续跟踪市场变化" : "，整体稳定性较好";
		return `${core}${risk}。`;
	}

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

	onMount(async () => {
		resumes = await fetchMyResumes().catch(() => []);
		if (resumes.length) {
			selectedResumeId = resumes[0].id;
		}
		reportHistory = await fetchMyCareerReports(20).catch(() => []);
		if (reportHistory.length) {
			selectedHistoryReportId = reportHistory[0].report_id;
		}
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
	}

	function removeTarget(jobId: string): void {
		selectedTargets = selectedTargets.filter((x) => x.job_id !== jobId);
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
		selectedTimelineReviewId = null;
		const adj = adjustmentNodes.find((x) => x.id === adjustId);
		if (adj?.line_id) {
			focusLineId = adj.line_id;
		}
	}

	function selectTimelineReview(rid: number | undefined): void {
		if (rid == null || Number.isNaN(Number(rid))) return;
		const n = Number(rid);
		selectedAdjustmentId = "";
		selectedTimelineReviewId = selectedTimelineReviewId === n ? null : n;
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

	async function importSmartTargets(): Promise<void> {
		if (selectedResumeId === "") {
			error = "请先选择画像记录。";
			return;
		}
		error = "";
		info = "";
		loadingImport = true;
		try {
			const data = await importTargetsFromMatch({
				resume_id: Number(selectedResumeId),
				match_goal: matchGoal,
				refine_with_llm: true,
				limit: 5,
			});
			selectedTargets = (data?.targets || []).slice(0, 5);
			info = `已导入 ${selectedTargets.length} 个智能推荐目标（来源：${data?.source || "unknown"}）。`;
		} catch (e) {
			error = e instanceof Error ? e.message : "导入智能推荐失败";
		} finally {
			loadingImport = false;
		}
	}

	async function runManualSearch(): Promise<void> {
		if (!searchQ.trim()) {
			error = "请输入岗位关键词。";
			return;
		}
		error = "";
		info = "";
		loadingSearch = true;
		try {
			const data = await manualSearchTargets({
				q: searchQ.trim(),
				location_q: searchLocation.trim(),
				limit: 20,
			});
			searchedTargets = data?.targets || [];
			info = `检索到 ${searchedTargets.length} 个候选岗位。`;
		} catch (e) {
			error = e instanceof Error ? e.message : "手动搜索失败";
		} finally {
			loadingSearch = false;
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
		try {
			const data = await generateCareerReport({
				resume_id: Number(selectedResumeId),
				target_job_ids: selectedTargets.map((x) => x.job_id),
				primary_job_id: selectedTargets[0].job_id,
			});
			generatedReportId = data?.report_id || null;
			generatedReport = data?.report || null;
			selectedTimelineReviewId = null;
			focusLineId = generatedReport?.development_lines?.lines?.[0]?.line_id || "";
			const firstLineId = focusLineId;
			const firstAdjG = (generatedReport?.development_lines?.adjustments || []).find(
				(a) => a.line_id === firstLineId,
			);
			selectedAdjustmentId = firstAdjG?.id || generatedReport?.development_lines?.adjustments?.[0]?.id || "";
			if (generatedReportId) {
				await loadReviewsForReport(generatedReportId);
			}
			info = generatedReportId ? `报告生成成功，ID: ${generatedReportId}` : "报告生成成功。";
		} catch (e) {
			error = e instanceof Error ? e.message : "生成报告失败";
		} finally {
			loadingGenerate = false;
		}
	}

	async function loadHistoryReport(): Promise<void> {
		if (selectedHistoryReportId === "") return;
		error = "";
		info = "";
		try {
			const data = await fetchCareerReportDetail(Number(selectedHistoryReportId));
			generatedReportId = data?.report_id || null;
			generatedReport = data?.report || null;
			selectedTimelineReviewId = null;
			focusLineId = generatedReport?.development_lines?.lines?.[0]?.line_id || "";
			const firstAdjH = generatedReport?.development_lines?.adjustments?.find(
				(a) => a.line_id === focusLineId,
			);
			selectedAdjustmentId = firstAdjH?.id || generatedReport?.development_lines?.adjustments?.[0]?.id || "";
			if (generatedReportId) {
				await loadReviewsForReport(generatedReportId);
			}
			info = generatedReportId ? `已加载历史报告 #${generatedReportId}` : "历史报告加载成功。";
		} catch (e) {
			error = e instanceof Error ? e.message : "加载历史报告失败";
		}
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
			reviewInfo = res.adjustment.auto_adjustment.triggered
				? "评估已提交，触发自动重规划。"
				: "评估已提交。";
			if (res.llm_extract?.source === "deepseek") {
				reviewInfo += " DeepSeek 已完成复盘量化。";
			}
			if (generatedReportId) {
				await loadReviewsForReport(generatedReportId);
				const latest = await fetchCareerReportDetail(generatedReportId);
				generatedReport = latest?.report || generatedReport;
				const lid = focusLineId || generatedReport?.development_lines?.lines?.[0]?.line_id || "";
				const adjsForLine = (generatedReport?.development_lines?.adjustments || []).filter((a) => a.line_id === lid);
				const fa = adjsForLine[adjsForLine.length - 1];
				selectedAdjustmentId = fa?.id || "";
				selectedTimelineReviewId = typeof res.review_id === "number" ? res.review_id : null;
			}
			reviewText = "";
		} catch (e) {
			reviewError = e instanceof Error ? e.message : "评估提交失败";
		} finally {
			submittingReview = false;
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

<section class="report-workbench">
	<div class="report-grid">
		<aside class="control-rail">
			<div class="rail-card">
				<div class="rail-head">
					<h3>目标职业配置</h3>
					<p>导入智能推荐或手动选择，最多 5 个目标。</p>
				</div>

				<label class="field">
					<span>画像记录</span>
					<select bind:value={selectedResumeId} disabled={!resumes.length}>
						{#each resumes as r (r.id)}
							<option value={r.id}>#{r.id} {r.name} · {r.major}</option>
						{/each}
					</select>
				</label>

				<div class="field">
					<span>模式</span>
					<div class="mode-switch">
						<label><input type="radio" name="report-goal" bind:group={matchGoal} value="fit" />适配优先</label>
						<label><input type="radio" name="report-goal" bind:group={matchGoal} value="stretch" />冲刺优先</label>
					</div>
				</div>

				<div class="actions-row">
					<button type="button" class="primary" disabled={loadingImport || selectedResumeId === ""} onclick={() => void importSmartTargets()}>
						{loadingImport ? "导入中..." : "导入 Top5 智能推荐"}
					</button>
				</div>

				{#if reportHistory.length}
					<div class="history-box">
						<select bind:value={selectedHistoryReportId}>
							{#each reportHistory as h (h.report_id)}
								<option value={h.report_id}>#{h.report_id} {h.title}</option>
							{/each}
						</select>
						<button type="button" class="ghost" onclick={() => void loadHistoryReport()}>加载历史报告</button>
					</div>
				{/if}

				<div class="search-box">
					<input type="text" bind:value={searchQ} placeholder="岗位关键词，如：数据分析师" />
					<input type="text" bind:value={searchLocation} placeholder="地点（可选）" />
					<button type="button" class="ghost" disabled={loadingSearch} onclick={() => void runManualSearch()}>
						{loadingSearch ? "搜索中..." : "搜索候选"}
					</button>
				</div>

				{#if searchedTargets.length}
					<div class="search-list">
						{#each searchedTargets as t (t.job_id)}
							<button type="button" class="result-item" onclick={() => upsertTarget(t)}>
								<span class="result-title">{t.title || t.job_id}</span>
								<span class="result-sub">{t.company || "未知公司"} · {t.location || "未知地点"}</span>
							</button>
						{/each}
					</div>
				{/if}

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
								<div class="min-w-0">
									<p class="truncate">{t.title || t.job_id}</p>
									<p class="truncate text-xs text-50">{t.company || "未知公司"} · {t.location || "未知地点"}</p>
								</div>
								<button type="button" class="text-btn danger" onclick={() => removeTarget(t.job_id)}>移除</button>
							</div>
						{/each}
					{:else}
						<p class="text-sm text-50">暂未添加目标职业。</p>
					{/if}
				</div>

				<button
					type="button"
					class="primary generate-btn"
					disabled={loadingGenerate || selectedResumeId === "" || !selectedTargets.length}
					onclick={() => void generate()}
				>
					{loadingGenerate ? "生成中..." : "生成 M2 生涯报告画布"}
				</button>
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
									placeholder="点「一键复盘模板」快速开始，或直接写：本周完成了什么、能力哪里进步、和目标岗位比感觉如何、有没有新成果。"
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
						先在上排卡片选择要看的岗位。横轴为<strong>第 n 月</strong>（每月一次复盘），纵轴为进步度（0–100）。未提交前只有起点 (0,0)；每月提交后在该月横坐标处新增一点并连线。点击<strong>蓝色复盘圆点</strong>可展开本次输入与量化结果；橙色菱形为自动重规划插入点。
					</p>
				</div>
			</div>

			{#if generatedReport}
				<div class="report-badges">
					<span>报告 #{generatedReportId}</span>
					<span>{generatedReport.generated_at}</span>
					<span>目标职业 {generatedReport.targets.length}</span>
					<span>复盘节奏 {generatedReport.evaluation.cycle.default === "monthly" ? "每月" : generatedReport.evaluation.cycle.default}</span>
				</div>

				<div class="planning-main">
					<div class="planning-head">
						<h4>个性化成长规划（分阶段）</h4>
						<p>先看策略和任务，再结合下方发展线与趋势图验证可行性。</p>
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
											{#if item.learning_path?.length}
												<p class="meta">学习路径：{item.learning_path.join("；")}</p>
											{/if}
											{#if item.practice_plan?.length}
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
											{#if item.learning_path?.length}
												<p class="meta">学习路径：{item.learning_path.join("；")}</p>
											{/if}
											{#if item.practice_plan?.length}
												<p class="meta">实践安排：{item.practice_plan.join("；")}</p>
											{/if}
										</article>
									{/each}
								</div>
							{:else}
								<p>暂无中期计划数据。</p>
							{/if}
						</section>

						<section class="plan-block">
							<h5>多岗位任务规划说明</h5>
							{#if linePlanSummary.shared.length}
								<div class="stack-desc">
									<p class="sub">叠合部分（可共用）</p>
									{#each linePlanSummary.shared as s (`shared-${s.group}`)}
										<p class="meta">同组 {s.lines.length} 条职业线共用准备：{s.lines.join("、")}</p>
									{/each}
								</div>
							{/if}
							{#if linePlanSummary.split.length}
								<div class="stack-desc">
									<p class="sub">分开部分（需定向准备）</p>
									{#each linePlanSummary.split as s (`split-${s.overlay_group}-${s.line_name}`)}
										<p class="meta">{s.line_name} 需要单独任务线（组：{s.overlay_group}）</p>
									{/each}
								</div>
							{/if}
							{#if !linePlanSummary.shared.length && !linePlanSummary.split.length}
								<p>暂无多职业路径说明。</p>
							{/if}
						</section>
					</div>
				</div>

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

				<div class="line-canvas-wrap">
					<svg viewBox="0 0 700 300" class="line-canvas" aria-label="进步度时间曲线">
						<!-- 网格 -->
						{#each [3, 6, 9] as gx}
							{@const gx1 = scalePoint(gx, chartLayout.ax.yMin).x}
							<line
								x1={gx1}
								y1={CHART.t}
								x2={gx1}
								y2={CHART.t + chartLayout.ph}
								class="grid-line"
							/>
						{/each}
						{#each [25, 50, 75] as gy}
							{@const gy1 = CHART.t + chartLayout.ph - (gy / 100) * chartLayout.ph}
							<line x1={CHART.l} y1={gy1} x2={CHART.l + chartLayout.pw} y2={gy1} class="grid-line" />
						{/each}
						<!-- 坐标轴 -->
						<line
							x1={CHART.l}
							y1={CHART.t + chartLayout.ph}
							x2={CHART.l + chartLayout.pw}
							y2={CHART.t + chartLayout.ph}
							class="axis-main"
						/>
						<line x1={CHART.l} y1={CHART.t} x2={CHART.l} y2={CHART.t + chartLayout.ph} class="axis-main" />
						<!-- Y 刻度 -->
						{#each [0, 25, 50, 75, 100] as tick}
							{@const yy = CHART.t + chartLayout.ph - (tick / 100) * chartLayout.ph}
							<line x1={CHART.l - 5} y1={yy} x2={CHART.l} y2={yy} class="axis-tick" />
							<text x={CHART.l - 8} y={yy + 3} text-anchor="end" class="axis-num">{tick}</text>
						{/each}
						<!-- X 刻度 -->
						{#each [0, 3, 6, 9, 12] as xm}
							{@const xx = scalePoint(xm, 0).x}
							<line x1={xx} y1={CHART.t + chartLayout.ph} x2={xx} y2={CHART.t + chartLayout.ph + 6} class="axis-tick" />
							<text x={xx} y={CHART.t + chartLayout.ph + 18} text-anchor="middle" class="axis-num">{xm}</text>
						{/each}
						<text x={CHART.l + chartLayout.pw / 2} y={CHART.h - 4} text-anchor="middle" class="axis-title">
							{chartLayout.ax.xLabel}
						</text>
						<text
							x="16"
							y={CHART.t + chartLayout.ph / 2}
							text-anchor="middle"
							class="axis-title"
							transform={`rotate(-90,16,${CHART.t + chartLayout.ph / 2})`}
						>
							{chartLayout.ax.yLabel}
						</text>

						{#if activeTimeline.length >= 2}
							<polyline
								points={timelinePolylineString()}
								fill="none"
								stroke={LINE_COLORS[activeLineIndex % LINE_COLORS.length]}
								stroke-width="3"
								stroke-linejoin="round"
								stroke-linecap="round"
							/>
						{/if}
						{#each activeTimeline as t, ti (`tl-${ti}-${t.month}`)}
							{@const p = scalePoint(t.month, t.progress)}
							{#if t.kind === "review"}
								<g
									class="hit-review-point"
									class:selected={selectedTimelineReviewId === t.review_id}
									role="button"
									tabindex="0"
									aria-label={`查看第${Math.round(t.month)}月复盘详情`}
									onclick={() => selectTimelineReview(t.review_id)}
									onkeydown={(e) => {
										if (e.key === "Enter" || e.key === " ") {
											e.preventDefault();
											selectTimelineReview(t.review_id);
										}
									}}
								>
									<circle cx={p.x} cy={p.y} r="10" fill="transparent" class="hit-pad" />
									<circle
										cx={p.x}
										cy={p.y}
										r="5.2"
										fill={LINE_COLORS[activeLineIndex % LINE_COLORS.length]}
										stroke="#ffffff"
										stroke-width={selectedTimelineReviewId === t.review_id ? "2.4" : "1.2"}
									/>
									{#if t.label}
										<text x={p.x} y={p.y - 10} text-anchor="middle" class="point-label">{t.label}</text>
									{/if}
								</g>
							{:else}
								<circle
									cx={p.x}
									cy={p.y}
									r={t.kind === "origin" ? "3.8" : "4.2"}
									fill={LINE_COLORS[activeLineIndex % LINE_COLORS.length]}
									stroke={t.kind === "origin" ? "#ffffff" : "none"}
									stroke-width={t.kind === "origin" ? "1.2" : "0"}
								/>
							{/if}
						{/each}

						{#each adjustmentsForActiveLine as adj (adj.id)}
							{@const pt = adjChartPoint(adj)}
							<rect
								x={pt.x - 5}
								y={pt.y - 5}
								width="10"
								height="10"
								transform={`rotate(45 ${pt.x} ${pt.y})`}
								fill={selectedAdjustmentId === adj.id ? "#d97706" : "#f59e0b"}
								fill-opacity={selectedAdjustmentId && selectedAdjustmentId !== adj.id ? "0.45" : "0.95"}
								stroke={selectedAdjustmentId === adj.id ? "#111827" : "#ffffff"}
								stroke-width={selectedAdjustmentId === adj.id ? "1.8" : "1.2"}
								class="adjust-node"
								role="button"
								tabindex="0"
								aria-label={`查看调整节点 ${adj.label}`}
								onclick={() => selectAdjustment(adj.id)}
								onkeydown={(e) => {
									if (e.key === "Enter" || e.key === " ") selectAdjustment(adj.id);
								}}
							/>
						{/each}
					</svg>
				</div>

				{#if selectedTimelinePoint?.kind === "review"}
					<div class="timeline-detail-panel">
						<div class="timeline-detail-head">
							<h4>{selectedTimelinePoint.label || `第${Math.round(selectedTimelinePoint.month)}月复盘`}</h4>
							<button type="button" class="text-btn" onclick={() => (selectedTimelineReviewId = null)}>关闭</button>
						</div>
						{#if selectedTimelinePoint.detail}
							<p class="detail-pass">
								通过率 {Math.round((selectedTimelinePoint.detail.pass_rate ?? 0) * 100)}% · {selectedTimelinePoint.detail
									.all_passed
									? "全部达标"
									: "存在未达标项"}
							</p>
							{#if selectedTimelinePoint.detail.llm_summary}
								<p class="detail-block">
									<span class="sub">DeepSeek 小结</span>{selectedTimelinePoint.detail.llm_summary}
								</p>
							{/if}
							{#if selectedTimelinePoint.detail.review_text}
								<p class="detail-block">
									<span class="sub">你的复盘原文</span><span class="pre">{selectedTimelinePoint.detail.review_text}</span>
								</p>
							{/if}
							{#if selectedTimelinePoint.detail.submitted}
								<p class="detail-block">
									<span class="sub">量化结果</span>
									缺口收敛 {Number(selectedTimelinePoint.detail.submitted.dim_gap_reduction ?? 0).toFixed(1)}% · 项目完成
									{Number(selectedTimelinePoint.detail.submitted.project_completion ?? 0).toFixed(1)}% · 匹配变化
									{Number(selectedTimelinePoint.detail.submitted.match_score_change ?? 0).toFixed(1)} 分 · 成果
									{Math.round(Number(selectedTimelinePoint.detail.submitted.delivery_output ?? 0))} 项
								</p>
							{/if}
						{:else}
							<p class="text-sm text-50">暂无详情数据，请重新加载报告后再试。</p>
						{/if}
					</div>
				{/if}

				{#if selectedAdjustmentDetail}
					<div class="canvas-side-cards">
						<article class="insight-mini-card insight-mini-card--adjust">
							<h4 class="insight-mini-card-title">
								{selectedAdjustmentDetail.kind === "initial_plan"
									? "起步执行安排（第 0 月）"
									: "下一月执行安排"}
							</h4>
							<div class="adjustment-detail">
								<p class="title">{selectedAdjustmentDetail.focus_label || "能力补齐"} · {selectedAdjustmentDetail.label}</p>
								<p>所属发展线：{selectedAdjustmentDetail.line_name}</p>
								<p>
									时间定位：目标执行<strong
										>第 {selectedAdjustmentDetail.plan_month ??
											Math.max(1, Math.round(Number(selectedAdjustmentDetail.month) || 1))} 月</strong>
									{#if selectedAdjustmentDetail.anchor_review_month != null && selectedAdjustmentDetail.anchor_review_month !== undefined}
										（复盘锚点：第 {Math.round(Number(selectedAdjustmentDetail.anchor_review_month))} 月）
									{/if}
									· 阶段 {STAGE_LABELS[selectedAdjustmentDetail.stage] ?? selectedAdjustmentDetail.stage}
								</p>
								{#if selectedAdjustmentDetail.execution_hints?.length}
									<p class="subhead">细化落地</p>
									<ul class="adjustment-hint-list">
										{#each selectedAdjustmentDetail.execution_hints as hint, hi (`h-${hi}`)}
											<li>{hint}</li>
										{/each}
									</ul>
								{/if}
								{#if selectedAdjustmentDetail.created_at}
									<p>触发时间：{selectedAdjustmentDetail.created_at}</p>
								{/if}
								{#if selectedAdjustmentDetail.failed_rows?.length}
									<p class="subhead">关联未达标指标</p>
									<ul>
										{#each selectedAdjustmentDetail.failed_rows as r (r.code)}
											<li>
												<button type="button" class="metric-link" onclick={() => focusMetric(r.code)}>
													{r.label}：实际 {r.actual_value} / 目标 {r.target_raw}
												</button>
											</li>
										{/each}
									</ul>
								{:else if selectedAdjustmentDetail.kind !== "initial_plan"}
									<p class="hint">暂无可关联的指标失败记录，可能来自更早一次自动调整。</p>
								{/if}
								{#if selectedAdjustmentDetail.review_created_at}
									<p class="hint">最近评估时间：{selectedAdjustmentDetail.review_created_at}</p>
								{/if}
							</div>
						</article>
					</div>
				{/if}
			{:else}
				<div class="empty-canvas">
					<p>先在左侧配置目标职业并生成报告，发展线画布会在这里显示。</p>
				</div>
			{/if}
		</div>

		<aside class="insight-rail">
			<div class="rail-head">
				<h3>趋势与评估</h3>
				<p>聚合展示目标职业趋势、能力缺口与评估指标。</p>
			</div>

			{#if generatedReport}
				<div class="mini-title">职业趋势强度</div>
				{#if trendOverview}
					<div class="trend-overview">
						<p class="summary">{trendOverview.tone}</p>
						<p class="meta">
							平均需求 {trendOverview.demandAvg} · 平均增长 {trendOverview.growthAvg} · 平均波动
							{trendOverview.volatilityAvg}（{trendOverview.stable}）
						</p>
						<p class="meta">说明：需求越高代表岗位机会越多；增长越高代表未来空间更大；波动越高代表路径不确定性更强。</p>
					</div>
				{/if}
				{#if generatedReport?.trend_meta}
					<p class="trend-meta-note">
						{generatedReport.trend_meta.ok
							? `趋势由 DeepSeek 增强分析（${generatedReport.trend_meta.model || "model"}），更新 ${generatedReport.trend_meta.updated || 0} 个目标。`
							: `趋势使用启发式估算（未启用或调用失败：${generatedReport.trend_meta.reason || "unknown"}）。`}
					</p>
				{/if}
				<div class="trend-chart">
					{#each trendRows as row (row.id)}
						<div class="trend-row">
							<div class="trend-name">{row.display_title || `${row.title} · ${row.company || "未知公司"}`}</div>
							<div class="trend-bars">
								<div class="bar-item">
									<span>需求</span>
									<div class="bar-track"><div class="bar demand" style={`width:${barWidth(row.trend.demand_index_0_100, maxTrend)}`}></div></div>
								</div>
								<div class="bar-item">
									<span>增长</span>
									<div class="bar-track"><div class="bar growth" style={`width:${barWidth(row.trend.growth_signal_0_100, maxTrend)}`}></div></div>
								</div>
								<div class="bar-item">
									<span>波动</span>
									<div class="bar-track"><div class="bar risk" style={`width:${barWidth(row.trend.volatility_0_100, maxTrend)}`}></div></div>
								</div>
							</div>
							<p class="trend-text">
								需求{trendLevelText(row.trend.demand_index_0_100)} / 增长{trendLevelText(
									row.trend.growth_signal_0_100,
								)}
								/ 波动{trendLevelText(row.trend.volatility_0_100)}：{trendInterpretation(row)}
							</p>
						</div>
					{/each}
				</div>

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
								{@const value = Number(t.match_preview.dimension_gaps?.[dim] || 0)}
								<span class="gap-cell" style={heatColor(value)}>{value.toFixed(1)}</span>
							{/each}
						</div>
					{/each}
				</div>

				<div class="mini-title">这段时间重点看什么</div>
				<div class="metric-list">
					{#each generatedReport.evaluation.metrics as metric (metric.code)}
						<div
							class="metric-item"
							class:metric-highlight={highlightedMetricCode === metric.code}
							data-metric-code={metric.code}
						>
							<p>{metricDisplayLabel(metric)}</p>
							<p class="meta">{readableCycleText(metric.cycle)} · 希望达到 {readableTargetText(metric.target)}</p>
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
							量化指标：缺口收敛 {Number(generatedReport.evaluation.latest_review.submitted_metrics?.dim_gap_reduction ?? 0).toFixed(1)}% ·
							项目完成 {Number(generatedReport.evaluation.latest_review.submitted_metrics?.project_completion ?? 0).toFixed(1)}% ·
							匹配变化 {Number(generatedReport.evaluation.latest_review.submitted_metrics?.match_score_change ?? 0).toFixed(1)} 分 ·
							成果 {Math.round(Number(generatedReport.evaluation.latest_review.submitted_metrics?.delivery_output ?? 0))} 项
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
		</aside>
	</div>

	{#if focusTarget}
		<div class="focus-strip">
			<strong>{focusTarget.title}</strong>
			<span>{focusTarget.company} · {focusTarget.location}</span>
			<span>匹配度 {focusTarget.match_preview.match_score}</span>
			<span>需求指数 {focusTarget.trend.demand_index_0_100}</span>
		</div>
	{/if}

	{#if error}
		<p class="msg error">{error}</p>
	{/if}
	{#if info}
		<p class="msg ok">{info}</p>
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
		grid-template-columns: 320px minmax(0, 1fr) 360px;
		align-items: start;
	}
	.control-rail {
		display: grid;
		gap: 0.9rem;
	}
	.rail-card,
	.m3-card,
	.canvas-main,
	.insight-rail {
		border: 1px solid color-mix(in oklch, currentColor 12%, transparent);
		background: color-mix(in oklch, var(--card-bg) 94%, transparent);
		border-radius: 1rem;
		padding: 1rem;
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
	.search-box,
	.selected-area,
	.history-box {
		margin-top: 0.8rem;
		display: grid;
		gap: 0.5rem;
	}
	.search-list {
		margin-top: 0.7rem;
		max-height: 11rem;
		overflow: auto;
		display: grid;
		gap: 0.35rem;
	}
	.result-item {
		text-align: left;
		padding: 0.55rem 0.6rem;
		border-radius: 0.7rem;
		border: 1px solid color-mix(in oklch, currentColor 12%, transparent);
		background: color-mix(in oklch, var(--btn-regular-bg) 75%, transparent);
	}
	.result-title {
		display: block;
		font-size: 0.82rem;
		font-weight: 600;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.result-sub {
		display: block;
		font-size: 0.73rem;
		color: color-mix(in oklch, currentColor 55%, transparent);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.selected-head,
	.selected-item {
		display: flex;
		gap: 0.6rem;
		align-items: center;
		justify-content: space-between;
	}
	.selected-item {
		padding: 0.45rem 0.5rem;
		border-radius: 0.6rem;
		background: color-mix(in oklch, var(--btn-regular-bg) 70%, transparent);
	}
	.text-btn {
		font-size: 0.74rem;
		color: color-mix(in oklch, currentColor 55%, transparent);
	}
	.text-btn.danger {
		color: #ef4444;
	}
	.generate-btn {
		margin-top: 0.8rem;
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
		margin-top: 0.8rem;
		border-radius: 0.9rem;
		padding: 0.65rem;
		background: color-mix(in oklch, var(--btn-regular-bg) 78%, transparent);
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
	.trend-chart {
		display: grid;
		gap: 0.5rem;
	}
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
	.trend-meta-note {
		margin-bottom: 0.35rem;
		font-size: 0.68rem;
		color: color-mix(in oklch, currentColor 58%, transparent);
	}
	.trend-row {
		padding: 0.45rem 0.5rem;
		border-radius: 0.65rem;
		background: color-mix(in oklch, var(--btn-regular-bg) 70%, transparent);
	}
	.trend-name {
		font-size: 0.75rem;
		font-weight: 600;
		margin-bottom: 0.25rem;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.trend-bars {
		display: grid;
		gap: 0.2rem;
	}
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
		.insight-rail {
			grid-column: 1 / -1;
		}
	}
	@media (max-width: 900px) {
		.report-grid {
			grid-template-columns: 1fr;
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
