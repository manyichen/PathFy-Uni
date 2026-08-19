<script setup lang="ts">
import type { MatchPreferenceContext } from '~/types/match'
const props = defineProps<{ context?: MatchPreferenceContext }>()
const content = computed(() => {
  const context = props.context
  if (!context || context.mode === 'off') return { color: 'neutral' as const, icon: 'i-lucide-shield-minus', title: '本次仅使用八维能力匹配', description: '工作偏好没有参与解释或排序。' }
  if (context.status !== 'measured') return { color: 'warning' as const, icon: 'i-lucide-circle-dashed', title: '工作偏好暂不可用', description: context.status === 'legacy' ? '历史结果需要重新测评后才能生成连续偏好解释。' : context.status === 'disabled' ? '个性化已关闭，本次仍按能力排序。' : '补充人格测评后可获得工作方式解释。' }
  const tie = context.tie_break
  if (context.mode === 'tie_break') {
    if (tie?.applied) return { color: 'success' as const, icon: 'i-lucide-list-filter', title: '已启用同分岗位偏好优先', description: `只在能力分差不超过 ${tie.max_ability_gap} 分的岗位中二级排序，共 ${tie.changed_jobs} 个岗位名次变化；可切回原能力排名。` }
    const reasons: Record<string, string> = { system_disabled: '系统安全开关当前关闭', insufficient_workstyle_coverage: `岗位证据覆盖率 ${(Number(context.workstyle_coverage || 0) * 100).toFixed(0)}%，未达到 ${(Number(tie?.minimum_coverage || 0) * 100).toFixed(0)}%`, experiment_control: '本次处于实验对照组', missing_user_profile: '偏好画像不可用' }
    return { color: 'info' as const, icon: 'i-lucide-flask-conical', title: '已请求偏好软排序，本次保持能力原序', description: `${reasons[tie?.reason || ''] || '未满足启用条件'}；偏好解释仍可查看。` }
  }
  return { color: 'info' as const, icon: 'i-lucide-brain-circuit', title: `${context.mbti_type || '当前'} 工作偏好已附加到本次匹配`, description: context.jobs_with_preference_fit ? `本次有 ${context.jobs_with_preference_fit} 个岗位达到解释门槛；逐轴结论均可展开查看证据，且没有改变能力排名。` : '本次岗位尚未达到工作环境证据门槛，因此不输出伪精确分数，也不改变排名。' }
})
</script>

<template><UAlert :color="content.color" variant="soft" :icon="content.icon" :title="content.title" :description="content.description" /></template>
