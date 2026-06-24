#=======================================================================================
#.       tui/widgets/auth_modal.py — 新用户授权弹窗
#.       当未知用户首次向 Bot 发送消息时，通过此弹窗让管理员选择：
#.         - 私人 (Private) — 分配 Premium 模式
#.         - 公共 (Public)  — 分配 Normal 模式
#.         - 禁止 (Deny)    — 加入黑名单，拒绝服务
#.
#.       动画方案与其他 modal 一致：空壳 fade-in → 替换为真实 dialog。
#=======================================================================================

import asyncio

from textual.app import ComposeResult
from textual.containers import VerticalScroll, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, Button


class AuthModal(ModalScreen):
    BINDINGS = [
        ("escape", "dismiss", "Close"),
    ]
    CSS = """
    AuthModal {
        align: center middle;
    }

    /* ================================================================
    .   Fade 空壳 — 仅用于淡入动画
    .=============================================================== */

    #auth-shell {
        width: 50%;
        height: 30;
        border: thick $primary;
        background: $surface;
        display: none;
        opacity: 0%;
    }

    #auth-shell.-visible {
        display: block;
    }

    #auth-shell.-fade-in {
        opacity: 100%;
        transition: opacity 300ms in_out_cubic;
    }

    /* ================================================================
    .   真实 dialog — 无渐变，fade 完成后替换壳
    .=============================================================== */

    #auth-dialog {
        width: 50%;
        height: 30;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
        display: none;
    }

    #auth-dialog.-visible {
        display: block;
    }

    #auth-title {
        text-align: center;
        padding: 1;
        background: $primary;
        color: $text;
        text-style: bold;
    }

    #auth-info {
        padding: 1;
        margin: 1 0;
    }

    #auth-buttons {
        height: 3;
        align: center middle;
        margin-bottom: 1;
    }

    #auth-buttons Button {
        margin: 0 1;
        min-width: 10;
    }
    """

    def __init__(self, user_id: int, user_name: str, chat_type: str,
                 group_id: int = None, group_name: str = None):
        super().__init__()
        self._user_id = user_id
        self._user_name = user_name
        self._chat_type = chat_type
        self._group_id = group_id
        self._group_name = group_name
        self._future: asyncio.Future | None = None

    def set_future(self, future: asyncio.Future) -> None:
        self._future = future

    #===================================================================================
    #.       界面构建 — 壳 + 真实 dialog
    #===================================================================================

    def compose(self) -> ComposeResult:
        # -- Fade 空壳
        yield VerticalScroll(id="auth-shell")

        # -- 真实 dialog（初始隐藏）
        info_lines = [
            f"用户 ID: {self._user_id}",
            f"名称: {self._user_name}",
        ]
        if self._group_id:
            info_lines.append(f"来源群组: {self._group_name} (ID: {self._group_id})")
        else:
            info_lines.append("来源: 私聊")

        with VerticalScroll(id="auth-dialog"):
            yield Static("新用户请求接入", id="auth-title")
            yield Static("\n".join(info_lines),
                id="auth-info",
            )
            with Horizontal(id="auth-buttons"):
                yield Button(" 私人 (Private) ", id="auth-pr", variant="primary")
                yield Button(" 公共 (Public) ", id="auth-pb", variant="primary")
                yield Button(" 禁止 (Deny) ", id="auth-deny", variant="error")

    #===================================================================================
    #.       挂载 — 壳淡入 → 替换为真实 dialog
    #===================================================================================

    def on_mount(self) -> None:
        shell = self.query_one("#auth-shell")
        shell.add_class("-visible")
        self.set_timer(0.03, lambda: shell.add_class("-fade-in"))
        self.set_timer(0.35, self._swap_to_real)

    def _swap_to_real(self) -> None:
        """壳淡入完成 → 隐藏壳，显示真实 dialog。"""
        self.query_one("#auth-shell").display = False
        self.query_one("#auth-dialog").add_class("-visible")

    #===================================================================================
    #.       按钮事件
    #===================================================================================

    def on_button_pressed(self, event: Button.Pressed) -> None:
        choice = event.button.id
        if choice == "auth-pr":
            self._resolve("pr")
        elif choice == "auth-pb":
            self._resolve("pb")
        elif choice == "auth-deny":
            self._resolve("deny")

    def _resolve(self, choice: str) -> None:
        if self._future and not self._future.done():
            self._future.set_result(choice)
        self.dismiss()
