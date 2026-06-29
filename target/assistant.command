#!/bin/bash
#=======================================================================================
#.       assistant.command — macOS 启动器
#.       双击或终端执行，自动检查环境并启动 Assistant Bot TUI。
#=======================================================================================

cd "$(dirname "$0")"

# 检查 Python
if ! command -v python3 &>/dev/null; then
    echo "需要 Python 3.10+，请先安装: brew install python@3.13"
    read -p "按回车退出..."
    exit 1
fi

echo "Assistant Bot 启动中..."
python3 run.py

# 如果异常退出，等待用户查看错误
if [ $? -ne 0 ]; then
    echo ""
    read -p "启动失败，按回车退出..."
fi
