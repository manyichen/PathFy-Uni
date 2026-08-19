import type { AuthJourneySnapshot } from '~/types/auth-journey'
import { journeyConfig } from './config'
import { clamp01, easeInExpo, easeInOutSine, easeOutCubic } from './easing'

interface Point { x: number; y: number }
interface FlightPose { point: Point; rotation: number; morph: number }
interface JourneyGeometry { start: Point; end: Point; lineY: number; birdSize: number }
interface LineParticle extends Point { u: number; vx: number; vy: number; size: number }
interface BurstParticle { angle: number; speed: number; size: number; life: number; phase: number }
interface WingStrand { lane: number; color: string; phase: number; delay: number; weight: number }
interface AmbientMote { x: number; y: number; size: number; alpha: number; phase: number }

export interface JourneySketchController {
  remove: () => void
  setActive: (active: boolean) => void
}

type SnapshotReader = () => AuthJourneySnapshot

function seededRandom(seed: number) {
  let value = seed >>> 0
  return () => {
    value += 0x6D2B79F5
    let next = value
    next = Math.imul(next ^ next >>> 15, next | 1)
    next ^= next + Math.imul(next ^ next >>> 7, next | 61)
    return ((next ^ next >>> 14) >>> 0) / 4294967296
  }
}

function lerp(start: number, end: number, amount: number) {
  return start + (end - start) * amount
}

function pointOnQuadratic(start: Point, control: Point, end: Point, amount: number): Point {
  const inverse = 1 - amount
  return {
    x: inverse * inverse * start.x + 2 * inverse * amount * control.x + amount * amount * end.x,
    y: inverse * inverse * start.y + 2 * inverse * amount * control.y + amount * amount * end.y
  }
}

function quadraticDerivative(start: Point, control: Point, end: Point, amount: number): Point {
  return {
    x: 2 * (1 - amount) * (control.x - start.x) + 2 * amount * (end.x - control.x),
    y: 2 * (1 - amount) * (control.y - start.y) + 2 * amount * (end.y - control.y)
  }
}

function pointOnCubic(start: Point, controlA: Point, controlB: Point, end: Point, amount: number): Point {
  const inverse = 1 - amount
  return {
    x: inverse ** 3 * start.x + 3 * inverse ** 2 * amount * controlA.x + 3 * inverse * amount ** 2 * controlB.x + amount ** 3 * end.x,
    y: inverse ** 3 * start.y + 3 * inverse ** 2 * amount * controlA.y + 3 * inverse * amount ** 2 * controlB.y + amount ** 3 * end.y
  }
}

function cubicDerivative(start: Point, controlA: Point, controlB: Point, end: Point, amount: number): Point {
  const inverse = 1 - amount
  return {
    x: 3 * inverse * inverse * (controlA.x - start.x) + 6 * inverse * amount * (controlB.x - controlA.x) + 3 * amount * amount * (end.x - controlB.x),
    y: 3 * inverse * inverse * (controlA.y - start.y) + 6 * inverse * amount * (controlB.y - controlA.y) + 3 * amount * amount * (end.y - controlB.y)
  }
}

function rotationFromVelocity(velocity: Point) {
  // The canonical crescent bird faces left, so a leftward tangent has zero rotation.
  return Math.atan2(velocity.y, velocity.x) - Math.PI
}

function getIdleFlightPose(geometry: JourneyGeometry, cycle: number, now: number): FlightPose {
  const leftX = geometry.start.x + 22
  const rightX = geometry.end.x - 22
  const distance = Math.max(120, rightX - leftX)
  const lowerY = geometry.lineY - 27
  const turnRise = Math.min(38, Math.max(25, distance * 0.105))
  const turnWidth = Math.min(31, Math.max(21, distance * 0.085))
  const upperY = lowerY - turnRise * 2
  const arcHeight = Math.min(journeyConfig.idle.arcHeight, distance * 0.24)
  const lowerLeft = { x: leftX, y: lowerY }
  const lowerRight = { x: rightX, y: lowerY }
  const upperRight = { x: rightX, y: upperY }
  const upperLeft = { x: leftX, y: upperY }
  let point: Point
  let velocity: Point

  if (cycle < 0.36) {
    const local = cycle / 0.36
    const control = { x: (leftX + rightX) / 2, y: lowerY - arcHeight }
    point = pointOnQuadratic(lowerLeft, control, lowerRight, local)
    velocity = quadraticDerivative(lowerLeft, control, lowerRight, local)
  } else if (cycle < 0.5) {
    // Right-node U-turn: bottom -> outside -> top, with a continuous 180° heading change.
    const local = (cycle - 0.36) / 0.14
    const theta = Math.PI / 2 - Math.PI * local
    point = {
      x: rightX + Math.cos(theta) * turnWidth,
      y: lowerY - turnRise + Math.sin(theta) * turnRise
    }
    velocity = {
      x: Math.PI * turnWidth * Math.sin(theta),
      y: -Math.PI * turnRise * Math.cos(theta)
    }
  } else if (cycle < 0.86) {
    const local = (cycle - 0.5) / 0.36
    const control = { x: (leftX + rightX) / 2, y: upperY - arcHeight * 0.62 }
    point = pointOnQuadratic(upperRight, control, upperLeft, local)
    velocity = quadraticDerivative(upperRight, control, upperLeft, local)
  } else {
    // Mirrored left-node U-turn: top -> outside -> bottom.
    const local = (cycle - 0.86) / 0.14
    const theta = -Math.PI / 2 - Math.PI * local
    point = {
      x: leftX + Math.cos(theta) * turnWidth,
      y: upperY + turnRise + Math.sin(theta) * turnRise
    }
    velocity = {
      x: Math.PI * turnWidth * Math.sin(theta),
      y: -Math.PI * turnRise * Math.cos(theta)
    }
  }

  return {
    point,
    rotation: rotationFromVelocity(velocity),
    morph: Math.sin(now * 0.0142) * 0.76 + Math.sin(now * 0.0067 + 0.8) * 0.18
  }
}

