import subprocess
import datetime

# 专门提供给 tools_list 的函数
def get_current_system_time():
    """
    当用户询问‘现在几点’、‘今天是几号’或‘当前时间’时，调用此函数。
    """
    now = datetime.datetime.now()
    current_time = now.strftime('%Y-%m-%d %H:%M:%S')
    weekday_str = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]
    
    print(f"\n[Reminder绫波执行中] 正在告知 Andy 当前时间: {current_time}")
    
    # 返回给 Gemini，让她组织语言告诉你
    return f"现在是 {current_time}，正好是{weekday_str}哦。"
def add_local_reminder(name: str, due_date_str: str, body: str = ""):
    """
    当用户要求记住某事、设置提醒、或记录待办任务时，调用此函数。
    参数:
        name: 提醒的简短标题，例如 '去图书馆'。
        due_date_str: 提醒的具体时间，严格格式为 'YYYY-MM-DD HH:MM:SS'。
        body: 提醒的具体备注内容。
    """
    print(f"\n[Reminder绫波执行中] 收到指令: {name} | 时间: {due_date_str}")
    
    try:
        # 1. 这里的格式转换非常重要，Gemini 有时会传 2026-03-21T10:00:00
        clean_date_str = due_date_str.replace('T', ' ')
        
        # 2. 直接调用你最稳的那版 add_reminder
        # 我们把字符串转回 datetime，因为你的 add_reminder 接受 datetime
        due_date_obj = datetime.datetime.strptime(clean_date_str, '%Y-%m-%d %H:%M:%S')
        
        result = add_reminder(name, body=body, due_date=due_date_obj)
        
        if result:
            return f"已经帮 Andy 记好啦：'{name}'，设定在 {clean_date_str}。"
        else:
            return "系统未能创建提醒，请检查 macOS 权限设置。"
            
    except Exception as e:
        print(f"❌ 执行出错: {e}")
        return f"设置提醒时发生错误: {str(e)}"
    
def remove_local_reminder(name: str):
    """
    当用户要求删除、取消或移除某个具体的提醒/任务时，调用此函数。
    参数:
        name: 提醒的准确标题。
    """
    print(f"\n[Reminder绫波执行中] 正在尝试删除任务: {name}")
    try:
        # 调用你已有的 delete_reminder
        result = delete_reminder(name)
        return f"已经按照 Andy 的吩咐，把 '{name}' 从提醒事项里删掉啦。"
    except Exception as e:
        return f"删除失败了呢：{str(e)}"

def update_reminder_priority(name: str, level: int):
    """
    当用户要求调整任务的优先级、重要程度时，调用此函数。
    参数:
        name: 提醒的标题。
        level: 优先级数字。1 代表低(Low)，2 代表中(Medium)，3 代表高(High)，0 代表无优先级。
    """
    print(f"\n[Reminder绫波执行中] 正在调整任务优先级: {name} -> 级别 {level}")
    try:
        # 调用你已有的 set_priority
        result = set_priority(name, level)
        mapping = {0: "无", 1: "低", 2: "中", 3: "高"}
        return f"已经把 '{name}' 的优先级调成 '{mapping.get(level, level)}' 啦。"
    except Exception as e:
        return f"调整优先级失败了：{str(e)}"

def fetch_local_reminders():
    """
    当用户询问‘我今天有什么安排’、‘查看提醒清单’或‘有哪些任务’时，调用此函数列出所有标题。
    """
    print(f"\n[Reminder绫波执行中] 正在读取提醒清单...")
    try:
        reminders = list_reminders()
        if not reminders:
            return "目前提醒事项里空空的哦，Andy 还没布置任务呢。"
        return "当前的提醒事项有：" + "、".join(reminders)
    except Exception as e:
        return f"读取清单出错：{str(e)}"


def run_applescript(script):
    """运行AppleScript命令"""
    try:
        result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            print(f"Error: {result.stderr}")
            return None
    except Exception as e:
        print(f"Exception: {e}")
        return None

def add_reminder(name, body=None, due_date=None, priority=0):
    """添加提醒事项"""
    script = f'tell application "Reminders" to make new reminder with properties {{name:"{name}"'
    if body:
        script += f', body:"{body}"'
    if due_date:
        # due_date 应该是 datetime 对象或字符串
        if isinstance(due_date, datetime.datetime):
            due_str = due_date.strftime('%Y-%m-%d %H:%M:%S')
        else:
            due_str = due_date
        script += f', due date:date "{due_str}"'
    if priority:
        script += f', priority:{priority}'
    script += '}'
    return run_applescript(script)

def delete_reminder(name):
    """删除提醒事项"""
    script = f'tell application "Reminders" to delete (reminders whose name is "{name}")'
    return run_applescript(script)

def set_priority(name, priority):
    """设置提醒优先级"""
    script = f'tell application "Reminders" to set priority of (reminders whose name is "{name}") to {priority}'
    return run_applescript(script)

def list_reminders():
    """列出所有提醒事项"""
    script = 'tell application "Reminders" to get name of reminders'
    result = run_applescript(script)
    if result:
        return result.split(', ')
    return []

# 示例使用
if __name__ == "__main__":
    # 添加提醒
    add_reminder("测试提醒", "这是一个测试", datetime.datetime.now() + datetime.timedelta(hours=1), 1)
    # 列出提醒
    print(list_reminders())
    # 设置优先级
    set_priority("测试提醒", 2)
    # 删除提醒
    # delete_reminder("测试提醒")