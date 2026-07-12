<script lang="ts">
	import { onMount } from "svelte";

	interface Props {
		size?: number;
		pupilSize?: number;
		maxDistance?: number;
		eyeColor?: string;
		pupilColor?: string;
		isBlinking?: boolean;
		forceLookX?: number;
		forceLookY?: number;
		isSad?: boolean;
		sadRotate?: number;
	}

	let {
		size = 48,
		pupilSize = 16,
		maxDistance = 10,
		eyeColor = "white",
		pupilColor = "black",
		isBlinking = false,
		forceLookX = undefined,
		forceLookY = undefined,
		isSad = false,
		sadRotate = 0,
	}: Props = $props();

	let eyeRef = $state<HTMLDivElement | null>(null);
	let mouseX = $state(0);
	let mouseY = $state(0);

	const pupilPosition = $derived.by(() => {
		if (!eyeRef) return { x: 0, y: 0 };
		if (forceLookX !== undefined && forceLookY !== undefined) {
			return { x: forceLookX, y: forceLookY };
		}
		const rect = eyeRef.getBoundingClientRect();
		const centerX = rect.left + rect.width / 2;
		const centerY = rect.top + rect.height / 2;
		const deltaX = mouseX - centerX;
		const deltaY = mouseY - centerY;
		const distance = Math.min(
			Math.sqrt(deltaX * deltaX + deltaY * deltaY),
			maxDistance,
		);
		const angle = Math.atan2(deltaY, deltaX);
		return { x: Math.cos(angle) * distance, y: Math.sin(angle) * distance };
	});

	onMount(() => {
		const handleMouseMove = (e: MouseEvent): void => {
			mouseX = e.clientX;
			mouseY = e.clientY;
		};
		window.addEventListener("mousemove", handleMouseMove, { passive: true });
		return () => window.removeEventListener("mousemove", handleMouseMove);
	});
</script>

<div
	bind:this={eyeRef}
	class="eyeball"
	class:eyeball--sad={isSad}
	style={`width:${size}px;height:${isBlinking ? 2 : isSad ? size * 0.5 : size}px;background:${eyeColor};border-radius:${isSad ? `0 0 ${size}px ${size}px` : "50%"};transform:${isSad ? `rotate(${sadRotate}deg)` : "rotate(0deg)"}`}
>
	{#if !isBlinking}
		<div
			class="pupil"
			style={`width:${pupilSize}px;height:${pupilSize}px;background:${pupilColor};transform:translate(${pupilPosition.x}px,${isSad ? -1 : pupilPosition.y}px);`}
		></div>
	{/if}
</div>

<style>
	.eyeball {
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
		overflow: hidden;
		will-change: height, border-radius, transform;
	}

	.pupil {
		border-radius: 50%;
		transition: transform 0.1s ease-out;
		will-change: transform;
	}
</style>
