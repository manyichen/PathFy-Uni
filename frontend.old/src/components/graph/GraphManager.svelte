<script lang="ts">
	import { onMount } from "svelte";
	import { isLoggedIn } from "@/lib/api/jobs";
	import {
		fetchGraphStats,
		importJobs,
		syncJobTitles,
		generatePromotionPaths,
		type GraphStats,
		type ImportResult,
		type SyncResult,
	} from "@/lib/api/graph";

	// ============================================================
	// 状态
	// ============================================================

	let statsLoading = $state(true);
	let statsError = $state("");
	let stats = $state<GraphStats | null>(null);

	let importLoading = $state(false);
	let importError = $state("");
	let importResult = $state<ImportResult | null>(null);
	let selectedFile = $state<File | null>(null);
	let batchSize = $state(128);
	let clearAll = $state(false);

	let syncLoading = $state("");
	let syncError = $state("");
	let syncResult = $state<SyncResult | null>(null);
	let syncDryRun = $state(true);

	// ============================================================
	// 初始化
	// ============================================================

	onMount(() => {
		if (!isLoggedIn()) {
			statsError = "请先登录后再访问图谱管理。";
			statsLoading = false;
			return;
		}
		loadStats();
	});

	async function loadStats(): Promise<void> {
		statsLoading = true;
		statsError = "";
		try {
			stats = await fetchGraphStats();
		} catch (e) {
			statsError = e instanceof Error ? e.message : "获取统计失败";
		} finally {
			statsLoading = false;
		}
	}

	// ============================================================
	// 岗位导入
	// ============================================================

	function onFileChange(e: Event): void {
		const input = e.target as HTMLInputElement;
		if (input.files?.[0]) {
			selectedFile = input.files[0];
		}
	}

	async function handleImport(): Promise<void> {
		if (!selectedFile) {
			importError = "请先选择 Excel 文件";
			return;
		}
		importLoading = true;
		importError = "";
		importResult = null;
		try {
			importResult = await importJobs(selectedFile, batchSize, clearAll);
			await loadStats();
		} catch (e) {
			importError = e instanceof Error ? e.message : "导入失败";
		} finally {
			importLoading = false;
		}
	}

	async function runSync(label: string, fn: (dry: boolean) => Promise<SyncResult>): Promise<void> {
		syncLoading = label;
		syncError = "";
		syncResult = null;
		try {
			syncResult = await fn(syncDryRun);
			await loadStats();
		} catch (e) {
			syncError = e instanceof Error ? e.message : `${label}失败`;
		} finally {
			syncLoading = "";
		}
	}
</script>

