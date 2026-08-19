<script setup lang="ts">
type ModuleItem = {
  to: string
  title: string
  question: string
  verb: string
  desc: string
  icon: string
  evidence: string[]
  output: string
  tone: string
}

const modules: ModuleItem[] = [
  { to: '/jobs', title: '岗位探索', question: '市场上有哪些真实机会？', verb: '看市场', desc: '从行业、城市、薪资和能力标签里筛选真实岗位，把“我想做什么”放进现实坐标。', icon: 'i-lucide-briefcase-business', evidence: ['岗位样本', '薪资区间', '能力关键词'], output: '候选方向清单', tone: '#0e7490' },
  { to: '/profile', title: '个人职业画像', question: '我的优势和偏好是什么？', verb: '看自己', desc: '把经历拆成可追溯的八维能力，也把工作偏好作为并列信息呈现，不把性格误当成能力。', icon: 'i-lucide-radar', evidence: ['简历材料', '八维评分', '工作偏好'], output: '能力与偏好双层画像', tone: '#0f766e' },
  { to: '/match', title: '人岗匹配', question: '我和目标之间差多少？', verb: '看差距', desc: '并排比较岗位要求与个人画像，找到最值得投入时间的提升项，并解释匹配依据。', icon: 'i-lucide-git-compare', evidence: ['匹配分', '维度差距', '解释文本'], output: '优先提升项', tone: '#2563eb' },
  { to: '/graph', title: '职业图谱', question: '这条路还能走向哪里？', verb: '看路径', desc: '沿着晋升、转岗和能力迁移关系探索路线，不只盯住眼前的一个职位名称。', icon: 'i-lucide-network', evidence: ['岗位节点', '路径关系', '资源密度'], output: '发展路线判断', tone: '#7c3aed' },
  { to: '/report', title: '生涯报告', question: '下个月具体做什么？', verb: '做计划', desc: '把目标岗位拆成短中期行动，保留目标来源、差距、证据和每一次复盘。', icon: 'i-lucide-file-text', evidence: ['目标岗位', '行动计划', '复盘记录'], output: '动态报告画布', tone: '#b45309' },
  { to: '/personality', title: '工作偏好测评', question: '怎样的环境让我更自在？', verb: '补偏好', desc: '理解沟通方式、工作节奏和环境偏好，为能力与岗位判断补上一层人的感受。', icon: 'i-lucide-brain', evidence: ['问卷回答', '连续偏好', '人格指纹'], output: '工作偏好画像', tone: '#be185d' }
]

const activeIndex = ref(0)
const activeModule = computed(() => modules[activeIndex.value] ?? modules[0]!)
const sceneStyle = computed(() => ({ '--tone': activeModule.value.tone }))
</script>

<template>
  <section class="module-atlas" aria-labelledby="feature-title">
    <header class="atlas-heading home-editorial-heading">
      <div class="section-mark home-editorial-mark" aria-hidden="true"><span>02</span><i /></div>
      <div class="home-editorial-title">
        <p class="home-editorial-kicker">从你的问题出发</p>
        <h2 id="feature-title">选择一个入口，直接开始规划</h2>
      </div>
      <p class="atlas-note home-editorial-note">不需要按固定顺序完成。选中此刻最困扰你的那个问题，其他材料会在后续自动汇合。</p>
    </header>

    <div class="module-browser" :style="sceneStyle">
      <div class="module-index" role="tablist" aria-label="规划模块">
        <button
          v-for="(item, index) in modules"
          :id="`module-tab-${index}`"
          :key="item.to"
          type="button"
          role="tab"
          :aria-controls="'module-stage'"
          :aria-selected="index === activeIndex"
          :class="{ active: index === activeIndex }"
          @click="activeIndex = index"
        >
          <span class="index-number">{{ String(index + 1).padStart(2, '0') }}</span>
          <span class="index-copy"><strong>{{ item.verb }}</strong><small>{{ item.title }}</small></span>
          <UIcon name="i-lucide-arrow-up-right" class="size-4 index-arrow" />
        </button>
      </div>

      <article id="module-stage" class="module-stage" role="tabpanel" :aria-labelledby="`module-tab-${activeIndex}`">
        <div class="stage-watermark" aria-hidden="true">{{ String(activeIndex + 1).padStart(2, '0') }}</div>
        <div class="stage-orbit" aria-hidden="true">
          <span /><span /><span />
          <UIcon :name="activeModule.icon" class="orbit-icon" />
        </div>

        <div class="stage-copy">
          <p class="stage-verb">{{ activeModule.verb }}</p>
          <h3>{{ activeModule.question }}</h3>
          <p class="stage-description">{{ activeModule.desc }}</p>
          <UButton :to="activeModule.to" color="primary" size="lg" trailing-icon="i-lucide-arrow-up-right">
            打开{{ activeModule.title }}
          </UButton>
        </div>

        <div class="evidence-thread">
          <span class="thread-label">带入</span>
          <div v-for="item in activeModule.evidence" :key="item" class="thread-node">{{ item }}</div>
          <UIcon name="i-lucide-arrow-right" class="size-4" />
          <div class="thread-output"><span>得到</span><strong>{{ activeModule.output }}</strong></div>
        </div>
      </article>
    </div>
  </section>
</template>

