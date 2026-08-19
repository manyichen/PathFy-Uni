<script setup lang="ts">
import { classifyProfileMaterial, formatProfileFileSize } from '~/utils/profile-display'

defineProps<{ files: File[]; loading: boolean; error?: string }>()
defineEmits<{ choose: [event: Event]; remove: [index: number]; submit: [] }>()
const name = defineModel<string>('name', { required: true })
const major = defineModel<string>('major', { required: true })
const text = defineModel<string>('text', { required: true })
const accept = '.pdf,.docx,.txt,.md,.markdown,.csv,.json,.xls,.xlsx,.png,.jpg,.jpeg,.webp'
</script>

<template>
  <section class="profile-material-workbench" aria-labelledby="profile-material-heading">
    <header><div><span>01 / COLLECT</span><h2 id="profile-material-heading">装入个人材料</h2></div><UIcon name="i-lucide-folder-open" /></header>
    <p class="profile-material-intro">简历只是封面，项目、证书与成绩才让画像拥有细节。</p>
    <div class="profile-material-form">
      <div class="grid gap-3 sm:grid-cols-2"><UFormField label="姓名" required><UInput v-model="name" class="w-full" autocomplete="name" /></UFormField><UFormField label="专业" required><UInput v-model="major" class="w-full" /></UFormField></div>
      <UFormField label="上传材料" help="PDF、DOCX、TXT、Markdown、CSV、JSON、Excel 或图片">
        <div class="profile-upload-drop">
          <input id="profile-material-input" type="file" multiple :accept="accept" class="file-input" aria-label="上传材料" aria-describedby="profile-file-help" @change="$emit('choose', $event)">
          <label for="profile-material-input"><UIcon name="i-lucide-file-plus-2" /><span><strong>选择或拖入材料</strong><small>支持多份不同类型的经历证明</small></span></label>
        </div>
        <p id="profile-file-help" class="mt-2 text-xs muted">已选 {{ files.length }}/12；支持简历、证书、成绩、项目及补充材料。</p>
      </UFormField>
      <ul v-if="files.length" class="grid gap-2" aria-label="待上传材料">
        <li v-for="(file, index) in files" :key="`${file.name}-${file.lastModified}`" class="file-row">
          <div class="min-w-0"><div class="flex items-center gap-2"><UBadge :label="classifyProfileMaterial(file.name)" size="sm" variant="soft" /><span class="truncate text-sm font-medium">{{ file.name }}</span></div><p class="mt-1 text-xs muted">{{ formatProfileFileSize(file.size) }}</p></div>
          <UButton icon="i-lucide-x" color="neutral" variant="ghost" size="sm" :aria-label="`移除 ${file.name}`" @click="$emit('remove', Number(index))" />
        </li>
      </ul>
      <UFormField label="补充文本"><UTextarea v-model="text" :rows="4" autoresize :maxrows="8" class="w-full" placeholder="补充课程、项目、竞赛或职业目标" /></UFormField>
      <UAlert v-if="error" id="profile-submit-error" role="alert" color="error" variant="soft" icon="i-lucide-circle-alert" title="画像生成未完成" :description="error" />
      <UButton block :loading="loading" icon="i-lucide-sparkles" @click="$emit('submit')">生成能力画像</UButton>
    </div>
    <p class="profile-material-footnote">最多 12 份 · 单份不超过 10MB · 后端执行最终校验</p>
  </section>
</template>

<style>
.profile-material-workbench { min-width:0; padding:1.25rem; background:color-mix(in srgb,var(--pathfy-capability) 5%,var(--ui-bg)); }
.profile-material-workbench header { display:flex; align-items:flex-start; justify-content:space-between; gap:1rem; padding-bottom:.9rem; border-bottom:1px solid var(--pathfy-line); }
.profile-material-workbench header span,.profile-material-footnote { color:var(--ui-text-muted); font-size:.63rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }
.profile-material-workbench header h2 { margin-top:.18rem; font-size:1.05rem; font-weight:750; }
.profile-material-workbench header svg { width:1.35rem; height:1.35rem; color:var(--pathfy-capability); }
.profile-material-intro { margin:.8rem 0 1rem; color:var(--ui-text-muted); font-size:.76rem; line-height:1.65; }
.profile-material-form { display:grid; gap:1rem; }
.profile-material-footnote { margin-top:1rem; line-height:1.5; }
.profile-upload-drop { position:relative; }.file-input { position:absolute; z-index:1; inset:0; width:100%; height:100%; cursor:pointer; opacity:0; }
.profile-upload-drop label { display:flex; min-height:4.2rem; align-items:center; gap:.75rem; border:1px dashed color-mix(in srgb,var(--pathfy-capability) 48%,var(--ui-border)); border-radius:.65rem; background:var(--ui-bg); padding:.7rem; transition:border-color .18s ease,background .18s ease; }.profile-upload-drop label>svg { width:1.2rem;height:1.2rem;color:var(--pathfy-capability); }.profile-upload-drop label span { display:grid;gap:.12rem; }.profile-upload-drop label strong { font-size:.75rem; }.profile-upload-drop label small { color:var(--ui-text-muted);font-size:.63rem; }.file-input:hover+label { border-color:var(--pathfy-capability);background:color-mix(in srgb,var(--pathfy-capability) 5%,var(--ui-bg)); }.file-input:focus-visible+label { outline:2px solid var(--ui-primary);outline-offset:2px; }
.file-row { display: flex; min-width: 0; align-items: center; justify-content: space-between; gap: .75rem; border-left: 2px solid var(--pathfy-capability); background:var(--ui-bg); padding: .6rem .7rem; }
</style>
