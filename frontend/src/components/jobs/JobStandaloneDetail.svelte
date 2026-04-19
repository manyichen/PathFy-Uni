<script lang="ts">
	import { onMount } from "svelte";
	import { url } from "@utils/url-utils";
	import { fetchJobDetail, type JobDetailItem } from "@/lib/jobs";
	import StudentCapabilityRadar from "@/components/match/StudentCapabilityRadar.svelte";

	function normalizeText(text: string): string {
		return text.replace(/<br\s*\/?>/gi, "\n").replace(/&nbsp;/gi, " ").trim();
	}

	let jobId = $state("");
	let loading = $state(true);
	let errorMessage = $state("");
	let detail = $state<JobDetailItem | null>(null);

	async function load(id: string) {
		const trimmed = id.trim();
		if (!trimmed) {
			loading = false;
			errorMessage = "缺少岗位 ID。请从人岗匹配或岗位探索中的链接打开本页。";
			detail = null;
			return;
		}
		loading = true;
		errorMessage = "";
		detail = null;
		try {
			detail = await fetchJobDetail(trimmed);
		} catch (e) {
			errorMessage = e instanceof Error ? e.message : "加载失败";
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		const sp = new URLSearchParams(window.location.search);
		jobId = sp.get("id")?.trim() ?? "";
		void load(jobId);
	});
</script>

<section class="space-y-6">
	<nav class="text-sm text-75">
		<a href={url("/jobs")} class="text-[var(--primary)] underline-offset-2 hover:underline">岗位探索</a>
		<span class="mx-2 opacity-50">/</span>
		<a href={url("/match")} class="text-[var(--primary)] underline-offset-2 hover:underline">人岗匹配</a>
	</nav>

	{#if loading}
		<div
			class="rounded-2xl border border-black/10 bg-[var(--card-bg)] p-8 text-center text-sm text-75 dark:border-white/10"
		>
			岗位详情加载中…
		</div>
	{:else if errorMessage}
		<div
			class="rounded-2xl border border-red-500/25 bg-red-500/5 p-6 text-sm text-red-800 dark:text-red-200"
		>
			{errorMessage}
		</div>
	{:else if detail}
		<header class="space-y-2">
			<h1 class="text-2xl font-bold text-black dark:text-white">{detail.title}</h1>
			<p class="text-sm text-75">
				{detail.company} · {detail.location}
				{#if detail.salary}
					<span class="mx-1 opacity-40">|</span>
					{detail.salary}
				{/if}
			</p>
			<div class="flex flex-wrap gap-2 text-xs text-75">
				<code
					class="rounded-lg bg-black/5 px-2 py-1 font-mono text-[11px] dark:bg-white/10"
					>{detail.id}</code
				>
				{#if detail.experience_text}
					<span class="rounded-lg bg-[var(--btn-regular-bg)] px-2 py-1">经验 {detail.experience_text}</span>
				{/if}
				{#if detail.industry}
					<span class="rounded-lg bg-[var(--btn-regular-bg)] px-2 py-1">{detail.industry}</span>
				{/if}
			</div>
		</header>

		<div
			class="grid gap-8 rounded-2xl border border-black/10 bg-[var(--card-bg)] p-6 dark:border-white/10 md:grid-cols-[minmax(0,1fr)_280px] md:items-start"
		>
			<div class="space-y-6 text-sm text-75">
				{#if detail.company_detail}
					<section class="space-y-2">
						<h2 class="text-base font-semibold text-black dark:text-white">公司介绍</h2>
						<p class="leading-relaxed whitespace-pre-wrap">{normalizeText(detail.company_detail)}</p>
					</section>
				{/if}

				{#if detail.demand}
					<section class="space-y-2">
						<h2 class="text-base font-semibold text-black dark:text-white">岗位职责</h2>
						<p class="leading-relaxed whitespace-pre-wrap">{normalizeText(detail.demand)}</p>
					</section>
				{/if}

				{#if detail.internship_req}
					<section class="space-y-2">
						<h2 class="text-base font-semibold text-black dark:text-white">实习/任职要求</h2>
						<p class="leading-relaxed whitespace-pre-wrap">{normalizeText(detail.internship_req)}</p>
					</section>
				{/if}

				{#if detail.requirements?.length}
					<section class="space-y-2">
						<h2 class="text-base font-semibold text-black dark:text-white">关联能力要求</h2>
						<div class="flex flex-wrap gap-2">
							{#each detail.requirements as req (req.name + req.label)}
								<span
									class="rounded-lg border border-black/10 px-2 py-1 text-xs dark:border-white/10"
								>
									{req.name}{req.level ? `（${req.level}）` : ""}
								</span>
							{/each}
						</div>
					</section>
				{/if}

				{#if detail.cap_evidence?.length}
					<section class="space-y-2">
						<h2 class="text-base font-semibold text-black dark:text-white">能力证据片段</h2>
						<ul class="list-inside list-disc space-y-1">
							{#each detail.cap_evidence as ev (ev)}
								<li>{ev}</li>
							{/each}
						</ul>
					</section>
				{/if}

				{#if detail.source_url}
					<p>
						<a
							href={detail.source_url}
							target="_blank"
							rel="noreferrer"
							class="font-medium text-[var(--primary)] underline-offset-2 hover:underline"
							>查看原始岗位页面</a
						>
					</p>
				{/if}
			</div>

			<aside
				class="rounded-xl border border-black/10 bg-[var(--btn-regular-bg)]/30 p-4 dark:border-white/10"
			>
				<h2 class="mb-2 text-center text-sm font-semibold text-black dark:text-white">岗位八维需求</h2>
				<p class="mb-3 text-center text-xs text-75">与探索页一致的能力维度（0–100）</p>
				<StudentCapabilityRadar scores={detail.scores} />
				<p class="mt-2 text-center font-mono text-xs tabular-nums text-[var(--primary)]">
					八维均分 {detail.score_avg}
				</p>
			</aside>
		</div>
	{/if}
</section>
