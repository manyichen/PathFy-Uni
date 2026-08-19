<script setup lang="ts">
const route = useRoute()
const isAuthPage = computed(() => route.path === '/login' || route.path === '/register')
</script>

<template>
  <UApp>
    <AppHeader />
    <UMain :class="{ 'auth-main': isAuthPage }">
      <UContainer :class="isAuthPage ? 'auth-container' : 'py-6 sm:py-8'">
        <div class="page-viewport">
          <NuxtPage />
        </div>
      </UContainer>
    </UMain>
    <AppQuickDock v-if="!isAuthPage" />
  </UApp>
</template>
