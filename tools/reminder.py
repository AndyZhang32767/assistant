#==TOOL=======================================================================
#.       name: reminder
#.       access: pr
#.       title: 系统提醒
#.       description: 通过 AppleScript 与 macOS 提醒事项交互，支持增删改查和优先级管理
#.       version: 5.1
#.       sidebar: add_local_reminder=添加提醒, remove_local_reminder=删除提醒, update_reminder_priority=提醒优先级, fetch_local_reminders=查询提醒
#==END TOOL===================================================================

#==CONFIG=======================================================================
#.       (此工具无可配置参数)
#==END CONFIG===================================================================

#=======================================================================================
#.       tools/reminder.py — macOS 提醒事项集成
#.       通过 AppleScript 与 macOS Reminders.app 交互，实现：
#.         - 增/删/改提醒事项
#.         - 调整优先级、提前提醒时间
#.         - 列出所有提醒
#.
#.       所有 AppleScript 调用通过 subprocess 执行 osascript 命令。
#.       仅支持 macOS 平台。
#.
#.       暴露给 Gemini 的函数（注册在 core/gemini_setup.py 的 tools_list 中）：
#.         add_local_reminder         — 添加提醒（含提前提醒）
#.         remove_local_reminder      — 删除提醒
#.         update_reminder_priority   — 调整优先级
#.         update_reminder_settings   — 综合更新（优先级/提前提醒）
#.         fetch_local_reminders      — 列出所有提醒
#=======================================================================================

import re
import subprocess
import datetime


#=======================================================================================
#.       供 Gemini Function Calling 使用的工具函数
#.       这些函数被 core/gemini_setup.py 注册到 tools_list 中。
#.       每个函数都有 docstring 描述用途和参数，Gemini 会据此自主决定何时调用。
#=======================================================================================

#=============================================================
#.       添加本地提醒事项
#.       当用户要求"记住某事"、"设置提醒"、"记录待办"时由 Gemini 调用。
#.       参数：
#.         name                   — 提醒标题
#.         due_date_str           — 提醒时间，格式 'YYYY-MM-DD HH:MM:SS'（支持 'T' 分隔符）
#.         body                   — 备注内容（可选）
#.         early_reminder_minutes — 提前提醒分钟数（可选，如 15 表示提前 15 分钟弹通知）
#.       最终通过 AppleScript 写入 macOS Reminders.app
#=============================================================
def add_local_reminder(name: str, due_date_str: str, body: str = "", early_reminder_minutes: int = 0):
    """向 macOS Reminders.app 添加提醒事项。

    当用户说"帮我记一下"、"设个提醒"、"XX 时间提醒我"时调用。

    Args:
        name: 提醒标题（必填）。
        due_date_str: 提醒时间，格式 'YYYY-MM-DD HH:MM:SS'（支持 'T' 分隔符）。
        body: 备注内容（可选）。
        early_reminder_minutes: 提前提醒分钟数（可选，如 15 表示提前 15 分钟弹通知）。

    Returns:
        操作结果描述字符串。
    """
    print(f"\n[Reminder 收到指令: {name} | 时间: {due_date_str}]")
    try:
        # Gemini 有时传 '2026-03-21T10:00:00'，统一转为空格分隔
        clean_date_str = due_date_str.replace('T', ' ')
        due_date_obj = datetime.datetime.strptime(clean_date_str, '%Y-%m-%d %H:%M:%S')

        result = add_reminder(name, body=body, due_date=due_date_obj,
                              early_reminder_minutes=early_reminder_minutes)
        if result:
            extra = f"，提前 {early_reminder_minutes} 分钟提醒" if early_reminder_minutes > 0 else ""
            return f"已经记录：'{name}'，设定在 {clean_date_str}{extra}。"
        else:
            return "系统未能创建提醒，请检查 macOS 权限设置。"

    except Exception as e:
        return f"设置提醒时发生错误: {str(e)}"


#=============================================================
#.       删除本地提醒事项
#.       当用户要求"删除/取消/移除某个提醒"时由 Gemini 调用。
#.       参数 name 为提醒的准确标题（需与创建时一致）。
#=============================================================
def remove_local_reminder(name: str):
    """删除指定标题的提醒事项。

    当用户说"删掉 XX 提醒"、"取消 XX"时调用。

    Args:
        name: 提醒的准确标题（需与创建时一致）。

    Returns:
        操作结果描述字符串。
    """
    print(f"\n[Reminder] 正在尝试删除任务: {name}")
    try:
        delete_reminder(name)
        return f"已经把 '{name}' 从提醒事项里删掉啦。"
    except Exception as e:
        return f"删除失败了呢：{str(e)}"


