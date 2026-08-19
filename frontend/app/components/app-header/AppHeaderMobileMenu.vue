<script setup lang="ts">
import type { HeaderNavItem } from '~/types/navigation'

defineProps<{
  open: boolean
  items: HeaderNavItem[]
  authenticated: boolean
  accountLabel: string
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  logout: []
}>()

function close() {
  emit('update:open', false)
}
</script>

<template>
  <USlideover
    :open="open"
    title="导航"
    :ui="{ content: 'sm:max-w-sm', body: 'p-0' }"
    @update:open="emit('update:open', $event)"
  >
    <template #body>
      <div class="mobile-panel">
        <div class="mobile-panel-head">
          <div class="mobile-mark">
            <img src="/assets/home/fu.svg" alt="" class="size-7">
          </div>
          <div>
            <p class="text-sm font-semibold">PathFy</p>
            <p class="text-xs muted">选择一个入口继续规划</p>
          </div>
        </div>

        <nav class="mobile-nav" aria-label="移动端导航">
          <NuxtLink
            v-for="item in items"
            :key="item.to"
            :to="item.to"
            class="mobile-nav-link"
            :class="{ 'is-active': item.active }"
            :aria-current="item.active ? 'page' : undefined"
            @click="close"
          >
            <UIcon :name="item.icon" class="size-4 shrink-0" />
            <span>{{ item.label }}</span>
            <UIcon name="i-lucide-chevron-right" class="ml-auto size-4 opacity-45" />
          </NuxtLink>
        </nav>

        <div class="mobile-account">
          <UButton
            v-if="authenticated"
            to="/account"
            icon="i-lucide-user-round"
            color="neutral"
            variant="soft"
            block
            @click="close"
          >
            {{ accountLabel }}
          </UButton>
          <UButton
            v-if="authenticated"
            icon="i-lucide-log-out"
            color="error"
            variant="ghost"
            block
            @click="emit('logout')"
          >
            退出
          </UButton>
          <UButton v-else to="/login" icon="i-lucide-log-in" block @click="close">
            登录
          </UButton>
        </div>
      </div>
    </template>
  </USlideover>
</template>

<style scoped>
.mobile-mark {
  display: grid;
  place-items: center;
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 0.75rem;
  background: color-mix(in srgb, var(--ui-primary) 12%, var(--ui-bg));
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-primary) 20%, transparent);
}

.mobile-panel {
  display: grid;
  gap: 1rem;
  padding: 1rem;
}

.mobile-panel-head {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  border-bottom: 1px solid var(--ui-border);
  padding-bottom: 1rem;
}

.mobile-nav {
  display: grid;
  gap: 0.35rem;
}

.mobile-nav-link {
  position: relative;
  display: flex;
  min-height: 2.75rem;
  align-items: center;
  gap: 0.65rem;
  border: 1px solid transparent;
  border-radius: 0.75rem;
  padding: 0 0.75rem;
  color: var(--ui-text-muted);
  font-size: 0.95rem;
  font-weight: 600;
  text-decoration: none;
  transition: color 160ms ease, border-color 160ms ease, background 160ms ease;
}

.mobile-nav-link::before {
  content: "";
  width: 3px;
  height: 1.35rem;
  border-radius: 999px;
  background: var(--ui-primary);
  opacity: 0;
  transform: scaleY(0.45);
  transition: opacity 160ms ease, transform 160ms ease;
}

.mobile-nav-link:hover,
.mobile-nav-link.is-active {
  border-color: color-mix(in srgb, var(--ui-primary) 22%, transparent);
  background: color-mix(in srgb, var(--ui-primary) 8%, transparent);
  color: var(--ui-primary);
}

.mobile-nav-link.is-active::before {
  opacity: 1;
  transform: scaleY(1);
}

.mobile-account {
  display: grid;
  gap: 0.5rem;
  border-top: 1px solid var(--ui-border);
  padding-top: 1rem;
}
</style>
