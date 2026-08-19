<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import type { ReportDecisionAction, ReportPlan, ReportPlanAction, ReportTargetDecision } from '~/types/api'
import { useReportApi } from '~/composables/api/useReportApi'

const props = defineProps<{ reportId: number; plan?: ReportPlan; decision?: ReportTargetDecision }>()
const emit = defineEmits<{ changed: [reload: boolean] }>()
const reportApi = useReportApi()
const saving = ref('')
const pendingActionIds = reactive(new Set<string>())
let actionSaveQueue: Promise<void> = Promise.resolve()
const actionError = ref('')
const editorOpen = ref(false)
const editorMode = ref<'create' | 'edit'>('create')
const editingUid = ref('')
const form = reactive({ item_index: 0, text: '', kind: 'practice', deliverable: '', deadline: '本月内', effort_hours: 2, acceptance_rule: '' })

const modeLabel = computed(() => ({ initial: '起步计划', continue: '保持节奏', light: '重点调整', strong: '强化补齐' }[props.plan?.next_month_plan?.replan_mode || ''] || '当前执行'))
const kindLabel = (kind?: string) => ({ learning: '学习', learn: '学习', practice: '实践', project: '成果', evidence: '证据', deliverable: '成果' }[kind || ''] || '行动')
const groups = computed(() => props.plan?.next_month_plan?.items || [])
const decisionByPosition = computed(() => new Map((props.decision?.actions || []).map(action => [`${action.item_index}:${action.action_index}`, action])))

type ActionView = ReportDecisionAction & { source: ReportPlanAction }
const actions = computed<ActionView[]>(() => {
  const out: ActionView[] = []
  for (const [itemIndex, item] of groups.value.entries()) {
    for (const [actionIndex, source] of (item.custom_actions || []).entries()) {
      if (!source.text) continue
      const decision = decisionByPosition.value.get(`${itemIndex}:${actionIndex}`)
      out.push({
        id: String(source.action_uid || decision?.id || `legacy:${itemIndex}:${actionIndex}`),
        job_id: props.plan?.job_id || '', item_index: itemIndex, action_index: actionIndex,
        title: source.text, kind: (source.kind === 'learn' ? 'learn' : source.kind === 'deliverable' ? 'deliverable' : 'practice'),
        focus_dimension: item.focus_dimension, focus_label: item.focus_label,
        deliverable: String(source.deliverable || decision?.deliverable || item.milestone || source.text),
        deadline: String(source.deadline || decision?.deadline || '本月内'), effort_hours: Number(source.effort_hours || decision?.effort_hours || 2),
        acceptance_criteria: [String(source.acceptance_rule || decision?.acceptance_criteria?.[0] || `完成行动：${source.text}`)],
        evidence_required: true, evidence_grade_required: decision?.evidence_grade_required || 'B', evidence_type: decision?.evidence_type || 'other',
        status: source.done ? 'done' : 'todo', done: Boolean(source.done), done_at: source.done_at,
        source_claim_ids: decision?.source_claim_ids || [], source_fact_refs: decision?.source_fact_refs || [], resource_refs: decision?.resource_refs || [], source
      })
    }
  }
  return out
})
const totalHours = computed(() => actions.value.reduce((sum, action) => sum + Number(action.effort_hours || 0), 0))
const doneCount = computed(() => actions.value.filter(action => action.done).length)
const evidenceCount = computed(() => actions.value.filter(action => action.evidence_required).length)
const kindCount = computed(() => new Set(actions.value.map(action => action.kind)).size)
const nextAction = computed(() => actions.value.find(action => !action.done))

async function toggle(action: ActionView, nextValue: boolean) {
  if (!props.plan || pendingActionIds.has(action.id)) return
  const previous = Boolean(action.source.done)
  const previousAt = action.source.done_at
  action.source.done = nextValue
  action.source.done_at = nextValue ? new Date().toISOString() : undefined
  pendingActionIds.add(action.id)
  actionError.value = ''
  try {
    const request = () => reportApi.setPlanActionDone(props.reportId, { job_id: props.plan!.job_id, action_uid: action.id, item_index: action.item_index, action_index: action.action_index, done: nextValue })
    const currentSave = actionSaveQueue.then(request, request)
    actionSaveQueue = currentSave.then(() => undefined, () => undefined)
    await currentSave
    emit('changed', false)
  } catch (error) {
    action.source.done = previous
    action.source.done_at = previousAt
    actionError.value = error instanceof Error ? error.message : '行动状态保存失败，请稍后重试'
  } finally { pendingActionIds.delete(action.id) }
}

