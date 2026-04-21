<script lang="ts">
	import { onMount } from "svelte";
	import {
		analyzeJobTransition,
		fetchJobs,
		fetchPromotionPath,
		type JobLiteItem,
		type JobsPageResult,
		type PromotionPathResult,
		type TransitionAnalysisResult,
	} from "../../lib/jobs";
	import JobPickerModal from "./JobPickerModal.svelte";

	let loadingJobs = $state(true);
	let loadError = $state("");

	let fromJobId = $state("");
	let fromJob = $state<JobLiteItem | null>(null);
	let toJobId = $state("");
	let toJob = $state<JobLiteItem | null>(null);
	let transitionLoading = $state(false);
	let transitionError = $state("");
	let transitionResult = $state<TransitionAnalysisResult | null>(null);

	let promotionJobId = $state("");
	let promotionJob = $state<JobLiteItem | null>(null);
	let promotionLoading = $state(false);
	let promotionError = $state("");
	let promotionResult = $state<PromotionPathResult | null>(null);

	let pickerOpen = $state(false);
	let pickerTarget = $state<"from" | "to" | "promotion" | null>(null);

	function openPicker(target: "from" | "to" | "promotion") {
		pickerTarget = target;
		pickerOpen = true;
	}

	function closePicker() {
		pickerOpen = false;
		pickerTarget = null;
	}

	function handlePick(job: JobLiteItem) {
		if (pickerTarget === "from") {
			fromJobId = job.id;
			fromJob = job;
			return;
		}
		if (pickerTarget === "to") {
			toJobId = job.id;
			toJob = job;
			return;
		}
		if (pickerTarget === "promotion") {
			promotionJobId = job.id;
			promotionJob = job;
		}
	}

	function selectedJobIdForPicker(): string {
		if (pickerTarget === "from") return fromJobId;
		if (pickerTarget === "to") return toJobId;
		if (pickerTarget === "promotion") return promotionJobId;
		return "";
	}

	function pickerTitle(): string {
		if (pickerTarget === "from") return "选择当前岗位";
		if (pickerTarget === "to") return "选择目标岗位";
		if (pickerTarget === "promotion") return "选择升职起始岗位";
		return "选择岗位";
	}

	function applySelectionDefaults(seedJobs: JobLiteItem[]) {
		if (seedJobs.length <= 0) {
			fromJobId = "";
			toJobId = "";
			promotionJobId = "";
			fromJob = null;
			toJob = null;
			promotionJob = null;
			return;
		}

		const first = seedJobs[0];
		const second = seedJobs.length > 1 ? seedJobs[1] : seedJobs[0];

		fromJobId = first.id;
		fromJob = first;
		toJobId = second.id;
		toJob = second;
		promotionJobId = first.id;
		promotionJob = first;
	}

	onMount(async () => {
		try {
			const page: JobsPageResult = await fetchJobs({ page: 1, pageSize: 20 });
			const seedJobs: JobLiteItem[] = page.jobs.map((x) => ({
				id: x.id,
				title: x.title,
				company: x.company,
				location: x.location,
			}));
			applySelectionDefaults(seedJobs);
		} catch (err) {
			loadError = err instanceof Error ? err.message : "岗位列表加载失败";
		} finally {
			loadingJobs = false;
		}
	});

	function shortDimensionName(key: string): string {
		return key.replace("cap_req_", "");
	}

	async function runTransitionAnalysis() {
		transitionError = "";
		transitionResult = null;
		if (!fromJobId || !toJobId) {
			transitionError = "请先选择两个岗位";
			return;
		}

		transitionLoading = true;
		try {
			transitionResult = await analyzeJobTransition(fromJobId, toJobId);
		} catch (err) {
			transitionError = err instanceof Error ? err.message : "换岗分析失败";
		} finally {
			transitionLoading = false;
		}
	}

	async function runPromotionPath() {
		promotionError = "";
		promotionResult = null;
		if (!promotionJobId) {
			promotionError = "请先选择岗位";
			return;
		}

		promotionLoading = true;
		try {
			promotionResult = await fetchPromotionPath(promotionJobId, 5, 4);
		} catch (err) {
			promotionError = err instanceof Error ? err.message : "升职路径加载失败";
		} finally {
			promotionLoading = false;
		}
	}
</script>

