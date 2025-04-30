import os
import re
import requests
import httpx
from p123.tool import share_iterdir
from datetime import datetime
from colorama import init, Fore, Style
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.request import HTTPXRequest
from urllib.parse import unquote
import logging
from httpx import AsyncClient, HTTPTransport, Timeout

# --------------- 初始化日志 ---------------
init()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --------------- 配置类 ---------------
class Config:
    TG_TOKEN = os.getenv("TG_TOKEN", "")  # 必填
    PROXY_ENABLE = os.getenv("PROXY_ENABLE", "false").lower() == "true"
    PROXY_URL = os.getenv("PROXY_URL", "")
    BASE_URL = os.getenv("BASE_URL", "http://localhost:8123")
    OUTPUT_ROOT = "/app/strm_output"
    VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.ts', '.iso', '.rmvb', '.m2ts')
    SUBTITLE_EXTENSIONS = ('.srt', '.ass', '.sub', '.ssa', '.vtt')
    MAX_DEPTH = -1

# --------------- 代理初始化（已修复括号问题）---------------
def init_proxy_client():
    """初始化代理客户端（明确括号闭合）"""
    if not Config.PROXY_ENABLE or not Config.PROXY_URL:
        return None
    try:
        return AsyncClient(
            transport=HTTPTransport(proxy=Config.PROXY_URL),
            timeout=Timeout(30.0)
    except Exception as e:
        logger.error(f"代理初始化失败：{str(e)}")
        return None

# --------------- 文件生成逻辑 ---------------
def generate_strm_files(domain: str, share_key: str, share_pwd: str):
    base_url = Config.BASE_URL.rstrip('/')
    counts = {'video': 0, 'subtitle': 0, 'error': 0}
    
    try:
        for info in share_iterdir(share_key, share_pwd, domain=domain,
                                max_depth=Config.MAX_DEPTH, predicate=lambda x: not x["is_dir"]):
            try:
                raw_uri = unquote(info["uri"].split("://", 1)[-1].split('?')[0])
                relpath = info["relpath"].lstrip('/')
                ext = os.path.splitext(relpath)[1].lower()

                if ext not in Config.VIDEO_EXTENSIONS + Config.SUBTITLE_EXTENSIONS:
                    continue

                output_path = os.path.join(Config.OUTPUT_ROOT, relpath)
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                # 处理视频文件
                if ext in Config.VIDEO_EXTENSIONS:
                    strm_path = os.path.splitext(output_path)[0] + '.strm'
                    with open(strm_path, 'w', encoding='utf-8') as f:
                        f.write(f"{base_url}/{raw_uri}")
                    counts['video'] += 1
                    logger.info(f"生成视频STRM：{relpath}")

                # 处理字幕文件
                elif ext in Config.SUBTITLE_EXTENSIONS:
                    download_url = f"https://{domain}/{raw_uri}"
                    for retry in range(3):
                        try:
                            response = requests.get(download_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
                            response.raise_for_status()
                            with open(output_path, 'wb') as f:
                                f.write(response.content)
                            counts['subtitle'] += 1
                            break
                        except Exception as e:
                            if retry == 2:
                                counts['error'] += 1
                                logger.error(f"字幕下载失败：{relpath}")

            except Exception as e:
                counts['error'] += 1
                logger.error(f"文件处理异常：{relpath} - {str(e)}")

    except Exception as e:
        logger.critical(f"分享处理失败：{str(e)}")
        counts['error'] += 1

    return counts

# --------------- 消息处理 ---------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    logger.info(f"收到消息：{msg}")

    # 正则匹配逻辑
    match = re.search(
        r'(?:https?://)?(www\.123\d+\.com)/s/([\w-]+)(?:[\?&]提取码[=:：]|提取码[：:])?(\w{4})',
        msg,
        re.IGNORECASE
    )
    
    if not match:
        await update.message.reply_text("❌ 链接格式错误！正确示例：\nhttps://www.123pan.com/s/xxx提取码1234")
        return

    domain, share_key, share_pwd = match.groups()
    await update.message.reply_text("🔄 开始处理，请稍候...")

    try:
        start_time = datetime.now()
        report = generate_strm_files(domain, share_key, share_pwd)
        duration = datetime.now() - start_time
        result_msg = (
            f"✅ 处理完成！\n⏱ 耗时：{duration.total_seconds():.1f}秒\n"
            f"🎬 视频文件：{report['video']}\n📝 字幕文件：{report['subtitle']}\n❌ 错误数：{report['error']}"
        )
        await update.message.reply_text(result_msg)
    except Exception as e:
        logger.error(f"处理失败：{str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ 处理失败：{str(e)}")

# --------------- 主程序 ---------------
if __name__ == "__main__":
    if not Config.TG_TOKEN:
        logger.critical("❌ 未配置 TG_TOKEN 环境变量！")
        exit(1)

    # 初始化代理（无括号问题）
    async_client = init_proxy_client()
    request = HTTPXRequest(client=async_client) if async_client else None

    # 构建 Bot 应用
    try:
        app = Application.builder().token(Config.TG_TOKEN)
        if request:
            app = app.request(request)
        app = app.build().add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        logger.info("🤖 机器人启动成功 | 输出目录：/app/strm_output")
        app.run_polling()
    except Exception as e:
        logger.critical(f"机器人启动失败：{str(e)}")
        exit(1)
