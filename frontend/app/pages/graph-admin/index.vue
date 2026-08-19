<script setup lang="ts">
import { graphStatusLabels, taskLabel } from '~/types/graph'

definePageMeta({ middleware: 'admin' })
useSeoMeta({ title: '图谱 Dashboard' })

const graph = useGraphTasksApi()
const toast = useToast()
const loading = ref(true)
const stats = ref<Record<string, number>>({})
const guard = ref<any>()
const recent = ref<any[]>([])
const refreshedAt = ref<Date>()
const counts = ref({ queued: 0, running: 0, awaiting_confirmation: 0, failed: 0 })

const jobs = computed(() => Number(stats.value.jobs ?? stats.value.job_count ?? 0))
const qualityCoverage = computed(() => {
  if (!jobs.value) return 0
  return Math.max(0, Math.round((1 - Number(stats.value.capability_missing || 0) / jobs.value) * 100))
})
const workstyleCoverage = computed(() => Number(stats.value.workstyle_coverage_percent || 0))
const queueTotal = computed(() => Object.values(counts.value).reduce((sum, value) => sum + value, 0))

const queueItems = computed(() => [
  { key: 'queued', label: '排队中', value: counts.value.queued, icon: 'i-lucide-list-ordered', tone: 'text-blue-500', bg: 'bg-blue-500/10' },
  { key: 'running', label: '规划中', value: counts.value.running, icon: 'i-lucide-loader-circle', tone: 'text-primary', bg: 'bg-primary/10' },
  { key: 'awaiting_confirmation', label: '待确认', value: counts.value.awaiting_confirmation, icon: 'i-lucide-circle-alert', tone: 'text-amber-500', bg: 'bg-amber-500/10' },
  { key: 'failed', label: '失败', value: counts.value.failed, icon: 'i-lucide-circle-x', tone: 'text-red-500', bg: 'bg-red-500/10' }
])

const qualityItems = computed(() => [
  { label: '评分缺失', value: stats.value.capability_missing || 0, icon: 'i-lucide-circle-dashed', description: '尚未形成完整八维评分' },
  { label: '评分过期', value: stats.value.capability_stale || 0, icon: 'i-lucide-refresh-cw', description: '评估版本或输入指纹落后' },
  { label: '低置信度', value: stats.value.low_confidence || 0, icon: 'i-lucide-shield-alert', description: '任一维度置信度低于阈值' },
  { label: '薪资待规范', value: stats.value.salary_stale || 0, icon: 'i-lucide-badge-dollar-sign', description: '缺少当前版本的薪资解析' },
  { label: '环境证据缺失', value: stats.value.workstyle_missing || 0, icon: 'i-lucide-panels-top-left', description: '没有岗位或岗位族工作环境证据' },
  { label: '环境解释未就绪', value: Math.max(0, Number(stats.value.workstyle_evidenced || 0) - Number(stats.value.workstyle_ready || 0)), icon: 'i-lucide-shield-question', description: '已有证据但未达到至少两轴门槛' }
])

const inventory = computed(() => [
  { label: '岗位', value: stats.value.job_count || stats.value.jobs || 0, icon: 'i-lucide-briefcase-business' },
  { label: '岗位名称', value: stats.value.jobtitle_count || 0, icon: 'i-lucide-tags' },
  { label: '公司', value: stats.value.company_count || 0, icon: 'i-lucide-building-2' },
  { label: '技能', value: stats.value.skill_count || 0, icon: 'i-lucide-sparkles' },
  { label: '学习资源', value: stats.value.learningresource_count || 0, icon: 'i-lucide-book-open' },
  { label: '竞赛', value: stats.value.competition_count || 0, icon: 'i-lucide-trophy' }
])

