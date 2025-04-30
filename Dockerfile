# 第一阶段：构建环境
FROM python:3.12-slim as builder

WORKDIR /app

# 复制 requirements.txt
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir --user -r requirements.txt

# 第二阶段：运行时环境
FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖（SQLite + 脚本依赖）
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    bash \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制已安装的 Python 依赖
COPY --from=builder /root/.local /root/.local

# 确保脚本使用的 Python 依赖在 PATH 中
ENV PATH=/root/.local/bin:$PATH

# 复制应用代码和配置文件
COPY direct_link_service.py .
COPY 123tgstrm.py .
COPY VERSION .
COPY start.sh .

# 创建数据目录和输出目录
RUN mkdir -p /app/data /app/strm_output && \
    chmod 777 /app/data && \
    chmod 777 /app/strm_output

# 设置容器时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime

# 赋予启动脚本执行权限
RUN chmod +x start.sh

# 运行命令
CMD ["./start.sh"]