<section class="graph-manager">
	<!-- ==============================================
	图谱统计
	============================================== -->
	<div class="card">
		<div class="card-header">
			<h2>图谱统计</h2>
			<button class="btn-sm ghost" onclick={loadStats} disabled={statsLoading}>
				{statsLoading ? "刷新中..." : "刷新"}
			</button>
		</div>

		{#if statsLoading}
			<div class="status">正在加载图谱统计...</div>
		{:else if statsError}
			<div class="status error">{statsError}</div>
		{:else if stats}
			<div class="stats-grid">
				<div class="stat-item">
					<span class="stat-value">{stats.job_count}</span>
					<span class="stat-label">岗位 (Job)</span>
				</div>
				<div class="stat-item">
					<span class="stat-value">{stats.company_count}</span>
					<span class="stat-label">公司 (Company)</span>
				</div>
				<div class="stat-item">
					<span class="stat-value">{stats.skill_count}</span>
					<span class="stat-label">硬技能 (Skill)</span>
				</div>
				<div class="stat-item">
					<span class="stat-value">{stats.certificate_count}</span>
					<span class="stat-label">证书 (Certificate)</span>
				</div>
				<div class="stat-item">
					<span class="stat-value">{stats.softskill_count}</span>
					<span class="stat-label">软技能 (SoftSkill)</span>
				</div>
				<div class="stat-item">
					<span class="stat-value">{stats.careerlevel_count}</span>
					<span class="stat-label">职级 (CareerLevel)</span>
				</div>
				<div class="stat-item">
					<span class="stat-value">{stats.belongs_to_count}</span>
					<span class="stat-label">归属关系</span>
				</div>
				<div class="stat-item">
					<span class="stat-value">{stats.requires_count}</span>
					<span class="stat-label">需求关系</span>
				</div>
				<div class="stat-item">
					<span class="stat-value">{stats.vertical_up_count}</span>
					<span class="stat-label">晋升关系</span>
				</div>
			</div>
		{/if}
	</div>

	<!-- ==============================================
	岗位导入
	============================================== -->
	<div class="card">
		<div class="card-header">
			<h2>岗位导入</h2>
			<span class="sub">从 Excel (.xls) 导入招聘数据，通过大模型提取结构化字段</span>
		</div>

		<div class="form-row">
			<label class="form-label">Excel 文件</label>
			<input type="file" accept=".xls,.xlsx" onchange={onFileChange} class="file-input" />
			{#if selectedFile}
				<span class="file-name">{selectedFile.name} ({Math.round(selectedFile.size / 1024)} KB)</span>
			{/if}
		</div>

		<div class="form-row">
			<label class="form-label" for="batch-size">批次大小</label>
			<input id="batch-size" type="number" bind:value={batchSize} min="8" max="512" class="num-input" />
		</div>

		<div class="form-row">
			<label class="form-label" for="clear-all-sw">
				<input id="clear-all-sw" type="checkbox" bind:checked={clearAll} />
				导入前清空图谱
			</label>
		</div>

		<div class="card-actions">
			<button class="btn primary" onclick={handleImport} disabled={importLoading || !selectedFile}>
				{importLoading ? "导入中..." : "开始导入"}
			</button>
		</div>

		{#if importError}
			<div class="status error">{importError}</div>
		{/if}
		{#if importResult}
			<div class="result">
				<p>共 <strong>{importResult.total_jobs}</strong> 条，完成 <strong>{importResult.batches_completed}</strong> 批，失败 <strong>{importResult.batches_failed}</strong> 批</p>
				{#if importResult.core_templates.length > 0}
					<p>核心模板岗位：{importResult.core_templates.join("、")}</p>
				{/if}
				{#if importResult.errors.length > 0}
					<div class="status error">
						{#each importResult.errors as err}
							<div>{err}</div>
						{/each}
					</div>
				{/if}
			</div>
		{/if}
	</div>

	<!-- ==============================================
	JobTitle 晋升路径
	============================================== -->
	<div class="card">
		<div class="card-header">
			<h2>JobTitle 晋升路径</h2>
			<span class="sub">先把 Job 聚合到 JobTitle，再生成 JobPromotion 阶段化路径</span>
		</div>

		<div class="form-row">
			<label class="form-label" for="sync-dry-run-sw">
				<input id="sync-dry-run-sw" type="checkbox" bind:checked={syncDryRun} />
				预览模式（dry run，不写入数据库）
			</label>
		</div>

		<div class="card-actions sync-buttons">
			<button class="btn" onclick={() => runSync("同步 JobTitle", syncJobTitles)} disabled={!!syncLoading}>
				{syncLoading === "同步 JobTitle" ? "同步中..." : "同步 JobTitle"}
			</button>
			<button class="btn primary" onclick={() => runSync("生成 JobTitle 晋升路径", generatePromotionPaths)} disabled={!!syncLoading}>
				{syncLoading === "生成 JobTitle 晋升路径" ? "生成中..." : syncDryRun ? "预览晋升路径" : "生成晋升路径"}
			</button>
		</div>

		{#if syncError}
			<div class="status error">{syncError}</div>
		{/if}
		{#if syncResult}
			<div class="result">
				<p>执行结果</p>
				<pre class="result-json">{JSON.stringify(syncResult, null, 2)}</pre>
			</div>
		{/if}
	</div>
</section>

<style>
	.graph-manager {
		max-width: 860px;
		margin: 0 auto;
		display: flex;
		flex-direction: column;
		gap: 1.4rem;
	}

	.card {
		padding: 1.4rem;
		border: 1px solid rgba(15, 23, 42, 0.08);
		border-radius: 1rem;
		background: var(--card-bg);
	}

	.card-header {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		margin-bottom: 0.8rem;
	}

	.card-header h2 {
		margin: 0;
		font-size: 1.25rem;
		font-weight: 700;
		color: var(--text-100);
	}

	.sub {
		color: var(--text-75);
		font-size: 0.88rem;
	}

	.status {
		margin-top: 0.8rem;
		padding: 0.7rem 0.9rem;
		border-radius: 0.7rem;
		background: rgba(99, 102, 241, 0.1);
		color: #3730a3;
		font-size: 0.9rem;
	}

	.status.error {
		background: rgba(220, 38, 38, 0.1);
		color: #b91c1c;
	}

	.stats-grid {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 0.7rem;
		margin-top: 0.4rem;
	}

	.stat-item {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 0.7rem;
		border-radius: 0.7rem;
		background: var(--btn-regular-bg);
	}

	.stat-value {
		font-size: 1.5rem;
		font-weight: 700;
		color: var(--text-100);
	}

	.stat-label {
		font-size: 0.78rem;
		color: var(--text-75);
		margin-top: 0.2rem;
	}

	.form-row {
		margin-top: 0.8rem;
		display: flex;
		align-items: center;
		gap: 0.7rem;
		flex-wrap: wrap;
	}

	.form-label {
		color: var(--text-90);
		font-size: 0.9rem;
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		cursor: pointer;
	}

	.file-input {
		font-size: 0.85rem;
	}

	.file-name {
		font-size: 0.82rem;
		color: var(--text-75);
	}

	.num-input {
		width: 6rem;
		padding: 0.3rem 0.5rem;
		border: 1px solid rgba(15, 23, 42, 0.12);
		border-radius: 0.4rem;
		font-size: 0.88rem;
		background: var(--btn-regular-bg);
		color: var(--text-100);
	}

	.card-actions {
		margin-top: 1rem;
	}

	.sync-buttons {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}

	.btn {
		border: none;
		cursor: pointer;
		border-radius: 0.6rem;
		padding: 0.55rem 1rem;
		font-size: 0.9rem;
		font-weight: 600;
	}

	.btn.primary {
		color: white;
		background: #4f46e5;
	}

	.btn.primary:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.btn-sm {
		border: none;
		cursor: pointer;
		border-radius: 0.4rem;
		padding: 0.3rem 0.6rem;
		font-size: 0.82rem;
	}

	.btn-sm.ghost {
		color: var(--text-75);
		background: var(--btn-regular-bg);
	}

	.result {
		margin-top: 0.8rem;
		padding: 0.7rem 0.9rem;
		border-radius: 0.7rem;
		background: rgba(16, 185, 129, 0.08);
		color: var(--text-90);
		font-size: 0.9rem;
		line-height: 1.6;
	}

	.result strong {
		color: var(--text-100);
	}
</style>