const relationshipGroups = computed(() => [
  {
    label: '晋升路线', icon: 'i-lucide-trending-up',
    curated: stats.value.curated_promotions || 0, automatic: stats.value.auto_promotions || 0
  },
  {
    label: '横向换岗', icon: 'i-lucide-git-compare-arrows',
    curated: stats.value.curated_lateral || 0, automatic: stats.value.auto_lateral || 0
  }
])

const maintenanceItems = computed(() => [
  { label: '推断岗位', value: stats.value.inferred_jobs || 0, description: 'source = inferred', to: '/graph-admin/update' },
  { label: '低频岗位名称', value: stats.value.low_frequency_titles || 0, description: '关联真实岗位少于 2', to: '/graph-admin/update' }
])

function relationPercent(item: { curated: number, automatic: number }) {
  const total = Number(item.curated) + Number(item.automatic)
  return total ? Math.round(Number(item.curated) / total * 100) : 0
}

function statusColor(status: string) {
  if (status === 'succeeded') return 'success'
  if (status === 'failed' || status === 'partial_failed') return 'error'
  if (status === 'awaiting_confirmation') return 'warning'
  if (status === 'running' || status === 'applying') return 'info'
  return 'neutral'
}

function formatTime(value: string | undefined) {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
  }).format(date)
}

