<script lang="ts">
	import JobDetailDrawer from "@components/jobs/JobDetailDrawer.svelte";
	import { fetchJobDetail, type JobDetailItem } from "@/lib/api/jobs";
	import { fetchRandomBrowseTargets, manualSearchTargets, type ReportTargetItem } from "@/lib/api/report";

	type OnClose = () => void;
	type OnSelect = (target: ReportTargetItem) => void;
	type OnRemove = (jobId: string) => void;

	const {
		open = false,
		modalTitle = "搜索候选岗位",
		selectedTargets = [] as ReportTargetItem[],
		maxTargets = 5,
		onClose = (() => {}) as OnClose,
		onSelect = ((_: ReportTargetItem) => {}) as OnSelect,
		onRemove = ((_: string) => {}) as OnRemove,
	} = $props<{
		open?: boolean;
		modalTitle?: string;
		selectedTargets?: ReportTargetItem[];
		maxTargets?: number;
		onClose?: OnClose;
		onSelect?: OnSelect;
		onRemove?: OnRemove;
	}>();

	const PAGE_SIZE = 20;

	let searchQ = $state("");
	let searchLocation = $state("");
	let loading = $state(false);
	let error = $state("");
	let info = $state("");
	let results = $state<ReportTargetItem[]>([]);
	let listMode = $state<"random" | "search">("random");
	let browseSeed = $state("");
	let currentPage = $state(1);
	let totalPages = $state(1);
	let totalCount = $state(0);
	let wasOpen = false;

	let jobDetailOpen = $state(false);
	let jobDetailLoading = $state(false);
	let jobDetailError = $state("");
	let jobDetailData = $state<JobDetailItem | null>(null);

	const selectedSet = $derived.by(
		() => new Set(selectedTargets.map((x) => String(x.job_id || "").trim()).filter(Boolean)),
	);
	const atLimit = $derived.by(() => selectedTargets.length >= maxTargets);

	function portal(node: HTMLElement) {
		if (typeof document === "undefined") return;
		document.body.appendChild(node);
		return {
			destroy() {
				node.parentNode?.removeChild(node);
			},
		};
	}

	function isSelected(jobId: string): boolean {
		return selectedSet.has(String(jobId || "").trim());
	}

	function targetLabel(target: ReportTargetItem): string {
		const title = String(target.title || target.job_id || "未知岗位").trim();
		const company = String(target.company || "未知公司").trim();
		return `${title}-${company}`;
	}

	function newBrowseSeed(): string {
		if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
			return crypto.randomUUID();
		}
		return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
	}

	async function loadRandomPage(page: number): Promise<void> {
		if (!browseSeed) return;
		error = "";
		info = "";
		loading = true;
		try {
			const data = await fetchRandomBrowseTargets({
				seed: browseSeed,
				page,
				page_size: PAGE_SIZE,
			});
			results = data?.targets || [];
			currentPage = data?.page || page;
			totalPages = data?.total_pages || 1;
			totalCount = data?.total || 0;
			listMode = "random";
			info = results.length
				? `随机浏览岗位库（第 ${currentPage}/${totalPages} 页，共 ${totalCount} 条），点击即可加入列表。`
				: "岗位库暂无数据。";
		} catch (e) {
			error = e instanceof Error ? e.message : "加载随机岗位失败";
			results = [];
		} finally {
			loading = false;
		}
	}

	async function goToPage(page: number): Promise<void> {
		if (listMode !== "random" || loading) return;
		const next = Math.max(1, Math.min(totalPages, page));
		if (next === currentPage) return;
		await loadRandomPage(next);
	}

	async function runSearch(): Promise<void> {
		if (!searchQ.trim()) {
			error = "请输入岗位关键词。";
			info = "";
			return;
		}
		error = "";
		info = "";
		loading = true;
		try {
			const data = await manualSearchTargets({
				q: searchQ.trim(),
				location_q: searchLocation.trim(),
				limit: PAGE_SIZE,
			});
			results = data?.targets || [];
			listMode = "search";
			currentPage = 1;
			totalPages = 1;
			totalCount = results.length;
			info = results.length ? `检索到 ${results.length} 个候选岗位，点击即可加入列表。` : "未找到匹配岗位，请调整关键词或地点。";
		} catch (e) {
			error = e instanceof Error ? e.message : "搜索失败";
			results = [];
		} finally {
			loading = false;
		}
	}

	function pickTarget(target: ReportTargetItem): void {
		const jobId = String(target.job_id || "").trim();
		if (!jobId || isSelected(jobId)) return;
		if (atLimit) {
			error = `最多选择 ${maxTargets} 个目标职业。`;
			return;
		}
		error = "";
		onSelect(target);
		info = `已加入「${target.title || jobId}」`;
	}

	function removeTarget(jobId: string): void {
		const id = String(jobId || "").trim();
		if (!id) return;
		error = "";
		onRemove(id);
		info = "";
	}

	async function openJobDetail(jobId: string): Promise<void> {
		const id = String(jobId || "").trim();
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

	$effect(() => {
		if (!open) {
			wasOpen = false;
			return;
		}
		if (!wasOpen) {
			error = "";
			info = "";
			results = [];
			searchQ = "";
			searchLocation = "";
			listMode = "random";
			currentPage = 1;
			totalPages = 1;
			totalCount = 0;
			browseSeed = newBrowseSeed();
			void loadRandomPage(1);
		}
		wasOpen = true;
	});
</script>

{#if open}
	<div
		use:portal
		class="fixed inset-0 z-[200] flex items-start justify-center overflow-y-auto bg-black/45 px-4 pt-16 pb-6"
		role="dialog"
		aria-modal="true"
		aria-labelledby="manual-target-search-title"
		tabindex="-1"
		onkeydown={(event) => {
			if (event.key === "Escape") {
				event.preventDefault();
				if (jobDetailOpen) {
					closeJobDetail();
					return;
				}
				onClose();
			}
		}}
	>
		<button type="button" aria-label="关闭" onclick={onClose} class="absolute inset-0 cursor-default"></button>
		<div
			class="relative z-[1] flex w-full max-w-4xl max-h-[calc(100vh-5rem)] flex-col rounded-2xl border border-black/10 bg-[var(--page-bg)] p-5 shadow-2xl dark:border-white/15"
		>
			<div class="flex items-center justify-between gap-3">
				<h4 id="manual-target-search-title" class="text-base font-semibold text-black dark:text-white">
					{modalTitle}
				</h4>
				<button
					type="button"
					onclick={onClose}
					class="rounded-lg border border-black/15 px-3 py-1 text-xs hover:opacity-80 dark:border-white/20"
				>
					关闭
				</button>
			</div>
			<p class="mt-2 text-xs leading-relaxed text-50">
				从 Neo4j 岗位库检索，点击结果加入目标列表（已选 {selectedTargets.length}/{maxTargets}）。
			</p>

			<div class="mt-3 rounded-xl border border-black/10 bg-[var(--card-bg)] p-3 dark:border-white/10">
				<p class="text-xs font-medium text-75">已选岗位</p>
				{#if selectedTargets.length}
					<ul class="mt-2 flex flex-wrap gap-2">
						{#each selectedTargets as t (t.job_id)}
							<li
								class="flex max-w-full items-center gap-1.5 rounded-lg border border-[var(--primary)]/25 bg-[var(--primary)]/8 px-2.5 py-1.5 text-xs text-black dark:text-white"
							>
								<span class="min-w-0 truncate">{targetLabel(t)}</span>
								<button
									type="button"
									aria-label="取消选择 {targetLabel(t)}"
									class="shrink-0 rounded-md px-1 text-sm leading-none text-50 hover:bg-black/10 hover:text-red-600 dark:hover:bg-white/10 dark:hover:text-red-400"
									onclick={() => removeTarget(String(t.job_id || ""))}
								>
									×
								</button>
							</li>
						{/each}
					</ul>
				{:else}
					<p class="mt-1.5 text-xs text-50">暂未选择岗位，请搜索并点击加入。</p>
				{/if}
			</div>

			<div class="mt-4 grid gap-2 sm:grid-cols-2">
				<label class="grid gap-1 text-xs text-75">
					<span>岗位关键词</span>
					<input
						type="text"
						bind:value={searchQ}
						placeholder="如：数据分析师"
						class="rounded-xl border border-black/10 bg-[var(--btn-regular-bg)] px-3 py-2 text-sm dark:border-white/15"
						onkeydown={(event) => {
							if (event.key === "Enter") {
								event.preventDefault();
								void runSearch();
							}
						}}
					/>
				</label>
				<label class="grid gap-1 text-xs text-75">
					<span>地点（可选）</span>
					<input
						type="text"
						bind:value={searchLocation}
						placeholder="如：北京"
						class="rounded-xl border border-black/10 bg-[var(--btn-regular-bg)] px-3 py-2 text-sm dark:border-white/15"
						onkeydown={(event) => {
							if (event.key === "Enter") {
								event.preventDefault();
								void runSearch();
							}
						}}
					/>
				</label>
			</div>

			<div class="mt-3 flex flex-wrap items-center gap-2">
				<button
					type="button"
					disabled={loading}
					onclick={() => void runSearch()}
					class="rounded-xl bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
				>
					{loading ? "搜索中…" : "搜索"}
				</button>
			</div>

			{#if error}
				<p class="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>
			{/if}
			{#if info}
				<p class="mt-3 text-sm text-[var(--primary)]">{info}</p>
			{/if}

			<div class="mt-4 min-h-0 flex-1 overflow-y-auto pr-1">
				{#if loading}
					<p class="py-8 text-center text-sm text-50">正在加载岗位…</p>
				{:else if !results.length}
					<p class="py-8 text-center text-sm text-50">
						{listMode === "search" ? "未找到匹配岗位。" : "岗位库暂无数据。"}
					</p>
				{:else}
					<ul class="space-y-2">
						{#each results as t (t.job_id)}
							{@const picked = isSelected(String(t.job_id || ""))}
							<li>
								<div
									class="overflow-hidden rounded-xl border transition {picked
										? 'border-[var(--primary)]/35 bg-[var(--primary)]/8'
										: 'border-black/10 bg-[var(--card-bg)] dark:border-white/10'}"
								>
									<button
										type="button"
										disabled={picked || atLimit}
										onclick={() => pickTarget(t)}
										class="block w-full p-3 pb-2 text-left transition disabled:cursor-not-allowed disabled:opacity-80"
									>
										<div class="flex items-start justify-between gap-2">
											<span class="font-medium text-black dark:text-white">{t.title || t.job_id}</span>
											{#if picked}
												<span class="shrink-0 text-xs font-medium text-[var(--primary)]">已加入</span>
											{/if}
										</div>
										<p class="mt-1 text-xs text-50">
											{t.company || "未知公司"} · {t.location || "未知地点"}
											{#if t.salary}
												· {t.salary}
											{/if}
										</p>
									</button>
									<div
										class="flex justify-end border-t border-black/5 px-3 py-2 dark:border-white/5"
									>
										<button
											type="button"
											class="rounded-lg bg-[var(--primary)] px-3 py-1 text-xs font-semibold text-white hover:opacity-90"
											onclick={() => void openJobDetail(String(t.job_id || ""))}
										>
											查看详情
										</button>
									</div>
								</div>
							</li>
						{/each}
					</ul>
				{/if}
			</div>

			{#if listMode === "random" && totalPages > 1}
				<div class="mt-3 flex flex-wrap items-center justify-center gap-3 text-sm">
					<button
						type="button"
						disabled={loading || currentPage <= 1}
						onclick={() => void goToPage(currentPage - 1)}
						class="rounded-xl border border-black/15 px-4 py-1.5 disabled:opacity-50 dark:border-white/20"
					>
						上一页
					</button>
					<span class="text-xs text-50">第 {currentPage} / {totalPages} 页</span>
					<button
						type="button"
						disabled={loading || currentPage >= totalPages}
						onclick={() => void goToPage(currentPage + 1)}
						class="rounded-xl border border-black/15 px-4 py-1.5 disabled:opacity-50 dark:border-white/20"
					>
						下一页
					</button>
				</div>
			{/if}

			<div class="mt-4 flex flex-wrap justify-end gap-2 border-t border-black/10 pt-4 dark:border-white/10">
				<button
					type="button"
					onclick={onClose}
					class="rounded-xl border border-black/15 px-4 py-2 text-sm dark:border-white/20"
				>
					完成
				</button>
			</div>
		</div>
	</div>

	<JobDetailDrawer
		open={jobDetailOpen}
		loading={jobDetailLoading}
		error={jobDetailError}
		detail={jobDetailData}
		zIndex={220}
		onClose={closeJobDetail}
	/>
{/if}
