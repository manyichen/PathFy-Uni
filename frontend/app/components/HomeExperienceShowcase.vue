<script setup lang="ts">
const findings = [
  { label: '目标方向', value: '数据分析 / 产品运营 / AI 应用', icon: 'i-lucide-crosshair', tone: '#0e7490' },
  { label: '优先补齐', value: '实践 +18 · 数字 +12 · 协作 +9', icon: 'i-lucide-chart-no-axes-column-increasing', tone: '#2563eb' },
  { label: '下月动作', value: '完成 1 个作品项目，补 2 个 SQL 场景', icon: 'i-lucide-calendar-check', tone: '#b45309' }
]

const timeline = [
  { month: '现在', label: '导入匹配目标', done: true },
  { month: '1 个月', label: '补齐基础证据', done: false },
  { month: '3 个月', label: '形成作品集', done: false },
  { month: '6 个月', label: '投递并复盘', done: false }
]

const marginNotes = [
  '每个结论都能回到岗位或个人材料',
  'AI 摘要与原始依据分开呈现',
  '复盘后自动更新下一轮行动'
]
</script>

<template>
  <section class="report-desk" aria-labelledby="preview-title">
    <header class="desk-heading home-editorial-heading">
      <div class="section-mark home-editorial-mark" aria-hidden="true"><span>03</span><i /></div>
      <div class="home-editorial-title">
        <p class="home-editorial-kicker">把判断留下来</p>
        <h2 id="preview-title">报告不是终点，它是下一次行动的桌面</h2>
      </div>
      <p class="desk-note home-editorial-note">方向从哪里来、差距如何判断、下个月做什么——都留在同一份会持续更新的档案里。</p>
    </header>

    <div class="workroom">
      <article class="report-sheet">
        <div class="sheet-fold" aria-hidden="true" />
        <header class="sheet-header">
          <div>
            <span>PATHFY / 生涯档案</span>
            <strong>成长路线 · 001</strong>
          </div>
          <time>持续更新中</time>
        </header>

        <div class="sheet-title">
          <p>当前目标</p>
          <h3>从“我可能适合”<br>走到“我正在靠近”</h3>
          <span>最近 3 次岗位匹配共同指向：数据理解、业务表达与可展示的实践作品。</span>
        </div>

        <div class="finding-list">
          <div v-for="(item, index) in findings" :key="item.label" class="finding" :style="{ '--finding-tone': item.tone }">
            <span class="finding-index">{{ String(index + 1).padStart(2, '0') }}</span>
            <UIcon :name="item.icon" class="size-5 finding-icon" />
            <div><small>{{ item.label }}</small><strong>{{ item.value }}</strong></div>
          </div>
        </div>

        <div class="sheet-timeline" aria-label="报告复盘时间线">
          <div class="timeline-line" aria-hidden="true" />
          <div v-for="point in timeline" :key="point.month" class="timeline-point" :class="{ done: point.done }">
            <i />
            <span>{{ point.month }}</span>
            <strong>{{ point.label }}</strong>
          </div>
        </div>

        <footer class="sheet-footer">
          <span>来源：岗位样本 × 能力画像 × 匹配记录</span>
          <span>01 / 01</span>
        </footer>
      </article>

      <aside class="desk-margin">
        <div class="pencil-note">
          <span aria-hidden="true">↳</span>
          <p>不是替你决定，<br><strong>而是让决定有迹可循。</strong></p>
        </div>

        <div class="margin-copy">
          <p>这份档案会保留</p>
          <ul>
            <li v-for="note in marginNotes" :key="note">
              <UIcon name="i-lucide-check" class="size-4" />
              <span>{{ note }}</span>
            </li>
          </ul>
        </div>

        <div class="next-slip">
          <span>建议从这里开始</span>
          <strong>先带入一次匹配记录</strong>
          <p>岗位、匹配分和能力差距会自动成为报告的第一组依据。</p>
        </div>

        <UButton to="/report" size="lg" color="primary" trailing-icon="i-lucide-arrow-up-right">
          打开我的生涯档案
        </UButton>
      </aside>
    </div>
  </section>
</template>

