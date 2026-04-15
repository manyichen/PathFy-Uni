<script lang="ts">
	import AnimatedCharacters from "./AnimatedCharacters.svelte";
	import { login, register, saveAuth } from "@/lib/auth";

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
	let isTyping = $state(false);
	let isSubmitting = $state(false);
	let errorMessage = $state("");
	let successMessage = $state("");
	let loginFailed = $state(false);
	let loginSuccess = $state(false);
	let statusTimer: ReturnType<typeof setTimeout> | null = null;
	let redirecting = $state(false);
	const redirectTarget =
		typeof window !== "undefined"
			? new URLSearchParams(window.location.search).get("redirect")
			: null;

	const isRegister = $derived(mode === "register");
	const formTitle = $derived(isRegister ? "Welcome!" : "Welcome back!");
	const formSubtitle = $derived(
		isRegister ? "请输入信息完成注册" : "请输入账号与密码登录",
	);
	const submitText = $derived(
		isSubmitting ? "提交中..." : isRegister ? "注册" : "登录",
	);

	function resetStatusTimer(ms: number, setter: (v: boolean) => void): void {
		if (statusTimer) clearTimeout(statusTimer);
		statusTimer = setTimeout(() => setter(false), ms);
	}

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
		loginFailed = false;
		loginSuccess = false;

		const validationError = validate();
		if (validationError) {
			errorMessage = validationError;
			loginFailed = true;
			resetStatusTimer(3000, (v) => (loginFailed = v));
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
			loginFailed = true;
			resetStatusTimer(3000, (v) => (loginFailed = v));
		} finally {
			isSubmitting = false;
		}
	}

	$effect(() => {
		return () => {
			if (statusTimer) clearTimeout(statusTimer);
		};
	});
</script>

