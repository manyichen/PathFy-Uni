<script setup lang="ts">
import type { CareerReport, ReportPdfActionScope, ReportPdfExportOptions, ReportTarget } from '~/types/report'

const props = defineProps<{
  open: boolean
  reportId: number
  report: CareerReport
  sourceTitle?: string
  exporting?: boolean
  exportError?: string
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  export: [options: ReportPdfExportOptions]
}>()

const sectionChoices: Array<{ key: keyof ReportPdfExportOptions['sections']; label: string; description: string }> = [
  { key: 'overview', label: '当前判断', description: '报告摘要、目标岗位与匹配概况' },
  { key: 'actions', label: '本月行动', description: '任务、交付物、投入与验收标准' },
  { key: 'evidence', label: '判断依据', description: '优势、缺口、风险及其事实来源' },
  { key: 'route', label: '推进路线', description: '阶段计划、真实复盘节点与调整' },
  { key: 'review', label: '复盘与校准', description: '最近确认复盘与执行诊断' },
  { key: 'resources', label: '资源清单', description: '课程、竞赛与实践资源' },
  { key: 'preference', label: '执行方式', description: '基于偏好的执行建议，不参与能力评分' }
]

const actionScopes: Array<{ value: ReportPdfActionScope; label: string }> = [
  { value: 'all', label: '全部行动' },
  { value: 'todo', label: '仅未完成' },
  { value: 'done', label: '仅已完成' }
]

function targetKey(target: ReportTarget): string {
  return String(target.job_id || target.id || '')
}

function targetLabel(target: ReportTarget): string {
  return String(target.display_title || target.title || targetKey(target) || '未命名目标')
}

function reportSummary(): string {
  return String(props.report.summary || props.report.overview || props.report.narrative?.text || '').trim()
}

function createDefaults(): ReportPdfExportOptions {
  return {
    document_title: props.sourceTitle?.trim() || '我的生涯发展档案',
    executive_summary: reportSummary(),
    closing_note: '这份档案用于支持下一步行动与复盘，请结合最新经历持续更新。',
    selected_target_job_ids: (props.report.targets || []).map(targetKey).filter(Boolean),
    sections: {
      overview: true,
      actions: true,
      evidence: true,
      route: true,
      review: true,
      resources: true,
      preference: true
    },
    action_scope: 'all',
    show_source_details: true,
    show_resource_links: true
  }
}

const form = reactive<ReportPdfExportOptions>(createDefaults())
const validationMessage = ref('')
const enabledSectionCount = computed(() => Object.values(form.sections).filter(Boolean).length)
const selectedTargets = computed(() => (props.report.targets || []).filter(target => form.selected_target_job_ids.includes(targetKey(target))))
const hasTargets = computed(() => (props.report.targets || []).length > 0)

function resetForm() {
  const defaults = createDefaults()
  Object.assign(form, defaults)
  form.sections = { ...defaults.sections }
  form.selected_target_job_ids = [...defaults.selected_target_job_ids]
  validationMessage.value = ''
}

function toggleTarget(jobId: string) {
  form.selected_target_job_ids = form.selected_target_job_ids.includes(jobId)
    ? form.selected_target_job_ids.filter(item => item !== jobId)
    : [...form.selected_target_job_ids, jobId]
}

function submit() {
  const title = form.document_title.trim()
  if (!title) {
    validationMessage.value = '请填写 PDF 标题。'
    return
  }
  if (hasTargets.value && !form.selected_target_job_ids.length) {
    validationMessage.value = '至少选择一个目标岗位。'
    return
  }
  if (!enabledSectionCount.value) {
    validationMessage.value = '至少保留一个报告章节。'
    return
  }
  validationMessage.value = ''
  emit('export', {
    ...form,
    document_title: title,
    executive_summary: form.executive_summary.trim(),
    closing_note: form.closing_note.trim(),
    selected_target_job_ids: [...form.selected_target_job_ids],
    sections: { ...form.sections }
  })
}

