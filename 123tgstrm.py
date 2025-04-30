import os
import re
import requests
from p123.tool import share_iterdir
from datetime import datetime
from colorama import init, Fore, Style
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from urllib.parse import unquote, urlparse, parse_qs
import logging

# 初始化日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class Config:
    TG_TOKEN = os.getenv("TG_TOKEN", "")
    HTTP_PROXY = os.getenv("HTTP_PROXY")
    BASE_URL = os.getenv("BASE_URL", "http://172.17.0.1:8123")
    OUTPUT_ROOT = "/app/strm_output"
    VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.ts', '.iso', '.rmvb', '.m2ts')
    SUBTITLE_EXTENSIONS = ('.srt', '.ass', '.sub', '.ssa', '.vtt')
    MAX_DEPTH = -1

# 动态设置代理
proxies = {}
if Config.HTTP_PROXY:
    proxies = {
        'http': Config.HTTP_PROXY,
        'https': Config.HTTP_PROXY
    }
    logger.info(f"已启用代理：{Config.HTTP_PROXY}")

def generate_strm_files(domain: str, share_key: str, share_pwd: str):
    """生成STRM文件（关键修正版）"""
    base_url = Config.BASE_URL.rstrip('/')
    counts = {'video': 0, 'subtitle': 0, 'error': 0}
    
    logger.info(f"开始处理分享：{share_key}")
    
    try:
        for info in share_iterdir(share_key, share_pwd, domain=domain,
                                max_depth=Config.MAX_DEPTH, predicate=lambda x: not x["is_dir"]):
            try:
                # 增强URI解析
                raw_uri = unquote(info["uri"].split("://", 1)[-1].split('?')[0])
                relpath = info["relpath"].lstrip('/')
                
                # 调试输出
                logger.debug(f"Processing: {relpath}")
                
                # 文件类型过滤
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
                                proxies=proxies  # 应用代理
                            )
                            response.raise_for_status()
                            
                            with open(output_path, 'wb') as f:
                                f.write(response.content)
                            counts['subtitle'] += 1
                            logger.info(f"下载字幕成功：{relpath}")
                            break
                        except Exception as e:
                            if retry == 2:
                                counts['error'] += 1
                                logger.error(f"字幕下载失败：{relpath}")
                            logger.warning(f"重试中({retry+1}/3)：{relpath}")

            except Exception as e:
                counts['error'] += 1
                logger.error(f"文件处理异常：{str(e)}", exc_info=True)
    
    except Exception as e:
        logger.critical(f"分享处理严重错误：{str(e)}", exc_info=True)
    
    return counts

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """增强版消息处理器"""
    msg = update.message.text
    logger.info(f"收到消息：{msg}")
    
    # 强化正则表达式
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
        logger.warning(f"无效链接格式：{msg}")
        await update.message.reply_text("❌ 链接格式错误！正确示例：\nhttps://www.123pan.com/s/xxx?提取码=1234")
        return
    
    domain, share_key, share_pwd = match.groups()
    logger.info(f"匹配成功：domain={domain}, share_key={share_key}")
    
    try:
        await update.message.reply_text("🔄 开始处理，请稍候...")
        start_time = datetime.now()
        report = generate_strm_files(domain, share_key, share_pwd)
        duration = datetime.now() - start_time
        
        result_msg = (
            f"✅ 处理完成！\n"
            f"⏱ 耗时：{duration.total_seconds():.1f}秒\n"
            f"🎬 视频：{report['video']}\n"
            f"📝 字幕：{report['subtitle']}\n"
            f"❌ 错误：{report['error']}"
        )
        await update.message.reply_text(result_msg)
        
    except Exception as e:
        logger.error(f"处理失败：{str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ 处理失败：{str(e)}")

if __name__ == "__main__":
    # 启动验证
    if not Config.TG_TOKEN:
        logger.critical("未配置TG_TOKEN环境变量！")
        exit(1)
        
    if not os.path.exists(Config.OUTPUT_ROOT):
        os.makedirs(Config.OUTPUT_ROOT, exist_ok=True)
        logger.info(f"创建输出目录：{Config.OUTPUT_ROOT}")

    # 配置代理
    request_kwargs = {}
    if proxies:
        request_kwargs['proxy_url'] = Config.HTTP_PROXY
        
    app = Application.builder() \
        .token(Config.TG_TOKEN) \
        .connect_timeout(30) \
        .read_timeout(30) \
        .request(**request_kwargs) \
        .build()
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info(f"🤖 机器人启动 | 输出目录：{os.path.abspath(Config.OUTPUT_ROOT)}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
