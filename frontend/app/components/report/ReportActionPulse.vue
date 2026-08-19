<script setup lang="ts">
const props = defineProps<{
  done: number
  total: number
  hours: number
  evidence: number
  kinds: number
}>()

const completion = computed(() => props.total ? Math.round(props.done / props.total * 100) : 0)
const center = 110
const signature = computed(() => `A${String(props.total).padStart(2, '0')} · H${String(Math.round(props.hours)).padStart(2, '0')} · E${String(props.evidence).padStart(2, '0')}`)
const energy = computed(() => Math.max(12, Math.min(100, Math.round(completion.value * .62 + Math.min(props.hours, 24) * 1.25 + props.kinds * 4))))

function loopPath(ring: number) {
  const points: string[] = []
  const radius = 35 + ring * 15
  const phase = (completion.value + props.hours * 3 + props.evidence * 11 + ring * 17) * Math.PI / 180
  for (let index = 0; index <= 64; index += 1) {
    const angle = index / 64 * Math.PI * 2
    const wobble = Math.sin(angle * (3 + ring) + phase) * (2.2 + ring * .55)
      + Math.cos(angle * 2 - phase * .5) * 1.4
    const x = center + Math.cos(angle) * (radius + wobble)
    const y = center + Math.sin(angle) * (radius + wobble)
    points.push(`${index ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)}`)
  }
  return `${points.join(' ')} Z`
}

const loops = computed(() => Array.from({ length: 4 }, (_, index) => loopPath(index)))
const nodes = computed(() => Array.from({ length: Math.max(1, props.total) }, (_, index) => {
  const angle = -Math.PI / 2 + index / Math.max(1, props.total) * Math.PI * 2
  const radius = 93
  return {
    x: center + Math.cos(angle) * radius,
    y: center + Math.sin(angle) * radius,
    done: index < props.done
  }
}))
</script>

<template>
  <figure class="action-pulse" :aria-label="`行动回路：${done}/${total} 项完成，预计投入 ${hours} 小时`">
    <svg viewBox="0 0 220 220" role="img" aria-hidden="true">
      <defs>
        <radialGradient id="action-pulse-core" cx="38%" cy="32%">
          <stop offset="0" stop-color="#fffdf2" />
          <stop offset="1" stop-color="#eadba7" />
        </radialGradient>
        <filter id="action-pulse-glow" x="-80%" y="-80%" width="260%" height="260%">
          <feGaussianBlur stdDeviation="3.2" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>
      <g class="pulse-crosshair">
        <line x1="110" y1="10" x2="110" y2="210" />
        <line x1="10" y1="110" x2="210" y2="110" />
      </g>
      <circle class="pulse-guide" cx="110" cy="110" r="94" />
      <circle class="pulse-progress" cx="110" cy="110" r="99" pathLength="100" :stroke-dasharray="`${completion} ${100 - completion}`" />
      <path v-for="(path,index) in loops" :key="index" class="pulse-loop" :style="{ '--ring': index }" :d="path" />
      <g v-for="(node,index) in nodes" :key="index" class="pulse-node-group" :class="{ done: node.done }">
        <circle class="pulse-node-halo" :cx="node.x" :cy="node.y" r="7" />
        <circle class="pulse-node" :cx="node.x" :cy="node.y" r="3.6" />
      </g>
      <circle class="pulse-core-shadow" cx="110" cy="110" r="32" />
      <circle class="pulse-core" cx="110" cy="110" r="27" />
      <text class="pulse-value" x="110" y="108" text-anchor="middle">{{ completion }}%</text>
      <text class="pulse-label" x="110" y="123" text-anchor="middle">行动纹样</text>
      <text class="pulse-signature" x="110" y="216" text-anchor="middle">{{ signature }}</text>
    </svg>
    <figcaption>
      <span><i />{{ evidence }} 项需留证</span><span><i />{{ kinds }} 类行动</span><span><i />{{ hours }}h 投入</span><span><i />{{ energy }} 活跃度</span>
    </figcaption>
  </figure>
</template>

<style scoped>
.action-pulse{display:grid;place-items:center;min-width:0}.action-pulse svg{width:min(100%,18.5rem);overflow:visible;filter:drop-shadow(0 22px 34px rgb(0 0 0/.28))}.pulse-crosshair{stroke:rgb(255 255 255/.045);stroke-width:.6;stroke-dasharray:1 8}.pulse-guide,.pulse-progress,.pulse-loop{fill:none}.pulse-guide{stroke:rgb(255 255 255/.13);stroke-dasharray:1 6}.pulse-progress{stroke:#f0d77b;stroke-width:1.8;stroke-linecap:round;transform:rotate(-90deg);transform-origin:center;filter:url(#action-pulse-glow);opacity:.85}.pulse-loop{stroke:color-mix(in srgb,#67e8c2 calc(44% + var(--ring) * 11%),#b8f7ff);stroke-width:calc(.8px + var(--ring) * .24px);stroke-dasharray:calc(2px + var(--ring) * 1px) calc(1.6px + var(--ring) * .7px);opacity:calc(.38 + var(--ring) * .14);transform-origin:center;animation:pulse-draw 1.15s cubic-bezier(.22,1,.36,1) both;animation-delay:calc(var(--ring) * 75ms)}.pulse-node-halo{fill:none;stroke:rgb(103 232 194/.14);stroke-width:1}.pulse-node{fill:#173d46;stroke:rgb(255 255 255/.42);stroke-width:1.3}.pulse-node-group.done .pulse-node{fill:#67e8c2;stroke:#e4fff6;filter:url(#action-pulse-glow)}.pulse-node-group.done .pulse-node-halo{stroke:#67e8c2;animation:node-breathe 2.4s ease-in-out infinite}.pulse-core-shadow{fill:rgb(3 28 37/.72);stroke:rgb(255 255 255/.08);stroke-width:5}.pulse-core{fill:url(#action-pulse-core);stroke:rgb(255 255 255/.5)}.pulse-value{fill:#082f36;font-size:17px;font-weight:850}.pulse-label{fill:#416168;font-size:6.7px;letter-spacing:.1em}.pulse-signature{fill:rgb(226 242 242/.5);font:600 5.8px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.15em}.action-pulse figcaption{display:flex;max-width:18rem;flex-wrap:wrap;justify-content:center;gap:.4rem 1rem;color:rgb(226 242 242/.68);font-size:.62rem}.action-pulse figcaption span{display:flex;align-items:center;gap:.3rem}.action-pulse figcaption i{width:.28rem;height:.28rem;border-radius:50%;background:#67e8c2;box-shadow:0 0 10px #67e8c2}@keyframes pulse-draw{from{stroke-dashoffset:90;opacity:0;transform:scale(.86) rotate(-10deg)}to{stroke-dashoffset:0}}@keyframes node-breathe{50%{r:8.5;opacity:.35}}@media(prefers-reduced-motion:reduce){.pulse-loop,.pulse-node-group.done .pulse-node-halo{animation:none}}
</style>
