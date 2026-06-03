<script lang="ts">
	import { fade, fly } from "svelte/transition";
	import StudentCapabilityRadar from "@/components/match/StudentCapabilityRadar.svelte";
	import type { JobDetailItem } from "@/lib/api/jobs";
	import { portal } from "@/lib/portal";

	type Props = {
		open: boolean;
		loading: boolean;
		error: string;
		detail: JobDetailItem | null;
		onClose: () => void;
		/** 侧栏层级；嵌套在其它弹窗内时需高于父层（默认 120） */
		zIndex?: number;
	};

	let { open, loading, error, detail, onClose, zIndex = 120 }: Props = $props();

	$effect(() => {
		if (typeof document === "undefined") return;
		if (open) {
			document.body.style.overflow = "hidden";
			return () => {
				document.body.style.overflow = "";
			};
		}
		document.body.style.overflow = "";
	});

	function normalizeText(text: string): string {
		return text.replace(/<br\s*\/?>/gi, "\n").replace(/&nbsp;/gi, " ").trim();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (!open) return;
		if (e.key === "Escape") {
			e.preventDefault();
			onClose();
		}
	}

	function confidenceText(value: number): string {
		return `${value.toFixed(2)}%`;
	}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
	<div
		class="detail-overlay"
		style:z-index={zIndex}
		use:portal
		role="presentation"
		transition:fade={{ duration: 180 }}
		onclick={onClose}
	>
		<div class="detail-backdrop" aria-hidden="true"></div>
		<div
			class="detail-drawer"
			role="dialog"
			aria-modal="true"
			aria-busy={loading}
			transition:fly={{ x: 360, duration: 280, opacity: 1, easing: (t) => 1 - Math.pow(1 - t, 3) }}
			onclick={(e) => e.stopPropagation()}
		>
			<div class="detail-head">
				<h3>{detail?.title || "岗位详情"}</h3>
				<button type="button" class="close-btn" onclick={onClose}>关闭</button>
			</div>

			{#if loading}
				<div class="panel loading-panel" aria-live="polite">
					<div class="loading-shimmer" aria-hidden="true"></div>
					<p>详情加载中…</p>
				</div>
			{:else if error}
				<div class="panel error">{error}</div>
			{:else if detail}
				<div class="detail-body">
					<div class="detail-meta">
						<span>🏢 {detail.company || "未知公司"}</span>
						<span>📍 {detail.location || "未知地点"}</span>
						<span>💰 {detail.salary || "薪资面议"}</span>
						{#if detail.experience_text}
							<span>🧭 经验: {detail.experience_text}</span>
						{/if}
						{#if detail.industry}
							<span>🏭 行业: {detail.industry}</span>
						{/if}
					</div>

					{#if detail.scores}
						<section class="detail-section radar-section">
							<h4>八维能力需求</h4>
							<p class="radar-hint">与岗位探索页一致的能力维度（0–100）</p>
							<div class="radar-panel">
								<StudentCapabilityRadar scores={detail.scores} />
							</div>
							<div class="radar-foot">
								<span class="radar-avg">八维均分 {detail.score_avg}</span>
								<span class="radar-conf">平均置信度: {confidenceText(detail.conf_avg)}</span>
							</div>
							<div class="score-band">
								<span>0-39 低要求</span>
								<span>40-59 中等</span>
								<span>60-79 较高</span>
								<span>80-100 核心</span>
							</div>
						</section>
					{/if}

					{#if detail.company_detail}
						<section class="detail-section">
							<h4>公司介绍</h4>
							<p>{normalizeText(detail.company_detail)}</p>
						</section>
					{/if}

					{#if detail.demand}
						<section class="detail-section">
							<h4>岗位职责</h4>
							<p>{normalizeText(detail.demand)}</p>
						</section>
					{/if}

					{#if detail.internship_req}
						<section class="detail-section">
							<h4>实习/任职要求</h4>
							<p>{normalizeText(detail.internship_req)}</p>
						</section>
					{/if}

					{#if detail.requirements?.length}
						<section class="detail-section">
							<h4>关联能力要求</h4>
							<div class="chips">
								{#each detail.requirements.slice(0, 20) as req}
									<span>{req.name}{req.level ? `（${req.level}）` : ""}</span>
								{/each}
							</div>
						</section>
					{/if}

					{#if detail.cap_evidence?.length}
						<section class="detail-section">
							<h4>能力证据片段</h4>
							<ul>
								{#each detail.cap_evidence.slice(0, 6) as ev}
									<li>{ev}</li>
								{/each}
							</ul>
						</section>
					{/if}

					{#if detail.source_url}
						<section class="detail-section">
							<h4>原始链接</h4>
							<a href={detail.source_url} target="_blank" rel="noreferrer">查看原始岗位页面</a>
						</section>
					{/if}
				</div>
			{/if}
		</div>
	</div>
{/if}

<style>
	.panel {
		border-radius: 0.9rem;
		padding: 0.95rem 1rem;
		background: var(--btn-regular-bg);
	}
	.panel.error {
		color: #b91c1c;
		background: rgba(220, 38, 38, 0.08);
	}
	.loading-panel {
		display: grid;
		gap: 0.75rem;
		margin-top: 0.75rem;
	}
	.loading-panel p {
		margin: 0;
		font-size: 0.88rem;
		color: color-mix(in oklab, var(--text-75) 85%, transparent);
	}
	.loading-shimmer {
		height: 4.5rem;
		border-radius: 0.65rem;
		background: linear-gradient(
			90deg,
			color-mix(in oklab, var(--btn-regular-bg) 90%, var(--text-75)) 0%,
			color-mix(in oklab, var(--btn-regular-bg) 60%, white) 50%,
			color-mix(in oklab, var(--btn-regular-bg) 90%, var(--text-75)) 100%
		);
		background-size: 200% 100%;
		animation: shimmer 1.1s ease-in-out infinite;
	}
	@keyframes shimmer {
		0% {
			background-position: 100% 0;
		}
		100% {
			background-position: -100% 0;
		}
	}
	.detail-overlay {
		position: fixed;
		inset: 0;
		display: flex;
		align-items: stretch;
		justify-content: flex-end;
		padding: 0;
		z-index: 120;
	}
	.detail-backdrop {
		position: absolute;
		inset: 0;
		background: rgba(15, 23, 42, 0.4);
		backdrop-filter: blur(2px);
		pointer-events: none;
	}
	.detail-drawer {
		position: relative;
		z-index: 1;
		width: min(620px, 92vw);
		height: 100vh;
		height: 100dvh;
		overflow: auto;
		border-radius: 0;
		background: var(--card-bg);
		border-left: 1px solid color-mix(in oklab, var(--text-75) 20%, transparent);
		padding: 0 1rem 1.25rem;
		box-shadow: -12px 0 30px rgba(2, 6, 23, 0.15);
		font-family: "FangSong", "STFangsong", "仿宋", serif;
		overscroll-behavior: contain;
		-webkit-font-smoothing: antialiased;
		text-rendering: geometricPrecision;
	}
	.detail-head {
		position: sticky;
		top: 0;
		z-index: 2;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.8rem;
		background: var(--card-bg);
		padding-top: 0.7rem;
		padding-bottom: 0.7rem;
		border-bottom: 1px solid color-mix(in oklab, var(--text-75) 16%, transparent);
	}
	.detail-head h3 {
		margin: 0;
		font-size: 1.1rem;
		letter-spacing: 0.02em;
		color: var(--text-100);
	}
	.close-btn {
		height: 2rem;
		padding: 0 0.7rem;
		border-radius: 0.55rem;
		border: 1px solid color-mix(in oklab, var(--text-75) 20%, transparent);
		background: var(--btn-regular-bg);
		color: var(--text-90);
		font-size: 0.78rem;
		font-weight: 600;
	}
	.detail-body {
		margin-top: 0.75rem;
		display: grid;
		gap: 0.85rem;
		animation: body-in 0.22s ease-out;
	}
	@keyframes body-in {
		from {
			opacity: 0;
		}
		to {
			opacity: 1;
		}
	}
	.detail-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.45rem 0.7rem;
		font-size: 0.88rem;
		color: var(--text-90);
		line-height: 1.55;
	}
	.detail-section {
		border-top: 1px dashed color-mix(in oklab, var(--text-75) 18%, transparent);
		padding-top: 0.78rem;
	}
	.detail-section h4 {
		margin: 0 0 0.45rem 0;
		font-size: 0.96rem;
		font-weight: 700;
		letter-spacing: 0.02em;
		color: var(--primary);
	}
	.detail-section p {
		margin: 0;
		font-size: 0.9rem;
		line-height: 1.95;
		color: var(--text-90);
		text-indent: 2em;
		letter-spacing: 0.01em;
		white-space: pre-wrap;
	}
	.detail-section ul {
		margin: 0.1rem 0 0;
		padding-left: 1.2rem;
		display: grid;
		gap: 0.45rem;
		font-size: 0.86rem;
		line-height: 1.7;
		color: var(--text-75);
	}
	.detail-section ul li::marker {
		color: color-mix(in oklab, var(--primary) 72%, #60a5fa);
	}
	.detail-section a {
		font-size: 0.86rem;
		color: color-mix(in oklab, var(--primary) 80%, #1d4ed8);
		text-decoration: underline;
	}
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}
	.chips span {
		font-size: 0.78rem;
		padding: 0.22rem 0.52rem;
		border-radius: 999px;
		background: color-mix(in oklab, var(--primary) 10%, var(--btn-regular-bg));
		color: color-mix(in oklab, var(--primary) 70%, #1e3a8a);
		border: 1px solid color-mix(in oklab, var(--primary) 20%, transparent);
	}
	.radar-section {
		border-top: none;
		padding-top: 0;
	}
	.radar-hint {
		margin: 0 0 0.5rem;
		font-size: 0.78rem;
		color: var(--text-75);
		text-indent: 0;
	}
	.radar-panel {
		border-radius: 0.85rem;
		border: 1px solid color-mix(in oklab, var(--text-75) 14%, transparent);
		background: color-mix(in oklab, var(--btn-regular-bg) 55%, transparent);
		padding: 0.65rem 0.5rem 0.35rem;
	}
	.radar-foot {
		margin-top: 0.55rem;
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem 1rem;
		font-size: 0.8rem;
		color: var(--text-90);
	}
	.radar-avg {
		font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
		font-weight: 700;
		color: var(--primary);
	}
	.score-band {
		margin-top: 0.55rem;
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem 0.55rem;
		font-size: 0.72rem;
		color: var(--text-75);
	}
	@media (max-width: 768px) {
		.detail-drawer {
			width: 100vw;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.detail-body {
			animation: none;
		}
		.loading-shimmer {
			animation: none;
		}
	}
</style>