<style>
.module-atlas { display: grid; gap: 1.5rem; }
.module-browser { --tone: var(--pathfy-capability); display: grid; grid-template-columns: minmax(12rem, .27fr) minmax(0, 1fr); min-height: 34rem; overflow: hidden; border: 1px solid var(--ui-border); border-radius: 1.75rem; background: color-mix(in srgb, var(--tone) 3%, var(--ui-bg)); box-shadow: 0 30px 70px -55px rgb(15 23 42 / .75); }
.module-index { display: grid; align-content: center; padding: 1.5rem 0; background: color-mix(in srgb, var(--ui-bg-elevated) 82%, transparent); }
.module-index button { display: grid; grid-template-columns: 2rem 1fr auto; gap: .75rem; align-items: center; border: 0; border-left: 3px solid transparent; background: transparent; padding: .9rem 1.25rem .9rem 1rem; color: var(--ui-text-muted); text-align: left; transition: background 180ms ease, color 180ms ease, border-color 180ms ease; }
.module-index button:hover, .module-index button.active { border-left-color: var(--tone); background: color-mix(in srgb, var(--tone) 8%, transparent); color: var(--ui-text); }
.index-number { color: var(--ui-text-muted); font: 800 .72rem/1 ui-monospace, SFMono-Regular, Menlo, monospace; }
.index-copy { display: grid; gap: .08rem; }
.index-copy strong { font-size: .88rem; }
.index-copy small { color: var(--ui-text-muted); font-size: .7rem; font-weight: 600; }
.index-arrow { opacity: 0; transform: translate(-.25rem, .25rem); transition: opacity 160ms ease, transform 160ms ease; }
.module-index button.active .index-arrow { opacity: 1; transform: translate(0); }
.module-stage { position: relative; display: grid; align-content: space-between; min-width: 0; overflow: hidden; padding: clamp(2rem, 5vw, 4.5rem); background: radial-gradient(circle at 76% 33%, color-mix(in srgb, var(--tone) 16%, transparent), transparent 28%), linear-gradient(135deg, color-mix(in srgb, var(--tone) 7%, transparent), transparent 44%); }
.stage-watermark { position: absolute; top: -2.7rem; right: 1.5rem; color: color-mix(in srgb, var(--tone) 7%, transparent); font: 800 clamp(11rem, 22vw, 20rem)/1 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: -.12em; user-select: none; }
.stage-copy { position: relative; z-index: 2; max-width: 37rem; }
.stage-verb { color: var(--tone); font-size: .78rem; font-weight: 850; letter-spacing: .1em; }
.stage-copy h3 { margin-top: .75rem; font-size: clamp(2rem, 4vw, 3.7rem); font-weight: 780; letter-spacing: -.055em; line-height: 1.08; text-wrap: balance; }
.stage-description { max-width: 34rem; margin: 1.2rem 0 1.7rem; color: var(--ui-text-muted); font-size: .92rem; line-height: 1.8; }
.stage-orbit { position: absolute; top: 3rem; right: 4rem; width: 11rem; height: 11rem; border: 1px solid color-mix(in srgb, var(--tone) 22%, transparent); border-radius: 50%; }
.stage-orbit span { position: absolute; inset: 18%; border: 1px solid color-mix(in srgb, var(--tone) 20%, transparent); border-radius: 50%; }
.stage-orbit span:nth-child(2) { inset: 36%; }
.stage-orbit span:nth-child(3) { top: 49%; right: -1.3rem; bottom: auto; left: auto; width: .55rem; height: .55rem; border: 0; background: var(--tone); box-shadow: 0 0 0 .35rem color-mix(in srgb, var(--tone) 12%, transparent); }
.orbit-icon { position: absolute; top: 50%; left: 50%; width: 2rem; height: 2rem; color: var(--tone); transform: translate(-50%, -50%); }
.evidence-thread { position: relative; z-index: 2; display: flex; flex-wrap: wrap; gap: .55rem; align-items: center; margin-top: 3rem; border-top: 1px solid var(--ui-border); padding-top: 1rem; }
.thread-label { color: var(--ui-text-muted); font-size: .7rem; }
.thread-node { border: 1px solid color-mix(in srgb, var(--tone) 25%, var(--ui-border)); border-radius: 999px; background: color-mix(in srgb, var(--tone) 6%, var(--ui-bg)); padding: .4rem .7rem; color: var(--ui-text-muted); font-size: .72rem; }
.thread-output { display: flex; gap: .4rem; align-items: baseline; margin-left: auto; }
.thread-output span { color: var(--ui-text-muted); font-size: .7rem; }
.thread-output strong { color: color-mix(in srgb, var(--tone) 74%, var(--ui-text)); font-size: .82rem; }

@media (max-width: 1023px) {
  .module-browser { grid-template-columns: 1fr; min-height: auto; }
  .module-index { grid-template-columns: repeat(6, minmax(7rem, 1fr)); overflow-x: auto; padding: 0; }
  .module-index button { grid-template-columns: auto 1fr; border-left: 0; border-bottom: 3px solid transparent; padding: .9rem; }
  .module-index button:hover, .module-index button.active { border-bottom-color: var(--tone); }
  .index-copy small, .index-arrow { display: none; }
  .module-stage { min-height: 29rem; }
}

@media (max-width: 767px) {
  .module-browser { border-radius: 1.2rem; }
  .module-stage { min-height: 32rem; padding: 2rem 1.25rem; }
  .stage-orbit { top: auto; right: -2rem; bottom: 4rem; opacity: .7; }
  .stage-copy h3 { max-width: 18rem; }
  .thread-output { width: 100%; margin-left: 0; }
}
</style>
