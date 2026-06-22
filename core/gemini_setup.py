#=======================================================================================
#.       core/gemini_setup.py — Gemini 客户端初始化与工具函数注册
#.       负责三件事：
#.         1. 单例化 Gemini 客户端创建（支持代理配置）
#.         2. 注册可供模型调用的工具函数列表（Function Calling）
#.         3. 安全过滤器设置（私聊模式关闭过滤以允许更自由的内容）
#.       被 bot/handlers.py 中的消息处理器调用。
#=======================================================================================

import logging

from google import genai
from google.genai import types

# -- 从 core/config.py 拉取 API 密钥和代理配置
from core.config import GEMINI_API_KEY, PROXY_URL
# -- 从 tools/ 目录动态扫描所有工具插件
from utils.tool_scanner import scan_tools

logger = logging.getLogger(__name__)

# 启动时扫描一次，构建工具列表
_tools = scan_tools()

# 为 premium 模式收集所有工具函数，为 normal 模式仅收集 pb 工具
_tool_callables = {}
tools_list = []
toolsp_list = []

for t in _tools:
    _tool_callables[t.name] = t.functions
    for fn in t.functions.values():
        if t.access in ("pr", "pb"):
            tools_list.append(fn)
        if t.access == "pb":
            toolsp_list.append(fn)


def lookup_tool(name: str):
    """根据函数名查找 callable。"""
    for mod_funcs in _tool_callables.values():
        if name in mod_funcs:
            return mod_funcs[name]
    return None

#=======================================================================================
#.       Gemini 客户端单例
#.       通过 get_gemini_client() 获取，首次调用时初始化并缓存。
#.       若 PROXY_URL 非空，将代理参数注入 HTTP 选项，所有 API 请求走代理通道。
#=======================================================================================

_client = None


def get_gemini_client() -> genai.Client:
    #.
    #.       获取或初始化 Gemini 客户端单例。
    #.       若 core/config.py 中 PROXY_URL 非空，则所有请求经代理转发。
    #.
    global _client
    if _client is None:
        try:
            if PROXY_URL:
                http_options = types.HttpOptions(client_args={"proxy": PROXY_URL})
                _client = genai.Client(api_key=GEMINI_API_KEY, http_options=http_options)
                logger.info(f"Gemini 客户端初始化成功（使用代理: {PROXY_URL}）。")
            else:
                _client = genai.Client(api_key=GEMINI_API_KEY)
                logger.info("Gemini 客户端初始化成功。")
        except Exception as e:
            logger.critical(f"Gemini 客户端初始化失败，程序退出: {e}")
            raise
    return _client


# -- safety_settings_off → bot/handlers.py handle_message() / handle_reply() 中 premium 模式使用
#=======================================================================================
#.       safety_settings_off — 安全过滤器关闭配置
#.       私聊 Premium 模式下将所有安全过滤类别设为 BLOCK_NONE，
#.       允许模型在私密场景下产生更自由的内容输出。
#.       群聊 Normal 模式下不使用此配置（保持默认安全级别）。
#=======================================================================================
safety_settings_off = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]
