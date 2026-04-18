<script lang="ts">
	import { onDestroy, onMount } from "svelte";
	import type { JobCardItem } from "@/lib/jobs";

	/** 与 `JobsExplorer.svelte` 岗位卡片雷达一致 */
	const DIMENSIONS: { key: keyof JobCardItem["scores"]; label: string; full: string }[] = [
		{ key: "cap_req_theory", label: "理论知识", full: "专业理论知识" },
		{ key: "cap_req_cross", label: "交叉广度", full: "交叉学科广度" },
		{ key: "cap_req_practice", label: "实践技能", full: "专业实践技能" },
		{ key: "cap_req_digital", label: "数字素养", full: "数字素养技能" },
		{ key: "cap_req_innovation", label: "创新创业", full: "创新创业能力" },
		{ key: "cap_req_teamwork", label: "团队协作", full: "团队协作能力" },
		{ key: "cap_req_social", label: "社会实践", full: "社会实践网络" },
		{ key: "cap_req_growth", label: "学习发展", full: "学习与发展潜力" },
	];

	const RADAR_TIERS = [0.25, 0.5, 0.75, 1] as const;
	const RADAR_CX = 140;
	const RADAR_CY = 120;
	const RADAR_MAX_R = 88;
	const RADAR_LABEL_R = 110;

	/** 无上传结果时的占位形状（与岗位卡风格一致） */
	const DEMO_SCORES: JobCardItem["scores"] = {
		cap_req_theory: 85,
		cap_req_cross: 78,
		cap_req_practice: 82,
		cap_req_digital: 80,
		cap_req_innovation: 75,
		cap_req_teamwork: 88,
		cap_req_social: 72,
		cap_req_growth: 80,
	};

	let scores = $state({
		theory: 0,
		cross: 0,
		practice: 0,
		digital: 0,
		innovation: 0,
		teamwork: 0,
		social: 0,
		growth: 0,
	});

	let radarScores = $derived.by((): JobCardItem["scores"] => {
		const raw = [
			scores.theory,
			scores.cross,
			scores.practice,
			scores.digital,
			scores.innovation,
			scores.teamwork,
			scores.social,
			scores.growth,
		];
		const allZero = raw.every((v) => v === 0 || v === null || v === undefined);
		if (allZero) return { ...DEMO_SCORES };
		return {
			cap_req_theory: Number(scores.theory) || 0,
			cap_req_cross: Number(scores.cross) || 0,
			cap_req_practice: Number(scores.practice) || 0,
			cap_req_digital: Number(scores.digital) || 0,
			cap_req_innovation: Number(scores.innovation) || 0,
			cap_req_teamwork: Number(scores.teamwork) || 0,
			cap_req_social: Number(scores.social) || 0,
			cap_req_growth: Number(scores.growth) || 0,
		};
	});

	let scoreAvgDisplay = $derived.by(() => {
		const s = radarScores;
		const sum =
			s.cap_req_theory +
			s.cap_req_cross +
			s.cap_req_practice +
			s.cap_req_digital +
			s.cap_req_innovation +
			s.cap_req_teamwork +
			s.cap_req_social +
			s.cap_req_growth;
		return Math.round((sum / 8) * 100) / 100;
	});

	function confidenceText(value: number): string {
		return `${value.toFixed(2)}%`;
	}

	function point(angleIndex: number, value: number) {
		const angle = (-Math.PI / 2 + (angleIndex * 2 * Math.PI) / DIMENSIONS.length) % (2 * Math.PI);
		const r = (Math.max(0, Math.min(100, value)) / 100) * RADAR_MAX_R;
		return { x: RADAR_CX + r * Math.cos(angle), y: RADAR_CY + r * Math.sin(angle) };
	}

	function pointByRadius(angleIndex: number, radius: number) {
		const angle = (-Math.PI / 2 + (angleIndex * 2 * Math.PI) / DIMENSIONS.length) % (2 * Math.PI);
		return {
			x: RADAR_CX + radius * Math.cos(angle),
			y: RADAR_CY + radius * Math.sin(angle),
		};
	}

	function calcPoints(s: JobCardItem["scores"]): string {
		const points = DIMENSIONS.map((d, idx) => {
			const p = point(idx, s[d.key]);
			return `${p.x.toFixed(2)},${p.y.toFixed(2)}`;
		});
		return points.join(" ");
	}

	function calcGridPointsByTier(tier: number): string {
		const points = DIMENSIONS.map((_, idx) => {
			const p = point(idx, 100 * tier);
			return `${p.x.toFixed(2)},${p.y.toFixed(2)}`;
		});
		return points.join(" ");
	}

	function axisEnd(idx: number) {
		const p = point(idx, 100);
		return { x: p.x, y: p.y };
	}

	function labelPos(idx: number) {
		const p = pointByRadius(idx, RADAR_LABEL_R);
		return { x: p.x, y: p.y };
	}

	function handleUpdateScores(e: CustomEvent) {
		scores = { ...scores, ...e.detail };
	}

	onMount(() => {
		window.addEventListener("updateRadarScores", handleUpdateScores as EventListener);
	});

	onDestroy(() => {
		window.removeEventListener("updateRadarScores", handleUpdateScores as EventListener);
	});
