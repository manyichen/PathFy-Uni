<script setup lang="ts">
import { useAccountPreferences } from '~/composables/account/useAccountPreferences'

definePageMeta({ middleware: 'auth' })
useSeoMeta({ title: '个人中心' })
const account = useAccountPreferences()
</script>

<template>
  <div class="cockpit-page">
    <CockpitPageHeader eyebrow="Personal Settings / Control" title="个人中心" description="集中管理账户身份、界面主题、匹配偏好、推荐范围与隐私选择。" icon="i-lucide-circle-user-round" mark="07" edition-label="个人设置" />
    <USkeleton v-if="account.loading.value" class="h-96" />
    <template v-else>
      <AccountIdentityCard :user="account.auth.user.value" :admin="account.auth.isAdmin.value" />
      <div class="grid gap-4 xl:grid-cols-2"><AccountAppearanceCard :form="account.form" /><AccountMatchPreferences :form="account.form" :max-results="account.limits.value.match_result_count" :error="account.errors.value.match_result_count" /></div>
      <AccountPrivacyCard :form="account.form" :payload="account.data.value" />
      <AccountRecommendationLimits :form="account.form" :learning-max="account.limits.value.learning_resource_count" :competition-max="account.limits.value.competition_count" :learning-error="account.errors.value.learning_resource_count" :competition-error="account.errors.value.competition_count" />
      <AccountSaveBar :dirty="account.dirty.value" :saving="account.saving.value" :valid="account.valid.value" :error="account.saveError.value" @save="account.save" @rollback="account.rollback" />
    </template>
  </div>
</template>
