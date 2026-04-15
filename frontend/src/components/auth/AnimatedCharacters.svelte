<script lang="ts">
	import { onMount } from "svelte";
	import EyeBall from "./EyeBall.svelte";
	import Pupil from "./Pupil.svelte";

	interface Props {
		isTyping?: boolean;
		showPassword?: boolean;
		passwordLength?: number;
		loginFailed?: boolean;
		loginSuccess?: boolean;
	}

	type Pos = { faceX: number; faceY: number; bodySkew: number };
	type Center = { x: number; y: number };

	let {
		isTyping = false,
		showPassword = false,
		passwordLength = 0,
		loginFailed = false,
		loginSuccess = false,
	}: Props = $props();

	let purpleRef = $state<HTMLDivElement | null>(null);
	let blackRef = $state<HTMLDivElement | null>(null);
	let orangeRef = $state<HTMLDivElement | null>(null);
	let yellowRef = $state<HTMLDivElement | null>(null);

	let hasEntered = $state(false);
	let isPurpleBlinking = $state(false);
	let isBlackBlinking = $state(false);
	let isOrangeBlinking = $state(false);
	let isYellowBlinking = $state(false);
	let isLookingAtEachOther = $state(false);
	let isPurplePeeking = $state(false);
	let successLookY = $state(-5);
	let showConfetti = $state(false);
	let confettiStyles = $state<string[]>([]);

	let purplePos = $state<Pos>({ faceX: 0, faceY: 0, bodySkew: 0 });
	let blackPos = $state<Pos>({ faceX: 0, faceY: 0, bodySkew: 0 });
	let orangePos = $state<Pos>({ faceX: 0, faceY: 0, bodySkew: 0 });
	let yellowPos = $state<Pos>({ faceX: 0, faceY: 0, bodySkew: 0 });

	let centers: Record<"purple" | "black" | "orange" | "yellow", Center> = {
		purple: { x: 0, y: 0 },
		black: { x: 0, y: 0 },
		orange: { x: 0, y: 0 },
		yellow: { x: 0, y: 0 },
	};

	let pendingMouseX = 0;
	let pendingMouseY = 0;
	let needsUpdate = false;
	let rafId: number | null = null;
	let successLookAnimId: number | null = null;
	let confettiTimeout: ReturnType<typeof setTimeout> | null = null;
	let peekTimeout: ReturnType<typeof setTimeout> | null = null;
	let typingLookTimeout: ReturnType<typeof setTimeout> | null = null;

	const isHidingPassword = $derived(passwordLength > 0 && !showPassword);

	function updateCharacterCenters(): void {
		if (purpleRef) {
			const rect = purpleRef.getBoundingClientRect();
			centers.purple = { x: rect.left + rect.width / 2, y: rect.top + rect.height / 3 };
		}
		if (blackRef) {
			const rect = blackRef.getBoundingClientRect();
			centers.black = { x: rect.left + rect.width / 2, y: rect.top + rect.height / 3 };
		}
		if (orangeRef) {
			const rect = orangeRef.getBoundingClientRect();
			centers.orange = { x: rect.left + rect.width / 2, y: rect.top + rect.height / 3 };
		}
		if (yellowRef) {
			const rect = yellowRef.getBoundingClientRect();
			centers.yellow = { x: rect.left + rect.width / 2, y: rect.top + rect.height / 3 };
		}
	}

	function calculatePosition(
		centerX: number,
		centerY: number,
		mx: number,
		my: number,
		rangeX = 15,
		rangeY = 10,
		minX: number | null = null,
		maxX: number | null = null,
		minY: number | null = null,
		maxY: number | null = null,
	): Pos {
		const rMinX = minX ?? -rangeX;
		const rMaxX = maxX ?? rangeX;
		const rMinY = minY ?? -rangeY;
		const rMaxY = maxY ?? rangeY;

		const deltaX = mx - centerX;
		const deltaY = my - centerY;

		const scaleX = Math.max(Math.abs(rMinX), Math.abs(rMaxX));
		const scaleY = Math.max(Math.abs(rMinY), Math.abs(rMaxY));
		const faceX = Math.max(rMinX, Math.min(rMaxX, deltaX / (300 / scaleX)));
		const faceY = Math.max(rMinY, Math.min(rMaxY, deltaY / (300 / scaleY)));
		const bodySkew = Math.max(-6, Math.min(6, -deltaX / 120));
		return { faceX, faceY, bodySkew };
	}

	function updatePositions(): void {
		if (needsUpdate && hasEntered) {
			needsUpdate = false;
			purplePos = calculatePosition(
				centers.purple.x,
				centers.purple.y,
				pendingMouseX,
				pendingMouseY,
				0,
				0,
				-46,
				18,
				-8,
				5,
			);
			blackPos = calculatePosition(
				centers.black.x,
				centers.black.y,
				pendingMouseX,
				pendingMouseY,
			);
			orangePos = calculatePosition(
				centers.orange.x,
				centers.orange.y,
				pendingMouseX,
				pendingMouseY,
				0,
				0,
				-46,
				20,
				-18,
				20,
			);
			yellowPos = calculatePosition(
				centers.yellow.x,
				centers.yellow.y,
				pendingMouseX,
				pendingMouseY,
			);
		}
		rafId = requestAnimationFrame(updatePositions);
	}

	function handleMouseMove(e: MouseEvent): void {
		pendingMouseX = e.clientX;
		pendingMouseY = e.clientY;
		needsUpdate = true;
	}

	function scheduleBlink(setter: (v: boolean) => void): ReturnType<typeof setTimeout> {
		const interval = Math.random() * 4000 + 3000;
		return setTimeout(() => {
			setter(true);
			setTimeout(() => setter(false), 150);
		}, interval);
	}

	function loopBlink(
		setter: (v: boolean) => void,
		assignTimer: (t: ReturnType<typeof setTimeout>) => void,
	): void {
		const t = scheduleBlink((v) => {
			setter(v);
			if (!v) loopBlink(setter, assignTimer);
		});
		assignTimer(t);
	}

	let purpleBlinkTimer: ReturnType<typeof setTimeout> | null = null;
	let blackBlinkTimer: ReturnType<typeof setTimeout> | null = null;
	let orangeBlinkTimer: ReturnType<typeof setTimeout> | null = null;
	let yellowBlinkTimer: ReturnType<typeof setTimeout> | null = null;

	function generateConfetti(): void {
		const colors = ["#FF6B6B", "#4ECDC4", "#FFE66D", "#A78BFA", "#FF9B6B", "#6BCB77", "#4D96FF"];
		confettiStyles = Array.from({ length: 150 }, (_, i) => {
			const color = colors[i % colors.length];
			return `left:${Math.random() * 100}%;top:-${10 + Math.random() * 30}%;background:${color};width:${4 + Math.random() * 6}px;height:${8 + Math.random() * 12}px;animation-delay:${Math.random() * 2}s;animation-duration:${4.5 + Math.random() * 2}s;transform:rotate(${Math.random() * 360}deg);`;
		});
		showConfetti = true;
		if (confettiTimeout) clearTimeout(confettiTimeout);
		confettiTimeout = setTimeout(() => {
			showConfetti = false;
			confettiStyles = [];
		}, 8000);
	}

	function animateSuccessLook(): void {
		const startY = -5;
		const endY = 4;
		const duration = 5500;
		const startTime = performance.now();
		const step = (now: number): void => {
			const progress = Math.min((now - startTime) / duration, 1);
			const eased =
				progress < 0.5
					? 4 * progress * progress * progress
					: 1 - Math.pow(-2 * progress + 2, 3) / 2;
			successLookY = startY + (endY - startY) * eased;
			if (progress < 1) {
				successLookAnimId = requestAnimationFrame(step);
			}
		};
		successLookAnimId = requestAnimationFrame(step);
	}

	$effect(() => {
		if (loginSuccess) {
			generateConfetti();
			successLookY = -5;
			if (successLookAnimId) cancelAnimationFrame(successLookAnimId);
			animateSuccessLook();
		} else {
			successLookY = -5;
			if (successLookAnimId) cancelAnimationFrame(successLookAnimId);
		}
	});

	$effect(() => {
		if (isTyping) {
			isLookingAtEachOther = true;
			if (typingLookTimeout) clearTimeout(typingLookTimeout);
			typingLookTimeout = setTimeout(() => {
				isLookingAtEachOther = false;
			}, 800);
		} else {
			isLookingAtEachOther = false;
			if (typingLookTimeout) clearTimeout(typingLookTimeout);
		}
	});

	$effect(() => {
		if (passwordLength > 0 && showPassword) {
			if (peekTimeout) clearTimeout(peekTimeout);
			const interval = Math.random() * 3000 + 2000;
			peekTimeout = setTimeout(() => {
				isPurplePeeking = true;
				setTimeout(() => {
					isPurplePeeking = false;
				}, 800);
			}, interval);
		} else {
			isPurplePeeking = false;
			if (peekTimeout) clearTimeout(peekTimeout);
		}
	});

	onMount(() => {
		window.addEventListener("mousemove", handleMouseMove, { passive: true });
		window.addEventListener("resize", updateCharacterCenters, { passive: true });

		loopBlink((v) => (isPurpleBlinking = v), (t) => (purpleBlinkTimer = t));
		loopBlink((v) => (isBlackBlinking = v), (t) => (blackBlinkTimer = t));
		loopBlink((v) => (isOrangeBlinking = v), (t) => (orangeBlinkTimer = t));
		loopBlink((v) => (isYellowBlinking = v), (t) => (yellowBlinkTimer = t));

		const enterTimer = setTimeout(() => {
			hasEntered = true;
			updateCharacterCenters();
			rafId = requestAnimationFrame(updatePositions);
		}, 1400);

		return () => {
			window.removeEventListener("mousemove", handleMouseMove);
			window.removeEventListener("resize", updateCharacterCenters);
			clearTimeout(enterTimer);
			if (purpleBlinkTimer) clearTimeout(purpleBlinkTimer);
			if (blackBlinkTimer) clearTimeout(blackBlinkTimer);
			if (orangeBlinkTimer) clearTimeout(orangeBlinkTimer);
			if (yellowBlinkTimer) clearTimeout(yellowBlinkTimer);
			if (typingLookTimeout) clearTimeout(typingLookTimeout);
			if (peekTimeout) clearTimeout(peekTimeout);
			if (confettiTimeout) clearTimeout(confettiTimeout);
			if (rafId) cancelAnimationFrame(rafId);
			if (successLookAnimId) cancelAnimationFrame(successLookAnimId);
		};
	});
