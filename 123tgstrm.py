import os
import re
import requests
from p123.tool import share_iterdir
from datetime import datetime
from colorama import init, Fore, Style
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from urllib.parse import unquote
import logging

# 初始化日志和颜色输出
init()
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',  # 移除 %(name)s
    level=logging.INFO
)
# 抑制第三方库的 INFO 日志
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

class Config:
    # 从环境变量读取配置（移除 HTTP_PROXY）
    TG_TOKEN = os.getenv("TG_TOKEN", "")
    BASE_URL = os.getenv("BASE_URL", "http://localhost:8123")
    OUTPUT_ROOT = "/app/strm_output"
    VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.ts', '.iso', '.rmvb', '.m2ts')
    SUBTITLE_EXTENSIONS = ('.srt', '.ass', '.sub', '.ssa', '.vtt')
    MAX_DEPTH = -1

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

                # 处理字幕文件（移除代理逻辑）
                elif ext in Config.SUBTITLE_EXTENSIONS:
                    download_url = f"https://{domain}/{raw_uri}"
                    for retry in range(3):
                        try:
                            response = requests.get(
                                download_url,
                                headers={'User-Agent': 'Mozilla/5.0'},
                                timeout=20
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

    # 强化正则匹配（支持所有常见格式）
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
        await update.message.reply_text(
            "❌ 链接格式错误！"
        )
        return

    domain, share_key, share_pwd = match.groups()
    await update.message.reply_text("🔄 123STRM开始处理，请稍候...")

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
    # 启动验证
    if not Config.TG_TOKEN:
        logger.critical("未配置 TG_TOKEN 环境变量！")
        exit(1)

    # 初始化 Bot（移除代理配置）
    try:
        app = Application.builder() \
            .token(Config.TG_TOKEN) \
            .build()
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        logger.info("🤖 机器人启动成功 | 输出目录：/app/strm_output")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.critical(f"机器人启动失败：{str(e)}")
        exit(1)
