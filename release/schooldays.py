import csv
import os
import datetime

# 节次到时间的映射
time_map = {
    '01': ('8:30', '9:15'),
    '02': ('9:20', '10:05'),
    '03': ('10:25', '11:10'),
    '04': ('11:15', '12:00'),
    '05': ('13:50', '14:35'),
    '06': ('14:40', '15:25'),
    '07': ('15:30', '16:15'),
    '08': ('16:30', '17:15'),
    '09': ('17:20', '18:05'),
    '10': ('18:30', '19:15'),
    '11': ('19:20', '20:05'),
    '12': ('20:10', '20:55'),
}

def get_time_for_section(section_str):
    """
    根据节次字符串返回时间范围
    :param section_str: 如 '0102' 或 '101112'
    :return: 时间字符串，如 '8:30-10:05'
    """
    if len(section_str) % 2 != 0:
        return section_str  # 如果不是偶数长度，返回原字符串
    
    # 提取节次，每两位一个
    sections = [section_str[i:i+2] for i in range(0, len(section_str), 2)]
    
    if len(sections) == 1:
        # 单节
        if sections[0] in time_map:
            start, end = time_map[sections[0]]
            return f"{start}-{end}"
        else:
            return section_str
    else:
        # 多节，连续
        start_section = sections[0]
        end_section = sections[-1]
        if start_section in time_map and end_section in time_map:
            start_time = time_map[start_section][0]
            end_time = time_map[end_section][1]
            return f"{start_time}-{end_time}"
        else:
            return section_str

# 读取schedule文件
schedule_file = '/Users/andyzhang123/Documents/work/assistant/schedule'
courses = []

def fetch_school_schedule(target_date: str = None):
    """
    当用户询问课程表、课表、今天上什么课或 /class 命令时调用。
    参数:
        target_date: 查询日期，格式为 'YYYY-MM-DD'。如果为空则默认为当天。
    """
    if not target_date:
        target_date = datetime.datetime.now().strftime('%Y-%m-%d')
    
    # 确保格式兼容（处理 YYYY/MM/DD）
    search_date = target_date.replace('/', '-')
    
    courses = []
    if os.path.exists(schedule_file):
        with open(schedule_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['排课日期'] == search_date:
                    courses.append(row)
    
    if not courses:
        return f"{search_date}好像没有安排课程呢，休息一下吧"

    # 格式化输出
    res = f"📅 {search_date} 的课程安排如下：\n"
    for c in courses:
        time_str = get_time_for_section(c['节次'])
        res += f"🔹 {time_str} | {c['课程名称']}\n   📍 地点：{c['上课地点']}\n   👨‍🏫 教师：{c['教师']}\n"
    return res

if os.path.exists(schedule_file):
    with open(schedule_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            courses.append(row)

def parse_date(date_str):
    """将 yyyy/mm/dd 转换为 yyyy-mm-dd"""
    return date_str.replace('/', '-')

def get_courses_on_day(day):
    """
    查询某一天（yyyy/mm/dd）的课程
    :param day: 日期，格式 yyyy/mm/dd
    :return: 课程列表
    """
    target_date = parse_date(day)
    day_courses = [course for course in courses if course['排课日期'] == target_date]
    return day_courses

def get_classroom_for_course(course_name):
    """
    查询某一节课程（yyyy/mm/dd/<n>）的上课地点
    :param course_name: 格式 yyyy/mm/dd/<n>，<n>为二位数字节次
    :return: 上课地点
    """
    parts = course_name.split('/')
    if len(parts) != 4:
        return "格式错误"
    date_str = '/'.join(parts[:3])
    n = parts[3]
    if len(n) != 2:
        return "节次格式错误"
    target_date = parse_date(date_str)
    for course in courses:
        if course['排课日期'] == target_date and course['节次'].startswith(n):
            return course['上课地点']
    return "未找到课程"

# 查询第几节（某一课程的节次） - 可能不再需要，因为course_name包含节次

# 主程序：示例
if __name__ == "__main__":
    # 示例：查询2026/03/10的课程
    day = "2026/03/10"
    day_courses = get_courses_on_day(day)
    print(f"{day} 的课程：")
    for course in day_courses:
        print(f"课程：{course['课程名称']}, 教师：{course['教师']}, 地点：{course['上课地点']}, 节次：{course['节次']}")

    # 示例：查询2026/03/10/06的教室
    course_name = "2026/03/10/06"
    classroom = get_classroom_for_course(course_name)
    print(f"\n{course_name} 的教室：{classroom}")

    # 示例：查询2026/03/10/10的教室
    course_name2 = "2026/03/10/10"
    classroom2 = get_classroom_for_course(course_name2)
    print(f"{course_name2} 的教室：{classroom2}")

    # 测试 fetch_school_schedule
    print("\n测试 fetch_school_schedule:")
    result = fetch_school_schedule("2026-03-10")
    print(result)