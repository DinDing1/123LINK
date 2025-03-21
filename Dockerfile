# 第一阶段：构建环境
FROM python:3.12-slim as builder

WORKDIR /app

# 复制 requirements.txt
COPY requirements.txt .

# 全局安装 uvicorn
RUN pip install --no-cache-dir uvicorn

# 第二阶段：运行时环境
FROM python:3.12-alpine

WORKDIR /app

# 安装 SQLite3 和其他必要的系统依赖
RUN apk add --no-cache sqlite

# 从构建阶段复制 uvicorn
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

# 复制应用代码和 VERSION 文件
COPY direct_link_service.py .
COPY VERSION .

# 创建数据目录
RUN mkdir -p /app/data && chmod 777 /app/data

# 设置容器时区
ENV TZ=Asia/Shanghai
RUN apk add --no-cache tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo "$TZ" > /etc/timezone

# 运行命令
CMD ["uvicorn", "direct_link_service:app", "--host", "0.0.0.0", "--port", "8123", "--log-level", "warning"]
