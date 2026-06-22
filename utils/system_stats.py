#=======================================================================================
#.       utils/system_stats.py — 系统资源占用采集
#.
#.       提供 macOS 系统实时状态：
#.         - CPU 占用百分比
#.         - 内存使用量 / 总量 (MB)
#.         - 功耗 (W) — powermetrics（CPU/GPU/ANE 分项）或 ioreg 回退
#=======================================================================================

import subprocess
import re

import psutil


def get_cpu_percent() -> float:
    #.       返回当前 CPU 总占用百分比 (0.0–100.0)。
    #.       首次调用会初始化计数器（返回 0.0），后续调用返回
    #.       自上次调用以来的增量百分比。
    try:
        return round(psutil.cpu_percent(interval=None), 1)
    except Exception:
        return 0.0


def get_memory_mb() -> tuple[float, float]:
    #.       返回 (used_mb, total_mb)。
    try:
        mem = psutil.virtual_memory()
        used_mb = round(mem.used / (1024 * 1024), 0)
        total_mb = round(mem.total / (1024 * 1024), 0)
        return used_mb, total_mb
    except Exception:
        return 0.0, 0.0


#===========================================================================
#.       功耗 — powermetrics 优先（CPU/GPU/ANE 分项），回退 ioreg
#===========================================================================

import threading

_pm_started = False


def _ensure_powermetrics():
    #.       惰性启动 powermetrics 后台监控（首次调用时在后台线程
    #.       弹出 macOS 管理员密码对话框，不阻塞 UI）。
    #.       启动失败则重置标记，下次可重试。
    global _pm_started
    if _pm_started:
        return
    _pm_started = True

    def _do_start():
        from utils.power_monitor import get_power_monitor
        ok = get_power_monitor().start()
        if not ok:
            global _pm_started
            _pm_started = False  # 允许下次重试

    threading.Thread(target=_do_start, daemon=True).start()


def get_power_breakdown() -> dict:
    #.       返回 {'cpu': W, 'gpu': W, 'ane': W, 'package': W}。
    #.       优先从 powermetrics 读取分项功耗；
    #.       如果 powermetrics 不可用，回退到 ioreg SystemPowerIn
    #.       （只有总功耗，各分项为 0）。
    _ensure_powermetrics()
    from utils.power_monitor import get_power_monitor
    pm = get_power_monitor()

    if pm.is_running:
        # powermetrics 数据
        return {
            "cpu": pm.cpu_w,
            "gpu": pm.gpu_w,
            "ane": pm.ane_w,
            "package": pm.package_w,
        }

    # 回退：ioreg SystemPowerIn
    fallback = _ioreg_system_power_w()
    return {
        "cpu": 0.0,
        "gpu": 0.0,
        "ane": 0.0,
        "package": fallback or 0.0,
    }


def get_power_watts() -> float | None:
    #.       返回总 package 功耗 (W)。先尝试 powermetrics，
    #.       不可用时回退到 ioreg SystemPowerIn。
    _ensure_powermetrics()
    from utils.power_monitor import get_power_monitor
    pm = get_power_monitor()

    if pm.is_running:
        pkg = pm.package_w
        if pkg > 0:
            return pkg

    return _ioreg_system_power_w()


def _ioreg_system_power_w() -> float | None:
    #.       从 ioreg AppleSmartBattery 读取 SystemPowerIn (mW)。
    try:
        result = subprocess.run(
            ["ioreg", "-rw0", "-c", "AppleSmartBattery"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode != 0:
            return None

        # SystemPowerIn (mW) — AC/电池均可用 (Apple Silicon)
        match = re.search(r'"SystemPowerIn"\s*=\s*(\d+)', result.stdout)
        if match:
            mw = int(match.group(1))
            if mw > 0:
                return round(mw / 1000.0, 1)

        # 电池放电回退：Voltage(mV) × |InstantAmperage|(mA) / 1e6
        v_match = re.search(r'"Voltage"\s*=\s*(\d+)', result.stdout)
        a_match = re.search(r'"InstantAmperage"\s*=\s*(-?\d+)', result.stdout)
        if v_match and a_match:
            voltage_mv = int(v_match.group(1))
            amperage_ma = int(a_match.group(1))
            if amperage_ma != 0:
                watts = (voltage_mv * abs(amperage_ma)) / 1_000_000.0
                return round(watts, 1)

        return None
    except Exception:
        return None
