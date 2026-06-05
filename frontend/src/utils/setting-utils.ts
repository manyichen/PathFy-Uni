import {
	DARK_MODE,
	DEFAULT_THEME,
	LIGHT_MODE,
} from "@constants/constants";
import { siteConfig } from "@/config";
import type { LIGHT_DARK_MODE } from "@/types/config";

export type ThemeSwitchOrigin = { x: number; y: number };

type StorageLike = Pick<Storage, "getItem" | "setItem">;

function setThemeRevealOrigin(origin?: ThemeSwitchOrigin) {
	if (typeof window === "undefined") return;
	const root = document.documentElement;
	if (origin) {
		const maxR = Math.hypot(
			Math.max(origin.x, window.innerWidth - origin.x),
			Math.max(origin.y, window.innerHeight - origin.y),
		);
		root.style.setProperty("--theme-x", `${origin.x}px`);
		root.style.setProperty("--theme-y", `${origin.y}px`);
		root.style.setProperty("--theme-r", `${maxR}px`);
	} else {
		root.style.setProperty("--theme-x", "50vw");
		root.style.setProperty("--theme-y", "50vh");
		root.style.setProperty("--theme-r", "150vmax");
	}
}

function clearThemeRevealOrigin() {
	document.documentElement.style.removeProperty("--theme-x");
	document.documentElement.style.removeProperty("--theme-y");
	document.documentElement.style.removeProperty("--theme-r");
}

function getSafeLocalStorage(): StorageLike | null {
	if (typeof globalThis === "undefined") {
		return null;
	}

	const storage = (globalThis as { localStorage?: unknown }).localStorage;
	if (!storage || typeof storage !== "object") {
		return null;
	}

	if (
		typeof (storage as StorageLike).getItem !== "function" ||
		typeof (storage as StorageLike).setItem !== "function"
	) {
		return null;
	}

	return storage as StorageLike;
}

export function getDefaultHue(): number {
	if (typeof document === "undefined") {
		return siteConfig.themeColor.hue;
	}
	const el = document.getElementById("config-carrier");
	if (!el) {
		return siteConfig.themeColor.hue;
	}
	return Number.parseInt(el.dataset.hue || String(siteConfig.themeColor.hue), 10);
}

export function getHue(): number {
	const storage = getSafeLocalStorage();
	if (!storage) {
		return siteConfig.themeColor.hue;
	}
	const stored = storage.getItem("hue");
	return stored ? Number.parseInt(stored, 10) : getDefaultHue();
}

export function setHue(hue: number): void {
	const storage = getSafeLocalStorage();
	if (storage) {
		storage.setItem("hue", String(hue));
	}
	if (typeof document === "undefined") {
		return;
	}
	const r = document.documentElement;
	r.style.setProperty("--hue", String(hue));
}

export function applyThemeToDocument(
	theme: LIGHT_DARK_MODE,
	origin?: ThemeSwitchOrigin,
): Promise<void> {
	const currentIsDark = document.documentElement.classList.contains("dark");
	let targetIsDark = false;
	switch (theme) {
		case LIGHT_MODE:
			targetIsDark = false;
			break;
		case DARK_MODE:
			targetIsDark = true;
			break;
		default:
			targetIsDark = currentIsDark;
	}

	const needsThemeChange = currentIsDark !== targetIsDark;
	const expectedTheme = targetIsDark ? "github-dark" : "github-light";
	const currentDataTheme = document.documentElement.getAttribute("data-theme");
	const needsCodeThemeUpdate = currentDataTheme !== expectedTheme;

	if (!needsThemeChange && !needsCodeThemeUpdate) {
		return Promise.resolve();
	}

	setThemeRevealOrigin(origin);

	const performThemeChange = () => {
		if (needsThemeChange) {
			if (targetIsDark) {
				document.documentElement.classList.add("dark");
			} else {
				document.documentElement.classList.remove("dark");
			}
		}
		if (needsCodeThemeUpdate) {
			document.documentElement.setAttribute("data-theme", expectedTheme);
		}
	};

	const finishTransition = () => {
		document.documentElement.classList.remove(
			"is-theme-transitioning",
			"use-view-transition",
		);
		clearThemeRevealOrigin();
	};

	const THEME_TRANSITION_MAX_MS = 1200;

	const withSafetyTimeout = (promise: Promise<unknown>) =>
		new Promise<void>((resolve) => {
			const timer = window.setTimeout(() => {
				finishTransition();
				resolve();
			}, THEME_TRANSITION_MAX_MS);
			Promise.resolve(promise)
				.then(() => {
					window.clearTimeout(timer);
					finishTransition();
					resolve();
				})
				.catch(() => {
					window.clearTimeout(timer);
					finishTransition();
					resolve();
				});
		});

	if (
		needsThemeChange &&
		document.startViewTransition &&
		!window.matchMedia("(prefers-reduced-motion: reduce)").matches
	) {
		document.documentElement.classList.add(
			"is-theme-transitioning",
			"use-view-transition",
		);
		const transition = document.startViewTransition(() => {
			performThemeChange();
		});
		return withSafetyTimeout(transition.finished);
	}

	if (needsThemeChange) {
		document.documentElement.classList.add("is-theme-transitioning");
	}
	performThemeChange();
	return new Promise((resolve) => {
		window.setTimeout(() => {
			document.documentElement.classList.remove("is-theme-transitioning");
			clearThemeRevealOrigin();
			resolve();
		}, 420);
	});
}

export function setTheme(
	theme: LIGHT_DARK_MODE,
	origin?: ThemeSwitchOrigin,
): Promise<void> {
	const storage = getSafeLocalStorage();
	if (storage) {
		storage.setItem("theme", theme);
	}
	if (typeof document === "undefined") {
		return Promise.resolve();
	}
	return applyThemeToDocument(theme, origin);
}

export function getStoredTheme(): LIGHT_DARK_MODE {
	const storage = getSafeLocalStorage();
	if (!storage) {
		return DEFAULT_THEME;
	}
	return (storage.getItem("theme") as LIGHT_DARK_MODE) || DEFAULT_THEME;
}
