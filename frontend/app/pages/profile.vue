<script setup lang="ts">
import { useProfileWorkspace } from '~/composables/profile/useProfileWorkspace'

definePageMeta({ middleware: 'auth' })
useSeoMeta({ title: '个人职业画像' })
const workspace = useProfileWorkspace()
</script>

<template>
  <div class="cockpit-page profile-page">
    <CockpitPageHeader eyebrow="Career Portrait / Evidence & Preference" title="个人职业画像" description="把能力证据与工作偏好并列整理：一边回答你已经能做什么，一边说明怎样的工作方式更自然。" icon="i-lucide-radar" mark="02" edition-label="职业画像">
      <template #actions><UButton icon="i-lucide-history" color="neutral" variant="soft" @click="workspace.loadHistory">历史画像</UButton></template>
    </CockpitPageHeader>
    <CockpitStageRail current="profile" variant="journey" />

    <section class="profile-chapter">
      <header class="profile-chapter-heading">
        <span>01 · Primary View</span>
        <div><h2>先把你的经历摊开来</h2><p>材料进入左侧档案夹，经由中央能力雷达整理，最终沉淀为右侧两项核心刻度。</p></div>
        <small>INPUT → PORTRAIT</small>
      </header>
      <div class="profile-top-grid">
      <ProfileMaterialWorkbench v-model:name="workspace.name.value" v-model:major="workspace.major.value" v-model:text="workspace.text.value" :files="workspace.files.value" :loading="workspace.loading.value" :error="workspace.submitError.value" @choose="workspace.choose" @remove="workspace.removeFile" @submit="workspace.submit" />
      <ProfileRadarCard :scores="workspace.scores.value" :resume-id="workspace.activeResumeId.value" />
      <ProfileScoreSummary :completeness="workspace.result.value?.completeness" :competitiveness="workspace.result.value?.competitiveness" :completeness-text="workspace.analysis.value.completeness_analysis" :competitiveness-text="workspace.analysis.value.competitiveness_analysis" />
      </div>
      <ProfilePreferenceCard />
      <article v-if="workspace.result.value" class="profile-verdict profile-primary-verdict"><div><span>编辑批注 / OVERALL</span><UIcon name="i-lucide-quote" /></div><blockquote>{{ workspace.analysis.value.overall_evaluation || '暂无整体评价' }}</blockquote><p>这是一份阶段性判断。增加新的项目、证书或实践材料后，画像会随证据一起更新。</p></article>
    </section>
    <div v-if="!workspace.result.value" class="profile-empty"><span>档案仍是空白页</span><h2>还没有能力画像</h2><p>上传一份材料开始生成，或从历史画像中恢复。</p></div>
    <template v-else>
      <section class="profile-chapter">
      <header class="profile-chapter-heading"><span>02 · Supporting Evidence</span><div><h2>沿着证据，读懂这张画像</h2><p>核对参与分析的材料、优势与待提升项，再进入八个具体维度。</p></div><small>EVIDENCE → INSIGHT</small></header>
      <div class="profile-analysis-board">
        <ProfileEvidenceMap :materials="workspace.materials.value" :advantages="workspace.analysis.value.advantage_dimensions" :weaknesses="workspace.analysis.value['劣势_dimensions'] || workspace.analysis.value.weakness_dimensions" />
        <ProfileDimensionAnalysis :items="workspace.analysis.value.dimension_analysis" :material-names="workspace.materials.value.map(item => String(item.name || item.kind || '画像材料'))" />
        <header class="profile-chapter-heading profile-board-transition"><span>03 · Next Action</span><div><h2>让画像继续生长</h2><p>把近期动作排进日程，同时保留长期方向、行业机会与材料中的关键词。</p></div><small>INSIGHT → ACTION</small></header>
        <ProfileActionPlan :short-term="workspace.analysis.value.short_term_plan" :long-term="workspace.analysis.value.long_term_goals" :dimensions="workspace.analysis.value.dimension_analysis" />
        <div class="profile-opportunity-grid"><ProfileIndustryFit :items="workspace.analysis.value.industry_match || workspace.analysis.value.industry_adaptability" /><ProfileKeywordAnalysis :items="workspace.analysis.value.material_keywords || workspace.analysis.value.keywords || workspace.analysis.value.keyword_analysis" /></div>
      </div>
      </section>
    </template>
    <ProfileHistoryModal v-model:open="workspace.historyOpen.value" :items="workspace.history.value" :loading="workspace.historyLoading.value" :restoring-id="workspace.restoringId.value" :error="workspace.historyError.value" @restore="workspace.loadPortrait" @retry="workspace.loadHistory" />
  </div>
</template>

<style src="~/assets/css/profile-workspace.css"></style>
