<script lang="ts">
import { onMount, onDestroy } from 'svelte';

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
      personalityProfile = data.data;
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
  } else {
    answers.push({ question_id: questionId, user_choice: choice });
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
  showResults = false;
  currentQuestionIndex = 0;
  answers = [];
  personalityProfile = null;
}

onMount(() => {
  loadQuestions();
});
</script>

<div class="space-y-6">
  {#if isLoading}
    <div class="flex items-center justify-center py-16">
      <div class="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
    </div>
  {:else if errorMessage}
    <div class="p-4 text-red-600 dark:text-red-400">{errorMessage}</div>
  {:else if showStartScreen}
    <!-- 开始测试界面 -->
    <div class="relative overflow-hidden rounded-2xl border border-black/10 bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50 dark:border-white/10 dark:from-blue-900/20 dark:via-purple-900/20 dark:to-pink-900/20">
      <div class="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none">
        <div class="absolute -top-20 -left-20 w-40 h-40 bg-blue-400/20 rounded-full blur-3xl animate-pulse"></div>
        <div class="absolute top-40 right-10 w-32 h-32 bg-purple-400/20 rounded-full blur-3xl animate-pulse" style="animation-delay: 1s;"></div>
        <div class="absolute bottom-20 left-1/3 w-28 h-28 bg-pink-400/20 rounded-full blur-3xl animate-pulse" style="animation-delay: 2s;"></div>
      </div>
      
      <div class="relative z-10 p-8 md:p-12">
        <div class="max-w-3xl mx-auto text-center space-y-8">
          <!-- 标题部分 -->
          <div class="space-y-4 animate-fadeIn">
            <div class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/70 dark:bg-gray-800/70 backdrop-blur-sm border border-black/10 dark:border-white/10">
              <span class="text-2xl">🧠</span>
              <span class="text-sm font-medium text-gray-700 dark:text-gray-300">MBTI 性格测试</span>
            </div>
            
            <h1 class="text-4xl md:text-5xl font-bold bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">
              探索你的性格密码
            </h1>
            
            <p class="text-lg text-gray-600 dark:text-gray-400 leading-relaxed">
              用50道精心设计的题目，发现真实的你。了解你的优势、工作偏好和成长方向，
              为职业规划提供科学参考。
            </p>
          </div>

          <!-- 特性卡片 -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4 animate-slideUp" style="animation-delay: 0.3s;">
            <div class="bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm rounded-xl p-5 border border-black/10 dark:border-white/10">
              <div class="w-12 h-12 bg-gradient-to-br from-blue-400 to-blue-600 rounded-xl flex items-center justify-center mb-3 mx-auto">
                <span class="text-2xl">📊</span>
              </div>
              <h3 class="font-semibold text-gray-800 dark:text-gray-200 mb-1">科学维度</h3>
              <p class="text-sm text-gray-600 dark:text-gray-400">4维度深度分析</p>
            </div>

            <div class="bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm rounded-xl p-5 border border-black/10 dark:border-white/10">
              <div class="w-12 h-12 bg-gradient-to-br from-purple-400 to-purple-600 rounded-xl flex items-center justify-center mb-3 mx-auto">
                <span class="text-2xl">💼</span>
              </div>
              <h3 class="font-semibold text-gray-800 dark:text-gray-200 mb-1">职业建议</h3>
              <p class="text-sm text-gray-600 dark:text-gray-400">个性化岗位推荐</p>
            </div>

            <div class="bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm rounded-xl p-5 border border-black/10 dark:border-white/10">
              <div class="w-12 h-12 bg-gradient-to-br from-pink-400 to-pink-600 rounded-xl flex items-center justify-center mb-3 mx-auto">
                <span class="text-2xl">🚀</span>
              </div>
              <h3 class="font-semibold text-gray-800 dark:text-gray-200 mb-1">快速完成</h3>
              <p class="text-sm text-gray-600 dark:text-gray-400">仅需5-10分钟</p>
            </div>
          </div>

          <!-- 开始按钮 -->
          <div class="animate-slideUp" style="animation-delay: 0.6s;">
            <button
              on:click={startTest}
              class="group relative inline-flex items-center gap-3 px-8 py-4 bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 rounded-xl text-white font-semibold text-lg shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-[1.02] active:scale-[0.98]"
            >
              <span class="relative z-10">开始测试</span>
              <span class="relative z-10 group-hover:translate-x-1 transition-transform duration-300">
                →
              </span>
              <div class="absolute inset-0 rounded-xl bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
            </button>
            
            <p class="mt-4 text-sm text-gray-500 dark:text-gray-400">
              您的测试结果将被安全保存
            </p>
          </div>

          <!-- 进度提示 -->
          <div class="animate-slideUp" style="animation-delay: 0.9s;">
            <div class="flex items-center justify-center gap-2 text-sm text-gray-500 dark:text-gray-400">
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
    <div class="space-y-6">
      <!-- MBTI类型概览 -->
      <div class="rounded-2xl border bg-gradient-to-r from-blue-50 to-purple-50 p-6 dark:border-blue-900/30 dark:from-blue-900/10 dark:to-purple-900/10">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-2xl font-bold text-black dark:text-white">您的MBTI性格类型</h2>
          <div class="flex items-center gap-2">
            <span class="text-4xl font-bold text-[var(--primary)]">{personalityProfile.mbti_type}</span>
            <span class="text-lg text-gray-600 dark:text-gray-400">（{personalityProfile.complete_analysis?.name || ''}）</span>
          </div>
        </div>
        <p class="text-sm leading-relaxed text-gray-700 dark:text-gray-300">
          {personalityProfile.complete_analysis?.summary || ''}
        </p>
      </div>

      <!-- 四维度详细分析 -->
      <div class="rounded-2xl border bg-background p-6 shadow-sm">
        <h3 class="mb-4 text-lg font-semibold text-black dark:text-white">🔬 四维度深度分析</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          {#each personalityProfile.dimension_analysis || [] as dim}
            <div class="rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800/50">
              <div class="flex items-center justify-between mb-2">
                <h4 class="text-sm font-semibold text-gray-800 dark:text-gray-200">{dim.dimension}</h4>
                <span class="rounded-full bg-blue-100 px-3 py-1 text-sm font-bold text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">{dim.type}</span>
              </div>
              <p class="text-sm font-medium text-blue-600 dark:text-blue-400 mb-2">{dim.name}</p>
              <p class="text-xs text-gray-600 dark:text-gray-400 mb-3">{dim.description}</p>
              
              <div class="mb-2">
                <p class="text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">特征：</p>
                <ul class="space-y-1">
                  {#each dim.characteristics || [] as char}
                    <li class="flex items-start text-xs text-gray-600 dark:text-gray-400">
                      <span class="mr-1 text-green-500">✓</span>
                      {char}
                    </li>
                  {/each}
                </ul>
              </div>
              
              <div class="mb-2">
                <p class="text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">工作偏好：</p>
                <ul class="space-y-1">
                  {#each dim.work_preference || [] as pref}
                    <li class="flex items-start text-xs text-gray-600 dark:text-gray-400">
                      <span class="mr-1 text-blue-500">•</span>
                      {pref}
                    </li>
                  {/each}
                </ul>
              </div>
              
              <div>
                <p class="text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">发展建议：</p>
                <ul class="space-y-1">
                  {#each dim.growth_suggestions || [] as suggestion}
                    <li class="flex items-start text-xs text-orange-600 dark:text-orange-400">
                      <span class="mr-1">→</span>
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
      <div class="rounded-2xl border bg-background p-6 shadow-sm">
        <h3 class="mb-4 text-lg font-semibold text-black dark:text-white">📋 完整性格分析报告</h3>
        
        <!-- 核心优势 -->
        <div class="mb-6">
          <h4 class="text-sm font-medium text-green-700 dark:text-green-400 mb-2">💪 核心优势</h4>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
            {#each personalityProfile.complete_analysis?.core_strengths || [] as strength}
              <div class="flex items-center rounded-lg border border-green-200 bg-green-50 px-3 py-2 dark:border-green-900/30 dark:bg-green-900/10">
                <span class="mr-2 text-green-500">★</span>
                <span class="text-sm text-green-800 dark:text-green-300">{strength}</span>
              </div>
            {/each}
          </div>
        </div>

        <!-- 职业倾向 -->
        <div class="mb-6">
          <h4 class="text-sm font-medium text-blue-700 dark:text-blue-400 mb-2">💼 职业倾向</h4>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
            {#each personalityProfile.complete_analysis?.career_tendencies || [] as tendency}
              <div class="flex items-center rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 dark:border-blue-900/30 dark:bg-blue-900/10">
                <span class="mr-2 text-blue-500">•</span>
                <span class="text-sm text-blue-800 dark:text-blue-300">{tendency}</span>
              </div>
            {/each}
          </div>
        </div>

        <!-- 职场人际关系 -->
        <div class="mb-6">
          <h4 class="text-sm font-medium text-purple-700 dark:text-purple-400 mb-2">🤝 职场人际关系</h4>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
            {#each personalityProfile.complete_analysis?.workplace_relationships || [] as relationship}
              <div class="flex items-center rounded-lg border border-purple-200 bg-purple-50 px-3 py-2 dark:border-purple-900/30 dark:bg-purple-900/10">
                <span class="mr-2 text-purple-500">♦</span>
                <span class="text-sm text-purple-800 dark:text-purple-300">{relationship}</span>
              </div>
            {/each}
          </div>
        </div>

        <!-- 发展建议 -->
        <div class="mb-6">
          <h4 class="text-sm font-medium text-orange-700 dark:text-orange-400 mb-2">🌱 个人发展建议</h4>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
            {#each personalityProfile.complete_analysis?.development_areas || [] as area}
              <div class="flex items-center rounded-lg border border-orange-200 bg-orange-50 px-3 py-2 dark:border-orange-900/30 dark:bg-orange-900/10">
                <span class="mr-2 text-orange-500">→</span>
                <span class="text-sm text-orange-800 dark:text-orange-300">{area}</span>
              </div>
            {/each}
          </div>
        </div>

        <!-- 压力应对 -->
        <div class="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900/30 dark:bg-red-900/10">
          <h4 class="text-sm font-medium text-red-700 dark:text-red-400 mb-2">⚠️ 压力应对方式</h4>
          <p class="text-sm text-red-800 dark:text-red-300">{personalityProfile.complete_analysis?.stress_response || ''}</p>
        </div>
      </div>

      <!-- 岗位推荐 -->
      <div class="rounded-2xl border bg-background p-6 shadow-sm">
        <h3 class="mb-4 text-lg font-semibold text-black dark:text-white">🎯 推荐岗位</h3>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          {#each personalityProfile.recommended_jobs || [] as job}
            <div class="rounded-lg border border-[var(--primary)] bg-[var(--primary)]/10 px-3 py-2 text-center">
              <span class="text-sm font-medium text-[var(--primary)]">{job}</span>
            </div>
          {/each}
        </div>
        <div class="rounded-lg border border-green-200 bg-green-50 p-4 dark:border-green-900/30 dark:bg-green-900/10">
          <h4 class="text-sm font-medium text-green-700 dark:text-green-400 mb-2">💡 职业发展建议</h4>
          <p class="text-sm text-green-800 dark:text-green-300">{personalityProfile.job_recommendations?.career_advice || ''}</p>
        </div>
      </div>

      <!-- 综合分析报告 -->
      <div class="rounded-2xl border bg-background p-6 shadow-sm">
        <h3 class="mb-4 text-lg font-semibold text-black dark:text-white">📊 综合分析报告</h3>
        <div class="rounded-lg border bg-gradient-to-r from-gray-50 to-gray-100 p-4 dark:border-gray-700 dark:from-gray-800/50 dark:to-gray-700/50">
          <p class="text-sm leading-relaxed text-gray-700 dark:text-gray-300 whitespace-pre-line">{personalityProfile.personality_analysis || ''}</p>
        </div>
      </div>

      <!-- 重新测试按钮 -->
      <div class="flex justify-center">
        <button
          on:click={resetTest}
          class="rounded-lg bg-[var(--primary)] px-6 py-3 text-sm font-medium text-white hover:bg-[var(--primary)]/90 focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/50"
        >
          重新测试
        </button>
      </div>
    </div>
  {:else}
    <!-- 答题界面 -->
    <div class="space-y-6">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold text-black dark:text-white">问题 {currentQuestionIndex + 1}/{questions.length}</h2>
        <div class="flex-1 mx-4">
          <div class="h-2 bg-gray-200 rounded-full dark:bg-gray-700">
            <div
              class="h-2 bg-[var(--primary)] rounded-full transition-all duration-300"
              style="width: {((currentQuestionIndex + 1) / questions.length) * 100}%"
            ></div>
          </div>
        </div>
        <span class="text-sm text-gray-500 dark:text-gray-400">
          {Math.round(((currentQuestionIndex + 1) / questions.length) * 100)}%
        </span>
      </div>

      {#if questions.length > 0}
        <div class="rounded-lg border bg-gray-50 p-6 dark:border-gray-700 dark:bg-gray-800/50">
          <h3 class="mb-4 text-base font-medium text-black dark:text-white">
            {questions[currentQuestionIndex].question_text}
          </h3>
          <div class="space-y-3">
            <button
              on:click={() => selectAnswer(questions[currentQuestionIndex].id, 'A')}
              class={`w-full rounded-lg px-4 py-3 text-left text-sm transition-all duration-200 hover:shadow-md ${answers.find(a => a.question_id === questions[currentQuestionIndex].id)?.user_choice === 'A'
                ? 'bg-blue-100 border-2 border-blue-500 text-blue-800 dark:bg-blue-900/30 dark:border-blue-500 dark:text-blue-300'
                : 'bg-white border-2 border-gray-300 text-gray-700 hover:bg-gray-50 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-700'}
              `}
            >
              <span class="font-bold mr-2">A</span>
              {questions[currentQuestionIndex].option_a}
            </button>
            <button
              on:click={() => selectAnswer(questions[currentQuestionIndex].id, 'B')}
              class={`w-full rounded-lg px-4 py-3 text-left text-sm transition-all duration-200 hover:shadow-md ${answers.find(a => a.question_id === questions[currentQuestionIndex].id)?.user_choice === 'B'
                ? 'bg-blue-100 border-2 border-blue-500 text-blue-800 dark:bg-blue-900/30 dark:border-blue-500 dark:text-blue-300'
                : 'bg-white border-2 border-gray-300 text-gray-700 hover:bg-gray-50 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-700'}
              `}
            >
              <span class="font-bold mr-2">B</span>
              {questions[currentQuestionIndex].option_b}
            </button>
          </div>
        </div>

        <div class="flex justify-between">
          <button
            on:click={prevQuestion}
            disabled={currentQuestionIndex === 0}
            class="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-700"
          >
            上一题
          </button>
          {#if currentQuestionIndex === questions.length - 1}
            <button
              on:click={submitAnswers}
              disabled={isSubmitting || !answers.find(a => a.question_id === questions[currentQuestionIndex].id)}
              class="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--primary)]/90 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/50"
            >
              {isSubmitting ? '提交中...' : '提交答案'}
            </button>
          {:else}
            <button
              on:click={nextQuestion}
              disabled={!answers.find(a => a.question_id === questions[currentQuestionIndex].id)}
              class="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--primary)]/90 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/50"
            >
              下一题
            </button>
          {/if}
        </div>

        <!-- 已答题目进度 -->
        <div class="rounded-lg border bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800/50">
          <p class="text-sm text-gray-600 dark:text-gray-400 mb-2">已答题目：{answers.length}/{questions.length}</p>
          <div class="flex flex-wrap gap-1">
            {#each questions as q, i}
              <div 
                class={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${
                  answers.find(a => a.question_id === q.id)
                    ? 'bg-[var(--primary)] text-white'
                    : 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                }`}
              >
                {i + 1}
              </div>
            {/each}
          </div>
        </div>
      {:else}
        <div class="p-4 text-gray-600 dark:text-gray-400">
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
