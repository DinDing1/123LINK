# 第一阶段：构建环境
FROM python:3.12-slim as builder

WORKDIR /app

# 复制 requirements.txt
COPY requirements.txt .

# 安装依赖到本地目录
RUN pip install --no-cache-dir --user -r requirements.txt

# 第二阶段：运行时环境
FROM alpine:latest

WORKDIR /app

# 安装 Python、SQLite3 和其他必要的系统依赖
RUN apk add --no-cache python3 py3-pip sqlite

# 从构建阶段复制已安装的 Python 依赖
COPY --from=builder /root/.local /root/.local

# 确保脚本使用的 Python 依赖在 PATH 中
ENV PATH=/root/.local/bin:$PATH

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
