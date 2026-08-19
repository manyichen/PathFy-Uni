export type ThemePreference = 'light' | 'dark' | 'system'
export type HuePreference = string

export interface UserPreferences {
  theme: ThemePreference
  hue: HuePreference
  allow_external_llm: boolean
  default_match_goal: 'fit' | 'stretch'
  default_refine_with_llm: boolean
  match_result_count: number
  report_copywriter: boolean
  report_public_info: boolean
  report_auto_replan: boolean
  report_graph_recommendations: boolean
  report_recommendation_llm: boolean
  report_longitudinal_personalization: boolean
  use_personality_in_match: boolean
  use_personality_in_report: boolean
  default_preference_mode: 'off' | 'explain' | 'tie_break'
  learning_resource_count: number
  competition_count: number
}

export interface PreferencesPayload {
  stored?: boolean
  preferences?: Partial<UserPreferences>
  effective?: Partial<UserPreferences>
  limits?: Partial<Record<'match_result_count' | 'learning_resource_count' | 'competition_count', number>>
  capabilities?: Partial<Record<'external_llm' | 'match_llm' | 'report_llm', boolean>>
  [key: string]: unknown
}

export interface SystemSettings {
  revision?: number
  settings?: Record<string, unknown>
  [key: string]: unknown
}