<section class="auth-page" class:is-success={loginSuccess} class:redirecting={redirecting}>
	<div class="left-section">
		<div class="logo-section">
			<a href="/" class="logo-link">
				<img
					src="https://i.postimg.cc/nLrDYrHW/icon.png"
					alt="CareerCompass logo"
					class="logo-image"
				/>
				<span>CareerCompass</span>
			</a>
		</div>
		<div class="characters-section">
			<AnimatedCharacters
				isTyping={isTyping}
				showPassword={showPassword}
				passwordLength={password.length}
				loginFailed={loginFailed}
				loginSuccess={loginSuccess}
			/>
		</div>
		<div class="footer-links">
			<a href="#" class="footer-link">Privacy Policy</a>
			<a href="#" class="footer-link">Terms of Service</a>
		</div>
		<div class="grid-overlay"></div>
		<div class="blur-circle blur-circle-1"></div>
		<div class="blur-circle blur-circle-2"></div>
	</div>

	<div class="right-section">
		<div class="form-wrapper">
			<div class="mobile-logo">
				<img
					src="https://i.postimg.cc/nLrDYrHW/icon.png"
					alt="CareerCompass logo"
					class="logo-image"
				/>
				<span>CareerCompass</span>
			</div>

			<div class="form-header">
				<h1>{formTitle}</h1>
				<p>{formSubtitle}</p>
			</div>

			<form class="auth-form" onsubmit={handleSubmit}>
				{#if isRegister}
					<label>
						用户名
						<input
							type="text"
							bind:value={username}
							placeholder="suilli_user"
							required
							onfocus={() => (isTyping = true)}
							onblur={() => (isTyping = false)}
						/>
					</label>
					<label>
						邮箱
						<input
							type="email"
							bind:value={email}
							placeholder="you@example.com"
							required
							onfocus={() => (isTyping = true)}
							onblur={() => (isTyping = false)}
						/>
					</label>
				{:else}
					<label>
						用户名或邮箱
						<input
							type="text"
							bind:value={account}
							placeholder="请输入用户名或邮箱"
							required
							onfocus={() => (isTyping = true)}
							onblur={() => (isTyping = false)}
						/>
					</label>
				{/if}

				<label>
					密码
					<div class="password-wrap">
						<input
							type={showPassword ? "text" : "password"}
							bind:value={password}
							placeholder="至少 6 位"
							required
						/>
						<button
							type="button"
							class="toggle-btn"
							aria-label={showPassword ? "隐藏密码" : "显示密码"}
							onclick={() => (showPassword = !showPassword)}
						>
							{#if showPassword}
								<svg viewBox="0 0 24 24" aria-hidden="true">
									<path
										d="M3 3l18 18M10.6 10.6a2 2 0 102.8 2.8M9.9 5.1A10.8 10.8 0 0112 5c6.2 0 9.4 7 9.4 7a13.9 13.9 0 01-3.2 3.9M6.5 6.5A13.4 13.4 0 002.6 12s3.2 7 9.4 7a10.3 10.3 0 005.5-1.6"
									/>
								</svg>
							{:else}
								<svg viewBox="0 0 24 24" aria-hidden="true">
									<path d="M2.6 12S5.8 5 12 5s9.4 7 9.4 7-3.2 7-9.4 7-9.4-7-9.4-7z" />
									<circle cx="12" cy="12" r="3" />
								</svg>
							{/if}
						</button>
					</div>
				</label>

				{#if errorMessage}
					<div class="alert error">{errorMessage}</div>
				{/if}
				{#if successMessage}
					<div class="alert success">{successMessage}</div>
				{/if}

				<button type="submit" class="submit-btn" disabled={isSubmitting}>{submitText}</button>
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
		grid-template-columns: 1fr 1fr;
		min-height: calc(100vh - 8rem);
		max-height: calc(100vh - 8rem);
		overflow: hidden;
		border-radius: 1.25rem;
		border: 1px solid rgba(15, 23, 42, 0.08);
		background: white;
		transition: opacity 0.72s cubic-bezier(0.22, 1, 0.36, 1),
			transform 0.72s cubic-bezier(0.22, 1, 0.36, 1), box-shadow 0.48s ease;
	}
	.auth-page.is-success {
		box-shadow: 0 0 0 1px rgba(34, 197, 94, 0.18), 0 18px 36px rgba(22, 163, 74, 0.16);
	}
	.auth-page.redirecting {
		opacity: 0;
		transform: translateY(12px) scale(0.985);
		pointer-events: none;
	}
	.left-section {
		position: relative;
		display: flex;
		flex-direction: column;
		justify-content: space-between;
		background: linear-gradient(to bottom right, #9ca3af, #6b7280, #4b5563);
		padding: 2rem;
		color: white;
	}
	.logo-section,
	.characters-section,
	.footer-links {
		position: relative;
		z-index: 2;
	}
	.logo-link {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 1.125rem;
		font-weight: 600;
		color: inherit;
		text-decoration: none;
	}
	.logo-image {
		width: 32px;
		height: 32px;
		background: rgba(255, 255, 255, 0.1);
		backdrop-filter: blur(4px);
		padding: 0.25rem;
		border-radius: 0.5rem;
	}
	.characters-section {
		display: flex;
		align-items: flex-end;
		justify-content: center;
		height: 500px;
	}
	.footer-links {
		display: flex;
		gap: 2rem;
		font-size: 0.875rem;
		color: #d1d5db;
	}
	.footer-link {
		color: inherit;
		text-decoration: none;
	}
	.grid-overlay {
		position: absolute;
		inset: 0;
		background-image: linear-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px),
			linear-gradient(90deg, rgba(255, 255, 255, 0.05) 1px, transparent 1px);
		background-size: 20px 20px;
	}
	.blur-circle {
		position: absolute;
		border-radius: 50%;
		filter: blur(96px);
	}
	.blur-circle-1 {
		top: 25%;
		right: 25%;
		width: 16rem;
		height: 16rem;
		background: rgba(156, 163, 175, 0.2);
	}
	.blur-circle-2 {
		bottom: 25%;
		left: 25%;
		width: 24rem;
		height: 24rem;
		background: rgba(209, 213, 219, 0.2);
	}
	.right-section {
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 2rem;
		background: white;
	}
	.form-wrapper {
		width: 100%;
		max-width: 420px;
	}
	.mobile-logo {
		display: none;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		font-size: 1.125rem;
		font-weight: 600;
		margin-bottom: 3rem;
	}
	.form-header {
		text-align: center;
		margin-bottom: 2rem;
	}
	h1 {
		font-size: 1.85rem;
		font-weight: 700;
		margin: 0;
		color: #111827;
	}
	p {
		font-size: 0.9rem;
		color: #6b7280;
		margin-top: 0.5rem;
	}
	.auth-form {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}
	label {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		font-size: 0.9rem;
		color: #374151;
	}
	input {
		height: 3rem;
		padding: 0 1rem;
		border: 1.5px solid rgba(229, 231, 235, 0.7);
		border-radius: 0.5rem;
		font-size: 1rem;
		outline: none;
		transition: all 0.2s;
	}
	input:focus {
		border-color: #6366f1;
	}
	.password-wrap {
		position: relative;
		width: 100%;
	}
	.password-wrap input {
		width: 100%;
		padding-right: 3rem;
	}
	.toggle-btn {
		position: absolute;
		right: 0.45rem;
		top: 50%;
		transform: translateY(-50%);
		width: 2.2rem;
		height: 2.2rem;
		border-radius: 999px;
		border: none;
		background: transparent;
		cursor: pointer;
		color: #6b7280;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		transition: background-color 0.2s ease, color 0.2s ease;
	}
	.toggle-btn:hover {
		background: rgba(99, 102, 241, 0.1);
		color: #4f46e5;
	}
	.toggle-btn svg {
		width: 1.1rem;
		height: 1.1rem;
		fill: none;
		stroke: currentColor;
		stroke-width: 2;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
	/* 避免 Edge/IE 自带密码显隐图标与自定义图标重叠 */
	.password-wrap input::-ms-reveal,
	.password-wrap input::-ms-clear {
		display: none;
	}
	.alert {
		padding: 0.75rem;
		font-size: 0.875rem;
		border-radius: 0.5rem;
	}
	.alert.error {
		color: #dc2626;
		background: rgba(220, 38, 38, 0.1);
		border: 1px solid rgba(220, 38, 38, 0.2);
	}
	.alert.success {
		color: #15803d;
		background: rgba(22, 163, 74, 0.1);
		border: 1px solid rgba(22, 163, 74, 0.2);
	}
	.submit-btn {
		width: 100%;
		height: 3rem;
		border: none;
		border-radius: 0.5rem;
		background: #111827;
		color: white;
		font-size: 1rem;
		font-weight: 500;
		cursor: pointer;
	}
	.submit-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
	.switch-link {
		margin-top: 1.5rem;
		text-align: center;
		font-size: 0.875rem;
		color: #6b7280;
	}
	.switch-link a {
		color: #111827;
		text-decoration: none;
		font-weight: 600;
	}
	@media (max-width: 1200px) {
		.characters-section {
			transform: scale(0.88);
		}
	}
	@media (max-width: 1024px) {
		.auth-page {
			grid-template-columns: 1fr;
		}
		.left-section {
			display: none;
		}
		.mobile-logo {
			display: flex;
		}
	}
</style>
