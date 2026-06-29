#=======================================================================================
#.       utils/power_monitor.py — 后台 powermetrics 功耗监控
#.
#.       通过 osascript + administrator privileges 启动后台 powermetrics 进程，
#.       实时解析 CPU/GPU/ANE 功耗（毫瓦 → 瓦特）。
#.
#.       首次启动会弹出 macOS 原生管理员密码对话框。
#.       回退方案：读取 ioreg AppleSmartBattery 的 SystemPowerIn。
#=======================================================================================

import logging
import os
import re
import subprocess
import threading
import time

logger = logging.getLogger(__name__)

_PM_OUTPUT = "/tmp/bot_pm_live.out"


class PowerMonitor:
    #.       单例：管理后台 powermetrics 进程，实时解析各组件功耗。

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cpu_w = 0.0
            cls._instance._gpu_w = 0.0
            cls._instance._ane_w = 0.0
            cls._instance._package_w = 0.0
            cls._instance._running = False
            cls._instance._lock = threading.Lock()
            cls._instance._file_pos = 0
        return cls._instance

    #=============================================================
    #.       启动后台 powermetrics
    #=============================================================
    def start(self) -> bool:
        if self._running:
            return True

        # 清理旧输出文件
        try:
            os.remove(_PM_OUTPUT)
        except (FileNotFoundError, PermissionError):
            pass

        # 通过 osascript 获取管理员权限启动 powermetrics
        # 子 shell 后台运行，osascript 立即返回
        script = (
            f'do shell script "(powermetrics'
            f' --samplers cpu_power,gpu_power,ane_power'
            f' -i 1000'
            f' > {_PM_OUTPUT} 2>&1 &) ; echo ok"'
            f' with administrator privileges'
        )

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=30,
            )
            if "ok" not in result.stdout:
                logger.error(f"powermetrics 启动失败: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            logger.error("osascript 超时（用户取消了密码对话框？）")
            return False
        except FileNotFoundError:
            logger.error("osascript 不可用")
            return False

        # 等待输出文件出现第一份采样
        for _ in range(50):  # 最多等 5 秒
            if os.path.exists(_PM_OUTPUT) and os.path.getsize(_PM_OUTPUT) > 100:
                break
            time.sleep(0.1)

        if not os.path.exists(_PM_OUTPUT):
            logger.error("powermetrics 输出文件未创建")
            return False

        self._running = True
        self._file_pos = 0
        logger.info("powermetrics 后台监控已启动")
        return True

    #=============================================================
    #.       停止后台 powermetrics
    #=============================================================
    def stop(self) -> None:
        if not self._running:
            return
        try:
            subprocess.run(
                ["sudo", "pkill", "-x", "powermetrics"],
                capture_output=True, timeout=5,
            )
        except Exception:
            pass
        self._running = False
        logger.info("powermetrics 已停止")

    _MAX_FILE_SIZE = 2 * 1024 * 1024  # 超过 2MB 重启 powermetrics 截断文件

    #=============================================================
    #.       读取最新功耗数据
    #=============================================================
    def _read_latest(self) -> None:
        #.       从输出文件读取增量内容，解析最新采样中的功耗值。
        #.       文件超过 _MAX_FILE_SIZE 时自动重启 powermetrics 截断。
        if not self._running:
            return

        try:
            if not os.path.exists(_PM_OUTPUT):
                return

            # 文件过大 → 重启截断
            if os.path.getsize(_PM_OUTPUT) > self._MAX_FILE_SIZE:
                logger.info("powermetrics 输出文件过大，重启截断")
                self.stop()
                time.sleep(0.3)
                self.start()
                return

            with open(_PM_OUTPUT, "r") as f:
                f.seek(self._file_pos)
                new_data = f.read()
                self._file_pos = f.tell()

            if not new_data:
                return

            # 取最后一个完整采样块（以 "*** Sampled" 分隔）
            blocks = re.split(r'\*{3} Sampled system activity', new_data)
            last_block = blocks[-1] if blocks else ""

            # 从最后一块中提取功耗值（单位 mW）
            cpu_match = re.search(r'CPU Power:\s+(\d+)\s*mW', last_block)
            gpu_match = re.search(r'^GPU Power:\s+(\d+)\s*mW', last_block, re.MULTILINE)
            ane_match = re.search(r'ANE Power:\s+(\d+)\s*mW', last_block)
            combined_match = re.search(r'Combined Power.*?:\s+(\d+)\s*mW', last_block)

            with self._lock:
                if cpu_match:
                    self._cpu_w = int(cpu_match.group(1)) / 1000.0
                if gpu_match:
                    self._gpu_w = int(gpu_match.group(1)) / 1000.0
                if ane_match:
                    self._ane_w = int(ane_match.group(1)) / 1000.0
                if combined_match:
                    self._package_w = int(combined_match.group(1)) / 1000.0

        except Exception:
            logger.debug("读取 powermetrics 输出失败", exc_info=True)

    #=============================================================
    #.       公开属性 — 返回瓦特值
    #=============================================================
    @property
    def cpu_w(self) -> float:
        self._read_latest()
        with self._lock:
            return self._cpu_w

    @property
    def gpu_w(self) -> float:
        self._read_latest()
        with self._lock:
            return self._gpu_w

    @property
    def ane_w(self) -> float:
        self._read_latest()
        with self._lock:
            return self._ane_w

    @property
    def package_w(self) -> float:
        self._read_latest()
        with self._lock:
            return self._package_w

    @property
    def is_running(self) -> bool:
        return self._running


#===========================================================================
#.       模块级便捷函数
#===========================================================================

def get_power_monitor() -> PowerMonitor:
    return PowerMonitor()
