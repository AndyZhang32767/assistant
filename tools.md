# Tools 插件开发指南

## 快速开始

在 `tools/` 目录下创建 `my_tool.py`，添加 `#==TOOL==` 头部即可自动注册，无需修改核心代码。

### 最小示例

```python
#==TOOL=======================================================================
#.       name: my_tool
#.       access: pb
#.       title: 我的工具
#.       description: 这是一个示例工具
#.       version: 1.0
#.       sidebar: my_func=我的功能
#==END TOOL===================================================================

#==CONFIG=======================================================================
API_URL = "http://localhost:8080"  # API 地址
MAX_RESULTS = 10                  # 最大结果数
#==END CONFIG===================================================================

def my_func(query: str) -> str:
    """执行搜索并返回结果。

    当用户询问"帮我查一下"时调用。

    Args:
        query: 搜索关键词。
    """
    return f"搜索结果：{query}"
```

保存后重启 Bot，`my_func` 会自动注册到 Gemini 的 Function Calling 列表中。

## TOOL 头部字段

| 字段 | 必填 | 说明 |
|------|:--:|------|
| `name` | ✓ | 模块标识，全局唯一（不含 `.py`），如 `my_tool` |
| `access` | ✓ | `pr` = 仅 premium 可用，`pb` = premium + normal 均可用 |
| `title` | | TUI 展示名称，如 `我的工具` |
| `description` | | 功能描述，显示在 TUI 设置界面头部 |
| `version` | | 版本号，如 `1.0` |
| `sidebar` | | 侧边栏开关，格式 `func_name=中文标签, ...` |

### access 说明

| 值 | 注册到 Gemini | 适用场景 |
|:--:|------|------|
| `pr` | 仅 `tools_list`（premium） | 私密功能：提醒管理、BT 下载 |
| `pb` | `tools_list` + `toolsp_list` | 通用功能：时间查询、网页搜索、课表查询 |

`pr` 工具仅在 premium 模式的私聊中可用；`pb` 工具在 premium 和 normal 模式下均可用。

### sidebar 格式

```
sidebar: func_name=标签, another_func=另一个标签
```

每项生成侧边栏一个独立开关。不填 sidebar 则不注册开关（工具始终可用，无法单独禁用）。

## CONFIG 段

`#==CONFIG==` / `#==END CONFIG==` 之间的变量会被 TUI Tools 菜单识别为可编辑参数。

### 格式要求

```python
#==CONFIG=======================================================================
SETTING_NAME = default_value  # 中文标签（行尾注释作为 TUI 显示名）
#==END CONFIG===================================================================
```

- 变量名使用大写 + 下划线
- 值支持字符串（双引号）、数字、布尔值（`True`/`False`）
- 行尾 `#` 后的注释作为 TUI 中的中文显示标签
- 不支持表达式（如 `os.path.join(...)`）和多行字符串（`"""..."""`）

### 示例

```python
#==CONFIG=======================================================================
QB_HOST = "127.0.0.1"    # qBittorrent 地址
QB_PORT = "8080"         # qBittorrent 端口
RETRY_COUNT = 3          # 重试次数
ENABLE_LOG = True        # 启用日志
#==END CONFIG===================================================================
```

### 无 CONFIG 段的工具

即使没有可配置参数，也需要添加空标记以避免解析错误：

```python
#==CONFIG=======================================================================
#.       (此工具无可配置参数)
#==CONFIG=======================================================================
#==END CONFIG===================================================================
```

## Gemini 工具函数

TOOL 头部的 `access` 决定函数的注册范围。模块中所有**公开的顶层函数**（不以 `_` 开头、有 docstring）会被自动发现并注册。

### 函数规范

1. **必须有 docstring**：Gemini 根据 `__doc__` 决定何时调用，需包含：
   - 一句话功能描述
   - 触发场景（如"当用户说 XXX 时调用"）
   - 参数说明（Args）
   - 返回值说明

