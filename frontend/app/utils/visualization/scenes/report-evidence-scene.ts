import type { ReportEvidenceDecisionRow, ReportEvidenceSceneData } from '~/types/report-evidence'
import type { P5SceneFactory, P5SceneSize } from '~/types/visualization'
import { loadP5 } from '../p5-loader'

interface RowBox { row: ReportEvidenceDecisionRow; x: number; y: number; width: number; height: number }

const stateColor = { hard_gap: '#e05a6d', verify: '#d99a2b', strength: '#148b80', opportunity: '#3b82c4' } as const
const stateTint = { hard_gap: 'rgba(224,90,109,.08)', verify: 'rgba(217,154,43,.09)', strength: 'rgba(20,139,128,.075)', opportunity: 'rgba(59,130,196,.075)' } as const
const closureColor = { verified: '#148b80', awaiting_review: '#d99a2b', in_progress: '#3b82c4', missing_action: '#d05b68' } as const

function emptyData(): ReportEvidenceSceneData {
  return {
    jobId: '', title: '', transitionKey: 'empty', selectedRowId: '', rows: [], orphanActions: [],
    summary: { coverage: 0, claimCount: 0, comparableCount: 0, riskCount: 0, actionCount: 0, linkedActionCount: 0, unlinkedActionCount: 0, completedActionCount: 0, outcomeEvidenceCount: 0 }
  }
}

function isSceneData(value: unknown): value is ReportEvidenceSceneData {
  if (!value || typeof value !== 'object') return false
  const candidate = value as Partial<ReportEvidenceSceneData>
  return Array.isArray(candidate.rows) && Array.isArray(candidate.orphanActions) && typeof candidate.transitionKey === 'string'
}

function clamp(value: number, minimum = 0, maximum = 100) {
  return Math.max(minimum, Math.min(maximum, value))
}

function roundedRect(ctx: CanvasRenderingContext2D, x: number, y: number, width: number, height: number, radius: number) {
  ctx.beginPath(); ctx.roundRect(x, y, width, height, radius)
}

function fitText(ctx: CanvasRenderingContext2D, text: string, maxWidth: number) {
  if (ctx.measureText(text).width <= maxWidth) return text
  let value = text
  while (value.length > 1 && ctx.measureText(`${value}…`).width > maxWidth) value = value.slice(0, -1)
  return `${value}…`
}

function drawLines(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, maxWidth: number, lineHeight: number, maxLines = 2) {
  const characters = [...text]
  const lines: string[] = []
  let line = ''
  for (const character of characters) {
    if (ctx.measureText(line + character).width <= maxWidth) line += character
    else { lines.push(line); line = character; if (lines.length === maxLines - 1) break }
  }
  const consumed = lines.join('').length
  if (lines.length < maxLines && consumed < characters.length) lines.push(characters.slice(consumed).join(''))
  else if (line && lines.length < maxLines) lines.push(line)
  const finalLines = lines.slice(0, maxLines).map((value, index) => index === maxLines - 1 ? fitText(ctx, value + (consumed + value.length < characters.length ? '…' : ''), maxWidth) : value)
  finalLines.forEach((value, index) => ctx.fillText(value, x, y + index * lineHeight))
}

