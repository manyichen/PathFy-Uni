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
		scores: JobCardItem["scores"];
	};

	let { scores }: Props = $props();

	const jobForRadar = $derived({ scores } as Pick<JobCardItem, "scores">);
</script>

<div class="radar-wrap">
	<svg viewBox="0 0 280 240" class="radar" aria-label="八维能力雷达图">
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
		<polygon points={calcRadarPolygonPoints(jobForRadar)} class="data-layer" />
		{#each RADAR_DIMENSIONS as d, i}
			{@const p = radarLabelPos(i)}
			<text
				x={p.x}
				y={p.y}
				class="axis-label fill-black/60 text-[9px] dark:fill-white/70"
				text-anchor="middle"
				dominant-baseline="middle"
				aria-label="{d.full} {scores[d.key]} 分"
			>
				<tspan x={p.x} dy="-0.2em">{d.label}</tspan>
				<tspan x={p.x} dy="1.2em" class="score-text">{scores[d.key]}</tspan>
			</text>
		{/each}
	</svg>
</div>

<style>
	.radar-wrap {
		width: 100%;
	}
	.radar {
		width: 100%;
		max-width: 340px;
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
</style>