function openCreate() {
  editorMode.value = 'create'; editingUid.value = ''
  Object.assign(form, { item_index: 0, text: '', kind: 'practice', deliverable: '', deadline: '本月内', effort_hours: 2, acceptance_rule: '' })
  editorOpen.value = true
}

function openEdit(action: ActionView) {
  editorMode.value = 'edit'; editingUid.value = action.id
  Object.assign(form, { item_index: action.item_index, text: action.title, kind: action.kind, deliverable: action.deliverable, deadline: action.deadline, effort_hours: action.effort_hours, acceptance_rule: action.acceptance_criteria[0] || '' })
  editorOpen.value = true
}

async function saveEditor() {
  if (!props.plan || !form.text.trim() || saving.value) return
  saving.value = editorMode.value
  actionError.value = ''
  const payload = { job_id: props.plan.job_id, item_index: form.item_index, text: form.text.trim(), kind: form.kind, deliverable: form.deliverable.trim(), deadline: form.deadline.trim(), effort_hours: Number(form.effort_hours), acceptance_rule: form.acceptance_rule.trim() }
  try {
    if (editorMode.value === 'create') await reportApi.createPlanAction(props.reportId, payload)
    else await reportApi.updatePlanAction(props.reportId, editingUid.value, payload)
    editorOpen.value = false
    emit('changed', true)
  } catch (error) { actionError.value = error instanceof Error ? error.message : '行动保存失败' }
  finally { saving.value = '' }
}

async function remove(action: ActionView) {
  if (!props.plan || saving.value || !window.confirm(`确认删除“${action.title}”？`)) return
  saving.value = action.id
  actionError.value = ''
  try {
    await reportApi.deletePlanAction(props.reportId, action.id, props.plan.job_id)
    emit('changed', true)
  } catch (error) { actionError.value = error instanceof Error ? error.message : '行动删除失败' }
  finally { saving.value = '' }
}
</script>

