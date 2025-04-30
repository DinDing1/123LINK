import os
import re
import requests
from p123.tool import share_iterdir
from datetime import datetime
from colorama import init, Fore, Style
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from urllib.parse import unquote, urlparse, parse_qs

# 初始化colorama
init()

class Config:
    TG_TOKEN = os.getenv("TG_TOKEN", "")  # 默认值为空
    HTTP_PROXY = os.getenv("HTTP_PROXY")  # 允许为空
    
    # STRM生成配置（改为环境变量读取）
    BASE_URL = os.getenv("BASE_URL", "http://172.17.0.1:8123")  # 设置默认值

    OUTPUT_ROOT = "./strm_output"
    VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.ts', '.iso', '.rmvb', '.m2ts')
    SUBTITLE_EXTENSIONS = ('.srt', '.ass', '.sub', '.ssa', '.vtt')
    MAX_DEPTH = -1

proxies = {'http': Config.HTTP_PROXY, 'https': Config.HTTP_PROXY} if Config.HTTP_PROXY else None

def generate_strm_files(domain: str, share_key: str, share_pwd: str):
    """生成STRM文件及字幕文件（增强版）"""
    base_url = Config.BASE_URL.rstrip('/')
    counts = {'video': 0, 'subtitle': 0, 'error': 0}
    
    print(f"\n{Fore.YELLOW}🚀 开始处理 {domain} 的分享：{share_key}{Style.RESET_ALL}")

    for info in share_iterdir(share_key, share_pwd, domain=domain,
                            max_depth=Config.MAX_DEPTH, predicate=lambda x: not x["is_dir"]):
        try:
            raw_uri = unquote(info["uri"].split("://", 1)[-1])
            relpath = info["relpath"]
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
                print(f"{Fore.GREEN}✅ 视频文件：{relpath}{Style.RESET_ALL}")
            
            # 处理字幕文件（优化下载逻辑）
            elif ext in Config.SUBTITLE_EXTENSIONS:
                download_url = f"https://{domain}/{raw_uri}"
                for retry in range(3):
                    try:
                        response = requests.get(
                            download_url,
                            headers={
                                'User-Agent': 'Mozilla/5.0',
                                'Referer': f'https://{domain}/'
                            },
                            timeout=20,
                            proxies=proxies
                        )
                        response.raise_for_status()
                        
                        with open(output_path, 'wb') as f:
                            f.write(response.content)
                        counts['subtitle'] += 1
                        print(f"{Fore.BLUE}📝 字幕文件：{relpath}{Style.RESET_ALL}")
                        break
                    except Exception as e:
                        if retry == 2:
                            counts['error'] += 1
                            print(f"{Fore.RED}❌ 下载失败：{relpath}（最终尝试）{Style.RESET_ALL}")
                        else:
                            print(f"{Fore.YELLOW}⚠️ 重试中({retry+1}/3)：{relpath}{Style.RESET_ALL}")

        except Exception as e:
            counts['error'] += 1
            print(f"{Fore.RED}❌ 处理异常：{relpath}\n{str(e)}{Style.RESET_ALL}")
    
    return counts

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """支持所有123链接格式的消息处理器"""
    msg = update.message.text
    
    # 强化正则表达式（支持所有变体）
    pattern = r'''
        https?://                          # 协议
        (www\.123\d+\.com)                 # 域名
        /s/                                # 固定路径
        ([\w-]+)                           # 分享码
        (?:                                # 非捕获组开始
          \?.*?(?:提取码|密码|code)[=:：]?  # 问号后带参数
          |提取码[:：]?                     # 无问号直接接提取码
        )
        (\w{4})                            # 4位提取码
    '''
    match = re.search(pattern, msg, re.VERBOSE | re.IGNORECASE)
    
    if not match:
        await update.message.reply_text(
            "❌ 链接格式错误！正确示例：\n"
            "https://www.123684.com/s/xxx?提取码=1234\n"
            "https://www.123912.com/s/xxx提取码:1234"
        )
        return
    
    domain, share_key, share_pwd = match.groups()
    await update.message.reply_text(f"🔄 123网盘STRM任务执行中")

    try:
        start_time = datetime.now()
        report = generate_strm_files(domain, share_key, share_pwd)
        duration = datetime.now() - start_time

        result_msg = (
            f"✅ 处理完成！\n"
            f"⏱️ 耗时: {duration.total_seconds():.1f}秒\n"
            f"🎬 视频文件: {report['video']}\n"
            f"📝 字幕文件: {report['subtitle']}"
        )
        if report['error'] > 0:
            result_msg += f"\n❌ 遇到错误：{report['error']}个"
        
        await update.message.reply_text(result_msg)
    except Exception as e:
        await update.message.reply_text(f"❌ 处理失败：{str(e)}")

if __name__ == "__main__":
    os.makedirs(Config.OUTPUT_ROOT, exist_ok=True)
    app = Application.builder().token(Config.TG_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print(f"\n{Fore.GREEN}🤖 机器人已启动 | 输出目录：{os.path.abspath(Config.OUTPUT_ROOT)}{Style.RESET_ALL}")
    app.run_polling()
