<script setup lang="ts">
import { nextTick } from 'vue'

export type ReportWorkspaceTab = 'action' | 'evidence' | 'route' | 'review'
const props = defineProps<{ modelValue: ReportWorkspaceTab; evidenceCount?: number; reviewCount?: number }>()
const emit = defineEmits<{ 'update:modelValue': [value: ReportWorkspaceTab] }>()
const items: Array<{ key: ReportWorkspaceTab; label: string; description: string; icon: string }> = [
  { key: 'action', label: '行动', description: '现在做什么', icon: 'i-lucide-list-checks' },
  { key: 'evidence', label: '依据', description: '为什么这样判断', icon: 'i-lucide-shield-check' },
  { key: 'route', label: '路线', description: '3/6/12 月怎么走', icon: 'i-lucide-route' },
  { key: 'review', label: '复盘', description: '结果如何校准', icon: 'i-lucide-refresh-cw' }
]
function count(key: ReportWorkspaceTab) {
  if (key === 'evidence') return props.evidenceCount || 0
  if (key === 'review') return props.reviewCount || 0
  return 0
}
function move(event: KeyboardEvent, index: number) {
  const direction = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
  if (!direction) return
  event.preventDefault()
  const next = (index + direction + items.length) % items.length
  const item = items[next]
  if (!item) return
  emit('update:modelValue', item.key)
  nextTick(() => (event.currentTarget as HTMLElement)?.parentElement?.querySelectorAll<HTMLElement>('[role="tab"]')[next]?.focus())
}
</script>

<template>
  <nav class="workspace-tabs" role="tablist" aria-label="生涯报告工作区">
    <button
      v-for="(item, index) in items"
      :id="`report-tab-${item.key}`"
      :key="item.key"
      type="button"
      role="tab"
      :aria-selected="modelValue === item.key"
      :aria-controls="`report-panel-${item.key}`"
      :tabindex="modelValue === item.key ? 0 : -1"
      :class="{ active: modelValue === item.key }"
      @click="emit('update:modelValue', item.key)"
      @keydown="move($event, index)"
    >
      <UIcon :name="item.icon" class="size-4" />
      <span><strong>{{ item.label }}</strong><small>{{ item.description }}</small></span>
      <UBadge v-if="count(item.key)" :label="String(count(item.key))" size="sm" color="neutral" variant="soft" />
    </button>
  </nav>
</template>

<style scoped>
.workspace-tabs{position:sticky;top:.6rem;z-index:12;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.45rem;border:1px solid var(--ui-border);border-radius:1rem;background:color-mix(in srgb,var(--ui-bg) 94%,transparent);padding:.4rem;box-shadow:0 .5rem 1.5rem color-mix(in srgb,#000 8%,transparent);backdrop-filter:blur(14px)}
.workspace-tabs button{display:flex;min-width:0;align-items:center;justify-content:center;gap:.5rem;border-radius:.7rem;padding:.65rem;color:var(--ui-text-muted);text-align:left;transition:160ms}.workspace-tabs button:hover,.workspace-tabs button.active{background:color-mix(in srgb,var(--ui-primary) 10%,var(--ui-bg));color:var(--ui-primary)}
.workspace-tabs span{min-width:0}.workspace-tabs strong,.workspace-tabs small{display:block}.workspace-tabs strong{font-size:.84rem}.workspace-tabs small{margin-top:.1rem;overflow:hidden;font-size:.65rem;text-overflow:ellipsis;white-space:nowrap}
@media(max-width:640px){.workspace-tabs{top:.25rem;gap:.2rem;padding:.25rem}.workspace-tabs button{display:grid;gap:.2rem;justify-items:center;padding:.5rem .2rem;text-align:center}.workspace-tabs small{display:none}}
</style>