2. **类型注解**：参数应有类型注解，帮助 Gemini 正确传参

3. **返回值**：统一返回 `str` 类型，内容由 Gemini 组织语言告知用户

### 完整示例

```python
def add_local_reminder(name: str, due_date_str: str, body: str = "") -> str:
    """向系统添加一条提醒事项。

    当用户说"帮我记一下"、"设个提醒"、"XX 时间提醒我"时调用。

    Args:
        name: 提醒标题（必填）。
        due_date_str: 提醒时间，格式 'YYYY-MM-DD HH:MM:SS'。
        body: 备注内容（可选）。

    Returns:
        操作结果描述字符串，告知用户是否创建成功。
    """
    # 实现逻辑...
    return f"已记录：{name}"
```

### 不被注册的函数

- 以 `_` 开头的函数（内部函数）
- 没有 docstring 的函数
- 非 callable 对象（常量、类等）

## 调试

工具函数中的 `print()` 输出会出现在 TUI 日志面板和控制台中，用于调试：

```python
def my_func(query: str) -> str:
    print(f"[MyTool] 收到查询: {query}")  # 出现在日志中
    # ...
    return result
```

建议使用 `[ToolName]` 前缀以便区分日志来源。

## 可用 API

### 定时任务注册

```python
from utils.scheduler import register_schedule, set_timezone

set_timezone("Asia/Shanghai")

# 每天 05:00 执行
register_schedule(hour=5, minute=0, callback=my_daily_task)
```

- 精度 10 秒（每整 10 秒检查一次）
- 回调签名：`async def callback(context=None)`
- 需在 `bot/main.py` 中注册

### 功能开关检查

```python
from tui.feature_flags import flag

if flag("my_func"):
    # 用户已在侧边栏开启此功能
    pass
else:
    return "此功能已关闭，请在 TUI 侧边栏开启。"
```

### 日志

```python
import logging
logger = logging.getLogger(__name__)
logger.info("操作成功")
logger.warning("需要注意")
logger.error("发生错误")
```

日志同时输出到控制台、文件（`data/bot.log`）和 TUI 日志面板。

### Bot 上下文

在 handler 调用的函数中，可通过参数接收 `chat_id` 等信息，用于区分不同用户/群组：

```python
def my_func(chat_id: int, ...) -> str:
    # chat_id 可用于标识来源
    ...
```

### 文件操作（需开启功能开关）

```python
from tui.feature_flags import flag

if not flag("file_attachment"):
    return "文件附件功能已关闭。"
```

## 已注册工具

| 工具 | access | 功能 | 主要函数 |
|------|:--:|------|------|
| system_time | pb | 获取 macOS 系统当前时间 | `get_current_system_time` |
| reminder | pr | macOS 提醒事项管理 | `add_local_reminder`, `remove_local_reminder`, `update_reminder_priority`, `update_reminder_settings`, `fetch_local_reminders` |
| schooldays | pb | 课表查询 + 每日推送 | `fetch_school_schedule` |
| search | pb | DuckDuckGo 网页搜索 | `web_search` |
| notice | pb | 群组备忘录 | `group_reminder` |
| doc_converter | pb | Office 文档 → PDF 转换 | 由 handlers 调用，不直接暴露给 Gemini |
| qbittorrent | pr | BT 下载集成 | `add_qbittorrent_download`, `fetch_qb_status` |

## 完整 TOOL 头部参考

```python
#==TOOL=======================================================================
#.       name: my_tool             # 必填，模块标识（全局唯一）
#.       access: pb                # 必填，pr=仅premium, pb=全部
#.       title: 我的工具           # TUI 展示名称
#.       description: 功能描述     # 显示在 TUI 设置界面
#.       version: 1.0              # 版本号
#.       sidebar: key1=标签1, key2=标签2  # 侧边栏开关（可选）
#==END TOOL===================================================================
```
