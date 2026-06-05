<script lang="ts">
	import Icon from "@iconify/svelte";
	import { login, register } from "@/lib/api/auth";
	import { saveAuth } from "@/lib/features/auth/session";

	type Mode = "login" | "register";

	interface Props {
		mode: Mode;
	}

	let { mode }: Props = $props();

	let username = $state("");
	let email = $state("");
	let account = $state("");
	let password = $state("");
	let showPassword = $state(false);
	let isSubmitting = $state(false);
	let errorMessage = $state("");
	let successMessage = $state("");
	let loginSuccess = $state(false);
	let redirecting = $state(false);
	const redirectTarget =
		typeof window !== "undefined"
			? new URLSearchParams(window.location.search).get("redirect")
			: null;

	const isRegister = $derived(mode === "register");
	const formTitle = $derived(isRegister ? "创建你的规划账户" : "欢迎回来");
	const formSubtitle = $derived(
		isRegister ? "完成注册后即可保存画像、匹配结果和生涯报告。" : "登录后继续你的岗位探索、能力画像和行动计划。",
	);
	const submitText = $derived(
		isSubmitting ? "提交中..." : isRegister ? "创建账号" : "登录",
	);

	function safeRedirectPath(path: string | null): string {
		if (!path) return "/";
		if (!path.startsWith("/")) return "/";
		if (path.startsWith("//")) return "/";
		return path;
	}

	function withUid(path: string, userId: number): string {
		const [pathAndQuery, hash = ""] = path.split("#");
		const [pathname, query = ""] = pathAndQuery.split("?");
		const params = new URLSearchParams(query);
		params.set("uid", String(userId));
		const search = params.toString();
		return `${pathname}${search ? `?${search}` : ""}${hash ? `#${hash}` : ""}`;
	}

	function redirectWithTransition(path: string): void {
		redirecting = true;
		setTimeout(() => {
			window.location.assign(path);
		}, 720);
	}

	function validate(): string {
		if (isRegister && !/^[a-zA-Z0-9_]{2,32}$/.test(username.trim())) {
			return "用户名需为2-32位，仅支持字母、数字和下划线";
		}
		if (isRegister && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
			return "请输入正确邮箱地址";
		}
		if (!(isRegister ? email.trim() : account.trim())) {
			return isRegister ? "邮箱不能为空" : "请输入用户名或邮箱";
		}
		if (password.length < 6) {
			return "密码至少6位";
		}
		return "";
	}

	async function handleSubmit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		errorMessage = "";
		successMessage = "";
		loginSuccess = false;

		const validationError = validate();
		if (validationError) {
			errorMessage = validationError;
			return;
		}

		isSubmitting = true;
		try {
			const res = isRegister
				? await register(username.trim(), email.trim(), password)
				: await login(account.trim(), password);
			if (!res.ok || !res.data) {
				throw new Error(res.message || "请求失败");
			}
			saveAuth(res.data.token, res.data.user);
			successMessage = isRegister
				? "注册成功，已自动登录。"
				: `登录成功，欢迎 ${res.data.user.username}`;
			loginSuccess = true;
			password = "";
			const target = withUid(
				safeRedirectPath(redirectTarget),
				res.data.user.id,
			);
			setTimeout(() => {
				redirectWithTransition(target);
			}, 1800);
		} catch (err) {
			errorMessage = err instanceof Error ? err.message : "请求失败，请稍后再试";
		} finally {
			isSubmitting = false;
		}
	}
</script>