#=============================================================
#.       更新提醒事项优先级
#.       当用户要求"调整任务优先级/重要程度"时由 Gemini 调用。
#.       参数：
#.         name  — 提醒的标题
#.         level — 优先级：0=无, 1=低, 2=中, 3=高
#=============================================================
def update_reminder_priority(name: str, level: int):
    """调整提醒事项的优先级。

    当用户说"把 XX 提醒设成高优先级"时调用。

    Args:
        name: 提醒的准确标题。
        level: 优先级（0=无, 1=低, 2=中, 3=高）。

    Returns:
        操作结果描述字符串。
    """
    print(f"\n[Reminder] 正在调整任务优先级: {name} -> 级别 {level}")
    try:
        set_priority(name, level)
        mapping = {0: "无", 1: "低", 2: "中", 3: "高"}
        return f"已经把 '{name}' 的优先级调成 '{mapping.get(level, level)}' 啦。"
    except Exception as e:
        return f"调整优先级失败了：{str(e)}"


#=============================================================
#.       综合更新提醒事项设置
#.       当用户要求修改提醒的优先级或提前提醒时间时调用。
#.       参数：
#.         name                   — 提醒的准确标题（必填）
#.         priority               — 新优先级（可选）：0=无, 1=低, 2=中, 3=高
#.         early_reminder_minutes — 提前多少分钟弹通知（可选）
#.       各参数独立更新，传 None 表示不修改该项。
#=============================================================
def update_reminder_settings(name: str, priority: int = None, early_reminder_minutes: int = None):
    """综合更新提醒事项的优先级和提前提醒时间。

    当用户说"修改 XX 提醒的优先级/提前提醒"时调用。各参数独立更新，传 None 表示不修改。

    Args:
        name: 提醒的准确标题（必填）。
        priority: 新优先级（可选，None 表示不修改）：0=无, 1=低, 2=中, 3=高。
        early_reminder_minutes: 提前多少分钟弹通知（可选，None 表示不修改）。

    Returns:
        操作结果描述字符串。
    """
    print(f"\n[Reminder] 正在更新任务设置: {name}")
    results = []
    try:
        if priority is not None:
            r = set_priority(name, priority)
            mapping = {0: "无", 1: "低", 2: "中", 3: "高"}
            results.append(f"优先级 → {mapping.get(priority, priority)}" if r else "优先级更新失败")

        if early_reminder_minutes is not None:
            due = get_reminder_due_date(name)
            if due:
                r = set_remind_me_date_from_offset(name, due, early_reminder_minutes)
                if r:
                    remind_time = due - datetime.timedelta(minutes=early_reminder_minutes)
                    results.append(f"提前提醒 → {remind_time.strftime('%Y-%m-%d %H:%M')}（提前 {early_reminder_minutes} 分钟）")
                else:
                    results.append("提前提醒设置失败")
            else:
                results.append("无法获取提醒的截止时间，请确保该提醒已设定截止日期")

        if results:
            return f"已更新 '{name}'：{'；'.join(results)}。"
        else:
            return f"未对 '{name}' 做任何修改（所有参数均为空）。"

    except Exception as e:
        return f"更新设置时出错：{str(e)}"


