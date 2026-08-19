<script setup lang="ts">
import type { DevelopmentLine } from '~/types/api'

defineProps<{ lines: DevelopmentLine[] }>()
const fullscreen = ref(false)
const trigger = ref<{ $el?: HTMLElement } | null>(null)
function openFullscreen() { fullscreen.value = true }
function closeFullscreen() { fullscreen.value = false }
watch(fullscreen, (value, previous) => { if (!value && previous) nextTick(() => trigger.value?.$el?.focus()) })
</script>

<template>
  <section v-if="lines.length">
    <div class="section-heading"><div><h2>发展线与复盘节点</h2><p>横轴是报告生成后的第 0—12 月，纵轴是复盘进步度；折线由计划节点与真实复盘共同形成。</p></div><UButton ref="trigger" color="neutral" variant="soft" icon="i-lucide-maximize-2" @click="openFullscreen">全屏查看发展线</UButton></div>
    <UCard>
      <DeferredDevelopmentLineChart :lines="lines" />
      <div class="mt-3 border-t border-default pt-4">
        <div class="grid gap-4">
          <article v-for="line in lines" :key="line.line_id">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <h3 class="font-semibold">{{ line.line_name }}</h3>
              <span class="text-xs muted">蓝色节点表示已复盘，其他节点表示计划安排</span>
            </div>
            <div v-if="line.timeline?.length" class="mt-2 flex flex-wrap gap-2">
              <UBadge
                v-for="point in line.timeline"
                :key="`${point.month}-${point.review_id}`"
                :label="`${point.month} 月 · ${point.label || Math.round(point.progress || 0) + '%'}`"
                :color="point.kind === 'review' ? 'primary' : 'neutral'"
                variant="soft"
              />
            </div>
          </article>
        </div>
      </div>
    </UCard>
    <UModal v-model:open="fullscreen" fullscreen title="发展线与复盘节点"><template #body><div class="mx-auto grid min-h-[75vh] w-full max-w-6xl place-items-center"><DeferredDevelopmentLineChart :lines="lines" class="w-full" /></div></template><template #footer><div class="flex w-full justify-end"><UButton icon="i-lucide-minimize-2" @click="closeFullscreen">关闭全屏</UButton></div></template></UModal>
  </section>
</template>

<style scoped>
.section-heading {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  justify-content: space-between;
  gap: .75rem;
  margin: 0.25rem 0 0.8rem;
}

.section-heading h2 {
  font-size: 1.2rem;
  font-weight: 700;
}

.section-heading p {
  margin-top: 0.2rem;
  color: var(--ui-text-muted);
  font-size: 0.875rem;
}
</style>
