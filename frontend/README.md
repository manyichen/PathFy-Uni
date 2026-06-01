# 职业规划智能体 · 前端

> 项目总览与文档索引见仓库根目录 [`README.md`](../README.md)。

基于 [Astro](https://astro.build) + [Svelte](https://svelte.dev) + [Tailwind CSS](https://tailwindcss.com)，视觉与主题变量沿用 Mizuki 主题风格。

## 开发

```bash
cd frontend
pnpm install
pnpm dev
```

默认 <http://localhost:4321>。`/api/*` 请求由 Vite 代理到 Flask（默认 `http://127.0.0.1:5000`），可在启动前设置环境变量 `FLASK_BACKEND`。

## 构建

```bash
pnpm build
```

产物在 `dist/`，可由 Flask `send_from_directory` 托管，或与 Nginx 静态目录配合；API 建议同源 `/api` 以避免 CORS。

## 环境变量

复制 `.env.example` 为 `.env`。`PUBLIC_API_BASE` 为空时使用相对路径请求 API。

## 与后端的约定

见 `src/lib/api/`（HTTP 与各域 API）与 `src/lib/features/`（如 auth session）。Flask 提供 `GET/POST /api/...` JSON 接口，各模块页面已对接对应 API。

## 动态路由说明

`src/pages/jobs/[id].astro` 当前仅静态生成 `demo` 路径；若需任意岗位 ID，请在生产环境由 Flask 配置 **fallback 到 `index.html`** 或改为服务端渲染。
