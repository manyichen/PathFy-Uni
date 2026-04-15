# Flask Backend (MySQL Auth)

## 1) 安装依赖

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 2) 初始化数据库

在 MySQL 中执行 `schema.sql`。

## 3) 配置环境变量

复制 `.env.example` 为 `.env`，并确认：

- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_DATABASE`
- `FRONTEND_ORIGIN`

## 4) 启动服务

```bash
python run.py
```

默认地址：`http://127.0.0.1:5000`

## 5) API

- `POST /api/auth/register`
  - body: `{ "username": "test_user", "email": "a@b.com", "password": "123456" }`
- `POST /api/auth/login`
  - body: `{ "account": "test_user_or_email", "password": "123456" }`
- `GET /api/auth/me`
  - header: `Authorization: Bearer <token>`
