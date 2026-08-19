const ALLOWED_EXTERNAL_PROTOCOLS = new Set(['http:', 'https:'])

export function safeExternalUrl(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined
  const candidate = value.trim()
  if (!candidate || /[\u0000-\u001f\u007f]/.test(candidate)) return undefined
  try {
    const url = new URL(candidate)
    return ALLOWED_EXTERNAL_PROTOCOLS.has(url.protocol) ? url.href : undefined
  } catch {
    return undefined
  }
}
