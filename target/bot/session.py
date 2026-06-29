#=======================================================================================
#.       bot/session.py — 会话管理（授权、持久化、黑名单）
#.
#.       管理所有与用户会话相关的运行时状态和持久化：
#.         1. sessions 字典 — 内存中的用户授权信息 {chat_id: {mode, chk, ...}}
#.         2. save_history 字典 — 内存中的对话历史 {chat_id: [types.Content, ...]}
#.         3. 新用户授权 — get_chat_session() 通过 TUI 弹窗或 console input 获取授权
#.         4. 持久化 — 将以上数据读写到 data/ 目录下的 JSON 文件
#.
#.       被 bot/main.py 加载/保存，被 bot/handlers.py 每条消息调用。
#=======================================================================================

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# -- 从 core/config.py 拉取会话文件路径和两种 System Prompt
from core.config import SESSION_FILE, PRIVATE_INSTRUCTION, PUBLIC_INSTRUCTION

logger = logging.getLogger(__name__)

#=======================================================================================
#.       持久化文件路径
#.       HISTORY_FILE — 对话历史 JSON（只保存文本部分，跳过二进制 blob）
#.       sessions 中 chk="D" 表示被 Ban 的用户
#=======================================================================================
HISTORY_FILE = os.path.join(os.path.dirname(SESSION_FILE), "history.json")

#=======================================================================================
#.       模块级运行时状态（内存中）
#.
#.       sessions     — {user_id: {"chk": "T"|"F"|"D", "name": str}}
#.                       mode 由 chk 运行时查 config 生成，不持久化
#.       save_history — {chat_id: [types.Content, ...]}  对话历史（Gemini 格式）
#.       denied_ids   — {int, ...}  已被拒绝授权的用户 chat_id 集合
#=======================================================================================
sessions = {}
save_history = {}


#=======================================================================================
#.       Sessions 持久化 — 读写 sessions 字典到 JSON 文件
#=======================================================================================

#=============================================================
#.       将内存中的 sessions 字典异步写入 JSON 文件
#.       使用 asyncio.to_thread 避免阻塞事件循环
#=============================================================
async def persist_sessions():
    def _save():
        with open(SESSION_FILE, 'w') as f:
            json.dump(sessions, f)
    await asyncio.to_thread(_save)


#=============================================================
#.       从 JSON 文件恢复 sessions 字典到内存
#.       JSON 的 key 是字符串，恢复时转为 int
#=============================================================
def load_sessions() -> None:
    sessions.clear()
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, 'r') as f:
                loaded = json.load(f)
            for k, v in loaded.items():
                # 迁移：只保留 chk + name，丢弃旧格式的 mode/session/creation
                sessions[int(k)] = {
                    "chk": v.get("chk", "F"),
                    "name": v.get("name", f"ID: {k}"),
                }
            logger.info(f"已恢复 {len(sessions)} 个历史会话。")
        except Exception as e:
            logger.error(f"加载 sessions 失败: {e}")
            sessions.clear()


#=======================================================================================
#.       History 持久化 — 读写对话历史
#.       只保存文本部分（types.Part.text），跳过二进制 blob（无法 JSON 序列化）。
#.       保存格式：{chat_id: [{role: "user"/"model", parts: [{text: "..."}]}, ...]}
#=======================================================================================

#=============================================================
#.       将内存中的 save_history 异步写入 JSON 文件
#.       遍历每个 chat 的 Content 列表，提取 role 和文本 parts，
#.       跳过二进制 blob（图片/文件等二进制数据不持久化）
#=============================================================
async def persist_history():
    def _save():
        data = {}
        for chat_id, contents in save_history.items():
            rows = []
            for c in contents:
                row = {"role": getattr(c, "role", "user"), "parts": []}
                if hasattr(c, "parts"):
                    for p in c.parts:
                        if hasattr(p, "text") and p.text is not None:
                            row["parts"].append({"text": p.text})
                        # 跳过二进制 blob（无法 JSON 序列化）
                rows.append(row)
            data[str(chat_id)] = rows
        with open(HISTORY_FILE, 'w') as f:
            json.dump(data, f, ensure_ascii=False)
    await asyncio.to_thread(_save)


#=============================================================
#.       从 JSON 文件恢复 save_history 到内存（仅文本部分）
#.       将 JSON 中的 {role, parts: [{text}]} 结构转回 google.genai.types.Content 对象
#=============================================================
def load_history() -> None:
    from google.genai import types

    save_history.clear()
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                data = json.load(f)
            for chat_id_str, rows in data.items():
                contents = []
                for row in rows:
                    parts = []
                    for p in row.get("parts", []):
                        if "text" in p:
                            parts.append(types.Part.from_text(text=p["text"]))
                    if parts:
                        contents.append(types.Content(role=row["role"], parts=parts))
                save_history[int(chat_id_str)] = contents
            logger.info(f"已恢复 {len(save_history)} 个会话的历史记录。")
        except Exception as e:
            logger.error(f"加载 history 失败: {e}")
            save_history.clear()


