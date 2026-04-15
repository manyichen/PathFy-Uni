<script lang="ts">
	import { onMount } from "svelte";
	import {
		clearAuth,
		fetchMe,
		getToken,
		getUser,
		saveAuth,
		type AuthUser,
	} from "@/lib/auth";

	let loading = $state(true);
	let errorMessage = $state("");
	let user = $state<AuthUser | null>(getUser());

	onMount(() => {
		const run = async (): Promise<void> => {
			const token = getToken();
			if (!token) {
				errorMessage = "未检测到登录状态，请先登录。";
				loading = false;
				return;
			}

			try {
				const latestUser = await fetchMe(token);
				user = latestUser;
				saveAuth(token, latestUser);
			} catch {
				clearAuth();
				errorMessage = "登录状态已失效，请重新登录。";
			} finally {
				loading = false;
			}
		};
		void run();
	});

	function logout(): void {
		clearAuth();
		window.location.assign("/");
	}
</script>

<section class="account-card">
	<h1>个人中心</h1>
	<p class="sub">基础账户信息（来自 `/api/auth/me`）</p>

	{#if loading}
		<div class="status">正在加载用户信息...</div>
	{:else if errorMessage}
		<div class="status error">{errorMessage}</div>
		<a class="action" href="/login">去登录</a>
	{:else if user}
		<div class="info-grid">
			<div class="row">
				<span class="label">用户 ID</span>
				<span class="value">{user.id}</span>
			</div>
			<div class="row">
				<span class="label">用户名</span>
				<span class="value">{user.username}</span>
			</div>
			<div class="row">
				<span class="label">邮箱</span>
				<span class="value">{user.email}</span>
			</div>
		</div>

		<div class="actions">
			<a class="action ghost" href="/">返回首页</a>
			<button class="action danger" onclick={logout}>退出登录</button>
		</div>
	{/if}
</section>

<style>
	.account-card {
		max-width: 760px;
		margin: 0 auto;
		padding: 1.4rem;
		border: 1px solid rgba(15, 23, 42, 0.08);
		border-radius: 1rem;
		background: var(--card-bg);
	}
	h1 {
		margin: 0;
		font-size: 1.45rem;
		font-weight: 700;
		color: var(--text-100);
	}
	.sub {
		margin-top: 0.45rem;
		color: var(--text-75);
		font-size: 0.92rem;
	}
	.status {
		margin-top: 1.1rem;
		padding: 0.8rem 0.95rem;
		border-radius: 0.7rem;
		background: rgba(99, 102, 241, 0.1);
		color: #3730a3;
	}
	.status.error {
		background: rgba(220, 38, 38, 0.1);
		color: #b91c1c;
	}
	.info-grid {
		margin-top: 1.1rem;
		display: grid;
		gap: 0.7rem;
	}
	.row {
		display: grid;
		grid-template-columns: 110px 1fr;
		gap: 1rem;
		padding: 0.8rem 0.9rem;
		border-radius: 0.7rem;
		background: var(--btn-regular-bg);
	}
	.label {
		color: var(--text-75);
		font-size: 0.88rem;
	}
	.value {
		color: var(--text-100);
		font-weight: 600;
		word-break: break-all;
	}
	.actions {
		margin-top: 1.1rem;
		display: flex;
		gap: 0.7rem;
	}
	.action {
		border: none;
		cursor: pointer;
		border-radius: 0.6rem;
		padding: 0.6rem 0.9rem;
		font-size: 0.9rem;
		text-decoration: none;
		display: inline-flex;
		align-items: center;
		justify-content: center;
	}
	.action.ghost {
		color: var(--text-90);
		background: var(--btn-regular-bg);
	}
	.action.danger {
		color: white;
		background: #b91c1c;
	}
</style>