watch(() => props.open, (open) => {
  if (open) resetForm()
})
</script>

<template>
  <UModal
    :open="open"
    title="编辑并导出 PDF"
    description="生成一份独立的导出副本，不会修改当前生涯报告。"
    :dismissible="!exporting"
    :ui="{ content: 'max-w-[78rem]' }"
    @update:open="emit('update:open', $event)"
  >
    <template #body>
      <div class="pdf-workbench">
        <form class="pdf-editor" @submit.prevent="submit">
          <section class="editor-block is-intro">
            <span class="editor-index">01 / DOCUMENT</span>
            <UFormField label="PDF 标题" required>
              <UInput v-model="form.document_title" maxlength="120" class="w-full" placeholder="例如：我的 12 个月生涯行动档案" />
            </UFormField>
            <UFormField label="开篇摘要" hint="建议写清当前方向、主要差距与最近行动">
              <UTextarea v-model="form.executive_summary" :rows="4" :maxlength="3000" autoresize class="w-full" placeholder="留空时 PDF 将显示“暂无摘要”。" />
            </UFormField>
          </section>

          <section v-if="hasTargets" class="editor-block">
            <div class="block-heading"><span class="editor-index">02 / TARGETS</span><strong>导出哪些目标</strong></div>
            <div class="target-options">
              <label v-for="target in report.targets" :key="targetKey(target)" class="choice-card" :class="{ selected: form.selected_target_job_ids.includes(targetKey(target)) }">
                <input type="checkbox" :checked="form.selected_target_job_ids.includes(targetKey(target))" @change="toggleTarget(targetKey(target))">
                <span><strong>{{ targetLabel(target) }}</strong><small>{{ target.company || '目标岗位' }}</small></span>
              </label>
            </div>
          </section>

          <section class="editor-block">
            <div class="block-heading"><span class="editor-index">03 / SECTIONS</span><strong>编排报告内容</strong><small>{{ enabledSectionCount }}/{{ sectionChoices.length }} 个章节</small></div>
            <div class="section-options">
              <label v-for="section in sectionChoices" :key="section.key" class="section-option">
                <input v-model="form.sections[section.key]" type="checkbox">
                <span><strong>{{ section.label }}</strong><small>{{ section.description }}</small></span>
              </label>
            </div>
          </section>

          <section class="editor-block option-grid">
            <div>
              <span class="editor-index">04 / DETAILS</span>
              <UFormField label="行动范围">
                <select v-model="form.action_scope" class="native-select">
                  <option v-for="scope in actionScopes" :key="scope.value" :value="scope.value">{{ scope.label }}</option>
                </select>
              </UFormField>
            </div>
            <div class="switch-list">
              <label><input v-model="form.show_source_details" type="checkbox"><span>显示依据来源与证据等级</span></label>
              <label><input v-model="form.show_resource_links" type="checkbox"><span>在资源清单中显示链接</span></label>
            </div>
          </section>

          <section class="editor-block">
            <UFormField label="结语 / 备注" hint="仅写入本次 PDF">
              <UTextarea v-model="form.closing_note" :rows="3" :maxlength="2000" autoresize class="w-full" />
            </UFormField>
          </section>

          <UAlert v-if="validationMessage" color="error" variant="soft" icon="i-lucide-circle-alert" :title="validationMessage" />
          <UAlert v-else-if="exportError" color="error" variant="soft" icon="i-lucide-file-warning" title="PDF 导出失败" :description="`${exportError}。已保留当前编辑内容，可直接重试。`" />
        </form>

        <aside class="preview-stage" aria-label="PDF 内容预览">
          <div class="preview-toolbar"><span><i />A4 内容预览</span><small>实际分页由内容长度决定</small></div>
          <article class="paper-preview">
            <header>
              <span>PATHFY / CAREER ARCHIVE</span>
              <b>#{{ reportId }}</b>
            </header>
            <p class="paper-kicker">持续更新的生涯行动档案</p>
            <h2>{{ form.document_title || '未命名报告' }}</h2>
            <p class="paper-summary">{{ form.executive_summary || '暂无摘要。可在左侧补充当前方向、判断与下一步行动。' }}</p>
            <div class="paper-targets">
              <span v-for="target in selectedTargets" :key="targetKey(target)">{{ targetLabel(target) }}</span>
              <span v-if="!selectedTargets.length">尚未选择目标</span>
            </div>
            <ol class="paper-sections">
              <li v-for="section in sectionChoices.filter(item => form.sections[item.key])" :key="section.key">
                <span>{{ String(sectionChoices.indexOf(section) + 1).padStart(2, '0') }}</span>
                <div><strong>{{ section.label }}</strong><small>{{ section.description }}</small></div>
              </li>
            </ol>
            <footer><span>来源：报告事实 × 行动记录 × 已确认复盘</span><span>01 / 01</span></footer>
          </article>
        </aside>
      </div>
    </template>

    <template #footer>
      <div class="modal-footer">
        <p><i class="i-lucide-shield-check" /> 编辑内容仅用于本次导出，原报告保持不变。</p>
        <div>
          <UButton type="button" color="neutral" variant="ghost" :disabled="exporting" @click="resetForm">恢复默认</UButton>
          <UButton type="button" color="neutral" variant="soft" :disabled="exporting" @click="emit('update:open', false)">取消</UButton>
          <UButton type="button" icon="i-lucide-file-down" :loading="exporting" @click="submit">{{ exporting ? '正在排版…' : '生成并下载 PDF' }}</UButton>
        </div>
      </div>
    </template>
  </UModal>
