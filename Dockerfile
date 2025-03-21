# 第一阶段：构建环境
FROM python:3.12-slim as builder

WORKDIR /app

# 复制 requirements.txt
COPY requirements.txt .

# 全局安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 第二阶段：运行时环境
FROM python:3.12-alpine

WORKDIR /app

# 安装 SQLite3、libc6-compat 和 tzdata（合并为一条命令）
RUN apk add --no-cache sqlite libc6-compat tzdata && \
    # 设置容器时区
    ln -snf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    echo "Asia/Shanghai" > /etc/timezone

# 从构建阶段复制 Python 的 site-packages
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

# 复制应用代码和 VERSION 文件
COPY direct_link_service.py .
COPY VERSION .

# 创建数据目录（使用更严格的权限）
RUN mkdir -p /app/data && chmod 755 /app/data

# 运行命令
CMD ["uvicorn", "direct_link_service:app", "--host", "0.0.0.0", "--port", "8123", "--log-level", "warning"]
