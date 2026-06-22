# Assistant Bot

基于 Telegram + Google Gemini 的多功能 AI 助手，支持插件化工具扩展。

## 功能概览

- 私聊 AI 对话（premium 模式，开放全部工具）
- 群聊 @bot 响应（normal 模式，受限工具集）
- macOS 系统提醒事项管理
- 课表查询与每日定时推送
- DuckDuckGo 网页搜索
- 群组备忘录
- BT 下载集成（qBittorrent）
- Office 文档转 PDF（LibreOffice）
- 新用户授权弹窗
- TUI 控制台配置管理
- 插件系统：`tools/` 目录自动发现与注册

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 编辑 core/config.py，填入你的 Telegram Token、Gemini API Key 等配置

# 3. 启动
python3 run.py          # 命令行模式（阻塞 polling）
python3 tui_run.py      # TUI 控制台模式（推荐）
```

## 配置

编辑 [core/config.py](core/config.py) 中的以下变量：

| 变量 | 说明 | 示例 |
|------|------|------|
| `TELEGRAM_TOKEN` | Telegram Bot Token | 从 @BotFather 获取 |
| `GEMINI_API_KEY` | Google Gemini API 密钥 | 从 aistudio.google.com 获取 |
| `MODEL_TYPE` | Gemini 模型 | `gemini-3.1-flash-lite-preview` |
| `ADMIN_ID` | 管理员 Telegram 用户 ID（整数） | `123456789` |
| `PROXY_URL` | HTTP 代理（可选，留空不启用） | `http://127.0.0.1:10808` |
| `BOT_NAME` | 群聊中唤起 Bot 的关键词 | `助手` |
| `PRIVATE_INSTRUCTION` | 私聊 System Prompt | 定义角色和行为 |
| `PUBLIC_INSTRUCTION` | 群聊 System Prompt | 定义群聊角色和行为 |

Tools 参数（如 qBittorrent 连接信息、课表推送时间）编辑对应 `tools/*.py` 中的 `#==CONFIG==` 段，或通过 TUI 的 Tools 菜单编辑。

## 架构

```
assistant/
├── bot/                  # Bot 核心
│   ├── main.py           # 入口、Application 构建、定时任务注册
│   ├── handlers.py       # Telegram 消息/命令处理器
│   └── session.py        # 会话管理、授权、持久化
├── core/                 # 基础设施
│   ├── config.py         # 全局配置（密钥、模型、System Prompt）
│   ├── gemini_setup.py   # Gemini 客户端、工具注册、安全过滤
│   ├── file_support.py   # 文件类型与大小限制
│   └── logging_setup.py  # 日志配置
├── tools/                # 插件模块（自动发现注册）
│   ├── system_time.py    # 系统时间查询
│   ├── reminder.py       # macOS 提醒事项（增删改查）
│   ├── schooldays.py     # 课表查询 + 每日推送
│   ├── search.py         # DuckDuckGo 网页搜索
│   ├── notice.py         # 群组备忘录
│   ├── doc_converter.py  # Office → PDF 转换
│   └── qbittorrent.py    # BT 下载集成
├── tui/                  # Textual 控制台
│   ├── app.py            # TUI 主应用
│   ├── config_parser.py  # config.py 解析与写回
│   ├── feature_flags.py  # 功能开关管理
│   └── widgets/          # UI 组件
│       ├── sidebar.py        # 侧边栏（状态/开关）
│       ├── config_modal.py   # 配置编辑弹窗
│       ├── tools_modal.py    # Tools 参数编辑
│       ├── auth_modal.py     # 新用户授权弹窗
│       ├── history_modal.py  # 对话历史查看
│       ├── schedule_modal.py # 课表查看
│       ├── status_modal.py   # 系统状态
│       └── log_panel.py      # 日志面板
├── utils/                # 工具库
│   ├── tool_scanner.py   # 插件扫描与注册
│   ├── scheduler.py      # 定时任务注册 API
│   ├── helpers.py        # 对话历史裁剪、typing 动画
│   ├── identity.py       # 群聊发言者身份标签
│   ├── system_stats.py   # 系统资源监控
│   └── power_monitor.py  # 电源状态监控
├── data/                 # 运行时数据（会话、历史、开关状态等 JSON）
├── run.py                # 命令行启动入口
└── tui_run.py            # TUI 控制台启动入口
```

## TUI 控制台

TUI 模式基于 [Textual](https://textual.textualize.io/) 框架，提供实时配置管理界面。

### 界面布局

- **左侧边栏**：Bot 运行状态、CPU/内存、各 tool 独立开关
- **右侧主区域**：实时日志流
- **底部栏**：快捷键提示

### 快捷键

| 键 | 功能 |
|---|------|
| `c` | 打开配置编辑（config.py 变量） |
| `t` | 打开 Tools 参数管理 |
| `h` | 查看会话历史 |
| `s` | 保存配置到文件 |
| `r` | 重启 Bot |
| `q` | 退出 |
| `Ctrl+L` | 查看完整日志 |

### 功能开关

侧边栏提供每个 tool 和子功能的独立开关，实时生效无需重启。开关状态持久化到 `data/feature_flags.json`。

支持的功能开关：
- 各 tool 模块整体启用/禁用
- 文件附件支持（`file_attachment`）
- Office 转 PDF（`office_to_pdf`）
- 早间课表推送（`morning_push`）
- 更多…

## 命令

Bot 在 Telegram 中支持以下命令：

| 命令 | 说明 | 权限 |
|------|------|:--:|
| `/start` | 发送欢迎语 | 所有用户 |
| `/class` | 查询当日课表 | premium 用户 |
| `/clear` | 清除当前会话历史 | 已授权用户 |

## 用户授权

新用户首次发消息时，会在 TUI 控制台弹出授权窗口。管理员可选择：
- **Premium（私聊模式）**：开放全部工具，适合私密对话
- **Normal（群聊模式）**：受限工具集，适合群组场景
- **拒绝**：加入黑名单，Bot 不再响应

授权信息持久化到 `data/sessions_data.json`，黑名单单独存储。

## 插件系统

`tools/` 目录下的 `.py` 文件会被自动发现和注册，无需修改核心代码。

每个 tool 文件通过 `#==TOOL==` 头部声明元信息，可选 `#==CONFIG==` 段声明用户可配置参数。详见 [tools.md](tools.md)。

## 定时任务

通过 `utils/scheduler.py` 注册定时任务，精度 10 秒。当前内置任务：

- **课表推送**：每日指定时间向 premium 用户推送当日课表
- **qBittorrent 轮询**：定时检查 BT 下载状态，完成后自动打包通知
- **主调度器**：每 10 秒检查一次待执行任务队列

## 系统依赖（可选）

| 依赖 | 用途 | 安装 |
|------|------|------|
| LibreOffice | Office 文档 → PDF 转换 | `brew install libreoffice` |
| qBittorrent | BT 下载 | 需开启 Web UI（设置 → Web UI） |

不支持的操作系统特性：
- `tools/reminder.py` — 仅支持 macOS（依赖 AppleScript）
- `utils/power_monitor.py` — 仅支持 macOS（依赖 pmset）
