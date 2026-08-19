<script setup lang="ts">
import { useHeaderController } from '~/composables/app-header/useHeaderController'
import AppBrand from '~/components/app-header/AppBrand.vue'
import AppLogoutConfirm from '~/components/app-header/AppLogoutConfirm.vue'
import AppUserActions from '~/components/app-header/AppUserActions.vue'

const header = useHeaderController()
</script>

<template>
  <header class="app-header" :class="{ 'is-scrolled': header.headerScrolled.value }">
    <div class="header-shell">
      <div class="header-bar">
        <AppBrand />
        <AppHeaderNav :items="header.nav.value" />
        <AppUserActions :authenticated="header.auth.isAuthenticated.value" :account-label="header.accountLabel.value" @logout="header.requestLogout" @menu="header.mobileOpen.value = true" />
      </div>
    </div>
  </header>
  <AppHeaderMobileMenu v-model:open="header.mobileOpen.value" :items="header.nav.value" :authenticated="header.auth.isAuthenticated.value" :account-label="header.accountLabel.value" @logout="header.requestLogout" />
  <AppLogoutConfirm v-model:open="header.logoutOpen.value" @confirm="header.logout" />
</template>
