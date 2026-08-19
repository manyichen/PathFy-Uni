<script setup lang="ts">
const { isAuthenticated } = useAuth()
const journey = useAuthJourney()

const metrics = [
  { label: '岗位样本', value: '10,000+', icon: 'i-lucide-briefcase-business' },
  { label: '画像维度', value: '8 维', icon: 'i-lucide-radar' },
  { label: '规划输出', value: '短中期', icon: 'i-lucide-file-check-2' }
]

const workflow = [
  { title: '整理材料', desc: '建立能力证据', icon: 'i-lucide-folder-check' },
  { title: '生成画像', desc: '定位优势短板', icon: 'i-lucide-scan-face' },
  { title: '匹配岗位', desc: '比较真实要求', icon: 'i-lucide-git-compare' },
  { title: '行动计划', desc: '拆解阶段任务', icon: 'i-lucide-list-checks' },
  { title: '持续复盘', desc: '用结果校准', icon: 'i-lucide-refresh-cw' }
]

const entryActions = computed(() => [
  { to: '/profile', label: isAuthenticated.value ? '继续能力画像' : '开始能力画像', icon: 'i-lucide-radar', primary: true },
  { to: '/jobs', label: isAuthenticated.value ? '继续岗位探索' : '浏览岗位库', icon: 'i-lucide-search', primary: false },
  { to: '/report', label: isAuthenticated.value ? '继续生涯报告' : '生成生涯报告', icon: 'i-lucide-file-chart-column', primary: false }
])

const focusItems = [
  { label: '实践能力', value: 82 },
  { label: '数字素养', value: 79 },
  { label: '团队协作', value: 70 }
]

const radarAxes = [
  { label: '理论', value: 68 },
  { label: '交叉', value: 55 },
  { label: '实践', value: 82 },
  { label: '数字', value: 79 },
  { label: '创新', value: 41 },
  { label: '协作', value: 70 },
  { label: '社会', value: 36 },
  { label: '成长', value: 64 }
]

const radarCenter = 120
const radarRadius = 78

function radarPoint(index: number, value: number) {
  const angle = -Math.PI / 2 + index * 2 * Math.PI / radarAxes.length
  const r = value / 100 * radarRadius
  return {
    x: radarCenter + r * Math.cos(angle),
    y: radarCenter + r * Math.sin(angle)
  }
}

function polygonFor(value: number) {
  return radarAxes.map((_, index) => {
    const point = radarPoint(index, value)
    return `${point.x},${point.y}`
  }).join(' ')
}

const radarPolygon = computed(() => radarAxes.map((axis, index) => {
  const point = radarPoint(index, axis.value)
  return `${point.x},${point.y}`
}).join(' '))
</script>

<template>
  <section class="home-hero overflow-hidden" :class="{ 'is-auth-revealing': journey.isRevealing.value }" aria-labelledby="home-hero-title">
    <img
      src="https://images.unsplash.com/photo-1552664730-d307ca884978?auto=format&fit=crop&w=1800&q=82"
      alt=""
      aria-hidden="true"
      width="1800"
      height="1000"
      fetchpriority="high"
      decoding="async"
      class="hero-image"
    >
    <div class="hero-overlay" />

    <div class="hero-content">
      <div class="max-w-3xl">
        <UBadge class="hero-enter hero-enter-badge" color="primary" variant="soft" icon="i-lucide-route" label="大学生职业规划工作台" />
        <h1 id="home-hero-title" class="hero-enter hero-enter-title mt-5 max-w-3xl text-4xl font-bold leading-tight text-white sm:text-6xl">
          职业规划智能体
        </h1>
        <p class="hero-enter hero-enter-copy mt-5 max-w-2xl text-base leading-7 text-white/80 sm:text-lg sm:leading-8">
          把岗位数据、能力证据、工作偏好、人岗匹配和生涯报告放进同一条工作流，让职业方向变成可解释、可执行、可复盘的行动计划。
        </p>
        <div class="hero-enter hero-enter-actions mt-7 grid gap-3 sm:grid-cols-3" aria-label="规划快捷入口">
          <UButton v-for="action in entryActions" :key="action.to" :to="action.to" size="xl" color="neutral" :variant="action.primary ? 'solid' : 'outline'" :icon="action.icon">{{ action.label }}</UButton>
        </div>
      </div>

      <div class="hero-enter hero-enter-console mt-8 grid gap-4 lg:grid-cols-[1.08fr_0.92fr]">
        <div class="hero-panel">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p class="text-xs font-semibold uppercase text-cyan-100">Planning Console</p>
              <h2 class="mt-1 text-lg font-semibold text-white">从岗位探索到行动计划</h2>
            </div>
            <span class="rounded-full bg-emerald-300/15 px-3 py-1 text-xs font-medium text-emerald-100">闭环流程</span>
          </div>

          <div class="mt-4 grid grid-cols-3 gap-2">
            <div v-for="metric in metrics" :key="metric.label" class="mini-tile">
              <UIcon :name="metric.icon" class="size-5 text-cyan-200" />
              <p class="mt-2 text-xs text-white/62">{{ metric.label }}</p>
              <p class="text-base font-semibold text-white sm:text-lg">{{ metric.value }}</p>
            </div>
          </div>

          <div class="mt-4 hidden gap-2 sm:grid sm:grid-cols-2 lg:grid-cols-5">
            <div v-for="(step, index) in workflow" :key="step.title" class="workflow-tile">
              <div class="grid size-8 place-items-center rounded-lg bg-white/12 text-cyan-100">
                <UIcon :name="step.icon" class="size-5" />
              </div>
              <p class="mt-2 text-sm font-semibold text-white">{{ step.title }}</p>
              <p class="mt-1 text-xs leading-5 text-white/62">{{ step.desc }}</p>
              <span class="absolute right-3 top-3 text-xs font-semibold text-white/35">0{{ index + 1 }}</span>
            </div>
          </div>
        </div>

        <div class="hidden gap-4 md:grid md:grid-cols-[0.92fr_1.08fr] lg:grid-cols-1 xl:grid-cols-[0.92fr_1.08fr]">
          <div class="hero-panel">
            <div class="flex items-center justify-between">
              <h2 class="text-sm font-semibold text-white">能力画像预览</h2>
              <span class="rounded-full bg-cyan-300/15 px-2 py-0.5 text-xs text-cyan-100">八维</span>
            </div>
            <svg width="216" height="216" viewBox="0 0 240 240" class="mx-auto mt-2 max-w-full" aria-hidden="true">
              <polygon v-for="tier in [25, 50, 75, 100]" :key="tier" :points="polygonFor(tier)" fill="none" stroke="rgba(255,255,255,.18)" />
              <g v-for="(axis, index) in radarAxes" :key="axis.label">
                <line :x1="radarCenter" :y1="radarCenter" :x2="radarPoint(index, 100).x" :y2="radarPoint(index, 100).y" stroke="rgba(255,255,255,.16)" />
                <text :x="radarPoint(index, 114).x" :y="radarPoint(index, 114).y" text-anchor="middle" dominant-baseline="middle" class="fill-white/70 text-[9px]">
                  {{ axis.label }}
                </text>
              </g>
              <polygon :points="radarPolygon" fill="rgba(45,212,191,.32)" stroke="rgb(94,234,212)" stroke-width="2.5" />
              <circle :cx="radarCenter" :cy="radarCenter" r="3" fill="rgb(252,211,77)" />
            </svg>
          </div>

          <div class="hero-panel">
            <h2 class="text-sm font-semibold text-white">当前优势</h2>
            <div class="mt-4 space-y-3">
              <div v-for="item in focusItems" :key="item.label">
                <div class="flex items-center justify-between text-xs">
                  <span class="text-white/70">{{ item.label }}</span>
                  <span class="font-semibold text-amber-200">{{ item.value }}%</span>
                </div>
                <div class="mt-1.5 h-2 overflow-hidden rounded-full bg-white/10">
                  <div class="h-full rounded-full bg-gradient-to-r from-teal-300 to-amber-200" :style="{ width: `${item.value}%` }" />
                </div>
              </div>
            </div>
            <UButton to="/match" block class="mt-5" color="primary" trailing-icon="i-lucide-arrow-right">进入匹配分析</UButton>
          </div>
        </div>
      </div>
    </div>
    <HomeHeroWaves />
  </section>
