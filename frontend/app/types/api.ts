export interface AuthUser { id: number; username: string; email: string; is_admin?: boolean }
export interface OkEnvelope<T> { ok: boolean; data?: T; message?: string }
export interface CodeEnvelope<T> { code: number; data?: T; msg?: string }
export type CapabilityScores = Record<'cap_req_theory'|'cap_req_cross'|'cap_req_practice'|'cap_req_digital'|'cap_req_innovation'|'cap_req_teamwork'|'cap_req_social'|'cap_req_growth', number>
export interface JobCard { id: string; title: string; company: string; location: string; salary: string; scores: CapabilityScores; score_avg?: number; conf_avg?: number; [key: string]: unknown }
