<script lang="ts">
import Icon from "@iconify/svelte";
import { getDefaultHue, getHue, setHue } from "@utils/setting-utils";

let hue = $state(getHue());

function resetHue() {
	const d = getDefaultHue();
	hue = d;
	setHue(d);
}

$effect(() => {
	setHue(hue);
});
</script>

<div
	id="display-setting"
	class="float-panel float-panel-closed fixed right-4 z-[60] w-80 px-4 py-4 transition-all"
>
	<div class="mb-3 flex flex-row items-center justify-between gap-2">
		<div
			class="relative ml-3 flex gap-2 text-lg font-bold text-neutral-900 transition dark:text-neutral-100
			before:absolute before:-left-3 before:top-[0.33rem] before:h-4 before:w-1 before:rounded-md before:bg-[var(--primary)]"
		>
			主题色
			<button
				aria-label="恢复默认色相"
				class="btn-regular h-7 w-7 rounded-md active:scale-90"
				class:opacity-0={hue === getDefaultHue()}
				class:pointer-events-none={hue === getDefaultHue()}
				onclick={resetHue}
			>
				<div class="text-[var(--btn-content)]">
					<Icon icon="fa6-solid:arrow-rotate-left" class="text-[0.875rem]"></Icon>
				</div>
			</button>
		</div>
		<div
			class="flex h-7 w-10 items-center justify-center rounded-md bg-[var(--btn-regular-bg)] text-sm font-bold text-[var(--btn-content)] transition"
		>
			{hue}
		</div>
	</div>
	<div
		class="h-6 w-full select-none rounded bg-[oklch(0.80_0.10_0)] px-1 dark:bg-[oklch(0.70_0.10_0)]"
	>
		<input
			aria-label="主题色相"
			type="range"
			min="0"
			max="360"
			step="5"
			bind:value={hue}
			class="slider h-full w-full"
		/>
	</div>
</div>

<style>
	input[type="range"] {
		-webkit-appearance: none;
		height: 1.5rem;
		background-image: var(--color-selection-bar);
		transition: background-image 0.15s ease-in-out;
		border-radius: 0.25rem;
	}
	input[type="range"]::-webkit-slider-thumb {
		-webkit-appearance: none;
		height: 1rem;
		width: 0.5rem;
		border-radius: 0.125rem;
		background: rgba(255, 255, 255, 0.7);
	}
	input[type="range"]::-moz-range-thumb {
		height: 1rem;
		width: 0.5rem;
		border-radius: 0.125rem;
		border-width: 0;
		background: rgba(255, 255, 255, 0.7);
	}
</style>
