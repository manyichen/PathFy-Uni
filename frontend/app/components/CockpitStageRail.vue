<script setup lang="ts">
type Stage = 'material' | 'profile' | 'match' | 'plan' | 'review'
withDefaults(defineProps<{ current?: Stage; variant?: 'default' | 'journey' }>(), {
  variant: 'default'
})
const stages: Array<{ key: Stage; label: string; hint: string; to: string }> = [
  { key: 'material', label: '材料', hint: '建立证据', to: '/profile' },
  { key: 'profile', label: '画像', hint: '能力与偏好', to: '/profile' },
  { key: 'match', label: '匹配', hint: '比较岗位', to: '/match' },
  { key: 'plan', label: '计划', hint: '拆解行动', to: '/report' },
  { key: 'review', label: '复盘', hint: '校准路线', to: '/report#review' }
]
</script>

<template>
  <nav class="cockpit-stage-rail" :class="{ 'is-journey': variant === 'journey' }" aria-label="职业规划工作流">
    <NuxtLink v-for="(stage, index) in stages" :key="stage.key" :to="stage.to" class="cockpit-stage-link" :class="{ active: stage.key === current }" :data-index="String(index + 1).padStart(2, '0')" :aria-current="stage.key === current ? 'step' : undefined">
      <strong>{{ stage.label }}</strong><span>{{ stage.hint }}</span>
    </NuxtLink>
  </nav>
</template>

<style scoped>
.cockpit-stage-rail.is-journey {
  position: relative;
  grid-template-columns: repeat(5, minmax(9rem, 1fr));
  gap: 0;
  overflow: visible;
  padding: 1.1rem 0 0.25rem;
}

.cockpit-stage-rail.is-journey::before {
  content: "";
  position: absolute;
  top: 2.1rem;
  right: 8%;
  left: 8%;
  height: 1px;
  background: linear-gradient(90deg, transparent, color-mix(in srgb, var(--pathfy-capability) 45%, var(--ui-border)) 12% 88%, transparent);
}

.is-journey .cockpit-stage-link {
  position: relative;
  min-width: 0;
  justify-items: center;
  gap: 0.18rem;
  border: 0;
  border-radius: 0;
  background: transparent;
  padding: 2.85rem 0.6rem 0.5rem;
  text-align: center;
}

.is-journey .cockpit-stage-link::before {
  top: 0.35rem;
  left: 50%;
  width: 2.2rem;
  height: 2.2rem;
  border: 1px solid color-mix(in srgb, var(--pathfy-capability) 35%, var(--ui-border));
  background: var(--ui-bg);
  color: var(--pathfy-capability);
  box-shadow: 0 0 0 0.45rem var(--ui-bg);
  transform: translateX(-50%);
  transition: transform 180ms ease, background 180ms ease, color 180ms ease;
}

.is-journey .cockpit-stage-link:hover::before {
  background: var(--pathfy-capability);
  color: var(--ui-text-inverted);
  transform: translateX(-50%) translateY(-0.18rem) rotate(-7deg);
}

.is-journey .cockpit-stage-link strong {
  font-size: 0.85rem;
}

.is-journey .cockpit-stage-link span {
  font-size: 0.7rem;
}

@media (max-width: 767px) {
  .cockpit-stage-rail.is-journey {
    grid-template-columns: repeat(5, minmax(7.5rem, 1fr));
    overflow-x: auto;
  }
}
</style>
