<script setup lang="ts">
const props=defineProps<{guard:any}>()
</script>
<template><UAlert v-if="props.guard?.locked" color="warning" icon="i-lucide-lock" title="Neo4j 写入已锁定" :description="`任务 #${props.guard.locked_task_id} 正在等待确认，图谱版本 ${props.guard.graph_revision}`"><template #actions><UButton :to="`/graph-admin/tasks/${props.guard.locked_task_id}`" size="sm" color="warning" variant="soft">处理任务</UButton></template></UAlert></template>
