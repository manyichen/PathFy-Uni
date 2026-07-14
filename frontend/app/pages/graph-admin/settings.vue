<script setup lang="ts">
definePageMeta({ middleware: 'admin' }); useSeoMeta({ title: '系统设置' })
const api = useSettingsApi(); const toast = useToast(); const loading = ref(true); const saving = ref(false)
const payload = ref<any>(); const form = reactive<Record<string, any>>({}); const historyOpen = ref(false); const revisions = ref<any[]>([])
const groups = [
  { key: 'jobs', label: '岗位助手', icon: 'i-lucide-message-circle' },
  { key: 'match', label: '人岗匹配', icon: 'i-lucide-target' },
  { key: 'career', label: '生涯报告', icon: 'i-lucide-file-text' },
  { key: 'graph', label: '图谱任务', icon: 'i-lucide-network' },
  { key: 'privacy', label: '隐私与成本', icon: 'i-lucide-shield-check' }
]
const fields = computed(() => payload.value?.definitions || [])
function fieldsFor(group: string) { return fields.value.filter((field: any) => field.group === group) }
function reset(values = payload.value?.settings || {}) {
  Object.keys(form).forEach(key => delete form[key])
  for (const [key, value] of Object.entries(values)) form[key] = value
}
async function load() { loading.value = true; try { payload.value = await api.admin(); reset() } catch (error) { toast.add({ title: String(error), color: 'error' }) } finally { loading.value = false } }
async function save() { saving.value = true; try { const result = await api.publish(payload.value.revision, { ...form }); payload.value = { ...payload.value, ...result }; reset(result.settings); toast.add({ title: `配置 revision ${result.revision} 已发布`, color: 'success' }) } catch (error) { toast.add({ title: String(error), color: 'error' }) } finally { saving.value = false } }
async function openHistory() { historyOpen.value = true; try { revisions.value = (await api.history()).items || [] } catch (error) { toast.add({ title: String(error), color: 'error' }) } }
async function loadRevision(revision: number) { const item = await api.revision(revision); reset(item.settings); historyOpen.value = false; toast.add({ title: `已载入 revision ${revision}，发布后会生成新版本` }) }
function restoreDefaults() { reset(payload.value?.defaults || {}); toast.add({ title: '已恢复部署默认值，发布后生效' }) }
onMounted(load)
</script>

<template><div class="page-stack"><div class="flex flex-wrap items-end justify-between gap-3"><div class="page-heading"><h1 class="flex items-center gap-2"><UIcon name="i-lucide-settings" class="text-primary"/>系统设置</h1><p class="muted">整版发布业务策略；密钥、连接地址和磁盘路径仍由部署环境管理</p></div><div class="flex flex-wrap gap-2"><UButton color="neutral" variant="ghost" icon="i-lucide-rotate-ccw" @click="restoreDefaults">恢复部署默认</UButton><UButton color="neutral" variant="soft" icon="i-lucide-history" @click="openHistory">历史版本</UButton><UButton icon="i-lucide-save" :loading="saving" :disabled="loading" @click="save">发布整版配置</UButton></div></div>
<UAlert v-if="payload" color="info" icon="i-lucide-git-commit-horizontal" :title="payload.revision ? `当前 revision ${payload.revision}` : '尚未发布数据库配置'" :description="payload.source === 'legacy_env' ? '当前沿用环境变量；首次发布将创建 revision 1。' : '新请求立即使用本版本，既有任务和历史结果仍使用各自快照。'"/>
<USkeleton v-if="loading" class="h-96"/><template v-else><UCard v-for="group in groups" :key="group.key"><template #header><div class="flex items-center gap-2"><UIcon :name="group.icon" class="text-primary"/><h2 class="font-semibold">{{group.label}}</h2></div></template><div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3"><UFormField v-for="field in fieldsFor(group.key)" :key="field.key" :label="field.label" :hint="field.advanced?'高级参数':''"><USwitch v-if="field.kind==='bool'" v-model="form[field.key]"/><USelect v-else-if="field.options?.length" v-model="form[field.key]" :items="field.options" class="w-full"/><UInput v-else v-model.number="form[field.key]" type="number" :min="field.minimum" :max="field.maximum" :step="field.kind==='float'?'0.01':'1'" class="w-full"/></UFormField></div></UCard>
<UCard><template #header><h2 class="font-semibold">部署能力状态</h2></template><div class="flex flex-wrap gap-2"><UBadge v-for="(ready,key) in payload.credential_status" :key="key" :color="ready?'success':'neutral'" variant="soft" :label="`${key}: ${ready?'已配置':'未配置'}`"/></div><p class="mt-3 text-sm muted">这里只显示配置状态，后台不会读取或回显密钥。</p></UCard></template>
<UModal v-model:open="historyOpen" title="系统设置历史"><template #body><div class="grid gap-2"><button v-for="item in revisions" :key="item.revision" type="button" class="flex items-center justify-between rounded-xl border border-default p-3 text-left hover:border-primary" @click="loadRevision(item.revision)"><span><strong>revision {{item.revision}}</strong><span class="ml-2 text-sm muted">{{item.username||'系统'}} · {{item.created_at}}</span><small class="mt-1 block muted">{{item.changes?.length||0}} 项变化</small></span><UIcon name="i-lucide-rotate-ccw"/></button><UEmpty v-if="!revisions.length" title="暂无已发布版本"/></div></template></UModal></div></template>
