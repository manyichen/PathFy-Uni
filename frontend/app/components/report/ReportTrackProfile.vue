<script setup lang="ts">
import { computed } from 'vue'
import type { PublicInfoState, ReportTarget } from '~/types/api'
import { safeExternalUrl } from '~/utils/external-url'

const props = defineProps<{ target?: ReportTarget; state?: PublicInfoState }>()
const emit = defineEmits<{ load: [forceRefresh?: boolean] }>()
const metrics = computed(() => [
  { label: '招聘可见度', value: props.target?.track_profile?.hiring_visibility_0_100, hint: '内部岗位样本活跃度' },
  { label: '路径宽度', value: props.target?.track_profile?.path_breadth_0_100, hint: '系统估算的迁移空间' },
  { label: '资源密度', value: props.target?.track_profile?.resource_density_0_100, hint: '内置资源覆盖程度' }
])
function sourceUrl(value: unknown) { return safeExternalUrl(value) }
function metricValue(value: unknown) {
  const score = Number(value)
  return Number.isFinite(score) ? Math.round(score) : undefined
}
</script>

<template>
  <section class="track-profile" aria-labelledby="track-profile-title">
    <header>
      <div><span>外部校验</span><h3 id="track-profile-title">赛道信号</h3><p>{{ target?.track_profile?.job_title || target?.display_title || target?.title || '当前目标' }}</p></div>
      <UButton size="xs" color="neutral" variant="soft" icon="i-lucide-globe-2" :loading="state?.loading" @click="emit('load')">获取公开信息</UButton>
    </header>
    <div class="track-grid">
      <div v-for="metric in metrics" :key="metric.label" :class="{ missing: metricValue(metric.value) === undefined }">
        <strong>{{ metricValue(metric.value) ?? '—' }}</strong><span>{{ metric.label }}</span><small>{{ metric.hint }}</small>
      </div>
    </div>
    <p class="model-note"><UIcon name="i-lucide-database" />以上是项目内部岗位图谱指标，不是实时市场统计；缺失值不再按 0 展示。</p>
    <UAlert v-if="state?.error" class="mt-3" color="error" variant="soft" title="当前岗位公开信息加载失败" :description="state.error" />
    <div v-if="state?.data" class="public-info">
      <div class="public-info-label"><UIcon name="i-lucide-scan-search" /><strong>公开信息校验结果</strong></div>
      <p>{{ state.data.summary || '当前来源未提供可用摘要。' }}</p>
      <div v-if="state.data.sources?.length" class="sources"><a v-for="source in state.data.sources" v-show="sourceUrl(source.url)" :key="source.url || source.title" :href="sourceUrl(source.url)" target="_blank" rel="noopener noreferrer">{{ source.title || '查看来源' }}<UIcon name="i-lucide-external-link" /></a><UButton size="xs" color="neutral" variant="ghost" @click="emit('load', true)">刷新</UButton></div>
      <p v-else class="no-source">该摘要暂未附带可访问来源，请仅作辅助判断。</p>
    </div>
  </section>
</template>

<style scoped>
.track-profile{border:1px solid color-mix(in srgb,var(--pathfy-route) 22%,var(--pathfy-line));border-radius:1.15rem;background:radial-gradient(circle at 100% 0,color-mix(in srgb,var(--pathfy-route) 13%,transparent),transparent 14rem),var(--pathfy-surface-panel);padding:1.25rem}.track-profile>header{display:flex;align-items:start;justify-content:space-between;gap:1rem}.track-profile header>div>span{color:var(--pathfy-route);font-size:.73rem;font-weight:850;letter-spacing:.1em}.track-profile h3{margin-top:.28rem;font-size:1.15rem;font-weight:760}.track-profile header p{margin-top:.25rem;color:var(--ui-text-muted);font-size:.8rem}.track-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.65rem;margin-top:1rem}.track-grid>div{--metric-tone:var(--pathfy-route);display:grid;min-height:7rem;border:1px solid color-mix(in srgb,var(--metric-tone) 17%,var(--pathfy-line));border-radius:.85rem;background:linear-gradient(145deg,color-mix(in srgb,var(--metric-tone) 9%,var(--ui-bg)),var(--ui-bg));padding:.85rem;text-align:left}.track-grid>div:nth-child(2){--metric-tone:var(--pathfy-evidence)}.track-grid>div:nth-child(3){--metric-tone:var(--pathfy-success)}.track-grid>div.missing{border-style:dashed;--metric-tone:var(--ui-text-muted)}.track-grid strong{color:var(--metric-tone);font-size:1.8rem;line-height:1}.track-grid span{margin-top:.55rem;font-size:.8rem;font-weight:730}.track-grid small{margin-top:.25rem;color:var(--ui-text-muted);font-size:.68rem;line-height:1.5}.model-note{display:flex;gap:.45rem;margin-top:.85rem;color:var(--ui-text-muted);font-size:.72rem;line-height:1.6}.model-note svg{flex:0 0 auto;color:var(--pathfy-route)}.public-info{margin-top:.9rem;border:1px solid color-mix(in srgb,var(--pathfy-evidence) 18%,var(--pathfy-line));border-left:4px solid var(--pathfy-evidence);border-radius:.8rem;background:color-mix(in srgb,var(--pathfy-evidence) 7%,var(--ui-bg-elevated));padding:.9rem}.public-info-label{display:flex;align-items:center;gap:.4rem;font-size:.8rem}.public-info>p{margin-top:.45rem;color:var(--ui-text-muted);font-size:.8rem;line-height:1.7}.sources{display:flex;flex-wrap:wrap;align-items:center;gap:.55rem;margin-top:.7rem}.sources a{display:flex;align-items:center;gap:.25rem;color:var(--pathfy-evidence);font-size:.75rem}.public-info .no-source{font-size:.72rem;color:var(--pathfy-gap)}@media(max-width:520px){.track-grid{grid-template-columns:1fr}.track-grid>div{min-height:auto}.track-profile>header{align-items:flex-start}}
</style>
