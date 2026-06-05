<script lang="ts">
import { onMount } from "svelte";
import { DARK_MODE, LIGHT_MODE } from "@constants/constants";
import Icon from "@iconify/svelte";
import { getStoredTheme, setTheme, type ThemeSwitchOrigin } from "@utils/setting-utils";
import type { LIGHT_DARK_MODE } from "@/types/config";

let mode: LIGHT_DARK_MODE = $state(getStoredTheme());
let isChanging = false;

function syncModeFromStorage() {
	mode = getStoredTheme();
}

function originFromButton(el: HTMLElement): ThemeSwitchOrigin {
	const r = el.getBoundingClientRect();
	return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
}

async function switchScheme(newMode: LIGHT_DARK_MODE, origin?: ThemeSwitchOrigin) {
	if (isChanging || newMode === mode) return;
	isChanging = true;
	mode = newMode;
	try {
		await setTheme(newMode, origin);
	} finally {
		isChanging = false;
	}
}

function onToggle(e: MouseEvent) {
	const el = e.currentTarget as HTMLElement | null;
	const next = mode === LIGHT_MODE ? DARK_MODE : LIGHT_MODE;
	switchScheme(next, el ? originFromButton(el) : undefined);
}

onMount(() => {
	syncModeFromStorage();
	document.addEventListener("astro:page-load", syncModeFromStorage);
	return () => {
		document.removeEventListener("astro:page-load", syncModeFromStorage);
	};
});
</script>

<button
	type="button"
	aria-label={mode === DARK_MODE ? "切换到浅色模式" : "切换到深色模式"}
	class="btn-plain scale-animation relative z-[60] h-11 w-11 rounded-lg active:scale-90"
	id="scheme-switch"
	data-mode={mode}
	onclick={onToggle}
>
	<div
		class="icon-layer absolute inset-0 flex items-center justify-center transition-all duration-300 ease-in-out"
		class:opacity-0={mode !== LIGHT_MODE}
		class:scale-75={mode !== LIGHT_MODE}
		class:rotate-90={mode !== LIGHT_MODE}
		aria-hidden={mode !== LIGHT_MODE}
	>
		<Icon icon="material-symbols:wb-sunny-outline-rounded" class="text-[1.25rem]" />
	</div>
	<div
		class="icon-layer absolute inset-0 flex items-center justify-center transition-all duration-300 ease-in-out"
		class:opacity-0={mode !== DARK_MODE}
		class:scale-75={mode !== DARK_MODE}
		class:-rotate-90={mode !== DARK_MODE}
		aria-hidden={mode !== DARK_MODE}
	>
		<Icon icon="material-symbols:dark-mode-outline-rounded" class="text-[1.25rem]" />
	</div>
</button>

<style>
	.icon-layer {
		pointer-events: none;
	}
</style>
