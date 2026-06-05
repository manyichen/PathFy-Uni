<script lang="ts">
	import { onMount } from "svelte";
	import Icon from "@iconify/svelte";
	import {
		fetchJobs,
		fetchLateralPaths,
		fetchPromotionPath,
		type CareerActionPhase,
		type CareerPathCompetition,
		type CareerPathLearningResource,
		type JobLiteItem,
		type JobsPageResult,
		type LateralPathResult,
		type PromotionPathResult,
		type PromotionRoute,
	} from "@/lib/api/jobs";
	import { MATCH_CACHE_KEY_PREFIX, getUser } from "@/lib/features/auth/session";
	import JobPickerModal from "./JobPickerModal.svelte";

	type MatchCacheLike = {
		llmBlock?: {
			top5?: Array<{
				job_id?: string;
				title?: string;
				company?: string;
				location?: string;
				salary?: string;
			}>;
		};
		jobs?: Array<{
			id?: string;
			title?: string;
			company?: string;
			location?: string;
			salary?: string;
		}>;
	};

	let loadingInitial = $state(true);
	let loadError = $state("");
	let currentJobId = $state("");
	let currentJob = $state<JobLiteItem | null>(null);
	let selectionSource = $state<"match" | "fallback" | "manual">("fallback");

	let promotionLoading = $state(false);
	let promotionError = $state("");
	let promotionResult = $state<PromotionPathResult | null>(null);

	let lateralLoading = $state(false);
	let lateralError = $state("");
	let lateralResult = $state<LateralPathResult | null>(null);

	let pickerOpen = $state(false);
	let analysisRun = 0;

	const promotionRoutes = $derived.by(() => promotionResult?.routes ?? []);
	const lateralRoutes = $derived.by(() => lateralResult?.routes ?? []);
	const visibleLateralRoutes = $derived.by(() => {
		const limit = Math.max(1, promotionRoutes.length + 1);
		return lateralRoutes.slice(0, limit);
	});

	function matchStateStorageKey(): string {
		const u = getUser();
		return `${MATCH_CACHE_KEY_PREFIX}${u?.id ?? "guest"}`;
	}

	function readTopMatchedJob(): JobLiteItem | null {
		if (typeof window === "undefined") return null;
		try {
			const raw = localStorage.getItem(matchStateStorageKey());
			if (!raw) return null;
			const parsed = JSON.parse(raw) as MatchCacheLike;
			const top = parsed.llmBlock?.top5?.[0];
			if (top?.job_id) {
				return {
					id: String(top.job_id),
					title: top.title || "智能推荐岗位",
					company: top.company || "",
					location: top.location || "",
					salary: top.salary || "",
				};
			}
			const first = parsed.jobs?.[0];
			if (first?.id) {
				return {
					id: String(first.id),
					title: first.title || "匹配岗位",
					company: first.company || "",
					location: first.location || "",
					salary: first.salary || "",
				};
			}
		} catch {
			return null;
		}
		return null;
	}

	function applyCurrentJob(job: JobLiteItem, source: "match" | "fallback" | "manual") {
		currentJobId = job.id;
		currentJob = job;
		selectionSource = source;
		void runCareerPaths(job.id);
	}

	onMount(async () => {
		try {
			const matched = readTopMatchedJob();
			if (matched) {
				applyCurrentJob(matched, "match");
				return;
			}

			const page: JobsPageResult = await fetchJobs({ page: 1, pageSize: 1 });
			const first = page.jobs[0];
			if (first) {
				applyCurrentJob(
					{
						id: first.id,
						title: first.title,
						company: first.company,
						location: first.location,
						salary: first.salary,
					},
					"fallback",
				);
			} else {
				loadError = "暂无可用于分析的岗位数据。";
			}
		} catch (err) {
			loadError = err instanceof Error ? err.message : "岗位列表加载失败";
		} finally {
			loadingInitial = false;
		}
	});

	async function runCareerPaths(jobId = currentJobId) {
		const id = jobId.trim();
		if (!id) {
			promotionError = "请先选择岗位";
			lateralError = "请先选择岗位";
			return;
		}
		const runId = ++analysisRun;
		promotionLoading = true;
		lateralLoading = true;
		promotionError = "";
		lateralError = "";
		promotionResult = null;
		lateralResult = null;

		const [promotion, lateral] = await Promise.allSettled([
			fetchPromotionPath(id, 5, 8),
			fetchLateralPaths(id, 12),
		]);
		if (runId !== analysisRun) return;

		if (promotion.status === "fulfilled") {
			promotionResult = promotion.value;
		} else {
			promotionError = promotion.reason instanceof Error ? promotion.reason.message : "升职路径加载失败";
		}
		if (lateral.status === "fulfilled") {
			lateralResult = lateral.value;
		} else {
			lateralError = lateral.reason instanceof Error ? lateral.reason.message : "换岗路径加载失败";
		}
		promotionLoading = false;
		lateralLoading = false;
	}

	function handlePick(job: JobLiteItem) {
		applyCurrentJob(job, "manual");
	}

	function sourceLabel(): string {
		if (selectionSource === "match") return "来自人岗匹配第一名";
		if (selectionSource === "manual") return "手动选择";
		return "系统默认岗位";
	}

	function percent(value: number | undefined): string {
		const n = Number(value ?? 0);
		if (!Number.isFinite(n) || n <= 0) return "—";
		return `${Math.round(Math.min(1, n) * 100)}%`;
	}

	function routeParts(route: PromotionRoute): string[] {
		const raw = String(route.route_text || "").trim();
		const parts = raw
			.split(/\s*(?:→|->)\s*/)
			.map((x) => x.trim())
			.filter(Boolean);
		if (parts.length) return parts;
		return route.stages.map((x) => x.role).filter(Boolean);
	}

	function resourceMeta(resource: CareerPathLearningResource): string {
		return [resource.resource_type, resource.difficulty, resource.skill_tag].filter(Boolean).join(" · ");
	}

	function competitionMeta(competition: CareerPathCompetition): string {
		return [competition.competition_type, competition.difficulty, competition.award_level]
			.filter(Boolean)
			.join(" · ");
	}

	function phaseResources(phase: CareerActionPhase): CareerPathLearningResource[] {
		return phase.learning_resources?.slice(0, 3) ?? [];
	}

	function phaseCompetitions(phase: CareerActionPhase): CareerPathCompetition[] {
		return phase.competitions?.slice(0, 2) ?? [];
	}
