#=======================================================================================
#.       tui/widgets/tools_modal.py — Tools 参数管理
#.       ToolsModal (L2)：列出所有 tool 模块
#.       ToolSettingsModal (L3)：编辑单个 tool 的常函数/配置常量
#.       通过 #==CONFIG== / #==END CONFIG== 标记识别可编辑区域。
#=======================================================================================

import os
import re

from textual.app import ComposeResult
from textual.containers import VerticalScroll, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, Input, Button, Label
from utils.tool_scanner import scan_tools, ToolInfo

# -- 从 scanner 获取所有工具信息
_TOOLS = scan_tools()
_TOOL_MAP = {t.name: t for t in _TOOLS}


#=============================================================
#.       _parse_tool_config() — 从 ToolInfo 获取 CONFIG（含标签）
#=============================================================
def _parse_tool_config(module_name: str) -> dict[str, dict]:
    info = _TOOL_MAP.get(module_name)
    return dict(info.configs) if info else {}


#=============================================================
#.       _write_tool_config() — 写回 tool 文件的 CONFIG 段
#=============================================================
def _write_tool_config(filepath: str, updates: dict[str, str]):
    if not os.path.exists(filepath):
        return
    with open(filepath, "r") as f:
        lines = f.readlines()

    in_config = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#==CONFIG=="):
            in_config = True
            new_lines.append(line)
            continue
        if stripped.startswith("#==END CONFIG=="):
            in_config = False
        if in_config:
            m = re.match(r'^(\s*)([A-Za-z_]\w*)(\s*=\s*)(.+)$', line)
            if m:
                indent = m.group(1)
                name = m.group(2)
                eq = m.group(3)
                if name in updates:
                    # 保留原始行尾注释
                    tail = ""
                    raw_val = m.group(4).strip()
                    if "#" in raw_val:
                        val_part, _, comment_part = raw_val.partition("#")
                        tail = f"  #{comment_part}"
                    else:
                        val_part = raw_val
                    # 判断是否需要引号
                    v = updates[name]
                    if v.isdigit() or v in ("True", "False", "None"):
                        quoted = v
                    else:
                        quoted = f'"{v}"'
                    new_lines.append(f"{indent}{name}{eq}{quoted}{tail}\n")
                    del updates[name]
                    continue
        new_lines.append(line)

    with open(filepath, "w") as f:
        f.writelines(new_lines)


#=======================================================================================
#.       ToolSettingsModal (L3) — 单个 tool 的参数编辑
#=======================================================================================

class ToolSettingsModal(ModalScreen):
    CSS = """
    ToolSettingsModal {
        align: center middle;
    }
    #tool-settings-dialog {
        width: 55%;
        height: auto;
        border: thick $warning;
        background: $surface;
        padding: 1 2;
    }
    #tool-settings-title {
        text-align: center;
        padding: 1;
        background: $warning;
        color: $text;
        text-style: bold;
    }
    #tool-settings-body {
        margin: 1 0;
    }
    #tool-settings-buttons {
        dock: bottom;
        height: 3;
        align: right middle;
    }
    .ts-label {
        margin-top: 1;
        text-style: bold;
        color: $secondary;
    }
    .ts-input {
        margin-bottom: 1;
    }
    """

    def __init__(self, module_name: str, filepath: str):
        super().__init__()
        self._module_name = module_name
        self._filepath = filepath
        self._config = _parse_tool_config(module_name)
        self._info = _TOOL_MAP.get(module_name)  # ToolInfo
        self._inputs: dict[str, Input] = {}

    def compose(self) -> ComposeResult:
        if self._info and self._info.title:
            title = self._info.title
        else:
            title = self._module_name
        desc = self._info.description if self._info else ""
        ver = self._info.version if self._info else ""
        header = f"{title}"
        if desc:
            header += f"\n{desc}"
        if ver:
            header += f"  (v{ver})"
        with VerticalScroll(id="tool-settings-dialog"):
            yield Static(header, id="tool-settings-title")
            if not self._config:
                with VerticalScroll(id="tool-settings-body"):
                    yield Static("此模块暂无可配置参数。")
            else:
                with VerticalScroll(id="tool-settings-body"):
                    for name, info in self._config.items():
                        label_text = info.get("label", name)  # 中文标签
                        yield Label(label_text, classes="ts-label")
                        inp = Input(value=info.get("value", ""), id=f"ts-{name}", classes="ts-input")
                        self._inputs[name] = inp
                        yield inp
            with Horizontal(id="tool-settings-buttons"):
                yield Button("Back", id="ts-back")
                if self._config:
                    yield Button(" 💾 Save & Back ", id="ts-save", variant="success")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ts-back":
            self.dismiss()
        elif event.button.id == "ts-save":
            updates = {}
            for name, info in self._config.items():
                w = self._inputs.get(name)
                if w and w.value != info.get("value", ""):
                    updates[name] = w.value
            if updates:
                _write_tool_config(self._filepath, updates)
                self.app.notify(f"✅ {self._module_name} 已保存", title="保存完成")
            self.dismiss()


#=======================================================================================
#.       ToolsModal (L2) — tool 模块列表
#=======================================================================================

class ToolsModal(ModalScreen):
    BINDINGS = [
        ("escape", "dismiss", "Close"),
    ]
    CSS = """
    ToolsModal {
        align: center middle;
    }
    #tools-dialog {
        width: 45%;
        height: auto;
        border: thick $warning;
        background: $surface;
        padding: 1 2;
    }
    #tools-title {
        text-align: center;
        padding: 1;
        background: $warning;
        color: $text;
        text-style: bold;
    }
    #tools-body {
        margin: 1 0;
    }
    #tools-body Button {
        width: 100%;
        margin-bottom: 1;
    }
    #tools-close {
        dock: bottom;
        height: 3;
        align: right middle;
    }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="tools-dialog"):
            yield Static("🔧 Tools 参数管理", id="tools-title")
            with VerticalScroll(id="tools-body"):
                for t in _TOOLS:
                    has = bool(t.configs)
                    label = f"  {t.name}  {'✓' if has else '(无参数)'}"
                    yield Button(label, id=f"tool-{t.name}", variant="primary" if has else "default")
            with Horizontal(id="tools-close"):
                yield Button("Cancel", id="tools-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "tools-cancel":
            self.dismiss()
        elif bid.startswith("tool-"):
            name = bid[5:]
            root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            filepath = os.path.join(root, "tools", f"{name}.py")
            self.app.push_screen(ToolSettingsModal(name, filepath))