function getStageGeometry(width: number, height: number): JourneyGeometry {
  const stage = document.querySelector<HTMLElement>('[data-auth-journey-stage]')
  const rect = stage?.getBoundingClientRect()
  if (!rect || rect.width < 80 || rect.height < 80) {
    return {
      start: { x: width * 0.18, y: height * 0.57 },
      end: { x: width * 0.58, y: height * 0.57 },
      lineY: height * 0.57,
      birdSize: Math.max(44, Math.min(66, Math.min(width, height) * 0.075))
    }
  }

  const compact = rect.width < 620
  const lineY = rect.top + rect.height * (compact ? 0.58 : 0.61)
  const inset = rect.width * (compact ? 0.15 : 0.14)
  return {
    start: { x: rect.left + inset, y: lineY },
    end: { x: rect.right - inset, y: lineY },
    lineY,
    birdSize: Math.max(42, Math.min(66, Math.min(rect.width, rect.height) * 0.115))
  }
}

function drawNode(ctx: CanvasRenderingContext2D, point: Point, kind: 'start' | 'end', alpha: number, scale = 1) {
  ctx.save()
  ctx.globalAlpha = alpha
  ctx.translate(point.x, point.y)
  ctx.scale(scale, scale)
  ctx.shadowBlur = 16
  ctx.shadowColor = 'rgba(255,255,255,.32)'
  ctx.fillStyle = '#fff'
  ctx.beginPath()
  ctx.arc(0, 0, 15, 0, Math.PI * 2)
  ctx.fill()
  ctx.shadowBlur = 0
  ctx.strokeStyle = '#05070a'
  ctx.fillStyle = '#05070a'
  ctx.lineWidth = 1.45
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'

  if (kind === 'start') {
    ctx.beginPath()
    ctx.arc(0, -3.7, 2.6, 0, Math.PI * 2)
    ctx.fill()
    ctx.beginPath()
    ctx.arc(0, 4.2, 6.1, Math.PI * 1.08, Math.PI * 1.92)
    ctx.stroke()
    ctx.beginPath()
    ctx.arc(0, 0, 9, Math.PI * 0.16, Math.PI * 1.44)
    ctx.stroke()
  } else {
    for (const [x, y] of [[-3.8, -3.8], [3.8, -3.8], [-3.8, 3.8], [3.8, 3.8]] as const) {
      ctx.beginPath()
      ctx.arc(x, y, 1.65, 0, Math.PI * 2)
      ctx.fill()
    }
    ctx.beginPath()
    ctx.arc(0, 0, 9, 0, Math.PI * 2)
    ctx.stroke()
  }
  ctx.restore()
}

