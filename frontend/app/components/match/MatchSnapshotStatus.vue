<script setup lang="ts">
defineProps<{ warning?: string; restoredMessage?: string }>()
</script>

<template>
  <UAlert v-if="warning" color="warning" variant="soft" icon="i-lucide-cloud-alert" title="结果已生成，但快照保存失败" description="可继续查看本次结果；报告页暂时无法复用这次匹配，请稍后重新匹配。" />
  <UAlert v-else-if="restoredMessage" color="info" variant="soft" icon="i-lucide-history" title="已恢复历史匹配" :description="restoredMessage" />
  <UAlert v-else color="success" variant="soft" icon="i-lucide-cloud-check" title="匹配快照已保存" description="本次结果可在匹配历史中恢复，也可供职业报告导入。" />
</template>
