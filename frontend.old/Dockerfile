# PathFy-Uni 前端 — Astro 构建 + Nginx 托管
FROM node:20-alpine AS builder

WORKDIR /app
RUN corepack enable && corepack prepare pnpm@9 --activate

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN PUBLIC_API_BASE="" pnpm build

# 运行时：Nginx 托管静态文件 + 反代 /api
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
