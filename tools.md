# Tools 插件开发指南

## 快速开始

在 `tools/` 目录下创建 `my_tool.py`，添加 TOOL 头部即可自动注册。

### 最小示例

```python
#==TOOL=======================================================================
#.       name: my_tool
#.       access: pb
#.       title: 我的工具
#.       description: 这是一个示例工具的简短描述
#.       version: 1.0
#.       sidebar: my_func=我的功能, my_other=其他功能
#==END TOOL===================================================================

#==CONFIG=======================================================================
#.       用户可配置的参数
#==CONFIG=======================================================================
MY_TIMEOUT = 30       # 超时秒数
MY_API_URL = "http://localhost:8080"  # API地址
#==END CONFIG===================================================================

def my_func():
    """工具函数 — 会自动注册到 Gemini"""
    pass

def my_other():
    """工具函数 — 会自动注册到 Gemini"""
    pass
```

## TOOL 头部字段

| 字段 | 必填 | 说明 |
|------|:--:|------|
| `name` | ✓ | 模块标识，全局唯一，如 `my_tool` |
| `access` | ✓ | `pr` = 仅 premium 可用，`pb` = premium + normal 均可用 |
| `title` | | TUI 展示名称，如 `我的工具` |
| `description` | | 功能描述，显示在 TUI 设置界面头部 |
| `version` | | 版本号，如 `1.0` |
| `sidebar` | | 侧边栏开关，格式 `key=标签, key=标签`。每项自动生成独立开关 |

### access 说明

- `pr` (private)：工具仅注册到 premium 模式的 tools_list，私聊可用
- `pb` (public)：工具同时注册到 tools_list 和 toolsp_list，群聊也可用

### sidebar 格式

```
sidebar: func_name=中文标签, another_func=另一个标签
```

每个 function 对应侧边栏一个独立开关。不填 sidebar 则不注册开关（工具始终可用）。

## CONFIG 段

`#==CONFIG==` / `#==END CONFIG==` 之间的变量会被 TUI Tools 菜单识别为可编辑参数。

### 格式

```python
#==CONFIG=======================================================================
SETTING_NAME = default_value  # 中文标签
#==END CONFIG===================================================================
```

- 变量名大写，值可以是字符串、数字、布尔值
- 行尾 `#` 后的注释作为 TUI 中的中文显示标签
- 不能包含表达式（如 `os.path.join(...)`）或多行字符串

### 示例

```python
#==CONFIG=======================================================================
QB_HOST = "127.0.0.1"   # qbittorrent地址
QB_PORT = "8080"        # qbittorrent端口
RETRY_COUNT = 3         # 重试次数
ENABLE_LOG = True       # 启用日志
#==END CONFIG===================================================================
```

无 CONFIG 段的工具需添加空标记以避免误解析：

```python
#==CONFIG=======================================================================
#.       (此工具无可配置参数)
#==CONFIG=======================================================================
#==END CONFIG===================================================================
```

## Gemini 工具函数

TOOL 头部的 `access` 决定了函数的注册范围。所有顶层非下划线函数（不以 `_` 开头）自动被发现和注册。

### 函数要求

1. **必须有 docstring**：Gemini 根据 `__doc__` 决定何时调用。格式：

```python
def my_func(param: str):
    """一句话描述用途。

    当用户说"xxx"时调用。

    Args:
        param: 参数说明。
    """
```

2. **类型注解**：参数应该有类型注解，帮助 Gemini 传参。

3. **返回值**：字符串，由 Gemini 组织语言告知用户。

## 可用 API

### 定时任务注册

```python
from utils.scheduler import register_schedule

# 每天 05:00 执行
register_schedule(hour=5, minute=0, callback=my_daily_task)

# 每天 08:30 执行
register_schedule(hour=8, minute=30, callback=my_morning_job)
```

- 精度 10 秒（每整 10 秒检查一次）
- 回调签名：`async def callback(context=None)`

### 功能开关检查

```python
from tui.feature_flags import flag

if flag("my_func"):
    # 用户已开启此功能
    pass
```

### 日志

```python
import logging
logger = logging.getLogger(__name__)
logger.info("message")
```

## 当前已注册工具

| 工具 | access | 功能 |
|------|:---:|------|
| reminder | pr | macOS 提醒事项（增删改查 + 优先级） |
| schooldays | pb | 课表查询 + 每日推送 |
| search | pb | DuckDuckGo 网页搜索 |
| notice | pb | 群组备忘录 |
| doc_converter | pb | Office 文档 → PDF 转换 + 文件附件支持 |
| qbittorrent | pr | BT 下载集成（磁力/种子 → 自动打包上传） |

