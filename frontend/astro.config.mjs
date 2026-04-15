import svelte from "@astrojs/svelte";
import tailwind from "@astrojs/tailwind";
import icon from "astro-icon";
import { defineConfig } from "astro/config";

const flaskTarget = process.env.FLASK_BACKEND ?? "http://127.0.0.1:5000";

// https://astro.build/config
export default defineConfig({
	site: "http://localhost:4321",
	base: "/",
	trailingSlash: "ignore",
	output: "static",
	integrations: [
		tailwind({ nesting: true }),
		icon(),
		svelte(),
	],
	vite: {
		server: {
			proxy: {
				"/api": {
					target: flaskTarget,
					changeOrigin: true,
				},
			},
		},
	},
});
