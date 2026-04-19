<script lang="ts">
	import type { JobCardItem } from "@/lib/jobs";
	import {
		RADAR_DIMENSIONS,
		RADAR_TIERS,
		RADAR_CX,
		RADAR_CY,
		calcRadarPolygonPoints,
		calcRadarGridPolygon,
		radarAxisEnd,
		radarLabelPos,
	} from "@/lib/radar-geometry";

	type Props = {
		studentScores: JobCardItem["scores"];
		jobScores: JobCardItem["scores"];
		/** fill：占满父容器高度，用于智能推荐卡片右侧 */
		layout?: "compact" | "fill";
	};

	let { studentScores, jobScores, layout = "compact" }: Props = $props();

	const studentForRadar = $derived({ scores: studentScores } as Pick<JobCardItem, "scores">);
	const jobForRadar = $derived({ scores: jobScores } as Pick<JobCardItem, "scores">);
</script>

<div class="pair-radar" class:pair-radar--fill={layout === "fill"}>
	<div class="radar-svg-box" class:radar-svg-box--fill={layout === "fill"}>
		<svg
			viewBox="0 0 280 240"
			class="radar"
			class:radar--fill={layout === "fill"}
			preserveAspectRatio="xMidYMid meet"
			aria-label="画像供给与岗位需求八维对比"
		>
		{#each RADAR_TIERS as tier}
			<polygon
				points={calcRadarGridPolygon(tier)}
				class="grid-layer text-black/10 dark:text-white/10"
				stroke="currentColor"
				fill="none"
			/>
		{/each}
		{#each RADAR_DIMENSIONS as _d, i}
			{@const end = radarAxisEnd(i)}
			<line
				x1={RADAR_CX}
				y1={RADAR_CY}
				x2={end.x}
				y2={end.y}
				class="axis-line text-black/15 dark:text-white/15"
				stroke="currentColor"
			/>
		{/each}
		<polygon points={calcRadarPolygonPoints(jobForRadar)} class="job-layer" />
		<polygon points={calcRadarPolygonPoints(studentForRadar)} class="student-layer" />
		{#each RADAR_DIMENSIONS as d, i}
			{@const p = radarLabelPos(i)}
			<text
				x={p.x}
				y={p.y}
				class="axis-label fill-black/55 dark:fill-white/65"
				text-anchor="middle"
				dominant-baseline="middle"
				aria-label="{d.full}：画像 {studentScores[d.key]}，岗位需求 {jobScores[d.key]}"
			>
				{d.label}
			</text>
		{/each}
		</svg>
	</div>
	<div class="legend text-75" class:legend--fill={layout === "fill"}>
		<span class="lg-item"><span class="dot student" aria-hidden="true"></span>画像供给</span>
		<span class="lg-item"><span class="dot job" aria-hidden="true"></span>岗位需求</span>
	</div>
</div>

<style>
	.pair-radar {
		width: 100%;
		max-width: 220px;
		margin-inline: auto;
		display: flex;
		flex-direction: column;
		align-items: center;
	}
	.pair-radar--fill {
		max-width: none;
		height: 100%;
		min-height: 0;
		flex: 1;
		align-self: stretch;
	}
	.radar-svg-box {
		width: 100%;
	}
	.radar-svg-box--fill {
		width: 100%;
		aspect-ratio: 280 / 240;
		max-height: min(48vh, 26rem);
		flex: 1 1 auto;
		min-height: 13rem;
		min-width: 0;
	}
	.radar {
		width: 100%;
		height: auto;
		display: block;
	}
	.radar--fill {
		width: 100%;
		height: 100%;
		display: block;
	}
	.axis-label {
		font-size: 8px;
	}
	.pair-radar--fill .axis-label {
		font-size: 9.5px;
	}
	.radar :global(.grid-layer) {
		fill: none;
		stroke-width: 1;
	}
	.radar :global(.axis-line) {
		stroke-width: 1;
	}
	.radar :global(.job-layer) {
		fill: color-mix(in oklch, #0ea5e9 28%, transparent);
		stroke: #0284c7;
		stroke-width: 2;
	}
	:global(.dark) .radar :global(.job-layer) {
		fill: color-mix(in oklch, #38bdf8 22%, transparent);
		stroke: #7dd3fc;
	}
	.radar :global(.student-layer) {
		fill: color-mix(in oklch, var(--primary) 32%, transparent);
		stroke: var(--primary);
		stroke-width: 2;
	}
	.radar :global(.axis-label) {
		pointer-events: none;
	}
	.legend {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 0.65rem 1rem;
		margin-top: 0.35rem;
		font-size: 10px;
		line-height: 1.2;
		flex-shrink: 0;
	}
	.legend--fill {
		font-size: 11px;
		margin-top: 0.5rem;
	}
	.lg-item {
		display: inline-flex;
		align-items: center;
		gap: 0.28rem;
	}
	.dot {
		display: inline-block;
		width: 0.45rem;
		height: 0.45rem;
		border-radius: 999px;
		flex-shrink: 0;
	}
	.dot.student {
		background: var(--primary);
	}
	.dot.job {
		background: #0284c7;
	}
	:global(.dark) .dot.job {
		background: #7dd3fc;
	}
</style>