async function load() {
  loading.value = true
  try {
    const [statData, guardData, recentData, queued, running, waiting, failed] = await Promise.all([
      graph.stats(), graph.guard(), graph.tasks(), graph.tasks({ status: 'queued' }),
      graph.tasks({ status: 'running' }), graph.tasks({ status: 'awaiting_confirmation' }),
      graph.tasks({ status: 'failed' })
    ])
    stats.value = statData
    guard.value = guardData
    recent.value = recentData.items || []
    counts.value = { queued: queued.total, running: running.total, awaiting_confirmation: waiting.total, failed: failed.total }
    refreshedAt.value = new Date()
  } catch (error) {
    toast.add({ title: 'Dashboard 加载失败', description: String(error), color: 'error' })
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page-stack">
    <GraphAdminNav />
    <GraphGuardBanner :guard="guard" />

    <div class="flex flex-wrap items-end justify-between gap-4">
      <div class="page-heading">
        <h1 class="flex items-center gap-2"><UIcon name="i-lucide-layout-dashboard" class="text-primary" />图谱 Dashboard</h1>
        <p class="muted">集中查看图谱质量、更新队列与来源构成</p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <span v-if="refreshedAt" class="text-xs muted">更新于 {{ formatTime(refreshedAt.toISOString()) }}</span>
        <UButton color="neutral" variant="ghost" icon="i-lucide-refresh-cw" :loading="loading" @click="load">刷新</UButton>
        <UButton to="/graph-admin/update" icon="i-lucide-plus">创建更新任务</UButton>
      </div>
    </div>

    <div v-if="loading && !guard" class="grid gap-4 lg:grid-cols-3">
      <USkeleton class="h-48 lg:col-span-1" />
      <USkeleton class="h-48 lg:col-span-2" />
    </div>

    <div v-else class="grid gap-4 lg:grid-cols-3">
      <UCard class="overflow-hidden lg:col-span-1" :ui="{ body: 'h-full p-0 sm:p-0' }">
        <div class="flex h-full min-h-48 flex-col justify-between bg-gradient-to-br from-primary/20 via-primary/8 to-transparent p-6">
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="text-sm font-medium muted">当前图谱版本</p>
              <p class="mt-2 text-5xl font-bold tracking-tight">{{ guard?.graph_revision ?? '-' }}</p>
            </div>
            <div class="grid size-11 place-items-center rounded-xl bg-primary/15 text-primary">
              <UIcon name="i-lucide-git-commit-horizontal" class="size-6" />
            </div>
          </div>
          <div class="mt-8 flex items-center justify-between gap-3 border-t border-default pt-4">
            <div class="flex items-center gap-2 text-sm font-medium">
              <span class="size-2 rounded-full" :class="guard?.locked ? 'bg-amber-500' : 'bg-emerald-500'" />
              {{ guard?.locked ? '写入已锁定' : '写入通道正常' }}
            </div>
            <UButton v-if="guard?.locked_task_id" :to="`/graph-admin/tasks/${guard.locked_task_id}`" size="sm" color="warning" variant="soft">处理 #{{ guard.locked_task_id }}</UButton>
          </div>
        </div>
      </UCard>

      <UCard class="lg:col-span-2">
        <template #header>
          <div class="flex items-center justify-between gap-3">
            <div><h2 class="font-semibold">更新队列</h2><p class="mt-1 text-sm muted">当前共有 {{ queueTotal }} 个活跃或异常任务</p></div>
            <UButton to="/graph-admin/tasks" color="neutral" variant="ghost" trailing-icon="i-lucide-arrow-right">任务队列</UButton>
          </div>
        </template>
        <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
          <div v-for="item in queueItems" :key="item.key" class="rounded-xl border border-default p-4">
            <div class="flex items-center justify-between gap-2">
              <span class="grid size-9 place-items-center rounded-lg" :class="[item.bg, item.tone]"><UIcon :name="item.icon" class="size-5" /></span>
              <span class="text-2xl font-bold tabular-nums">{{ item.value }}</span>
            </div>
            <p class="mt-3 text-sm font-medium">{{ item.label }}</p>
          </div>
        </div>
      </UCard>
    </div>

    <div class="grid gap-4 xl:grid-cols-12">
      <UCard class="xl:col-span-7">
        <template #header>
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div><h2 class="font-semibold">岗位数据质量</h2><p class="mt-1 text-sm muted">{{ jobs.toLocaleString() }} 个岗位的评估与规范化状态</p></div>
            <div class="flex flex-wrap gap-2"><UBadge :label="`八维完整度 ${qualityCoverage}%`" :color="qualityCoverage >= 95 ? 'success' : qualityCoverage >= 80 ? 'warning' : 'error'" variant="soft" /><UBadge :label="`工作环境覆盖 ${workstyleCoverage}%`" :color="workstyleCoverage >= 80 ? 'success' : workstyleCoverage >= 40 ? 'warning' : 'error'" variant="soft" /></div>
          </div>
        </template>
        <div class="mb-5 h-2 overflow-hidden rounded-full bg-elevated">
          <div class="h-full rounded-full bg-primary transition-all" :style="{ width: `${qualityCoverage}%` }" />
        </div>
        <div class="grid gap-3 sm:grid-cols-2">
          <div v-for="item in qualityItems" :key="item.label" class="flex items-center gap-3 rounded-xl border border-default p-3.5">
            <span class="grid size-10 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary"><UIcon :name="item.icon" class="size-5" /></span>
            <div class="min-w-0 flex-1"><p class="font-medium">{{ item.label }}</p><p class="truncate text-xs muted">{{ item.description }}</p></div>
            <span class="text-xl font-bold tabular-nums" :class="item.value ? 'text-amber-500' : 'text-emerald-500'">{{ Number(item.value).toLocaleString() }}</span>
          </div>
        </div>
      </UCard>

      <UCard class="xl:col-span-5">
        <template #header><div><h2 class="font-semibold">图谱规模</h2><p class="mt-1 text-sm muted">核心业务节点数量</p></div></template>
        <div class="grid grid-cols-2 gap-x-5 gap-y-1">
          <div v-for="item in inventory" :key="item.label" class="flex items-center gap-3 border-b border-default py-3">
            <UIcon :name="item.icon" class="size-5 shrink-0 text-primary" />
            <span class="min-w-0 flex-1 text-sm muted">{{ item.label }}</span>
            <strong class="tabular-nums">{{ Number(item.value).toLocaleString() }}</strong>
          </div>
        </div>
      </UCard>

      <UCard class="xl:col-span-7">
        <template #header><div><h2 class="font-semibold">关系来源构成</h2><p class="mt-1 text-sm muted">策展数据优先，自动生成用于补齐空缺</p></div></template>
        <div class="grid gap-5 md:grid-cols-2">
          <div v-for="item in relationshipGroups" :key="item.label" class="rounded-xl border border-default p-4">
            <div class="flex items-center justify-between gap-3">
              <div class="flex items-center gap-2 font-medium"><UIcon :name="item.icon" class="size-5 text-primary" />{{ item.label }}</div>
              <strong>{{ Number(item.curated + item.automatic).toLocaleString() }}</strong>
            </div>
            <div class="mt-4 flex h-2 overflow-hidden rounded-full bg-elevated">
              <span class="bg-primary" :style="{ width: `${relationPercent(item)}%` }" />
              <span class="bg-primary/30" :style="{ width: `${100 - relationPercent(item)}%` }" />
            </div>
            <div class="mt-3 flex justify-between text-xs">
              <span><i class="mr-1 inline-block size-2 rounded-full bg-primary" />策展 {{ Number(item.curated).toLocaleString() }}</span>
              <span class="muted"><i class="mr-1 inline-block size-2 rounded-full bg-primary/30" />自动 {{ Number(item.automatic).toLocaleString() }}</span>
            </div>
          </div>
        </div>
      </UCard>

      <UCard class="xl:col-span-5">
        <template #header><div><h2 class="font-semibold">维护提示</h2><p class="mt-1 text-sm muted">建议通过任务队列集中处理</p></div></template>
        <div class="grid gap-3">
          <NuxtLink v-for="item in maintenanceItems" :key="item.label" :to="item.to" class="group flex items-center gap-4 rounded-xl border border-default p-4 transition hover:border-primary">
            <span class="text-2xl font-bold tabular-nums" :class="item.value ? 'text-amber-500' : 'text-emerald-500'">{{ Number(item.value).toLocaleString() }}</span>
            <span class="min-w-0 flex-1"><strong class="block text-sm">{{ item.label }}</strong><small class="muted">{{ item.description }}</small></span>
            <UIcon name="i-lucide-chevron-right" class="text-muted transition group-hover:translate-x-0.5 group-hover:text-primary" />
          </NuxtLink>
        </div>
      </UCard>
    </div>

    <UCard>
      <template #header>
        <div class="flex items-center justify-between gap-3">
          <div><h2 class="font-semibold">最近任务</h2><p class="mt-1 text-sm muted">最近创建的图谱更新与维护任务</p></div>
          <UButton to="/graph-admin/tasks" color="neutral" variant="ghost" trailing-icon="i-lucide-arrow-right">查看全部</UButton>
        </div>
      </template>
      <div v-if="recent.length" class="divide-y divide-default">
        <NuxtLink v-for="item in recent.slice(0, 6)" :key="item.id" :to="`/graph-admin/tasks/${item.id}`" class="group grid gap-2 py-3.5 transition first:pt-0 last:pb-0 hover:text-primary md:grid-cols-[auto_minmax(0,1fr)_auto_auto] md:items-center md:gap-4">
          <span class="text-sm font-semibold text-muted">#{{ item.id }}</span>
          <div class="min-w-0"><p class="truncate font-medium text-highlighted group-hover:text-primary">{{ taskLabel(item.task_type) }}</p><p class="truncate text-xs muted">{{ item.source_id || '无来源标识' }} · 申请人 #{{ item.requested_by }}</p></div>
          <UBadge :label="graphStatusLabels[item.status] || item.status" :color="statusColor(item.status) as any" variant="soft" />
          <time class="text-xs muted">{{ formatTime(item.created_at) }}</time>
        </NuxtLink>
      </div>
      <UEmpty v-else title="暂无图谱任务" description="创建第一个更新任务后，状态会显示在这里。"><template #actions><UButton to="/graph-admin/update" icon="i-lucide-plus">创建任务</UButton></template></UEmpty>
    </UCard>
  </div>
</template>
