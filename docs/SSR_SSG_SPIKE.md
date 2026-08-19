# 公开路由 SSR/SSG 技术试验

更新日期：2026-08-15  
结论：技术上可采用“公开页 SSG + 登录后工作台 SPA”的混合模式；本迭代保留主配置 `ssr: false`，不直接改变生产部署形态。

## 1. 试验入口

- 配置：`frontend/experiments/ssr-spike/nuxt.config.ts`
- 构建与静态 HTML 检查：`pnpm experiment:ssr`
- hydration 与 fallback 检查：`pnpm experiment:ssr:test`
- 公开预渲染路由：`/`、`/login`、`/register`
- 登录后路由通过 route rules 保持 `ssr: false`

## 2. 验证结果

| 检查项 | 结果 |
| --- | --- |
| 首页真实 HTML | 包含“职业规划智能体”，通过 |
| 登录/注册真实 HTML | 分别包含表单标题和字段，通过 |
| `.client.vue` 图表 hydration | 首页不包含 ECharts；公开页运行时无 mismatch，通过 |
| localStorage 边界 | `useAuth`、外观偏好和缓存访问均有 client/storage guard，通过 |
| 服务端认证中间件 | `auth.ts` 在非 client 环境直接返回，不发生错误服务端跳转，通过 |
| 深链接 fallback | 未生成的 `/report` 由 `200.html` 返回应用壳，再在客户端跳转 `/login?redirect=/report`，通过 |
| 静态错误页 | 生成 `200.html` 与 `404.html`，通过 |

运行时 Playwright 共 4 条：首页、登录、注册 hydration，以及受保护深链接 fallback。

## 3. 体积与复杂度对比

| 产物 | 总原始大小 | HTML | 说明 |
| --- | ---: | ---: | --- |
| 当前 SPA generate | 1,753,169 B | 43,469 B | 17 个 HTML 壳/路由产物 |
| SSR/SSG spike | 1,832,760 B | 120,463 B | 公开页包含真实内容，增加约 79.6 KiB |

增加量主要来自三个公开页的真实 HTML 与 payload，JS/CSS 基本不变。部署复杂度增加在 route rules、两类 fallback 行为和构建时间，而不是浏览器 bundle。

## 4. 部署约束

静态 Nginx 必须优先命中真实文件和目录，再回退到 `200.html`：

```nginx
location / {
    try_files $uri $uri/ /200.html;
}
```

不能统一把所有路径重写到 `index.html`，否则 `/login`、`/register` 的预渲染 HTML 会被首页覆盖。CDN 也应让 `/login` 与 `/login/` 规范化到同一缓存键。

## 5. 推荐落地顺序

1. 先在预发布环境沿用该 layer，确认 CDN/Nginx 对目录首页和 `200.html` 的行为；
2. 将 Hero 外部图片迁到同域响应式静态资源，并采集公开首页 p75 LCP/CLS；
3. 保持 CI 中的公开路由构建、静态 HTML 断言和 hydration/fallback 4 条测试；
4. 预发布稳定后，把主配置改为 `ssr: true`，继续让登录后路由以 route rules 关闭 SSR；
5. 如目标静态平台无法同时支持目录首页与 `200.html` fallback，则维持 SPA，并保留现有首页 220 KiB gzip 与 ECharts 禁入门禁。