</script>

<div class="radar-card">
	<div class="radar-row">
		<svg viewBox="0 0 280 240" class="radar">
			{#each RADAR_TIERS as tier}
				<polygon
					points={calcGridPointsByTier(tier)}
					class="grid-layer text-black/10 dark:text-white/10"
					stroke="currentColor"
					fill="none"
				/>
			{/each}
			{#each DIMENSIONS as d, i}
				{@const end = axisEnd(i)}
				<line
					x1={RADAR_CX}
					y1={RADAR_CY}
					x2={end.x}
					y2={end.y}
					class="axis-line text-black/15 dark:text-white/15"
					stroke="currentColor"
				/>
			{/each}
			<polygon points={calcPoints(radarScores)} class="data-layer" />
			{#each DIMENSIONS as d, i}
				{@const p = labelPos(i)}
				<text
					x={p.x}
					y={p.y}
					class="axis-label fill-black/60 text-[9px] dark:fill-white/70"
					text-anchor="middle"
					dominant-baseline="middle"
					aria-label={`${d.full} ${radarScores[d.key]} 分`}
				>
					<tspan x={p.x} dy="-0.2em">{d.label}</tspan>
					<tspan x={p.x} dy="1.2em" class="score-text">{radarScores[d.key]}</tspan>
				</text>
			{/each}
		</svg>
	</div>

	<div class="score-band">
		<span>分档: 0-39 低要求</span>
		<span>40-59 中等要求</span>
		<span>60-79 较高要求</span>
		<span>80-100 核心高要求</span>
	</div>

	<div class="card-foot">
		<span class="confidence-tag">平均置信度: {confidenceText(scoreAvgDisplay)}</span>
	</div>
</div>

<style>
	.radar-card {
		border-radius: 1rem;
		padding: 0.75rem 0.5rem 0.5rem;
		background: var(--card-bg);
		border: 1px solid color-mix(in oklab, var(--text-75) 20%, transparent);
		box-shadow: 0 8px 22px rgba(2, 6, 23, 0.06);
	}
	.radar-row {
		margin-top: 0.2rem;
		display: block;
	}
	.radar {
		width: 100%;
		max-width: 360px;
		height: auto;
		display: block;
		margin: 0 auto;
	}
	.radar :global(.grid-layer) {
		fill: none;
		stroke-width: 1;
	}
	.radar :global(.axis-line) {
		stroke-width: 1;
	}
	.radar :global(.data-layer) {
		fill: color-mix(in oklch, var(--primary) 35%, transparent);
		stroke: var(--primary);
		stroke-width: 2;
	}
	.radar :global(.axis-label) {
		pointer-events: none;
	}
	.radar :global(.score-text) {
		fill: var(--primary);
		font-size: 8px;
		font-weight: 600;
	}
	.score-band {
		margin-top: 0.5rem;
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
	}
	.score-band span {
		font-size: 0.72rem;
		padding: 0.15rem 0.42rem;
		border-radius: 999px;
		color: var(--text-75);
		background: color-mix(in oklab, var(--btn-regular-bg) 78%, transparent);
	}
	.card-foot {
		margin-top: 0.75rem;
		display: flex;
		align-items: center;
		justify-content: flex-start;
	}
	.confidence-tag {
		font-size: 0.78rem;
		color: var(--text-75);
	}
	@media (max-width: 768px) {
		.radar {
			max-width: 320px;
		}
	}
</style>