</template>

<style scoped>
.pdf-workbench{display:grid;grid-template-columns:minmax(0,1fr) minmax(25rem,.82fr);gap:1.3rem;max-height:min(73vh,54rem);overflow:hidden}.pdf-editor{display:grid;gap:1rem;overflow:auto;padding:.15rem .65rem .8rem .1rem}.editor-block{display:grid;gap:.85rem;border:1px solid var(--ui-border);border-radius:1rem;background:color-mix(in srgb,var(--ui-bg-elevated) 92%,#e6f7fb);padding:1rem}.editor-block.is-intro{border-top:3px solid var(--pathfy-capability)}.editor-index{color:var(--pathfy-capability);font:800 .66rem/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.1em}.block-heading{display:flex;align-items:baseline;gap:.65rem}.block-heading strong{font-size:.95rem}.block-heading small{margin-left:auto;color:var(--ui-text-muted);font-size:.72rem}.target-options{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.6rem}.choice-card{display:flex;gap:.6rem;align-items:flex-start;border:1px solid var(--ui-border);border-radius:.75rem;padding:.75rem;cursor:pointer;transition:.16s ease}.choice-card.selected{border-color:color-mix(in srgb,var(--pathfy-capability) 58%,var(--ui-border));background:color-mix(in srgb,var(--pathfy-capability) 8%,var(--ui-bg))}.choice-card span,.section-option span{display:grid;gap:.18rem}.choice-card small,.section-option small{color:var(--ui-text-muted);font-size:.7rem;line-height:1.45}.section-options{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.35rem .9rem}.section-option{display:flex;align-items:flex-start;gap:.55rem;padding:.45rem .2rem;cursor:pointer}.section-option strong{font-size:.82rem}.option-grid{grid-template-columns:1fr 1fr;align-items:end}.option-grid>div:first-child{display:grid;gap:.65rem}.native-select{width:100%;min-height:2.45rem;border:1px solid var(--ui-border);border-radius:.55rem;background:var(--ui-bg);padding:0 .7rem;color:var(--ui-text);font-size:.875rem}.switch-list{display:grid;gap:.7rem;padding-bottom:.18rem}.switch-list label{display:flex;gap:.55rem;align-items:center;font-size:.8rem;cursor:pointer}.pdf-editor input[type=checkbox]{width:1rem;height:1rem;accent-color:var(--pathfy-capability);flex:0 0 auto}.preview-stage{overflow:auto;border-radius:1rem;background:linear-gradient(145deg,#e7f0f2,#eef1f8);padding:1rem}.preview-toolbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:.75rem;color:#3d5261;font-size:.72rem}.preview-toolbar span{display:flex;align-items:center;gap:.4rem;font-weight:800;letter-spacing:.05em}.preview-toolbar i{width:.48rem;height:.48rem;border-radius:999px;background:#16b8ad;box-shadow:0 0 0 4px rgb(22 184 173/.12)}.preview-toolbar small{font-size:.65rem}.paper-preview{position:relative;min-height:41rem;overflow:hidden;border:1px solid #d9d4c7;border-radius:.25rem;background:repeating-linear-gradient(90deg,transparent 0 29px,rgb(49 65 64/.035) 30px),#fffdf6;padding:2rem 2.15rem;color:#26363a;box-shadow:0 28px 55px -38px rgb(15 23 42/.65)}.paper-preview::after{position:absolute;right:0;top:0;width:3.8rem;height:3.8rem;background:linear-gradient(225deg,#d8dfd6 0 50%,transparent 51%);content:""}.paper-preview header,.paper-preview footer{display:flex;justify-content:space-between;border-bottom:1px solid rgb(38 54 58/.18);padding-bottom:.65rem;color:rgb(38 54 58/.5);font:650 .58rem/1.4 ui-monospace,monospace;letter-spacing:.08em}.paper-kicker{margin:2.1rem 0 .55rem;color:#088577;font-size:.69rem;font-weight:850}.paper-preview h2{max-width:24rem;margin:0;font-size:2rem;line-height:1.12;letter-spacing:-.045em}.paper-summary{margin:1rem 0 1.2rem;color:rgb(38 54 58/.68);font-size:.76rem;line-height:1.75;white-space:pre-line}.paper-targets{display:flex;flex-wrap:wrap;gap:.4rem;border-block:1px solid rgb(38 54 58/.13);padding:.75rem 0}.paper-targets span{border-radius:999px;background:#e2f0ed;padding:.28rem .55rem;color:#176c65;font-size:.63rem;font-weight:750}.paper-sections{display:grid;gap:0;margin:1rem 0 3rem;padding:0;list-style:none}.paper-sections li{display:grid;grid-template-columns:2rem 1fr;gap:.65rem;border-bottom:1px solid rgb(38 54 58/.12);padding:.72rem 0}.paper-sections li>span{color:#07877b;font:800 .6rem/1.5 ui-monospace,monospace}.paper-sections li div{display:grid;gap:.1rem}.paper-sections strong{font-size:.78rem}.paper-sections small{color:rgb(38 54 58/.58);font-size:.62rem}.paper-preview footer{position:absolute;right:2.15rem;bottom:1.3rem;left:2.15rem;border-top:1px solid rgb(38 54 58/.18);border-bottom:0;padding-top:.65rem;padding-bottom:0}.modal-footer{display:flex;width:100%;align-items:center;justify-content:space-between;gap:1rem}.modal-footer p{display:flex;align-items:center;gap:.4rem;color:var(--ui-text-muted);font-size:.75rem}.modal-footer>div{display:flex;gap:.5rem}@media(max-width:900px){.pdf-workbench{grid-template-columns:1fr;max-height:70vh;overflow:auto}.pdf-editor{overflow:visible}.preview-stage{display:none}}@media(max-width:580px){.target-options,.section-options,.option-grid{grid-template-columns:1fr}.modal-footer{align-items:flex-start;flex-direction:column}.modal-footer>div{width:100%;justify-content:flex-end}.modal-footer p{display:none}}
</style>
