# PathFy-Uni Flask 后端
FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 源码
COPY . .

# 确保 Playwright 浏览器已装（用于 PDF 报告导出）
RUN python -m playwright install --with-deps chromium 2>/dev/null || true

EXPOSE 5000

# 默认用 Gunicorn 启动；可通过环境变量覆盖
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "300", "--workers", "2", "app:create_app()"]
