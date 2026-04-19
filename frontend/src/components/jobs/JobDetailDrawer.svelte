<script lang="ts">
	import type { JobDetailItem } from "@/lib/jobs";
	import { portal } from "@/lib/portal";

	type Props = {
		open: boolean;
		loading: boolean;
		error: string;
		detail: JobDetailItem | null;
		onClose: () => void;
	};

	let { open, loading, error, detail, onClose }: Props = $props();

	function normalizeText(text: string): string {
		return text.replace(/<br\s*\/?>/gi, "\n").replace(/&nbsp;/gi, " ").trim();
	}
</script>

{#if open}
	<div class="detail-overlay" use:portal role="presentation" onclick={onClose}>
		<div class="detail-drawer" role="dialog" aria-modal="true" onclick={(e) => e.stopPropagation()}>
			<div class="detail-head">
				<h3>{detail?.title || "岗位详情"}</h3>
				<button type="button" class="close-btn" onclick={onClose}>关闭</button>
			</div>

			{#if loading}
				<div class="panel">详情加载中...</div>
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
	.detail-overlay {
		position: fixed;
		inset: 0;
		background: rgba(15, 23, 42, 0.35);
		display: flex;
		align-items: stretch;
		justify-content: flex-end;
		padding: 0;
		z-index: 120;
	}
	.detail-drawer {
		width: min(620px, 92vw);
		height: 100vh;
		overflow: auto;
		border-radius: 0;
		background: var(--card-bg);
		border-left: 1px solid color-mix(in oklab, var(--text-75) 20%, transparent);
		padding: 0 1rem 1.25rem;
		box-shadow: -12px 0 30px rgba(2, 6, 23, 0.15);
		font-family: "FangSong", "STFangsong", "仿宋", serif;
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
	}
	.detail-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.45rem 0.7rem;
		font-size: 0.88rem;
		color: color-mix(in oklab, var(--text-90) 92%, #475569);
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
		color: color-mix(in oklab, var(--primary) 65%, #1e3a8a);
	}
	.detail-section p {
		margin: 0;
		font-size: 0.9rem;
		line-height: 1.95;
		color: color-mix(in oklab, var(--text-90) 88%, #334155);
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
		color: color-mix(in oklab, var(--text-90) 84%, #475569);
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
	@media (max-width: 768px) {
		.detail-drawer {
			width: 100vw;
		}
	}
</style>
