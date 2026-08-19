export interface AuthUser { id: number; username: string; email: string; is_admin?: boolean }
export interface OkEnvelope<T> { ok: boolean; data?: T; message?: string; errors?: ApiFieldError[] }
export interface CodeEnvelope<T> { code: number; data?: T; msg?: string; errors?: ApiFieldError[] }
export type ApiEnvelope<T> = OkEnvelope<T> | CodeEnvelope<T>
export interface ApiFieldError { path?: string; message: string; [key: string]: unknown }

export * from './capability'
export * from './job'
export * from './profile'
export * from './personality'
export * from './match'
export * from './report'
export * from './settings'
export * from './graph-task'
