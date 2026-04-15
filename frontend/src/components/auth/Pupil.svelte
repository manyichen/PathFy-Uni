<script lang="ts">
	import { onMount } from "svelte";

	interface Props {
		size?: number;
		maxDistance?: number;
		pupilColor?: string;
		forceLookX?: number;
		forceLookY?: number;
		isBlinking?: boolean;
	}

	let {
		size = 12,
		maxDistance = 5,
		pupilColor = "black",
		forceLookX = undefined,
		forceLookY = undefined,
		isBlinking = false,
	}: Props = $props();

	let pupilRef = $state<HTMLDivElement | null>(null);
	let mouseX = $state(0);
	let mouseY = $state(0);

	const pupilPosition = $derived.by(() => {
		if (!pupilRef) return { x: 0, y: 0 };
		if (forceLookX !== undefined && forceLookY !== undefined) {
			return { x: forceLookX, y: forceLookY };
		}
		const rect = pupilRef.getBoundingClientRect();
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
	bind:this={pupilRef}
	class="pupil"
	style={`width:${size}px;height:${isBlinking ? 2 : size}px;background:${pupilColor};transform:translate(${pupilPosition.x}px,${pupilPosition.y}px);`}
></div>

<style>
	.pupil {
		border-radius: 50%;
		transition: transform 0.1s ease-out, height 0.15s ease-out;
		will-change: transform, height;
	}
</style>
