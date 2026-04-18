<script lang="ts">
  import { onMount, onDestroy } from 'svelte';

  // 使用本地状态管理分数数据
  let scores = {
    theory: 0,
    cross: 0,
    practice: 0,
    digital: 0,
    innovation: 0,
    teamwork: 0,
    social: 0,
    growth: 0
  };

  let canvasEl: HTMLCanvasElement;
  let chart: any = null;
  let Chart: any;
  let registerables: any;

  function renderChart() {
    if (!canvasEl || typeof window === 'undefined') return;
    if (chart) chart.destroy();
    chart = new Chart(canvasEl, {
      type: 'radar',
      data: {
        labels: ['专业理论', '交叉广度', '专业实践', '数字素养', '创新能力', '团队协作', '社会实践', '学习成长'],
        datasets: [{
          label: '能力画像',
          data: [
            scores.theory, scores.cross, scores.practice, scores.digital,
            scores.innovation, scores.teamwork, scores.social, scores.growth
          ],
          backgroundColor: 'rgba(59, 130, 246, 0.2)',
          borderColor: 'rgb(59, 130, 246)',
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { r: { beginAtZero: true, max: 100 } }
      }
    });
    console.log('雷达图已渲染，数据:', scores);
  }

  // 监听自定义事件
  function handleUpdateScores(e: CustomEvent) {
    scores = { ...scores, ...e.detail };
    console.log('收到分数更新:', e.detail);
    renderChart();
  }

  onMount(async () => {
    console.log('雷达图组件已挂载');
    if (typeof window !== 'undefined') {
      // 动态导入Chart.js
      const chartModule = await import('chart.js');
      Chart = chartModule.Chart;
      registerables = chartModule.registerables;
      Chart.register(...registerables);
      renderChart();
      window.addEventListener('updateRadarScores', handleUpdateScores);
    }
  });

  onDestroy(() => {
    if (typeof window !== 'undefined') {
      window.removeEventListener('updateRadarScores', handleUpdateScores);
    }
    if (chart) chart.destroy();
  });
</script>

<div class="w-full h-96 rounded-lg border bg-background p-4 shadow-sm">
  <canvas bind:this={canvasEl} />
</div>