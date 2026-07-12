# PathFy Nuxt 前端

正式前端使用 Nuxt 4、Vue 3、Nuxt UI，采用静态 SPA 输出并由 Nginx 托管。旧 Astro/Svelte 实现保存在 `../frontend.old/`，仅供查阅和紧急回退。

```bash
pnpm install
pnpm dev
pnpm typecheck
pnpm test
pnpm generate
```

开发环境 `/api` 默认代理至 `http://127.0.0.1:5000`，可通过 `FLASK_BACKEND` 修改。生产环境 `NUXT_PUBLIC_API_BASE` 留空，继续使用 Nginx 同源 `/api` 反代。静态产物位于 `.output/public`。