<section class="auth-page" class:is-success={loginSuccess} class:redirecting={redirecting}>
	<aside class="auth-visual" aria-label="职业规划智能体登录引导">
		<a href="/" class="brand-link" aria-label="返回首页">
			<img src="/assets/home/fu.svg" alt="" class="brand-icon" />
			<span>职业规划智能体</span>
		</a>

		<div class="visual-copy">
			<p class="eyebrow">PathFy-Uni</p>
			<h2>把职业方向变成一条清晰路线</h2>
			<p>
				保存你的能力画像、岗位匹配和阶段计划，让每一次分析都能接上下一步行动。
			</p>
		</div>

		<div class="visual-console">
			<div class="console-head">
				<span>今日规划状态</span>
				<strong>Ready</strong>
			</div>
			<div class="console-grid">
				<div>
					<Icon icon="material-symbols:radar" />
					<span>画像</span>
					<strong>8 维</strong>
				</div>
				<div>
					<Icon icon="material-symbols:compare-arrows-rounded" />
					<span>匹配</span>
					<strong>4 维</strong>
				</div>
				<div>
					<Icon icon="material-symbols:task-alt-rounded" />
					<span>计划</span>
					<strong>可复盘</strong>
				</div>
			</div>
		</div>

		<nav class="visual-links" aria-label="登录页快捷入口">
			<a href="/">首页</a>
			<a href="/jobs/">岗位探索</a>
			<a href="/profile/">能力画像</a>
		</nav>
	</aside>

	<div class="auth-panel">
		<div class="form-wrapper">
			<a href="/" class="mobile-brand" aria-label="返回首页">
				<img src="/assets/home/fu.svg" alt="" class="brand-icon" />
				<span>职业规划智能体</span>
			</a>

			<div class="form-header">
				<p class="eyebrow">{isRegister ? "New Account" : "Sign In"}</p>
				<h1>{formTitle}</h1>
				<p>{formSubtitle}</p>
			</div>

			<form class="auth-form" onsubmit={handleSubmit} aria-busy={isSubmitting}>
				{#if isRegister}
					<label>
						<span>用户名</span>
						<div class="input-wrap">
							<Icon icon="material-symbols:person-outline" />
							<input
								type="text"
								bind:value={username}
								placeholder="suilli_user"
								autocomplete="username"
								required
							/>
						</div>
					</label>
					<label>
						<span>邮箱</span>
						<div class="input-wrap">
							<Icon icon="material-symbols:mail-outline" />
							<input
								type="email"
								bind:value={email}
								placeholder="you@example.com"
								autocomplete="email"
								required
							/>
						</div>
					</label>
				{:else}
					<label>
						<span>用户名或邮箱</span>
						<div class="input-wrap">
							<Icon icon="material-symbols:person-outline" />
							<input
								type="text"
								bind:value={account}
								placeholder="请输入用户名或邮箱"
								autocomplete="username"
								required
							/>
						</div>
					</label>
				{/if}

				<label>
					<span>密码</span>
					<div class="input-wrap password-wrap">
						<Icon icon="material-symbols:lock-outline" />
						<input
							type={showPassword ? "text" : "password"}
							bind:value={password}
							placeholder="至少 6 位"
							autocomplete={isRegister ? "new-password" : "current-password"}
							required
						/>
						<button
							type="button"
							class="toggle-btn"
							aria-label={showPassword ? "隐藏密码" : "显示密码"}
							onclick={() => (showPassword = !showPassword)}
						>
							<Icon icon={showPassword ? "material-symbols:visibility-off-outline" : "material-symbols:visibility-outline"} />
						</button>
					</div>
				</label>

				<div class="status-stack" aria-live="polite">
					{#if errorMessage}
						<div class="alert error">{errorMessage}</div>
					{/if}
					{#if successMessage}
						<div class="alert success">{successMessage}</div>
					{/if}
				</div>

				<button type="submit" class="submit-btn" disabled={isSubmitting}>
					<span>{submitText}</span>
					<Icon icon="material-symbols:arrow-forward-rounded" />
				</button>
			</form>

			<div class="switch-link">
				{#if isRegister}
					已有账号？ <a href="/login">去登录</a>
				{:else}
					还没有账号？ <a href="/register">去注册</a>
				{/if}
			</div>
		</div>
	</div>
</section>

<style>
	.auth-page {
		display: grid;
		grid-template-columns: minmax(0, 0.98fr) minmax(420px, 0.9fr);
		min-height: calc(100vh - 8rem);
		overflow: hidden;
		border: 1px solid rgba(15, 23, 42, 0.1);
		border-radius: 8px;
		background: var(--card-bg);
		box-shadow: 0 24px 70px -44px rgba(15, 23, 42, 0.7);
		transition:
			opacity 0.72s cubic-bezier(0.22, 1, 0.36, 1),
			transform 0.72s cubic-bezier(0.22, 1, 0.36, 1),
			box-shadow 0.48s ease;
	}

	.auth-page.is-success {
		box-shadow:
			0 0 0 1px rgba(20, 184, 166, 0.24),
			0 24px 60px -36px rgba(20, 184, 166, 0.5);
	}

	.auth-page.redirecting {
		opacity: 0;
		transform: translateY(12px) scale(0.985);
		pointer-events: none;
	}

	.auth-visual {
		position: relative;
		display: flex;
		min-height: 680px;
		flex-direction: column;
		overflow: hidden;
		padding: 2rem;
		color: white;
		background:
			linear-gradient(135deg, rgba(2, 6, 23, 0.95), rgba(15, 23, 42, 0.82) 46%, rgba(13, 148, 136, 0.72)),
			url("https://images.unsplash.com/photo-1517048676732-d65bc937f952?auto=format&fit=crop&w=1400&q=80");
		background-position: center;
		background-size: cover;
	}

	.auth-visual::before {
		content: "";
		position: absolute;
		inset: 0;
		background-image:
			linear-gradient(rgba(255, 255, 255, 0.06) 1px, transparent 1px),
			linear-gradient(90deg, rgba(255, 255, 255, 0.06) 1px, transparent 1px);
		background-size: 28px 28px;
		mask-image: linear-gradient(to bottom, black, transparent 84%);
		pointer-events: none;
	}

	.brand-link,
	.mobile-brand {
		position: relative;
		z-index: 2;
		display: inline-flex;
		align-items: center;
		gap: 0.6rem;
		width: fit-content;
		color: inherit;
		text-decoration: none;
		font-weight: 700;
	}

	.brand-icon {
		width: 32px;
		height: 32px;
		border-radius: 8px;
		background: rgba(255, 255, 255, 0.92);
		padding: 0.25rem;
	}

	.visual-copy {
		position: relative;
		z-index: 2;
		max-width: 32rem;
		margin-top: 4.5rem;
	}

	.eyebrow {
		margin: 0;
		color: #22d3ee;
		font-size: 0.75rem;
		font-weight: 800;
		letter-spacing: 0;
		text-transform: uppercase;
	}

	.visual-copy h2 {
		margin: 0.8rem 0 0;
		max-width: 28rem;
		color: white;
		font-size: clamp(2rem, 4.2vw, 3.65rem);
		line-height: 1.08;
		letter-spacing: 0;
	}

	.visual-copy p:not(.eyebrow) {
		margin: 1rem 0 0;
		max-width: 31rem;
		color: rgba(255, 255, 255, 0.78);
		font-size: 1rem;
		line-height: 1.8;
	}

	.visual-console {
		position: relative;
		z-index: 3;
		margin-top: 2rem;
		max-width: 34rem;
		border: 1px solid rgba(255, 255, 255, 0.14);
		border-radius: 8px;
		background: rgba(2, 6, 23, 0.58);
		padding: 1rem;
		backdrop-filter: blur(14px);
	}

	.console-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		color: rgba(255, 255, 255, 0.7);
		font-size: 0.78rem;
	}

	.console-head strong {
		border-radius: 999px;
		background: rgba(45, 212, 191, 0.15);
		padding: 0.25rem 0.65rem;
		color: #99f6e4;
	}

	.console-grid {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 0.7rem;
		margin-top: 0.9rem;
	}

	.console-grid div {
		display: grid;
		gap: 0.35rem;
		border: 1px solid rgba(255, 255, 255, 0.1);
		border-radius: 8px;
		background: rgba(255, 255, 255, 0.08);
		padding: 0.8rem;
	}

	.console-grid :global(svg) {
		width: 1.35rem;
		height: 1.35rem;
		color: #67e8f9;
	}

	.console-grid span {
		color: rgba(255, 255, 255, 0.62);
		font-size: 0.76rem;
	}

	.console-grid strong {
		color: white;
		font-size: 1rem;
	}

	.visual-links {
		position: relative;
		z-index: 2;
		display: flex;
		flex-wrap: wrap;
		gap: 0.7rem;
		margin-top: auto;
	}

	.visual-links a {
		border: 1px solid rgba(255, 255, 255, 0.16);
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.08);
		padding: 0.45rem 0.8rem;
		color: rgba(255, 255, 255, 0.82);
		font-size: 0.78rem;
		text-decoration: none;
		transition:
			background-color 160ms ease,
			color 160ms ease;
	}

	.visual-links a:hover {
		background: rgba(255, 255, 255, 0.16);
		color: white;
	}

	.auth-panel {
		display: flex;
		align-items: center;
		justify-content: center;
		padding: clamp(1.5rem, 5vw, 4rem);
		background:
			linear-gradient(180deg, color-mix(in oklch, var(--primary) 6%, transparent), transparent 42%),
			var(--card-bg);
	}

	.form-wrapper {
		width: 100%;
		max-width: 430px;
	}

	.mobile-brand {
		display: none;
		margin-bottom: 2.2rem;
		color: #0f172a;
	}

	.form-header {
		margin-bottom: 2rem;
	}

	.form-header h1 {
		margin: 0.45rem 0 0;
		color: #0f172a;
		font-size: clamp(1.9rem, 4vw, 2.55rem);
		font-weight: 800;
		line-height: 1.15;
		letter-spacing: 0;
	}

	.form-header p:not(.eyebrow) {
		margin: 0.75rem 0 0;
		color: #64748b;
		font-size: 0.95rem;
		line-height: 1.75;
	}

	.auth-form {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	label {
		display: grid;
		gap: 0.5rem;
		color: #334155;
		font-size: 0.88rem;
		font-weight: 700;
	}

	.input-wrap {
		position: relative;
		display: flex;
		align-items: center;
		border: 1px solid #dbe3ef;
		border-radius: 8px;
		background: rgba(255, 255, 255, 0.86);
		color: #64748b;
		transition:
			border-color 160ms ease,
			box-shadow 160ms ease,
			background-color 160ms ease;
	}

	.input-wrap:focus-within {
		border-color: color-mix(in oklch, var(--primary) 58%, #22d3ee);
		background: white;
		box-shadow: 0 0 0 4px color-mix(in oklch, var(--primary) 15%, transparent);
	}

	.input-wrap > :global(svg) {
		width: 1.2rem;
		height: 1.2rem;
		margin-left: 0.9rem;
		color: color-mix(in oklch, var(--primary) 72%, #64748b);
	}

	input {
		width: 100%;
		height: 3.1rem;
		min-width: 0;
		border: 0;
		background: transparent;
		padding: 0 0.9rem;
		color: #0f172a;
		font-size: 1rem;
		outline: none;
	}

	input::placeholder {
		color: #94a3b8;
	}

	.password-wrap input {
		padding-right: 3rem;
	}

	.toggle-btn {
		position: absolute;
		right: 0.45rem;
		top: 50%;
		display: inline-flex;
		width: 2.25rem;
		height: 2.25rem;
		transform: translateY(-50%);
		align-items: center;
		justify-content: center;
		border: 0;
		border-radius: 8px;
		background: transparent;
		color: #64748b;
		cursor: pointer;
		transition:
			background-color 160ms ease,
			color 160ms ease;
	}

	.toggle-btn:hover {
		background: color-mix(in oklch, var(--primary) 10%, transparent);
		color: var(--primary);
	}

	.toggle-btn :global(svg) {
		width: 1.2rem;
		height: 1.2rem;
	}

	.password-wrap input::-ms-reveal,
	.password-wrap input::-ms-clear {
		display: none;
	}

	.status-stack {
		display: grid;
		gap: 0.6rem;
		min-height: 0;
	}

	.alert {
		border-radius: 8px;
		padding: 0.75rem 0.85rem;
		font-size: 0.86rem;
		line-height: 1.5;
	}

	.alert.error {
		border: 1px solid rgba(220, 38, 38, 0.2);
		background: rgba(254, 226, 226, 0.8);
		color: #b91c1c;
	}

	.alert.success {
		border: 1px solid rgba(20, 184, 166, 0.28);
		background: rgba(204, 251, 241, 0.82);
		color: #0f766e;
	}

	.submit-btn {
		display: inline-flex;
		width: 100%;
		height: 3.1rem;
		align-items: center;
		justify-content: center;
		gap: 0.55rem;
		border: 0;
		border-radius: 8px;
		background: linear-gradient(135deg, #0f172a, #0f766e);
		color: white;
		font-size: 1rem;
		font-weight: 800;
		cursor: pointer;
		transition:
			transform 160ms ease,
			box-shadow 160ms ease,
			opacity 160ms ease;
		box-shadow: 0 16px 30px -22px rgba(15, 23, 42, 0.9);
	}

	.submit-btn:hover:not(:disabled) {
		transform: translateY(-1px);
		box-shadow: 0 22px 36px -24px rgba(15, 118, 110, 0.85);
	}

	.submit-btn:disabled {
		opacity: 0.62;
		cursor: not-allowed;
	}

	.submit-btn :global(svg) {
		width: 1.25rem;
		height: 1.25rem;
	}

	.switch-link {
		margin-top: 1.4rem;
		color: #64748b;
		text-align: center;
		font-size: 0.9rem;
	}

	.switch-link a {
		color: var(--primary);
		font-weight: 800;
		text-decoration: none;
	}

	.switch-link a:hover {
		text-decoration: underline;
	}

	:global(.dark) .auth-page {
		border-color: rgba(255, 255, 255, 0.1);
		box-shadow: none;
	}

	:global(.dark) .mobile-brand,
	:global(.dark) .form-header h1 {
		color: white;
	}

	:global(.dark) .form-header p:not(.eyebrow),
	:global(.dark) .switch-link {
		color: rgba(255, 255, 255, 0.66);
	}

	:global(.dark) label {
		color: rgba(255, 255, 255, 0.82);
	}

	:global(.dark) .input-wrap {
		border-color: rgba(255, 255, 255, 0.12);
		background: rgba(255, 255, 255, 0.06);
		color: rgba(255, 255, 255, 0.62);
	}

	:global(.dark) .input-wrap:focus-within {
		background: rgba(255, 255, 255, 0.08);
	}

	:global(.dark) input {
		color: white;
	}

	:global(.dark) input::placeholder {
		color: rgba(255, 255, 255, 0.42);
	}

	:global(.dark) .submit-btn {
		background: linear-gradient(135deg, #14b8a6, #2563eb);
	}

	@media (max-width: 1180px) {
		.auth-page {
			grid-template-columns: minmax(0, 0.9fr) minmax(380px, 1fr);
		}

	}

	@media (max-width: 980px) {
		.auth-page {
			grid-template-columns: 1fr;
			min-height: auto;
		}

		.auth-visual {
			display: none;
		}

		.auth-panel {
			min-height: auto;
			align-items: flex-start;
			padding: 1.5rem;
		}

		.mobile-brand {
			display: inline-flex;
		}
	}

	@media (max-width: 520px) {
		.auth-panel {
			padding: 1rem;
		}

		.form-header {
			margin-bottom: 1.4rem;
		}

		.form-header h1 {
			font-size: 1.85rem;
		}

		.console-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
