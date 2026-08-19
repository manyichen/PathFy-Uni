export const clamp01 = (value: number) => Math.max(0, Math.min(1, value))

export const easeInOutSine = (value: number) => -(Math.cos(Math.PI * clamp01(value)) - 1) / 2

export const easeOutCubic = (value: number) => 1 - Math.pow(1 - clamp01(value), 3)

export const easeInExpo = (value: number) => {
  const x = clamp01(value)
  return x === 0 ? 0 : Math.pow(2, 10 * x - 10)
}
