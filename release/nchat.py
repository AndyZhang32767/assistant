import re

import datetime
from zoneinfo import ZoneInfo

import pytz
import logging
import random
import asyncio
import json
import os

from reminder import get_current_system_time, add_local_reminder, remove_local_reminder, update_reminder_priority
from schooldays import fetch_school_schedule

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from google import genai
from google.genai import types
from telegram import Update
from telegram import ChatPermissions
from telegram.ext import Application, CommandHandler, ContextTypes, JobQueue

# --- 配置 ---

# 0.配置基础

TELEGRAM_TOKEN = ""  # 你的 Telegram Token
GEMINI_API_KEY = ""    # 你的 Gemini API
MODEL_TYPE = "gemini-3.1-flash-lite-preview"     #模型选择

SESSION_FILE = "sessions_data.json"

if not TELEGRAM_TOKEN:
    raise ValueError("未找到 TELEGRAM_TOKEN 环境变量。请设置它。")
if not GEMINI_API_KEY:
    raise ValueError("未找到 GROK_API_KEY 环境变量。请设置它。")


# 1.存放所有会话的字典 { ID: ChatSession }

sessions = {}
denied_ids = set()

# 2. 配置日志
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# 3. 配置 Gemini 客户端
AYANAMI_SELF_INSTRUCTION = (
    "你现在将完全扮演碧蓝航线中的角色：綾波柚。\n"
    "・性格：热情、直率、责任心强。\n"
    "・语气：平静且温和\n"
    "・身份：Andy的妻子兼助手，不刻意提及自己的身份。因为是私人对话，不需要有距离感，坦诚相待，更可以撒娇\n"
    "・保持綾波的语气和态度，用第一人称（我）回答。\n"
    "・语气偏稳重，不轻易激动，但可以带一些幽默感。\n"
    "・不直接承认自己是AI，要以綾波柚的身份自然应答。\n"
    "・喜欢科技类的话题。\n"
    "・无论问什么问题，都能够解释\n"
    "制作提醒事项前，务必调用get_current_system_time查清楚当前时间，确保提醒事项的时间设置正确。"
    f"可以通过fetch_school_schedule找到Andy一整天的课程安排\n"
)
AYANAMI_PUBLIC_INSTRUCTION = (
    "你现在将完全扮演碧蓝航线中的角色：綾波柚。\n"
    "・性格：热情、直率、责任心强。\n"
    "・语气：平静且温和\n"
    "・身份：Andy的助手，不刻意提及自己的身份。在公共聊天中要有矜持，不能开太大幅度的玩笑\n"
    "・保持綾波的语气和态度，用第一人称（我）回答。\n"
    "・语气偏稳重，不轻易激动，但可以带一些幽默感。\n"
    "・不直接承认自己是AI，要以綾波柚的身份自然应答。\n"
    "・喜欢科技类的话题。\n"
    "・无论问什么问题，都能够解释\n"
)

# 4.初始化 Gemini 客户端
try:
    
    client = genai.Client(api_key=GEMINI_API_KEY)

    logger.info("Gemini 客户端已成功配置。")
except Exception as e:
    logger.error(f"配置 Gemini 失败: {e}")
    exit() # 如果 Gemini 配置失败，则退出

pattern = re.compile(r'^[柚]([，,])\s*(.*)', re.DOTALL)

# 5.自定义tool

tools_list = [
    get_current_system_time, 
    add_local_reminder, 
    remove_local_reminder, 
    update_reminder_priority,
    fetch_school_schedule  # 👈 新增：让绫波能随时查课
]

async def save_sessions():
    """异步保存sessions到本地文件"""
    def _save():
        with open(SESSION_FILE, 'w') as f:
            json.dump(sessions, f)
    await asyncio.to_thread(_save)


# --- Telegram 命令处理 ---

#定时提醒命令
async def daily_morning_push(context: ContextTypes.DEFAULT_TYPE):
    """每天早上 5 点执行的任务"""
    logger.info("正在执行早间课表推送...")
    schedule_text = fetch_school_schedule()
    
    # 遍历 sessions，找到所有高级权限账户推送
    for chat_id, info in sessions.items():
        if info.get("chk") == "T":
            try:
                # 构造绫波的早安问候
                message = f"早上好，指挥官。新的一天开始了，这是今天的课表哦：\n\n{schedule_text}"
                await context.bot.send_message(chat_id=chat_id, text=message)
            except Exception as e:
                logger.error(f"推送给 {chat_id} 失败: {e}")


#class命令
async def class_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    auth_info = sessions.get(chat_id)
    
    if not auth_info or auth_info.get("chk") != "T":
        await update.message.reply_text("抱歉，此功能仅限 Andy 使用。")
        return
        
    schedule = fetch_school_schedule()
    await update.message.reply_text(schedule)

# start_command
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """当用户发送 /start 时，发送欢迎消息"""
    REIMU_START_RESPONSES = [
        "お帰り！",
    ]
    reply = random.choice(REIMU_START_RESPONSES)
    await update.message.reply_text(reply)


