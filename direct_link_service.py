from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from p123 import P123Client, check_response, P123OSError
import logging
from datetime import datetime, timedelta, timezone
import errno  # 导入 errno 模块
import os
client = P123Client(
    passport=os.getenv("P123_PASSPORT"),
    password=os.getenv("P123_PASSWORD")
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("direct_link_service.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# 禁用 httpx 的日志
logging.getLogger("httpx").setLevel(logging.WARNING)

# 初始化客户端
client = P123Client(
    passport=os.getenv("P123_PASSPORT"),
    password=os.getenv("P123_PASSWORD")
)
token_expiry = None  # 用于存储 Token 的过期时间

def login_client():
    """登录并更新 Token 和过期时间"""
    global client, token_expiry
    try:
        # 显式登录
        login_response = client.user_login(
            {"passport": client.passport, "password": client.password, "remember": True},
            async_=False  # 确保同步调用
        )
        if isinstance(login_response, dict) and login_response.get("code") == 200:  # 修改为 200
            # 从响应中提取 Token 和过期时间
            token = login_response["data"]["token"]
            expired_at = login_response["data"].get("expire")  # 注意字段名是 "expire"，不是 "expiredAt"
            if expired_at:
                token_expiry = datetime.fromisoformat(expired_at)
            else:
                token_expiry = datetime.now() + timedelta(days=30)  # 默认有效期 30 天
            client.token = token  # 更新客户端的 Token
            logger.info("登录成功，Token 已更新")
        else:
            logger.error(f"登录失败: {login_response}")
            raise P123OSError(errno.EIO, login_response)  # 使用 errno.EIO
    except Exception as e:
        logger.error(f"登录时发生错误: {str(e)}", exc_info=True)
        raise

def ensure_token_valid():
    """确保 Token 有效，如果过期则重新登录"""
    global token_expiry
    if token_expiry is None:
        logger.info("Token 未初始化，正在重新登录...")
        login_client()
    else:
        # 将 token_expiry 转换为不带时区的 datetime 对象
        token_expiry_naive = token_expiry.replace(tzinfo=None)
        if datetime.now() >= token_expiry_naive:
            logger.info("Token 已过期，正在重新登录...")
            login_client()

# 初始化时登录
login_client()

app = FastAPI(debug=True)

@app.get("/{uri:path}")
@app.head("/{uri:path}")
async def index(request: Request, uri: str):
    try:
        logger.info(f"收到请求: {request.url}")

        # 确保 Token 有效
        ensure_token_valid()

        # 解析 URI（格式：文件名|大小|etag）
        if uri.count("|") < 2:
            logger.error("URI 格式错误，应为 '文件名|大小|etag'")
            return JSONResponse({"state": False, "message": "URI 格式错误，应为 '文件名|大小|etag'"}, 400)

        parts = uri.split("|")
        file_name = parts[0]
        size = parts[1]
        etag = parts[2].split("?")[0]
        s3_key_flag = request.query_params.get("s3keyflag", "")

        # 构造字典参数（与原代码兼容）
        payload = {
            "FileName": file_name,
            "Size": int(size),
            "Etag": etag,
            "S3KeyFlag": s3_key_flag
        }

        # 使用原 download_info 方法
        download_resp = check_response(client.download_info(payload))
        download_url = download_resp["data"]["DownloadUrl"]
        logger.info(f"302 重定向成功: {file_name}")
        return RedirectResponse(download_url, 302)

    except Exception as e:
        logger.error(f"处理失败: {str(e)}", exc_info=True)
        return JSONResponse({"state": False, "message": f"内部错误: {str(e)}"}, 500)

if __name__ == "__main__":
    from uvicorn import run
    run(app, host="0.0.0.0", port=8123, log_level="warning")
