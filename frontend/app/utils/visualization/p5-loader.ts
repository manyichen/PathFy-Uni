type P5Constructor = typeof import('p5/core').default

let p5Promise: Promise<P5Constructor> | undefined

/**
 * Loads the p5 core once and keeps it outside initial route bundles.
 * Accessibility is registered here so scenes do not repeat bootstrap logic.
 */
export function loadP5(): Promise<P5Constructor> {
  p5Promise ||= Promise.all([
    import('p5/core'),
    import('p5/accessibility')
  ]).then(([{ default: P5 }, { default: accessibility }]) => {
    accessibility(P5)
    return P5
  })

  return p5Promise
}
