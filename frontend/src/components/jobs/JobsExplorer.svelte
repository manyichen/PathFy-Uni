<script lang="ts">
	import { onMount } from "svelte";
	import {
		chatJobsAssistant,
		fetchJobDetail,
		fetchJobs,
		getAssistantSessionDetail,
		isLoggedIn,
		listAssistantSessions,
		saveAssistantMessage,
		type AssistantMessageItem,
		type AssistantSessionItem,
		type JobCardItem,
		type JobDetailItem,
	} from "@/lib/jobs";
	import { getToken } from "@/lib/auth";
	import JobDetailDrawer from "./JobDetailDrawer.svelte";
	import {
		RADAR_DIMENSIONS as DIMENSIONS,
		RADAR_TIERS,
		RADAR_CX,
		RADAR_CY,
		calcRadarPolygonPoints as calcPoints,
		calcRadarGridPolygon as calcGridPointsByTier,
		radarAxisEnd as axisEnd,
		radarLabelPos as labelPos,
	} from "@/lib/radar-geometry";
	const ROWS_PER_PAGE = 20;
	const CARDS_PER_ROW = 2;
	const PAGE_SIZE = ROWS_PER_PAGE * CARDS_PER_ROW;
	const AI_LOADING_PLACEHOLDER = "__AI_LOADING__";
	/** 用户点了「新对话」后刷新仍应保持空白会话，避免再自动打开列表里第一条历史 */
	const NEW_CHAT_DRAFT_LS_KEY = "jobsExplorerAiNewChatDraft";
	const NEW_CHAT_DRAFT_VALUE = "1";

	function markNewChatDraft(): void {
		if (typeof localStorage === "undefined") return;
		localStorage.setItem(NEW_CHAT_DRAFT_LS_KEY, NEW_CHAT_DRAFT_VALUE);
	}

	function clearNewChatDraft(): void {
		if (typeof localStorage === "undefined") return;
		localStorage.removeItem(NEW_CHAT_DRAFT_LS_KEY);
	}

	function isNewChatDraftPreferred(): boolean {
		if (typeof localStorage === "undefined") return false;
		return localStorage.getItem(NEW_CHAT_DRAFT_LS_KEY) === NEW_CHAT_DRAFT_VALUE;
	}

	let loading = $state(true);
	let q = $state("");
	let jobs = $state<JobCardItem[]>([]);
	let errorMessage = $state("");
	let currentPage = $state(1);
	let totalCount = $state(0);
	let totalPagesState = $state(1);
	let jumpToIndexInput = $state("");
	let jumpToPageInput = $state("");
	let detailVisible = $state(false);
	let detailLoading = $state(false);
	let detailError = $state("");
	let detailData = $state<JobDetailItem | null>(null);
	let assistantLoading = $state(false);
	let assistantError = $state("");
	let assistantSending = $state(false);
	let sessions = $state<AssistantSessionItem[]>([]);
	let currentSessionId = $state<number | null>(null);
	let historyPickerOpen = $state(false);
	let messages = $state<AssistantMessageItem[]>([]);
	let assistantInput = $state("");
	let saveMessageState = $state<Record<number, "idle" | "saving" | "saved">>({});

	let totalPages = $derived(Math.max(1, totalPagesState));
	let pageInfoText = $derived(`第 ${currentPage} / ${totalPages} 页 · 共 ${totalCount} 条`);

	function goToPage(page: number): void {
		if (page < 1 || page > totalPages || page === currentPage || loading) return;
		void loadJobs(q, page);
	}

	function onJumpToIndex(e: SubmitEvent): void {
		e.preventDefault();
		if (loading || totalCount <= 0) return;
		const target = Number(jumpToIndexInput);
		if (!Number.isFinite(target)) return;
		const safeIndex = Math.min(totalCount, Math.max(1, Math.floor(target)));
		const targetPage = Math.ceil(safeIndex / PAGE_SIZE);
		void loadJobs(q, targetPage);
		jumpToIndexInput = String(safeIndex);
	}

	function onJumpToPage(e: SubmitEvent): void {
		e.preventDefault();
		if (loading || totalPages <= 0) return;
		const target = Number(jumpToPageInput);
		if (!Number.isFinite(target)) return;
		const safePage = Math.min(totalPages, Math.max(1, Math.floor(target)));
		void loadJobs(q, safePage);
		jumpToPageInput = String(safePage);
	}

	function scoreTone(avg: number): string {
		if (avg >= 75) return "high";
		if (avg >= 55) return "mid";
		return "low";
	}

	function confidenceText(value: number): string {
		return `${value.toFixed(2)}%`;
	}

	async function loadJobs(keyword = "", page = 1): Promise<void> {
		loading = true;
		errorMessage = "";
		try {
			const res = await fetchJobs({ q: keyword, page, pageSize: PAGE_SIZE });
			jobs = res.jobs;
			totalCount = res.total;
			totalPagesState = res.totalPages;
			currentPage = res.page;
		} catch (e) {
			errorMessage = e instanceof Error ? e.message : "加载岗位数据失败";
			jobs = [];
			totalCount = 0;
			totalPagesState = 1;
			currentPage = 1;
		} finally {
			loading = false;
		}
	}

	function onSearchSubmit(e: SubmitEvent): void {
		e.preventDefault();
		void loadJobs(q, 1);
	}

	async function openDetail(jobId: string): Promise<void> {
		detailVisible = true;
		detailLoading = true;
		detailError = "";
		detailData = null;
		try {
			detailData = await fetchJobDetail(jobId);
		} catch (e) {
			detailError = e instanceof Error ? e.message : "加载岗位详情失败";
		} finally {
			detailLoading = false;
		}
	}

	function closeDetail(): void {
		detailVisible = false;
	}

	async function loadSessionDetail(sessionId: number): Promise<void> {
		assistantError = "";
		try {
			console.log("检查登录状态...");
			console.log("是否登录:", isLoggedIn());
			console.log("令牌:", getToken());
			
			if (!isLoggedIn()) {
				assistantError = "请先登录后再使用 AI 助手";
				return;
			}
			
			console.log("开始加载会话详情...");
			console.log("会话ID:", sessionId);
			
			const detail = await getAssistantSessionDetail(sessionId);
			console.log("会话详情加载成功:", detail);
			clearNewChatDraft();
			currentSessionId = detail.session.id;
			historyPickerOpen = false;
			messages = detail.messages;
			if (detail.jobs?.length) {
				jobs = detail.jobs;
				totalCount = detail.jobs.length;
				totalPagesState = 1;
				currentPage = 1;
			}
			sessions = sessions.map((item) =>
				item.id === sessionId ? detail.session : item,
			);
		} catch (e) {
			console.error("加载历史会话失败:", e);
			assistantError = e instanceof Error ? e.message : "加载历史会话失败";
		}
	}

	async function loadAssistantSessions(): Promise<void> {
		assistantLoading = true;
		assistantError = "";
		try {
			console.log("检查登录状态...");
			console.log("是否登录:", isLoggedIn());
			console.log("令牌:", getToken());
			
			if (!isLoggedIn()) {
				assistantError = "请先登录后再使用 AI 助手";
				currentSessionId = null;
				messages = [];
				return;
			}
			
			console.log("开始加载会话...");
			sessions = await listAssistantSessions();
			console.log("会话加载成功:", sessions);
			if (isNewChatDraftPreferred()) {
				currentSessionId = null;
				messages = [];
				return;
			}
			if (sessions.length > 0) {
				await loadSessionDetail(sessions[0].id);
			} else {
				currentSessionId = null;
				messages = [];
			}
		} catch (e) {
			console.error("加载 AI 会话失败:", e);
			assistantError = e instanceof Error ? e.message : "加载 AI 会话失败";
		} finally {
			assistantLoading = false;
		}
	}

	async function refreshSessionsListOnly(): Promise<void> {
		console.log("检查登录状态...");
		console.log("是否登录:", isLoggedIn());
		console.log("令牌:", getToken());
		
		if (!isLoggedIn()) {
			return;
		}
		try {
			console.log("开始刷新会话列表...");
			sessions = await listAssistantSessions();
			console.log("会话列表刷新成功:", sessions);
		} catch (e) {
			console.error("刷新会话列表失败:", e);
			// 不阻塞主流程，保留当前界面状态
		}
	}

	async function sendAssistantMessage(e: SubmitEvent): Promise<void> {
		e.preventDefault();
		const message = assistantInput.trim();
		if (!message || assistantSending) return;
		
		console.log("检查登录状态...");
		console.log("是否登录:", isLoggedIn());
		console.log("令牌:", getToken());
		
		if (!isLoggedIn()) {
			assistantError = "请先登录后再使用 AI 助手";
			return;
		}
		
		assistantSending = true;
		assistantError = "";
		const optimisticUserId = -Date.now();
		const optimisticAssistantId = -(Date.now() + 1);
		assistantInput = "";
		messages = [
			...messages,
			{
				id: optimisticUserId,
				role: "user",
				content: message,
				filters_json: {},
				result_job_ids_json: [],
				is_saved: false,
			},
			{
				id: optimisticAssistantId,
				role: "assistant",
				content: AI_LOADING_PLACEHOLDER,
				filters_json: {},
				result_job_ids_json: [],
				is_saved: false,
			},
		];
		try {
			console.log("开始发送消息...");
			console.log("消息内容:", message);
			console.log("会话ID:", currentSessionId);
			
			const res = await chatJobsAssistant({
				message,
				sessionId: currentSessionId ?? undefined,
			});
			console.log("消息发送成功:", res);
			
			currentSessionId = res.session_id;
			clearNewChatDraft();
			messages = messages.map((item) => {
				if (item.id === optimisticUserId) {
					return {
						...item,
						id: res.user_message.id,
						content: res.user_message.content,
					};
				}
				if (item.id === optimisticAssistantId) {
					return {
						...item,
						id: res.assistant_message.id,
						content: res.assistant_message.content,
						filters_json: (res.filters || {}) as Record<string, unknown>,
						result_job_ids_json: res.jobs.map((job) => job.id),
					};
				}
				return item;
			});
			jobs = res.jobs;
			totalCount = res.jobs.length;
			totalPagesState = 1;
			currentPage = 1;
			await refreshSessionsListOnly();
		} catch (e) {
			console.error("发送消息失败:", e);
			assistantError = e instanceof Error ? e.message : "发送消息失败";
			messages = messages.map((item) => {
				if (item.id === optimisticAssistantId) {
					return {
						...item,
						content: "请求失败，请重试。",
					};
				}
				return item;
			});
		} finally {
			assistantSending = false;
		}
	}

	async function onSaveAssistantMessage(messageId: number): Promise<void> {
		if (saveMessageState[messageId] === "saving") return;
		
		console.log("检查登录状态...");
		console.log("是否登录:", isLoggedIn());
		console.log("令牌:", getToken());
		
		if (!isLoggedIn()) {
			assistantError = "请先登录后再使用 AI 助手";
			return;
		}
		
		saveMessageState = { ...saveMessageState, [messageId]: "saving" };
		try {
			console.log("开始保存消息...");
			console.log("消息ID:", messageId);
			
			await saveAssistantMessage(messageId);
			console.log("消息保存成功:", messageId);
			
			saveMessageState = { ...saveMessageState, [messageId]: "saved" };
			messages = messages.map((item) =>
				item.id === messageId ? { ...item, is_saved: true } : item,
			);
		} catch (e) {
			console.error("保存回答失败:", e);
			saveMessageState = { ...saveMessageState, [messageId]: "idle" };
			assistantError = "保存回答失败，请稍后重试";
		}
	}

	function createNewConversation(): void {
		currentSessionId = null;
		historyPickerOpen = false;
		messages = [];
		assistantInput = "";
		assistantError = "";
		markNewChatDraft();
		void loadJobs(q, 1);
	}

	function toggleHistoryPicker(): void {
		historyPickerOpen = !historyPickerOpen;
	}

	function selectHistorySession(sessionId: number): void {
		historyPickerOpen = false;
		void loadSessionDetail(sessionId);
	}

	onMount(() => {
		void loadJobs();
		void loadAssistantSessions();
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

							<div class="card-foot">
								<span class="confidence-tag">平均置信度: {confidenceText(job.conf_avg)}</span>
								<button type="button" class="detail-btn" onclick={() => openDetail(job.id)}>
									查看详情
								</button>
							</div>
						</article>
					{/each}
				</div>
				<div class="pager">
					<button type="button" onclick={() => goToPage(currentPage - 1)} disabled={currentPage === 1}>
						上一页
					</button>
					<span class="pager-info">{pageInfoText}</span>
					<button
						type="button"
						onclick={() => goToPage(currentPage + 1)}
						disabled={currentPage === totalPages}
					>
						下一页
					</button>
					<form class="pager-jump" onsubmit={onJumpToPage}>
						<label for="jump-to-page">前往第</label>
						<input
							id="jump-to-page"
							type="number"
							min="1"
							max={Math.max(1, totalPages)}
							step="1"
							bind:value={jumpToPageInput}
							placeholder="页码"
						/>
						<span>页</span>
						<button type="submit" disabled={loading || totalPages === 0}>跳转</button>
					</form>
					<form class="pager-jump" onsubmit={onJumpToIndex}>
						<label for="jump-to-index">前往第</label>
						<input
							id="jump-to-index"
							type="number"
							min="1"
							max={Math.max(1, totalCount)}
							step="1"
							bind:value={jumpToIndexInput}
							placeholder="条目序号"
						/>
						<span>条</span>
						<button type="submit" disabled={loading || totalCount === 0}>跳转</button>
					</form>
				</div>
			{/if}
		</div>

		<aside class="assistant-col">
			<div class="assistant-card chat-card">
				<div class="chat-head">
					<h3>AI 对话助手</h3>
					<span class="chat-status">在线</span>
				</div>
				<div class="session-row">
					<button type="button" class="new-chat-btn" onclick={createNewConversation}>新对话</button>
					<div class="session-actions">
						<button
							type="button"
							class="history-btn"
							onclick={toggleHistoryPicker}
							disabled={assistantLoading || sessions.length === 0}
						>
							历史对话
						</button>
						{#if assistantLoading}
							<span class="session-tip">加载中...</span>
						{:else if currentSessionId}
							<span class="session-tip">会话 #{currentSessionId}</span>
						{:else}
							<span class="session-tip">未选择会话</span>
						{/if}
						{#if historyPickerOpen && sessions.length > 0}
							<div class="session-popover">
								{#each sessions as sess}
									<button
										type="button"
										class="session-item {currentSessionId === sess.id ? 'active' : ''}"
										onclick={() => selectHistorySession(sess.id)}
									>
										<span class="session-title">{sess.title}</span>
									</button>
								{/each}
							</div>
						{/if}
					</div>
				</div>
				<div class="chat-body">
					{#if assistantError}
						<div class="panel error">{assistantError}</div>
					{/if}
					{#if messages.length === 0}
						<div class="message ai">
							<div class="avatar ai">AI</div>
							<div class="bubble">
								你好，我可以基于你的要求自动筛选岗位，并总结筛选结果。你可以直接说：“帮我找杭州 2-3 年、月薪 2 万以上的科研岗”。
							</div>
						</div>
					{:else}
						{#each messages as msg}
							<div class="message {msg.role === 'user' ? 'user' : 'ai'}">
								{#if msg.role === "assistant"}
									<div class="avatar ai">AI</div>
									<div class="bubble">
										{#if msg.content === AI_LOADING_PLACEHOLDER}
											<span class="typing-dots" aria-label="AI 正在思考">
												<span>.</span><span>.</span><span>.</span>
											</span>
										{:else}
											{msg.content}
											<div class="msg-actions">
												<button
													type="button"
													class="save-btn"
													disabled={msg.id < 0 || msg.is_saved || saveMessageState[msg.id] === "saving"}
													onclick={() => onSaveAssistantMessage(msg.id)}
												>
													{#if msg.is_saved || saveMessageState[msg.id] === "saved"}
														已保存
													{:else if saveMessageState[msg.id] === "saving"}
														保存中...
													{:else}
														保存本次结果
													{/if}
												</button>
											</div>
										{/if}
									</div>
								{:else}
									<div class="bubble">{msg.content}</div>
									<div class="avatar user">我</div>
								{/if}
							</div>
						{/each}
					{/if}
				</div>
				<form class="chat-input-wrap" onsubmit={sendAssistantMessage}>
					<input
						type="text"
						placeholder="输入筛选条件或问题，例如：上海算法岗，3年经验，20k以上"
						bind:value={assistantInput}
					/>
					<button type="submit" disabled={assistantSending || !assistantInput.trim()}>
						发送
					</button>
				</form>
			</div>
		</aside>
	</div>

	<JobDetailDrawer
		open={detailVisible}
		loading={detailLoading}
		error={detailError}
		detail={detailData}
		onClose={closeDetail}
	/>
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
	.pager {
		margin-top: 0.9rem;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.7rem;
	}
	.pager button {
		height: 2rem;
		padding: 0 0.75rem;
		border-radius: 0.6rem;
		border: 1px solid color-mix(in oklab, var(--text-75) 22%, transparent);
		background: var(--card-bg);
		color: var(--text-90);
		font-size: 0.82rem;
		font-weight: 600;
	}
	.pager button:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}
	.pager-info {
		font-size: 0.82rem;
		color: var(--text-75);
		min-width: 6.8rem;
		text-align: center;
	}
	.pager-jump {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		margin-left: 0.35rem;
		font-size: 0.8rem;
		color: var(--text-75);
	}
	.pager-jump input {
		width: 6.2rem;
		height: 2rem;
		border-radius: 0.55rem;
		border: 1px solid color-mix(in oklab, var(--text-75) 22%, transparent);
		background: var(--card-bg);
		padding: 0 0.55rem;
		font-size: 0.8rem;
		color: var(--text-90);
	}
	.pager-jump button {
		height: 2rem;
		padding: 0 0.65rem;
		border-radius: 0.55rem;
		border: 1px solid color-mix(in oklab, var(--text-75) 22%, transparent);
		background: var(--btn-regular-bg);
		color: var(--text-90);
		font-size: 0.78rem;
		font-weight: 600;
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
	.session-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}
	.session-actions {
		position: relative;
		display: flex;
		align-items: center;
		gap: 0.45rem;
	}
	.new-chat-btn {
		height: 1.9rem;
		padding: 0 0.6rem;
		border-radius: 0.5rem;
		border: 1px solid color-mix(in oklab, var(--text-75) 22%, transparent);
		background: var(--btn-regular-bg);
		color: var(--text-90);
		font-size: 0.76rem;
		font-weight: 600;
	}
	.history-btn {
		height: 1.9rem;
		padding: 0 0.6rem;
		border-radius: 0.5rem;
		border: 1px solid color-mix(in oklab, var(--text-75) 22%, transparent);
		background: var(--card-bg);
		color: var(--text-90);
		font-size: 0.76rem;
		font-weight: 600;
	}
	.history-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.session-tip {
		font-size: 0.74rem;
		color: var(--text-75);
	}
	.session-popover {
		position: absolute;
		top: calc(100% + 0.35rem);
		right: 0;
		width: min(260px, 70vw);
		max-height: 220px;
		overflow: auto;
		display: grid;
		gap: 0.35rem;
		padding: 0.45rem;
		border-radius: 0.65rem;
		border: 1px solid color-mix(in oklab, var(--text-75) 18%, transparent);
		background: var(--card-bg);
		box-shadow: 0 10px 24px rgba(2, 6, 23, 0.12);
		z-index: 8;
	}
	.session-item {
		text-align: left;
		border: 1px solid color-mix(in oklab, var(--text-75) 16%, transparent);
		background: var(--btn-regular-bg);
		color: var(--text-90);
		border-radius: 0.55rem;
		padding: 0.35rem 0.45rem;
		font-size: 0.76rem;
	}
	.session-item.active {
		border-color: color-mix(in oklab, var(--primary) 48%, transparent);
		background: color-mix(in oklab, var(--primary) 10%, var(--btn-regular-bg));
	}
	.session-title {
		display: block;
		overflow: hidden;
		white-space: nowrap;
		text-overflow: ellipsis;
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
		white-space: pre-wrap;
	}
	.msg-actions {
		margin-top: 0.45rem;
		display: flex;
		justify-content: flex-end;
	}
	.save-btn {
		height: 1.75rem;
		padding: 0 0.58rem;
		border-radius: 0.5rem;
		border: 1px solid color-mix(in oklab, var(--text-75) 18%, transparent);
		background: var(--card-bg);
		color: var(--text-75);
		font-size: 0.72rem;
		font-weight: 600;
	}
	.save-btn:disabled {
		opacity: 0.7;
	}
	.typing-dots {
		display: inline-flex;
		align-items: center;
		gap: 0.14rem;
		font-size: 1.15rem;
		line-height: 1;
		color: var(--text-75);
	}
	.typing-dots span {
		animation: dot-bounce 1s infinite ease-in-out;
	}
	.typing-dots span:nth-child(2) {
		animation-delay: 0.18s;
	}
	.typing-dots span:nth-child(3) {
		animation-delay: 0.36s;
	}
	@keyframes dot-bounce {
		0%,
		80%,
		100% {
			opacity: 0.3;
			transform: translateY(0);
		}
		40% {
			opacity: 1;
			transform: translateY(-2px);
		}
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
		background: color-mix(in oklab, var(--primary) 70%, #94a3b8);
		color: white;
	}
	.chat-input-wrap button:disabled {
		opacity: 0.6;
		cursor: not-allowed;
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
	.card-foot {
		margin-top: 0.85rem;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.6rem;
	}
	.confidence-tag {
		font-size: 0.78rem;
		color: var(--text-75);
	}
	.detail-btn {
		height: 2rem;
		padding: 0 0.75rem;
		border-radius: 0.6rem;
		border: none;
		background: color-mix(in oklab, var(--primary) 88%, #0f172a);
		color: white;
		font-size: 0.78rem;
		font-weight: 600;
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
