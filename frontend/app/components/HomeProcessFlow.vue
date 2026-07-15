<script setup lang="ts">
const tracks = [
  {
    title: '先判断方向',
    desc: '从岗位样本、城市、能力标签里筛掉“听起来不错但不适合”的方向。',
    icon: 'i-lucide-compass',
    accent: '#0891b2'
  },
  {
    title: '再补齐证据',
    desc: '把课程、项目、竞赛和作品连接到目标岗位，不再只写抽象能力。',
    icon: 'i-lucide-folder-check',
    accent: '#0f766e'
  },
  {
    title: '最后滚动复盘',
    desc: '每月用结果修正路线，让报告成为动态工作区，而不是一次性 PDF。',
    icon: 'i-lucide-refresh-cw',
    accent: '#b45309'
  }
]

const todayActions = [
  { label: '上传一份最新简历', to: '/profile', icon: 'i-lucide-upload-cloud' },
  { label: '比较 3 个候选岗位', to: '/jobs', icon: 'i-lucide-columns-3' },
  { label: '生成一次匹配解释', to: '/match', icon: 'i-lucide-git-compare' },
  { label: '沉淀下月行动计划', to: '/report', icon: 'i-lucide-list-checks' }
]

const signals = [
  ['岗位信号', '活跃度 / 薪资 / 地点'],
  ['个人信号', '八维能力 / 项目证据'],
  ['路径信号', '晋升 / 转岗 / 学习资源']
]
</script>

<template>
  <section class="decision-board" aria-labelledby="decision-title">
    <div class="decision-copy">
      <p class="text-xs font-semibold uppercase text-primary">Planning Board</p>
      <h2 id="decision-title" class="mt-2 text-2xl font-bold">不是测一测就结束，而是把选择变成一张工作台</h2>
      <p class="mt-3 max-w-2xl text-sm leading-6 muted">
        PathFy 把“我适合什么”“现在差多少”“下一步做什么”放在同一个节奏里。你可以先从任意模块进入，系统会把证据继续传到后面的报告与复盘。
      </p>
    </div>

    <div class="board-grid">
      <div class="board-map">
        <div class="map-header">
          <span>职业决策链路</span>
          <UBadge color="neutral" variant="soft" label="可回溯" />
        </div>
        <div class="track-list">
          <article v-for="(track, index) in tracks" :key="track.title" class="track-item" :style="{ '--accent': track.accent }">
            <div class="track-index">{{ String(index + 1).padStart(2, '0') }}</div>
            <div class="track-icon">
              <UIcon :name="track.icon" class="size-5" />
            </div>
            <div>
              <h3>{{ track.title }}</h3>
              <p>{{ track.desc }}</p>
            </div>
          </article>
        </div>
      </div>

      <aside class="action-panel">
        <div>
          <p class="text-sm font-semibold">今天可以先做</p>
          <p class="mt-1 text-xs muted">不需要完整填完所有资料，先留下第一组可用证据。</p>
        </div>
        <div class="mt-4 grid gap-2">
          <UButton
            v-for="action in todayActions"
            :key="action.to"
            :to="action.to"
            :icon="action.icon"
            color="neutral"
            variant="soft"
            trailing-icon="i-lucide-arrow-right"
            block
          >
            {{ action.label }}
          </UButton>
        </div>
      </aside>
    </div>

    <div class="signal-strip">
      <div v-for="[label, value] in signals" :key="label" class="signal-item">
        <span>{{ label }}</span>
        <strong>{{ value }}</strong>
      </div>
    </div>
  </section>
</template>

<style scoped>
.decision-board {
  display: grid;
  gap: 1.25rem;
}

.decision-copy {
  max-width: 52rem;
}

.board-grid {
  display: grid;
  gap: 1rem;
}

.board-map {
  border: 1px solid var(--ui-border);
  border-radius: 0.9rem;
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--ui-primary) 8%, transparent), transparent 42%),
    var(--ui-bg);
  padding: 1rem;
}

.map-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  color: var(--ui-text-muted);
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
}

.track-list {
  position: relative;
  display: grid;
  gap: 0.75rem;
  margin-top: 1rem;
}

.track-list::before {
  content: "";
  position: absolute;
  top: 1.4rem;
  bottom: 1.4rem;
  left: 1.08rem;
  width: 1px;
  background: color-mix(in srgb, var(--ui-primary) 30%, var(--ui-border));
}

.track-item {
  --accent: var(--ui-primary);
  position: relative;
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr);
  gap: 0.8rem;
  align-items: start;
  border: 1px solid color-mix(in srgb, var(--accent) 24%, var(--ui-border));
  border-radius: 0.75rem;
  background: color-mix(in srgb, var(--accent) 5%, var(--ui-bg));
  padding: 1rem;
}

.track-index {
  position: relative;
  z-index: 1;
  display: grid;
  width: 2.15rem;
  height: 2.15rem;
  place-items: center;
  border-radius: 999px;
  background: var(--ui-bg);
  color: color-mix(in srgb, var(--accent) 72%, var(--ui-text));
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.75rem;
  font-weight: 800;
}

.track-icon {
  display: grid;
  width: 2.15rem;
  height: 2.15rem;
  place-items: center;
  border-radius: 0.6rem;
  background: color-mix(in srgb, var(--accent) 12%, var(--ui-bg-elevated));
  color: color-mix(in srgb, var(--accent) 72%, var(--ui-text));
}

.track-item h3 {
  font-weight: 700;
}

.track-item p {
  margin-top: 0.25rem;
  color: var(--ui-text-muted);
  font-size: 0.875rem;
  line-height: 1.6;
}

.action-panel {
  border: 1px solid var(--ui-border);
  border-radius: 0.9rem;
  background: var(--ui-bg-elevated);
  padding: 1rem;
}

.signal-strip {
  display: grid;
  gap: 0.75rem;
}

.signal-item {
  display: grid;
  gap: 0.25rem;
  border-left: 3px solid var(--ui-primary);
  background: color-mix(in srgb, var(--ui-primary) 5%, transparent);
  padding: 0.75rem 1rem;
}

.signal-item span {
  color: var(--ui-text-muted);
  font-size: 0.75rem;
}

.signal-item strong {
  font-size: 0.95rem;
}

@media (min-width: 768px) {
  .signal-strip {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (min-width: 1024px) {
  .board-grid {
    grid-template-columns: minmax(0, 1fr) minmax(18rem, 0.34fr);
  }
}
</style>
