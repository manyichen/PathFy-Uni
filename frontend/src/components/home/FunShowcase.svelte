<script lang="ts">
	type Scene = {
		name: string;
		tagline: string;
		desc: string;
		image: string;
		points: string[];
	};

	const scenes: Scene[] = [
		{
			name: "岗位探索模式",
			tagline: "看见真实市场，而不是只看热门词",
			desc: "基于岗位样本与能力标签，把“职位名称”拆成可理解的能力要求、成长空间和转岗可能性。",
			image:
				"https://images.unsplash.com/photo-1523240795612-9a054b0db644?auto=format&fit=crop&w=1200&q=80",
			points: ["岗位要求拆解", "城市与薪资对比", "技能缺口预估"],
		},
		{
			name: "能力画像模式",
			tagline: "从简历到八维雷达，一眼看到优势与短板",
			desc: "上传简历或手动录入后，系统按理论、实践、数字素养等八维输出画像，并给出可执行优化建议。",
			image:
				"https://images.unsplash.com/photo-1513258496099-48168024aec0?auto=format&fit=crop&w=1200&q=80",
			points: ["八维能力雷达", "完整度与竞争力评分", "可解释证据链"],
		},
		{
			name: "生涯路径模式",
			tagline: "把“想法”变成“阶段计划”",
			desc: "结合匹配分析结果自动生成短期/中期行动路径，覆盖学习、项目、实习和成果沉淀四个层次。",
			image:
				"https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?auto=format&fit=crop&w=1200&q=80",
			points: ["分阶段目标", "里程碑计划", "报告一键导出"],
		},
	];

	const floatingTags = [
		"AI 分析",
		"岗位图谱",
		"八维画像",
		"路径规划",
		"动态调整",
		"可解释结果",
	];

	let activeIndex = $state(0);
	const activeScene = $derived(scenes[activeIndex]);
</script>

<section class="fun-wrap rounded-2xl border border-black/10 bg-[var(--card-bg)] p-6 dark:border-white/10 md:p-7">
	<div class="mb-5 flex flex-wrap items-center justify-between gap-3">
		<div>
			<h2 class="bg-gradient-to-r from-[var(--primary)] to-teal-400 bg-clip-text text-xl font-bold text-transparent">
				更有趣的职业规划体验
			</h2>
			<p class="mt-1 text-sm text-75">点击切换场景，感受从探索到行动的完整旅程。</p>
		</div>
		<span class="rounded-full bg-[var(--btn-regular-bg)] px-2.5 py-1 text-xs text-75">Interactive Demo</span>
	</div>

	<div class="grid gap-5 lg:grid-cols-[0.95fr_1.05fr]">
		<div class="space-y-3">
			{#each scenes as scene, i}
				<button
					type="button"
					class="scene-btn w-full rounded-xl border px-4 py-3 text-left transition"
					class:active={i === activeIndex}
					onclick={() => (activeIndex = i)}
				>
					<div class="flex items-center justify-between gap-3">
						<div>
							<p class="text-sm font-semibold text-[var(--primary)]">{scene.name}</p>
							<p class="mt-1 text-xs text-75">{scene.tagline}</p>
						</div>
					</div>
				</button>
			{/each}

			<div class="rounded-xl border border-black/8 bg-[var(--btn-regular-bg)] p-4 text-sm leading-6 text-75 dark:border-white/10">
				{activeScene.desc}
			</div>
		</div>

		<div class="relative overflow-hidden rounded-2xl border border-black/10 dark:border-white/10">
			<img
				src={activeScene.image}
				alt={activeScene.name}
				class="h-[320px] w-full object-cover"
				loading="lazy"
				decoding="async"
			/>
			<div class="absolute inset-0 bg-gradient-to-t from-black/55 via-black/20 to-transparent"></div>
			<div class="absolute bottom-0 left-0 right-0 p-4 text-white">
				<p class="text-sm font-semibold">{activeScene.name}</p>
				<ul class="mt-2 flex flex-wrap gap-2 text-xs">
					{#each activeScene.points as point}
						<li class="rounded-full bg-white/20 px-2 py-0.5 backdrop-blur">{point}</li>
					{/each}
				</ul>
			</div>
			<div class="pointer-events-none absolute left-3 top-3 rounded-full bg-white/85 px-2 py-1 text-[11px] text-black">
				AI Career Compass
			</div>
		</div>
	</div>

	<div class="tag-marquee mt-5" aria-hidden="true">
		<div class="track">
			{#each [...floatingTags, ...floatingTags] as tag}
				<span class="tag-pill">{tag}</span>
			{/each}
		</div>
	</div>
</section>

<style>
	.scene-btn {
		border-color: rgb(0 0 0 / 0.1);
		background: color-mix(in oklch, var(--card-bg) 85%, transparent);
	}
	.scene-btn:hover {
		transform: translateY(-1px);
		border-color: color-mix(in oklch, var(--primary) 35%, black 10%);
	}
	.scene-btn.active {
		border-color: color-mix(in oklch, var(--primary) 45%, black 5%);
		box-shadow: 0 0 0 1px color-mix(in oklch, var(--primary) 25%, transparent);
		background: color-mix(in oklch, var(--primary) 10%, var(--card-bg));
	}
	:global(.dark) .scene-btn {
		border-color: rgb(255 255 255 / 0.14);
	}
	.tag-marquee {
		overflow: hidden;
		white-space: nowrap;
		mask-image: linear-gradient(to right, transparent, black 8%, black 92%, transparent);
	}
	.track {
		display: inline-flex;
		gap: 0.5rem;
		min-width: 100%;
		animation: move 18s linear infinite;
	}
	.tag-pill {
		border-radius: 999px;
		padding: 0.35rem 0.7rem;
		font-size: 0.75rem;
		background: var(--btn-regular-bg);
		color: color-mix(in oklch, var(--text-90) 88%, black 10%);
	}
	@keyframes move {
		from {
			transform: translateX(0);
		}
		to {
			transform: translateX(-50%);
		}
	}
</style>
