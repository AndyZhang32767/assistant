# CLAUDE.md — Assistant Bot 开发指南

## 运行

```bash
python3 tui_run.py    # TUI 控制台模式（主要开发入口）
python3 run.py        # 命令行模式（无界面）
```

## 架构要领

### 权限系统
- **权限跟人**：`sessions` key 是 `sender_id`（用户 ID），不是 `chat_id`（群组 ID）
- **历史跟会话**：`save_history` key 是 `chat_id`，群友共享上下文
- `chk="T"`=Premium, `"F"`=Normal, `"D"`=Banned
- 新用户触发 auth modal（`auth_modal.py`）→ 管理员选 pr/pb/deny
- 私聊 `sender_id == chat_id`

### 消息触发
- 私聊：所有消息自动触发
- 群聊：检测 `@bot_username` mention entity 或 `BOT_NAME in contents`
- 触发逻辑在 `bot/handlers.py` 的 `handle_message` / `handle_reply` / `handle_file`

### TUI 动画模式（壳 + 真身）
所有 modal 使用统一动画：
1. 空壳（border/background，无子控件）`display:none; opacity:0%`
2. `on_mount` → `.-visible` → `0.03s: .-fade-in`（transition 250-300ms）
3. `0.3s` 后 `_swap_to_real`：壳隐藏，真 dialog 显示
4. 真 dialog 不使用 opacity/transition（避免 Textual 渲染 bug 导致文字消失）

### 关键模块
| 模块 | 作用 |
|------|------|
| `core/config.py` | 全局配置（Token、Key、Prompt），TUI 通过 `config_parser.py` 读写 |
| `bot/session.py` | sessions/history 持久化，授权回调，confirm_send |
| `bot/handlers.py` | 6 个 handler（start/class/clear/message/reply/file） |
| `bot/main.py` | Application 构建、Handler 注册、定时任务 |
| `tui/app.py` | BotTUI 主类，compose 布局、动画触发 |
| `tui/widgets/` | 各 modal/screen 组件 |
| `tools/` | 插件模块，自动发现注册（`tool_scanner.py`） |

### 配置解析（config_parser.py）
- `_READONLY_VARS` 集合中的变量在 TUI 只读显示
- `write_config()` 按原格式写回，保留注释和缩进
- 多行字符串支持 3 种格式：A（`"""text` 开头）、A2（`"""` 单独一行）、B（单行闭合）

### 启动流程
```
SETUP=False:
  on_mount → LoadingScreen（约3s）→ header/sidebar/footer 动画 → Bot 启动

SETUP=True:
  on_mount → SetupScreen（7步向导）→ 写 SETUP=False → os.execv 重启 → Loading → 主界面
```

### 发送确认（confirm_send）
- 在 Permission modal 底部 Select 设置（off/public/all）
- `handlers.py` 的 `reply_text` 前调用 `confirm_send(reply, chk, chat_id)`
- 需要确认时弹出 `ConfirmSendModal`（可编辑 TextArea + 取消/发送）

### 日志系统
- `_TUILogHandler` 挂 root logger，转发到 RichLog
- 关键词匹配着色（`_KEYWORD_COLORS`），优先于来源模块色
- `setup_logging()` 幂等，httpx getUpdates 轮询被 `TelegramFilter` 过滤

### 代码风格
- 注释用 `#.` 段落标题，`#==` 分隔线
- 类/方法用 ASCII box 注释块
- 模块用 `#====` 头注释说明用途
- 变量命名：`_private_method`，`ClassName`，`module_name`
