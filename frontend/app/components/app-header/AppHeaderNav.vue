<script setup lang="ts">
import type { HeaderNavItem } from '~/types/navigation'

defineProps<{ items: HeaderNavItem[] }>()
</script>

<template>
  <nav class="desktop-nav" aria-label="主导航">
    <NuxtLink
      v-for="item in items"
      :key="item.to"
      :to="item.to"
      class="nav-pill"
      :class="{ 'is-active': item.active }"
      :aria-current="item.active ? 'page' : undefined"
    >
      <UIcon :name="item.icon" class="size-4 shrink-0" />
      <span>{{ item.label }}</span>
    </NuxtLink>
  </nav>
</template>

<style scoped>
.desktop-nav {
  display: none;
  min-width: 0;
  justify-content: center;
  gap: 0.15rem;
}

.nav-pill {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  min-height: 2.5rem;
  border-radius: 0.7rem;
  padding: 0 0.62rem;
  color: var(--ui-text-muted);
  font-size: 0.86rem;
  font-weight: 600;
  text-decoration: none;
  transition: color 160ms ease, background 160ms ease, transform 160ms ease;
}

.nav-pill::after {
  content: "";
  position: absolute;
  right: 0.72rem;
  bottom: 0.38rem;
  left: 0.72rem;
  height: 2px;
  border-radius: 999px;
  background: var(--ui-primary);
  opacity: 0;
  transform: scaleX(0.3);
  transition: opacity 160ms ease, transform 160ms ease;
}

.nav-pill:hover {
  background: color-mix(in srgb, var(--ui-primary) 7%, transparent);
  color: var(--ui-text);
}

.nav-pill.is-active {
  background: color-mix(in srgb, var(--ui-primary) 11%, transparent);
  color: var(--ui-primary);
}

.nav-pill.is-active::after {
  opacity: 1;
  transform: scaleX(1);
}

@media (min-width: 1180px) {
  .desktop-nav {
    display: flex;
  }
}
</style>
