<script setup lang="ts">
import { computed } from 'vue'
import type { DevelopmentAdjustment, DevelopmentLine } from '~/types/api'
const props=defineProps<{ line?:DevelopmentLine; adjustments:DevelopmentAdjustment[]; selectedMonth:number }>()
const emit=defineEmits<{ select:[month:number] }>()
const months=computed(()=>Array.from({length:13},(_,month)=>{ const review=props.line?.timeline?.find(item=>Math.round(Number(item.month)||0)===month && item.kind==='review'); const plans=props.adjustments.filter(item=>Math.round(Number(item.anchor_review_month ?? item.month)||0)===month); return {month,review,plans,hasPlan:plans.length>0} }))
</script>

<template>
  <UCard>
    <template #header><div><h2 class="font-semibold">0—12 月发展时间轴</h2><p class="text-xs muted">圆点代表已提交复盘，菱形代表计划或调整；点击节点查看当月详情。</p></div></template>
    <div class="timeline" role="group" aria-label="月度发展节点">
      <button v-for="item in months" :key="item.month" type="button" :class="{selected:item.month===selectedMonth,review:Boolean(item.review),plan:item.hasPlan}" :aria-current="item.month===selectedMonth ? 'step' : undefined" :aria-label="`查看第${item.month}月详情${item.review?'，已复盘':''}${item.hasPlan?'，有计划':''}${item.month===selectedMonth?'，当前查看':''}`" @click="emit('select',item.month)">
        <span class="node"><UIcon :name="item.review?'i-lucide-circle-check':item.hasPlan?'i-lucide-diamond':'i-lucide-circle'"/></span><strong>{{ item.month }}</strong><small>{{ item.month===selectedMonth?'当前查看':item.review?'已复盘':item.hasPlan?'有计划':item.month===0?'起点':'待进行' }}</small>
      </button>
    </div>
  </UCard>
</template>
<style scoped>.timeline{display:grid;grid-template-columns:repeat(13,minmax(3.3rem,1fr));gap:.35rem;overflow-x:auto;padding-bottom:.3rem}.timeline button{display:grid;min-width:3.3rem;place-items:center;border:1px solid transparent;border-radius:.7rem;padding:.5rem .25rem;color:var(--ui-text-muted)}.timeline button:hover,.timeline button.selected{border-color:var(--pathfy-capability);background:color-mix(in srgb,var(--pathfy-capability) 8%,transparent)}.timeline button.selected{box-shadow:inset 0 -2px var(--pathfy-capability)}.node{display:grid;width:1.7rem;height:1.7rem;place-items:center}.timeline .review .node{color:var(--pathfy-success)}.timeline .plan .node{color:var(--pathfy-gap)}.timeline strong{font-size:.8rem}.timeline small{font-size:.62rem;white-space:nowrap}</style>