<template>
  <section v-if="plan" class="action-board">
    <div class="action-stage">
      <span class="field-coordinate" aria-hidden="true">PATHFY / ACTION SIGNATURE · {{ String(actions.length).padStart(2, '0') }}</span>
      <header class="board-header">
        <div>
          <p class="eyebrow">NOW / ACTION FIELD</p>
          <h2>第 {{ plan.next_month_plan?.plan_month || 1 }} 月<br>{{ plan.next_month_plan?.phase_label || '近期任务' }}</h2>
          <p>把行动变成可以被看到、被核对、被复盘的真实进展。</p>
        </div>
        <div class="header-actions"><span class="mode-chip">{{ modeLabel }}</span><UButton size="sm" icon="i-lucide-plus" @click="openCreate">添加行动</UButton></div>
      </header>

      <div class="pulse-station">
        <span>GENERATIVE TRACE / 本月行动纹样</span>
        <ReportActionPulse :done="doneCount" :total="actions.length" :hours="totalHours" :evidence="evidenceCount" :kinds="kindCount" />
      </div>

      <aside class="next-move">
        <span>NEXT MOVE / 下一步</span>
        <strong>{{ nextAction?.title || '本月行动已全部完成' }}</strong>
        <p>{{ nextAction?.deliverable || '现在可以带着成果进入复盘，让事实决定下一轮计划。' }}</p>
        <div><b>{{ doneCount }}/{{ actions.length }}</b><small>完成</small><b>{{ totalHours }}h</b><small>预计投入</small></div>
      </aside>
    </div>

    <div v-if="actionError" class="save-error" role="alert"><UIcon name="i-lucide-circle-alert" /><span>{{ actionError }}</span><button type="button" @click="actionError=''">关闭</button></div>

    <div v-if="actions.length" class="task-workbench">
      <div class="task-workbench-heading"><span>EXECUTION TRACE / 执行轨迹</span><p>勾选不是终点，交付物与验收标准才让行动留下证据。</p></div>
      <div class="task-list">
      <article v-for="(action, index) in actions" :key="action.id" class="task-row" :class="{ done: action.done }" :data-kind="action.kind">
        <span class="task-index">{{ String(index + 1).padStart(2, '0') }}</span>
        <UCheckbox :model-value="Boolean(action.done)" :disabled="pendingActionIds.has(action.id)" :aria-label="`标记${action.title}为${action.done ? '未完成' : '完成'}`" @update:model-value="toggle(action, Boolean($event))" />
        <div class="task-main">
          <div class="task-title"><span v-if="index === 0 && !action.done" class="priority-dot">优先</span><strong>{{ action.title }}</strong><span class="kind">{{ kindLabel(action.kind) }}</span><span v-if="action.focus_label" class="task-focus">{{ action.focus_label }}</span></div>
          <p>{{ action.deliverable }}</p>
          <div class="task-meta"><span><UIcon name="i-lucide-calendar" />{{ action.deadline }}</span><span><UIcon name="i-lucide-clock-3" />{{ action.effort_hours }} 小时</span><span><UIcon name="i-lucide-badge-check" />{{ action.evidence_grade_required }} 级证据</span></div>
          <details><summary>验收标准</summary><p>{{ action.acceptance_criteria[0] }}</p></details>
        </div>
        <div class="row-actions"><UButton icon="i-lucide-pencil" color="neutral" variant="ghost" size="xs" aria-label="编辑行动" @click="openEdit(action)" /><UButton icon="i-lucide-trash-2" color="error" variant="ghost" size="xs" aria-label="删除行动" @click="remove(action)" /></div>
      </article>
      </div>
    </div>
    <div v-else class="empty-actions"><p>本月还没有行动</p><button type="button" @click="openCreate">添加第一项可完成的任务</button></div>

    <UModal v-model:open="editorOpen" :title="editorMode === 'create' ? '添加行动' : '编辑行动'">
      <template #body><div class="editor-grid">
        <UFormField label="行动标题" required><UInput v-model="form.text" maxlength="150" placeholder="例如：完成一个岗位相关项目并发布复盘" /></UFormField>
        <div class="editor-pair"><UFormField label="所属分组"><select v-model.number="form.item_index" class="native-field"><option v-for="(item,index) in groups" :key="index" :value="index">{{ item.focus_label || `计划分组 ${index + 1}` }}</option></select></UFormField><UFormField label="行动类型"><select v-model="form.kind" class="native-field"><option value="learn">学习</option><option value="practice">实践</option><option value="deliverable">成果</option></select></UFormField></div>
        <UFormField label="交付物"><UInput v-model="form.deliverable" maxlength="180" placeholder="能被查看或验证的成果" /></UFormField>
        <div class="editor-pair"><UFormField label="截止时间"><UInput v-model="form.deadline" maxlength="40" /></UFormField><UFormField label="预计投入（小时）"><UInput v-model.number="form.effort_hours" type="number" min="0.5" max="80" step="0.5" /></UFormField></div>
        <UFormField label="验收标准"><UTextarea v-model="form.acceptance_rule" :rows="3" maxlength="220" placeholder="做到什么程度才算完成" /></UFormField>
      </div></template>
      <template #footer><div class="flex w-full justify-end gap-2"><UButton color="neutral" variant="soft" @click="() => { editorOpen = false }">取消</UButton><UButton :loading="saving === editorMode" :disabled="!form.text.trim()" @click="saveEditor">保存行动</UButton></div></template>
    </UModal>
  </section>
</template>

