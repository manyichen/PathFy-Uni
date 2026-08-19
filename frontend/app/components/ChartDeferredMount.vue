<script setup lang="ts">
const props = withDefaults(defineProps<{ height?: string; rootMargin?: string }>(), { height: '300px', rootMargin: '180px' })
const root = ref<HTMLElement>()
const visible = ref(false)
let observer: IntersectionObserver | undefined

onMounted(() => {
  if (!root.value || !('IntersectionObserver' in window)) { visible.value = true; return }
  observer = new IntersectionObserver(([entry]) => {
    if (!entry?.isIntersecting) return
    visible.value = true
    observer?.disconnect()
  }, { rootMargin: props.rootMargin })
  observer.observe(root.value)
})

onBeforeUnmount(() => observer?.disconnect())
</script>

<template>
  <div ref="root" :style="{ minHeight: height }" :aria-busy="!visible">
    <slot v-if="visible" />
    <USkeleton v-else class="w-full" :style="{ height }" />
  </div>
</template>