#=============================================================
#.       列出所有提醒事项（从新到旧，含完成状态过滤）
#.       当用户询问"今天有什么安排"、"查看提醒清单"时由 Gemini 调用。
#.       返回规则：
#.         - 所有未完成的提醒 → 全部返回（从新到旧）
#.         - 已完成的提醒     → 最多返回最近 4 条
#.         - 总数不超过 30 条（避免上下文过长）
#=============================================================
def fetch_local_reminders() -> str:
    """列出所有提醒事项，含完成状态过滤。

    当用户说"查看提醒"、"今天有什么安排"时调用。
    未完成提醒全部返回，已完成最多返回最近 4 条，总上限 30 条。

    Returns:
        格式化后的提醒清单文本。
    """
    print(f"\n[Reminder] 正在读取提醒清单...")
    try:
        reminders = list_reminders_detailed()
        if not reminders:
            return "目前提醒事项里空空的哦，还没有布置任务呢。"

        undone = [r for r in reminders if not r["completed"]]
        done   = [r for r in reminders if r["completed"]]
        recent_done = done[:4]

        max_undone = 30 - len(recent_done)
        if max_undone <= 0:
            undone = []
        elif len(undone) > max_undone:
            undone = undone[:max_undone]

        lines = []
        if undone:
            lines.append(f"📋 未完成 ({len(undone)} 条)：")
            for i, r in enumerate(undone, 1):
                lines.append(f"  {i}. {r['name']}")
        if recent_done:
            lines.append(f"✅ 最近完成 ({len(recent_done)} 条)：")
            for i, r in enumerate(recent_done, 1):
                lines.append(f"  {i}. {r['name']}")
            if len(done) > 4:
                lines.append(f"  （还有 {len(done) - 4} 条更早的已完成提醒未显示）")

        return "\n".join(lines)
    except Exception as e:
        return f"读取清单出错：{str(e)}"


#=======================================================================================
#.       AppleScript 底层执行函数 & CRUD 操作
#.       通过 subprocess 调用 osascript，与 macOS Reminders.app 交互。
#.       以下函数均以 _ 开头（内部函数）或无下划线（CRUD），不注册给 Gemini。
#=======================================================================================

#=============================================================
#.       _format_date_for_applescript() — 将 datetime 转为 AppleScript 兼容日期字符串
#.       AppleScript 的 date 关键字是 locale 敏感的，ISO 格式在中文系统下不可靠。
#.       使用 M/D/YYYY HH:MM:SS 格式，在所有 macOS 语言设置下均可正确解析。
#=============================================================
def _format_date_for_applescript(dt: datetime.datetime) -> str:
    """将 datetime 转为 AppleScript 可靠识别的日期字符串。

    实测结果（中文 macOS 15）：
      - ISO 格式 YYYY-MM-DD HH:MM:SS → ✅ 正常
      - M/D/YYYY 格式               → ❌ 报错
    因此直接用 ISO 格式，在所有测试系统上均可用。

    Args:
        dt: datetime 对象。

    Returns:
        格式化后的日期字符串，如 "2026-06-22 15:00:00"。
    """
    return dt.strftime('%Y-%m-%d %H:%M:%S')


#=============================================================
#.       _run_applescript() — 执行 AppleScript 并返回结果
#.       参数：script — 完整的 AppleScript 字符串
#.       返回：stdout 内容（已 strip），失败返回 None
#=============================================================
def _run_applescript(script: str) -> str | None:
    try:
        print(f"[AppleScript CMD] {script}")
        result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
        print(f"[AppleScript OUT] rc={result.returncode} stdout={result.stdout.strip()!r} stderr={result.stderr.strip()!r}")
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return None
    except Exception as e:
        print(f"[AppleScript EXCEPTION] {e}")
        return None


#=============================================================
#.       add_reminder() — 向 Reminders.app 添加提醒事项
#.       参数：
#.         name                   — 标题（必填）
#.         body                   — 备注内容（可选）
#.         due_date               — datetime 对象或 'YYYY-MM-DD HH:MM:SS' 字符串（可选）
#.         priority               — 优先级 0-3（可选，0 为无优先级）
#.         early_reminder_minutes — 提前提醒分钟数（可选，需配合 due_date 使用）
#.
#.       提前提醒原理：remind me date = due_date - early_reminder_minutes，
#.       系统会在 remind me date 时刻弹出通知，而非等到 due_date。
#=============================================================
def add_reminder(name: str, body: str | None = None, due_date: datetime.datetime | str | None = None,
                 priority: int = 0, early_reminder_minutes: int = 0) -> str | None:
    script = f'tell application "Reminders" to make new reminder with properties {{name:"{name}"'
    if body:
        script += f', body:"{body}"'
    if due_date:
        if isinstance(due_date, datetime.datetime):
            due_dt = due_date
        else:
            due_dt = datetime.datetime.strptime(due_date, '%Y-%m-%d %H:%M:%S')
        script += f', due date:date "{_format_date_for_applescript(due_dt)}"'

        if early_reminder_minutes > 0:
            remind_dt = due_dt - datetime.timedelta(minutes=early_reminder_minutes)
            script += f', remind me date:date "{_format_date_for_applescript(remind_dt)}"'
    if priority:
        script += f', priority:{priority}'
    script += '}'
    return _run_applescript(script)