<style scoped>
.action-board { display: grid; overflow: hidden; border: 1px solid color-mix(in srgb, var(--pathfy-capability) 28%, var(--ui-border)); border-radius: 1.65rem .55rem 1.65rem .55rem; background: var(--ui-bg); box-shadow: 0 36px 70px -58px rgb(5 34 42 / .9); }
.action-stage { position: relative; display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(16rem, .78fr) minmax(15rem, .72fr); gap: clamp(1rem, 2vw, 2rem); align-items: center; overflow: hidden; min-height: 27rem; padding: clamp(1.6rem, 3vw, 2.7rem); background: radial-gradient(circle at 53% 43%, rgb(30 151 145 / .2), transparent 26%), radial-gradient(circle at 98% 4%, rgb(240 215 123 / .08), transparent 25%), linear-gradient(135deg, #082f36, #061d28 72%); color: #effcf8; }
.action-stage::before { position: absolute; inset: 0; background-image: radial-gradient(rgb(103 232 194 / .17) .7px, transparent .7px); background-size: 22px 22px; mask-image: linear-gradient(90deg, #000, transparent 88%); content: ""; pointer-events: none; }
.action-stage::after { position: absolute; right: -7rem; bottom: -11rem; width: 24rem; height: 24rem; border: 1px solid rgb(103 232 194 / .08); border-radius: 46% 54% 61% 39%; box-shadow: 0 0 0 2.8rem rgb(103 232 194 / .025), 0 0 0 5.6rem rgb(103 232 194 / .018); content: ""; transform: rotate(24deg); }
.field-coordinate { position: absolute; right: 1.1rem; top: 1rem; z-index: 2; color: rgb(226 242 242 / .34); font: 650 .56rem/1.4 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .11em; }
.board-header, .next-move, .pulse-station { position: relative; z-index: 1; }
.board-header { align-self: stretch; display: flex; flex-direction: column; justify-content: space-between; gap: 1.5rem; }
.eyebrow { color: #67e8c2 !important; font: 800 .7rem/1.4 ui-monospace, SFMono-Regular, Menlo, monospace !important; letter-spacing: .13em; }
.board-header h2 { margin-top: .8rem; font-size: clamp(1.65rem, 3vw, 2.65rem); font-weight: 760; letter-spacing: -.045em; line-height: 1.08; }
.board-header p { max-width: 28rem; margin-top: .8rem; color: rgb(226 242 242 / .68); font-size: .82rem; line-height: 1.7; }
.header-actions { display: flex; flex-wrap: wrap; align-items: center; gap: .55rem; }
.mode-chip, .kind, .priority-dot { display: inline-flex; border-radius: 999px; padding: .18rem .5rem; font-size: .68rem; font-weight: 700; }
.mode-chip { border: 1px solid rgb(103 232 194 / .25); background: rgb(103 232 194 / .08); color: #9ff5dc; }
.pulse-station { display: grid; justify-items: center; align-self: stretch; border-right: 1px solid rgb(255 255 255 / .1); border-left: 1px solid rgb(255 255 255 / .1); padding: 0 clamp(.3rem, 1vw, .8rem); }
.pulse-station > span { align-self: start; color: rgb(226 242 242 / .44); font: 700 .58rem/1.4 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .11em; }
.pulse-station :deep(.action-pulse) { align-self: center; }
.next-move { align-self: center; display: flex; min-height: 17.5rem; flex-direction: column; justify-content: center; margin: .7rem 0; padding: 1.35rem 1.25rem; background: #f4ebcf; color: #24383c; box-shadow: 0 20px 34px -25px rgb(0 0 0 / .75); clip-path: polygon(1.5% 2%, 97% 0, 100% 95%, 48% 100%, 0 97%); transform: rotate(1.2deg); }
.next-move::before { position: absolute; top: -.35rem; left: 50%; width: 4.1rem; height: 1rem; background: rgb(255 255 255 / .52); box-shadow: 0 2px 4px rgb(20 30 34 / .1); content: ""; transform: translateX(-50%) rotate(-2deg); }
.next-move > span { color: #987217; font: 800 .67rem/1.4 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .11em; }
.next-move > strong { margin-top: .8rem; font-size: 1.05rem; line-height: 1.55; }
.next-move > p { margin-top: .55rem; color: rgb(36 56 60 / .68); font-size: .76rem; line-height: 1.65; }
.next-move > div { display: grid; grid-template-columns: auto 1fr auto 1fr; gap: .35rem .45rem; align-items: baseline; margin-top: 1.2rem; border-top: 1px dashed rgb(36 56 60 / .18); padding-top: .8rem; }
.next-move b { color: #0f766e; font-size: 1.4rem; }.next-move small { color: rgb(36 56 60 / .58); font-size: .64rem; }
.save-error { display: flex; align-items: center; gap: .5rem; margin: .8rem 1rem 0; padding: .65rem .75rem; border-radius: .6rem; background: color-mix(in srgb, var(--ui-error) 9%, transparent); color: var(--ui-error); font-size: .78rem; }.save-error span { flex: 1; }.save-error button { text-decoration: underline; }
.task-workbench { position: relative; background: linear-gradient(90deg, color-mix(in srgb, var(--pathfy-capability) 5%, transparent) 1px, transparent 1px), linear-gradient(var(--ui-bg), var(--pathfy-surface-workbench)); background-size: 32px 100%, 100% 100%; padding: clamp(1rem, 2.4vw, 2rem); }
.task-workbench::before { position: absolute; top: 0; bottom: 0; left: clamp(2.3rem, 5vw, 4.6rem); width: 1px; background: color-mix(in srgb, var(--pathfy-risk) 18%, transparent); content: ""; }
.task-workbench-heading { position: relative; display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; border-bottom: 1px solid var(--pathfy-line); padding: 0 .4rem 1rem 2.4rem; }.task-workbench-heading span { color: var(--pathfy-capability); font: 850 .68rem/1.4 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .11em; }.task-workbench-heading p { color: var(--ui-text-muted); font-size: .7rem; }
.task-list { position: relative; display: grid; }.task-row { --task-color: var(--pathfy-capability); position: relative; display: grid; grid-template-columns: 2rem auto minmax(0, 1fr) auto; align-items: flex-start; gap: .8rem; padding: 1.15rem .5rem 1.15rem .1rem; border-top: 1px dashed color-mix(in srgb, var(--ui-border) 68%, transparent); }.task-row[data-kind=learn] { --task-color: #4f83cc; }.task-row[data-kind=deliverable] { --task-color: #b7862d; }
.task-row::after { position: absolute; top: 1.55rem; left: 1.57rem; width: .42rem; height: .42rem; border: 1px solid color-mix(in srgb, var(--task-color) 65%, white); border-radius: 50%; background: var(--pathfy-surface-workbench); box-shadow: 0 0 0 .25rem color-mix(in srgb, var(--task-color) 8%, transparent); content: ""; }.task-row:first-child { border-top: 0; }.task-row:hover { background: linear-gradient(90deg, color-mix(in srgb, var(--task-color) 7%, transparent), transparent 72%); }.task-index { color: var(--task-color); font: 800 .7rem/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; }.task-row.done { opacity: .62; }.task-row.done strong { text-decoration: line-through; }.task-row.done::after { background: var(--task-color); }
.task-title { display: flex; flex-wrap: wrap; align-items: center; gap: .45rem; font-size: .9rem; }.priority-dot { background: color-mix(in srgb, var(--pathfy-gap) 13%, transparent); color: var(--pathfy-gap); }.kind { background: color-mix(in srgb, var(--task-color) 9%, var(--ui-bg)); color: var(--task-color); font-weight: 650; }.task-focus { color: var(--ui-text-muted); font-size: .66rem; }.task-focus::before { margin-right: .3rem; content: "/"; }
.task-main > p { margin-top: .35rem; color: var(--ui-text-muted); font-size: .76rem; line-height: 1.55; }.task-meta { display: flex; flex-wrap: wrap; gap: .85rem; margin-top: .6rem; color: var(--ui-text-muted); font-size: .7rem; }.task-meta span { display: flex; align-items: center; gap: .25rem; }.task-main details { margin-top: .55rem; font-size: .72rem; }.task-main summary { cursor: pointer; color: var(--task-color); }.task-main details p { margin-top: .35rem; color: var(--ui-text-muted); }.row-actions { display: flex; gap: .1rem; opacity: .5; }.task-row:hover .row-actions { opacity: 1; }
.empty-actions { padding: 3rem; text-align: center; color: var(--ui-text-muted); }.empty-actions button { margin-top: .35rem; color: var(--ui-primary); font-weight: 650; }.editor-grid { display: grid; gap: 1rem; }.editor-pair { display: grid; grid-template-columns: 1fr 1fr; gap: .8rem; }.native-field { width: 100%; min-height: 2.25rem; border: 1px solid var(--ui-border); border-radius: .5rem; background: var(--ui-bg); padding: 0 .65rem; color: var(--ui-text); }
@media (max-width: 980px) { .action-stage { grid-template-columns: 1fr 1fr; }.pulse-station { border-right: 0; }.next-move { grid-column: 1 / -1; width: min(100%, 32rem); min-height: 13rem; justify-self: center; }.next-move > div { max-width: 24rem; } }
@media (max-width: 700px) { .action-stage { grid-template-columns: 1fr; }.field-coordinate { display: none; }.board-header { min-height: 15rem; }.pulse-station { border-top: 1px solid rgb(255 255 255 / .1); border-left: 0; padding-top: 1rem; }.next-move { grid-column: auto; width: 100%; }.task-workbench { padding: .9rem .7rem; }.task-workbench::before { display: none; }.task-workbench-heading { display: grid; padding-left: .2rem; }.task-row { grid-template-columns: 1.5rem auto minmax(0, 1fr); padding: .9rem .2rem; }.task-row::after { display: none; }.row-actions { grid-column: 3; opacity: 1; }.editor-pair { grid-template-columns: 1fr; } }
</style>
