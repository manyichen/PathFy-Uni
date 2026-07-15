<script setup lang="ts">
type ModuleItem = {
  to: string
  title: string
  verb: string
  desc: string
  icon: string
  evidence: string[]
  output: string
  tone: string
}

const modules: ModuleItem[] = [
  {
    to: '/jobs',
    title: '岗位探索',
    verb: '看市场',
    desc: '从行业、城市、薪资和能力标签里找到真实存在的机会。',
    icon: 'i-lucide-briefcase-business',
    evidence: ['岗位样本', '薪资区间', '能力关键词'],
    output: '候选方向清单',
    tone: '#0891b2'
  },
  {
    to: '/profile',
    title: '能力画像',
    verb: '看自己',
    desc: '把简历、经历和技能拆成八维能力，减少纯主观判断。',
    icon: 'i-lucide-radar',
    evidence: ['简历材料', '八维评分', '能力证据'],
    output: '个人能力底图',
    tone: '#0f766e'
  },
  {
    to: '/match',
    title: '人岗匹配',
    verb: '看差距',
    desc: '比较岗位要求与个人画像，定位最该补齐的维度。',
    icon: 'i-lucide-git-compare',
    evidence: ['匹配分', '维度差距', '解释文本'],
    output: '优先提升项',
    tone: '#2563eb'
  },
  {
    to: '/graph',
    title: '职业图谱',
    verb: '看路径',
    desc: '查看晋升链、转岗路径和能力迁移关系。',
    icon: 'i-lucide-network',
    evidence: ['岗位节点', '路径关系', '资源密度'],
    output: '发展路线判断',
    tone: '#7c3aed'
  },
  {
    to: '/report',
    title: '生涯报告',
    verb: '做计划',
    desc: '把目标岗位拆成短中期行动，并支持导出和复盘。',
    icon: 'i-lucide-file-text',
    evidence: ['目标岗位', '行动计划', '复盘记录'],
    output: '动态报告画布',
    tone: '#b45309'
  },
  {
    to: '/personality',
    title: '性格测试',
    verb: '补偏好',
    desc: '理解沟通方式、偏好环境和职业适配性。',
    icon: 'i-lucide-brain',
    evidence: ['问卷回答', '类型结果', '偏好解释'],
    output: '职业偏好补充',
    tone: '#db2777'
  }
]

const activeIndex = ref(0)
const activeModule = computed(() => modules[activeIndex.value] ?? modules[0]!)

function toneStyle(item: ModuleItem) {
  return { '--tone': item.tone } as Record<string, string>
}
</script>

<template>
  <section class="module-router" aria-labelledby="feature-title">
    <div class="module-heading">
      <div>
        <p class="text-xs font-semibold uppercase text-primary">Start Here</p>
        <h2 id="feature-title" class="mt-2 text-2xl font-bold">选择一个入口，直接开始规划</h2>
        <p class="mt-2 max-w-2xl text-sm leading-6 muted">
          入口不再是割裂的页面：每一次浏览、上传、匹配或复盘，都会成为下一步报告判断的证据。
        </p>
      </div>
      <UButton to="/profile" color="neutral" variant="outline" trailing-icon="i-lucide-arrow-right">先试能力画像</UButton>
    </div>

    <div class="module-shell" :style="toneStyle(activeModule)">
      <div class="module-tabs" role="tablist" aria-label="规划模块">
        <button
          v-for="(item, index) in modules"
          :key="item.to"
          type="button"
          class="module-tab"
          :class="{ active: index === activeIndex }"
          role="tab"
          :aria-selected="index === activeIndex"
          @click="activeIndex = index"
        >
          <UIcon :name="item.icon" class="size-4" />
          <span>{{ item.verb }}</span>
        </button>
      </div>

      <div class="module-preview">
        <div class="module-stage">
          <div class="stage-icon">
            <UIcon :name="activeModule.icon" class="size-7" />
          </div>
          <div>
            <p class="text-sm font-semibold" style="color: var(--tone)">{{ activeModule.verb }}</p>
            <h3 class="mt-1 text-2xl font-bold">{{ activeModule.title }}</h3>
            <p class="mt-3 max-w-xl text-sm leading-6 muted">{{ activeModule.desc }}</p>
          </div>
          <UButton :to="activeModule.to" color="primary" trailing-icon="i-lucide-arrow-right">
            进入{{ activeModule.title }}
          </UButton>
        </div>

        <div class="evidence-lane" aria-label="证据流">
          <div v-for="item in activeModule.evidence" :key="item" class="evidence-node">
            <UIcon name="i-lucide-dot" class="size-5" />
            <span>{{ item }}</span>
          </div>
          <div class="evidence-output">
            <span>输出</span>
            <strong>{{ activeModule.output }}</strong>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.module-router {
  display: grid;
  gap: 1.25rem;
}

.module-heading {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  justify-content: space-between;
  gap: 1rem;
}

.module-shell {
  --tone: var(--ui-primary);
  display: grid;
  gap: 1rem;
  border: 1px solid color-mix(in srgb, var(--tone) 24%, var(--ui-border));
  border-radius: 1rem;
  background:
    radial-gradient(circle at top left, color-mix(in srgb, var(--tone) 14%, transparent), transparent 34%),
    var(--ui-bg);
  padding: 0.8rem;
}

.module-tabs {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.5rem;
}

.module-tab {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  min-height: 2.6rem;
  border: 1px solid var(--ui-border);
  border-radius: 0.7rem;
  background: color-mix(in srgb, var(--ui-bg) 88%, transparent);
  color: var(--ui-text-muted);
  font-size: 0.875rem;
  font-weight: 700;
  transition: border-color 160ms ease, background 160ms ease, color 160ms ease, transform 160ms ease;
}

.module-tab:hover,
.module-tab.active {
  border-color: color-mix(in srgb, var(--tone) 48%, var(--ui-border));
  background: color-mix(in srgb, var(--tone) 10%, var(--ui-bg));
  color: var(--ui-text);
}

.module-tab:active {
  transform: translateY(1px);
}

.module-preview {
  display: grid;
  gap: 1rem;
}

.module-stage {
  display: grid;
  gap: 1rem;
  align-items: center;
  border-radius: 0.85rem;
  background: color-mix(in srgb, var(--ui-bg-elevated) 82%, transparent);
  padding: 1rem;
}

.stage-icon {
  display: grid;
  width: 3.4rem;
  height: 3.4rem;
  place-items: center;
  border-radius: 0.8rem;
  background: color-mix(in srgb, var(--tone) 14%, var(--ui-bg));
  color: color-mix(in srgb, var(--tone) 75%, var(--ui-text));
}

.evidence-lane {
  display: grid;
  gap: 0.65rem;
}

.evidence-node,
.evidence-output {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  border-left: 3px solid color-mix(in srgb, var(--tone) 45%, var(--ui-border));
  background: color-mix(in srgb, var(--tone) 6%, transparent);
  padding: 0.75rem;
}

.evidence-node {
  color: var(--ui-text-muted);
  font-size: 0.875rem;
}

.evidence-output {
  align-items: start;
  flex-direction: column;
  border-left-color: var(--tone);
}

.evidence-output span {
  color: var(--ui-text-muted);
  font-size: 0.75rem;
}

.evidence-output strong {
  color: color-mix(in srgb, var(--tone) 72%, var(--ui-text));
}

@media (min-width: 768px) {
  .module-tabs {
    grid-template-columns: repeat(6, minmax(0, 1fr));
  }

  .module-stage {
    grid-template-columns: auto minmax(0, 1fr) auto;
  }

  .evidence-lane {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
</style>
