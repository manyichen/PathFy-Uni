<script lang="ts">
	import { onMount } from "svelte";
	import { url } from "@utils/url-utils";
	import { getToken, getUser, MATCH_CACHE_KEY_PREFIX } from "@/lib/auth";
	import JobDetailDrawer from "@components/jobs/JobDetailDrawer.svelte";
	import { fetchJobDetail, type JobCardItem, type JobDetailItem } from "@/lib/jobs";
	import {
		fetchMyResumes,
		postMatchPreview,
		type LlmTop5Item,
		type MatchLlmBlock,
		type MatchPreviewJob,
		type MatchStudentPayload,
		type MyResumeSummary,
	} from "@/lib/match";
	import { emptyCapabilityScores } from "@/lib/radar-geometry";
	import StudentCapabilityRadar from "./StudentCapabilityRadar.svelte";
	import MatchPairRadar from "./MatchPairRadar.svelte";

	let myResumes = $state<MyResumeSummary[]>([]);
	let resumesError = $state("");

	let selectedResumeId = $state<number | "">("");

	let q = $state("");
	let locationQ = $state("");
	/** fit=匹配适合岗位；stretch=冲刺高质岗位（粗排/精排策略不同） */
	let matchGoal = $state<"fit" | "stretch">("fit");
	let refineLlm = $state(true);

	let loading = $state(false);
	let runError = $state("");
	let resultStudent = $state<MatchStudentPayload | null>(null);
	let resultJobs = $state<MatchPreviewJob[]>([]);
	let resultStats = $state<{
		scanned: number;
		returned: number;
		match_top_k_return?: number;
		match_llm_pool_k?: number;
		llm_pool_size?: number;
	} | null>(null);
	let llmBlock = $state<MatchLlmBlock | null>(null);

	let jobDetailOpen = $state(false);
	let jobDetailLoading = $state(false);
	let jobDetailError = $state("");
	let jobDetailData = $state<JobDetailItem | null>(null);

	async function openJobDetail(jobId: string): Promise<void> {
		const id = jobId.trim();
		if (!id) return;
		jobDetailOpen = true;
		jobDetailLoading = true;
		jobDetailError = "";
		jobDetailData = null;
		try {
			jobDetailData = await fetchJobDetail(id);
		} catch (e) {
			jobDetailError = e instanceof Error ? e.message : "加载岗位详情失败";
		} finally {
			jobDetailLoading = false;
		}
	}

	function closeJobDetail(): void {
		jobDetailOpen = false;
	}

	const previewScores = $derived.by((): JobCardItem["scores"] => {
		if (selectedResumeId !== "" && myResumes.length) {
			const id = Number(selectedResumeId);
			const r = myResumes.find((x) => x.id === id);
			if (r?.scores) return { ...r.scores };
		}
		return emptyCapabilityScores();
	});

	const jobsById = $derived.by(() => new Map(resultJobs.map((j) => [j.id, j])));

	const previewLabel = $derived.by(() => {
		if (selectedResumeId !== "" && myResumes.length) {
			const id = Number(selectedResumeId);
			const r = myResumes.find((x) => x.id === id);
			if (r) return `#${r.id} ${r.name} · ${r.major}（均分 ${r.score_avg}）`;
		}
		return "请选择上方画像记录";
	});

	onMount(async () => {
		const resumes = await fetchMyResumes().catch(() => []);
		myResumes = resumes;

		if (myResumes.length) {
			selectedResumeId = myResumes[0].id;
		}

		if (tryRestoreMatchState()) {
			/* 已从本机恢复上次匹配结果 */
		}

		if (!resumes.length && getToken()) {
			resumesError = "暂无已保存的能力画像。请先到「能力画像」页上传简历生成画像。";
		}
		if (!resumes.length && !getToken()) {
			resumesError = "登录后可使用「我的能力画像」并开始匹配。";
		}
	});

	async function runMatch() {
		if (!getToken()) {
			runError = "使用能力画像请先登录。";
			return;
		}
		if (selectedResumeId === "" || !myResumes.length) {
			runError = "请先在能力画像页生成并保存画像。";
			return;
		}
		runError = "";
		loading = true;
		resultStudent = null;
		resultJobs = [];
		resultStats = null;
		llmBlock = null;
		try {
			const base = {
				q: q.trim(),
				location_q: locationQ.trim(),
				refine_with_llm: refineLlm,
				match_goal: matchGoal,
			};
			const data = await postMatchPreview({
				...base,
				resume_id: Number(selectedResumeId),
			});
			resultStudent = data.student;
			resultJobs = data.jobs || [];
			const st = data.stats;
			resultStats = st
				? {
						scanned: st.scanned,
						returned: st.returned,
						match_top_k_return: st.match_top_k_return,
						match_llm_pool_k: st.match_llm_pool_k,
						llm_pool_size: st.llm_pool_size,
					}
				: null;
			llmBlock = data.llm ?? null;
			persistMatchState();
		} catch (e) {
			runError = e instanceof Error ? e.message : "请求失败";
		} finally {
			loading = false;
		}
	}

	async function copyId(id: string) {
		try {
			await navigator.clipboard.writeText(id);
		} catch {
			/* ignore */
		}
	}

	function top5JobScoresForRadar(row: LlmTop5Item): JobCardItem["scores"] | null {
		const fromRow = row.scores;
		const fromList = jobsById.get(row.job_id)?.scores;
		const raw = fromRow ?? fromList;
		if (!raw) return null;
		return { ...emptyCapabilityScores(), ...raw };
	}

	/** 旧版缓存：含示例画像 sourceMode=mock，已废弃，恢复时跳过 */
	type MatchPageCacheV1 = {
		v: 1;
		student: MatchStudentPayload;
		jobs: MatchPreviewJob[];
		resultStats: {
			scanned: number;
			returned: number;
			match_top_k_return?: number;
			match_llm_pool_k?: number;
			llm_pool_size?: number;
		} | null;
		llmBlock: MatchLlmBlock | null;
		q: string;
		locationQ: string;
		matchGoal?: "fit" | "stretch";
		refineLlm: boolean;
		sourceMode?: "resume" | "mock";
		selectedResumeId: number | "";
		selectedMockId?: string;
	};

	type MatchPageCacheV2 = {
		v: 2;
		student: MatchStudentPayload;
		jobs: MatchPreviewJob[];
		resultStats: {
			scanned: number;
			returned: number;
			match_top_k_return?: number;
			match_llm_pool_k?: number;
			llm_pool_size?: number;
		} | null;
		llmBlock: MatchLlmBlock | null;
		q: string;
		locationQ: string;
		matchGoal?: "fit" | "stretch";
		refineLlm: boolean;
		selectedResumeId: number | "";
	};

	function matchStateStorageKey(): string {
		const u = getUser();
		return `${MATCH_CACHE_KEY_PREFIX}${u?.id ?? "guest"}`;
	}

	function persistMatchState(): void {
		if (!resultStudent) return;
		try {
			const payload: MatchPageCacheV2 = {
				v: 2,
				student: resultStudent,
				jobs: resultJobs,
				resultStats,
				llmBlock,
				q,
				locationQ,
				matchGoal,
				refineLlm,
				selectedResumeId,
			};
			localStorage.setItem(matchStateStorageKey(), JSON.stringify(payload));
		} catch {
			/* ignore quota */
		}
	}

	function tryRestoreMatchState(): boolean {
		try {
			const raw = localStorage.getItem(matchStateStorageKey());
			if (!raw) return false;
			const o = JSON.parse(raw) as MatchPageCacheV1 | MatchPageCacheV2;
			if (!o?.student || !Array.isArray(o.jobs)) return false;

			if (o.v === 2) {
				const rid = o.selectedResumeId;
				if (rid === "" || !myResumes.some((x) => x.id === rid)) return false;
			} else if (o.v === 1) {
				if (o.sourceMode === "mock") return false;
				const rid = o.selectedResumeId;
				if (rid === "" || !myResumes.some((x) => x.id === rid)) return false;
			} else {
				return false;
			}

			resultStudent = o.student;
			resultJobs = o.jobs;
			resultStats = o.resultStats;
			llmBlock = o.llmBlock;
			q = o.q ?? "";
			locationQ = o.locationQ ?? "";
			matchGoal = o.matchGoal === "stretch" ? "stretch" : "fit";
			refineLlm = typeof o.refineLlm === "boolean" ? o.refineLlm : true;
			selectedResumeId = o.selectedResumeId;
			return true;
		} catch {
			return false;
		}
	}
