<script setup lang="ts">
import type { AuthJourneyMode } from '~/types/auth-journey'

const props = defineProps<{ mode: AuthJourneyMode }>()

const content = computed(() => props.mode === 'login'
  ? {
      eyebrow: 'CONTINUE YOUR PATH',
      title: '回来，继续向前。',
      description: '从上一次停下的位置出发，让岗位、能力与行动重新连接。',
      start: '此刻',
      end: '下一步',
      startMeta: 'ME',
      endMeta: 'PATH'
    }
  : {
      eyebrow: 'BEGIN YOUR PATH',
      title: '从一个起点，看见更多方向。',
      description: '建立你的第一份职业画像，让每一种可能都有清晰的依据。',
      start: '起点',
      end: '方向',
      startMeta: 'ME',
      endMeta: 'PATH'
    })
</script>

<template>
  <section data-auth-journey-stage class="auth-journey-stage" aria-labelledby="auth-journey-title">
    <div class="auth-journey-copy">
      <p class="auth-journey-eyebrow">{{ content.eyebrow }}</p>
      <h2 id="auth-journey-title">{{ content.title }}</h2>
      <p>{{ content.description }}</p>
    </div>

    <div class="auth-journey-axis" aria-hidden="true">
      <div class="auth-axis-label auth-axis-label-start">
        <span>{{ content.start }}</span>
        <small>{{ content.startMeta }}</small>
      </div>
      <div class="auth-axis-label auth-axis-label-end">
        <span>{{ content.end }}</span>
        <small>{{ content.endMeta }}</small>
      </div>
    </div>

    <div class="auth-journey-footnote" aria-hidden="true">
      <span>01</span>
      <p>一条暂时的路线，不是一种唯一的答案。</p>
    </div>
  </section>
</template>
