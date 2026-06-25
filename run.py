#=======================================================================================
#.       run.py — TUI 控制台模式入口
#.       启动前检查依赖，缺失则自动安装。
#=======================================================================================

import subprocess
import sys


def _check_requirements():
    """检查 requirements.txt 中的包，缺失则自动安装。"""
    import os
    from importlib.metadata import version, PackageNotFoundError

    req_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
    if not os.path.exists(req_path):
        return

    with open(req_path) as f:
        required = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    missing = []
    for req in required:
        pkg_name = req.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].split("!=")[0].strip()
        try:
            version(pkg_name)
        except PackageNotFoundError:
            missing.append(req)

    if missing:
        print(f"Missing {len(missing)} package(s): {missing}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
        print("Done. Restarting...")
        os.execv(sys.executable, [sys.executable] + sys.argv)


if __name__ == "__main__":
    _check_requirements()
    from tui.app import BotTUI
    app = BotTUI()
    app.run()
