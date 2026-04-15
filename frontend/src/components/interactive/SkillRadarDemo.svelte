<script lang="ts">
const axes = [
	{
		key: "cap_req_theory",
		label: "理论知识",
		fullLabel: "专业理论知识",
	},
	{
		key: "cap_req_cross",
		label: "交叉广度",
		fullLabel: "交叉学科广度",
	},
	{
		key: "cap_req_practice",
		label: "实践技能",
		fullLabel: "专业实践技能",
	},
	{
		key: "cap_req_digital",
		label: "数字素养",
		fullLabel: "数字素养技能",
	},
	{
		key: "cap_req_innovation",
		label: "创新创业",
		fullLabel: "创新创业能力",
	},
	{
		key: "cap_req_teamwork",
		label: "团队协作",
		fullLabel: "团队协作能力",
	},
	{
		key: "cap_req_social",
		label: "社会实践",
		fullLabel: "社会实践网络",
	},
	{
		key: "cap_req_growth",
		label: "发展潜力",
		fullLabel: "学习与发展潜力",
	},
] as const;

// 演示值与《能力画像图谱职业评估依据（最终版）》示例口径保持一致
const values = [68, 55, 82, 79, 41, 70, 36, 64];
const n = axes.length;
const cx = 120;
const cy = 120;
const maxR = 88;

function point(angleIndex: number, value: number) {
	const angle = (-Math.PI / 2 + (angleIndex * 2 * Math.PI) / n) % (2 * Math.PI);
	const r = (value / 100) * maxR;
	return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
}

let polygonPoints = $derived(
	values
		.map((v, i) => {
			const p = point(i, v);
			return `${p.x},${p.y}`;
		})
		.join(" "),
);

let axisLines = $derived(
	axes.map((_, i) => {
		const p = point(i, 100);
		return { x2: p.x, y2: p.y };
	}),
);
</script>

<div class="rounded-2xl border border-black/10 bg-[var(--card-bg)] p-6 dark:border-white/10">
	<h3 class="mb-4 text-center font-semibold text-black dark:text-white">能力雷达（八维演示）</h3>
	<div class="flex justify-center">
		<svg width="280" height="280" viewBox="0 0 240 240" class="max-w-full" aria-hidden="true">
			{#each [0.25, 0.5, 0.75, 1] as tier}
				<polygon
					points={axes
						.map((_, i) => {
							const p = point(i, 100 * tier);
							return `${p.x},${p.y}`;
						})
						.join(" ")}
					fill="none"
					stroke="currentColor"
					class="text-black/10 dark:text-white/10"
					stroke-width="1"
				/>
			{/each}
			{#each axisLines as line, i}
				<line
					x1={cx}
					y1={cy}
					x2={line.x2}
					y2={line.y2}
					stroke="currentColor"
					class="text-black/15 dark:text-white/15"
					stroke-width="1"
				/>
				{@const lp = point(i, 108)}
				<text
					x={lp.x}
					y={lp.y}
					text-anchor="middle"
					dominant-baseline="middle"
					class="fill-black/60 text-[9px] dark:fill-white/70"
				>
					{axes[i].label}
				</text>
			{/each}
			<polygon
				points={polygonPoints}
				fill="color-mix(in oklch, var(--primary) 35%, transparent)"
				stroke="var(--primary)"
				stroke-width="2"
				class="radar-poly"
			/>
		</svg>
	</div>
	<ul class="mt-4 grid grid-cols-2 gap-2 text-xs text-75 sm:grid-cols-3">
		{#each axes as ax, i}
			<li class="flex justify-between rounded-lg bg-[var(--btn-regular-bg)] px-2 py-1.5">
				<span title={ax.key}>{ax.fullLabel}</span>
				<span class="font-mono text-[var(--primary)]">{values[i]}</span>
			</li>
		{/each}
	</ul>
</div>

<style>
	.radar-poly {
		animation: radar-pop 0.9s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
		transform-origin: 120px 120px;
	}
	@keyframes radar-pop {
		from {
			opacity: 0;
			transform: scale(0.4);
		}
		to {
			opacity: 1;
			transform: scale(1);
		}
	}
</style>
