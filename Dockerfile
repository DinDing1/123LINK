# 使用Python 3.12 slim镜像减小体积
FROM python:3.12-slim

WORKDIR /app

# 先安装依赖以利用Docker缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY direct_link_service.py .

# 运行命令（使用--log-level warning减少uvicorn日志）
CMD ["uvicorn", "direct_link_service:app", "--host", "0.0.0.0", "--port", "8123", "--log-level", "warning"]
