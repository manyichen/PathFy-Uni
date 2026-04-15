<script lang="ts">
import Icon from "@iconify/svelte";

type Item = {
	href: string;
	title: string;
	desc: string;
	icon: string;
	tone: string;
	tags: string[];
	highlight: string;
	metricLabel: string;
	metricValue: string;
	progress: number;
	accent?: boolean;
};

const items: Item[] = [
	{
		href: "/jobs/",
		title: "岗位探索",
		desc: "万级岗位数据 · 多维度画像",
		icon: "material-symbols:work-outline",
		tone: "#22d3ee",
		tags: ["热门岗位", "技能画像", "城市筛选"],
		highlight: "快速定位目标岗位与能力要求",
		metricLabel: "岗位样本覆盖",
		metricValue: "10,000+",
		progress: 88,
		accent: true,
	},
	{
		href: "/profile/",
		title: "能力画像",
		desc: "简历解析 · 完整度与竞争力",
		icon: "material-symbols:person-search-outline",
		tone: "#2dd4bf",
		tags: ["八维雷达", "简历解析", "竞争力评分"],
		highlight: "生成学生就业能力画像与短板提示",
		metricLabel: "画像维度完整度",
		metricValue: "8 / 8",
		progress: 92,
	},
	{
		href: "/match/",
		title: "人岗匹配",
		desc: "四维加权 · 实时沙盘",
		icon: "material-symbols:compare-arrows-rounded",
		tone: "#60a5fa",
		tags: ["权重可调", "匹配解释", "差距诊断"],
		highlight: "比较岗位需求与个人能力差距",
		metricLabel: "匹配分析维度",
		metricValue: "4 维",
		progress: 80,
	},
	{
		href: "/graph/",
		title: "职业图谱",
		desc: "晋升链 · 换岗路径",
		icon: "material-symbols:account-tree-outline",
		tone: "#a78bfa",
		tags: ["纵向晋升", "横向转岗", "图谱关系"],
		highlight: "查看可落地的职业迁移路线",
		metricLabel: "路径可视节点",
		metricValue: "多跳图谱",
		progress: 76,
	},
	{
		href: "/report/",
		title: "生涯报告",
		desc: "目标 · 行动计划 · 导出",
		icon: "material-symbols:article-outline",
		tone: "#f59e0b",
		tags: ["目标拆解", "行动清单", "报告导出"],
		highlight: "沉淀个性化成长计划与执行节奏",
		metricLabel: "计划执行颗粒度",
		metricValue: "短/中期",
		progress: 84,
	},
];

function tilt(e: MouseEvent & { currentTarget: HTMLAnchorElement }) {
	const el = e.currentTarget;
	const r = el.getBoundingClientRect();
	const x = e.clientX - r.left;
	const y = e.clientY - r.top;
	const px = (x / r.width - 0.5) * 2;
	const py = (y / r.height - 0.5) * 2;
	el.style.transform = `perspective(800px) rotateX(${py * -6}deg) rotateY(${px * 6}deg) scale3d(1.02,1.02,1)`;
}

function resetTilt(e: MouseEvent & { currentTarget: HTMLAnchorElement }) {
	e.currentTarget.style.transform = "";
}
</script>

<div>
	<div class="mb-6 flex flex-wrap items-end justify-between gap-3">
		<div>
			<h2 class="bg-gradient-to-r from-[var(--primary)] to-cyan-400 bg-clip-text text-lg font-bold text-transparent">
				功能入口
			</h2>
			<p class="mt-1 text-sm text-75">覆盖“探索-画像-匹配-路径-报告”全链路能力。</p>
		</div>
		<a
			href="/profile/"
			class="inline-flex items-center gap-1 rounded-lg border border-black/10 bg-[var(--card-bg)] px-3 py-1.5 text-xs text-75 transition hover:border-[var(--primary)]/40 hover:text-[var(--primary)] dark:border-white/10"
		>
			先试能力画像
			<Icon icon="material-symbols:arrow-forward-rounded" />
		</a>
	</div>
	<div class="grid auto-rows-fr gap-4 sm:grid-cols-2 lg:grid-cols-3">
		{#each items as item, i (item.href)}
			<a
				href={item.href}
				class="ca-card-tilt group relative flex flex-col overflow-hidden rounded-xl border border-black/10 bg-[var(--card-bg)] p-6 dark:border-white/10 {item.accent
					? 'sm:col-span-2 lg:col-span-2 lg:row-span-1'
					: ''}"
				style="animation-delay: {i * 60}ms"
				onmousemove={tilt}
				onmouseleave={resetTilt}
			>
				<div
					class="pointer-events-none absolute -right-8 -top-8 h-32 w-32 rounded-full bg-[var(--primary)] opacity-[0.12] blur-2xl transition-opacity group-hover:opacity-25"
				></div>
				<div
					class="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl transition-transform duration-300 group-hover:scale-110"
					style={`color: ${item.tone}; background: color-mix(in oklch, ${item.tone} 16%, var(--btn-regular-bg));`}
				>
					<Icon icon={item.icon} class="text-2xl" />
				</div>
				<h3
					class="mb-2 text-lg font-bold"
					style={`color: color-mix(in oklch, ${item.tone} 45%, var(--text-100));`}
				>
					{item.title}
				</h3>
				<p class="text-sm leading-relaxed text-75">{item.desc}</p>
				{#if item.accent}
					<p
						class="mt-2 text-xs"
						style={`color: color-mix(in oklch, ${item.tone} 55%, var(--text-75));`}
					>
						{item.highlight}
					</p>
				{/if}
				<div class="mt-3 rounded-lg border border-black/8 bg-[var(--btn-regular-bg)] p-2.5 text-xs dark:border-white/10">
					<div class="flex items-center justify-between gap-2">
						<span class="text-75">{item.metricLabel}</span>
						<span class="font-semibold" style={`color: ${item.tone};`}>{item.metricValue}</span>
					</div>
					{#if item.accent}
						<div class="mt-1.5 h-1.5 overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
							<div
								class="h-full rounded-full transition-all duration-500"
								style={`background: ${item.tone}; width: ${item.progress}%;`}
							></div>
						</div>
					{/if}
				</div>
				<div class="mt-3 flex flex-wrap gap-1.5">
					{#each item.tags as tag, tagIndex}
						<span
							class="rounded-full px-2 py-0.5 text-[11px]"
							style={`background: color-mix(in oklch, ${item.tone} ${10 + tagIndex * 3}%, var(--btn-regular-bg)); color: color-mix(in oklch, ${item.tone} 58%, var(--text-90));`}
						>
							{tag}
						</span>
					{/each}
				</div>
				<span
					class="mt-4 inline-flex items-center gap-1 text-sm font-medium opacity-80 transition group-hover:opacity-100"
					style={`color: ${item.tone};`}
				>
					进入
					<Icon icon="material-symbols:arrow-forward-rounded" class="transition-transform group-hover:translate-x-1"
					></Icon>
				</span>
			</a>
		{/each}
	</div>
</div>
