<script lang="ts">
  import { onMount } from 'svelte';

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

  let questions: Question[] = [];
  let currentQuestionIndex = 0;
  let answers: Answer[] = [];
  let isLoading = true;
  let isSubmitting = false;
  let showResults = false;
  let personalityProfile: any = null;
  let errorMessage = '';

  // 加载题目
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

  // 提交答案
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

  // 选择答案
  function selectAnswer(questionId: number, choice: string) {
    const existingAnswerIndex = answers.findIndex(a => a.question_id === questionId);
    if (existingAnswerIndex !== -1) {
      answers[existingAnswerIndex].user_choice = choice;
    } else {
      answers.push({ question_id: questionId, user_choice: choice });
    }
  }

  // 下一题
  function nextQuestion() {
    if (currentQuestionIndex < questions.length - 1) {
      currentQuestionIndex++;
    }
  }

  // 上一题
  function prevQuestion() {
    if (currentQuestionIndex > 0) {
      currentQuestionIndex--;
    }
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
  {:else if showResults}
    <!-- 结果展示 -->
    <div class="space-y-6">
      <h2 class="text-xl font-semibold text-black dark:text-white">测试结果</h2>
      <div class="rounded-lg border bg-blue-50 p-4 dark:border-blue-900/30 dark:bg-blue-900/10">
        <h3 class="text-lg font-medium text-blue-800 dark:text-blue-300 mb-2">你的MBTI类型：{personalityProfile.mbti_type}</h3>
        <p class="text-sm text-gray-700 dark:text-gray-300">{personalityProfile.personality_analysis}</p>
      </div>
      {#if personalityProfile.recommended_jobs}
        <div class="rounded-lg border bg-green-50 p-4 dark:border-green-900/30 dark:bg-green-900/10">
          <h3 class="text-sm font-medium text-green-800 dark:text-green-300 mb-2">推荐岗位</h3>
          <p class="text-sm text-gray-700 dark:text-gray-300">{personalityProfile.recommended_jobs}</p>
        </div>
      {/if}
      <div class="flex justify-center">
        <button
          on:click={() => {
            showResults = false;
            currentQuestionIndex = 0;
            answers = [];
          }}
          class="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--primary)]/90 focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/50"
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
              class="h-2 bg-[var(--primary)] rounded-full"
              style="width: ${((currentQuestionIndex + 1) / questions.length) * 100}%"
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
              class={`w-full rounded-lg px-4 py-3 text-left text-sm transition ${answers.find(a => a.question_id === questions[currentQuestionIndex].id)?.user_choice === 'A'
                ? 'bg-blue-100 border-blue-500 text-blue-800 dark:bg-blue-900/30 dark:border-blue-500 dark:text-blue-300'
                : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-700'}
              border`}
            >
              A. {questions[currentQuestionIndex].option_a}
            </button>
            <button
              on:click={() => selectAnswer(questions[currentQuestionIndex].id, 'B')}
              class={`w-full rounded-lg px-4 py-3 text-left text-sm transition ${answers.find(a => a.question_id === questions[currentQuestionIndex].id)?.user_choice === 'B'
                ? 'bg-blue-100 border-blue-500 text-blue-800 dark:bg-blue-900/30 dark:border-blue-500 dark:text-blue-300'
                : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-700'}
              border`}
            >
              B. {questions[currentQuestionIndex].option_b}
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
      {:else}
        <div class="p-4 text-gray-600 dark:text-gray-400">
          没有加载到测试题目，请刷新页面重试。
        </div>
      {/if}
    </div>
  {/if}
</div>