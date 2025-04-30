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

# 初始化日志和颜色输出
init()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class Config:
    # Telegram 配置
    TG_TOKEN = os.getenv("TG_TOKEN", "")
    # 代理配置
    PROXY_ENABLE = os.getenv("PROXY_ENABLE", "false").lower() == "true"  # 是否启用代理
    PROXY_URL = os.getenv("PROXY_URL", "http://10.10.10.14:7890")       # 代理地址
    # 业务配置
    BASE_URL = os.getenv("BASE_URL", "http://localhost:8123")
    OUTPUT_ROOT = "/app/strm_output"
    VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.ts', '.iso', '.rmvb', '.m2ts')
    SUBTITLE_EXTENSIONS = ('.srt', '.ass', '.sub', '.ssa', '.vtt')
    MAX_DEPTH = -1

# 动态设置代理
proxies = {
    'http': Config.PROXY_URL,
    'https': Config.PROXY_URL
} if Config.PROXY_ENABLE else None

def init_proxy_client():
    """初始化代理客户端（无括号问题版）"""
    if not Config.PROXY_ENABLE or not Config.PROXY_URL:
        return None
    
    try:
        # 明确闭合所有括号
        return AsyncClient(
            transport=HTTPTransport(proxy=Config.PROXY_URL),
            timeout=Timeout(30.0)
    except Exception as e:
        logger.error(f"代理初始化失败: {str(e)}")
        return None

def generate_strm_files(domain: str, share_key: str, share_pwd: str):
    """生成STRM文件及字幕文件"""
    base_url = Config.BASE_URL.rstrip('/')
    counts = {'video': 0, 'subtitle': 0, 'error': 0}
    
    logger.info(f"开始处理分享：{share_key}")

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
                            response = requests.get(
                                download_url,
                                headers={'User-Agent': 'Mozilla/5.0'},
                                timeout=20,
                                proxies=proxies
                            )
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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理用户消息"""
    msg = update.message.text
    logger.info(f"收到消息：{msg}")

    # 正则匹配逻辑
    pattern = r'''
        (?:https?://)?                # 协议可选
        (www\.123\d+\.com)            # 域名
        /s/                           # 固定路径
        ([\w-]+)                      # 分享码
        (?:[\?&]提取码[=:：]|提取码[：:])?  # 提取码标识符
        (\w{4})                       # 4位提取码
    '''
    match = re.search(pattern, msg, re.VERBOSE | re.IGNORECASE)
    
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
            f"✅ 处理完成！\n"
            f"⏱ 耗时：{duration.total_seconds():.1f}秒\n"
            f"🎬 视频文件：{report['video']}\n"
            f"📝 字幕文件：{report['subtitle']}\n"
            f"❌ 错误数：{report['error']}"
        )
        await update.message.reply_text(result_msg)

    except Exception as e:
        logger.error(f"处理失败：{str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ 处理失败：{str(e)}")

if __name__ == "__main__":
    # 初始化代理客户端（强制语法正确）
    async_client = init_proxy_client()
    request = HTTPXRequest(client=async_client) if async_client else None
    
    # 构建Bot应用（简化版）
    app = Application.builder().token(Config.TG_TOKEN)
    if request:
        app = app.request(request)
    app = app.build().add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    logger.info("🤖 机器人启动成功")
    app.run_polling()
    except Exception as e:
        logger.critical(f"机器人启动失败：{str(e)}")
        exit(1)
