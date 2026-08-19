declare module 'p5/core' {
  import P5 from 'p5'
  export default P5
}

declare module 'p5/accessibility' {
  import P5 from 'p5'
  const accessibility: (p5: typeof P5) => void
  export default accessibility
}
