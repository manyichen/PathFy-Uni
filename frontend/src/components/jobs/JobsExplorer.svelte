<script lang="ts">
	import { onMount } from "svelte";
	import { fetchJobs, type JobCardItem } from "@/lib/jobs";

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
	const RADAR_TIERS = [0.25, 0.5, 0.75, 1];
	const RADAR_CX = 140;
	const RADAR_CY = 120;
	const RADAR_MAX_R = 88;
	const RADAR_LABEL_R = 110;

	let loading = $state(true);
	let q = $state("");
	let jobs = $state<JobCardItem[]>([]);
	let errorMessage = $state("");

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

	function calcPoints(job: JobCardItem): string {
		const points = DIMENSIONS.map((d, idx) => {
			const p = point(idx, job.scores[d.key]);
			const x = p.x;
			const y = p.y;
			return `${x.toFixed(2)},${y.toFixed(2)}`;
		});
		return points.join(" ");
	}

	function calcGridPointsByTier(tier: number): string {
		const points = DIMENSIONS.map((_, idx) => {
			const p = point(idx, 100 * tier);
			const x = p.x;
			const y = p.y;
			return `${x.toFixed(2)},${y.toFixed(2)}`;
		});
		return points.join(" ");
	}

	function axisEnd(idx: number) {
		const p = point(idx, 100);
		return {
			x: p.x,
			y: p.y,
		};
	}

	function labelPos(idx: number) {
	const p = pointByRadius(idx, RADAR_LABEL_R);
		return {
			x: p.x,
			y: p.y,
		};
	}

	function scoreTone(avg: number): string {
		if (avg >= 75) return "high";
		if (avg >= 55) return "mid";
		return "low";
	}

	async function loadJobs(keyword = ""): Promise<void> {
		loading = true;
		errorMessage = "";
		try {
			jobs = await fetchJobs(keyword, 72);
		} catch (e) {
			errorMessage = e instanceof Error ? e.message : "加载岗位数据失败";
		} finally {
			loading = false;
		}
	}

	function onSearchSubmit(e: SubmitEvent): void {
		e.preventDefault();
		void loadJobs(q);
	}

	onMount(() => {
		void loadJobs();
	});
</script>

