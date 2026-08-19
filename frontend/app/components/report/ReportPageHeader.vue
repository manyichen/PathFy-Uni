<script setup lang="ts">
import type { ReportEnrichmentState } from '~/types/report'
defineProps<{ hasReport: boolean; reportId?: number; enrichState: ReportEnrichmentState | 'idle'; configCollapsed: boolean; enrichError?: string; exportState: 'idle' | 'preparing' | 'failed' }>()
const emit = defineEmits<{ toggleConfig: []; history: []; enrich: []; export: []; exportData: []; deleteReport: []; reset: [] }>()
</script>

<template>
  <CockpitPageHeader eyebrow="Career Plan / Reviewable" title="我的生涯计划" description="从岗位差距出发安排本月行动，用完成记录和真实证据持续修正方向。" icon="i-lucide-route" mark="05" edition-label="生涯档案">
    <template #actions>
      <div class="report-header-toolbar" aria-label="生涯报告操作">
        <div class="report-header-action-group">
          <UButton v-if="hasReport" class="report-header-action" size="md" color="neutral" variant="soft" :icon="configCollapsed ? 'i-lucide-panel-top-open' : 'i-lucide-panel-top-close'" @click="emit('toggleConfig')">{{ configCollapsed ? '展开配置' : '收起配置' }}</UButton>
          <UButton class="report-header-action" size="md" icon="i-lucide-history" color="neutral" variant="soft" @click="emit('history')">历史报告</UButton>
          <UButton v-if="reportId" class="report-header-action is-ai" size="md" :loading="enrichState === 'queued' || enrichState === 'running'" icon="i-lucide-wand-sparkles" color="primary" variant="soft" @click="emit('enrich')">{{ enrichState === 'queued' || enrichState === 'running' ? 'AI 增强中…' : enrichError ? '重试 AI 增强' : 'AI 增强' }}</UButton>
        </div>
        <i class="report-header-separator" aria-hidden="true" />
        <div class="report-header-action-group">
          <UButton v-if="reportId" class="report-header-action is-export" size="md" :loading="exportState === 'preparing'" icon="i-lucide-file-pen-line" @click="emit('export')">{{ exportState === 'failed' ? '重新编辑并导出' : exportState === 'preparing' ? '正在排版…' : '编辑并导出 PDF' }}</UButton>
          <UButton v-if="reportId" class="report-header-action" size="md" icon="i-lucide-database-backup" color="neutral" variant="outline" @click="emit('exportData')">导出我的数据</UButton>
        </div>
        <i v-if="reportId" class="report-header-separator" aria-hidden="true" />
        <div class="report-header-action-group">
          <UButton v-if="reportId" class="report-header-action" size="md" icon="i-lucide-shield-x" color="error" variant="soft" @click="emit('deleteReport')">永久删除报告</UButton>
          <UButton class="report-header-action" size="md" color="neutral" variant="outline" icon="i-lucide-trash-2" @click="emit('reset')">清空工作区</UButton>
        </div>
      </div>
    </template>
  </CockpitPageHeader>
</template>

<style scoped>
.report-header-toolbar { display:flex; width:100%; min-width:0; max-width:100%; flex-wrap:wrap; align-items:center; justify-content:flex-end; gap:.65rem; border:1px solid color-mix(in srgb,var(--pathfy-capability) 17%,var(--ui-border)); border-radius:1rem; background:color-mix(in srgb,var(--ui-bg-elevated) 82%,transparent); padding:.42rem; box-shadow:0 14px 34px -26px rgb(15 23 42/.65); backdrop-filter:blur(12px) }
.report-header-action-group { display:flex; min-width:0; flex-wrap:wrap; align-items:center; gap:.4rem }
.report-header-separator { width:1px; height:1.8rem; flex:0 0 auto; background:color-mix(in srgb,var(--pathfy-capability) 18%,var(--ui-border)) }
.report-header-action { min-height:2.5rem; border-radius:.72rem; transition:transform .16s ease,box-shadow .16s ease,filter .16s ease }
.report-header-action:hover { transform:translateY(-1px); box-shadow:0 10px 22px -17px rgb(15 23 42/.75); filter:saturate(1.08) }
.report-header-action.is-ai { box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--pathfy-capability) 16%,transparent) }
.report-header-action.is-export { box-shadow:0 8px 20px -15px color-mix(in srgb,var(--pathfy-capability) 65%,transparent) }
@media(max-width:1100px){.report-header-toolbar{justify-content:flex-start}.report-header-separator{display:none}}
@media(max-width:639px){.report-header-action-group{width:100%}.report-header-action{min-height:2.35rem}}
</style>