function drawReferenceBird(
  ctx: CanvasRenderingContext2D,
  point: Point,
  size: number,
  morph: number,
  alpha = 1,
  rotation = 0,
  glow = 12,
  color = '#fff'
) {
  const upperSpan = size * 0.49 * (1 + morph * 0.105)
  const lowerSpan = size * 0.49 * (1 - morph * 0.045)
  const tipSweep = size * morph * 0.052
  const outerBow = -size * (0.415 + morph * 0.018)
  const innerBow = -size * (0.255 - morph * 0.012)
  ctx.save()
  ctx.globalAlpha = alpha
  ctx.translate(point.x, point.y)
  ctx.rotate(rotation)
  ctx.strokeStyle = color
  ctx.fillStyle = color
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.shadowBlur = glow
  ctx.shadowColor = color

  // The wings are one filled crescent ribbon. Its centre carries the visual
  // weight while both tips taper to nothing, matching the reference silhouette.
  ctx.beginPath()
  ctx.moveTo(size * 0.2 + tipSweep, -upperSpan)
  ctx.bezierCurveTo(
    -size * 0.11 + tipSweep * 0.25,
    -upperSpan * 0.86,
    outerBow,
    -size * 0.2,
    outerBow,
    0
  )
  ctx.bezierCurveTo(
    outerBow,
    size * 0.2,
    -size * 0.11 - tipSweep * 0.18,
    lowerSpan * 0.86,
    size * 0.2 - tipSweep * 0.45,
    lowerSpan
  )
  ctx.bezierCurveTo(
    size * 0.01 - tipSweep * 0.16,
    lowerSpan * 0.63,
    innerBow,
    size * 0.145,
    innerBow,
    0
  )
  ctx.bezierCurveTo(
    innerBow,
    -size * 0.145,
    size * 0.01 + tipSweep * 0.12,
    -upperSpan * 0.63,
    size * 0.2 + tipSweep,
    -upperSpan
  )
  ctx.closePath()
  ctx.fill()

  // A soft inner facet keeps the crescent dimensional without turning its
  // wings back into wire-frame strokes.
  ctx.shadowBlur = glow * 0.4
  ctx.globalAlpha = alpha * 0.14
  ctx.fillStyle = 'rgba(255,255,255,.92)'
  ctx.beginPath()
  ctx.moveTo(outerBow + size * 0.025, 0)
  ctx.bezierCurveTo(-size * 0.22, -size * 0.055, size * 0.02, -upperSpan * 0.44, size * 0.15 + tipSweep * 0.7, -upperSpan * 0.87)
  ctx.bezierCurveTo(-size * 0.02, -upperSpan * 0.55, -size * 0.23, -size * 0.09, outerBow + size * 0.025, 0)
  ctx.fill()

  // A slim fuselage crosses the wing root and tapers into the tail. The small
  // oval at the leading point reads as the head even when the bird is distant.
  const bodyRoot = outerBow + size * 0.018
  const bodyTip = size * (0.49 + morph * 0.012)
  ctx.globalAlpha = alpha * 0.92
  ctx.fillStyle = color
  ctx.shadowBlur = glow * 0.82
  ctx.beginPath()
  ctx.moveTo(bodyRoot, -size * 0.032)
  ctx.bezierCurveTo(-size * 0.16, -size * 0.027, size * 0.18, -size * 0.018, bodyTip, -size * 0.006)
  ctx.quadraticCurveTo(bodyTip + size * 0.055, 0, bodyTip, size * 0.006)
  ctx.bezierCurveTo(size * 0.18, size * 0.018, -size * 0.16, size * 0.027, bodyRoot, size * 0.032)
  ctx.closePath()
  ctx.fill()

  // The reference has only faint tail quills inside the open side. They remain
  // subordinate to the solid crescent wings.
  ctx.globalAlpha = alpha * 0.3
  ctx.strokeStyle = color
  ctx.lineWidth = Math.max(0.55, size * 0.009)
  ctx.beginPath()
  ctx.moveTo(innerBow + size * 0.015, -size * 0.018)
  ctx.quadraticCurveTo(size * 0.05, -size * 0.025, size * 0.43, -size * 0.065)
  ctx.moveTo(innerBow, size * 0.018)
  ctx.quadraticCurveTo(size * 0.08, size * 0.018, size * 0.47, size * 0.055)
  ctx.stroke()

  ctx.globalAlpha = alpha
  ctx.shadowBlur = glow * 0.72
  ctx.fillStyle = color
  ctx.beginPath()
  ctx.ellipse(bodyRoot - size * 0.012, 0, Math.max(1.25, size * 0.035), Math.max(1.05, size * 0.027), 0, 0, Math.PI * 2)
  ctx.fill()
  ctx.restore()
}

