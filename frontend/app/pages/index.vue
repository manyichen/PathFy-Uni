<script setup lang="ts">
useSeoMeta({ title: '首页' })
const features = [
  ['能力画像', '整合简历、证书和项目材料，形成八维能力画像', '/profile', 'i-lucide-chart-radar'],
  ['岗位探索', '浏览岗位要求、晋升路径与横向转岗机会', '/jobs', 'i-lucide-briefcase-business'],
  ['人岗匹配', '结合能力画像进行岗位粗排和 AI 精排', '/match', 'i-lucide-git-compare'],
  ['生涯报告', '生成目标明确、可复盘的职业成长计划', '/report', 'i-lucide-file-chart-column']
]
</script>
<template>
  <div class="page-stack">
    <section class="py-14 text-center sm:py-20">
      <UBadge label="大学生职业规划智能体" variant="soft" />
      <h1 class="mx-auto mt-5 max-w-4xl text-4xl font-bold tracking-tight sm:text-6xl">从能力画像到职业行动计划</h1>
      <p class="mx-auto mt-5 max-w-2xl text-lg muted">用结构化数据、岗位知识图谱和 AI 分析，帮助你探索方向、衡量差距并持续复盘。</p>
      <div class="mt-8 flex justify-center gap-3"><UButton to="/profile" size="xl">开始画像</UButton><UButton to="/jobs" size="xl" color="neutral" variant="outline">探索岗位</UButton></div>
    </section>
    <div class="grid gap-4 md:grid-cols-2">
      <UCard v-for="item in features" :key="item[0]">
        <UIcon :name="item[3]" class="size-7 text-primary" />
        <h2 class="mt-4 text-xl font-semibold">{{ item[0] }}</h2><p class="mt-2 muted">{{ item[1] }}</p>
        <UButton :to="item[2]" variant="link" class="mt-3 px-0">进入功能</UButton>
      </UCard>
    </div>
  </div>
</template>
