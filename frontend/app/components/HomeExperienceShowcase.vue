<script setup lang="ts">
const reportSections = [
  { label: '目标', value: '数据分析师 / 产品运营 / AI 应用助理', icon: 'i-lucide-target' },
  { label: '差距', value: '实践 +18、数字 +12、协作 +9', icon: 'i-lucide-chart-no-axes-column-increasing' },
  { label: '下月', value: '完成 1 个可展示项目，补 2 个 SQL 场景', icon: 'i-lucide-calendar-check' }
]

const timeline = [
  { month: '0 月', label: '导入匹配目标', done: true },
  { month: '1 月', label: '补齐基础证据', done: false },
  { month: '3 月', label: '形成作品集', done: false },
  { month: '6 月', label: '投递与复盘', done: false }
]

const actions = [
  '候选岗位可回看近期公开信息',
  'AI 增强摘要可单独触发',
  '复盘后自动更新发展线'
]
</script>

<template>
  <section class="report-preview" aria-labelledby="preview-title">
    <div class="preview-copy">
      <p class="text-xs font-semibold uppercase text-primary">Career Report</p>
      <h2 id="preview-title" class="mt-2 text-2xl font-bold">最后产出的不是“建议”，而是一份能继续工作的报告</h2>
      <p class="mt-3 max-w-2xl text-sm leading-6 muted">
        报告会保留目标来源、能力差距、公开信息、行动计划和月度复盘。它更像一张职业规划画布，而不是下载后就封存的文档。
      </p>
    </div>

    <div class="preview-shell">
      <div class="report-paper">
        <div class="paper-header">
          <div>
            <span class="text-xs text-primary">Report Canvas</span>
            <h3>生涯发展报告预览</h3>
          </div>
          <UBadge color="primary" variant="soft" label="动态复盘" />
        </div>

        <div class="section-stack">
          <article v-for="item in reportSections" :key="item.label" class="report-row">
            <div class="row-icon">
              <UIcon :name="item.icon" class="size-5" />
            </div>
            <div>
              <p>{{ item.label }}</p>
              <strong>{{ item.value }}</strong>
            </div>
          </article>
        </div>

        <div class="timeline">
          <div v-for="point in timeline" :key="point.month" class="timeline-point" :class="{ done: point.done }">
            <span>{{ point.month }}</span>
            <strong>{{ point.label }}</strong>
          </div>
        </div>
      </div>

      <aside class="preview-side">
        <div>
          <p class="text-sm font-semibold">报告模块已补回的关键动作</p>
          <p class="mt-1 text-xs muted">候选、公开信息、AI 增强和复盘会回到同一张页面里。</p>
        </div>
        <ul class="mt-4 grid gap-2">
          <li v-for="action in actions" :key="action">
            <UIcon name="i-lucide-check" class="size-4 text-primary" />
            <span>{{ action }}</span>
          </li>
        </ul>
        <UButton to="/report" class="mt-5" block trailing-icon="i-lucide-arrow-right">打开生涯报告</UButton>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.report-preview {
  display: grid;
  gap: 1.25rem;
}

.preview-copy {
  max-width: 52rem;
}

.preview-shell {
  display: grid;
  gap: 1rem;
  align-items: stretch;
}

.report-paper {
  border: 1px solid var(--ui-border);
  border-radius: 1rem;
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--ui-primary) 7%, transparent), transparent 36%),
    var(--ui-bg);
  padding: 1rem;
  box-shadow: 0 24px 55px -42px rgb(15 23 42 / 0.55);
}

.paper-header {
  display: flex;
  flex-wrap: wrap;
  align-items: start;
  justify-content: space-between;
  gap: 1rem;
  border-bottom: 1px solid var(--ui-border);
  padding-bottom: 1rem;
}

.paper-header h3 {
  margin-top: 0.2rem;
  font-size: 1.25rem;
  font-weight: 800;
}

.section-stack {
  display: grid;
  gap: 0.75rem;
  margin-top: 1rem;
}

.report-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 0.75rem;
  align-items: center;
  border: 1px solid var(--ui-border);
  border-radius: 0.75rem;
  background: color-mix(in srgb, var(--ui-bg-elevated) 68%, transparent);
  padding: 0.9rem;
}

.row-icon {
  display: grid;
  width: 2.4rem;
  height: 2.4rem;
  place-items: center;
  border-radius: 0.65rem;
  background: color-mix(in srgb, var(--ui-primary) 12%, var(--ui-bg));
  color: var(--ui-primary);
}

.report-row p {
  color: var(--ui-text-muted);
  font-size: 0.75rem;
}

.report-row strong {
  display: block;
  margin-top: 0.2rem;
  font-size: 0.95rem;
}

.timeline {
  display: grid;
  gap: 0.75rem;
  margin-top: 1rem;
}

.timeline-point {
  position: relative;
  border-left: 3px solid var(--ui-border);
  padding: 0.2rem 0 0.2rem 0.8rem;
}

.timeline-point.done {
  border-left-color: var(--ui-primary);
}

.timeline-point span {
  color: var(--ui-text-muted);
  font-size: 0.75rem;
}

.timeline-point strong {
  display: block;
  margin-top: 0.15rem;
  font-size: 0.9rem;
}

.preview-side {
  border: 1px solid color-mix(in srgb, var(--ui-primary) 20%, var(--ui-border));
  border-radius: 1rem;
  background: color-mix(in srgb, var(--ui-primary) 6%, var(--ui-bg));
  padding: 1rem;
}

.preview-side li {
  display: flex;
  gap: 0.5rem;
  color: var(--ui-text-muted);
  font-size: 0.875rem;
  line-height: 1.5;
}

@media (min-width: 768px) {
  .timeline {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

@media (min-width: 1024px) {
  .preview-shell {
    grid-template-columns: minmax(0, 1fr) minmax(18rem, 0.34fr);
  }
}
</style>
