<script lang="ts">
type Node = { id: string; x: number; y: number; label: string };
const nodes: Node[] = [
	{ id: "a", x: 50, y: 180, label: "初级开发" },
	{ id: "b", x: 200, y: 80, label: "高级工程师" },
	{ id: "c", x: 350, y: 180, label: "技术专家" },
	{ id: "d", x: 200, y: 280, label: "全栈" },
];

const edges: [string, string][] = [
	["a", "b"],
	["a", "d"],
	["d", "b"],
	["b", "c"],
];

let active = $state<string | null>("a");

function nodeFill(id: string) {
	if (active === id) return "var(--primary)";
	return "var(--card-bg)";
}
function nodeStroke(id: string) {
	if (active === id) return "var(--primary)";
	return "color-mix(in oklch, var(--primary) 45%, transparent)";
}
</script>

<div class="relative rounded-2xl border border-black/10 bg-[var(--page-bg)] p-4 dark:border-white/10">
	<p class="mb-4 text-center text-sm text-75">点击节点或下方标签高亮（演示路径）</p>
	<svg
		class="mx-auto max-h-[340px] w-full max-w-lg touch-manipulation"
		viewBox="0 0 400 360"
		role="img"
		aria-label="职业路径示意图"
	>
		<defs>
			<filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
				<feGaussianBlur stdDeviation="3" result="blur" />
				<feMerge>
					<feMergeNode in="blur" />
					<feMergeNode in="SourceGraphic" />
				</feMerge>
			</filter>
		</defs>
		{#each edges as [from, to] (`${from}-${to}`)}
			{@const na = nodes.find((n) => n.id === from)!}
			{@const nb = nodes.find((n) => n.id === to)!}
			<line
				x1={na.x}
				y1={na.y}
				x2={nb.x}
				y2={nb.y}
				stroke="var(--primary)"
				stroke-width="2"
				stroke-opacity={active === from || active === to ? "0.65" : "0.18"}
				stroke-dasharray="6 8"
				class="transition-all duration-300"
			/>
		{/each}
		{#each nodes as n (n.id)}
			<g>
				<circle
					cx={n.x}
					cy={n.y}
					r="28"
					fill={nodeFill(n.id)}
					stroke={nodeStroke(n.id)}
					stroke-width="3"
					filter={active === n.id ? "url(#glow)" : undefined}
					class="cursor-pointer transition-all duration-300"
					role="button"
					tabindex="0"
					onclick={() => (active = n.id)}
					onkeydown={(e) => {
						if (e.key === "Enter" || e.key === " ") {
							e.preventDefault();
							active = n.id;
						}
					}}
				/>
				<text
					x={n.x}
					y={n.y + 4}
					text-anchor="middle"
					class="pointer-events-none fill-black text-[11px] font-bold dark:fill-white"
				>
					{n.label.slice(0, 2)}
				</text>
			</g>
		{/each}
	</svg>
	<div class="mt-2 flex flex-wrap justify-center gap-2 text-xs">
		{#each nodes as n (n.id)}
			<button
				type="button"
				class="rounded-full border px-3 py-1 transition {active === n.id
					? 'border-[var(--primary)] bg-[var(--btn-regular-bg)] text-[var(--primary)]'
					: 'border-black/10 text-75 dark:border-white/15'}"
				onclick={() => (active = n.id)}
			>
				{n.label}
			</button>
		{/each}
	</div>
</div>