<div class="space-y-5">
	<section class="rounded-2xl border border-black/10 bg-[var(--page-bg)] p-4 dark:border-white/10">
		<h3 class="text-base font-semibold">换岗对比分析</h3>
		<p class="mt-1 text-xs text-75">选择当前岗位与目标岗位，系统会给出技能差异、能力缺口和大模型建议。</p>

		{#if loadingJobs}
			<p class="mt-3 text-sm text-75">岗位数据加载中...</p>
		{:else if loadError}
			<p class="mt-3 text-sm text-rose-500">{loadError}</p>
		{:else}
			<div class="mt-3 grid gap-3 md:grid-cols-2">
				<div class="rounded-xl border border-black/10 bg-white/70 p-3 dark:border-white/15 dark:bg-white/5">
					<p class="text-xs text-75">当前岗位</p>
					<p class="mt-1 text-sm font-medium">{fromJob ? `${fromJob.title} | ${fromJob.company}` : "未选择"}</p>
					<button
						type="button"
						onclick={() => openPicker("from")}
						class="mt-2 rounded-lg border border-black/15 px-3 py-1 text-xs transition hover:opacity-80 dark:border-white/20"
					>
						选择岗位
					</button>
				</div>
				<div class="rounded-xl border border-black/10 bg-white/70 p-3 dark:border-white/15 dark:bg-white/5">
					<p class="text-xs text-75">目标岗位</p>
					<p class="mt-1 text-sm font-medium">{toJob ? `${toJob.title} | ${toJob.company}` : "未选择"}</p>
					<button
						type="button"
						onclick={() => openPicker("to")}
						class="mt-2 rounded-lg border border-black/15 px-3 py-1 text-xs transition hover:opacity-80 dark:border-white/20"
					>
						选择岗位
					</button>
				</div>
			</div>

			<button
				type="button"
				onclick={runTransitionAnalysis}
				disabled={transitionLoading}
				class="mt-3 rounded-xl border border-[var(--primary)] bg-[var(--btn-regular-bg)] px-4 py-2 text-sm font-medium text-[var(--primary)] transition hover:opacity-90 disabled:opacity-60"
			>
				{transitionLoading ? "分析中..." : "开始换岗分析"}
			</button>

			{#if transitionError}
				<p class="mt-3 text-sm text-rose-500">{transitionError}</p>
			{/if}

			{#if transitionResult}
				<div class="mt-4 space-y-3 rounded-xl border border-black/10 bg-white/70 p-3 text-sm dark:border-white/15 dark:bg-white/5">
					<div class="grid gap-2 md:grid-cols-4">
						<div class="rounded-lg bg-[var(--btn-regular-bg)] p-2">
							<p class="text-xs text-75">经验年限差</p>
							<p class="text-base font-semibold">{transitionResult.analysis.score_summary.experience_gap}</p>
						</div>
						<div class="rounded-lg bg-[var(--btn-regular-bg)] p-2">
							<p class="text-xs text-75">重叠技能</p>
							<p class="text-base font-semibold">{transitionResult.analysis.score_summary.overlap_count}</p>
						</div>
						<div class="rounded-lg bg-[var(--btn-regular-bg)] p-2">
							<p class="text-xs text-75">缺失技能</p>
							<p class="text-base font-semibold">{transitionResult.analysis.score_summary.missing_count}</p>
						</div>
						<div class="rounded-lg bg-[var(--btn-regular-bg)] p-2">
							<p class="text-xs text-75">可行性</p>
							<p class="text-base font-semibold">{transitionResult.advice.feasibility}</p>
						</div>
					</div>

					<p class="rounded-lg border border-black/10 p-2 text-sm dark:border-white/15">{transitionResult.advice.summary}</p>

					<div class="grid gap-3 md:grid-cols-2">
						<div>
							<p class="text-xs font-semibold text-75">优势（可迁移）</p>
							<ul class="mt-1 list-disc pl-5 text-xs">
								{#each transitionResult.advice.advantages as item (item)}
									<li>{item}</li>
								{/each}
							</ul>
						</div>
						<div>
							<p class="text-xs font-semibold text-75">主要缺口</p>
							<ul class="mt-1 list-disc pl-5 text-xs">
								{#each transitionResult.advice.gaps as item (item)}
									<li>{item}</li>
								{/each}
							</ul>
						</div>
					</div>

					<div>
						<p class="text-xs font-semibold text-75">能力维度差（Top 5）</p>
						<div class="mt-1 grid gap-2 md:grid-cols-2">
							{#each transitionResult.analysis.capability_gaps.slice(0, 5) as gap (`${gap.dimension}-${gap.gap}`)}
								<div class="rounded-lg border border-black/10 px-2 py-1 text-xs dark:border-white/15">
									<span class="font-medium">{shortDimensionName(gap.dimension)}</span>
									<span class="ml-2 text-75">{gap.from} -> {gap.to}</span>
									<span class="ml-2 font-semibold">gap {gap.gap}</span>
								</div>
							{/each}
						</div>
					</div>

					<div>
						<p class="text-xs font-semibold text-75">学习计划</p>
						<ul class="mt-1 list-decimal pl-5 text-xs">
							{#each transitionResult.advice.learning_plan as step (step)}
								<li>{step}</li>
							{/each}
						</ul>
					</div>

					<p class="rounded-lg border border-amber-400/30 bg-amber-100/40 p-2 text-xs text-amber-900 dark:bg-amber-200/10 dark:text-amber-100">
						{transitionResult.advice.final_recommendation}
					</p>
				</div>
			{/if}
		{/if}
	</section>

	<section class="rounded-2xl border border-black/10 bg-[var(--page-bg)] p-4 dark:border-white/10">
		<h3 class="text-base font-semibold">升职路径查询</h3>
		<p class="mt-1 text-xs text-75">基于同公司岗位升职链，展示从当前岗位向上的候选路径。</p>

		{#if !loadingJobs && !loadError}
			<div class="mt-3 flex flex-wrap items-end gap-3">
				<div class="min-w-[260px] flex-1 rounded-xl border border-black/10 bg-white/70 p-3 dark:border-white/15 dark:bg-white/5">
					<p class="text-xs text-75">起始岗位</p>
					<p class="mt-1 text-sm font-medium">{promotionJob ? `${promotionJob.title} | ${promotionJob.company}` : "未选择"}</p>
					<button
						type="button"
						onclick={() => openPicker("promotion")}
						class="mt-2 rounded-lg border border-black/15 px-3 py-1 text-xs transition hover:opacity-80 dark:border-white/20"
					>
						选择岗位
					</button>
				</div>
				<button
					type="button"
					onclick={runPromotionPath}
					disabled={promotionLoading}
					class="rounded-xl border border-[var(--primary)] bg-[var(--btn-regular-bg)] px-4 py-2 text-sm font-medium text-[var(--primary)] transition hover:opacity-90 disabled:opacity-60"
				>
					{promotionLoading ? "查询中..." : "查询升职路径"}
				</button>
			</div>
		{/if}

		{#if promotionError}
			<p class="mt-3 text-sm text-rose-500">{promotionError}</p>
		{/if}

		{#if promotionResult}
			<div class="mt-4 space-y-3 text-sm">
				{#if promotionResult.paths.length > 0}
					{#each promotionResult.paths as path, idx (`path-${idx}`)}
						<div class="rounded-xl border border-black/10 bg-white/70 p-3 dark:border-white/15 dark:bg-white/5">
							<p class="text-xs text-75">路径 {idx + 1} · 共 {path.hops} 步</p>
							<div class="mt-2 flex flex-wrap items-center gap-2">
								{#each path.nodes as node, nidx (`${node.id}-${nidx}`)}
									<span class="rounded-full border border-black/15 px-3 py-1 text-xs dark:border-white/20">{node.title}</span>
									{#if nidx < path.nodes.length - 1}
										<span class="text-xs text-75">-></span>
									{/if}
								{/each}
							</div>
						</div>
					{/each}
				{:else}
					<p class="rounded-xl border border-dashed border-black/20 p-3 text-sm text-75 dark:border-white/20">
						当前岗位暂未找到升职链路。可以先运行同公司升职关系构建脚本后再查询。
					</p>
				{/if}

				{#if promotionResult.next_steps.length > 0}
					<div class="rounded-xl border border-black/10 bg-white/70 p-3 dark:border-white/15 dark:bg-white/5">
						<p class="text-xs font-semibold text-75">可直接晋升的下一步岗位</p>
						<div class="mt-2 grid gap-2 md:grid-cols-2">
							{#each promotionResult.next_steps as item (item.id)}
								<div class="rounded-lg border border-black/10 px-2 py-1 text-xs dark:border-white/15">
									<div class="font-medium">{item.title}</div>
									<div class="text-75">{item.company}</div>
									<div class="text-75">exp_gap: {item.exp_gap} | score_gap: {item.score_gap}</div>
								</div>
							{/each}
						</div>
					</div>
				{/if}
			</div>
		{/if}
	</section>
</div>

<JobPickerModal
	open={pickerOpen}
	modalTitle={pickerTitle()}
	selectedJobId={selectedJobIdForPicker()}
	onClose={closePicker}
	onSelect={handlePick}
/>
