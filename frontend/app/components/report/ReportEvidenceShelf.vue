<script setup lang="ts">
import { computed } from 'vue'
import type { ReportPlan, ReportRecommendationRef, ReportRecommendationSet } from '~/types/api'
import { safeExternalUrl } from '~/utils/external-url'

const props = defineProps<{ plan?: ReportPlan; recommendations?: ReportRecommendationSet }>()
const source = computed(() => props.plan?.recommendations || props.recommendations || {})
function label(item: ReportRecommendationRef) { return item.label || item.resource_name || item.competition_name || item.id || '推荐内容' }
function url(item: ReportRecommendationRef) { return safeExternalUrl(item.url || item.resource_url || item.official_url) }
const groups = computed(() => [
  { key:'learning', title:'学习资源', description:'用于补知识，不计为完成证据', icon:'i-lucide-book-open', items:source.value.learning_resources || [] },
  { key:'competition', title:'实践机会', description:'报名不等于能力证明，以实际产出为准', icon:'i-lucide-trophy', items:source.value.competitions || [] },
  { key:'project', title:'计划引用', description:'当前行动引用的候选材料与路径', icon:'i-lucide-waypoints', items:(props.plan?.next_month_plan?.items || []).flatMap(item => [...(item.learning_path_refs || []), ...(item.practice_plan_refs || [])]) }
])
</script>

<template>
  <section class="resource-shelf" aria-labelledby="resource-shelf-title">
    <header><div><span>候选输入</span><h3 id="resource-shelf-title">资源与成果入口</h3><p>这里提供行动素材，不把“推荐过、浏览过、报名过”误记成已经完成的证据。</p></div><UBadge label="需经复盘确认" color="warning" variant="soft" /></header>
    <div class="resource-grid">
      <section v-for="group in groups" :key="group.key" :data-group="group.key">
        <div class="group-title"><span><UIcon :name="group.icon" /><b>{{ group.title }}</b></span><em>{{ group.items.length }} 项</em></div>
        <p>{{ group.description }}</p>
        <div v-if="group.items.length" class="items">
          <component :is="url(item) ? 'a' : 'div'" v-for="(item, index) in group.items" :key="item.id || item.resource_id || item.competition_id || index" :href="url(item) || undefined" :target="url(item) ? '_blank' : undefined" rel="noopener noreferrer">
            <span><strong>{{ label(item) }}</strong><small>{{ [item.resource_type,item.competition_type,item.difficulty,item.skill_tag].filter(Boolean).join(' · ') || '候选行动材料' }}</small></span>
            <UIcon :name="url(item) ? 'i-lucide-external-link' : 'i-lucide-link-2-off'" />
          </component>
        </div>
        <p v-else class="empty">暂无匹配内容；不使用无关推荐填充版面。</p>
      </section>
    </div>
    <footer><UIcon name="i-lucide-clipboard-check" /><span>完成资源对应的练习后，到“复盘”记录产物链接、截图、证书或他人反馈，系统才会将其升级为个人证据。</span></footer>
  </section>
</template>

<style scoped>
.resource-shelf{border:1px solid color-mix(in srgb,var(--pathfy-gap) 20%,var(--pathfy-line));border-radius:1.2rem;background:radial-gradient(circle at 96% 0,color-mix(in srgb,var(--pathfy-gap) 10%,transparent),transparent 18rem),var(--pathfy-surface-panel);padding:1.35rem}.resource-shelf>header{display:flex;align-items:start;justify-content:space-between;gap:1rem}.resource-shelf header>div>span{color:var(--pathfy-gap);font-size:.74rem;font-weight:850;letter-spacing:.1em}.resource-shelf h3{margin-top:.28rem;font-size:1.28rem;font-weight:760}.resource-shelf header p{margin-top:.32rem;color:var(--ui-text-muted);font-size:.82rem;line-height:1.65}.resource-grid{display:grid;gap:.85rem;margin-top:1rem}.resource-grid>section{--group-tone:var(--pathfy-evidence);min-width:0;border:1px solid color-mix(in srgb,var(--group-tone) 20%,var(--pathfy-line));border-top:4px solid var(--group-tone);border-radius:.9rem;background:linear-gradient(145deg,color-mix(in srgb,var(--group-tone) 8%,var(--ui-bg-elevated)),var(--ui-bg-elevated) 42%);padding:1rem}.resource-grid>section[data-group=competition]{--group-tone:var(--pathfy-gap)}.resource-grid>section[data-group=project]{--group-tone:var(--pathfy-route)}.group-title{display:flex;align-items:center;justify-content:space-between;gap:.6rem}.group-title>span{display:flex;align-items:center;gap:.45rem;color:var(--group-tone);font-size:.9rem}.group-title em{border-radius:999px;background:color-mix(in srgb,var(--group-tone) 10%,var(--ui-bg));padding:.25rem .5rem;color:var(--group-tone);font-size:.68rem;font-style:normal;font-weight:700}.resource-grid>section>p{margin-top:.35rem;color:var(--ui-text-muted);font-size:.72rem;line-height:1.55}.items{display:grid;gap:.5rem;margin-top:.75rem}.items>a,.items>div{display:flex;align-items:center;justify-content:space-between;gap:.65rem;border:1px solid color-mix(in srgb,var(--group-tone) 9%,var(--pathfy-line));border-radius:.65rem;background:var(--ui-bg);padding:.68rem .72rem;font-size:.8rem;transition:transform 160ms ease,border-color 160ms ease}.items>a:hover{border-color:color-mix(in srgb,var(--group-tone) 45%,var(--pathfy-line));color:var(--group-tone);transform:translateX(2px)}.items span{min-width:0}.items strong,.items small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.items small{margin-top:.2rem;color:var(--ui-text-muted);font-size:.68rem}.items>div>svg{color:var(--ui-text-muted)}.resource-grid>section>.empty{margin-top:.7rem;border:1px dashed color-mix(in srgb,var(--group-tone) 22%,var(--pathfy-line));border-radius:.65rem;padding:.7rem}.resource-shelf>footer{display:flex;gap:.55rem;margin-top:1rem;border:1px solid color-mix(in srgb,var(--pathfy-success) 14%,var(--pathfy-line));border-radius:.8rem;background:color-mix(in srgb,var(--pathfy-success) 8%,var(--ui-bg-elevated));padding:.8rem;color:var(--ui-text-muted);font-size:.75rem;line-height:1.65}.resource-shelf>footer svg{flex:0 0 auto;color:var(--pathfy-success)}@media(min-width:800px){.resource-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:560px){.resource-shelf{padding:1rem}.resource-shelf>header{flex-direction:column}}
</style>
