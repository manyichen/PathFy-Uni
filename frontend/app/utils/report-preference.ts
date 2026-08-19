import type { ReportPreferenceStrategySection } from '~/types/report'

/**
 * Vue props are readonly reactive proxies and cannot be passed to structuredClone.
 * Copy the editable records explicitly so the form never mutates report source data.
 */
export function copyPreferenceSections(
  value: readonly ReportPreferenceStrategySection[] | undefined
): ReportPreferenceStrategySection[] {
  return (value || []).map(section => ({
    ...section,
    ...(section.source ? { source: { ...section.source } } : {})
  }))
}
