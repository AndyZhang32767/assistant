#=======================================================================================
#.       utils/scheduler.py — Tools 定时任务注册 API
#.       提供 register_schedule() 供任何 tool 注册"在 H:M 时刻执行回调"。
#.       主轮询 check_schedules() 每 10s 触发一次，由 bot/main.py 注册。
#.       时间精度 10 秒，12:34:33 向下取整为 12:34:30。
#=======================================================================================

import logging
from collections import defaultdict
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

# {(hour, minute, sec10): [async_callback, ...]}
# sec10 = (second // 10) * 10，取值 0, 10, 20, 30, 40, 50
_schedules: dict[tuple[int, int, int], list[Callable[[], Awaitable[None]]]] = defaultdict(list)


def register_schedule(hour: int, minute: int, callback: Callable[[], Awaitable[None]], second: int = 0):
    """注册一个定时任务。hour=5, minute=0 → 每天 05:00:00 触发。
    幂等：同一个回调不会被重复注册。

    Args:
        hour: 小时 (0-23)
        minute: 分钟 (0-59)
        callback: async 回调函数
        second: 秒 (0-59)，精度 10s，如 5 → floor 为 0, 15 → floor 为 10
    """
    sec10 = (second // 10) * 10
    key = (hour, minute, sec10)
    if callback not in _schedules[key]:  # 防止重复注册
        _schedules[key].append(callback)
        logger.info(f"[scheduler] 注册: {hour:02d}:{minute:02d}:{sec10:02d} → {callback.__name__}")


_timezone = None  # 可选时区字符串，如 "Asia/Shanghai"


def set_timezone(tz_name: str | None) -> None:
    """设置调度器时区。设置后 check_schedules 使用该时区判断当前时间。"""
    global _timezone
    _timezone = tz_name


async def check_schedules(context=None):
    """每 10s 由 job_queue 触发，检查并执行匹配当前时间的回调。"""
    import datetime
    import pytz
    if _timezone:
        now = datetime.datetime.now(pytz.timezone(_timezone))
    else:
        now = datetime.datetime.now()
    sec10 = (now.second // 10) * 10
    key = (now.hour, now.minute, sec10)
    callbacks = _schedules.get(key, [])

    for cb in callbacks:
        try:
            if context is not None:
                await cb(context)
            else:
                await cb()
        except Exception as e:
            logger.error(f"[scheduler] 回调执行失败 {cb.__name__}: {e}")


def get_schedules() -> list[dict]:
    """返回已注册的定时任务列表，供 TUI 显示。"""
    result = []
    for (h, m, s), cbs in sorted(_schedules.items()):
        for cb in cbs:
            result.append({"time": f"{h:02d}:{m:02d}:{s:02d}", "callback": cb.__name__})
    return result
