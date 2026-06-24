#=======================================================================================
#.       bot/main.py — Bot 入口与组装
#.       负责三件事：
#.         1. create_application() — 构建 Telegram Application，注册消息/
#.            命令处理器和定时任务（同时供 TUI 模式复用）
#.         2. daily_morning_push() — 每日定时向 premium 用户推送课表
#.         3. main() — 命令行模式的阻塞式 polling 入口
#=======================================================================================

import logging
import os

from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram.request import HTTPXRequest

# -- 从 bot/handlers.py 导入所有消息和命令处理器
from bot.handlers import start_command, class_command, clear_command, handle_message, handle_reply, handle_file
# -- 从 bot/session.py 导入会话持久化函数和运行时 sessions 字典
from bot.session import load_sessions, load_history, persist_history, sessions
# -- 从 core/config.py 拉取 Bot Token、代理地址和版本号
from core.config import TELEGRAM_TOKEN, PROXY_URL, VERSION
from core.logging_setup import setup_logging
from utils.scheduler import register_schedule, check_schedules, set_timezone

# 安全导入：插件可能不存在
try:
    from tools.schooldays import PUSH_HOUR, PUSH_MINUTE, PUSH_SECOND, PUSH_TIMEZONE, fetch_school_schedule
    _has_schooldays = True
except ImportError:
    _has_schooldays = False

try:
    from tools.qbittorrent import _check_qbittorrent_torrents, QB_POLL_INTERVAL
    _has_qbittorrent = True
except ImportError:
    _has_qbittorrent = False

logger = logging.getLogger(__name__)


#=======================================================================================
#.       每日早间推送任务
#.       由调度器在每天 PUSH_HOUR:PUSH_MINUTE:PUSH_SECOND (PUSH_TIMEZONE) 触发。
#.       检查侧边栏 morning_push 开关，关闭时跳过。
#.       遍历 sessions 字典，找到所有 chk="T"（premium）用户，
#.       调用 fetch_school_schedule() 获取当日课表并逐一发送。
#=======================================================================================

async def daily_morning_push(context):
    from tui.feature_flags import flag
    if not flag("morning_push"):
        logger.info("早间推送已关闭（侧边栏开关），跳过。")
        return

    logger.info("执行早间课表推送任务...")
    schedule_text = fetch_school_schedule()

    push_count = 0
    for cid, info in sessions.items():
        if info.get("chk") == "T":
            try:
                message = f"早上好。新的一天开始了，这是今天的课表哦：\n\n{schedule_text}"
                await context.bot.send_message(chat_id=cid, text=message)
                push_count += 1
                logger.info(f"课表推送成功 -> chat_id={cid}")
            except Exception as e:
                logger.error(f"课表推送失败 -> chat_id={cid}: {e}")

    logger.info(f"早间推送完成，共推送 {push_count} 个账户。")


#=======================================================================================
#.       Shutdown 回调 — 在 Bot 停止前将内存中的聊天历史持久化到 JSON 文件
#=======================================================================================

async def _save_history_on_shutdown(application):
    await persist_history()
    logger.info("历史记录已保存。")


#=======================================================================================
#.       create_application() — 构建并配置 Telegram Application
#.
#.       执行流程：
#.         1. 初始化日志系统（幂等）
#.         2. 将 PROXY_URL 写入环境变量（确保 httpx 所有请求走代理）
#.         3. 从本地 JSON 文件恢复 sessions / history / denied_ids
#.         4. 构建 Application 对象（有代理则注入 HTTPXRequest）
#.            — 同时通过 .post_shutdown() 注册持久化回调
#.         5. 注册 Handler — 顺序很重要：
#.            a. REPLY + (TEXT|PHOTO) → handle_reply （回复消息，优先级最高）
#.            b. Document|PHOTO|VIDEO|AUDIO|VOICE → handle_file （文件/媒体）
#.            c. TEXT + 非命令 → handle_message （普通文字消息）
#.            d. /start → start_command
#.            e. /class → class_command
#.            f. /clear → clear_command
#.         6. 注册每日 05:00 SGT 的课表推送定时任务
#.
#.       返回配置完成但尚未启动的 Application 对象。
#=======================================================================================

def create_application() -> Application:
    # 1. 配置日志
    setup_logging()

    # 2. 设置代理环境变量（确保 httpx 所有请求都走代理）
    if PROXY_URL:
        os.environ["HTTP_PROXY"] = PROXY_URL
        os.environ["HTTPS_PROXY"] = PROXY_URL
        os.environ["ALL_PROXY"] = PROXY_URL
        logger.info(f"已设置代理环境变量: {PROXY_URL}")

    # 3. 从本地文件恢复上次的会话记录（sessions / history / denied_ids）
    load_sessions()
    load_history()

    # 4. 构建 Application（如配置了代理则注入 HTTPXRequest 走代理通道）
    if PROXY_URL:
        request = HTTPXRequest(
            proxy=PROXY_URL,
            connect_timeout=15.0,
            read_timeout=30.0,
            write_timeout=15.0,
        )
        application = (
            Application.builder()
            .token(TELEGRAM_TOKEN)
            .post_shutdown(_save_history_on_shutdown)
            .request(request)
            .get_updates_request(request)
            .build()
        )
        logger.info(f"Telegram 使用代理: {PROXY_URL}")
    else:
        application = Application.builder().token(TELEGRAM_TOKEN).post_shutdown(_save_history_on_shutdown).build()

    # 5. 注册 Handler（顺序很重要：reply 优先 → 文件/媒体 → 普通文字 → 命令）
    application.add_handler(MessageHandler(filters.REPLY & (filters.TEXT | filters.PHOTO), handle_reply))
    application.add_handler(MessageHandler(
        filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE,
        handle_file
    ))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("class", class_command))
    application.add_handler(CommandHandler("clear", clear_command))

    # 6. 注册主调度器（每 10s 检查一次）
    application.job_queue.run_repeating(
        check_schedules,
        interval=10,
        first=5,
        name="master_scheduler",
        job_kwargs={"max_instances": 1, "misfire_grace_time": 15},
    )

    # 6a. 课表推送（通过调度器注册）
    if _has_schooldays:
        set_timezone(PUSH_TIMEZONE)
        register_schedule(
            hour=int(PUSH_HOUR), minute=int(PUSH_MINUTE),
            second=int(PUSH_SECOND),
            callback=daily_morning_push,
        )
        logger.info(f"课表推送已注册到调度器 (时区: {PUSH_TIMEZONE})。")

    # 6b. qbittorrent 下载轮询
    if _has_qbittorrent:
        logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)
        application.job_queue.run_repeating(
            _check_qbittorrent_torrents,
            interval=int(QB_POLL_INTERVAL),
            first=10,
            name="qb_poll",
            job_kwargs={"max_instances": 5, "misfire_grace_time": 30},
        )
        logger.info("qbittorrent 轮询任务已注册。")

    return application


#=======================================================================================
#.       main() — 命令行模式入口
#.       启动阻塞式 polling（shutdown 回调已在 create_application() 中注册）。
#.       该函数在 TUI 模式下不会被调用（TUI 使用 create_application() + 手动 start）。
#=======================================================================================

def main() -> None:
    application = create_application()
    logger.info(f"Bot {VERSION} 启动，开始轮询...")
    application.run_polling()


if __name__ == "__main__":
    main()