<style>
.report-desk { display: grid; gap: 1.5rem; }
.workroom { display: grid; grid-template-columns: minmax(0, 1fr) minmax(16rem, .31fr); gap: clamp(1.5rem, 4vw, 4rem); align-items: center; border-radius: 1.75rem; background: linear-gradient(145deg, color-mix(in srgb, var(--pathfy-capability) 8%, var(--ui-bg-elevated)), var(--ui-bg-elevated)); padding: clamp(1.25rem, 4vw, 3.5rem); }
.report-sheet { position: relative; overflow: hidden; border: 1px solid color-mix(in srgb, #9b8155 26%, var(--ui-border)); border-radius: .25rem .9rem .9rem .25rem; background: linear-gradient(90deg, rgb(141 118 78 / .06) 1px, transparent 1px), linear-gradient(#fffdf5, #faf7ed); background-size: 28px 100%, 100% 100%; padding: clamp(1.5rem, 4vw, 3.25rem); color: #233034; box-shadow: 0 30px 65px -38px rgb(47 39 25 / .55); transform: rotate(-.45deg); }
.report-sheet::before { content: ""; position: absolute; top: 0; bottom: 0; left: 1rem; width: 1px; background: rgb(190 24 93 / .14); }
.sheet-fold { position: absolute; top: 0; right: 0; width: 4rem; height: 4rem; background: linear-gradient(225deg, color-mix(in srgb, var(--pathfy-capability) 13%, #f2ecdb) 49%, #fffdf5 50%); box-shadow: -8px 8px 16px rgb(68 60 44 / .07); }
.sheet-header { display: flex; justify-content: space-between; gap: 1rem; align-items: start; border-bottom: 1px solid rgb(35 48 52 / .18); padding-bottom: 1rem; }
.sheet-header > div { display: grid; gap: .18rem; }
.sheet-header span, .sheet-header time { color: rgb(35 48 52 / .52); font: 700 .65rem/1.4 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .07em; }
.sheet-header strong { font-size: .85rem; }
.sheet-title { padding: clamp(2rem, 5vw, 4rem) 0 2.2rem; }
.sheet-title p { color: #0f766e; font-size: .7rem; font-weight: 850; letter-spacing: .12em; }
.sheet-title h3 { margin-top: .55rem; max-width: 38rem; font-size: clamp(2rem, 4.3vw, 4.1rem); font-weight: 790; letter-spacing: -.06em; line-height: 1.03; }
.sheet-title > span { display: block; max-width: 39rem; margin-top: 1rem; color: rgb(35 48 52 / .62); font-size: .82rem; line-height: 1.75; }
.finding-list { display: grid; border-top: 1px solid rgb(35 48 52 / .18); }
.finding { --finding-tone: #0e7490; display: grid; grid-template-columns: 2rem 2.4rem 1fr; gap: .7rem; align-items: center; border-bottom: 1px solid rgb(35 48 52 / .14); padding: .9rem 0; }
.finding-index { color: rgb(35 48 52 / .35); font: 700 .64rem/1 ui-monospace, SFMono-Regular, Menlo, monospace; }
.finding-icon { color: var(--finding-tone); }
.finding div { display: grid; gap: .12rem; }
.finding small { color: rgb(35 48 52 / .48); font-size: .68rem; }
.finding strong { font-size: .86rem; }
.sheet-timeline { position: relative; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin-top: 2.4rem; }
.timeline-line { position: absolute; top: .28rem; right: 10%; left: 0; height: 1px; background: rgb(35 48 52 / .2); }
.timeline-point { position: relative; display: grid; gap: .22rem; padding-right: .5rem; }
.timeline-point i { z-index: 1; width: .62rem; height: .62rem; border: 2px solid #faf7ed; border-radius: 50%; background: #9ca3af; box-shadow: 0 0 0 1px rgb(35 48 52 / .2); }
.timeline-point.done i { background: #0f766e; }
.timeline-point span { margin-top: .35rem; color: rgb(35 48 52 / .48); font-size: .65rem; }
.timeline-point strong { font-size: .75rem; }
.sheet-footer { display: flex; justify-content: space-between; gap: 1rem; margin-top: 2.5rem; border-top: 1px solid rgb(35 48 52 / .18); padding-top: .8rem; color: rgb(35 48 52 / .42); font: 600 .61rem/1.4 ui-monospace, SFMono-Regular, Menlo, monospace; }
.desk-margin { position: relative; display: grid; gap: 1.5rem; }
.pencil-note { display: flex; gap: .65rem; color: var(--pathfy-capability); font-size: 1.5rem; transform: rotate(1.5deg); }
.pencil-note p { color: var(--ui-text-muted); font-family: ui-rounded, "Comic Sans MS", system-ui, sans-serif; font-size: 1rem; line-height: 1.55; }
.pencil-note strong { color: var(--ui-text); font-weight: 750; }
.margin-copy { border-top: 1px solid var(--ui-border); padding-top: 1.1rem; }
.margin-copy > p { font-size: .78rem; font-weight: 800; }
.margin-copy ul { display: grid; gap: .65rem; margin-top: .75rem; }
.margin-copy li { display: flex; gap: .5rem; align-items: start; color: var(--ui-text-muted); font-size: .77rem; line-height: 1.5; }
.margin-copy li svg { flex: 0 0 auto; margin-top: .12rem; color: var(--pathfy-capability); }
.next-slip { position: relative; border-radius: .25rem; background: #f3df99; padding: 1.25rem; color: #382f1e; box-shadow: 0 18px 35px -27px rgb(67 49 11 / .65); transform: rotate(-1.4deg); }
.next-slip::before { content: ""; position: absolute; top: -.35rem; left: 42%; width: 3.3rem; height: .7rem; background: rgb(255 255 255 / .5); transform: rotate(3deg); }
.next-slip span { font-size: .66rem; font-weight: 800; letter-spacing: .08em; }
.next-slip strong { display: block; margin-top: .3rem; font-size: .95rem; }
.next-slip p { margin-top: .45rem; color: #51462e; font-size: .72rem; font-weight: 500; line-height: 1.6; }

@media (max-width: 1023px) {
  .workroom { grid-template-columns: 1fr; }
  .desk-margin { grid-template-columns: repeat(2, minmax(0, 1fr)); align-items: start; }
  .desk-margin > :last-child { justify-self: start; }
}

@media (max-width: 767px) {
  .workroom { border-radius: 1.2rem; padding: 1rem; }
  .report-sheet { padding: 1.5rem 1rem 1.5rem 1.6rem; transform: none; }
  .sheet-title h3 { font-size: 2.1rem; }
  .sheet-timeline { grid-template-columns: repeat(2, 1fr); gap: 1.2rem 0; }
  .timeline-line { display: none; }
  .desk-margin { grid-template-columns: 1fr; padding: .5rem; }
}
</style>
