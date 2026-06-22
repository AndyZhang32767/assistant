#=======================================================================================
#.       tui/widgets/schedule_modal.py — 定时任务查看
#.       展示所有已注册的定时唤起计划，每 10s 自动刷新。
#=======================================================================================

from textual.app import ComposeResult
from textual.containers import VerticalScroll, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, Button

from utils.scheduler import get_schedules


class ScheduleModal(ModalScreen):
    BINDINGS = [
        ("escape", "dismiss", "Close"),
    ]
    CSS = """
    ScheduleModal {
        align: center middle;
    }
    #schedule-dialog {
        width: 55%;
        height: auto;
        max-height: 70%;
        border: thick $secondary;
        background: $surface;
        padding: 1 2;
    }
    #schedule-title {
        text-align: center;
        padding: 1;
        background: $secondary;
        color: $text;
        text-style: bold;
    }
    #schedule-header {
        height: 1;
        margin-top: 1;
        padding: 0 2;
        background: $panel;
        color: $text-disabled;
        text-style: bold;
    }
    #schedule-body {
        height: auto;
        max-height: 20;
        margin-bottom: 1;
    }
    .schedule-row {
        height: 1;
        padding: 0 2;
    }
    #schedule-close {
        dock: bottom;
        height: 3;
        align: right middle;
    }
    """

    def __init__(self):
        super().__init__()
        self._timer = None

    def compose(self) -> ComposeResult:
        items = get_schedules()
        with VerticalScroll(id="schedule-dialog"):
            yield Static("🕐 定时唤起计划", id="schedule-title")
            with VerticalScroll(id="schedule-body"):
                if not items:
                    yield Static("  暂无已注册的定时任务", classes="schedule-row")
                else:
                    yield Static("  时间          唤起的函数", classes="schedule-header")
                    for item in items:
                        yield Static(f"  {item['time']}        {item['callback']}", classes="schedule-row")
            with Horizontal(id="schedule-close"):
                yield Button("Close (Esc)", id="schedule-close-btn")

    def on_mount(self) -> None:
        """每 10s 刷新一次，与调度器同步。"""
        self._timer = self.set_interval(10, self._refresh)

    def on_unmount(self) -> None:
        if self._timer:
            self._timer.stop()

    def _refresh(self) -> None:
        body = self.query_one("#schedule-body")
        body.remove_children()
        items = get_schedules()
        if not items:
            body.mount(Static("  暂无已注册的定时任务", classes="schedule-row"))
        else:
            body.mount(Static("  时间          唤起的函数", classes="schedule-header"))
            for item in items:
                body.mount(Static(f"  {item['time']}        {item['callback']}", classes="schedule-row"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()
