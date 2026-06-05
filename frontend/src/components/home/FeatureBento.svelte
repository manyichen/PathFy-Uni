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
			desc: "按行业、城市、能力标签浏览岗位，快速看懂真实市场需求。",
			icon: "material-symbols:work-outline",
			tone: "#0891b2",
			tags: ["热门岗位", "技能画像", "城市筛选"],
			highlight: "适合先确定方向，也适合比较多个备选岗位。",
			metricLabel: "岗位样本覆盖",
			metricValue: "10,000+",
			progress: 88,
			accent: true,
		},
		{
			href: "/profile/",
			title: "能力画像",
			desc: "上传简历，生成八维就业能力画像和可解释的短板提示。",
			icon: "material-symbols:person-search-outline",
			tone: "#0f766e",
			tags: ["八维雷达", "简历解析", "竞争力评分"],
			highlight: "让自我评估有证据，而不是凭感觉打分。",
			metricLabel: "画像维度",
			metricValue: "8 / 8",
			progress: 92,
		},
		{
			href: "/match/",
			title: "人岗匹配",
			desc: "比较岗位需求与个人能力，定位匹配度和优先补齐项。",
			icon: "material-symbols:compare-arrows-rounded",
			tone: "#2563eb",
			tags: ["权重可调", "匹配解释", "差距诊断"],
			highlight: "把“适不适合”拆成看得见的维度差距。",
			metricLabel: "分析维度",
			metricValue: "4 维",
			progress: 80,
		},
		{
			href: "/graph/",
			title: "职业图谱",
			desc: "查看岗位之间的晋升链、转岗路径与能力迁移关系。",
			icon: "material-symbols:account-tree-outline",
			tone: "#7c3aed",
			tags: ["纵向晋升", "横向转岗", "图谱关系"],
			highlight: "帮助你判断一条路径能不能持续走下去。",
			metricLabel: "路径形态",
			metricValue: "多跳图谱",
			progress: 76,
		},
		{
			href: "/report/",
			title: "生涯报告",
			desc: "根据目标岗位生成阶段行动计划，并支持持续复盘。",
			icon: "material-symbols:article-outline",
			tone: "#d97706",
			tags: ["目标拆解", "行动清单", "报告导出"],
			highlight: "把分析结论沉淀为下一步行动。",
			metricLabel: "计划颗粒度",
			metricValue: "短/中期",
			progress: 84,
		},
		{
			href: "/personality/",
			title: "性格测试",
			desc: "结合 MBTI 结果理解沟通方式、偏好环境和职业适配性。",
			icon: "material-symbols:psychology-outline",
			tone: "#db2777",
			tags: ["性格分析", "职业匹配", "行为洞察"],
			highlight: "适合补充能力画像之外的个人偏好信息。",
			metricLabel: "测试类型",
			metricValue: "16 型",
			progress: 95,
		},
	];
</script>

<section class="space-y-5" aria-labelledby="feature-title">
	<div class="flex flex-wrap items-end justify-between gap-4">
		<div>
			<p class="text-xs font-semibold uppercase text-[var(--primary)]">Start Here</p>
			<h2 id="feature-title" class="mt-2 text-2xl font-bold tracking-normal text-black dark:text-white">
				选择一个入口，直接开始规划
			</h2>
			<p class="mt-2 text-sm leading-6 text-75">
				每个模块都能单独使用，也会在完整流程中互相连接。
			</p>
		</div>
		<a
			href="/profile/"
			class="inline-flex h-10 items-center gap-2 rounded-lg border border-black/10 bg-[var(--card-bg)] px-4 text-sm font-semibold text-black/80 transition hover:border-[var(--primary)]/45 hover:text-[var(--primary)] dark:border-white/10 dark:text-white/80"
		>
			先试能力画像
			<Icon icon="material-symbols:arrow-forward-rounded" class="text-lg" />
		</a>
	</div>

	<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
		{#each items as item (item.href)}
			<a
				href={item.href}
				class="feature-card group flex min-h-[236px] flex-col rounded-lg border border-black/10 p-5 dark:border-white/10"
				class:featured={item.accent}
				style={`--tone: ${item.tone};`}
			>
				<div class="flex items-start justify-between gap-3">
					<div class="feature-icon flex h-11 w-11 items-center justify-center rounded-lg">
						<Icon icon={item.icon} class="text-2xl" />
					</div>
					<div class="rounded-lg bg-[var(--btn-regular-bg)] px-2.5 py-1 text-right">
						<p class="text-[11px] text-75">{item.metricLabel}</p>
						<p class="text-sm font-bold" style="color: var(--tone);">{item.metricValue}</p>
					</div>
				</div>

				<h3 class="mt-4 text-lg font-bold tracking-normal text-black dark:text-white">{item.title}</h3>
				<p class="mt-2 text-sm leading-6 text-75">{item.desc}</p>
				<p class="mt-3 text-xs leading-5" style="color: color-mix(in oklch, var(--tone) 72%, var(--feature-text-base));">
					{item.highlight}
				</p>

				<div class="mt-4 flex flex-wrap gap-1.5">
					{#each item.tags as tag}
						<span class="feature-tag rounded-full px-2 py-0.5 text-[11px]">{tag}</span>
					{/each}
				</div>

				<div class="mt-auto pt-4">
					<div class="h-1.5 overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
						<div
							class="h-full rounded-full"
							style={`width: ${item.progress}%; background: var(--tone);`}
						></div>
					</div>
					<span class="mt-3 inline-flex items-center gap-1 text-sm font-semibold" style="color: var(--tone);">
						进入模块
						<Icon icon="material-symbols:arrow-forward-rounded" class="text-lg transition group-hover:translate-x-1" />
					</span>
				</div>
			</a>
		{/each}
	</div>
</section>

<style>
	.feature-card {
		--feature-text-base: oklch(0.25 0.02 var(--hue));
		background:
			linear-gradient(180deg, color-mix(in oklch, var(--tone) 5%, transparent), transparent 40%),
			var(--card-bg);
		transition:
			transform 180ms ease,
			border-color 180ms ease,
			box-shadow 180ms ease;
	}

	:global(.dark) .feature-card {
		--feature-text-base: white;
	}

	.feature-card.featured {
		background:
			linear-gradient(135deg, color-mix(in oklch, var(--tone) 12%, transparent), transparent 58%),
			var(--card-bg);
	}

	.feature-card:hover {
		transform: translateY(-3px);
		border-color: color-mix(in oklch, var(--tone) 45%, transparent);
		box-shadow: 0 18px 34px -24px color-mix(in oklch, var(--tone) 65%, black);
	}

	.feature-icon {
		color: var(--tone);
		background: color-mix(in oklch, var(--tone) 12%, var(--btn-regular-bg));
	}

	.feature-tag {
		color: color-mix(in oklch, var(--tone) 64%, var(--feature-text-base));
		background: color-mix(in oklch, var(--tone) 10%, var(--btn-regular-bg));
	}
</style>
