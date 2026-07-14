export const graphTaskCatalog = {
  job_import: { label: '岗位 Excel 导入', category: '岗位与能力', icon: 'i-lucide-file-spreadsheet', file: true },
  job_capability_evaluation: { label: '存量岗位八维评估', category: '岗位与能力', icon: 'i-lucide-gauge', file: false },
  job_capability_result_import: { label: '历史能力结果导入', category: '岗位与能力', icon: 'i-lucide-file-json-2', file: true },
  learning_resource_import: { label: '学习资源导入', category: '策展数据', icon: 'i-lucide-book-open', file: true },
  competition_import: { label: '竞赛导入', category: '策展数据', icon: 'i-lucide-trophy', file: true },
  job_promotion_import: { label: '晋升路线导入', category: '策展数据', icon: 'i-lucide-trending-up', file: true },
  job_lateral_import: { label: '横向换岗导入', category: '策展数据', icon: 'i-lucide-git-compare-arrows', file: true },
  promotion_recommendation_import: { label: '晋升推荐导入', category: '策展数据', icon: 'i-lucide-waypoints', file: true },
  salary_normalization: { label: '薪资规范化', category: '图谱维护', icon: 'i-lucide-badge-dollar-sign', file: false },
  inferred_job_cleanup: { label: '清理推断岗位', category: '图谱维护', icon: 'i-lucide-trash-2', file: false, dangerous: true },
  emergency_clear: { label: '紧急清空', category: '图谱维护', icon: 'i-lucide-triangle-alert', file: false, dangerous: true }
} as const

export type GraphTaskType = keyof typeof graphTaskCatalog
export const taskLabel = (type: string) => graphTaskCatalog[type as GraphTaskType]?.label || type
export const taskDangerous = (type: string) => {
  const item = graphTaskCatalog[type as GraphTaskType]
  return Boolean(item && 'dangerous' in item && item.dangerous)
}

export const graphStatusLabels: Record<string, string> = {
  queued: '排队中', running: '规划中', awaiting_confirmation: '待确认', applying: '应用中',
  succeeded: '已完成', partial_failed: '部分异常', failed: '失败', rejected: '已拒绝', cancelled: '已取消'
}

export const summaryLabels: Record<string, string> = {
  input_rows: '输入行数', unique_jobs: '唯一岗位', duplicate_rows: '重复行', new_or_changed_jobs: '新增/变化岗位',
  unchanged_jobs: '未变化岗位', evaluated_jobs: '已评估岗位', candidate_jobs: '候选岗位', low_confidence_jobs: '低置信度岗位',
  job_titles: '岗位名称', promotions: '晋升路线', lateral_transfers: '换岗关系', items: '数据项', job_title_links: '岗位关联',
  relationships: '关系数', resource_recommendations: '学习资源推荐', competition_recommendations: '竞赛推荐',
  jobs: '岗位数', parsed: '解析成功', unparsed: '无法解析', delete_jobs: '删除岗位', delete_job_titles: '删除岗位名称',
  affected_relationships: '影响关系', scope: '评估范围', source_id: '数据来源', snapshot_prune: '来源快照清理'
}
