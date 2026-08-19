import type { CareerReport, ReportTarget } from '~/types/report'
import { asRecord } from '~/utils/normalizers'
import { cacheKey, readCache, removeCache, type CacheUserId, writeCache } from './base'

const prefix = 'career_report_workspace_v1_'
export interface ReportWorkspaceCache { resumeId?: number; selectedResumeId?: number; targets?: ReportTarget[]; selectedTargets?: ReportTarget[]; primaryJobId?: string; reportPrimaryJobId?: string; goal?: string; reportMatchGoal?: string; reportId?: number; reportTitle?: string; report?: CareerReport; reportSnapshot?: CareerReport; activeJobId?: string; selectedMonth?: number; selectedCanvasMonth?: number; configCollapsed?: boolean; configRailCollapsed?: boolean }
export const reportCacheKey = (userId: CacheUserId) => cacheKey(prefix, userId)

function withoutMaterialText(report: CareerReport | undefined): CareerReport | undefined {
  if (!report) return undefined
  const copy = { ...report }
  delete copy.materials
  delete copy.resume_text
  return copy
}

function migrate(raw: unknown): ReportWorkspaceCache | undefined {
  const row = asRecord(raw)
  const payload = asRecord(row.data || row)
  if (!Object.keys(payload).length) return undefined
  return {
    resumeId: Number(payload.resumeId || payload.selectedResumeId) || undefined,
    selectedResumeId: Number(payload.selectedResumeId || payload.resumeId) || undefined,
    targets: Array.isArray(payload.targets) ? payload.targets as ReportTarget[] : undefined,
    selectedTargets: Array.isArray(payload.selectedTargets) ? payload.selectedTargets as ReportTarget[] : undefined,
    primaryJobId: typeof payload.primaryJobId === 'string' ? payload.primaryJobId : undefined,
    reportPrimaryJobId: typeof payload.reportPrimaryJobId === 'string' ? payload.reportPrimaryJobId : undefined,
    goal: typeof payload.goal === 'string' ? payload.goal : undefined,
    reportMatchGoal: typeof payload.reportMatchGoal === 'string' ? payload.reportMatchGoal : undefined,
    reportId: Number(payload.reportId) || undefined,
    reportTitle: typeof payload.reportTitle === 'string' ? payload.reportTitle : undefined,
    report: withoutMaterialText(payload.report as CareerReport | undefined),
    reportSnapshot: withoutMaterialText(payload.reportSnapshot as CareerReport | undefined),
    activeJobId: typeof payload.activeJobId === 'string' ? payload.activeJobId : undefined,
    selectedMonth: Number.isFinite(Number(payload.selectedMonth ?? payload.selectedCanvasMonth)) ? Number(payload.selectedMonth ?? payload.selectedCanvasMonth) : undefined,
    selectedCanvasMonth: Number.isFinite(Number(payload.selectedCanvasMonth ?? payload.selectedMonth)) ? Number(payload.selectedCanvasMonth ?? payload.selectedMonth) : undefined,
    configCollapsed: typeof payload.configCollapsed === 'boolean' ? payload.configCollapsed : Boolean(payload.configRailCollapsed),
    configRailCollapsed: typeof payload.configRailCollapsed === 'boolean' ? payload.configRailCollapsed : Boolean(payload.configCollapsed)
  }
}

export const readReportCache = (userId: CacheUserId) => readCache(reportCacheKey(userId), userId, migrate)
export const writeReportCache = (userId: CacheUserId, data: ReportWorkspaceCache) => writeCache(reportCacheKey(userId), userId, migrate(data) || data)
export const clearReportCache = (userId: CacheUserId) => removeCache(reportCacheKey(userId))