</template>

<style scoped>
.home-hero {
  position: relative;
  border-radius: 1rem;
  min-height: 42rem;
  background: #020617;
  color: white;
  box-shadow: 0 24px 60px -40px rgb(2 6 23 / 0.8);
}

.hero-image,
.hero-overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.hero-image {
  object-fit: cover;
  opacity: 0.74;
}

.hero-overlay {
  background:
    linear-gradient(90deg, rgb(2 6 23 / 0.96) 0%, rgb(15 23 42 / 0.82) 46%, hsl(var(--pathfy-hue) 70% 34% / 0.58) 100%),
    linear-gradient(0deg, rgb(2 6 23 / 0.44), rgb(2 6 23 / 0.08));
}

.hero-content {
  position: relative;
  z-index: 1;
  padding: 3rem 1.25rem 7rem;
}

@media (min-width: 768px) {
  .hero-content {
    padding: 4rem 2.5rem 8rem;
  }
}

.hero-panel {
  border: 1px solid rgb(255 255 255 / 0.15);
  border-radius: 0.75rem;
  background: rgb(2 6 23 / 0.58);
  padding: 1rem;
  box-shadow: 0 24px 48px -30px rgb(0 0 0 / 0.45);
  backdrop-filter: blur(14px);
}

.mini-tile,
.workflow-tile {
  position: relative;
  border: 1px solid rgb(255 255 255 / 0.1);
  border-radius: 0.65rem;
  background: rgb(255 255 255 / 0.08);
  padding: 0.75rem;
}

.is-auth-revealing .hero-enter {
  animation: auth-home-enter 1.9s cubic-bezier(.22, 1, .36, 1) both;
}

.is-auth-revealing .hero-image {
  animation: auth-home-surface-enter 2.35s cubic-bezier(.22, 1, .36, 1) both;
}

.is-auth-revealing .hero-enter-badge { animation-delay: 1.05s; }
.is-auth-revealing .hero-enter-title { animation-delay: 1.15s; }
.is-auth-revealing .hero-enter-copy { animation-delay: 1.27s; }
.is-auth-revealing .hero-enter-actions { animation-delay: 1.39s; }
.is-auth-revealing .hero-enter-console { animation-delay: 1.52s; }

@keyframes auth-home-enter {
    from { opacity: 0; filter: blur(7px); transform: translateX(-76px) scale(.992); }
    to { opacity: 1; filter: blur(0); transform: translateX(0) scale(1); }
}

@keyframes auth-home-surface-enter {
    from { opacity: .38; filter: saturate(.72) blur(3px); transform: translateX(-4.5%) scale(1.055); }
    to { opacity: .74; filter: saturate(1) blur(0); transform: translateX(0) scale(1); }
}

@media (prefers-reduced-motion: reduce) {
  .is-auth-revealing .hero-enter,
  .is-auth-revealing .hero-image { animation: none; }
}
</style>
