/** @type {import('tailwindcss').Config} */
const defaultTheme = require("tailwindcss/defaultTheme");
module.exports = {
	content: ["./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue,mjs}"],
	darkMode: "class",
	theme: {
		extend: {
			/** 与能力画像等页一致：卡片/表单底随 :root / .dark 变量切换 */
			colors: {
				background: "var(--card-bg)",
			},
			fontFamily: {
				/** 与 suillilab 一致：Zen Maru Gothic + Noto Sans SC（由 Layout 内联 font-family 覆盖 body） */
				sans: [
					'"Zen Maru Gothic"',
					'"Noto Sans SC"',
					"system-ui",
					...defaultTheme.fontFamily.sans,
				],
			},
			screens: {
				md: "1280px",
				lg: "1280px",
			},
		},
	},
	plugins: [],
};
