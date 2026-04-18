<script lang="ts">
	import { onMount, onDestroy } from "svelte";
	import type { Chart as ChartType } from "chart.js";

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
	let chart: ChartType<"radar", number[], string> | null = null;
	let ChartCtor: (typeof import("chart.js"))["Chart"] | null = null;
	let themeObserver: MutationObserver | null = null;
	let themeRaf = 0;

	function cssVar(name: string, fallback: string): string {
		if (typeof window === "undefined") return fallback;
		const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
		return v || fallback;
	}

	function primaryFillRgba(primaryCss: string): string {
		try {
			const tmp = document.createElement("span");
			tmp.style.color = primaryCss;
			document.body.appendChild(tmp);
			const rgb = getComputedStyle(tmp).color;
			document.body.removeChild(tmp);
			if (rgb && rgb !== "rgba(0, 0, 0, 0)") {
				return rgb.replace(")", ", 0.22)").replace("rgb", "rgba");
			}
		} catch {
			/* ignore */
		}
		return "rgba(59, 130, 246, 0.22)";
	}

	function radarOptions() {
		const text = cssVar("--content-meta", "rgba(0,0,0,0.65)");
		const grid = cssVar("--line-color", "rgba(0,0,0,0.12)");

		return {
			responsive: true,
			maintainAspectRatio: false,
			scales: {
				r: {
					beginAtZero: true,
					max: 100,
					ticks: {
						color: text,
						backdropColor: "transparent",
						showLabelBackdrop: false,
						stepSize: 20,
					},
					grid: { color: grid },
					angleLines: { color: grid },
					pointLabels: {
						color: text,
						font: { size: 11 },
					},
				},
			},
			plugins: {
				legend: {
					labels: {
						color: text,
						boxWidth: 14,
					},
				},
			},
		} as const;
	}

	function renderChart() {
		if (!canvasEl || typeof window === "undefined" || !ChartCtor) return;

		const primary = cssVar("--primary", "rgb(59, 130, 246)");
		const fill = primaryFillRgba(primary);

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
						data: [
							scores.theory,
							scores.cross,
							scores.practice,
							scores.digital,
							scores.innovation,
							scores.teamwork,
							scores.social,
							scores.growth,
						],
						backgroundColor: fill,
						borderColor: primary,
						borderWidth: 2,
						pointBackgroundColor: primary,
						pointBorderColor: primary,
					},
				],
			},
			options: { ...radarOptions() },
		});
	}

	function scheduleThemeRerender() {
		cancelAnimationFrame(themeRaf);
		themeRaf = requestAnimationFrame(() => {
			renderChart();
		});
	}

	function handleUpdateScores(e: CustomEvent) {
		scores = { ...scores, ...e.detail };
		renderChart();
	}

	onMount(async () => {
		const { Chart, registerables } = await import("chart.js");
		Chart.register(...registerables);
		ChartCtor = Chart;
		renderChart();
		window.addEventListener("updateRadarScores", handleUpdateScores as EventListener);

		themeObserver = new MutationObserver(() => scheduleThemeRerender());
		themeObserver.observe(document.documentElement, {
			attributes: true,
			attributeFilter: ["class"],
		});
	});

	onDestroy(() => {
		window.removeEventListener("updateRadarScores", handleUpdateScores as EventListener);
		themeObserver?.disconnect();
		themeObserver = null;
		cancelAnimationFrame(themeRaf);
		if (chart) {
			chart.destroy();
			chart = null;
		}
		ChartCtor = null;
	});
</script>

<div class="h-96 w-full rounded-lg border border-black/10 bg-[var(--card-bg)] p-4 shadow-sm dark:border-white/10">
	<canvas bind:this={canvasEl}></canvas>
</div>
