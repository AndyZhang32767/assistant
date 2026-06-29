#=======================================================================================
#.       utils/tool_scanner.py — Tools 插件扫描器
#.       扫描 tools/ 目录下所有 .py 文件，解析 #==TOOL== 头部提取：
#.         - 工具名称、访问级别（pr/pb）、侧边栏标签
#.       解析 #==CONFIG== 段内变量，提取行尾 # 注释作为中文标签。
#.
#.       供 core/gemini_setup.py、tui/widgets/sidebar.py、
#.       tui/widgets/tools_modal.py、tui/feature_flags.py 动态加载。
#=======================================================================================

import os
import re
import importlib


#=============================================================
#.       数据结构
#=============================================================
class ToolInfo:
    """一个 tool 插件的元信息。"""
    def __init__(self):
        self.name: str = ""           # 模块标识，如 "qbittorrent"
        self.access: str = "pr"       # "pr" = 仅 premium, "pb" = premium + normal
        self.title: str = ""          # 展示名称
        self.description: str = ""    # 功能描述
        self.version: str = ""        # 版本号
        self.switches: list[tuple[str, str]] = []  # [(key, label), ...]  多个侧边栏开关
        self.configs: dict[str, dict] = {}  # {VAR_NAME: {"value": "...", "label": "中文标签"}}
        self.functions: dict[str, object] = {}  # {func_name: callable}


def _parse_tool_header(filepath: str) -> ToolInfo | None:
    """解析 tool 文件的 #==TOOL== 头部。"""
    if not os.path.exists(filepath):
        return None
    info = ToolInfo()
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    in_header = False
    for line in lines:
        s = line.strip()
        if s.startswith("#==TOOL=="):
            in_header = True
            continue
        if in_header:
            if s.startswith("#==END TOOL=="):
                break
            # 解析 #. key: value 格式
            m = re.match(r'^#\.\s*(\w+)\s*:\s*(.+)$', s)
            if m:
                key = m.group(1).lower()
                val = m.group(2).strip()
                if key == "name":
                    info.name = val
                elif key == "access":
                    info.access = val.strip().lower()
                elif key == "title":
                    info.title = val
                elif key == "description":
                    info.description = val
                elif key == "version":
                    info.version = val
                elif key == "sidebar":
                    # 格式: key=label, key=label, ...
                    for item in val.split(","):
                        item = item.strip()
                        if "=" in item:
                            k, v = item.split("=", 1)
                            info.switches.append((k.strip(), v.strip()))
                        else:
                            info.switches.append((item, item))
                    info.sidebar_label = val

    if not info.name:
        return None
    return info


def _parse_config_with_labels(filepath: str) -> dict[str, dict]:
    """解析 CONFIG 变量。优先查找 #==CONFIG== 段；若无，扫描全文件。"""
    if not os.path.exists(filepath):
        return {}
    configs: dict[str, dict] = {}
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    has_markers = any(l.strip().startswith("#==CONFIG==") for l in lines)
    in_config = not has_markers  # 无标记时扫描全文件
    for line in lines:
        s = line.strip()
        if has_markers:
            if s.startswith("#==CONFIG=="):
                in_config = True
                continue
            if s.startswith("#==END CONFIG=="):
                break
        if in_config:
            m = re.match(r'^(\s*)([A-Za-z_]\w*)\s*=\s*(.+)$', line)
            if m:
                name = m.group(2)
                val_part = m.group(3).strip()
                # 跳过只读、表达式和多行字符串
                if name in ("VERSION",):
                    continue
                if "(" in val_part and ")" in val_part:  # os.path.join(...) 等
                    continue
                if val_part.startswith('"""'):  # 多行字符串
                    continue
                # 提取行尾 # 注释作为中文标签
                label = name
                if "#" in val_part:
                    val, _, comment = val_part.partition("#")
                    val = val.strip()
                    label = comment.strip() or name
                else:
                    val = val_part
                # 去掉引号
                if (val.startswith('"') and val.endswith('"')) or \
                   (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                configs[name] = {"value": val, "label": label}
    return configs


def _load_tool_functions(filepath: str):
    """从 tool 文件导入所有顶层可调用对象。"""
    mod_name = os.path.splitext(os.path.basename(filepath))[0]
    try:
        mod = importlib.import_module(f"tools.{mod_name}")
    except Exception:
        return {}
    return {n: getattr(mod, n) for n in dir(mod)
            if callable(getattr(mod, n)) and not n.startswith("_")}


def scan_tools(tools_dir: str = None) -> list[ToolInfo]:
    """扫描 tools/ 目录，返回所有 tool 的元信息列表。"""
    if tools_dir is None:
        tools_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "tools",
        )

    tools = []
    for filename in sorted(os.listdir(tools_dir)):
        if not filename.endswith(".py") or filename.startswith("__"):
            continue
        filepath = os.path.join(tools_dir, filename)

        info = _parse_tool_header(filepath)
        if info is None:
            continue

        info.configs = _parse_config_with_labels(filepath)
        info.functions = _load_tool_functions(filepath)

        tools.append(info)

    return tools
