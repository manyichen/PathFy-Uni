<script lang="ts">
import { untrack } from "svelte";

const labels = ["基础要求", "职业技能", "职业素养", "发展潜力"] as const;
const mockScores = [72, 85, 68, 90] as const;

let weights = $state([25, 25, 25, 25]);

let composite = $derived.by(() => {
	const sum = weights.reduce((a, b) => a + b, 0);
	if (sum === 0) return 0;
	return weights.reduce((acc, w, i) => acc + w * mockScores[i], 0) / sum;
});

let displayScore = $state(0);
let raf = 0;

$effect(() => {
	const target = Math.round(composite * 10) / 10;
	cancelAnimationFrame(raf);
	const start = untrack(() => displayScore);
	const t0 = performance.now();
	const dur = 450;
	function tick(now: number) {
		const t = Math.min(1, (now - t0) / dur);
		const ease = 1 - (1 - t) ** 3;
		displayScore = Math.round((start + (target - start) * ease) * 10) / 10;
		if (t < 1) raf = requestAnimationFrame(tick);
	}
	raf = requestAnimationFrame(tick);
	return () => cancelAnimationFrame(raf);
});
</script>

<div class="space-y-8">
	<div
		class="relative overflow-hidden rounded-2xl border border-black/10 bg-[var(--card-bg)] p-6 dark:border-white/10 md:p-8"
	>
		<div
			class="pointer-events-none absolute -right-16 top-0 h-40 w-40 rounded-full bg-[var(--primary)] opacity-15 blur-3xl"
		></div>
		<div class="relative flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
			<div>
				<p class="mb-1 text-sm font-medium text-[var(--primary)]">综合匹配度（演示）</p>
				<p class="text-5xl font-black tabular-nums tracking-tight text-black dark:text-white">
					{displayScore}<span class="text-2xl font-bold text-50">/100</span>
				</p>
				<p class="mt-2 max-w-md text-sm text-75">
					拖动滑块调整各维度权重，观察加权总分变化。正式环境由后端按岗位与学生画像计算。
				</p>
			</div>
			<div
				class="flex h-28 w-28 shrink-0 items-center justify-center rounded-full border-4 border-[var(--primary)]/40 bg-[var(--btn-regular-bg)] shadow-inner"
			>
				<svg class="h-full w-full -rotate-90" viewBox="0 0 100 100" aria-hidden="true">
					<circle
						cx="50"
						cy="50"
						r="42"
						fill="none"
						stroke="currentColor"
						class="text-black/10 dark:text-white/10"
						stroke-width="8"
					></circle>
					<circle
						cx="50"
						cy="50"
						r="42"
						fill="none"
						stroke="var(--primary)"
						stroke-width="8"
						stroke-linecap="round"
						stroke-dasharray="264"
						style="stroke-dashoffset: {264 - (264 * composite) / 100}"
						class="transition-all duration-500"
					></circle>
				</svg>
			</div>
		</div>
	</div>

	<div class="grid gap-6 md:grid-cols-2">
		{#each labels as label, i (label)}
			<div
				class="rounded-xl border border-black/10 bg-[var(--card-bg)] p-5 dark:border-white/10"
			>
				<div class="mb-3 flex items-center justify-between">
					<span class="font-semibold text-black dark:text-white">{label}</span>
					<span class="font-mono text-sm text-[var(--primary)]">{weights[i]}%</span>
				</div>
				<input
					type="range"
					min="0"
					max="100"
					bind:value={weights[i]}
					class="mb-3 w-full accent-[var(--primary)]"
					aria-label="{label}权重"
				/>
				<div class="h-2 overflow-hidden rounded-full bg-[var(--btn-regular-bg)]">
					<div
						class="h-full rounded-full bg-gradient-to-r from-[var(--primary)] to-[oklch(0.85_0.12_var(--hue))] transition-all duration-300"
						style="width: {mockScores[i]}%"
					></div>
				</div>
				<p class="mt-2 text-xs text-50">模拟岗位契合度：{mockScores[i]}（演示数据）</p>
			</div>
		{/each}
	</div>
</div>
