FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（SQLite）
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# 创建数据目录
RUN mkdir -p /app/data && chmod 777 /app/data

# 复制应用代码
COPY requirements.txt .
COPY direct_link_service.py .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 设置容器时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime

# 运行命令
CMD ["uvicorn", "direct_link_service:app", "--host", "0.0.0.0", "--port", "8123", "--log-level", "warning"]