#=============================================================
#.       delete_reminder() — 按标题删除提醒事项
#.       注意：会删除所有同名提醒（AppleScript whose 匹配）
#=============================================================
def delete_reminder(name: str) -> str | None:
    script = f'tell application "Reminders" to delete (reminders whose name is "{name}")'
    return _run_applescript(script)


#=============================================================
#.       set_priority() — 设置提醒事项优先级
#.       参数：name — 标题, priority — 新优先级 (0-3)
#=============================================================
def set_priority(name: str, priority: int) -> str | None:
    script = f'tell application "Reminders" to set priority of (reminders whose name is "{name}") to {priority}'
    return _run_applescript(script)


#=============================================================
#.       get_reminder_due_date() — 获取提醒事项的截止日期
#.       返回：datetime 对象 或 None（无截止日期/未找到）
#.       用于计算提前提醒时间（remind me date = due_date - offset）
#=============================================================
def get_reminder_due_date(name: str) -> datetime.datetime | None:
    script = f'tell application "Reminders" to get due date of (first reminder whose name is "{name}")'
    result = _run_applescript(script)
    if not result or result == "missing value":
        return None
    try:
        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y年%m月%d日 %A %H:%M:%S']:
            try:
                cleaned = re.sub(r' [一-鿿]+ ', ' ', result)
                return datetime.datetime.strptime(cleaned, fmt)
            except ValueError:
                continue
        print(f"无法解析 AppleScript 日期格式: {result}")
    except Exception as e:
        print(f"解析日期出错: {e}")
    return None


#=============================================================
#.       set_remind_me_date_from_offset() — 根据截止时间和提前分钟数设置提醒时间
#.       计算 remind me date = due_date - offset，然后写入 AppleScript。
#=============================================================
def set_remind_me_date_from_offset(name: str, due_date: datetime.datetime,
                                   early_reminder_minutes: int) -> str | None:
    remind_dt = due_date - datetime.timedelta(minutes=early_reminder_minutes)
    script = (f'tell application "Reminders" to set remind me date of '
              f'(reminders whose name is "{name}") to date "{_format_date_for_applescript(remind_dt)}"')
    return _run_applescript(script)


#=============================================================
#.       list_reminders() — 列出所有提醒事项的标题（简单版）
#=============================================================
def list_reminders() -> list[str]:
    script = 'tell application "Reminders" to get name of reminders'
    result = _run_applescript(script)
    return result.split(', ') if result else []


#=============================================================
#.       list_reminders_detailed() — 获取所有提醒的详细信息
#.       通过 AppleScript 遍历 reminders，获取每条的名称 + 完成状态。
#.       AppleScript 默认按创建时间从新到旧返回，符合"最新在前"的需求。
#.       返回：list[dict]，每项为 {"name": str, "completed": bool}
#=============================================================
def list_reminders_detailed() -> list[dict]:
    script = '''
    tell application "Reminders"
        set output to ""
        repeat with r in reminders
            set output to output & (name of r) & "|||" & (completed of r as text) & "---"
        end repeat
        return output
    end tell
    '''
    result = _run_applescript(script)
    reminders = []
    if result:
        for item in result.split("---"):
            item = item.strip()
            if not item:
                continue
            parts = item.split("|||", 1)
            if len(parts) >= 2:
                name = parts[0].strip()
                completed = parts[1].strip().lower() == "true"
                reminders.append({"name": name, "completed": completed})
    return reminders


#=============================================================
#.       本地测试入口（直接运行本文件时执行）
#=============================================================
if __name__ == "__main__":
    # 添加提醒（含提前提醒）
    add_reminder("测试提醒", "这是一个测试",
                 datetime.datetime.now() + datetime.timedelta(hours=1),
                 priority=1, early_reminder_minutes=15)
    # 列出提醒
    print(list_reminders())
    # 设置优先级
    set_priority("测试提醒", 2)
    # 综合更新
    print(update_reminder_settings("测试提醒", priority=3, early_reminder_minutes=30))
    # 删除提醒（取消注释以执行）
    # delete_reminder("测试提醒")
