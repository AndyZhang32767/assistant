#=======================================================================================
#.       tui/widgets/config_modal.py — 配置编辑弹窗
#.       ConfigModal：主配置弹窗，编辑 core/config.py 所有变量。
#.       被 tui/app.py 的 config 按钮/快捷键触发。
#=======================================================================================

from textual.app import ComposeResult
from textual.containers import VerticalScroll, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, Input, TextArea, Button, Label

from tui.config_parser import Section, write_config


#=======================================================================================
#.       ConfigModal — 主配置弹窗
#=======================================================================================

class ConfigModal(ModalScreen):
    BINDINGS = [
        ("escape", "dismiss", "Close"),
    ]
    CSS = """
    ConfigModal {
        align: center middle;
    }
    #config-modal-dialog {
        width: 70%;
        height: 80%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #config-modal-title {
        text-align: center;
        padding: 1;
        background: $primary;
        color: $text;
        text-style: bold;
    }
    #config-modal-body {
        height: 1fr;
        margin: 1 0;
    }
    #config-modal-buttons {
        dock: bottom;
        align: right middle;
        height: 3;
    }
    .var-label {
        margin-top: 1;
        text-style: bold;
        color: $secondary;
    }
    .var-input {
        margin-bottom: 1;
    }
    """

    def __init__(self, section: Section, config_path: str):
        super().__init__()
        self._section = section
        self._config_path = config_path
        self._inputs: dict[str, Input | TextArea] = {}

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="config-modal-dialog"):
            yield Static(f"📝 {self._section.title}", id="config-modal-title")
            with VerticalScroll(id="config-modal-body"):
                for var in self._section.variables:
                    yield Label(f"{var.name}", classes="var-label")
                    if var.is_multiline:
                        ta = TextArea(var.value, id=f"var-{var.name}", classes="var-input")
                        ta.styles.height = 10
                        self._inputs[var.name] = ta
                        yield ta
                    else:
                        inp = Input(value=var.value, id=f"var-{var.name}", classes="var-input")
                        self._inputs[var.name] = inp
                        yield inp
            with Horizontal(id="config-modal-buttons"):
                yield Button(" Cancel ", id="btn-modal-cancel")
                yield Button(" 💾 Save & Close ", id="btn-modal-save", variant="success")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-modal-save":
            for var in self._section.variables:
                widget = self._inputs.get(var.name)
                if widget:
                    if isinstance(widget, TextArea):
                        var.value = widget.text
                    else:
                        var.value = widget.value
            write_config(self._config_path, [self._section])
            self.app.notify(f"✅ '{self._section.title}' 已保存", title="保存完成")
            self.dismiss()
        elif event.button.id == "btn-modal-cancel":
            self.dismiss()