function buildEffects(geometry: JourneyGeometry, width: number, height: number, compact: boolean) {
  const random = seededRandom(Math.round(geometry.end.x * 19 + geometry.end.y * 31 + width))
  const lineParticles: LineParticle[] = Array.from({ length: journeyConfig.fracture.lineParticles }, (_, index) => {
    const u = index / (journeyConfig.fracture.lineParticles - 1)
    const strength = lerp(0.35, 5.8, u * u)
    return {
      x: lerp(geometry.start.x, geometry.end.x, u),
      y: geometry.lineY,
      u,
      vx: (random() - 0.48) * strength,
      vy: (random() - 0.5) * strength * 1.5,
      size: lerp(0.6, 1.75, random())
    }
  })

  const sparkCount = compact ? journeyConfig.fracture.sparksMobile : journeyConfig.fracture.sparksDesktop
  const sparks: BurstParticle[] = Array.from({ length: sparkCount }, () => ({
    angle: random() * Math.PI * 2,
    speed: lerp(0.45, compact ? 3.8 : 6.8, Math.pow(random(), 0.56)),
    size: lerp(0.55, 2.2, random()),
    life: lerp(0.38, 1, random()),
    phase: random() * Math.PI * 2
  }))

  const routeCount = compact ? journeyConfig.routes.mobileCount : journeyConfig.routes.desktopCount
  const strands: WingStrand[] = Array.from({ length: routeCount }, (_, index) => ({
    lane: routeCount <= 1 ? 0 : index / (routeCount - 1) * 2 - 1,
    color: journeyConfig.colors[Math.min(journeyConfig.colors.length - 1, Math.floor(index / routeCount * journeyConfig.colors.length))]!,
    phase: random() * Math.PI * 2,
    delay: random() * 0.22,
    weight: lerp(0.65, 1.35, random())
  }))

  const ambient: AmbientMote[] = Array.from({ length: compact ? 70 : 220 }, () => ({
    x: random(),
    y: random(),
    size: lerp(0.4, 2.2, random()),
    alpha: lerp(0.08, 0.55, random()),
    phase: random() * Math.PI * 2
  }))

  return { lineParticles, sparks, strands, ambient }
}

type JourneyEffects = ReturnType<typeof buildEffects>

function drawSpeedEchoes(ctx: CanvasRenderingContext2D, point: Point, progress: number, alpha: number) {
  ctx.save()
  ctx.strokeStyle = '#fff'
  ctx.lineCap = 'round'
  for (let index = 0; index < 6; index += 1) {
    const distance = 22 + index * 13 + progress * 8
    const height = 17 + index * 3.5
    ctx.globalAlpha = alpha * (0.34 - index * 0.042)
    ctx.lineWidth = 1.15
    ctx.beginPath()
    ctx.bezierCurveTo(point.x - distance + 8, point.y - height, point.x - distance, point.y - height * 0.5, point.x - distance, point.y)
    ctx.bezierCurveTo(point.x - distance, point.y + height * 0.5, point.x - distance + 8, point.y + height, point.x - distance + 16, point.y + height * 0.92)
    ctx.stroke()
  }
  ctx.restore()
}

function drawEnergyBackdrop(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  origin: Point,
  effects: JourneyEffects,
  progress: number,
  alpha: number,
  now: number
) {
  const background = ctx.createLinearGradient(0, 0, width, height * 0.35)
  background.addColorStop(0, '#03154c')
  background.addColorStop(0.42, '#0737bc')
  background.addColorStop(0.72, '#075cf1')
  background.addColorStop(1, '#42c8ff')
  ctx.save()
  ctx.globalAlpha = alpha * easeOutCubic(progress)
  ctx.fillStyle = background
  ctx.fillRect(0, 0, width, height)

  const core = ctx.createRadialGradient(origin.x, origin.y, 0, origin.x, origin.y, Math.min(width, height) * 0.72)
  core.addColorStop(0, 'rgba(255,255,255,.24)')
  core.addColorStop(0.2, 'rgba(78,213,255,.17)')
  core.addColorStop(0.58, 'rgba(13,71,230,.08)')
  core.addColorStop(1, 'rgba(0,15,72,0)')
  ctx.fillStyle = core
  ctx.fillRect(0, 0, width, height)

  const bandX = width * 0.79
  const band = ctx.createLinearGradient(bandX - width * 0.13, 0, bandX + width * 0.13, 0)
  band.addColorStop(0, 'rgba(112,225,255,0)')
  band.addColorStop(0.44, 'rgba(184,244,255,.3)')
  band.addColorStop(0.52, 'rgba(255,255,255,.74)')
  band.addColorStop(0.62, 'rgba(96,217,255,.24)')
  band.addColorStop(1, 'rgba(50,178,255,0)')
  ctx.fillStyle = band
  ctx.fillRect(0, 0, width, height)

  ctx.globalCompositeOperation = 'lighter'
  ctx.fillStyle = '#dffaff'
  for (const mote of effects.ambient) {
    const drift = Math.sin(now * 0.00045 + mote.phase) * 13
    const x = mote.x * width + drift
    const y = mote.y * height + Math.cos(now * 0.00032 + mote.phase) * 8
    ctx.globalAlpha = alpha * mote.alpha * (0.55 + Math.sin(now * 0.003 + mote.phase) * 0.45)
    ctx.beginPath()
    ctx.arc(x, y, mote.size, 0, Math.PI * 2)
    ctx.fill()
  }
  ctx.restore()
}