</script>

<div class="space-y-8">
	<div class="grid gap-8 lg:grid-cols-2 lg:items-start">
		<div
			class="rounded-2xl border border-black/10 bg-[var(--card-bg)] p-6 dark:border-white/10 md:p-8"
		>
			<h2 class="mb-4 text-lg font-semibold text-black dark:text-white">匹配条件</h2>
		{#if resumesError}
			<div
				class="mb-4 rounded-xl border border-sky-500/30 bg-sky-500/10 px-4 py-3 text-sm text-sky-950 dark:text-sky-100"
			>
				{resumesError}
			</div>
		{/if}
		<div class="grid gap-4 md:grid-cols-2">
			<div class="space-y-2 md:col-span-2">
				<label class="block text-sm font-medium text-75" for="pj-resume">选用画像记录</label>
				<select
					id="pj-resume"
					bind:value={selectedResumeId}
					class="w-full rounded-xl border border-black/10 bg-[var(--btn-regular-bg)] px-3 py-2.5 text-sm text-black dark:border-white/10 dark:text-white"
					disabled={!myResumes.length}
				>
					{#each myResumes as r (r.id)}
						<option value={r.id}>
							#{r.id} {r.name} · {r.major}（均分 {r.score_avg}）
						</option>
					{/each}
				</select>
			</div>
			<div class="space-y-2 md:col-span-2">
				<label class="block text-sm font-medium text-75" for="pj-q">岗位关键词（可选）</label>
				<input
					id="pj-q"
					type="text"
					bind:value={q}
					placeholder="职位名称、公司或地点"
					class="w-full rounded-xl border border-black/10 bg-[var(--btn-regular-bg)] px-3 py-2.5 text-sm dark:border-white/10 dark:text-white"
				/>
			</div>
			<div class="space-y-2 md:col-span-2">
				<label class="block text-sm font-medium text-75" for="pj-loc">地点包含（可选）</label>
				<input
					id="pj-loc"
					type="text"
					bind:value={locationQ}
					placeholder="例如：上海"
					class="w-full rounded-xl border border-black/10 bg-[var(--btn-regular-bg)] px-3 py-2.5 text-sm dark:border-white/10 dark:text-white"
				/>
			</div>
			<div class="space-y-2 md:col-span-2">
				<span class="block text-sm font-medium text-75">匹配策略</span>
				<div class="flex flex-wrap gap-4 text-sm text-black dark:text-white">
					<label class="flex cursor-pointer items-center gap-2">
						<input type="radio" name="pj-goal" bind:group={matchGoal} value="fit" />
						匹配适合岗位
					</label>
					<label class="flex cursor-pointer items-center gap-2">
						<input type="radio" name="pj-goal" bind:group={matchGoal} value="stretch" />
						冲刺高质岗位
					</label>
				</div>
				<p class="text-xs leading-relaxed text-50">
					适合：按八维缺口加权分优先，更贴近「能胜任、吻合度高」。冲刺：在匹配分达到底线的前提下，更优先「岗位八维需求更高」的挑战岗，精排文案侧重成长与准备路径。
				</p>
			</div>
		</div>

		<div class="mt-4 flex flex-wrap items-center gap-4">
			<label class="flex cursor-pointer items-center gap-2 text-sm text-75">
				<input type="checkbox" bind:checked={refineLlm} class="accent-[var(--primary)]" />
				开启智能精排与匹配说明（推荐）
			</label>
			<button
				type="button"
				class="rounded-xl bg-[var(--primary)] px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:opacity-90 disabled:opacity-50"
				disabled={loading || selectedResumeId === "" || !myResumes.length}
				onclick={() => void runMatch()}
			>
				{loading ? "匹配中…" : "开始匹配"}
			</button>
			<a
				href={url("/jobs")}
				class="text-sm font-medium text-[var(--primary)] underline-offset-2 hover:underline"
			>
				岗位探索
			</a>
		</div>

			{#if runError}
				<p class="mt-3 text-sm text-red-600 dark:text-red-400">{runError}</p>
			{/if}
		</div>

		<aside
			class="rounded-2xl border border-black/10 bg-[var(--card-bg)] p-6 dark:border-white/10 md:p-8 lg:sticky lg:top-20"
		>
			<h2 class="mb-2 text-lg font-semibold text-black dark:text-white">所选画像 · 八维雷达</h2>
			<p class="mb-4 text-sm leading-relaxed text-75">{previewLabel}</p>
			<StudentCapabilityRadar scores={previewScores} />
		</aside>
	</div>

	{#if resultStudent}
		<div
			class="rounded-2xl border border-black/10 bg-[var(--card-bg)] p-6 dark:border-white/10 md:p-8"
		>
			<h2 class="mb-3 text-lg font-semibold text-black dark:text-white">当前画像</h2>
			<p class="text-base font-medium text-black dark:text-white">
				{resultStudent.display_name || resultStudent.id}
			</p>
			{#if resultStudent.education}
				<p class="mt-1 text-sm text-75">{resultStudent.education}</p>
			{/if}
			<div class="mt-3 flex flex-wrap gap-2 text-xs text-75">
				<span
					class="rounded-lg bg-[var(--btn-regular-bg)] px-2 py-1 font-mono tabular-nums text-[var(--primary)]"
				>
					八维均分 {resultStudent.score_avg ?? "—"}
				</span>
				{#if resultStudent.city_pref}
					<span class="rounded-lg bg-[var(--btn-regular-bg)] px-2 py-1">期望 {resultStudent.city_pref}</span>
				{/if}
			</div>
			{#if resultStudent.skills_hint?.length}
				<div class="mt-3 flex flex-wrap gap-2">
					{#each resultStudent.skills_hint as s (s)}
						<span
							class="rounded-lg border border-black/10 px-2 py-0.5 text-xs dark:border-white/10"
							>{s}</span
						>
					{/each}
				</div>
			{/if}
		</div>
	{/if}

	{#if llmBlock}
		<div
			class="rounded-2xl border border-black/10 bg-[var(--card-bg)] p-6 dark:border-white/10 md:p-8"
		>
			<h2 class="mb-1 text-lg font-semibold text-black dark:text-white">智能推荐（前 5）</h2>
			{#if llmBlock.ok && llmBlock.top5?.length}
				<p class="mb-4 text-xs text-50">以下为结合岗位与画像的优先推荐。</p>
				<div class="space-y-4">
					{#each llmBlock.top5 as row (row.job_id + String(row.rank))}
						<div
							class="rounded-xl border border-[var(--primary)]/25 bg-[var(--primary)]/5 p-4 dark:border-[var(--primary)]/30"
						>
							<div
								class="grid gap-4 md:grid-cols-[minmax(0,1fr)_clamp(14rem,32vw,22rem)] md:items-stretch"
							>
								<div class="min-w-0">
									<div class="flex flex-wrap items-start justify-between gap-2">
										<div class="min-w-0">
											<p class="text-xs font-medium text-[var(--primary)]">第 {row.rank} 名</p>
											<p class="text-base font-semibold text-black dark:text-white">
												{row.title || "（无标题）"}
											</p>
											<p class="text-sm text-75">{row.company || ""} · {row.location || ""}</p>
										</div>
										<p
											class="shrink-0 font-mono text-xl font-bold tabular-nums text-[var(--primary)] md:hidden"
										>
											{row.overall_fit_0_100}
										</p>
									</div>
									<p class="mt-2 text-sm leading-relaxed text-75">{row.one_line}</p>
									{#if row.strengths?.length}
										<p class="mt-2 text-xs font-semibold text-black dark:text-white">优势</p>
										<ul class="mt-1 list-inside list-disc text-sm text-75">
											{#each row.strengths as t (t)}
												<li>{t}</li>
											{/each}
										</ul>
									{/if}
									{#if row.gaps?.length}
										<p class="mt-2 text-xs font-semibold text-black dark:text-white">缺口</p>
										<ul class="mt-1 list-inside list-disc text-sm text-75">
											{#each row.gaps as t (t)}
												<li>{t}</li>
											{/each}
										</ul>
									{/if}
									{#if row.risks?.length}
										<p class="mt-2 text-xs font-semibold text-amber-800 dark:text-amber-200">风险</p>
										<ul
											class="mt-1 list-inside list-disc text-sm text-amber-900/90 dark:text-amber-100/90"
										>
											{#each row.risks as t (t)}
												<li>{t}</li>
											{/each}
										</ul>
									{/if}
									{#if row.llm_fallback}
										<p class="mt-2 text-xs text-50">（该条由系统按匹配分顺序补位）</p>
									{/if}
									<div
										class="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-black/10 pt-3 text-xs text-75 dark:border-white/10"
									>
										<span class="min-w-0 truncate font-medium text-black dark:text-white">
											{row.title || "岗位"} :: {row.company || "公司"}
										</span>
									</div>
									<div class="mt-2 flex flex-wrap gap-2">
										<code class="rounded bg-black/5 px-2 py-0.5 text-[11px] dark:bg-white/10"
											>{row.job_id}</code
										>
										<button
											type="button"
											class="text-xs text-[var(--primary)] underline-offset-2 hover:underline"
											onclick={() => void copyId(row.job_id)}
										>
											复制 ID
										</button>
										<button
											type="button"
											class="text-xs text-[var(--primary)] underline-offset-2 hover:underline"
											onclick={() => void openJobDetail(row.job_id)}
										>
											岗位详情页
										</button>
									</div>
								</div>
								<div
									class="pj-radar-col flex min-h-[17rem] flex-col items-center gap-1 border-t border-black/10 pt-3 md:min-h-0 md:border-t-0 md:border-l md:pl-5 md:pt-0 dark:border-white/10"
								>
									<div class="hidden shrink-0 text-center md:block">
										<p class="font-mono text-3xl font-bold tabular-nums text-[var(--primary)]">
											{row.overall_fit_0_100}
										</p>
										<p class="text-[11px] font-medium text-50">匹配度</p>
									</div>
									{#if resultStudent?.scores}
										{@const jobRadarScores = top5JobScoresForRadar(row)}
										{#if jobRadarScores}
											<div class="flex w-full min-h-0 flex-1 flex-col items-stretch">
												<MatchPairRadar
													layout="fill"
													studentScores={resultStudent.scores}
													jobScores={jobRadarScores}
												/>
											</div>
										{:else}
											<p class="max-w-[12rem] text-center text-[11px] text-50">
												暂无八维数据用于对比（岗位可能不在本页返回列表中）。
											</p>
										{/if}
									{:else}
										<p class="max-w-[12rem] text-center text-[11px] text-50">当前无画像八维分，无法绘制对比雷达。</p>
									{/if}
								</div>
							</div>
						</div>
					{/each}
				</div>
			{:else}
				<p class="text-sm text-amber-800 dark:text-amber-200">
					{llmBlock.error || "暂未获得智能推荐结果，请稍后重试或关闭「智能精排」仅查看列表匹配。"}
				</p>
			{/if}
		</div>
	{/if}

	{#if resultJobs.length}
		<div
			class="rounded-2xl border border-black/10 bg-[var(--card-bg)] p-6 dark:border-white/10 md:p-8"
		>
			<div class="mb-4 flex flex-wrap items-end justify-between gap-2">
				<h2 class="text-lg font-semibold text-black dark:text-white">岗位匹配列表</h2>
				{#if resultStats}
					<p class="text-xs text-50">
						在岗位库中浏览了 {resultStats.scanned} 条，按匹配度展示其中 {resultStats.returned} 条。
					</p>
				{/if}
			</div>
			<div class="max-h-[28rem] space-y-3 overflow-y-auto pr-1">
				{#each resultJobs as job (job.id)}
					<div
						class="rounded-xl border border-black/10 bg-[var(--btn-regular-bg)]/40 p-4 dark:border-white/10"
					>
						<div class="flex flex-wrap items-start justify-between gap-2">
							<div>
								<p class="font-semibold text-black dark:text-white">{job.title}</p>
								<p class="text-sm text-75">{job.company} · {job.location}</p>
								<p class="mt-1 text-xs text-50">{job.salary}</p>
							</div>
							<div class="text-right">
								<p
									class="font-mono text-lg font-bold tabular-nums text-[var(--primary)]"
								>
									{job.match_preview.match_score}
								</p>
								<p class="text-xs text-50">匹配度</p>
							</div>
						</div>
						<div class="mt-2 flex flex-wrap items-center gap-2">
							<code
								class="max-w-full truncate rounded bg-black/5 px-2 py-0.5 text-[11px] dark:bg-white/10"
								>{job.id}</code
							>
							<button
								type="button"
								class="text-xs font-medium text-[var(--primary)] underline-offset-2 hover:underline"
								onclick={() => void copyId(job.id)}
							>
								复制 ID
							</button>
							<button
								type="button"
								class="text-xs font-medium text-[var(--primary)] underline-offset-2 hover:underline"
								onclick={() => void openJobDetail(job.id)}
							>
								岗位详情页
							</button>
						</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<JobDetailDrawer
		open={jobDetailOpen}
		loading={jobDetailLoading}
		error={jobDetailError}
		detail={jobDetailData}
		onClose={closeJobDetail}
	/>
</div>

<style>
	@media (min-width: 768px) {
		.pj-radar-col {
			min-height: 100%;
		}
	}
</style>
