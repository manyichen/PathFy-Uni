# PathFy-Uni 生产部署指南

本文档说明如何将 **PathFy-Uni（suilli_mizi）** 部署到生产环境。默认场景为：

- **云服务器**：阿里云 ECS（2 vCPU / 2 GiB 内存 / 40 GiB 磁盘）
- **面板**：宝塔 Linux 面板 9.x
- **域名**：`suilli.top`（`www.suilli.top` 301 到主域名）
- **依赖同机部署**：MySQL + Neo4j + Flask 后端 + Nginx 静态前端

> **当前服务器状态（已就绪）**  
> MySQL 与 Neo4j **已在该 ECS 上部署完成**。下文第 6、7 节改为**连接验证**为主；仅需部署应用层（Flask + 前端 + Nginx + Supervisor）时，请直接阅读 [快速部署路径](#快速部署路径mysql--neo4j-已就绪)。

仓库内已提供可直接复制的配置文件：

| 文件 | 说明 |
|------|------|
| [`nginx/suilli.top.conf`](./nginx/suilli.top.conf) | Nginx 站点（HTTPS + `/api` 反代） |
| [`supervisor/pathfy-backend.conf`](./supervisor/pathfy-backend.conf) | Gunicorn 常驻进程 |
| [`env.production.example`](./env.production.example) | 后端生产环境变量模板 |
| [`docker/neo4j-compose.yml`](./docker/neo4j-compose.yml) | Neo4j Docker（2G 内存限制） |

---

## 目录

1. [架构概览](#1-架构概览)
2. [部署前检查清单](#2-部署前检查清单)
3. [服务器与宝塔初始化](#3-服务器与宝塔初始化)
4. [域名与安全组](#4-域名与安全组)
5. [上传项目代码](#5-上传项目代码)
6. [MySQL 数据库](#6-mysql-数据库)
7. [Neo4j 图数据库](#7-neo4j-图数据库)
8. [后端 Flask 服务](#8-后端-flask-服务)
9. [前端 Astro 构建](#9-前端-astro-构建)
10. [Nginx 网站与 HTTPS](#10-nginx-网站与-https)
11. [Supervisor 进程守护](#11-supervisor-进程守护)
12. [导入岗位图谱数据](#12-导入岗位图谱数据)
13. [可选：PDF 报告（Playwright）](#13-可选pdf-报告playwright)
14. [验收测试](#14-验收测试)
15. [日常更新与运维](#15-日常更新与运维)
16. [2G 内存优化建议](#16-2g-内存优化建议)
17. [常见问题排查](#17-常见问题排查)

---

## 快速部署路径（MySQL / Neo4j 已就绪）

数据库与图数据库既已在服务器上运行，**本次只需完成应用层部署**。推荐顺序：

| 步骤 | 章节 | 操作 |
|------|------|------|
| 1 | [§6](#6-mysql-数据库) | 确认 MySQL 可连、库表已导入（缺表则补跑 migrations） |
| 2 | [§7](#7-neo4j-图数据库) | 确认 Neo4j 可连、岗位数据已存在（无数据见 [§12](#12-导入岗位图谱数据)） |
| 3 | [§5](#5-上传项目代码) | 上传 / 克隆代码到 `/www/wwwroot/pathfy-uni` |
| 4 | [§8](#8-后端-flask-服务) | 创建 venv、填写 `.env`（填入**已有** MySQL / Neo4j 账号） |
| 5 | [§9](#9-前端-astro-构建) | `pnpm build` 生成 `frontend/dist` |
| 6 | [§10](#10-nginx-网站与-https) | 宝塔建站、`suilli.top` 证书、合并 Nginx 反代 |
| 7 | [§11](#11-supervisor-进程守护) | Supervisor 托管 Gunicorn |
| 8 | [§14](#14-验收测试) | 健康检查与功能验收 |

**`.env` 中需对齐已有服务的典型值：**

```env
MYSQL_HOST=127.0.0.1          # 若 MySQL 在本机；否则填实际内网地址
MYSQL_PORT=3306
MYSQL_USER=你的已有账号
MYSQL_PASSWORD=你的已有密码
MYSQL_DATABASE=suilli_mizi    # 确认库名与现网一致

NEO4J_URI=bolt://127.0.0.1:7687   # 若 Neo4j 在本机；Docker 同机一般仍是 127.0.0.1
NEO4J_USER=neo4j
NEO4J_PASSWORD=你的已有密码

FRONTEND_ORIGIN=https://suilli.top
```

---

## 1. 架构概览

```
                    ┌─────────────────────────────────────┐
                    │           用户浏览器                 │
                    └─────────────────┬───────────────────┘
                                      │ HTTPS
                                      ▼
                    ┌─────────────────────────────────────┐
                    │  Nginx（宝塔网站 suilli.top）        │
                    │  ├─ /          → frontend/dist      │
                    │  └─ /api/*     → 127.0.0.1:5000     │
                    └─────────────────┬───────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
    ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
    │ Gunicorn+Flask  │     │ MySQL 8.x       │     │ Neo4j 5.x       │
    │ 127.0.0.1:5000  │────▶│ 127.0.0.1:3306  │     │ 127.0.0.1:7687  │
    └────────┬────────┘     └─────────────────┘     └─────────────────┘
             │
             ▼
    外部 API（按需）：DeepSeek / 通义 / 豆包 / 百度 OCR
```

**开发与生产的差异：**

| 环境 | 前端 | API 访问方式 |
|------|------|--------------|
| 本地开发 | `pnpm dev`（4321 端口） | Vite 代理 `/api` → Flask |
| 生产 | `pnpm build` 静态文件 | 浏览器同源请求 `/api`（Nginx 反代） |

生产环境前端 `PUBLIC_API_BASE` 应**留空**，使用相对路径，避免跨域。

---

## 2. 部署前检查清单

部署前请确认：

- [ ] 服务器可 SSH 登录，已安装宝塔面板
- [ ] 域名 `suilli.top` 已备案（国内 ECS 对外提供 Web 服务通常需要）
- [ ] 域名 DNS 已解析到服务器公网 IP
- [x] **MySQL 已部署** — 已知连接地址、端口、库名、账号密码（见 [§6](#6-mysql-数据库) 验证）
- [x] **Neo4j 已部署** — 已知 `bolt://` 地址与认证信息（见 [§7](#7-neo4j-图数据库) 验证）
- [ ] MySQL 中已存在 `suilli_mizi` 库及业务表（若无，仅补跑 [§6.2](#62-导入表结构若尚未执行) 迁移，**无需重装 MySQL**）
- [ ] Neo4j 中已有岗位图谱数据（若无，见 [§12](#12-导入岗位图谱数据)，**无需重装 Neo4j**）
- [ ] 已准备 `SECRET_KEY`（至少 32 位随机字符串）
- [ ] 按需准备 AI / OCR 的 API Key（见 [`backend/.env.example`](../backend/.env.example)）
- [ ] 了解 2G 内存限制：MySQL + Neo4j + Gunicorn 同机运行需做内存调优

**项目目录约定（全文统一）：**

```
/www/wwwroot/pathfy-uni/
├── backend/          # Flask 后端
├── frontend/         # Astro 前端
├── generate_graph/   # Neo4j 岗位数据 ETL
└── deploy/           # 本部署文档与配置模板
```

如使用其他路径，请同步修改 Supervisor、Nginx 配置中的路径。

---

## 3. 服务器与宝塔初始化

### 3.1 安装宝塔组件

登录宝塔面板 → **软件商店**，安装：

| 组件 | 用途 | 当前环境 |
|------|------|----------|
| **Nginx** | 静态站点 + API 反向代理 | **需安装** |
| **MySQL 8.0** | 业务数据库 | **已部署，跳过安装** |
| **Supervisor 管理器** 或 **Python 项目管理器** | 托管 Gunicorn 进程 | **需安装** |
| **Docker** | 运行 Neo4j 容器 | **已部署 Neo4j 时可跳过** |

### 3.2 安装系统依赖（SSH）

```bash
# Node.js（用于构建前端，推荐 20+）
# 可在宝塔「软件商店」安装 Node 版本管理器

# 确认 Python 3.11+
python3 --version

# 若使用 pnpm
npm install -g pnpm
```

### 3.3 建议开启 Swap（2G 机器强烈建议）

```bash
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
free -h
```

---

## 4. 域名与安全组

### 4.1 DNS 解析

在域名服务商处添加 **A 记录**：

| 主机记录 | 记录类型 | 记录值 |
|----------|----------|--------|
| `@` | A | 服务器公网 IP（如 `47.104.168.245`） |
| `www` | A | 同上 |

解析生效后，`ping suilli.top` 应指向该 IP。

### 4.2 阿里云安全组

**应对公网开放：**

- `80`（HTTP，用于证书申请与跳转 HTTPS）
- `443`（HTTPS）
- 宝塔面板端口（默认 `8888`，建议改端口并限制来源 IP）

**禁止对公网开放：**

- `3306`（MySQL）
- `7687` / `7474`（Neo4j）
- `5000`（Gunicorn）

上述服务仅监听 `127.0.0.1`，由 Nginx 或本机进程访问。

---

## 5. 上传项目代码

### 方式 A：Git 克隆（推荐）

```bash
mkdir -p /www/wwwroot
cd /www/wwwroot
git clone <你的仓库地址> pathfy-uni
cd pathfy-uni
```

### 方式 B：本地上传

将项目打包上传到 `/www/wwwroot/pathfy-uni/`，保持目录结构完整。

### 权限

```bash
chown -R www:www /www/wwwroot/pathfy-uni
```

---

## 6. MySQL 数据库

> **当前环境：MySQL 已部署。** 本节只需验证连接，并在缺少表结构时补跑 SQL 迁移。

### 6.1 验证连接

```bash
# 使用你已有的账号（示例）
mysql -h 127.0.0.1 -P 3306 -u 你的用户 -p -e "SHOW DATABASES LIKE 'suilli_mizi';"
mysql -h 127.0.0.1 -P 3306 -u 你的用户 -p suilli_mizi -e "SHOW TABLES;"
```

应能看到 `users`、`student_resume` 等业务表。若库不存在，在宝塔 **数据库** 中新建 `suilli_mizi` 即可，**不必重装 MySQL 服务**。

连接信息写入 `backend/.env` 的 `MYSQL_HOST`、`MYSQL_PORT`、`MYSQL_USER`、`MYSQL_PASSWORD`、`MYSQL_DATABASE`。

### 6.2 导入表结构（若尚未执行）

若 `SHOW TABLES` 为空或缺少新功能表，按顺序补跑：

按顺序执行（SSH 或 phpMyAdmin）：

```bash
cd /www/wwwroot/pathfy-uni

mysql -u root -p suilli_mizi < backend/schema.sql
mysql -u root -p suilli_mizi < backend/migrations/002_student_resume_cap_conf.sql
mysql -u root -p suilli_mizi < backend/migrations/003_student_resume_detailed_analysis.sql
mysql -u root -p suilli_mizi < backend/migrations/004_career_reports.sql
mysql -u root -p suilli_mizi < backend/migrations/005_match_runs.sql
```

也可使用 Python 迁移脚本（效果等价）：

```bash
cd /www/wwwroot/pathfy-uni/backend
source .venv/bin/activate   # 若尚未创建 venv，见下一节
python tools/run_migration_002.py
python tools/run_migration_003.py
python tools/run_migration_004.py
python tools/run_migration_005.py
```

### 6.3 MySQL 内存调优（2G 机器，可选）

MySQL 既已运行，可在宝塔 → **软件商店** → MySQL → **性能调整** 中将 `innodb_buffer_pool_size` 设为 **128M～256M**，避免与 Neo4j、Gunicorn 争抢内存。

<details>
<summary>附录：全新安装 MySQL（当前环境可忽略）</summary>

宝塔 → **数据库** → **添加数据库**：库名 `suilli_mizi`，访问权限选本地服务器，再执行 [§6.2](#62-导入表结构若尚未执行) 导入脚本。

</details>

---

## 7. Neo4j 图数据库

> **当前环境：Neo4j 已部署。** 本节只需验证 Bolt 连接与数据是否就绪；岗位浏览、人岗匹配依赖图谱中的 Job 节点。

### 7.1 验证连接

```bash
# HTTP 探测（Neo4j 在本机时；端口以你实际部署为准）
curl -s http://127.0.0.1:7474 | head

# 或用 cypher-shell（若已安装）
cypher-shell -a bolt://127.0.0.1:7687 -u neo4j -p '你的密码' \
  "MATCH (j:Job) RETURN count(j) AS job_count LIMIT 1;"
```

- `job_count > 0`：岗位数据已就绪，可跳过 [§12](#12-导入岗位图谱数据)。
- `job_count = 0` 或查询报错：Neo4j 服务正常但**缺数据**，见 [§12](#12-导入岗位图谱数据) 导入；或检查 `.env` 中 `NEO4J_URI` / 密码是否与现网一致。

连接信息写入 `backend/.env` 的 `NEO4J_URI`、`NEO4J_USER`、`NEO4J_PASSWORD`。若 Neo4j 不在本机，将 `127.0.0.1` 改为实际内网 IP，并确保安全组**不对公网**开放 7687。

浏览器调试 Neo4j Browser 请用 SSH 隧道，**不要**将 7474 暴露到公网。

### 7.2 内存与运维（可选）

2G 机器上 Neo4j 堆内存建议 ≤512M。若使用 Docker 且需调整参数，可参考 [`deploy/docker/neo4j-compose.yml`](./docker/neo4j-compose.yml)；**已运行的实例勿随意重建容器**，以免丢失数据卷。

<details>
<summary>附录：使用 Docker 全新安装 Neo4j（当前环境可忽略）</summary>

```bash
cd /www/wwwroot/pathfy-uni
# 编辑 deploy/docker/neo4j-compose.yml 中的 NEO4J_AUTH
docker compose -f deploy/docker/neo4j-compose.yml up -d
```

</details>

---

## 8. 后端 Flask 服务

### 8.1 创建虚拟环境并安装依赖

```bash
cd /www/wwwroot/pathfy-uni/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

> **注意：** 生产环境**不要**使用 `python run.py` 对外服务。`run.py` 为 Flask 内置开发服务器，仅适合本地调试。

### 8.2 配置环境变量

```bash
cp /www/wwwroot/pathfy-uni/deploy/env.production.example .env
nano .env   # 或使用宝塔文件编辑器
```

**必须修改的项：**

| 变量 | 说明 |
|------|------|
| `SECRET_KEY` | 随机长字符串，用于 JWT 签名 |
| `MYSQL_*` | **已有** MySQL 的连接信息（见 [§6.1](#61-验证连接)） |
| `NEO4J_*` | **已有** Neo4j 的连接信息（见 [§7.1](#71-验证连接)） |
| `FRONTEND_ORIGIN` | 固定为 `https://suilli.top` |

`FRONTEND_ORIGIN` 必须与用户浏览器地址一致。当前后端 CORS 仅允许单一 Origin；`www.suilli.top` 会在 Nginx 层 301 到主域名。

按需填写 AI / OCR 相关 Key，详见 [`backend/.env.example`](../backend/.env.example)。

### 8.3 手动测试后端

```bash
cd /www/wwwroot/pathfy-uni/backend
source .venv/bin/activate
gunicorn -w 2 -b 127.0.0.1:5000 "app:create_app()" --timeout 120
```

另开终端：

```bash
curl http://127.0.0.1:5000/api/health
# 期望: {"ok":true,"message":"backend alive"}
```

测试通过后 `Ctrl+C` 停止，改由 Supervisor 托管（见第 11 节）。

---

## 9. 前端 Astro 构建

### 9.1 配置

```bash
cd /www/wwwroot/pathfy-uni/frontend
echo "PUBLIC_API_BASE=" > .env
```

`PUBLIC_API_BASE` 留空表示使用同源相对路径 `/api/...`，与 Nginx 反代配合。

### 9.2 安装依赖并构建

```bash
pnpm install
pnpm build
```

构建产物位于 `frontend/dist/`。

也可在本地 Windows 构建后，仅上传 `dist/` 目录到服务器对应路径。

### 9.3 构建失败排查

- 确认 Node.js ≥ 18（推荐 20+）
- 若服务器内存不足导致 build OOM，可在本地构建后上传 `dist/`

---

## 10. Nginx 网站与 HTTPS

### 10.1 添加站点

宝塔 → **网站** → **添加站点**：

| 项 | 值 |
|----|-----|
| 域名 | `suilli.top`、`www.suilli.top` |
| 根目录 | `/www/wwwroot/pathfy-uni/frontend/dist` |
| PHP | 纯静态（不创建 PHP） |

### 10.2 申请 SSL 证书

站点 → **SSL** → **Let's Encrypt**：

- 勾选 `suilli.top` 与 `www.suilli.top`
- 申请并开启 **强制 HTTPS**

证书路径一般为：

```
/www/server/panel/vhost/cert/suilli.top/fullchain.pem
/www/server/panel/vhost/cert/suilli.top/privkey.pem
```

### 10.3 合并 Nginx 配置

站点 → **配置文件**，参考 [`deploy/nginx/suilli.top.conf`](./nginx/suilli.top.conf) 合并或替换。

**核心配置要点：**

```nginx
# API 反代到 Gunicorn
location /api/ {
    proxy_pass http://127.0.0.1:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 120s;
    client_max_body_size 10m;
}

# 前端路由回退
location / {
    try_files $uri $uri/ /index.html;
}
```

保存后重载 Nginx。

### 10.4 HTTP 跳转

配置中已包含：

- 所有 HTTP 请求 301 到 `https://suilli.top`
- `www.suilli.top` 301 到 `https://suilli.top`

---

## 11. Supervisor 进程守护

### 方式 A：宝塔 Supervisor 管理器（推荐）

1. 软件商店安装 **Supervisor 管理器**
2. 添加守护进程：

| 字段 | 值 |
|------|-----|
| 名称 | `pathfy-backend` |
| 运行目录 | `/www/wwwroot/pathfy-uni/backend` |
| 启动命令 | 见下方 |
| 运行用户 | `www` |

启动命令：

```bash
/www/wwwroot/pathfy-uni/backend/.venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 "app:create_app()" --timeout 120 --access-logfile /www/wwwlogs/pathfy-backend-access.log --error-logfile /www/wwwlogs/pathfy-backend-error.log
```

3. 开启 **开机启动**

### 方式 B：SSH 复制配置文件

```bash
cp /www/wwwroot/pathfy-uni/deploy/supervisor/pathfy-backend.conf /etc/supervisor/conf.d/
supervisorctl reread
supervisorctl update
supervisorctl start pathfy-backend
supervisorctl status pathfy-backend
```

完整配置见 [`deploy/supervisor/pathfy-backend.conf`](./supervisor/pathfy-backend.conf)。

### 日志位置

| 日志 | 路径 |
|------|------|
| Gunicorn 访问日志 | `/www/wwwlogs/pathfy-backend-access.log` |
| Gunicorn 错误日志 | `/www/wwwlogs/pathfy-backend-error.log` |
| Nginx 访问日志 | `/www/wwwlogs/suilli.top.log` |
| Nginx 错误日志 | `/www/wwwlogs/suilli.top.error.log` |

---

## 12. 导入岗位图谱数据

**若 [§7.1](#71-验证连接) 中 `job_count > 0`，本节可跳过。**

Neo4j 已部署但尚无 Job 节点时，需导入岗位数据才能使用岗位浏览与人岗匹配。

详细步骤见 [`generate_graph/README.md`](../generate_graph/README.md)。

概要流程：

```bash
cd /www/wwwroot/pathfy-uni/generate_graph
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# 配置 .env（NEO4J_URI、LLM 相关 Key、EXCEL_PATH 等）
python script.py
# 可选：导入晋升关系
python openai_lmstudio_promotion_update.py
```

导入完成后，在前端 `/jobs` 页面应能看到岗位列表。

---

## 13. 可选：PDF 报告（Playwright）

生涯报告 PDF 导出依赖 Playwright + Chromium，内存占用较高。**2G 机器建议后期按需开启。**

```bash
cd /www/wwwroot/pathfy-uni/backend
source .venv/bin/activate
python -m playwright install chromium
python -m playwright install-deps   # Linux 系统依赖，若报错再执行
```

安装后重启 `pathfy-backend` 进程。

---

## 14. 验收测试

### 14.1 接口健康检查

```bash
curl -s https://suilli.top/api/health
# {"ok":true,"message":"backend alive"}
```

### 14.2 浏览器功能测试

按顺序验证：

| 步骤 | 页面 | 预期 |
|------|------|------|
| 1 | `https://suilli.top` | 首页正常加载 |
| 2 | `/register` | 注册成功 |
| 3 | `/login` | 登录成功 |
| 4 | `/profile` | 上传简历、生成能力画像 |
| 5 | `/jobs` | 岗位列表有数据（需 Neo4j 已导入） |
| 6 | `/match` | 人岗匹配可返回结果 |
| 7 | `/report` | 生涯报告可生成（需 AI Key） |

### 14.3 安全抽查

- [ ] `https://suilli.top/api/health` 可访问
- [ ] `http://服务器IP:5000/api/health` 从外网**不可**访问
- [ ] `http://服务器IP:3306` 从外网**不可**访问
- [ ] 浏览器 DevTools → Network 中 API 请求为同源 `/api/...`，无 CORS 报错

---

## 15. 日常更新与运维

### 15.1 更新代码

```bash
cd /www/wwwroot/pathfy-uni
git pull

# 后端依赖有变更时
cd backend && source .venv/bin/activate && pip install -r requirements.txt

# 前端有变更时
cd ../frontend && pnpm install && pnpm build

# 数据库有新迁移时，按顺序执行 migrations/*.sql

# 重启后端
supervisorctl restart pathfy-backend
# 或在宝塔 Supervisor 管理器中点击重启
```

### 15.2 数据库备份

宝塔 → **计划任务** → 添加 **备份数据库** 任务，建议每日备份 `suilli_mizi`。

Neo4j 数据备份（Docker 部署示例；非 Docker 请用对应备份方式）：

```bash
docker exec pathfy-neo4j neo4j-admin database dump neo4j --to-path=/data/backups
```

### 15.3 查看资源占用

```bash
free -h
docker stats pathfy-neo4j --no-stream
supervisorctl status
```

---

## 16. 2G 内存优化建议

| 组件 | 建议 |
|------|------|
| **Swap** | 开启 2G swapfile（见 3.3 节） |
| **MySQL** | `innodb_buffer_pool_size` = 128M～256M |
| **Neo4j** | 堆 512M、pagecache 256M（见 compose 文件） |
| **Gunicorn** | `-w 2`，勿增加 worker |
| **Playwright** | 非必需可暂不安装 |
| **前端构建** | 可在本地 build 后只上传 `dist/` |

若用户量增长或 LLM 调用频繁，建议将 ECS 升级至 **4G 内存**，或将 Neo4j 迁到独立实例。

---

## 17. 常见问题排查

### 502 Bad Gateway（访问 `/api/...`）

**原因：** Gunicorn 未运行或崩溃。

**处理：**

```bash
supervisorctl status pathfy-backend
tail -n 100 /www/wwwlogs/pathfy-backend-error.log
```

检查 `.env` 中 MySQL / Neo4j 连接是否正确。

---

### CORS 跨域错误

**原因：** `FRONTEND_ORIGIN` 与浏览器地址不一致（如用了 `http` 而非 `https`，或用了 `www` 域名）。

**处理：** 确保 `.env` 中为 `FRONTEND_ORIGIN=https://suilli.top`，且 Nginx 已将 `www` 301 到主域名。

---

### 岗位列表为空

**原因：** Neo4j 无数据或未启动。

**处理：**

```bash
docker ps | grep neo4j
# 确认 generate_graph 已执行
```

---

### 简历上传失败（413）

**原因：** Nginx 上传大小限制。

**处理：** 确认站点配置中 `client_max_body_size 10m;` 与后端 `MAX_UPLOAD_MB=10` 一致。

**隐私：** 简历原文件写入 `RESUME_UPLOAD_DIR`（默认 `backend/private_uploads/resumes`，生产建议 `/var/private/pathfy/resumes`），OCR 入库后自动删除，**不会**出现在 Nginx 静态目录中。部署时创建目录并限制权限：

```bash
sudo mkdir -p /var/private/pathfy/resumes
sudo chown www:www /var/private/pathfy/resumes
sudo chmod 700 /var/private/pathfy/resumes
```

---

### LLM 接口超时

**原因：** 匹配/报告调用外部 API 较慢。

**处理：**

- Nginx `proxy_read_timeout` 设为 `120s` 或更高
- Gunicorn `--timeout 120` 与之一致
- 检查 API Key 与网络连通性

---

### 内存不足 / 进程被 Kill

**处理：**

```bash
dmesg | tail -20          # 查看 OOM killer 记录
free -h
```

按第 16 节降低 MySQL / Neo4j 内存，或升级服务器。

---

### SSL 证书路径错误

宝塔申请证书后，若 Nginx 报证书找不到，在站点 SSL 页面查看实际路径，并更新 [`nginx/suilli.top.conf`](./nginx/suilli.top.conf) 中 `ssl_certificate` 两行。

---

## 附录：环境变量速查

完整说明见 [`backend/.env.example`](../backend/.env.example) 与 [`deploy/env.production.example`](./env.production.example)。

| 变量 | 生产典型值 |
|------|------------|
| `FLASK_ENV` | `production` |
| `FLASK_DEBUG` | `0` |
| `FRONTEND_ORIGIN` | `https://suilli.top` |
| `MYSQL_HOST` | `127.0.0.1` |
| `NEO4J_URI` | `bolt://127.0.0.1:7687` |
| `PUBLIC_API_BASE`（前端） | 留空 |

---

## 附录：相关文档

- 后端 API 与本地启动：[`backend/README.md`](../backend/README.md)
- 前端开发与构建：[`frontend/README.md`](../frontend/README.md)
- Neo4j 岗位数据 ETL：[`generate_graph/README.md`](../generate_graph/README.md)
- 项目总体设计：[`PathFy-Uni项目总体设计文档.md`](../PathFy-Uni项目总体设计文档.md)