#=======================================================================================
#.       会话授权 — 新用户接入流程
#=======================================================================================

# -- _auth_callback → tui/app.py on_mount() 通过 set_auth_callback() 设置 TUI 弹窗回调
#=============================================================
#.       _auth_callback — TUI 模式下的新用户授权回调
#.       当 get_chat_session() 遇到新用户时，调用此回调弹出授权弹窗。
#.       若为 None 则降级为 console input 模式。
#=============================================================
_auth_callback = None


def set_auth_callback(cb):
    #.       TUI 调用此函数注入弹窗授权回调，替代 console input。
    global _auth_callback
    _auth_callback = cb


#=======================================================================================
#.       发送确认设置 & 待确认消息队列
#.       _confirm_premium: True = Premium 用户的消息需确认后才发送
#.       _confirm_normal:  True = Normal 用户的消息需确认后才发送
#.       _pending_messages: 待确认消息队列（FIFO，先进先出）
#=======================================================================================

from tui.widgets.permission_modal import PREMIUM, NORMAL

_confirm_premium: bool = PREMIUM
_confirm_normal: bool = NORMAL


@dataclass
class PendingMessage:
    """一条待确认的回复消息。"""
    msg_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    text: str = ""
    chat_id: int = 0
    message: Any = None          # telegram.Message 对象，用于 reply_text
    chk: str = "F"               # 用户权限标记
    timestamp: datetime = field(default_factory=datetime.now)


_pending_messages: list[PendingMessage] = []


def confirm_send(text: str, chk: str, chat_id: int, message) -> bool:
    """非阻塞发送确认。

    根据 _confirm_premium / _confirm_normal 决定是否需要确认。
    - 无需确认 → asyncio.create_task 直接发送，返回 True
    - 需确认 → 加入 _pending_messages 队列，返回 False

    不 await，不阻塞 handler 流程。
    """
    # Premium 用户：_confirm_premium=False 时直接发送
    if chk == "T" and not _confirm_premium:
        asyncio.create_task(message.reply_text(text))
        return True
    # Normal 用户：_confirm_normal=False 时直接发送
    if chk != "T" and not _confirm_normal:
        asyncio.create_task(message.reply_text(text))
        return True
    # 需要确认 → 加入队列
    msg = PendingMessage(
        text=text,
        chat_id=chat_id,
        message=message,
        chk=chk,
    )
    _pending_messages.append(msg)
    logger.info(f"[确认队列] chat_id={chat_id} | 队列长度={len(_pending_messages)}")
    return False


#=============================================================
#.       确认设置 getter / setter
#=============================================================

def get_confirm_settings() -> tuple[bool, bool]:
    """返回 (confirm_premium, confirm_normal)。"""
    return (_confirm_premium, _confirm_normal)


def set_confirm_settings(premium: bool, normal: bool) -> None:
    """设置 premium / normal 用户是否需要确认，并写回 permission_modal.py。"""
    global _confirm_premium, _confirm_normal
    _confirm_premium = premium
    _confirm_normal = normal
    # 不阻塞 UI：后台线程写盘
    import threading
    threading.Thread(target=_persist_confirm_to_modal, daemon=True).start()


# -- permission_modal.py 的路径（相对于 session.py 向上两级）
_MODAL_PATH = os.path.join(os.path.dirname(__file__), "..", "tui", "widgets", "permission_modal.py")


def _persist_confirm_to_modal() -> None:
    """将 _confirm_premium / _confirm_normal 写回 permission_modal.py 的 PREMIUM / NORMAL 常量。"""
    try:
        normalized = os.path.normpath(_MODAL_PATH)
        with open(normalized, 'r') as f:
            lines = f.readlines()

        premium_val = "True" if _confirm_premium else "False"
        normal_val = "True" if _confirm_normal else "False"

        for i, line in enumerate(lines):
            if line.strip().startswith("PREMIUM = ") or line.strip().startswith("PREMIUM="):
                lines[i] = f"PREMIUM = {premium_val}\n"
            elif line.strip().startswith("NORMAL = ") or line.strip().startswith("NORMAL="):
                lines[i] = f"NORMAL = {normal_val}\n"

        with open(normalized, 'w') as f:
            f.writelines(lines)
    except Exception as e:
        logger.error(f"持久化 confirm 设置到 permission_modal.py 失败: {e}")


#=============================================================
#.       待确认消息队列操作
#=============================================================

