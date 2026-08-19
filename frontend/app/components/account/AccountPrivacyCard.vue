<script setup lang="ts">
import type { PreferencesPayload, UserPreferences } from '~/types/settings'
defineProps<{ payload?: PreferencesPayload; form: UserPreferences }>()
</script>

<template>
  <UCard>
    <template #header><div><h2 class="font-semibold">AI、人格偏好与隐私</h2><p class="text-sm muted">人格数据只用于工作方式解释；关闭后，匹配和新报告不再读取人格画像。</p></div></template>
    <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <USwitch v-model="form.allow_external_llm" label="允许外部 AI 处理个人数据" />
      <USwitch v-model="form.use_personality_in_match" label="在匹配中使用人格偏好" />
      <USwitch v-model="form.use_personality_in_report" label="在报告中使用人格偏好" />
      <USwitch v-model="form.report_copywriter" label="报告 AI 文案" />
      <USwitch v-model="form.report_public_info" label="公开信息增强" />
      <USwitch v-model="form.report_auto_replan" label="自动重新规划" />
      <USwitch v-model="form.report_graph_recommendations" label="图谱资源推荐" />
      <USwitch v-model="form.report_recommendation_llm" label="推荐 AI 精排" />
      <USwitch v-model="form.report_longitudinal_personalization" label="基于确认历史优化执行节奏" />
    </div>
    <UFormField class="mt-5" label="默认工作偏好模式"><USelect v-model="form.default_preference_mode" :items="[{label:'不使用',value:'off'},{label:'仅解释',value:'explain'},{label:'同分带软排序实验',value:'tie_break'}]" /></UFormField>
    <UAlert class="mt-5" color="info" variant="soft" icon="i-lucide-info" title="数据边界" description="人格偏好不会改写八维能力、岗位要求或能力缺口；报告保存生成时的最小派生快照，复盘行为证据必须由你确认。" />
    <div v-if="payload?.effective" class="mt-3 text-xs muted">当前平台实际生效：外部 AI {{ payload.effective.allow_external_llm ? '允许' : '关闭' }}，匹配结果最多 {{ payload.effective.match_result_count ?? form.match_result_count }} 个。</div>
  </UCard>
</template>
