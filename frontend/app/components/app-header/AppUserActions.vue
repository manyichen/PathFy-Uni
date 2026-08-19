<script setup lang="ts">
import AppAppearanceActions from './AppAppearanceActions.vue'

defineProps<{ authenticated: boolean; accountLabel: string }>()
defineEmits<{ logout: []; menu: [] }>()
</script>
<template><div class="header-actions"><AppAppearanceActions /><UButton v-if="authenticated" to="/account" color="neutral" variant="ghost" icon="i-lucide-user-round" class="account-entry desktop-auth-action">{{ accountLabel }}</UButton><UButton v-if="authenticated" color="neutral" variant="soft" icon="i-lucide-log-out" class="desktop-auth-action" @click="$emit('logout')">退出</UButton><UButton v-else to="/login" icon="i-lucide-log-in" class="desktop-auth-action">登录</UButton><UButton class="mobile-menu-button" icon="i-lucide-menu" color="neutral" variant="ghost" aria-label="打开导航" @click="$emit('menu')" /></div></template>
