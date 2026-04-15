/**
 * 站点配置 — 字体、顶栏标题等与 suillilab（Mizuki）`siteConfig` 对齐。
 * 若将 suillilab 的 `ZenMaruGothic-Medium.woff2`、`萝莉体 第二版.woff2` 放入 `public/assets/font/`，
 * 可把下方 `fontFamily` 改为与 suillilab 完全一致，并启用 `main.css` 中的 `@font-face`。
 */
export const siteConfig = {
	title: "职业规划智能体",
	subtitle: "基于 AI 的就业辅助",
	themeColor: {
		hue: 230,
		fixed: false,
	},
	/** 顶栏标题与图标（同 suillilab navbarTitle） */
	navbarTitle: {
		text: "职业规划智能体",
		icon: "assets/home/fu.svg",
	},
	/**
	 * 字体：与 suillilab 顺序一致 — ASCII 优先，CJK 回退。
	 * 默认使用 Google Fonts 的 Zen Maru Gothic + Noto Sans SC，视觉效果接近 suillilab 线上方案。
	 */
	font: {
		asciiFont: {
			fontFamily: "Zen Maru Gothic",
			fontWeight: "500",
		},
		cjkFont: {
			fontFamily: "Noto Sans SC",
			fontWeight: "500",
		},
	},
	/** 导航透明模式（与 suillilab banner.navbar.transparentMode 同名，无 Banner 时仅作 data 属性预留） */
	banner: {
		navbar: {
			transparentMode: "semi" as const,
		},
	},
} as const;
