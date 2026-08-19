<script setup lang="ts">
import { useMatchWorkspace } from '~/composables/match/useMatchWorkspace'

definePageMeta({ middleware: 'auth' })
useSeoMeta({ title: '人岗匹配' })

const workspace = useMatchWorkspace()
</script>

<template>
  <div class="cockpit-page">
    <CockpitPageHeader eyebrow="Matching Workspace / Fit" title="人岗匹配" description="从八维能力画像出发，区分智能精排与完整粗排，并明确展示每个排名的依据。" icon="i-lucide-target" mark="03" edition-label="匹配工作台" />
    <CockpitStageRail current="match" />

    <section><CockpitSectionHeading kicker="01 · Primary View" title="设置本次匹配意图" description="选择画像、关键词、地点与策略后开始比较。" />
    <MatchIntentPanel
      v-model:resume-id="workspace.resumeId.value"
      v-model:q="workspace.q.value"
      v-model:location-q="workspace.locationQ.value"
      v-model:goal="workspace.goal.value"
      v-model:refine="workspace.refine.value"
      v-model:preference-mode="workspace.preferenceMode.value"
      :resumes="workspace.resumes.value"
      :personality="workspace.personalityProfile.value"
      :preference-context="workspace.result.value?.preference_context"
      :loading="workspace.loading.value"
      @run="workspace.run"
      @history="workspace.openHistory"
    />
    </section>

    <UAlert
      v-if="workspace.runError.value"
      role="alert"
      color="error"
      variant="soft"
      icon="i-lucide-circle-alert"
      title="匹配未完成"
      :description="workspace.runError.value"
    >
      <template #actions>
        <UButton
          size="sm"
          color="error"
          variant="outline"
          icon="i-lucide-rotate-ccw"
          :loading="workspace.loading.value"
          @click="workspace.run"
        >重新匹配</UButton>
      </template>
    </UAlert>

    <div v-if="workspace.loading.value" class="grid gap-4"><USkeleton class="h-48" /><USkeleton class="h-48" /></div>
    <template v-else-if="workspace.result.value">
      <MatchSnapshotStatus :warning="workspace.result.value.snapshot_warning" :restored-message="workspace.restoredMessage.value" />
      <MatchPreferenceStatus :context="workspace.result.value.preference_context" />
      <CockpitSectionHeading kicker="02 · Supporting Evidence" title="排名结果与比较依据" description="智能精排解释发展适配，完整粗排保留八维能力差距，两种结果不会混为一谈。" />
      <div v-if="workspace.jobs.value.length" class="match-results-layout grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <MatchResultList :jobs="workspace.jobs.value" :llm="workspace.result.value.llm" :preference-context="workspace.result.value.preference_context" :refine-requested="workspace.refine.value" :refining="workspace.refineLoading.value" @select="workspace.select" @detail="workspace.openDetail" @retry-refine="workspace.retryRefine" />
        <aside class="match-comparison-float" aria-label="固定八维能力对比浮窗"><MatchComparisonPanel :student-scores="workspace.studentScores.value" :job="workspace.selectedJob.value" @detail="workspace.openDetail" /></aside>
      </div>
      <UEmpty v-else title="没有找到匹配岗位" description="尝试减少关键词或放宽地点条件" icon="i-lucide-search-x" />
    </template>
    <UEmpty v-else title="尚未生成匹配结果" description="选择能力画像后开始匹配" icon="i-lucide-target" />

    <MatchHistoryModal v-model:open="workspace.historyOpen.value" :items="workspace.history.value" :loading="workspace.historyLoading.value" @restore="workspace.restore" />
    <JobDetailModal :job-id="workspace.detailJobId.value" @close="workspace.detailJobId.value = null" />
  </div>
</template>

<style scoped>
.match-comparison-float{position:sticky;top:4.75rem;z-index:10;align-self:start;max-height:calc(100vh - 5.5rem);overflow-y:auto;overscroll-behavior:contain;scrollbar-gutter:stable;border-radius:.75rem}
@media(max-width:1279px){.match-comparison-float{position:static;max-height:none;overflow:visible}}
</style>