def get_pending_messages() -> list[PendingMessage]:
    """获取当前所有待确认的消息（按加入顺序，旧→新）。"""
    return list(_pending_messages)


def remove_pending_message(msg_id: str) -> PendingMessage | None:
    """从队列移除指定 msg_id 的消息。返回被移除的消息或 None。"""
    for i, msg in enumerate(_pending_messages):
        if msg.msg_id == msg_id:
            return _pending_messages.pop(i)
    return None


#=============================================================
#.       get_chat_session() — 获取或创建用户会话（授权入口）
#.
#.       调用时机：每次收到用户消息时（bot/handlers.py 中的各个 handler）。
#.
#.       逻辑分支：
#.         1. chat_id 已在 sessions 中 → 直接返回已授权会话
#.         2. chat_id 在 denied_ids 中 → 返回 None（黑名单拦截）
#.         3. 新用户 → 通过 TUI 弹窗（_auth_callback）或 console input 获取管理员选择：
#.            - "pr" → 分配 PRIVATE_INSTRUCTION，chk="T"（premium）→ 写入 sessions
#.            - "pb" → 分配 PUBLIC_INSTRUCTION，chk="F"（normal）→ 写入 sessions
#.            - 其他 → 加入 denied_ids，返回 None
#.
#.       返回：sessions[chat_id] dict 或 None（被拒绝）
#=============================================================
async def get_chat_session(chat_id: int, chat_name: str, chat_type: str,
                           sender_id: int = None, sender_name: str = None):
    #.       获取或创建用户会话。
    #.       权限以个人（sender_id）为单位，群聊中每个成员独立授权。
    #.       history 仍以 chat_id 为单位（群友共享上下文）。
    #.
    #.       私聊时 sender_id == chat_id。
    #.       群聊时 sender_id 是发言者 ID，chat_id 是群组 ID。
    #.
    # 统一用 sender_id 做权限 key（私聊时 = chat_id）
    auth_id = sender_id if sender_id else chat_id
    display_name = sender_name or chat_name

    def _with_mode(info: dict) -> dict:
        """运行时注入 mode（不持久化），保持 sessions 精简。"""
        result = dict(info)
        chk = info.get("chk", "F")
        result["mode"] = PRIVATE_INSTRUCTION if chk == "T" else PUBLIC_INSTRUCTION
        return result

    # 1. 已在 sessions 中 — 检查是否被 ban
    if auth_id in sessions:
        if sessions[auth_id].get("chk") == "D":
            logger.info(f"拦截已拒绝 ID: {auth_id} ({display_name})")
            return None
        return _with_mode(sessions[auth_id])

    # 3. 新用户 — 输出日志等待管理员决定
    context = f"{chat_name}(群聊)" if chat_type != "private" else "私聊"
    logger.info("=" * 20)
    logger.info(f"[新请求] user_id={auth_id} | 名称={display_name} | 来源={context}")
    logger.info("=" * 20)

    try:
        if _auth_callback is not None:
            # TUI 模式：弹窗显示 sender 信息 + 群组上下文
            choice = await _auth_callback(auth_id, display_name, chat_type,
                                          chat_id if chat_type != "private" else None,
                                          chat_name if chat_type != "private" else None)
        else:
            # 命令行模式：阻塞等待 console input
            choice = await asyncio.to_thread(input, "[pr=私聊 / pb=群聊 / n=拒绝]: ")
            choice = choice.lower().strip()

        if choice == 'pr':
            mode_label = "私聊(premium)"
            chk = "T"
        elif choice == 'pb':
            mode_label = "群聊(普通)"
            chk = "F"
        else:
            logger.warning(f"[拒绝] user_id={auth_id} ({display_name})")
            sessions[auth_id] = {"chk": "D", "name": display_name}
            await persist_sessions()
            return None

        sessions[auth_id] = {"chk": chk, "name": display_name}
        # history 仍按 chat_id 存储（群聊共享上下文）
        if chat_id not in save_history:
            save_history[chat_id] = []
        await persist_sessions()
        logger.info(f"[授权] user_id={auth_id} ({display_name}) -> 模式={mode_label}")
        return _with_mode(sessions[auth_id])

    except Exception as e:
        logger.error(f"审核过程异常: {e}")
        return None


#=============================================================
#.       clear_chat_history() — 清除指定 chat 的对话历史
#.       将 save_history[chat_id] 重置为空列表并立即持久化。
#.       被 bot/handlers.py 的 /clear 命令调用。
#=============================================================
async def clear_chat_history(chat_id: int) -> None:
    save_history[chat_id] = []
    await persist_history()
    logger.info(f"[清除] chat_id={chat_id} 的对话历史已清除")
