<script setup lang="ts">
const WorkflowExperienceDialog = defineAsyncComponent(() => import('~/components/visualization/home/HomeWorkflowExperience.vue'))
const experienceOpen = ref(false)
const experienceTrigger = ref<{ $el?: HTMLElement }>()

const routes = [
  {
    title: '先把方向缩小',
    desc: '从真实岗位、城市与能力要求里，删掉那些听起来不错、实际并不适合的选项。',
    note: '留下 3 个值得继续看的方向',
    icon: 'i-lucide-compass'
  },
  {
    title: '再把经历变成证据',
    desc: '课程、项目、竞赛和作品不再散落，它们会被放到对应的岗位要求旁边。',
    note: '知道优势来自哪里，也看见空缺',
    icon: 'i-lucide-folder-check'
  },
  {
    title: '用结果修正下一步',
    desc: '计划不是一次写完。每个月把完成情况放回来，路线会跟着真实进展变化。',
    note: '让报告持续生长，而不是封存',
    icon: 'i-lucide-refresh-cw'
  }
]

const quickActions = [
  { label: '放入一份简历', to: '/profile', icon: 'i-lucide-paperclip' },
  { label: '补充工作偏好', to: '/personality', icon: 'i-lucide-brain-circuit' },
  { label: '挑选候选岗位', to: '/jobs', icon: 'i-lucide-search' },
  { label: '看一次能力差距', to: '/match', icon: 'i-lucide-git-compare' },
  { label: '整理下月计划', to: '/report', icon: 'i-lucide-calendar-range' }
]

function openExperience() {
  experienceOpen.value = true
}

function updateExperienceOpen(open: boolean) {
  experienceOpen.value = open
  if (!open) nextTick(() => experienceTrigger.value?.$el?.focus())
}
</script>

<template>
  <section class="decision-studio" aria-labelledby="decision-title">
    <header class="studio-heading home-editorial-heading">
      <div class="section-mark home-editorial-mark" aria-hidden="true">
        <span>01</span>
        <i />
      </div>
      <div class="heading-copy home-editorial-title">
        <p class="home-editorial-kicker">把问题放到桌面上</p>
        <h2 id="decision-title">先别急着找答案，先看清自己站在哪里</h2>
      </div>
      <p class="heading-note home-editorial-note">
        职业选择很少是一道单选题。PathFy 把方向、证据和行动摊开，让你看见每一步为什么发生。
      </p>
    </header>

    <div class="route-field">
      <div class="field-noise" aria-hidden="true" />
      <svg class="route-line" viewBox="0 0 1000 590" preserveAspectRatio="none" aria-hidden="true">
        <path d="M75 104 C250 40 330 185 276 270 C222 355 146 324 160 432 C174 548 410 520 530 388 C650 256 656 105 826 88" />
        <circle cx="76" cy="104" r="7" />
        <circle cx="276" cy="270" r="7" />
        <circle cx="160" cy="432" r="7" />
      </svg>

      <article v-for="(route, index) in routes" :key="route.title" class="route-stop" :class="`route-stop-${index + 1}`">
        <div class="stop-head">
          <span>{{ String(index + 1).padStart(2, '0') }}</span>
          <UIcon :name="route.icon" class="size-5" />
        </div>
        <h3>{{ route.title }}</h3>
        <p>{{ route.desc }}</p>
        <small>{{ route.note }}</small>
      </article>

      <aside class="today-note">
        <span class="note-pin" aria-hidden="true" />
        <p class="note-label">今天，只做一件小事</p>
        <strong>先留下第一份<br>可以被判断的证据</strong>
        <p class="note-copy">不用填完所有资料。简历、一个作品链接，或一个感兴趣的岗位都可以成为起点。</p>
        <UButton to="/profile" color="neutral" trailing-icon="i-lucide-arrow-up-right">
          从一份简历开始
        </UButton>
      </aside>

      <div class="quick-route" aria-label="快速开始">
        <span class="quick-label">也可以从这里插队</span>
        <NuxtLink v-for="action in quickActions" :key="action.to" :to="action.to">
          <UIcon :name="action.icon" class="size-4" />
          <span>{{ action.label }}</span>
          <UIcon name="i-lucide-arrow-right" class="size-4 arrow" />
        </NuxtLink>
      </div>

      <UButton
        ref="experienceTrigger"
        class="experience-trigger"
        color="primary"
        variant="solid"
        icon="i-lucide-play"
        @click="openExperience"
      >
        体验五阶段职业路径
      </UButton>
    </div>

    <div class="signal-equation" aria-label="PathFy 的判断逻辑">
      <span>岗位正在要求什么</span>
      <b>×</b>
      <span>你的能力证据与工作偏好</span>
      <b>→</b>
      <strong>下一步该把时间放在哪里</strong>
    </div>

    <WorkflowExperienceDialog v-if="experienceOpen" :open="experienceOpen" @update:open="updateExperienceOpen" />
  </section>
</template>