</script>

<div class="career-preview space-y-5">
	<section class="rounded-2xl border border-black/10 bg-[var(--page-bg)] p-4 dark:border-white/10">
		<div class="flex flex-wrap items-start justify-between gap-3">
			<div class="min-w-0">
				<p class="text-xs font-medium text-[var(--primary)]">当前岗位</p>
				<h3 class="mt-1 text-base font-semibold text-black dark:text-white">
					{currentJob ? currentJob.title : "尚未选择岗位"}
				</h3>
				{#if currentJob}
					<p class="mt-1 text-sm text-75">
						{currentJob.company || "未知公司"} · {currentJob.location || "未知地点"}
						{#if currentJob.salary} · {currentJob.salary}{/if}
					</p>
					<p class="mt-2 text-xs text-50">{sourceLabel()}</p>
				{/if}
			</div>
			<div class="flex flex-wrap gap-2">
				<button
					type="button"
					onclick={() => {
						pickerOpen = true;
					}}
					class="inline-flex items-center gap-1.5 rounded-xl border border-black/15 bg-[var(--btn-regular-bg)] px-3 py-2 text-xs font-medium transition hover:opacity-85 dark:border-white/20"
				>
					<Icon icon="material-symbols:search-rounded" class="text-base" />
					选择岗位
				</button>
				<button
					type="button"
					onclick={() => void runCareerPaths()}
					disabled={!currentJobId || promotionLoading || lateralLoading}
					class="inline-flex items-center gap-1.5 rounded-xl border border-[var(--primary)] bg-[var(--btn-regular-bg)] px-3 py-2 text-xs font-medium text-[var(--primary)] transition hover:opacity-85 disabled:opacity-50"
				>
					<Icon icon="material-symbols:refresh-rounded" class="text-base" />
					刷新分析
				</button>
			</div>
		</div>

		{#if loadingInitial}
			<p class="mt-3 text-sm text-75">正在读取岗位与匹配缓存...</p>
		{:else if loadError}
			<p class="mt-3 text-sm text-rose-500">{loadError}</p>
		{/if}
	</section>

	<div class="grid gap-5 xl:grid-cols-2">
		<section class="rounded-2xl border border-black/10 bg-[var(--page-bg)] p-4 dark:border-white/10">
			<div class="flex items-start justify-between gap-3">
				<div>
					<h3 class="text-base font-semibold">垂直晋升路径</h3>
					<p class="mt-1 text-xs text-75">先定位当前 Job 的标准 JobTitle，再读取图谱中预置的 JobPromotion 路线。</p>
				</div>
				<span class="rounded-full bg-[var(--btn-regular-bg)] px-2.5 py-1 text-xs text-75">
					{promotionRoutes.length} 条
				</span>
			</div>

			{#if promotionLoading}
				<p class="mt-4 text-sm text-75">正在加载晋升路线...</p>
			{:else if promotionError}
				<p class="mt-4 text-sm text-rose-500">{promotionError}</p>
			{:else if promotionResult && promotionRoutes.length === 0}
				<p class="mt-4 rounded-xl border border-dashed border-black/20 p-3 text-sm text-75 dark:border-white/20">
					当前岗位已定位到 {promotionResult.meta.job_title || currentJob?.title}，但暂未配置晋升路线。
				</p>
			{:else if promotionRoutes.length}
				<div class="mt-4 space-y-4">
					{#each promotionRoutes as route, idx (route.id || `${route.route_title}-${idx}`)}
						<article class="route-panel">
							<div class="flex flex-wrap items-start justify-between gap-3">
								<div class="min-w-0">
									<p class="text-xs text-[var(--primary)]">路径 {idx + 1}</p>
									<h4 class="mt-1 text-sm font-semibold text-black dark:text-white">{route.route_title}</h4>
									<p class="mt-1 text-xs text-75">目标：{route.target_title}</p>
								</div>
								{#if route.confidence > 0}
									<span class="metric-pill">置信度 {percent(route.confidence)}</span>
								{/if}
							</div>

							<div class="mt-3 flex flex-wrap items-center gap-2">
								{#each routeParts(route) as part, partIdx (`${route.id}-${part}-${partIdx}`)}
									<span class="path-node">{part}</span>
									{#if partIdx < routeParts(route).length - 1}
										<Icon icon="material-symbols:arrow-forward-rounded" class="text-sm text-50" />
									{/if}
								{/each}
							</div>

							<p class="mt-3 rounded-lg bg-[var(--btn-regular-bg)]/70 p-2 text-xs leading-relaxed text-75">
								{route.rationale}
							</p>

							<div class="mt-3 space-y-3">
								{#each route.action_plan.phases as phase (`promo-${route.id}-${phase.stage}`)}
									<div class="phase-panel">
										<div class="phase-head">
											<div>
												<p class="phase-label">{phase.label} · {phase.period}</p>
												<p class="phase-role">{phase.role}</p>
											</div>
											<span class="phase-index">S{phase.stage}</span>
										</div>
										<p class="mt-2 text-xs text-75">里程碑：{phase.milestone}</p>
										<ul class="mt-2 list-disc pl-5 text-xs leading-relaxed text-75">
											{#each phase.actions as action (action)}
												<li>{action}</li>
											{/each}
										</ul>

										<div class="mt-3 grid gap-2 md:grid-cols-2">
											<div class="resource-list">
												<p class="resource-title">学习资源</p>
												{#each phaseResources(phase) as lr (`promo-lr-${route.id}-${phase.stage}-${lr.resource_id}`)}
													<a class="resource-item" href={lr.resource_url || undefined} target="_blank" rel="noopener noreferrer">
														<span>{lr.resource_name}</span>
														<small>{resourceMeta(lr) || lr.rationale}</small>
													</a>
												{:else}
													<p class="empty-mini">暂无阶段资源</p>
												{/each}
											</div>
											<div class="resource-list">
												<p class="resource-title">竞赛/实践</p>
												{#each phaseCompetitions(phase) as cp (`promo-cp-${route.id}-${phase.stage}-${cp.competition_id}`)}
													<a class="resource-item" href={cp.official_url || undefined} target="_blank" rel="noopener noreferrer">
														<span>{cp.competition_name}</span>
														<small>{competitionMeta(cp) || cp.rationale}</small>
													</a>
												{:else}
													<p class="empty-mini">暂无阶段竞赛</p>
												{/each}
											</div>
										</div>
									</div>
								{/each}
							</div>
						</article>
					{/each}
				</div>
			{/if}
		</section>

		<section class="rounded-2xl border border-black/10 bg-[var(--page-bg)] p-4 dark:border-white/10">
			<div class="flex items-start justify-between gap-3">
				<div>
					<h3 class="text-base font-semibold">水平换岗路径</h3>
					<p class="mt-1 text-xs text-75">读取 JobTitle 层的 SIMILAR_FOR_LATERAL 关系，按迁移可行性排序。</p>
				</div>
				<span class="rounded-full bg-[var(--btn-regular-bg)] px-2.5 py-1 text-xs text-75">
					展示 {visibleLateralRoutes.length}/{lateralRoutes.length} 条
				</span>
			</div>

			{#if lateralLoading}
				<p class="mt-4 text-sm text-75">正在加载换岗路线...</p>
			{:else if lateralError}
				<p class="mt-4 text-sm text-rose-500">{lateralError}</p>
			{:else if lateralResult && lateralRoutes.length === 0}
				<p class="mt-4 rounded-xl border border-dashed border-black/20 p-3 text-sm text-75 dark:border-white/20">
					当前岗位对应的 JobTitle「{lateralResult.job_title || currentJob?.title}」暂未配置横向换岗关系。
				</p>
			{:else if visibleLateralRoutes.length}
				<div class="mt-4 space-y-4">
					{#each visibleLateralRoutes as route (route.id)}
						<article class="route-panel">
							<div class="flex flex-wrap items-start justify-between gap-3">
								<div class="min-w-0">
									<p class="text-xs text-[var(--primary)]">第 {route.rank} 推荐</p>
									<h4 class="mt-1 text-sm font-semibold text-black dark:text-white">
										{route.from_title} → {route.target_title}
									</h4>
									<p class="mt-1 text-xs text-75">{route.rationale}</p>
								</div>
								<span class="metric-pill">迁移度 {percent(route.score)}</span>
							</div>

							<div class="mt-3 flex flex-wrap gap-2 text-xs">
								{#if route.track_to}<span class="tag-pill">{route.track_to}</span>{/if}
								{#if route.same_track}<span class="tag-pill">同赛道</span>{/if}
								{#if route.promotion_linked}<span class="tag-pill">与晋升路线相邻</span>{/if}
								{#if route.cap_similarity}<span class="tag-pill">能力相似 {percent(route.cap_similarity)}</span>{/if}
							</div>

							{#if route.candidate_jobs.length}
								<div class="mt-3">
									<p class="resource-title">可参考的具体岗位</p>
									<div class="mt-1 grid gap-2">
										{#each route.candidate_jobs as job (`lat-job-${route.id}-${job.id}`)}
											<div class="job-mini">
												<span>{job.title}</span>
												<small>{job.company || "未知公司"} · {job.location || "未知地点"}{job.salary ? ` · ${job.salary}` : ""}</small>
											</div>
										{/each}
									</div>
								</div>
							{/if}

							<div class="mt-3 space-y-3">
								{#each route.action_plan.phases as phase (`lateral-${route.id}-${phase.stage}`)}
									<div class="phase-panel">
										<div class="phase-head">
											<div>
												<p class="phase-label">{phase.label} · {phase.period}</p>
												<p class="phase-role">{phase.role}</p>
											</div>
											<span class="phase-index">S{phase.stage}</span>
										</div>
										<p class="mt-2 text-xs text-75">里程碑：{phase.milestone}</p>
										<ul class="mt-2 list-disc pl-5 text-xs leading-relaxed text-75">
											{#each phase.actions as action (action)}
												<li>{action}</li>
											{/each}
										</ul>

										<div class="mt-3 grid gap-2 md:grid-cols-2">
											<div class="resource-list">
												<p class="resource-title">学习资源</p>
												{#each phaseResources(phase) as lr (`lat-lr-${route.id}-${phase.stage}-${lr.resource_id}`)}
													<a class="resource-item" href={lr.resource_url || undefined} target="_blank" rel="noopener noreferrer">
														<span>{lr.resource_name}</span>
														<small>{resourceMeta(lr) || lr.rationale}</small>
													</a>
												{:else}
													<p class="empty-mini">暂无阶段资源</p>
												{/each}
											</div>
											<div class="resource-list">
												<p class="resource-title">竞赛/实践</p>
												{#each phaseCompetitions(phase) as cp (`lat-cp-${route.id}-${phase.stage}-${cp.competition_id}`)}
													<a class="resource-item" href={cp.official_url || undefined} target="_blank" rel="noopener noreferrer">
														<span>{cp.competition_name}</span>
														<small>{competitionMeta(cp) || cp.rationale}</small>
													</a>
												{:else}
													<p class="empty-mini">暂无阶段竞赛</p>
												{/each}
											</div>
										</div>
									</div>
								{/each}
							</div>
						</article>
					{/each}
				</div>
			{/if}
		</section>
	</div>
</div>

<JobPickerModal
	open={pickerOpen}
	modalTitle="选择当前岗位"
	selectedJobId={currentJobId}
	onClose={() => {
		pickerOpen = false;
	}}
	onSelect={handlePick}
/>

<style>
	.route-panel {
		border: 1px solid color-mix(in oklch, currentColor 10%, transparent);
		border-radius: 0.85rem;
		background: color-mix(in oklch, var(--card-bg) 94%, transparent);
		padding: 0.85rem;
	}
	.metric-pill,
	.tag-pill,
	.path-node {
		display: inline-flex;
		align-items: center;
		max-width: 100%;
		border-radius: 999px;
		border: 1px solid color-mix(in oklch, currentColor 12%, transparent);
		background: color-mix(in oklch, var(--btn-regular-bg) 78%, transparent);
		color: color-mix(in oklch, currentColor 76%, transparent);
		font-size: 0.72rem;
		line-height: 1.25;
	}
	.metric-pill,
	.tag-pill {
		padding: 0.18rem 0.55rem;
	}
	.path-node {
		padding: 0.28rem 0.65rem;
		font-weight: 600;
		color: color-mix(in oklch, currentColor 86%, transparent);
	}
	.phase-panel {
		border-radius: 0.75rem;
		border: 1px solid color-mix(in oklch, currentColor 9%, transparent);
		background: color-mix(in oklch, var(--btn-regular-bg) 48%, transparent);
		padding: 0.75rem;
	}
	.phase-head {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 0.75rem;
	}
	.phase-label {
		margin: 0;
		font-size: 0.72rem;
		font-weight: 700;
		color: color-mix(in oklch, var(--primary) 80%, currentColor);
	}
	.phase-role {
		margin: 0.12rem 0 0;
		font-size: 0.86rem;
		font-weight: 700;
		color: color-mix(in oklch, currentColor 88%, transparent);
	}
	.phase-index {
		border-radius: 0.55rem;
		background: color-mix(in oklch, var(--primary) 12%, transparent);
		color: color-mix(in oklch, var(--primary) 85%, currentColor);
		font-size: 0.72rem;
		font-weight: 800;
		padding: 0.15rem 0.4rem;
	}
	.resource-list {
		min-width: 0;
		display: grid;
		gap: 0.38rem;
	}
	.resource-title {
		margin: 0;
		font-size: 0.72rem;
		font-weight: 700;
		color: color-mix(in oklch, currentColor 64%, transparent);
	}
	.resource-item,
	.job-mini {
		min-width: 0;
		display: grid;
		gap: 0.12rem;
		border-radius: 0.58rem;
		background: color-mix(in oklch, var(--card-bg) 90%, transparent);
		padding: 0.45rem 0.55rem;
		text-decoration: none;
	}
	.resource-item:hover {
		background: color-mix(in oklch, var(--primary) 8%, var(--card-bg));
	}
	.resource-item span,
	.job-mini span {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: 0.76rem;
		font-weight: 650;
		color: color-mix(in oklch, currentColor 88%, transparent);
	}
	.resource-item small,
	.job-mini small {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: 0.68rem;
		color: color-mix(in oklch, currentColor 55%, transparent);
	}
	.empty-mini {
		margin: 0;
		border-radius: 0.58rem;
		border: 1px dashed color-mix(in oklch, currentColor 12%, transparent);
		padding: 0.45rem 0.55rem;
		font-size: 0.72rem;
		color: color-mix(in oklch, currentColor 52%, transparent);
	}
</style>
