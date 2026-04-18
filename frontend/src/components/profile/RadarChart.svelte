<script lang="ts">
	import { onMount, onDestroy } from "svelte";

	/** 演示模式固定配色（与全局亮/暗主题解耦） */
	const DEMO_FRAME_BG = "#EBF1F5";
	const DEMO_CARD_BG = "#FFFFFF";
	const DEMO_GRID = "rgba(0, 0, 0, 0.08)";
	const DEMO_LABEL = "#5C6670";
	const DEMO_LEGEND = "#4B5563";
	const DEMO_ACCENT = "#00AEEF";
	const DEMO_FILL = "rgba(0, 174, 239, 0.42)";

	/** 无上传数据时展示的示例多边形（与演示稿一致：专业理论顶轴拉满） */
	const DEMO_VALUES = [100, 88, 92, 86, 84, 90, 82, 87] as const;

	let scores = {
		theory: 0,
		cross: 0,
		practice: 0,
		digital: 0,
		innovation: 0,
		teamwork: 0,
		social: 0,
		growth: 0,
	};

	let canvasEl: HTMLCanvasElement;
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	let chart: any = null;
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	let ChartCtor: any = null;

	function isBrowser(): boolean {
		return typeof window !== "undefined" && typeof document !== "undefined";
	}

	function effectiveSeries(): number[] {
		const arr = [
			scores.theory,
			scores.cross,
			scores.practice,
			scores.digital,
			scores.innovation,
			scores.teamwork,
			scores.social,
			scores.growth,
		];
		const allZero = arr.every((v) => v === 0 || v === null || v === undefined);
		if (allZero) return [...DEMO_VALUES];
		return arr.map((v) => Number(v) || 0);
	}

	function radarOptions() {
		return {
			responsive: true,
			maintainAspectRatio: false,
			scales: {
				r: {
					beginAtZero: true,
					max: 100,
					ticks: {
						color: DEMO_LABEL,
						backdropColor: "transparent",
						showLabelBackdrop: false,
						stepSize: 20,
					},
					grid: { color: DEMO_GRID },
					angleLines: { color: DEMO_GRID },
					pointLabels: {
						color: DEMO_LABEL,
						font: { size: 11, family: "system-ui, sans-serif" },
					},
				},
			},
			plugins: {
				legend: {
					labels: {
						color: DEMO_LEGEND,
						boxWidth: 14,
						usePointStyle: false,
					},
				},
			},
		} as const;
	}

	function renderChart() {
		if (!canvasEl || !isBrowser() || !ChartCtor) return;

		const series = effectiveSeries();

		if (chart) {
			chart.destroy();
			chart = null;
		}

		chart = new ChartCtor(canvasEl, {
			type: "radar",
			data: {
				labels: [
					"专业理论",
					"交叉广度",
					"专业实践",
					"数字素养",
					"创新能力",
					"团队协作",
					"社会实践",
					"学习成长",
				],
				datasets: [
					{
						label: "能力画像",
						data: series,
						backgroundColor: DEMO_FILL,
						borderColor: DEMO_ACCENT,
						borderWidth: 2,
						pointBackgroundColor: DEMO_ACCENT,
						pointBorderColor: "#FFFFFF",
						pointBorderWidth: 2,
						pointRadius: 4,
						pointHoverRadius: 5,
					},
				],
			},
			options: { ...radarOptions() },
		});
	}

	function handleUpdateScores(e: CustomEvent) {
		scores = { ...scores, ...e.detail };
		renderChart();
	}

	onMount(async () => {
		if (!isBrowser()) return;
		const { Chart, registerables } = await import("chart.js");
		Chart.register(...registerables);
		ChartCtor = Chart;
		renderChart();
		window.addEventListener("updateRadarScores", handleUpdateScores as EventListener);
	});

	onDestroy(() => {
		if (isBrowser()) {
			window.removeEventListener("updateRadarScores", handleUpdateScores as EventListener);
		}
		if (chart) {
			chart.destroy();
			chart = null;
		}
		ChartCtor = null;
	});
</script>

<!-- 演示模式固定外层：浅灰蓝底 + 白卡片，不随站点 dark 变化 -->
<div
	class="rounded-2xl p-4 shadow-sm"
	style="background-color: {DEMO_FRAME_BG};"
>
	<div
		class="h-96 w-full rounded-xl p-4 shadow-[0_1px_3px_rgba(0,0,0,0.06)]"
		style="background-color: {DEMO_CARD_BG};"
	>
		<canvas bind:this={canvasEl}></canvas>
	</div>
</div>
