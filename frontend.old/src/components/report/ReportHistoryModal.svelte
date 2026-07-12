<script lang="ts">
	import {
		fetchCareerReportDetail,
		fetchMyCareerReports,
		type CareerReportGenerateResponse,
		type CareerReportHistoryItem,
	} from "@/lib/api/report";

	type ReportDetail = NonNullable<CareerReportGenerateResponse["data"]>;
	type OnClose = () => void;
	type OnLoad = (detail: ReportDetail) => void;

	const {
		open = false,
		modalTitle = "加载历史报告",
		confirmLabel = "加载",
		emptyHint = "暂无历史报告，请先生成一份生涯报告。",
		resumeNames = {} as Record<number, string>,
		onClose = (() => {}) as OnClose,
		onLoad = ((_: ReportDetail) => {}) as OnLoad,
	} = $props<{
		open?: boolean;
		modalTitle?: string;
		confirmLabel?: string;
		emptyHint?: string;
		resumeNames?: Record<number, string>;
		onClose?: OnClose;
		onLoad?: OnLoad;
	}>();

	let loading = $state(false);
	let loadingDetail = $state(false);
	let error = $state("");
	let items = $state<CareerReportHistoryItem[]>([]);
	let selectedReportId = $state<number | null>(null);
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

	function formatTime(raw: string): string {
		const t = raw.trim();
		if (!t) return "—";
		return t.replace("T", " ").slice(0, 19);
	}

	function resumeLabel(resumeId: number): string {
		const name = resumeNames[resumeId]?.trim();
		return name || `画像 #${resumeId}`;
	}

	function targetTitles(row: CareerReportHistoryItem): string[] {
		return (row.target_titles || []).map((x) => x.trim()).filter(Boolean);
	}

	async function loadList(): Promise<void> {
		loading = true;
		error = "";
		try {
			items = await fetchMyCareerReports(40);
			if (items.length && selectedReportId === null) {
				selectedReportId = items[0].report_id;
			}
			if (selectedReportId !== null && !items.some((x) => x.report_id === selectedReportId)) {
				selectedReportId = items[0]?.report_id ?? null;
			}
		} catch (e) {
			error = e instanceof Error ? e.message : "加载失败";
			items = [];
			selectedReportId = null;
		} finally {
			loading = false;
		}
	}

	async function confirmLoad(): Promise<void> {
		if (selectedReportId === null) return;
		loadingDetail = true;
		error = "";
		try {
			const detail = await fetchCareerReportDetail(selectedReportId);
			if (!detail) {
				throw new Error("报告详情为空");
			}
			onLoad(detail);
			onClose();
		} catch (e) {
			error = e instanceof Error ? e.message : "加载报告失败";
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
			selectedReportId = null;
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
		aria-labelledby="report-history-title"
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
				<h4 id="report-history-title" class="text-base font-semibold text-black dark:text-white">
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
				选择一份已生成的生涯报告，点击「加载」即可恢复画布内容与复盘记录。
			</p>

			{#if error}
				<p class="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>
			{/if}

			<div class="mt-4 min-h-0 flex-1 overflow-y-auto pr-1">
				{#if loading}
					<p class="py-8 text-center text-sm text-50">加载历史记录…</p>
				{:else if !items.length}
					<p class="py-8 text-center text-sm text-50">{emptyHint}</p>
				{:else}
					<ul class="space-y-2">
						{#each items as row (row.report_id)}
							{@const titles = targetTitles(row)}
							<li>
								<label
									class="flex cursor-pointer gap-3 rounded-xl border p-3 transition {selectedReportId === row.report_id
										? 'border-[var(--primary)] bg-[var(--primary)]/5'
										: 'border-black/10 bg-[var(--card-bg)] dark:border-white/10'}"
								>
									<input
										type="radio"
										name="report-history-pick"
										class="mt-1 accent-[var(--primary)]"
										checked={selectedReportId === row.report_id}
										onchange={() => {
											selectedReportId = row.report_id;
										}}
									/>
									<div class="min-w-0 flex-1">
										<div class="flex flex-wrap items-center justify-between gap-2">
											<span class="font-medium text-black dark:text-white">{row.title}</span>
											<span class="shrink-0 text-xs text-50">{formatTime(row.created_at)}</span>
										</div>
										<p class="mt-1 text-xs text-75">{resumeLabel(row.resume_id)}</p>
										{#if titles.length}
											<p class="mt-0.5 text-xs leading-relaxed text-50">
												{#each titles as title, i}
													{#if i > 0}<span class="mx-1.5 font-semibold text-75">||</span>{/if}
													<span>{title}</span>
												{/each}
											</p>
										{:else if row.target_job_ids.length}
											<p class="mt-0.5 text-xs text-50">
												{row.target_job_ids.length} 个目标职业（名称未记录）
											</p>
										{:else}
											<p class="mt-0.5 text-xs text-50">暂无目标职业</p>
										{/if}
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
					disabled={selectedReportId === null || loadingDetail || loading}
					onclick={() => void confirmLoad()}
					class="rounded-xl bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
				>
					{loadingDetail ? "处理中…" : confirmLabel}
				</button>
			</div>
		</div>
	</div>
{/if}
