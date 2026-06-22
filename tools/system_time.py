#==TOOL=======================================================================
#.       name: system_time
#.       access: pb
#.       title: 系统时间
#.       description: 获取 macOS 系统当前时间，供 Gemini 回答时间相关问题
#.       version: 2.0
#.       sidebar: get_current_system_time=当前时间
#==END TOOL===================================================================

#=======================================================================================
#.       tools/system_time.py — 系统时间工具
#.       提供 get_current_system_time() 函数，返回当前日期时间和星期几。
#.       供 Gemini 在回答"现在几点"、"今天几号"等问题时获取准确时间。
#.
#.       access=pb 确保 Premium 和 Normal 模式均可使用。
#=======================================================================================

import datetime

#==CONFIG=======================================================================
#.       (此工具无可配置参数)
#==END CONFIG===================================================================


#=============================================================
#.       get_current_system_time() — 获取系统当前时间
#.       当用户询问"现在几点"、"今天是几号"时由 Gemini 调用。
#.       返回包含当前时间和星期几的格式化字符串。
#=============================================================
def get_current_system_time() -> str:
    now = datetime.datetime.now()
    current_time = now.strftime('%Y-%m-%d %H:%M:%S')
    weekday_str = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]

    print(f"\n[SystemTime] 正在告知当前时间: {current_time}")

    return (
        f"datetime = {current_time}\n"
        f"date = {now.strftime('%Y-%m-%d')}\n"
        f"time = {now.strftime('%H:%M:%S')}\n"
        f"weekday = {weekday_str}\n"
        f"调用 add_local_reminder 时，due_date_str 参数请使用格式 'YYYY-MM-DD HH:MM:SS'"
    )

