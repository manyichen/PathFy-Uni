import { getUser } from "@/lib/features/auth/session";
import type { CareerReportPayload, ReportTargetItem } from "@/lib/api/report";

/** 须与 session.clearAuth 中清除的键一致 */
export const REPORT_WORKSPACE_CACHE_KEY_PREFIX = "career_report_workspace_v1_";

export type ReportWorkspaceCacheV1 = {
	v: 1;
	reportId: number | null;
	/** 报告 JSON 快照，用于切页回来瞬时展示（后台再刷新） */
	reportSnapshot?: CareerReportPayload | null;
	infoMessage: string;
	selectedTargets: ReportTargetItem[];
	selectedResumeId: number | "";
	reportMatchGoal: "fit" | "stretch";
	activeJobId: string;
	activePhase: "early" | "mid" | "late";
	focusLineId: string;
	selectedAdjustmentId: string;
	selectedCanvasMonth: number | null;
	selectedTimelineReviewId: number | null;
	configRailCollapsed: boolean;
	nextMonthSectionOpen: boolean;
	nextMonthItemOpen: Record<string, boolean>;
	nextMonthActionDone: Record<string, boolean>;
};

function storageKey(): string {
	const u = getUser();
	return `${REPORT_WORKSPACE_CACHE_KEY_PREFIX}${u?.id ?? "guest"}`;
}

function isBrowser(): boolean {
	return typeof window !== "undefined" && typeof localStorage !== "undefined";
}

export function persistReportWorkspace(payload: ReportWorkspaceCacheV1): void {
	if (!isBrowser()) return;
	try {
		localStorage.setItem(storageKey(), JSON.stringify(payload));
	} catch {
		/* ignore quota */
	}
}

export function loadReportWorkspace(): ReportWorkspaceCacheV1 | null {
	if (!isBrowser()) return null;
	try {
		const raw = localStorage.getItem(storageKey());
		if (!raw) return null;
		const o = JSON.parse(raw) as ReportWorkspaceCacheV1;
		if (o?.v !== 1) return null;
		if (!Array.isArray(o.selectedTargets)) return null;
		return o;
	} catch {
		return null;
	}
}

/** 组件初始化时同步读取，避免 onMount 等待 API 才显示画布 */
export function readWorkspaceBootstrap(): ReportWorkspaceCacheV1 | null {
	return loadReportWorkspace();
}

export function clearReportWorkspaceCache(userId?: number | "guest"): void {
	if (!isBrowser()) return;
	if (userId !== undefined) {
		localStorage.removeItem(`${REPORT_WORKSPACE_CACHE_KEY_PREFIX}${userId}`);
		return;
	}
	localStorage.removeItem(`${REPORT_WORKSPACE_CACHE_KEY_PREFIX}guest`);
	const u = getUser();
	if (u?.id) {
		localStorage.removeItem(`${REPORT_WORKSPACE_CACHE_KEY_PREFIX}${u.id}`);
	}
}
