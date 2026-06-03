<script lang="ts">
	import {
		fetchMatchHistory,
		fetchMatchHistoryDetail,
		type MatchHistoryDetail,
		type MatchHistorySummary,
	} from "@/lib/api/match";

	type OnClose = () => void;
	type OnLoad = (detail: MatchHistoryDetail) => void;

	const {
		open = false,
		modalTitle = "加载历史匹配",
		confirmLabel = "加载",
		emptyHint = "暂无历史匹配记录，请先完成一次匹配。",
		resumeIdFilter = null as number | null,
		onClose = (() => {}) as OnClose,
		onLoad = ((_: MatchHistoryDetail) => {}) as OnLoad,
	} = $props<{
		open?: boolean;
		modalTitle?: string;
		confirmLabel?: string;
		emptyHint?: string;
		/** 若指定，仅展示该画像下的匹配记录 */
		resumeIdFilter?: number | null;
		onClose?: OnClose;
		onLoad?: OnLoad;
	}>();

	let loading = $state(false);
	let loadingDetail = $state(false);
	let error = $state("");
	let items = $state<MatchHistorySummary[]>([]);
	let selectedRunId = $state<number | null>(null);
	let wasOpen = false;

	function portal(node: HTMLElement) {
		if (typeof document === "undefined") return;
		document.body.appendChild(node);
		return {
			destroy() {
				node.parentNode?.removeChild(node);
			},
		};
	}

	function goalRemark(goal: string): { label: string; tone: "fit" | "stretch" } {
		return goal === "stretch"
			? { label: "用于冲刺", tone: "stretch" }
			: { label: "匹配合适", tone: "fit" };
	}

	function goalBadgeClass(tone: "fit" | "stretch"): string {
		return tone === "stretch"
			? "border-amber-500/35 bg-amber-500/10 text-amber-900 dark:text-amber-100"
			: "border-[var(--primary)]/35 bg-[var(--primary)]/10 text-[var(--primary)]";
	}

	function filterSummary(row: MatchHistorySummary): string {
		const parts: string[] = [];
		if (row.q.trim()) parts.push(`关键词「${row.q.trim()}」`);
		if (row.location_q.trim()) parts.push(`地点「${row.location_q.trim()}」`);
		return parts.length ? parts.join(" · ") : "无筛选条件";
	}

	function formatTime(raw: string): string {
		const t = raw.trim();
		if (!t) return "—";
		return t.replace("T", " ").slice(0, 19);
	}

	const visibleItems = $derived.by(() => {
		if (resumeIdFilter == null || resumeIdFilter <= 0) return items;
		return items.filter((x) => x.resume_id === resumeIdFilter);
	});

	async function loadList(): Promise<void> {
		loading = true;
		error = "";
		try {
			items = await fetchMatchHistory(40);
			const list = resumeIdFilter != null && resumeIdFilter > 0
				? items.filter((x) => x.resume_id === resumeIdFilter)
				: items;
			if (list.length && selectedRunId === null) {
				selectedRunId = list[0].run_id;
			}
			if (selectedRunId !== null && !list.some((x) => x.run_id === selectedRunId)) {
				selectedRunId = list[0]?.run_id ?? null;
			}
		} catch (e) {
			error = e instanceof Error ? e.message : "加载失败";
			items = [];
			selectedRunId = null;
		} finally {
			loading = false;
		}
	}

	async function confirmLoad(): Promise<void> {
		if (selectedRunId === null) return;
		loadingDetail = true;
		error = "";
		try {
			const detail = await fetchMatchHistoryDetail(selectedRunId);
			onLoad(detail);
			onClose();
		} catch (e) {
			error = e instanceof Error ? e.message : "加载记录失败";
		} finally {
			loadingDetail = false;
		}
	}

	$effect(() => {
		if (!open) {
			wasOpen = false;
			return;
		}
		if (!wasOpen) {
			selectedRunId = null;
			void loadList();
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
		aria-labelledby="match-history-title"
		tabindex="-1"
		onkeydown={(event) => {
			if (event.key === "Escape") {
				event.preventDefault();
				onClose();
			}
		}}
	>
		<button type="button" aria-label="关闭" onclick={onClose} class="absolute inset-0 cursor-default"></button>
		<div
			class="relative z-[1] flex w-full max-w-2xl max-h-[calc(100vh-5rem)] flex-col rounded-2xl border border-black/10 bg-[var(--page-bg)] p-5 shadow-2xl dark:border-white/15"
		>
			<div class="flex items-center justify-between gap-3">
				<h4 id="match-history-title" class="text-base font-semibold text-black dark:text-white">
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
				每次「开始匹配」成功后会自动保存到云端。选择一条记录并点击「加载」即可恢复当时的条件与结果。
			</p>

			{#if error}
				<p class="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>
			{/if}

			<div class="mt-4 min-h-0 flex-1 overflow-y-auto pr-1">
				{#if loading}
					<p class="py-8 text-center text-sm text-50">加载历史记录…</p>
				{:else if !visibleItems.length}
					<p class="py-8 text-center text-sm text-50">{emptyHint}</p>
				{:else}
					<ul class="space-y-2">
						{#each visibleItems as row (row.run_id)}
							{@const remark = goalRemark(row.match_goal)}
							<li>
								<label
									class="flex cursor-pointer gap-3 rounded-xl border p-3 transition {selectedRunId === row.run_id
										? 'border-[var(--primary)] bg-[var(--primary)]/5'
										: 'border-black/10 bg-[var(--card-bg)] dark:border-white/10'}"
								>
									<input
										type="radio"
										name="match-history-pick"
										class="mt-1 accent-[var(--primary)]"
										checked={selectedRunId === row.run_id}
										onchange={() => {
											selectedRunId = row.run_id;
										}}
									/>
									<div class="min-w-0 flex-1">
										<div class="flex flex-wrap items-center justify-between gap-2">
											<div class="flex min-w-0 flex-wrap items-center gap-2">
												<span class="font-medium text-black dark:text-white">{row.student_name}</span>
												<span
													class="shrink-0 rounded-md border px-2 py-0.5 text-[11px] font-medium {goalBadgeClass(remark.tone)}"
												>
													{remark.label}
												</span>
											</div>
											<span class="shrink-0 text-xs text-50">{formatTime(row.created_at)}</span>
										</div>
										<p class="mt-1 text-xs text-75">
											返回 {row.returned} 条
											{#if row.llm_ok}
												· 含智能精排
											{/if}
										</p>
										<p class="mt-0.5 truncate text-xs text-50">{filterSummary(row)}</p>
									</div>
								</label>
							</li>
						{/each}
					</ul>
				{/if}
			</div>

			<div class="mt-4 flex flex-wrap justify-end gap-2 border-t border-black/10 pt-4 dark:border-white/10">
				<button
					type="button"
					onclick={onClose}
					class="rounded-xl border border-black/15 px-4 py-2 text-sm dark:border-white/20"
				>
					取消
				</button>
				<button
					type="button"
					disabled={selectedRunId === null || loadingDetail || loading}
					onclick={() => void confirmLoad()}
					class="rounded-xl bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
				>
					{loadingDetail ? "处理中…" : confirmLabel}
				</button>
			</div>
		</div>
	</div>
{/if}
