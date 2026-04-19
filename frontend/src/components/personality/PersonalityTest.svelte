<script lang="ts">
import { onMount } from 'svelte';
import {
  clearPersonalityTestCache,
  loadPersonalityTestCache,
  savePersonalityTestCache,
} from '../../lib/personality-test-cache';

interface Question {
  id: number;
  question_text: string;
  option_a: string;
  option_b: string;
  dimension: string;
  option_a_type: string;
  option_b_type: string;
}

interface Answer {
  question_id: number;
  user_choice: string;
}

interface DimensionAnalysis {
  dimension: string;
  type: string;
  name: string;
  description: string;
  characteristics: string[];
  work_preference: string[];
  growth_suggestions: string[];
}

interface CompleteAnalysis {
  type: string;
  name: string;
  summary: string;
  core_strengths: string[];
  career_tendencies: string[];
  workplace_relationships: string[];
  development_areas: string[];
  stress_response: string;
}

interface JobRecommendation {
  recommended_jobs: string[];
  career_advice: string;
}

interface PersonalityResult {
  mbti_type: string;
  personality_analysis: string;
  recommended_jobs: string[];
  dimension_analysis: DimensionAnalysis[];
  complete_analysis: CompleteAnalysis;
  job_recommendations: JobRecommendation;
  profile_id: number;
}

let questions: Question[] = [];
let currentQuestionIndex = 0;
let answers: Answer[] = [];
let isLoading = true;
let isSubmitting = false;
let showResults = false;
let showStartScreen = true;
let personalityProfile: PersonalityResult | null = null;
let errorMessage = '';
let animationComplete = false;

async function loadQuestions() {
  try {
    const response = await fetch('http://localhost:5000/api/personality/questions');
    const data = await response.json();
    if (data.code === 200) {
      questions = data.data;
      const cached = loadPersonalityTestCache(questions.length);
      if (cached) {
        showStartScreen = cached.showStartScreen;
        showResults = cached.showResults;
        currentQuestionIndex = Math.min(
          Math.max(0, cached.currentQuestionIndex),
          Math.max(0, questions.length - 1),
        );
        const idSet = new Set(questions.map((q) => q.id));
        answers = (cached.answers || []).filter((a) => idSet.has(a.question_id));
        personalityProfile = (cached.personalityProfile || null) as PersonalityResult | null;
        if (!showStartScreen) {
          animationComplete = true;
        }
        if (showResults && !personalityProfile) {
          showResults = false;
        }
      }
    } else {
      throw new Error(data.msg || '加载题目失败');
    }
  } catch (error) {
    console.error('加载题目失败:', error);
    errorMessage = '加载题目失败，请稍后重试';
    alert('加载题目失败，请稍后重试');
  } finally {
    isLoading = false;
  }
}

function startTest() {
  showStartScreen = false;
  animationComplete = true;
}

async function submitAnswers() {
  if (answers.length < questions.length) {
    alert('请完成所有题目');
    return;
  }

  isSubmitting = true;
  try {
    const response = await fetch('http://localhost:5000/api/personality/submit', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        user_id: localStorage.getItem('user_id') || '1',
        answers
      })
    });

    const data = await response.json();
    if (data.code === 200) {
      personalityProfile = data.data as PersonalityResult;
      showResults = true;
    } else {
      throw new Error(data.msg || '提交答案失败');
    }
  } catch (error) {
    console.error('提交答案失败:', error);
    alert('提交答案失败，请稍后重试');
  } finally {
    isSubmitting = false;
  }
}

function selectAnswer(questionId: number, choice: string) {
  const existingAnswerIndex = answers.findIndex(a => a.question_id === questionId);
  if (existingAnswerIndex !== -1) {
    answers[existingAnswerIndex].user_choice = choice;
    answers = answers;
  } else {
    answers = [...answers, { question_id: questionId, user_choice: choice }];
  }
}

function nextQuestion() {
  if (currentQuestionIndex < questions.length - 1) {
    currentQuestionIndex++;
  }
}

function prevQuestion() {
  if (currentQuestionIndex > 0) {
    currentQuestionIndex--;
  }
}

function resetTest() {
  if (
    !showResults &&
    !showStartScreen &&
    answers.length > 0 &&
    !confirm('确定重新开始？当前答题进度将被清空。')
  ) {
    return;
  }
  clearPersonalityTestCache();
  showResults = false;
  showStartScreen = true;
  currentQuestionIndex = 0;
  answers = [];
  personalityProfile = null;
  animationComplete = false;
}

