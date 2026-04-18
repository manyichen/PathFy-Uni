<script lang="ts">
	import { onMount } from "svelte";
	import { url } from "@utils/url-utils";
	import {
		fetchMockProfiles,
		postMatchPreview,
		type MatchLlmBlock,
		type MatchPreviewJob,
		type MatchStudentPayload,
		type MockProfileSummary,
	} from "@/lib/match";

	let profiles = $state<MockProfileSummary[]>([]);
	let profilesError = $state("");
	let selectedId = $state("");

	let q = $state("");
	let locationQ = $state("");
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

	onMount(async () => {
		try {
			profiles = await fetchMockProfiles();
			if (profiles.length) {
				selectedId = profiles[0].id;
			}
		} catch (e) {
			profilesError =
				e instanceof Error
					? e.message
					: "加载虚构画像失败。请确认后端已设置 ENABLE_MOCK_PROFILE_API=1 并已重启。";
		}
	});

	async function runMatch() {
		if (!selectedId) {
			runError = "请先选择一个测试画像。";
			return;
		}
		runError = "";
		loading = true;
		resultStudent = null;
		resultJobs = [];
		resultStats = null;
		llmBlock = null;
		try {
			const data = await postMatchPreview({
				profile_id: selectedId,
				q: q.trim(),
				location_q: locationQ.trim(),
				refine_with_llm: refineLlm,
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
</script>

<div class="space-y-8">
	<div
		class="rounded-2xl border border-black/10 bg-[var(--card-bg)] p-6 dark:border-white/10 md:p-8"
	>
		<h2 class="mb-4 text-lg font-semibold text-black dark:text-white">匹配条件</h2>
		{#if profilesError}
			<div
				class="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-900 dark:text-amber-100"
			>
				{profilesError}
			</div>
		{/if}

		<div class="grid gap-4 md:grid-cols-2">
			<div class="space-y-2">
				<label class="block text-sm font-medium text-75" for="pj-profile">测试画像</label>
				<select
					id="pj-profile"
					bind:value={selectedId}
					class="w-full rounded-xl border border-black/10 bg-[var(--btn-regular-bg)] px-3 py-2.5 text-sm text-black dark:border-white/10 dark:text-white"
					disabled={!profiles.length}
				>
					{#each profiles as p (p.id)}
						<option value={p.id}>{p.display_name}</option>
					{/each}
				</select>
			</div>
			<p class="text-xs text-50 md:col-span-2">
				粗排返回条数与 LLM 候选池由服务端 <code class="rounded bg-[var(--btn-regular-bg)] px-1 py-0.5"
					>MATCH_TOP_K_RETURN</code
				>
				、<code class="rounded bg-[var(--btn-regular-bg)] px-1 py-0.5">MATCH_LLM_POOL_K</code>（<code
					class="rounded bg-[var(--btn-regular-bg)] px-1 py-0.5">backend/.env</code
				>）配置；匹配后在结果区可见实际取值。
			</p>
			<div class="space-y-2 md:col-span-2">
				<label class="block text-sm font-medium text-75" for="pj-q">岗位关键词（可选）</label>
				<input
					id="pj-q"
					type="text"
					bind:value={q}
					placeholder="标题 / 公司 / 地点 模糊匹配"
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
		</div>

		<div class="mt-4 flex flex-wrap items-center gap-4">
			<label class="flex cursor-pointer items-center gap-2 text-sm text-75">
				<input type="checkbox" bind:checked={refineLlm} class="accent-[var(--primary)]" />
				DeepSeek 精排 Top5 与文字分析（需 backend 配置 DEEPSEEK_API_KEY）
			</label>
			<button
				type="button"
				class="rounded-xl bg-[var(--primary)] px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:opacity-90 disabled:opacity-50"
				disabled={loading || !selectedId}
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
			<h2 class="mb-1 text-lg font-semibold text-black dark:text-white">精排 Top 5（大模型）</h2>
			{#if llmBlock.ok && llmBlock.top5?.length}
				<p class="mb-4 text-xs text-50">
					模型 {llmBlock.model ?? "—"} · 候选池 {llmBlock.pool_size ?? "—"} 条
				</p>
				<div class="space-y-4">
					{#each llmBlock.top5 as row (row.job_id + String(row.rank))}
						<div
							class="rounded-xl border border-[var(--primary)]/25 bg-[var(--primary)]/5 p-4 dark:border-[var(--primary)]/30"
						>
							<div class="flex flex-wrap items-start justify-between gap-2">
								<div>
									<p class="text-xs font-medium text-[var(--primary)]">第 {row.rank} 名</p>
									<p class="text-base font-semibold text-black dark:text-white">
										{row.title || "（无标题）"}
									</p>
									<p class="text-sm text-75">{row.company || ""} · {row.location || ""}</p>
								</div>
								<p class="font-mono text-xl font-bold tabular-nums text-[var(--primary)]">
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
								<p class="mt-2 text-xs text-50">（该条为服务端按粗排补位）</p>
							{/if}
							<div class="mt-3 flex flex-wrap gap-2">
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
								<a
									href={url(`/jobs/${encodeURIComponent(row.job_id)}`)}
									class="text-xs text-[var(--primary)] underline-offset-2 hover:underline"
								>
									岗位详情页
								</a>
							</div>
						</div>
					{/each}
				</div>
			{:else}
				<p class="text-sm text-amber-800 dark:text-amber-200">
					{llmBlock.error || "未返回精排结果（可检查 DEEPSEEK_API_KEY 与网络）。"}
				</p>
			{/if}
		</div>
	{/if}

	{#if resultJobs.length}
		<div
			class="rounded-2xl border border-black/10 bg-[var(--card-bg)] p-6 dark:border-white/10 md:p-8"
		>
			<div class="mb-4 flex flex-wrap items-end justify-between gap-2">
				<h2 class="text-lg font-semibold text-black dark:text-white">粗排结果</h2>
				{#if resultStats}
					<p class="text-xs text-50">
						扫描 {resultStats.scanned} 条 · 配置 Top {resultStats.match_top_k_return ?? "—"} · 实际返回
						{resultStats.returned}
						{#if resultStats.match_llm_pool_k != null}
							· LLM 候选配置 {resultStats.match_llm_pool_k} · 实际入池 {resultStats.llm_pool_size ?? "—"}
						{/if}
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
								<p class="text-xs text-50">粗排分</p>
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
						</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}
</div>
