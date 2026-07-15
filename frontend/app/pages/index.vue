<script setup lang="ts">
useSeoMeta({
  title: '首页',
  description: '基于岗位图谱、能力画像和 AI 分析的大学生职业规划工作台'
})
</script>

<template>
  <div class="home-page">
    <HomeHero />
    <HomeProcessFlow />
    <HomeFeatureBento />
    <HomeExperienceShowcase />
  </div>
</template>

<style scoped>
.home-page {
  display: grid;
  gap: 3.5rem;
  padding-bottom: 2rem;
}
</style>