<section class="space-y-5">
	<form class="search-row" onsubmit={onSearchSubmit}>
		<input bind:value={q} type="text" placeholder="搜索岗位/公司/地点（例如 实施工程师、合肥）" />
		<button type="submit">搜索</button>
	</form>

	<div class="jobs-layout">
		<div class="jobs-main">
			{#if loading}
				<div class="panel">岗位数据加载中...</div>
			{:else if errorMessage}
				<div class="panel error">{errorMessage}</div>
			{:else if jobs.length === 0}
				<div class="panel">暂无匹配岗位，换个关键词试试。</div>
			{:else}
				<div class="grid-wrap">
					{#each jobs as job}
						<article class="job-card">
							<div class="head">
								<h3>{job.title}</h3>
								<span class="score-badge {scoreTone(job.score_avg)}">{job.score_avg}</span>
							</div>

							<div class="meta">
								<span>💰 {job.salary}</span>
								<span>🏢 {job.company}</span>
								<span>📍 {job.location}</span>
							</div>

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
									<polygon points={calcPoints(job)} class="data-layer" />
									{#each DIMENSIONS as d, i}
										{@const p = labelPos(i)}
										<text
											x={p.x}
											y={p.y}
											class="axis-label fill-black/60 text-[9px] dark:fill-white/70"
											text-anchor="middle"
											dominant-baseline="middle"
											aria-label={`${d.full} ${job.scores[d.key]} 分`}
										>
											<tspan x={p.x} dy="-0.2em">{d.label}</tspan>
											<tspan x={p.x} dy="1.2em" class="score-text">{job.scores[d.key]}</tspan>
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

							{#if job.risk_flags?.length}
								<div class="flags">
									{#each job.risk_flags.slice(0, 2) as flag}
										<span>{flag}</span>
									{/each}
								</div>
							{/if}
						</article>
					{/each}
				</div>
			{/if}
		</div>

		<aside class="assistant-col">
			<div class="assistant-card chat-card">
				<div class="chat-head">
					<h3>AI 对话助手</h3>
					<span class="chat-status">在线</span>
				</div>
				<div class="chat-body">
					<div class="message ai">
						<div class="avatar ai">AI</div>
						<div class="bubble">
							你好，我可以帮你解读岗位要求、分析能力差距，并给出下一步行动建议。
						</div>
					</div>
					<div class="message user">
						<div class="bubble">请帮我分析“实施工程师”最关键的 3 项能力。</div>
						<div class="avatar user">我</div>
					</div>
					<div class="message ai">
						<div class="avatar ai">AI</div>
						<div class="bubble">
							已为你提取：1) 专业实践技能 2) 团队协作能力 3) 数字素养。后续可展开生成学习计划。
						</div>
					</div>
				</div>
				<div class="chat-input-wrap">
					<input type="text" placeholder="输入你想咨询的问题（功能待接入）" disabled />
					<button type="button" disabled>发送</button>
				</div>
			</div>
		</aside>
	</div>
</section>

<style>
	.search-row {
		display: flex;
		gap: 0.6rem;
	}
	.search-row input {
		flex: 1;
		height: 2.8rem;
		border-radius: 0.75rem;
		border: 1px solid color-mix(in oklab, var(--text-75) 28%, transparent);
		padding: 0 0.85rem;
		background: var(--card-bg);
	}
	.search-row button {
		height: 2.8rem;
		padding: 0 1.1rem;
		border-radius: 0.75rem;
		border: none;
		background: var(--primary);
		color: white;
		font-weight: 600;
	}
	.panel {
		border-radius: 0.9rem;
		padding: 0.95rem 1rem;
		background: var(--btn-regular-bg);
	}
	.panel.error {
		color: #b91c1c;
		background: rgba(220, 38, 38, 0.08);
	}
	.grid-wrap {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 1.2rem;
	}
	.jobs-layout {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 320px;
		gap: 1rem;
		align-items: start;
	}
	.jobs-main {
		min-width: 0;
	}
	.assistant-col {
		position: sticky;
		top: 1rem;
	}
	.assistant-card {
		border: 1px solid color-mix(in oklab, var(--text-75) 20%, transparent);
		border-radius: 1rem;
		padding: 1rem;
		background: var(--card-bg);
		box-shadow: 0 8px 20px rgba(2, 6, 23, 0.06);
	}
	.assistant-card h3 {
		margin: 0;
		font-size: 1rem;
		font-weight: 700;
		color: var(--text-100);
	}
	.chat-card {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.chat-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}
	.chat-status {
		font-size: 0.72rem;
		padding: 0.15rem 0.45rem;
		border-radius: 999px;
		background: rgba(34, 197, 94, 0.12);
		color: #166534;
	}
	.chat-body {
		display: flex;
		flex-direction: column;
		gap: 0.7rem;
		max-height: 560px;
		min-height: 560px;
		overflow: auto;
		padding-right: 0.15rem;
	}
	.message {
		display: flex;
		gap: 0.5rem;
		align-items: flex-start;
	}
	.message.user {
		justify-content: flex-end;
	}
	.avatar {
		flex: 0 0 1.8rem;
		width: 1.8rem;
		height: 1.8rem;
		border-radius: 999px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		font-size: 0.68rem;
		font-weight: 700;
	}
	.avatar.ai {
		background: color-mix(in oklab, var(--primary) 22%, var(--btn-regular-bg));
		color: color-mix(in oklab, var(--primary) 82%, #0f172a);
	}
	.avatar.user {
		background: color-mix(in oklab, #38bdf8 20%, var(--btn-regular-bg));
		color: #0369a1;
	}
	.bubble {
		font-size: 0.82rem;
		line-height: 1.5;
		padding: 0.55rem 0.65rem;
		border-radius: 0.7rem;
		max-width: 82%;
		word-break: break-word;
	}
	.message.ai .bubble {
		background: color-mix(in oklab, var(--btn-regular-bg) 82%, transparent);
		color: var(--text-90);
		border: 1px solid color-mix(in oklab, var(--text-75) 15%, transparent);
	}
	.message.user .bubble {
		background: color-mix(in oklab, var(--primary) 14%, transparent);
		color: color-mix(in oklab, var(--text-100) 85%, transparent);
	}
	.chat-input-wrap {
		display: grid;
		grid-template-columns: 1fr auto;
		gap: 0.45rem;
	}
	.chat-input-wrap input {
		height: 2.2rem;
		border-radius: 0.6rem;
		border: 1px solid color-mix(in oklab, var(--text-75) 25%, transparent);
		background: var(--btn-regular-bg);
		padding: 0 0.65rem;
		font-size: 0.8rem;
	}
	.chat-input-wrap button {
		height: 2.2rem;
		border-radius: 0.6rem;
		border: none;
		padding: 0 0.8rem;
		font-size: 0.78rem;
		font-weight: 600;
		background: color-mix(in oklab, var(--primary) 45%, #94a3b8);
		color: white;
		opacity: 0.75;
	}
	.job-card {
		border: 1px solid color-mix(in oklab, var(--text-75) 20%, transparent);
		border-radius: 1rem;
		padding: 1.2rem;
		background: var(--card-bg);
		box-shadow: 0 8px 22px rgba(2, 6, 23, 0.06);
	}
	.head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
	}
	.head h3 {
		margin: 0;
		font-size: 1.05rem;
		font-weight: 700;
		color: var(--text-100);
	}
	.score-badge {
		min-width: 2.75rem;
		text-align: center;
		border-radius: 999px;
		padding: 0.15rem 0.55rem;
		font-size: 0.78rem;
		font-weight: 700;
	}
	.score-badge.high {
		background: rgba(34, 197, 94, 0.15);
		color: #166534;
	}
	.score-badge.mid {
		background: rgba(59, 130, 246, 0.15);
		color: #1d4ed8;
	}
	.score-badge.low {
		background: rgba(245, 158, 11, 0.15);
		color: #92400e;
	}
	.meta {
		display: grid;
		gap: 0.25rem;
		margin-top: 0.7rem;
		color: var(--text-75);
		font-size: 0.87rem;
	}
	.radar-row {
		margin-top: 0.8rem;
		display: block;
	}
	.radar {
		width: 100%;
		max-width: 360px;
		height: auto;
		display: block;
		margin: 0 auto;
	}
	.radar .grid-layer {
		fill: none;
		stroke-width: 1;
	}
	.radar .axis-line {
		stroke-width: 1;
	}
	.radar .data-layer {
		fill: color-mix(in oklch, var(--primary) 35%, transparent);
		stroke: var(--primary);
		stroke-width: 2;
	}
	.radar .axis-label {
		pointer-events: none;
	}
	.radar .score-text {
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
	.flags {
		margin-top: 0.75rem;
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}
	.flags span {
		font-size: 0.75rem;
		padding: 0.2rem 0.48rem;
		border-radius: 999px;
		background: color-mix(in oklab, var(--btn-regular-bg) 80%, transparent);
		color: var(--text-75);
	}
	@media (max-width: 768px) {
		.jobs-layout {
			grid-template-columns: 1fr;
		}
		.assistant-col {
			position: static;
		}
		.grid-wrap {
			grid-template-columns: 1fr;
		}
		.radar {
			max-width: 320px;
		}
	}
</style>
