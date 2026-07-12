import type { CareerReportPayload } from "@/lib/api/report";

/** 纯 JSON 克隆，避免 structuredClone 无法处理 Svelte $state 代理 */
export function cloneReportPayload(report: CareerReportPayload): CareerReportPayload {
	return JSON.parse(JSON.stringify(report)) as CareerReportPayload;
}

export function nextMonthItemKey(jobId: string, itemIndex: number, dim: string): string {
	return `${jobId}-${itemIndex}-${dim || ""}`;
}

export function nextMonthActionKey(itemKey: string, actionIndex: number): string {
	return `${itemKey}-a-${actionIndex}`;
}

/** 从报告快照提取行动项勾选 map（用于刷新后恢复） */
export function collectActionDoneMap(report: CareerReportPayload | null | undefined): Record<string, boolean> {
	const out: Record<string, boolean> = {};
	if (!report?.plans_by_target?.length) return out;

	for (const plan of report.plans_by_target) {
		const jobId = String(plan.job_id || "").trim();
		if (!jobId) continue;
		const items = plan.next_month_plan?.items;
		if (!items?.length) continue;
		for (let ni = 0; ni < items.length; ni++) {
			const nm = items[ni];
			const itemKey = nextMonthItemKey(jobId, ni, nm.focus_dimension || "");
			const actions = nm.custom_actions || [];
			for (let ai = 0; ai < actions.length; ai++) {
				if (actions[ai]?.done) {
					out[nextMonthActionKey(itemKey, ai)] = true;
				}
			}
		}
	}
	return out;
}

function actionDoneFromSources(
	act: { done?: boolean } | undefined,
	key: string,
	localDone: Record<string, boolean>,
): boolean {
	if (act?.done === true) return true;
	if (localDone[key]) return true;
	if (act?.done === false) return false;
	return false;
}

/** 合并本地/缓存勾选状态到远端报告，避免静默刷新覆盖 done */
export function mergeReportActionProgress(
	remote: CareerReportPayload,
	sources: Array<CareerReportPayload | null | undefined>,
	localDone: Record<string, boolean>,
): CareerReportPayload {
	const merged = cloneReportPayload(remote);

	for (const plan of merged.plans_by_target || []) {
		const jobId = String(plan.job_id || "").trim();
		if (!jobId) continue;

		const sourcePlans = sources
			.map((s) => s?.plans_by_target?.find((p) => p.job_id === jobId))
			.filter(Boolean);

		const items = plan.next_month_plan?.items;
		if (!items?.length) continue;

		for (let ni = 0; ni < items.length; ni++) {
			const nm = items[ni];
			const itemKey = nextMonthItemKey(jobId, ni, nm.focus_dimension || "");
			const actions = nm.custom_actions || [];

			for (let ai = 0; ai < actions.length; ai++) {
				const act = actions[ai];
				const key = nextMonthActionKey(itemKey, ai);
				let done = actionDoneFromSources(act, key, localDone);

				for (const sp of sourcePlans) {
					const srcItem = sp?.next_month_plan?.items?.[ni];
					const srcAct = srcItem?.custom_actions?.[ai];
					if (srcAct?.done === true) {
						done = true;
						if (srcAct.done_at) act.done_at = srcAct.done_at;
						break;
					}
				}

				if (done) {
					act.done = true;
				} else if (act.done == null && !localDone[key]) {
					delete act.done;
					delete act.done_at;
				}
			}
		}
	}

	return merged;
}

export function mergeActionDoneMaps(...maps: Array<Record<string, boolean> | undefined>): Record<string, boolean> {
	const out: Record<string, boolean> = {};
	for (const m of maps) {
		if (!m) continue;
		for (const [k, v] of Object.entries(m)) {
			if (v) out[k] = true;
		}
	}
	return out;
}