export const createReportEvidenceScene: P5SceneFactory = async options => {
  const P5 = await loadP5()
  let data = isSceneData(options.data) ? options.data : emptyData()
  let size = options.size
  let active = true
  let reducedMotion = options.reducedMotion
  let hoveredId = ''
  let failed = false
  let setupComplete = false
  let rowBoxes: RowBox[] = []

  const p5Instance = new P5((p: any) => {
    const theme = () => {
      const styles = getComputedStyle(options.host)
      return {
        text: styles.getPropertyValue('--ui-text').trim() || '#24364d',
        muted: styles.getPropertyValue('--ui-text-muted').trim() || '#65758b',
        border: styles.getPropertyValue('--ui-border').trim() || '#d5dee8',
        bg: styles.getPropertyValue('--ui-bg').trim() || '#ffffff',
        elevated: styles.getPropertyValue('--ui-bg-elevated').trim() || '#f4f7fa'
      }
    }

    const layoutRows = () => {
      const compact = p.width < 760
      const top = compact ? 38 : 48
      const bottom = data.orphanActions.length ? 45 : 14
      const gap = compact ? 8 : 7
      const available = Math.max(1, p.height - top - bottom - gap * Math.max(0, data.rows.length - 1))
      const height = data.rows.length ? available / data.rows.length : available
      rowBoxes = data.rows.map((row, index) => ({ row, x: 12, y: top + index * (height + gap), width: p.width - 24, height }))
    }

    const drawBackdrop = (ctx: CanvasRenderingContext2D, colors: ReturnType<typeof theme>) => {
      ctx.clearRect(0, 0, p.width, p.height)
      const gradient = ctx.createLinearGradient(0, 0, p.width, p.height)
      gradient.addColorStop(0, 'rgba(36,165,206,.055)')
      gradient.addColorStop(.52, 'rgba(93,89,211,.035)')
      gradient.addColorStop(1, 'rgba(20,139,128,.055)')
      ctx.fillStyle = colors.bg; ctx.fillRect(0, 0, p.width, p.height)
      ctx.fillStyle = gradient; ctx.fillRect(0, 0, p.width, p.height)
      layoutRows()
    }

    const drawHeaders = (ctx: CanvasRenderingContext2D, colors: ReturnType<typeof theme>) => {
      ctx.textBaseline = 'middle'; ctx.textAlign = 'left'
      if (p.width < 760) {
        ctx.fillStyle = colors.muted; ctx.font = '600 12px system-ui, sans-serif'
        ctx.fillText('点击任一能力行，查看数值来源、行动与验收信息', 16, 20)
        return
      }
      const left = 18; const width = p.width - 36
      const columns = [
        { x: left, label: '能力维度', sub: '先识别判断类型' },
        { x: left + width * .155, label: '当前画像 vs 岗位标尺', sub: '直接展示真实差值' },
        { x: left + width * .43, label: '系统判断', sub: '结论与依据等级' },
        { x: left + width * .67, label: '关联行动', sub: '下一项可执行任务' },
        { x: left + width * .865, label: '成果闭环', sub: '是否已有真实证明' }
      ]
      columns.forEach(column => {
        ctx.fillStyle = colors.text; ctx.font = '700 12px system-ui, sans-serif'; ctx.fillText(column.label, column.x, 14)
        ctx.fillStyle = colors.muted; ctx.font = '10px system-ui, sans-serif'; ctx.fillText(column.sub, column.x, 30)
      })
    }

    const drawScoreComparison = (ctx: CanvasRenderingContext2D, row: ReportEvidenceDecisionRow, x: number, y: number, width: number, colors: ReturnType<typeof theme>, compact = false) => {
      const current = row.currentScore
      const required = row.requiredScore
      if (current === undefined || required === undefined) {
        ctx.fillStyle = colors.muted; ctx.font = '11px system-ui, sans-serif'; ctx.fillText('缺少当前分或岗位标尺', x, y)
        return
      }
      const lineY = y + (compact ? 3 : 5)
      const lineStart = x
      const lineEnd = x + width
      const currentX = lineStart + width * clamp(current) / 100
      const requiredX = lineStart + width * clamp(required) / 100
      ctx.strokeStyle = colors.border; ctx.lineWidth = 4; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(lineStart, lineY); ctx.lineTo(lineEnd, lineY); ctx.stroke()
      ctx.strokeStyle = stateColor[row.state]; ctx.globalAlpha = .42; ctx.lineWidth = 5; ctx.beginPath(); ctx.moveTo(Math.min(currentX, requiredX), lineY); ctx.lineTo(Math.max(currentX, requiredX), lineY); ctx.stroke(); ctx.globalAlpha = 1
      ctx.fillStyle = '#24a5ce'; ctx.beginPath(); ctx.arc(currentX, lineY, 5, 0, Math.PI * 2); ctx.fill()
      ctx.save(); ctx.translate(requiredX, lineY); ctx.rotate(Math.PI / 4); ctx.fillStyle = '#8b72df'; ctx.fillRect(-4.5, -4.5, 9, 9); ctx.restore()
      ctx.font = '700 10px system-ui, sans-serif'; ctx.textBaseline = 'top'
      ctx.fillStyle = '#198aae'; ctx.textAlign = currentX > lineStart + width * .82 ? 'right' : 'left'; ctx.fillText(`当前 ${Math.round(current)}`, currentX + (ctx.textAlign === 'right' ? -7 : 7), lineY + 8)
      ctx.fillStyle = '#7659d0'; ctx.textAlign = requiredX > lineStart + width * .82 ? 'right' : 'left'; ctx.fillText(`要求 ${Math.round(required)}`, requiredX + (ctx.textAlign === 'right' ? -7 : 7), lineY - 20)
      ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.fillStyle = stateColor[row.state]; ctx.font = '650 10px system-ui, sans-serif'
      if (!compact) ctx.fillText(fitText(ctx, row.comparisonLabel, width), x, lineY + 25)
    }

    const drawDesktopRow = (ctx: CanvasRenderingContext2D, box: RowBox, index: number, colors: ReturnType<typeof theme>) => {
      const { row, x, y, width, height } = box
      const selected = row.id === data.selectedRowId
      const hovered = row.id === hoveredId
      const accent = stateColor[row.state]
      ctx.save()
      ctx.fillStyle = selected ? stateTint[row.state] : colors.elevated
      ctx.strokeStyle = selected || hovered ? accent : colors.border; ctx.lineWidth = selected ? 1.6 : 1
      if (selected && active && !reducedMotion) { ctx.shadowColor = accent; ctx.shadowBlur = 8 + Math.sin(performance.now() / 300) * 2 }
      roundedRect(ctx, x, y, width, height, 10); ctx.fill(); ctx.stroke(); ctx.shadowBlur = 0
      ctx.fillStyle = accent; roundedRect(ctx, x, y, 4, height, 2); ctx.fill()

      const innerX = x + 14; const innerW = width - 28
      const columnX = [innerX, innerX + innerW * .155, innerX + innerW * .43, innerX + innerW * .67, innerX + innerW * .865]
      const [dimensionX, comparisonX, claimX, actionX, closureX] = columnX as [number, number, number, number, number]
      for (const divider of columnX.slice(1)) { ctx.strokeStyle = colors.border; ctx.globalAlpha = .48; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(divider - 9, y + 10); ctx.lineTo(divider - 9, y + height - 10); ctx.stroke(); ctx.globalAlpha = 1 }

      ctx.textAlign = 'left'; ctx.textBaseline = 'middle'
      ctx.fillStyle = colors.muted; ctx.font = '700 10px ui-monospace, monospace'; ctx.fillText(String(index + 1).padStart(2, '0'), dimensionX, y + 18)
      ctx.fillStyle = colors.text; ctx.font = '750 14px system-ui, sans-serif'; ctx.fillText(fitText(ctx, row.dimensionLabel, innerW * .13), dimensionX, y + 40)
      ctx.fillStyle = accent; ctx.font = '700 11px system-ui, sans-serif'; ctx.fillText(row.stateLabel, dimensionX, y + height - 17)

      drawScoreComparison(ctx, row, comparisonX, y + height / 2 - 7, innerW * .245, colors)

      ctx.fillStyle = accent; ctx.font = '700 10px system-ui, sans-serif'; ctx.fillText(`${row.grade} 级系统依据 · 优先级 ${Math.round(row.priority)}`, claimX, y + 18)
      ctx.fillStyle = colors.text; ctx.font = '650 12px system-ui, sans-serif'; ctx.textBaseline = 'top'; drawLines(ctx, row.title, claimX, y + 33, innerW * .215, 16, 2)

      ctx.textBaseline = 'middle'
      if (row.nextAction) {
        ctx.fillStyle = colors.muted; ctx.font = '650 10px system-ui, sans-serif'; ctx.fillText(`${row.actions.length} 项行动 · ${row.nextAction.deadline}`, actionX, y + 18)
        ctx.fillStyle = colors.text; ctx.font = '650 12px system-ui, sans-serif'; ctx.textBaseline = 'top'; drawLines(ctx, row.nextAction.title, actionX, y + 33, innerW * .17, 16, 2)
      } else {
        ctx.fillStyle = closureColor.missing_action; ctx.font = '650 11px system-ui, sans-serif'; ctx.fillText('未配置针对性行动', actionX, y + height / 2)
      }

      const proofColor = closureColor[row.closureState]
      ctx.textBaseline = 'middle'; ctx.fillStyle = proofColor; ctx.beginPath(); ctx.arc(closureX + 3, y + 20, 4, 0, Math.PI * 2); ctx.fill()
      ctx.fillStyle = proofColor; ctx.font = '700 10px system-ui, sans-serif'; ctx.textBaseline = 'top'; drawLines(ctx, row.closureLabel, closureX + 11, y + 13, innerW * .125, 14, 2)
      ctx.fillStyle = colors.muted; ctx.font = '10px system-ui, sans-serif'; ctx.textBaseline = 'middle'; ctx.fillText(row.chainConnected ? '依据到行动已连通' : '依据链存在断点', closureX, y + height - 17)

      if (selected && active && !reducedMotion) {
        const progress = (performance.now() / 1900) % 1
        const start = comparisonX - 8; const end = closureX - 14
        ctx.fillStyle = accent; ctx.globalAlpha = .75; ctx.beginPath(); ctx.arc(start + (end - start) * progress, y + height - 4, 2.3, 0, Math.PI * 2); ctx.fill(); ctx.globalAlpha = 1
      }
      ctx.restore()
    }

    const drawCompactRow = (ctx: CanvasRenderingContext2D, box: RowBox, index: number, colors: ReturnType<typeof theme>) => {
      const { row, x, y, width, height } = box
      const selected = row.id === data.selectedRowId; const accent = stateColor[row.state]
      ctx.fillStyle = selected ? stateTint[row.state] : colors.elevated; ctx.strokeStyle = selected ? accent : colors.border; ctx.lineWidth = selected ? 1.5 : 1
      roundedRect(ctx, x, y, width, height, 10); ctx.fill(); ctx.stroke()
      ctx.fillStyle = accent; roundedRect(ctx, x, y, 4, height, 2); ctx.fill()
      ctx.textAlign = 'left'; ctx.textBaseline = 'middle'
      ctx.fillStyle = colors.muted; ctx.font = '700 10px ui-monospace, monospace'; ctx.fillText(String(index + 1).padStart(2, '0'), x + 13, y + 18)
      ctx.fillStyle = colors.text; ctx.font = '750 14px system-ui, sans-serif'; ctx.fillText(row.dimensionLabel, x + 40, y + 18)
      ctx.fillStyle = accent; ctx.font = '700 10px system-ui, sans-serif'; ctx.textAlign = 'right'; ctx.fillText(row.stateLabel, x + width - 13, y + 18)
      ctx.textAlign = 'left'; drawScoreComparison(ctx, row, x + 16, y + 37, width - 32, colors, true)
      const split = x + width * .53
      ctx.fillStyle = colors.text; ctx.font = '650 11px system-ui, sans-serif'; ctx.textBaseline = 'top'; drawLines(ctx, row.title, x + 16, y + 62, width * .46, 15, 2)
      ctx.fillStyle = row.nextAction ? colors.text : closureColor.missing_action; drawLines(ctx, row.nextAction?.title || '未配置针对性行动', split, y + 62, width * .42, 15, 2)
      ctx.fillStyle = closureColor[row.closureState]; ctx.font = '700 10px system-ui, sans-serif'; ctx.textBaseline = 'bottom'; ctx.textAlign = 'right'; ctx.fillText(row.closureLabel, x + width - 13, y + height - 8)
    }

    const drawOrphanNotice = (ctx: CanvasRenderingContext2D, colors: ReturnType<typeof theme>) => {
      if (!data.orphanActions.length) return
      const y = p.height - 31
      ctx.fillStyle = 'rgba(217,154,43,.09)'; ctx.strokeStyle = 'rgba(217,154,43,.35)'; roundedRect(ctx, 12, y - 9, p.width - 24, 27, 7); ctx.fill(); ctx.stroke()
      ctx.fillStyle = '#b77912'; ctx.font = '650 10px system-ui, sans-serif'; ctx.textBaseline = 'middle'; ctx.textAlign = 'left'
      ctx.fillText(`另有 ${data.orphanActions.length} 项行动未映射到当前判断：${fitText(ctx, data.orphanActions.map(action => action.title).join('、'), Math.max(80, p.width - 260))}`, 23, y + 4)
    }

    const render = () => {
      if (failed) return
      try {
        const ctx = p.drawingContext as CanvasRenderingContext2D; const colors = theme()
        drawBackdrop(ctx, colors); drawHeaders(ctx, colors)
        rowBoxes.forEach((box, index) => p.width < 760 ? drawCompactRow(ctx, box, index, colors) : drawDesktopRow(ctx, box, index, colors))
        drawOrphanNotice(ctx, colors)
        if (reducedMotion || !active) p.noLoop()
      } catch (error) { failed = true; p.noLoop(); options.onError(error, { phase: 'render' }) }
    }

    const hitRow = (x: number, y: number) => rowBoxes.find(box => x >= box.x && x <= box.x + box.width && y >= box.y && y <= box.y + box.height)?.row

    p.setup = () => {
      p.pixelDensity(size.pixelRatio); const canvas = p.createCanvas(size.width, size.height); canvas.parent(options.host)
      canvas.elt.classList.add('report-evidence-canvas'); canvas.elt.setAttribute('aria-hidden', 'true'); p.frameRate(30); setupComplete = true
      if (reducedMotion) p.noLoop()
    }
    p.draw = render
    p.mouseMoved = () => { const next = hitRow(p.mouseX, p.mouseY)?.id || ''; if (next !== hoveredId) { hoveredId = next; options.host.style.cursor = next ? 'pointer' : 'default'; p.redraw() } }
    p.mousePressed = () => { const row = hitRow(p.mouseX, p.mouseY); if (!row) return; data = { ...data, selectedRowId: row.id }; options.onSelect({ rowId: row.id }); p.redraw() }
  }, options.host)

  return {
    update(next) { data = isSceneData(next) ? next : emptyData(); p5Instance.redraw() },
    resize(next: P5SceneSize) { size = next; if (!setupComplete) return; p5Instance.pixelDensity(next.pixelRatio); p5Instance.resizeCanvas(next.width, next.height); p5Instance.redraw() },
    setActive(next) { active = next; if (active && !reducedMotion) p5Instance.loop(); else p5Instance.noLoop() },
    setReducedMotion(next) { reducedMotion = next; if (next || !active) p5Instance.noLoop(); else p5Instance.loop(); p5Instance.redraw() },
    resetView() { data = { ...data, selectedRowId: data.rows.find(row => row.state === 'hard_gap' || row.state === 'verify')?.id || data.rows[0]?.id || '' }; p5Instance.redraw() },
    destroy() { p5Instance.remove() }
  }
}
