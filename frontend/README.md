# PathFy Nuxt 前端

正式前端使用 Nuxt 4、Vue 3、Nuxt UI，采用静态 SPA 输出并由 Nginx 托管。旧 Astro/Svelte 实现保存在 `../frontend.old/`，仅供只读查阅；它不兼容当前图谱接口，不能用于生产发布或回滚。生产回滚必须切换到上一版 Nuxt 静态产物。

```bash
pnpm install
pnpm dev
pnpm typecheck
pnpm test
pnpm generate
```

CI 使用 Node 22 和 pnpm 9。`pnpm bundle:check` 检查主站构建；`pnpm experiment:ssr:test` 会先构建并检查独立的 SSR 实验站，再运行浏览器测试，无需预先从其他 CI job 获取产物。`pnpm test:e2e` 运行主站浏览器测试，本机默认端口被占用时可设置 `PLAYWRIGHT_PORT`。

包体积预算记录在 `bundle-budget.json`。2026-09-13 基线对应 `1687049` 的平台和报告增强产物，更新了总量、报告路由和匹配 gzip 限额（约 3% 余量）；首页初始 gzip、最大 JS 块和路由隔离限制仍保持原值。画像检测使用当前证据收支簿的标记。

开发环境 `/api` 默认代理至 `http://127.0.0.1:5000`，可通过 `FLASK_BACKEND` 修改。生产环境 `NUXT_PUBLIC_API_BASE` 留空，继续使用 Nginx 同源 `/api` 反代。静态产物位于 `.output/public`。