<style>
.decision-studio { display: grid; gap: 1.5rem; }
.route-field { position: relative; min-height: 36.875rem; overflow: hidden; border-radius: 1.75rem; background: radial-gradient(circle at 78% 14%, rgb(103 232 219 / .14), transparent 26%), linear-gradient(145deg, #102b2d, #071b25 58%, #071421); color: white; box-shadow: 0 36px 80px -48px rgb(2 20 28 / .9); }
.field-noise { position: absolute; inset: 0; opacity: .42; background-image: radial-gradient(rgb(255 255 255 / .22) .7px, transparent .7px); background-size: 18px 18px; mask-image: linear-gradient(110deg, black, transparent 70%); }
.route-line { position: absolute; inset: 0; width: 62%; height: 100%; overflow: visible; }
.route-line path { fill: none; stroke: rgb(94 234 212 / .55); stroke-width: 2; stroke-dasharray: 7 9; }
.route-line circle { fill: #f4d889; stroke: #102b2d; stroke-width: 5; }
.route-stop { position: absolute; z-index: 1; width: min(27rem, 37%); padding-left: 3.4rem; }
.route-stop-1 { top: 3.4rem; left: 5.4rem; }
.route-stop-2 { top: 13.5rem; left: 17.5rem; }
.route-stop-3 { top: 24.3rem; left: 6.7rem; }
.stop-head { position: absolute; top: 0; left: 0; display: grid; width: 2.45rem; justify-items: center; gap: .35rem; color: #85e5da; font: 700 .68rem/1 ui-monospace, SFMono-Regular, Menlo, monospace; }
.route-stop h3 { font-size: 1.18rem; font-weight: 760; }
.route-stop > p { max-width: 25rem; margin-top: .45rem; color: rgb(226 245 244 / .7); font-size: .83rem; line-height: 1.65; }
.route-stop small { display: inline-block; margin-top: .65rem; color: #f4d889; font-size: .72rem; }
.today-note { position: absolute; z-index: 2; top: 3.3rem; right: 4.3rem; width: min(19rem, 29%); border-radius: .3rem 1rem 1rem .3rem; background: #f4efd9; padding: 2.1rem 1.55rem 1.5rem; color: #173135; box-shadow: 0 28px 55px -28px rgb(0 0 0 / .8); transform: rotate(1.4deg); }
.today-note::after { content: ""; position: absolute; right: 0; bottom: 0; width: 2rem; height: 2rem; background: linear-gradient(135deg, rgb(23 49 53 / .12) 50%, #fffdf2 50%); border-radius: 0 0 1rem; }
.note-pin { position: absolute; top: -.45rem; left: 48%; width: 2.8rem; height: .9rem; background: rgb(125 211 252 / .55); transform: rotate(-4deg); }
.note-label { color: #0f766e; font-size: .73rem; font-weight: 800; letter-spacing: .08em; }
.today-note strong { display: block; margin-top: .55rem; font-size: 1.45rem; letter-spacing: -.03em; line-height: 1.3; }
.note-copy { margin: .8rem 0 1.1rem; color: rgb(23 49 53 / .72); font-size: .78rem; line-height: 1.7; }
.quick-route { position: absolute; z-index: 2; right: 4.3rem; bottom: 3.3rem; display: grid; width: min(19rem, 29%); }
.quick-label { margin-bottom: .4rem; color: rgb(226 245 244 / .5); font-size: .68rem; letter-spacing: .08em; }
.quick-route a { display: grid; grid-template-columns: auto 1fr auto; gap: .6rem; align-items: center; border-top: 1px solid rgb(255 255 255 / .13); padding: .62rem .1rem; color: rgb(238 252 250 / .82); font-size: .78rem; text-decoration: none; }
.quick-route .arrow { opacity: .45; transition: transform 160ms ease, opacity 160ms ease; }
.quick-route a:hover .arrow { opacity: 1; transform: translateX(.25rem); }
.experience-trigger { position: absolute; z-index: 3; bottom: 2.4rem; left: 6.7rem; }
.signal-equation { display: flex; flex-wrap: wrap; justify-content: center; gap: .65rem 1rem; align-items: center; color: var(--ui-text-muted); font-size: .78rem; }
.signal-equation b { color: color-mix(in srgb, var(--pathfy-capability) 58%, var(--ui-text-muted)); font-size: 1rem; }
.signal-equation strong { color: var(--ui-text); }

@media (max-width: 1023px) {
  .route-field { display: grid; min-height: auto; gap: 0; padding: 2rem; }
  .route-line { display: none; }
  .route-stop, .today-note, .quick-route, .experience-trigger { position: relative; inset: auto; width: auto; }
  .route-stop { max-width: 38rem; margin-bottom: 2rem; }
  .today-note { max-width: 32rem; margin: 0 0 2rem 3rem; }
  .quick-route { max-width: 32rem; margin-left: auto; }
  .experience-trigger { width: fit-content; margin-top: 1.5rem; }
}

@media (max-width: 767px) {
  .route-field { border-radius: 1.2rem; padding: 1.5rem 1.1rem; }
  .route-stop { padding-left: 2.9rem; }
  .today-note { margin-left: .8rem; }
  .quick-route { width: 100%; }
}
</style>
