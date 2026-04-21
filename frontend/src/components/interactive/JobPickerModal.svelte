<script lang="ts">
	import { fetchJobs, type JobCardItem, type JobLiteItem } from "../../lib/jobs";

	type OnClose = () => void;
	type OnSelect = (job: JobLiteItem) => void;

	const {
		open = false,
		modalTitle = "选择岗位",
		selectedJobId = "",
		onClose = (() => {}) as OnClose,
		onSelect = ((_: JobLiteItem) => {}) as OnSelect,
	} = $props<{
		open?: boolean;
		modalTitle?: string;
		selectedJobId?: string;
		onClose?: OnClose;
		onSelect?: OnSelect;
	}>();

	let query = $state("");
	let page = $state(1);
	let pageSize = 20;

	let loading = $state(false);
	let error = $state("");
	let total = $state(0);
	let totalPages = $state(1);
	let jobs = $state<JobLiteItem[]>([]);
	let wasOpen = false;

	function portal(node: HTMLElement) {
		if (typeof document === "undefined") {
			return;
		}
		document.body.appendChild(node);
		return {
			destroy() {
				if (node.parentNode) {
					node.parentNode.removeChild(node);
				}
			},
		};
	}

	async function loadPage(targetPage: number, keyword: string) {
		if (!open) {
			return;
		}
		loading = true;
		error = "";
		try {
			const res = await fetchJobs({
				q: keyword,
				page: Math.max(1, targetPage),
				pageSize,
			});
			jobs = res.jobs.map((x: JobCardItem) => ({
				id: x.id,
				title: x.title,
				company: x.company,
				location: x.location,
			}));
			total = res.total;
			totalPages = Math.max(1, res.totalPages);
			page = Math.min(Math.max(1, res.page), totalPages);
		} catch (err) {
			error = err instanceof Error ? err.message : "岗位加载失败";
			jobs = [];
			total = 0;
			totalPages = 1;
		}
		finally {
			loading = false;
		}
	}

	function doSearch() {
		page = 1;
		loadPage(1, query);
	}

	function pick(job: JobLiteItem) {
		onSelect(job);
		onClose();
	}

	$effect(() => {
		if (!open) {
			wasOpen = false;
			return;
		}
		if (!wasOpen) {
			query = "";
			page = 1;
			void loadPage(1, "");
		}
		wasOpen = true;
	});
</script>

{#if open}
	<div
		use:portal
		class="fixed inset-0 z-[200] flex items-start justify-center overflow-y-auto bg-black/45 px-4 pt-20 pb-6"
		role="dialog"
		aria-modal="true"
		tabindex="-1"
		onkeydown={(event) => {
			if (event.key === "Escape") {
				event.preventDefault();
				onClose();
			}
		}}
	>
		<button
			type="button"
			aria-label="关闭岗位选择弹窗"
			onclick={onClose}
			class="absolute inset-0 cursor-default"
		></button>
		<div
			class="relative z-[1] flex w-full max-w-4xl max-h-[calc(100vh-6rem)] flex-col rounded-2xl border border-black/10 bg-[var(--page-bg)] p-4 shadow-2xl dark:border-white/15"
		>
			<div class="flex items-center justify-between gap-3">
				<h4 class="text-base font-semibold">{modalTitle}</h4>
				<button
					type="button"
					onclick={onClose}
					class="rounded-lg border border-black/15 px-3 py-1 text-xs hover:opacity-80 dark:border-white/20"
				>
					关闭
				</button>
			</div>

			<div class="mt-3 flex flex-wrap items-end gap-2">
				<label class="min-w-[220px] flex-1 text-sm">
					<span class="mb-1 block text-xs text-75">搜索岗位/公司/地点</span>
					<input
						type="text"
						bind:value={query}
						placeholder="例如：后端、产品经理、北京"
						onkeydown={(event) => {
							if (event.key === "Enter") {
								event.preventDefault();
								doSearch();
							}
						}}
						class="w-full rounded-xl border border-black/10 bg-white px-3 py-2 text-sm dark:border-white/20 dark:bg-white/5"
					/>
				</label>
				<button
					type="button"
					onclick={doSearch}
					disabled={loading}
					class="rounded-xl border border-[var(--primary)] bg-[var(--btn-regular-bg)] px-4 py-2 text-sm font-medium text-[var(--primary)] transition hover:opacity-90 disabled:opacity-60"
				>
					{loading ? "加载中..." : "搜索"}
				</button>
			</div>

			{#if error}
				<p class="mt-3 text-sm text-rose-500">{error}</p>
			{:else}
				<div class="mt-3 min-h-0 flex-1 overflow-auto rounded-xl border border-black/10 dark:border-white/15">
					{#if loading}
						<p class="p-4 text-sm text-75">正在加载岗位...</p>
					{:else if jobs.length === 0}
						<p class="p-4 text-sm text-75">没有匹配岗位，请调整搜索词。</p>
					{:else}
						<ul class="divide-y divide-black/10 dark:divide-white/10">
							{#each jobs as job (job.id)}
								<li class="flex items-center justify-between gap-3 px-3 py-2 text-sm">
									<div class="min-w-0">
										<p class="truncate font-medium">{job.title}</p>
										<p class="truncate text-xs text-75">{job.company} | {job.location || "未知地点"}</p>
									</div>
									<button
										type="button"
										onclick={() => pick(job)}
										disabled={selectedJobId === job.id}
										class="shrink-0 rounded-lg border border-black/15 px-3 py-1 text-xs transition hover:opacity-80 disabled:opacity-50 dark:border-white/20"
									>
										{selectedJobId === job.id ? "已选中" : "选择"}
									</button>
								</li>
							{/each}
						</ul>
					{/if}
				</div>

				<div class="mt-3 flex items-center justify-between text-xs text-75">
					<p>共 {total} 个岗位，当前第 {page}/{totalPages} 页</p>
					<div class="flex gap-2">
						<button
							type="button"
							onclick={() => loadPage(page - 1, query)}
							disabled={loading || page <= 1}
							class="rounded-lg border border-black/15 px-3 py-1 transition hover:opacity-80 disabled:opacity-50 dark:border-white/20"
						>
							上一页
						</button>
						<button
							type="button"
							onclick={() => loadPage(page + 1, query)}
							disabled={loading || page >= totalPages}
							class="rounded-lg border border-black/15 px-3 py-1 transition hover:opacity-80 disabled:opacity-50 dark:border-white/20"
						>
							下一页
						</button>
					</div>
				</div>
			{/if}
		</div>
	</div>
{/if}