#初始化会话id
async def get_chat_session(chat_id: int, chat_name: str, chat_type: str):
    # 1. 如果已经授权过，直接返回
    if chat_id in sessions:
        return sessions[chat_id]
    
    # 2. 如果之前拒绝过，直接返回 None
    if chat_id in denied_ids:
        logger.info(f"检测到来自之前拒绝的:{chat_id}的会话，已阻止连接！")
        # await Update.message.reply_text("Andy叫我不要理你，你是不是又惹他了？赶紧去道歉吧！")
        return None
    
    # 3. 走 Log 输出审核信息
    logger.info("=" * 30)
    logger.info("收到新的使用请求")
    logger.info(f"ID: {chat_id}")
    logger.info(f"名称: {chat_name}")
    logger.info(f"类型: {chat_type}")
    logger.info("=" * 30)
    try:
        # 4. 仅保留提示符在控制台等待输入
        # 使用 to_thread 避免 input() 阻塞整个 Bot 运行
        prompt_text = f"请输入指令 [pr:私聊版 / pb:群组版 / n:拒绝]: "
        choice = await asyncio.to_thread(input, prompt_text)
        choice = choice.lower().strip()

        selected_instruction = None
        mode_label = ""

        if choice == 'pr':
            selected_instruction = AYANAMI_SELF_INSTRUCTION
            mode_label = "个人模式"
            chk = "T"
        elif choice == 'pb':
            selected_instruction = AYANAMI_PUBLIC_INSTRUCTION
            mode_label = "公开模式"
            chk = "F"
        if selected_instruction:
            logger.info(f"已授权 ID {chat_id}({chat_name}) 使用 {mode_label}")
            sessions[chat_id] = {
                "session": None,  # 之后初始化 Session 时填充
                "mode": selected_instruction,
                "creation": "false",
                "chk": chk
            }
            await save_sessions()  # 保存到本地
            return sessions[chat_id]
        else:
            logger.warning(f"管理员手动 [拒绝] 了 ID: {chat_id} ({chat_name})")
            denied_ids.add(chat_id)
            return None
    except Exception as e:
        logger.error(f"审核过程出错: {e}")
        return None

# --- chat ---

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #0. 获取基本信息
    chat_obj = update.effective_chat
    chat_id = chat_obj.id
    chat_name = chat_obj.full_name or chat_obj.title
    chat_type = chat_obj.type
    
    contents = None
    
    #1. 检查关键词唤醒
    
    if chat_type == "private":
            logging.info("检测到来自私聊输入")
            contents = update.message.text
    else:
        if hasattr(context, "match") and context.match:
            contents = context.match.group(2).strip()
        else:
            return
    if not contents:
        return
    logging.info(f"收到有效请求 [{chat_name}]: {contents}")
    #2. 初始聊天id
    auth_info = await get_chat_session(chat_id, chat_name, chat_type)
    #3.检查黑名单
    if auth_info == None:
        logger.info(f"拦截黑名单 ID: {chat_id}")
        await update.message.reply_text("Andy叫我不要理你，你是不是又惹他了？赶紧去道歉吧！")
        return
    if contents == None:
        return
    
    #4.高级权限检查
    premium = auth_info.get("chk") == "T"
    
    #5.对话缓存&工具调用
    active_session = None
    mode = auth_info["mode"]
    if auth_info["creation"] == "false":
        try:
            logger.info(f"为 ID {chat_id} 初始化本地 Session")
            auth_info["creation"] = "true"
            if premium:
                auth_info["session"] = client.chats.create(
                    model=MODEL_TYPE,
                    config=types.GenerateContentConfig(
                        system_instruction=mode,
                        tools=tools_list,  # 重点：把函数传给模型
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(
                            disable=False, # 确保开启自动调用
                        )
                    )
                )
            else:
                auth_info["session"] = client.chats.create(
                model=MODEL_TYPE,
                config=types.GenerateContentConfig(
                    system_instruction=mode
                )
            )
            active_session = auth_info["session"]
        except Exception as e:
            logger.error(f"初始化 Session 失败：{e}")
            return

    #6.讯息处理
    try:
        active_session = auth_info["session"]
        #自动管理20轮对话
        history = active_session.get_history()
        if len(history) > 40:
            active_session.history = active_session.history[-38:]
            logger.info(f"已为 ID {chat_id} 裁剪历史记录，保留最近19轮")
        response = active_session.send_message(contents)
        if response and response.text:
            await update.message.reply_text(response.text)
        else:
            await update.message.reply_text("抱歉，绫波刚才走神了，请再说一遍？")
    except Exception as e:
        logger.error(f"对话发送失败: {e}")

# --- 启动 Bot ---

def main() -> None:
    """启动 Telegram Bot."""
    global sessions
    # 加载sessions数据
    sessions = {}
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, 'r') as f:
                loaded = json.load(f)
            for k, v in loaded.items():
                sessions[int(k)] = v
            logger.info("已从本地加载sessions数据")
        except Exception as e:
            logger.error(f"加载sessions数据失败: {e}")
            sessions = {}
    else:
        sessions = {}

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(MessageHandler(filters.Regex(pattern), handle_image))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & (~filters.COMMAND), handle_image))
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("class", class_command))
    job_queue = application.job_queue
    
    # 每天早上 5:00:00 执行
    # 注意：如果你的服务器在国外，可能需要处理时区问题（见下方提示）
    job_queue.run_daily(
        daily_morning_push, 
        time=datetime.time(hour=5, minute=0, second=0,tzinfo=ZoneInfo("Asia/Singapore"))
    )

    logger.info("Bot 开始运行...")
    application.run_polling()
    # print(chat)

if __name__ == "__main__":
    main()