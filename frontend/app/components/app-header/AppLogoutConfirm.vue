<script setup lang="ts">
defineEmits<{ confirm: [] }>()
const open = defineModel<boolean>('open', { required: true })
function close() { open.value = false }
</script>
<template><UModal v-model:open="open" title="确认退出登录" description="退出后会清除本机登录状态和当前用户缓存"><template #footer><div class="flex w-full justify-end gap-2"><UButton color="neutral" variant="ghost" @click="close">取消</UButton><UButton color="error" icon="i-lucide-log-out" @click="$emit('confirm')">确认退出</UButton></div></template></UModal></template>
