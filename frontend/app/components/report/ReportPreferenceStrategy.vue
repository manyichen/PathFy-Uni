<script setup lang="ts">
import type { ReportPreferenceStrategy, ReportPreferenceStrategySection } from '~/types/report'
import { useReportApi } from '~/composables/api/useReportApi'
import { copyPreferenceSections } from '~/utils/report-preference'

const props = defineProps<{ reportId: number; strategy?: ReportPreferenceStrategy }>()
const emit = defineEmits<{ changed: [] }>()
const api = useReportApi()
const toast = useToast()
const editing = ref(false)
const saving = ref(false)
const sections = ref<ReportPreferenceStrategySection[]>([])

function resetSections() {
  sections.value = copyPreferenceSections(props.strategy?.sections)
}

function cancelEditing() {
  resetSections()
  editing.value = false
}

watch(() => props.strategy?.sections, resetSections, { immediate: true, deep: true })

async function decide(decision: 'accept' | 'edit' | 'use_alternative') {
  saving.value = true
  try {
    await api.decidePreferenceStrategy(props.reportId, { decision, sections: copyPreferenceSections(sections.value) })
    editing.value = false
    emit('changed')
    toast.add({ title: decision === 'accept' ? '执行方式建议已接受' : decision === 'edit' ? '自定义执行方式已保存' : '已切换为备选执行方式', color: 'success' })
  } catch (error) {
    toast.add({ title: error instanceof Error ? error.message : '保存失败', color: 'error' })
  } finally { saving.value = false }
}
</script>

<template>
  <section v-if="strategy && strategy.status !== 'missing'" class="strategy-card">
    <header><div><span>PERSONALITY / EXECUTION</span><h2>按你更自然的方式，把同一目标做出来</h2><p>{{ strategy.mbti_type || '当前偏好画像' }} · {{ strategy.disclaimer }}</p></div><UBadge :label="strategy.status === 'accepted' ? '已接受' : strategy.status === 'edited' ? '已编辑' : '待确认'" :color="strategy.status === 'suggested' ? 'warning' : 'success'" variant="soft" /></header>
    <div class="strategy-grid">
      <article v-for="section in sections" :key="section.code">
        <small>{{ section.title }}</small>
        <UTextarea v-if="editing" v-model="section.recommendation" :rows="3" autoresize :maxrows="6" />
        <strong v-else>{{ section.recommendation }}</strong>
        <p>{{ section.rationale }}</p>
        <details><summary>查看备选方式</summary><UTextarea v-if="editing" v-model="section.alternative" class="mt-2" :rows="2" /><span v-else>{{ section.alternative }}</span></details>
      </article>
    </div>
    <UAlert v-if="strategy.calibration" class="mt-4" :color="strategy.calibration.status === 'review_recommended' ? 'warning' : 'neutral'" variant="soft" :title="strategy.calibration.status === 'review_recommended' ? '偏好校准提示' : `复盘校准 ${strategy.calibration.completed_cycles}/${strategy.calibration.required_cycles}`" :description="strategy.calibration.message" />
    <footer><UButton v-if="!editing" color="neutral" variant="soft" icon="i-lucide-pencil" @click="() => { editing = true }">编辑</UButton><UButton v-if="!editing" color="neutral" variant="ghost" @click="decide('use_alternative')">使用备选方式</UButton><UButton v-if="editing" color="neutral" variant="soft" @click="cancelEditing">取消</UButton><UButton :loading="saving" @click="decide(editing ? 'edit' : 'accept')">{{ editing ? '保存编辑' : '接受建议' }}</UButton></footer>
  </section>
</template>

<style scoped>
.strategy-card{display:grid;gap:1rem;border:1px solid color-mix(in srgb,var(--ui-primary) 24%,var(--ui-border));border-radius:1.25rem;background:linear-gradient(135deg,color-mix(in srgb,var(--ui-primary) 7%,var(--ui-bg)),var(--ui-bg));padding:clamp(1rem,2.5vw,1.6rem)}
header{display:flex;align-items:flex-start;justify-content:space-between;gap:1rem}header span{color:var(--ui-primary);font:700 .65rem/1.3 ui-monospace,monospace;letter-spacing:.12em}header h2{margin-top:.35rem;font-size:1.2rem;font-weight:750}header p{margin-top:.35rem;color:var(--ui-text-muted);font-size:.78rem}.strategy-grid{display:grid;gap:.8rem}.strategy-grid article{border-left:3px solid color-mix(in srgb,var(--ui-primary) 58%,transparent);background:color-mix(in srgb,var(--ui-bg) 86%,transparent);padding:.9rem 1rem}.strategy-grid small{display:block;color:var(--ui-primary);font-weight:700}.strategy-grid strong{display:block;margin-top:.3rem;line-height:1.7}.strategy-grid p,.strategy-grid details{margin-top:.35rem;color:var(--ui-text-muted);font-size:.75rem;line-height:1.6}.strategy-grid summary{cursor:pointer;font-weight:650}footer{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:.5rem}@media(min-width:900px){.strategy-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
