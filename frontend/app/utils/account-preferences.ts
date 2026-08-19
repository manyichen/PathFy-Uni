import { normalizeHuePreference, normalizeThemePreference } from '~/composables/useAppearancePreferences'
import type { UserPreferences } from '~/types/settings'

export type PreferenceNumberKey = 'match_result_count' | 'learning_resource_count' | 'competition_count'
export type PreferenceLimits = Record<PreferenceNumberKey, number>
export type PreferenceErrors = Partial<Record<PreferenceNumberKey, string>>

export const defaultUserPreferences: UserPreferences = {
  theme: 'system', hue: '192', allow_external_llm: true, default_match_goal: 'fit',
  default_refine_with_llm: false, match_result_count: 30, report_copywriter: true,
  report_public_info: true, report_auto_replan: true, report_graph_recommendations: true,
  report_recommendation_llm: true, report_longitudinal_personalization: true, learning_resource_count: 5, competition_count: 3,
  use_personality_in_match: true, use_personality_in_report: true, default_preference_mode: 'explain'
}

function numberOr(value: unknown, fallback: number): number {
  const result = Number(value)
  return Number.isFinite(result) ? result : fallback
}

export function normalizeUserPreferences(value: Partial<UserPreferences> = {}): UserPreferences {
  return {
    theme: normalizeThemePreference(value.theme),
    hue: normalizeHuePreference(value.hue),
    allow_external_llm: Boolean(value.allow_external_llm ?? defaultUserPreferences.allow_external_llm),
    default_match_goal: value.default_match_goal === 'stretch' ? 'stretch' : 'fit',
    default_refine_with_llm: Boolean(value.default_refine_with_llm ?? defaultUserPreferences.default_refine_with_llm),
    report_copywriter: Boolean(value.report_copywriter ?? defaultUserPreferences.report_copywriter),
    report_public_info: Boolean(value.report_public_info ?? defaultUserPreferences.report_public_info),
    report_auto_replan: Boolean(value.report_auto_replan ?? defaultUserPreferences.report_auto_replan),
    report_graph_recommendations: Boolean(value.report_graph_recommendations ?? defaultUserPreferences.report_graph_recommendations),
    report_recommendation_llm: Boolean(value.report_recommendation_llm ?? defaultUserPreferences.report_recommendation_llm),
    report_longitudinal_personalization: Boolean(value.report_longitudinal_personalization ?? defaultUserPreferences.report_longitudinal_personalization),
    use_personality_in_match: Boolean(value.use_personality_in_match ?? defaultUserPreferences.use_personality_in_match),
    use_personality_in_report: Boolean(value.use_personality_in_report ?? defaultUserPreferences.use_personality_in_report),
    default_preference_mode: value.default_preference_mode === 'off' || value.default_preference_mode === 'tie_break' || value.default_preference_mode === 'explain'
      ? value.default_preference_mode
      : defaultUserPreferences.default_preference_mode,
    match_result_count: numberOr(value.match_result_count, defaultUserPreferences.match_result_count),
    learning_resource_count: numberOr(value.learning_resource_count, defaultUserPreferences.learning_resource_count),
    competition_count: numberOr(value.competition_count, defaultUserPreferences.competition_count)
  }
}

export function validateUserPreferences(form: UserPreferences, limits: PreferenceLimits): PreferenceErrors {
  const errors: PreferenceErrors = {}
  if (!Number.isInteger(form.match_result_count) || form.match_result_count < 1 || form.match_result_count > limits.match_result_count) errors.match_result_count = `请输入 1～${limits.match_result_count} 的整数`
  if (!Number.isInteger(form.learning_resource_count) || form.learning_resource_count < 1 || form.learning_resource_count > limits.learning_resource_count) errors.learning_resource_count = `请输入 1～${limits.learning_resource_count} 的整数`
  if (!Number.isInteger(form.competition_count) || form.competition_count < 0 || form.competition_count > limits.competition_count) errors.competition_count = `请输入 0～${limits.competition_count} 的整数`
  return errors
}

export function serializeUserPreferences(form: UserPreferences): string {
  return JSON.stringify(form)
}