function drawWingStrands(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  origin: Point,
  strands: WingStrand[],
  progress: number,
  alpha: number,
  now: number
) {
  ctx.save()
  ctx.globalCompositeOperation = 'lighter'

  for (let index = 0; index < strands.length; index += 1) {
    const strand = strands[index]!
    const local = clamp01((progress - strand.delay * 0.42) / (1 - strand.delay * 0.42))
    if (local <= 0) continue
    const available = easeOutCubic(local)
    const lane = strand.lane
    const flutter = Math.sin(now * 0.00145 + strand.phase) * (1.8 + Math.abs(lane) * 3.2)
    const start = { x: origin.x, y: origin.y }
    const end: Point = {
      x: width * (0.82 + Math.cos(lane * Math.PI * 0.5) * 0.075),
      y: height * 0.5 + lane * height * 0.43 + flutter
    }
    const controlA: Point = {
      x: start.x + (end.x - start.x) * 0.34,
      y: start.y + lane * height * 0.055 + Math.sin(strand.phase) * 5
    }
    const controlB: Point = {
      x: end.x - width * (0.075 + Math.abs(lane) * 0.035),
      y: end.y - lane * height * 0.13
    }
    const pointCount = 58

    const trace = (lineWidth: number, opacity: number) => {
      ctx.beginPath()
      ctx.moveTo(start.x, start.y)
      for (let step = 1; step <= pointCount; step += 1) {
        const amount = step / pointCount
        if (amount > available) break
        const point = pointOnCubic(start, controlA, controlB, end, amount)
        const noise = Math.sin(amount * 15 + strand.phase + now * 0.0008) * strand.weight * amount * 1.1
        ctx.lineTo(point.x, point.y + noise)
      }
      ctx.strokeStyle = strand.color
      ctx.lineWidth = lineWidth
      ctx.globalAlpha = alpha * opacity
      ctx.stroke()
    }
    trace(8, 0.06)
    trace(2.8, 0.2)
    trace(Math.max(0.75, strand.weight), 0.9)

    const tipAmount = available
    const tip = pointOnCubic(start, controlA, controlB, end, tipAmount)
    const tipVelocity = cubicDerivative(start, controlA, controlB, end, tipAmount)
    drawReferenceBird(
      ctx,
      tip,
      15 + Math.abs(lane) * 4,
      Math.sin(now * 0.0135 + strand.phase),
      alpha * Math.min(1, local * 2.6),
      rotationFromVelocity(tipVelocity),
      6,
      strand.color
    )

    ctx.fillStyle = strand.color
    for (let speck = 7; speck < pointCount * available; speck += 8) {
      const amount = speck / pointCount
      const point = pointOnCubic(start, controlA, controlB, end, amount)
      ctx.globalAlpha = alpha * (0.3 + ((speck + index) % 3) * 0.18)
      ctx.beginPath()
      ctx.arc(point.x, point.y + Math.sin(speck + strand.phase) * 2, 0.7 + (index % 4) * 0.18, 0, Math.PI * 2)
      ctx.fill()
    }
  }
  ctx.restore()
}

function revealHomeFromBottomLeft(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  progress: number
) {
  if (progress <= 0) return
  const eased = easeInOutSine(progress)
  const radius = Math.hypot(width, height) * eased + 2

  ctx.save()
  ctx.globalCompositeOperation = 'destination-out'
  ctx.fillStyle = '#000'
  ctx.beginPath()
  ctx.arc(0, height, radius, 0, Math.PI * 2)
  ctx.fill()
  ctx.restore()

  if (progress < 0.98) {
    ctx.save()
    ctx.globalCompositeOperation = 'source-over'
    ctx.globalAlpha = (1 - progress) * 0.42
    ctx.strokeStyle = '#dffaff'
    ctx.shadowBlur = 18
    ctx.shadowColor = '#61dfff'
    ctx.lineWidth = 1.2
    ctx.beginPath()
    ctx.arc(0, height, radius, -Math.PI / 2, 0)
    ctx.stroke()
    ctx.restore()
  }
}