</script>

<div class="animated-characters-container">
	{#if showConfetti}
		<div class="confetti-container">
			{#each confettiStyles as style, i}
				<div class="confetti-piece" style={style}></div>
			{/each}
		</div>
	{/if}

	<div
		bind:this={purpleRef}
		class="character purple-character"
		class:entrance-complete={hasEntered}
		style={`left:70px;width:180px;height:${isTyping || isHidingPassword ? 440 : 400}px;background-color:#6C3FF5;border-radius:0;z-index:1;transform:${
			hasEntered
				? passwordLength > 0 && showPassword
					? "skewX(0deg)"
					: isTyping || isHidingPassword
						? `skewX(${purplePos.bodySkew - 12}deg) translateX(40px)`
						: `skewX(${purplePos.bodySkew}deg)`
				: ""
		};`}
	>
		<div
			class="eyes"
			style={`left:${passwordLength > 0 && showPassword ? 50 : isLookingAtEachOther ? 85 : 75 + purplePos.faceX}px;top:${passwordLength > 0 && showPassword ? 20 : isLookingAtEachOther ? 50 : 25 + purplePos.faceY}px;`}
		>
			<EyeBall
				size={18}
				pupilSize={7}
				maxDistance={5}
				eyeColor="white"
				pupilColor="#2D2D2D"
				isBlinking={isPurpleBlinking}
				forceLookX={loginSuccess ? 0 : passwordLength > 0 && showPassword ? (isPurplePeeking ? 4 : -4) : isLookingAtEachOther ? 3 : undefined}
				forceLookY={loginSuccess ? successLookY : passwordLength > 0 && showPassword ? (isPurplePeeking ? 5 : -4) : isLookingAtEachOther ? 4 : undefined}
			/>
			<EyeBall
				size={18}
				pupilSize={7}
				maxDistance={5}
				eyeColor="white"
				pupilColor="#2D2D2D"
				isBlinking={isPurpleBlinking}
				forceLookX={loginSuccess ? 0 : passwordLength > 0 && showPassword ? (isPurplePeeking ? 4 : -4) : isLookingAtEachOther ? 3 : undefined}
				forceLookY={loginSuccess ? successLookY : passwordLength > 0 && showPassword ? (isPurplePeeking ? 5 : -4) : isLookingAtEachOther ? 4 : undefined}
			/>
		</div>
		<div
			class="purple-mouth-shape"
			class:purple-mouth-shape--typing={(isTyping || isHidingPassword) && !loginFailed && !loginSuccess}
			class:purple-mouth-shape--sad={loginFailed}
			class:purple-mouth-shape--happy={loginSuccess}
			style={`left:${passwordLength > 0 && showPassword ? 72 : isLookingAtEachOther ? 106 : 97 + purplePos.faceX}px;top:${passwordLength > 0 && showPassword ? 57 : isLookingAtEachOther ? 82 : 57 + purplePos.faceY}px;--counter-skew:${isTyping || isHidingPassword ? `skewX(${-((purplePos.bodySkew || 0) - 12)}deg)` : "skewX(0deg)"};`}
		></div>
	</div>

	<div
		bind:this={blackRef}
		class="character black-character"
		class:entrance-complete={hasEntered}
		style={`left:240px;width:120px;height:310px;background-color:#2D2D2D;border-radius:0;z-index:2;transform:${
			hasEntered
				? passwordLength > 0 && showPassword
					? "skewX(0deg)"
					: isLookingAtEachOther
						? `skewX(${blackPos.bodySkew * 1.5 + 10}deg) translateX(20px)`
						: isTyping || isHidingPassword
							? `skewX(${blackPos.bodySkew * 1.5}deg)`
							: `skewX(${blackPos.bodySkew}deg)`
				: ""
		};`}
	>
		<div
			class="eyes"
			style={`left:${passwordLength > 0 && showPassword ? 10 : isLookingAtEachOther ? 32 : 26 + blackPos.faceX}px;top:${passwordLength > 0 && showPassword ? 28 : isLookingAtEachOther ? 12 : 32 + blackPos.faceY}px;`}
		>
			<EyeBall
				size={16}
				pupilSize={6}
				maxDistance={4}
				eyeColor="white"
				pupilColor="#2D2D2D"
				isBlinking={isBlackBlinking}
				isSad={loginFailed}
				sadRotate={-20}
				forceLookX={loginSuccess ? 0 : passwordLength > 0 && showPassword ? -4 : isLookingAtEachOther ? 0 : undefined}
				forceLookY={loginSuccess ? successLookY : passwordLength > 0 && showPassword ? -4 : isLookingAtEachOther ? -4 : undefined}
			/>
			<EyeBall
				size={16}
				pupilSize={6}
				maxDistance={4}
				eyeColor="white"
				pupilColor="#2D2D2D"
				isBlinking={isBlackBlinking}
				isSad={loginFailed}
				sadRotate={20}
				forceLookX={loginSuccess ? 0 : passwordLength > 0 && showPassword ? -4 : isLookingAtEachOther ? 0 : undefined}
				forceLookY={loginSuccess ? successLookY : passwordLength > 0 && showPassword ? -4 : isLookingAtEachOther ? -4 : undefined}
			/>
		</div>
	</div>

	<div
		bind:this={orangeRef}
		class="character orange-character"
		class:entrance-complete={hasEntered}
		style={`left:0;width:240px;height:150px;z-index:3;background-color:#FF9B6B;border-radius:120px 120px 0 0;transform:${hasEntered ? (passwordLength > 0 && showPassword ? "skewX(0deg)" : `skewX(${orangePos.bodySkew}deg)`) : ""};`}
	>
		<div
			class="eyes"
			style={`left:${passwordLength > 0 && showPassword ? 80 : 112 + orangePos.faceX}px;top:${passwordLength > 0 && showPassword ? 55 : 60 + orangePos.faceY}px;`}
		>
			<Pupil
				size={12}
				maxDistance={5}
				pupilColor="#2D2D2D"
				isBlinking={isOrangeBlinking}
				forceLookX={loginSuccess ? 0 : passwordLength > 0 && showPassword ? -5 : undefined}
				forceLookY={loginSuccess ? successLookY : passwordLength > 0 && showPassword ? -4 : undefined}
			/>
			<Pupil
				size={12}
				maxDistance={5}
				pupilColor="#2D2D2D"
				isBlinking={isOrangeBlinking}
				forceLookX={loginSuccess ? 0 : passwordLength > 0 && showPassword ? -5 : undefined}
				forceLookY={loginSuccess ? successLookY : passwordLength > 0 && showPassword ? -4 : undefined}
			/>
		</div>
		<div
			class="orange-mouth-shape"
			class:orange-mouth-shape--typing={(isTyping || isHidingPassword) && !loginFailed && !loginSuccess}
			class:orange-mouth-shape--sad={loginFailed}
			class:orange-mouth-shape--happy={loginSuccess}
			style={`left:${passwordLength > 0 && showPassword ? 94 : 126 + orangePos.faceX}px;top:${passwordLength > 0 && showPassword ? 87 : 92 + orangePos.faceY}px;`}
		></div>
	</div>

	<div
		bind:this={yellowRef}
		class="character yellow-character"
		class:entrance-complete={hasEntered}
		style={`left:310px;width:140px;height:230px;background-color:#E8D754;border-radius:70px 70px 0 0;z-index:4;transform:${hasEntered ? (passwordLength > 0 && showPassword ? "skewX(0deg)" : `skewX(${yellowPos.bodySkew}deg)`) : ""};`}
	>
		<div
			class="eyes"
			style={`left:${passwordLength > 0 && showPassword ? 20 : 52 + yellowPos.faceX}px;top:${passwordLength > 0 && showPassword ? 35 : 40 + yellowPos.faceY}px;`}
		>
			<Pupil
				size={12}
				maxDistance={5}
				pupilColor="#2D2D2D"
				isBlinking={isYellowBlinking}
				forceLookX={loginSuccess ? 0 : passwordLength > 0 && showPassword ? -5 : undefined}
				forceLookY={loginSuccess ? successLookY : passwordLength > 0 && showPassword ? -4 : undefined}
			/>
			<Pupil
				size={12}
				maxDistance={5}
				pupilColor="#2D2D2D"
				isBlinking={isYellowBlinking}
				forceLookX={loginSuccess ? 0 : passwordLength > 0 && showPassword ? -5 : undefined}
				forceLookY={loginSuccess ? successLookY : passwordLength > 0 && showPassword ? -4 : undefined}
			/>
		</div>
		<div
			class="yellow-mouth-wrapper"
			style={`left:${passwordLength > 0 && showPassword ? 10 : 40 + yellowPos.faceX}px;top:${passwordLength > 0 && showPassword ? 88 : 88 + yellowPos.faceY}px;`}
		>
			<svg width="80" height="20" viewBox="0 0 80 20">
				<path
					class="yellow-mouth-path"
					class:yellow-mouth-path--wavy={loginFailed}
					class:yellow-mouth-path--happy={loginSuccess}
					stroke="#2D2D2D"
					stroke-width="3"
					fill="none"
					stroke-linecap="round"
				></path>
			</svg>
		</div>
	</div>
</div>

<style>
	.animated-characters-container {
		position: relative;
		width: 550px;
		height: 400px;
	}

	.character {
		position: absolute;
		bottom: 0;
		transition: all 0.7s cubic-bezier(0.4, 0, 0.2, 1);
		transform-origin: bottom center;
		will-change: transform;
	}

	.purple-character {
		animation: purple-entrance 1.2s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
	}
	.black-character {
		animation: black-entrance 1s cubic-bezier(0.34, 1.56, 0.64, 1) 0.2s backwards;
	}
	.orange-character {
		animation: orange-entrance 1.1s cubic-bezier(0.34, 1.56, 0.64, 1) 0.1s backwards;
	}
	.yellow-character {
		animation: yellow-entrance 1s cubic-bezier(0.34, 1.56, 0.64, 1) 0.3s backwards;
	}
	.entrance-complete {
		animation: none;
	}

	@keyframes purple-entrance {
		0% {
			transform: translateX(-150px) translateY(50px) rotate(-15deg) scale(0.3);
			opacity: 0;
		}
		60% {
			transform: translateX(10px) translateY(-10px) rotate(3deg) scale(1.05);
		}
		100% {
			transform: translateX(0) translateY(0) rotate(0deg) scale(1);
			opacity: 1;
		}
	}
	@keyframes black-entrance {
		0% {
			transform: translateY(-100px) scale(0.5);
			opacity: 0;
		}
		70% {
			transform: translateY(10px) scale(1.08);
		}
		100% {
			transform: translateY(0) scale(1);
			opacity: 1;
		}
	}
	@keyframes orange-entrance {
		0% {
			transform: translateX(-200px) translateY(80px) rotate(-25deg) scale(0.2);
			opacity: 0;
		}
		65% {
			transform: translateX(15px) translateY(-8px) rotate(5deg) scale(1.1);
		}
		100% {
			transform: translateX(0) translateY(0) rotate(0deg) scale(1);
			opacity: 1;
		}
	}
	@keyframes yellow-entrance {
		0% {
			transform: translateX(200px) translateY(60px) rotate(20deg) scale(0.3);
			opacity: 0;
		}
		65% {
			transform: translateX(-12px) translateY(-5px) rotate(-4deg) scale(1.06);
		}
		100% {
			transform: translateX(0) translateY(0) rotate(0deg) scale(1);
			opacity: 1;
		}
	}

	.eyes {
		position: absolute;
		display: flex;
		transition: all 0.7s cubic-bezier(0.4, 0, 0.2, 1);
	}
	.purple-character .eyes {
		gap: 32px;
	}
	.black-character .eyes {
		gap: 24px;
	}
	.orange-character .eyes {
		gap: 32px;
		transition: all 0.2s cubic-bezier(0, 0, 0.2, 1);
	}
	.yellow-character .eyes {
		gap: 24px;
		transition: all 0.2s cubic-bezier(0, 0, 0.2, 1);
	}

	.purple-mouth-shape {
		position: absolute;
		width: 24px;
		height: 8px;
		background-color: #2d2d2d;
		border-radius: 0 0 12px 12px;
		transition: left 0.7s cubic-bezier(0.4, 0, 0.2, 1), top 0.7s cubic-bezier(0.4, 0, 0.2, 1), width 0.5s, height 0.5s, border-radius 0.5s, transform 0.5s;
	}
	.purple-mouth-shape--typing {
		width: 7px;
		height: 32px;
		border-radius: 0;
		transform: translateX(13.5px) translateY(-28px) var(--counter-skew, skewX(0deg));
	}
	.purple-mouth-shape--sad {
		width: 24px;
		height: 8px;
		border-radius: 12px 12px 0 0;
	}
	.purple-mouth-shape--happy {
		width: 30px;
		height: 16px;
		border-radius: 0 0 15px 15px;
	}

	.orange-mouth-shape {
		position: absolute;
		width: 26px;
		height: 13px;
		background-color: #2d2d2d;
		border-radius: 0 0 13px 13px;
		transition: left 0.2s, top 0.2s, width 0.5s, height 0.5s, border-radius 0.5s, transform 0.5s;
	}
	.orange-mouth-shape--typing {
		width: 14px;
		height: 14px;
		border-radius: 50%;
		transform: translateX(6px);
	}
	.orange-mouth-shape--sad {
		border-radius: 13px 13px 0 0;
	}
	.orange-mouth-shape--happy {
		width: 32px;
		height: 18px;
		border-radius: 0 0 16px 16px;
	}

	.yellow-mouth-wrapper {
		position: absolute;
		transition: all 0.2s cubic-bezier(0, 0, 0.2, 1);
	}
	.yellow-mouth-path {
		d: path("M0 10 Q10 10, 20 10 Q30 10, 40 10 Q50 10, 60 10 Q70 10, 80 10");
		transition: d 0.5s cubic-bezier(0.4, 0, 0.2, 1);
	}
	.yellow-mouth-path--wavy {
		d: path("M0 10 Q10 2, 20 10 Q30 18, 40 10 Q50 2, 60 10 Q70 18, 80 10");
	}
	.yellow-mouth-path--happy {
		d: path("M0 2 Q10 10, 20 14 Q30 18, 40 18 Q50 18, 60 14 Q70 10, 80 2");
	}

	.confetti-container {
		position: fixed;
		top: 0;
		left: 0;
		width: 100vw;
		height: 100vh;
		overflow: visible;
		pointer-events: none;
		z-index: 10;
	}
	.confetti-piece {
		position: absolute;
		border-radius: 2px;
		animation: confetti-fall linear forwards;
	}
	@keyframes confetti-fall {
		0% {
			translate: 0 0;
			opacity: 1;
		}
		100% {
			translate: 30px 200vh;
			opacity: 1;
			rotate: 720deg;
		}
	}
</style>
