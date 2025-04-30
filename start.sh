#!/bin/bash
# 后台启动 FastAPI 服务
uvicorn direct_link_service:app --host 0.0.0.0 --port 8123 --log-level warning &

# 启动 Telegram 机器人
python 123tgstrm.py