export async function createJourneySketch(
  host: HTMLElement,
  readSnapshot: SnapshotReader
): Promise<JourneySketchController> {
  const [{ default: P5 }, { default: accessibility }] = await Promise.all([
    import('p5/core'),
    import('p5/accessibility')
  ])
  accessibility(P5)

  let active = true
  let p5Instance: InstanceType<typeof P5>
  let transitionStartedAt = 0
  let transitionGeometry: JourneyGeometry | null = null
  let effects: JourneyEffects | null = null
  let lastBird: Point = { x: window.innerWidth * 0.34, y: window.innerHeight * 0.48 }
  let lastBirdRotation = 0
  let launchBird: Point = { ...lastBird }
  let launchBirdRotation = 0
  let lastVisibilityHandler: (() => void) | undefined
  let lastResizeHandler: (() => void) | undefined

  p5Instance = new P5((p: any) => {
    const render = (ctx: CanvasRenderingContext2D, now: number) => {
      const snapshot = readSnapshot()
      const geometry = getStageGeometry(p.width, p.height)
      const compact = p.width < 720
      ctx.clearRect(0, 0, p.width, p.height)

      // The component remains mounted briefly while the route settles. Do not
      // let the idle bird reappear over the newly revealed home page.
      if (snapshot.state === 'done') return

      const transitioning = ['success-arm', 'sprint', 'impact', 'fracture', 'branch', 'reveal'].includes(snapshot.state)
      if (transitioning && snapshot.successStartedAt !== transitionStartedAt) {
        transitionStartedAt = snapshot.successStartedAt
        transitionGeometry = geometry
        launchBird = { ...lastBird }
        launchBirdRotation = lastBirdRotation
        effects = buildEffects(geometry, p.width, p.height, compact)
      }

      if (!transitioning) {
        const elapsed = now % journeyConfig.idle.periodMs
        const cycle = elapsed / journeyConfig.idle.periodMs
        const errorElapsed = snapshot.state === 'error' ? now - snapshot.errorStartedAt : 0
        const terminalShake = snapshot.state === 'error' && errorElapsed < 440
          ? Math.sin(errorElapsed * 0.095) * (1 - errorElapsed / 440) * 5
          : 0
        const lineAlpha = snapshot.passwordReady ? 0.96 : journeyConfig.idle.lineAlpha

        ctx.save()
        ctx.strokeStyle = `rgba(255,255,255,${lineAlpha})`
        ctx.lineWidth = 1.15
        ctx.beginPath()
        ctx.moveTo(geometry.start.x + 15, geometry.lineY)
        ctx.lineTo(geometry.end.x - 15 + terminalShake, geometry.lineY)
        ctx.stroke()
        ctx.restore()
        drawNode(ctx, geometry.start, 'start', 0.98)
        drawNode(ctx, { x: geometry.end.x + terminalShake, y: geometry.end.y }, 'end', 0.98)

        const startX = geometry.start.x + 19
        const endX = geometry.end.x - 19
        const pose = getIdleFlightPose(geometry, cycle, now)
        lastBird = pose.point
        lastBirdRotation = pose.rotation
        drawReferenceBird(ctx, pose.point, geometry.birdSize, pose.morph, 0.98, pose.rotation)

        if (snapshot.state === 'submitting') {
          ctx.save()
          ctx.fillStyle = '#fff'
          for (let index = 0; index < 5; index += 1) {
            const pulse = (now * 0.00028 + index / 5) % 1
            ctx.globalAlpha = 0.34 * (1 - pulse)
            ctx.beginPath()
            ctx.arc(lerp(startX, endX, pulse), geometry.lineY, 1.25, 0, Math.PI * 2)
            ctx.fill()
          }
          ctx.restore()
        }

        if (snapshot.state === 'error' && errorElapsed < 650) {
          const ripple = clamp01(errorElapsed / 650)
          ctx.save()
          ctx.strokeStyle = `rgba(255,255,255,${0.36 * (1 - ripple)})`
          ctx.lineWidth = 1
          ctx.beginPath()
          ctx.arc(geometry.end.x, geometry.end.y, 17 + ripple * 36, Math.PI * 0.68, Math.PI * 1.32)
          ctx.stroke()
          ctx.restore()
        }
        return
      }

      const elapsed = Math.max(0, now - transitionStartedAt)
      const fixed = transitionGeometry || geometry
      const burst = effects || buildEffects(fixed, p.width, p.height, compact)
      const masterAlpha = 1
      const blackIn = easeOutCubic(elapsed / 190)

      ctx.save()
      ctx.globalAlpha = blackIn * masterAlpha
      ctx.fillStyle = '#000'
      ctx.fillRect(0, 0, p.width, p.height)
      ctx.restore()

      const energyProgress = clamp01((elapsed - 1510) / 980)
      if (energyProgress > 0) {
        drawEnergyBackdrop(ctx, p.width, p.height, fixed.end, burst, energyProgress, masterAlpha, now)
      }

      if (elapsed < journeyConfig.fracture.startMs) {
        ctx.save()
        ctx.globalAlpha = masterAlpha
        ctx.strokeStyle = 'rgba(255,255,255,.92)'
        ctx.lineWidth = 1.2
        ctx.beginPath()
        ctx.moveTo(fixed.start.x + 15, fixed.lineY)
        ctx.lineTo(fixed.end.x - 15, fixed.lineY)
        ctx.stroke()
        ctx.restore()
        drawNode(ctx, fixed.start, 'start', masterAlpha)
        drawNode(ctx, fixed.end, 'end', masterAlpha, elapsed > 1000 ? 1 + Math.sin((elapsed - 1000) * 0.025) * 0.08 : 1)
      }

      const startPoint = { x: fixed.start.x + 22, y: fixed.lineY - 27 }
      if (elapsed < journeyConfig.sprint.returnMs) {
        const linear = clamp01(elapsed / journeyConfig.sprint.returnMs)
        const amount = easeInOutSine(linear)
        const distance = Math.hypot(startPoint.x - launchBird.x, startPoint.y - launchBird.y)
        const handle = Math.min(96, Math.max(34, distance * 0.28))
        const heading = launchBirdRotation + Math.PI
        const controlA = {
          x: launchBird.x + Math.cos(heading) * handle,
          y: launchBird.y + Math.sin(heading) * handle
        }
        const controlB = {
          x: startPoint.x - Math.min(54, Math.max(30, distance * 0.18)),
          y: startPoint.y - Math.min(28, Math.max(12, distance * 0.09))
        }
        const point = pointOnCubic(launchBird, controlA, controlB, startPoint, amount)
        const velocity = cubicDerivative(launchBird, controlA, controlB, startPoint, amount)
        for (let index = 4; index >= 1; index -= 1) {
          const trailAmount = Math.max(0, amount - index * 0.042)
          if (trailAmount <= 0) continue
          const trailPoint = pointOnCubic(launchBird, controlA, controlB, startPoint, trailAmount)
          const trailVelocity = cubicDerivative(launchBird, controlA, controlB, startPoint, trailAmount)
          drawReferenceBird(
            ctx,
            trailPoint,
            fixed.birdSize * (1 - index * 0.025),
            Math.sin(now * 0.0142 - index * 0.3),
            masterAlpha * (0.17 / index),
            rotationFromVelocity(trailVelocity),
            5
          )
        }
        drawReferenceBird(ctx, point, fixed.birdSize, Math.sin(now * 0.0142), masterAlpha, rotationFromVelocity(velocity))
        if (linear > 0.55) drawSpeedEchoes(ctx, point, linear, masterAlpha * (linear - 0.55) * 0.62)
      } else if (elapsed < journeyConfig.sprint.sprintEndMs) {
        const local = clamp01((elapsed - journeyConfig.sprint.returnMs) / (journeyConfig.sprint.sprintEndMs - journeyConfig.sprint.returnMs))
        const sprint = easeInExpo(local)
        const point = {
          x: lerp(startPoint.x, fixed.end.x - 3, sprint),
          y: lerp(startPoint.y, fixed.end.y, sprint) - Math.sin(sprint * Math.PI) * 39
        }
        for (let index = 7; index >= 1; index -= 1) {
          const trail = Math.max(0, sprint - index * 0.027)
          const trailPoint = {
            x: lerp(startPoint.x, fixed.end.x - 3, trail),
            y: lerp(startPoint.y, fixed.end.y, trail) - Math.sin(trail * Math.PI) * 39
          }
          const trailVelocity = {
            x: fixed.end.x - 3 - startPoint.x,
            y: fixed.end.y - startPoint.y - Math.cos(trail * Math.PI) * Math.PI * 39
          }
          drawReferenceBird(
            ctx,
            trailPoint,
            fixed.birdSize * (0.98 - index * 0.018),
            0.15,
            masterAlpha * (0.25 / index),
            rotationFromVelocity(trailVelocity),
            5
          )
        }
        const velocity = {
          x: fixed.end.x - 3 - startPoint.x,
          y: fixed.end.y - startPoint.y - Math.cos(sprint * Math.PI) * Math.PI * 39
        }
        drawReferenceBird(ctx, point, fixed.birdSize, Math.sin(now * 0.006), masterAlpha, rotationFromVelocity(velocity))
        if (local > 0.5) drawSpeedEchoes(ctx, point, local, masterAlpha * easeOutCubic((local - 0.5) * 2))
      }

      if (elapsed >= 990 && elapsed < 1540) {
        const wave = clamp01((elapsed - 990) / 550)
        ctx.save()
        ctx.strokeStyle = '#fff'
        ctx.lineCap = 'round'
        for (let index = 0; index < 6; index += 1) {
          const local = clamp01(wave - index * 0.075)
          ctx.globalAlpha = masterAlpha * (1 - local) * (0.42 - index * 0.048)
          ctx.lineWidth = 1.35
          ctx.beginPath()
          ctx.ellipse(fixed.end.x - 5 - index * 4, fixed.end.y, 18 + local * (88 + index * 13), 12 + local * (55 + index * 8), 0, Math.PI * 0.66, Math.PI * 1.34)
          ctx.stroke()
        }
        ctx.restore()
      }

      if (elapsed >= journeyConfig.fracture.startMs && elapsed < 2100) {
        const fracture = clamp01((elapsed - journeyConfig.fracture.startMs) / 620)
        ctx.save()
        ctx.fillStyle = '#fff'
        for (const particle of burst.lineParticles) {
          const local = clamp01(fracture * 1.2 - (1 - particle.u) * 0.18)
          ctx.globalAlpha = masterAlpha * (1 - local) * 0.9
          ctx.beginPath()
          ctx.arc(
            particle.x + particle.vx * local * 26,
            particle.y + particle.vy * local * 26 + local * local * 10,
            particle.size,
            0,
            Math.PI * 2
          )
          ctx.fill()
        }
        ctx.restore()
      }

      if (elapsed >= 1060 && elapsed < 2600) {
        const explosion = clamp01((elapsed - 1060) / 1540)
        const fade = 1 - clamp01((explosion - 0.68) / 0.32)
        ctx.save()
        ctx.globalCompositeOperation = 'lighter'
        ctx.fillStyle = '#fff'
        for (const particle of burst.sparks) {
          const distance = particle.speed * easeOutCubic(explosion) * 32
          ctx.globalAlpha = masterAlpha * fade * particle.life
          ctx.beginPath()
          ctx.arc(
            fixed.end.x + Math.cos(particle.angle) * distance,
            fixed.end.y + Math.sin(particle.angle) * distance + explosion * explosion * 12,
            particle.size * (1 - explosion * 0.35),
            0,
            Math.PI * 2
          )
          ctx.fill()
        }
        ctx.restore()
      }

      if (elapsed >= journeyConfig.routes.startMs && elapsed < journeyConfig.reveal.finishAt) {
        const extension = clamp01((elapsed - journeyConfig.routes.startMs) / (journeyConfig.routes.extendEndMs - journeyConfig.routes.startMs))
        const routeFade = 1 - easeInOutSine(clamp01((elapsed - journeyConfig.routes.fadeStartMs) / (journeyConfig.routes.fadeEndMs - journeyConfig.routes.fadeStartMs)))
        drawWingStrands(ctx, p.width, p.height, fixed.end, burst.strands, extension, masterAlpha * routeFade, now)
      }

      if (elapsed >= 1030 && elapsed < 1380) {
        const flash = 1 - (elapsed - 1030) / 350
        ctx.save()
        ctx.globalAlpha = masterAlpha * flash * 0.42
        ctx.fillStyle = '#fff'
        ctx.shadowBlur = 38
        ctx.shadowColor = '#fff'
        ctx.beginPath()
        ctx.arc(fixed.end.x, fixed.end.y, 7 + (1 - flash) * 34, 0, Math.PI * 2)
        ctx.fill()
        ctx.restore()
      }

      const revealProgress = clamp01((elapsed - journeyConfig.reveal.peelStart) / (journeyConfig.reveal.peelEnd - journeyConfig.reveal.peelStart))
      revealHomeFromBottomLeft(ctx, p.width, p.height, revealProgress)
    }

    p.setup = () => {
      const density = (navigator.hardwareConcurrency || 8) <= 4 ? 1 : Math.min(window.devicePixelRatio || 1, 1.35)
      p.pixelDensity(density)
      const canvas = p.createCanvas(window.innerWidth, window.innerHeight)
      canvas.elt.setAttribute('aria-hidden', 'true')
      canvas.elt.setAttribute('role', 'presentation')
      canvas.elt.classList.add('auth-journey-canvas')
    }

    p.draw = () => {
      const ctx = p.drawingContext as CanvasRenderingContext2D
      render(ctx, performance.now())
    }

    lastResizeHandler = () => p.resizeCanvas(window.innerWidth, window.innerHeight)
    lastVisibilityHandler = () => {
      if (document.hidden || !active) p.noLoop()
      else p.loop()
    }
    window.addEventListener('resize', lastResizeHandler, { passive: true })
    document.addEventListener('visibilitychange', lastVisibilityHandler)
  }, host)

  return {
    setActive(nextActive: boolean) {
      active = nextActive
      if (document.hidden || !nextActive) p5Instance.noLoop()
      else p5Instance.loop()
    },
    remove() {
      if (lastResizeHandler) window.removeEventListener('resize', lastResizeHandler)
      if (lastVisibilityHandler) document.removeEventListener('visibilitychange', lastVisibilityHandler)
      p5Instance.remove()
    }
  }
}