$: if (!isLoading && questions.length > 0) {
  savePersonalityTestCache({
    questionCount: questions.length,
    showStartScreen,
    showResults,
    currentQuestionIndex,
    answers,
    personalityProfile,
  });
}

onMount(() => {
  loadQuestions();
});
</script>

<div class="space-y-8">
  {#if isLoading}
    <div
      class="flex min-h-[14rem] items-center justify-center rounded-xl border border-black/5 bg-[var(--btn-regular-bg)] py-16 dark:border-white/10 dark:bg-[var(--btn-regular-bg)]"
    >
      <div
        class="h-12 w-12 animate-spin rounded-full border-2 border-black/10 border-t-[var(--primary)] dark:border-white/15"
      ></div>
    </div>
  {:else if errorMessage}
    <div
      class="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-800 dark:border-red-500/25 dark:bg-red-500/10 dark:text-red-200"
    >
      {errorMessage}
    </div>
  {:else if showStartScreen}
    <!-- 开始测试界面 -->
    <div
      class="relative overflow-hidden rounded-xl border border-black/10 bg-[var(--btn-regular-bg)] dark:border-white/10"
    >
      <div class="relative z-10 p-8 md:p-12">
        <div class="max-w-3xl mx-auto text-center space-y-8">
          <!-- 标题部分 -->
          <div class="space-y-4 animate-fadeIn">
            <div
              class="inline-flex items-center gap-2 rounded-full border border-black/10 bg-background/95 px-4 py-2 backdrop-blur-sm dark:border-white/10 dark:bg-background/80"
            >
              <span class="text-2xl">🧠</span>
              <span class="text-sm font-medium text-black dark:text-white">MBTI 性格测试</span>
            </div>

            <h1 class="text-4xl font-bold text-black dark:text-white md:text-5xl">
              探索你的性格密码
            </h1>

            <p class="text-lg leading-relaxed text-75">
              用50道精心设计的题目，发现真实的你。了解你的优势、工作偏好和成长方向，
              为职业规划提供科学参考。
            </p>
          </div>

          <!-- 特性卡片 -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4 animate-slideUp" style="animation-delay: 0.3s;">
            <div
              class="rounded-xl border border-black/10 bg-background/95 p-5 shadow-sm backdrop-blur-sm dark:border-white/10 dark:bg-background/90"
            >
              <div
                class="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl border border-black/10 bg-background dark:border-white/10"
              >
                <span class="text-2xl opacity-90">📊</span>
              </div>
              <h3 class="mb-1 font-semibold text-black dark:text-white">科学维度</h3>
              <p class="text-sm text-75">4 维度深度分析</p>
            </div>

            <div
              class="rounded-xl border border-black/10 bg-background/95 p-5 shadow-sm backdrop-blur-sm dark:border-white/10 dark:bg-background/90"
            >
              <div
                class="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl border border-black/10 bg-background dark:border-white/10"
              >
                <span class="text-2xl opacity-90">💼</span>
              </div>
              <h3 class="mb-1 font-semibold text-black dark:text-white">职业建议</h3>
              <p class="text-sm text-75">个性化岗位推荐</p>
            </div>

            <div
              class="rounded-xl border border-black/10 bg-background/95 p-5 shadow-sm backdrop-blur-sm dark:border-white/10 dark:bg-background/90"
            >
              <div
                class="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl border border-black/10 bg-background dark:border-white/10"
              >
                <span class="text-2xl opacity-90">🚀</span>
              </div>
              <h3 class="mb-1 font-semibold text-black dark:text-white">快速完成</h3>
              <p class="text-sm text-75">仅需 5–10 分钟</p>
            </div>
          </div>

          <!-- 开始按钮 -->
          <div class="animate-slideUp" style="animation-delay: 0.6s;">
            <button
              on:click={startTest}
              class="group inline-flex items-center gap-3 rounded-2xl bg-[var(--primary)] px-8 py-4 text-lg font-semibold text-white shadow-md transition hover:opacity-95 active:scale-[0.98]"
            >
              <span>开始测试</span>
              <span class="transition-transform duration-300 group-hover:translate-x-1">→</span>
            </button>

            <p class="mt-4 text-sm text-75">您的测试结果将被安全保存</p>
          </div>

          <!-- 进度提示 -->
          <div class="animate-slideUp" style="animation-delay: 0.9s;">
            <div class="flex items-center justify-center gap-2 text-sm text-75">
              <span>共 {questions.length} 题</span>
              <span>•</span>
              <span>每题只需2个选择</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  {:else if showResults && personalityProfile}
    <!-- 详细结果展示 -->
    <div class="space-y-8">
      <!-- MBTI类型概览 -->
      <div
        class="rounded-2xl border border-black/10 bg-[var(--btn-regular-bg)] p-6 shadow-sm dark:border-white/10 md:p-8"
      >
        <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 class="text-2xl font-bold text-black dark:text-white">您的 MBTI 性格类型</h2>
          <div class="flex items-center gap-2">
            <span class="text-4xl font-bold text-[var(--primary)]">{personalityProfile.mbti_type}</span>
            <span class="text-lg text-75">（{personalityProfile.complete_analysis?.name || ''}）</span>
          </div>
        </div>
        <p class="text-sm leading-relaxed text-75">
          {personalityProfile.complete_analysis?.summary || ''}
        </p>
      </div>

      <!-- 四维度详细分析 -->
      <div
        class="rounded-2xl border border-black/10 bg-background p-6 shadow-sm dark:border-white/10 md:p-8"
      >
        <h3 class="mb-4 text-lg font-semibold text-black dark:text-white">🔬 四维度深度分析</h3>
        <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
          {#each personalityProfile.dimension_analysis || [] as dim}
            <div
              class="rounded-xl border border-black/10 bg-[var(--btn-regular-bg)] p-4 dark:border-white/10"
            >
              <div class="flex items-center justify-between mb-2">
                <h4 class="text-sm font-semibold text-black dark:text-white">{dim.dimension}</h4>
                <span class="rounded-full bg-[var(--primary)]/15 px-3 py-1 text-sm font-bold text-[var(--primary)]">{dim.type}</span>
              </div>
              <p class="mb-2 text-sm font-medium text-[var(--primary)]">{dim.name}</p>
              <p class="mb-3 text-xs text-75">{dim.description}</p>
              
              <div class="mb-2">
                <p class="mb-1 text-xs font-medium text-black dark:text-white">特征：</p>
                <ul class="space-y-1">
                  {#each dim.characteristics || [] as char}
                    <li class="flex items-start text-xs text-75">
                      <span class="mr-1 text-[var(--primary)]">✓</span>
                      {char}
                    </li>
                  {/each}
                </ul>
              </div>
              
              <div class="mb-2">
                <p class="mb-1 text-xs font-medium text-black dark:text-white">工作偏好：</p>
                <ul class="space-y-1">
                  {#each dim.work_preference || [] as pref}
                    <li class="flex items-start text-xs text-75">
                      <span class="mr-1 text-[var(--primary)]">•</span>
                      {pref}
                    </li>
                  {/each}
                </ul>
              </div>
              
              <div>
                <p class="mb-1 text-xs font-medium text-black dark:text-white">发展建议：</p>
                <ul class="space-y-1">
                  {#each dim.growth_suggestions || [] as suggestion}
                    <li class="flex items-start text-xs text-75">
                      <span class="mr-1 text-[var(--primary)]">→</span>
                      {suggestion}
                    </li>
                  {/each}
                </ul>
              </div>
            </div>
          {/each}
        </div>
      </div>

      <!-- 完整性格分析 -->
      <div
        class="rounded-2xl border border-black/10 bg-background p-6 shadow-sm dark:border-white/10 md:p-8"
      >
        <h3 class="mb-4 text-lg font-semibold text-black dark:text-white">📋 完整性格分析报告</h3>
        
        <!-- 核心优势 -->
        <div class="mb-6">
          <h4 class="mb-2 text-sm font-medium text-black dark:text-white">💪 核心优势</h4>
          <div class="grid grid-cols-1 gap-2 md:grid-cols-2">
            {#each personalityProfile.complete_analysis?.core_strengths || [] as strength}
              <div class="flex items-center rounded-lg border border-black/10 bg-[var(--btn-regular-bg)] px-3 py-2 dark:border-white/10">
                <span class="mr-2 text-[var(--primary)]">★</span>
                <span class="text-sm text-black dark:text-white">{strength}</span>
              </div>
            {/each}
          </div>
        </div>

        <!-- 职业倾向 -->
        <div class="mb-6">
          <h4 class="mb-2 text-sm font-medium text-black dark:text-white">💼 职业倾向</h4>
          <div class="grid grid-cols-1 gap-2 md:grid-cols-2">
            {#each personalityProfile.complete_analysis?.career_tendencies || [] as tendency}
              <div class="flex items-center rounded-lg border border-black/10 bg-[var(--btn-regular-bg)] px-3 py-2 dark:border-white/10">
                <span class="mr-2 text-[var(--primary)]">•</span>
                <span class="text-sm text-black dark:text-white">{tendency}</span>
              </div>
            {/each}
          </div>
        </div>

        <!-- 职场人际关系 -->
        <div class="mb-6">
          <h4 class="mb-2 text-sm font-medium text-black dark:text-white">🤝 职场人际关系</h4>
          <div class="grid grid-cols-1 gap-2 md:grid-cols-2">
            {#each personalityProfile.complete_analysis?.workplace_relationships || [] as relationship}
              <div class="flex items-center rounded-lg border border-black/10 bg-[var(--btn-regular-bg)] px-3 py-2 dark:border-white/10">
                <span class="mr-2 text-[var(--primary)]">♦</span>
                <span class="text-sm text-black dark:text-white">{relationship}</span>
              </div>
            {/each}
          </div>
        </div>

        <!-- 发展建议 -->
        <div class="mb-6">
          <h4 class="mb-2 text-sm font-medium text-black dark:text-white">🌱 个人发展建议</h4>
          <div class="grid grid-cols-1 gap-2 md:grid-cols-2">
            {#each personalityProfile.complete_analysis?.development_areas || [] as area}
              <div class="flex items-center rounded-lg border border-black/10 bg-[var(--btn-regular-bg)] px-3 py-2 dark:border-white/10">
                <span class="mr-2 text-[var(--primary)]">→</span>
                <span class="text-sm text-black dark:text-white">{area}</span>
              </div>
            {/each}
          </div>
        </div>

        <!-- 压力应对 -->
        <div class="rounded-lg border border-black/10 bg-[var(--btn-regular-bg)] p-4 dark:border-white/10">
          <h4 class="mb-2 text-sm font-medium text-black dark:text-white">⚠️ 压力应对方式</h4>
          <p class="text-sm text-75">{personalityProfile.complete_analysis?.stress_response || ''}</p>
        </div>
      </div>

      <!-- 岗位推荐 -->
      <div
        class="rounded-2xl border border-black/10 bg-background p-6 shadow-sm dark:border-white/10 md:p-8"
      >
        <h3 class="mb-4 text-lg font-semibold text-black dark:text-white">🎯 推荐岗位</h3>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          {#each personalityProfile.recommended_jobs || [] as job}
            <div class="rounded-lg border border-[var(--primary)] bg-[var(--primary)]/10 px-3 py-2 text-center">
              <span class="text-sm font-medium text-[var(--primary)]">{job}</span>
            </div>
          {/each}
        </div>
        <div class="rounded-lg border border-black/10 bg-[var(--btn-regular-bg)] p-4 dark:border-white/10">
          <h4 class="mb-2 text-sm font-medium text-black dark:text-white">💡 职业发展建议</h4>
          <p class="text-sm text-75">{personalityProfile.job_recommendations?.career_advice || ''}</p>
        </div>
      </div>

      <!-- 综合分析报告 -->
      <div
        class="rounded-2xl border border-black/10 bg-background p-6 shadow-sm dark:border-white/10 md:p-8"
      >
        <h3 class="mb-4 text-lg font-semibold text-black dark:text-white">📊 综合分析报告</h3>
        <div
          class="rounded-xl border border-black/10 bg-[var(--btn-regular-bg)] p-4 dark:border-white/10"
        >
          <p class="whitespace-pre-line text-sm leading-relaxed text-75">{personalityProfile.personality_analysis || ''}</p>
        </div>
      </div>

      <!-- 重新测试：清空本地缓存并回到欢迎页 -->
      <div class="flex justify-center">
        <button
          type="button"
          on:click={resetTest}
          class="rounded-2xl bg-[var(--primary)] px-8 py-3 text-sm font-semibold text-white shadow-md transition hover:opacity-95 focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/40"
        >
          重新测试
        </button>
      </div>
    </div>
  {:else}
    <!-- 答题界面 -->
    <div class="space-y-8">
      <div
        class="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-black/10 bg-background px-4 py-4 shadow-sm dark:border-white/10 md:px-6"
      >
        <div class="flex min-w-0 flex-1 flex-wrap items-center gap-3 md:gap-4">
          <h2 class="text-lg font-semibold text-black dark:text-white">
            问题 {currentQuestionIndex + 1}/{questions.length}
          </h2>
          <div class="min-w-[8rem] flex-1 basis-full sm:basis-auto md:mx-2">
            <div class="h-2 rounded-full bg-black/10 dark:bg-white/10">
              <div
                class="h-2 rounded-full bg-[var(--primary)] transition-all duration-300"
                style="width: {((currentQuestionIndex + 1) / questions.length) * 100}%"
              ></div>
            </div>
          </div>
          <span class="text-sm tabular-nums text-75">
            {Math.round(((currentQuestionIndex + 1) / questions.length) * 100)}%
          </span>
        </div>
        <button
          type="button"
          on:click={resetTest}
          class="shrink-0 rounded-xl border border-black/10 bg-[var(--btn-regular-bg)] px-3 py-2 text-sm font-medium text-black transition hover:bg-black/[0.03] dark:border-white/10 dark:text-white dark:hover:bg-white/5"
        >
          重新测试
        </button>
      </div>

      {#if questions.length > 0}
        <div
          class="rounded-2xl border border-black/10 bg-background p-6 shadow-sm dark:border-white/10 md:p-8"
        >
          <h3 class="mb-4 text-base font-medium text-black dark:text-white">
            {questions[currentQuestionIndex].question_text}
          </h3>
          <div class="space-y-3">
            <button
              on:click={() => selectAnswer(questions[currentQuestionIndex].id, 'A')}
              class={`w-full rounded-xl border-2 px-4 py-3 text-left text-sm transition-all duration-200 ${answers.find(a => a.question_id === questions[currentQuestionIndex].id)?.user_choice === 'A'
                ? 'border-[var(--primary)] bg-[var(--primary)]/10 text-black shadow-sm ring-2 ring-[var(--primary)]/30 dark:text-white'
                : 'border-black/10 bg-[var(--btn-regular-bg)] text-black hover:border-black/20 hover:shadow-sm dark:border-white/10 dark:text-white dark:hover:bg-white/5'}
              `}
            >
              <span class="font-bold mr-2">A</span>
              {questions[currentQuestionIndex].option_a}
            </button>
            <button
              on:click={() => selectAnswer(questions[currentQuestionIndex].id, 'B')}
              class={`w-full rounded-xl border-2 px-4 py-3 text-left text-sm transition-all duration-200 ${answers.find(a => a.question_id === questions[currentQuestionIndex].id)?.user_choice === 'B'
                ? 'border-[var(--primary)] bg-[var(--primary)]/10 text-black shadow-sm ring-2 ring-[var(--primary)]/30 dark:text-white'
                : 'border-black/10 bg-[var(--btn-regular-bg)] text-black hover:border-black/20 hover:shadow-sm dark:border-white/10 dark:text-white dark:hover:bg-white/5'}
              `}
            >
              <span class="font-bold mr-2">B</span>
              {questions[currentQuestionIndex].option_b}
            </button>
          </div>
        </div>

        <div class="flex flex-wrap justify-between gap-3">
          <button
            on:click={prevQuestion}
            disabled={currentQuestionIndex === 0}
            class="rounded-xl border border-black/10 bg-[var(--btn-regular-bg)] px-4 py-2.5 text-sm font-medium text-black hover:bg-black/[0.03] disabled:cursor-not-allowed disabled:opacity-50 dark:border-white/10 dark:text-white dark:hover:bg-white/5"
          >
            上一题
          </button>
          {#if currentQuestionIndex === questions.length - 1}
            <button
              on:click={submitAnswers}
              disabled={isSubmitting || !answers.find(a => a.question_id === questions[currentQuestionIndex].id)}
              class="rounded-xl bg-[var(--primary)] px-5 py-2.5 text-sm font-semibold text-white shadow-md transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/40"
            >
              {isSubmitting ? '提交中...' : '提交答案'}
            </button>
          {:else}
            <button
              on:click={nextQuestion}
              disabled={!answers.find(a => a.question_id === questions[currentQuestionIndex].id)}
              class="rounded-xl bg-[var(--primary)] px-5 py-2.5 text-sm font-semibold text-white shadow-md transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/40"
            >
              下一题
            </button>
          {/if}
        </div>

        <!-- 已答题目进度 -->
        <div
          class="rounded-2xl border border-black/10 bg-background p-4 shadow-sm dark:border-white/10 md:p-5"
        >
          <p class="mb-2 text-sm text-75">已答题目：{answers.length}/{questions.length}</p>
          <div class="flex flex-wrap gap-1">
            {#each questions as q, i}
              <div 
                class={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium ${
                  answers.find(a => a.question_id === q.id)
                    ? 'bg-[var(--primary)] text-white shadow-sm'
                    : 'bg-black/10 text-75 dark:bg-white/10'
                }`}
              >
                {i + 1}
              </div>
            {/each}
          </div>
        </div>
      {:else}
        <div class="rounded-xl border border-black/10 bg-background p-4 text-sm text-75 dark:border-white/10">
          没有加载到测试题目，请刷新页面重试。
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
.animate-fadeIn {
  animation: fadeIn 0.6s ease-out forwards;
}
.animate-slideUp {
  animation: slideUp 0.6s ease-out forwards;
  opacity: 0;
}
</style>
