#=======================================================================================
#.       tui/widgets/permission_modal.py — 用户权限管理界面
#.
#.       主界面：所有 sessions 用户列表，每人 3 行，pr=绿 / de=红 / pb=默认
#.              右侧 更改（黄）/ 删除（红）
#.       二级弹窗：ChangeModal（选 pr/pb/ban）、DeleteModal（确认 Ban）
#.       动画方案：空壳 fade-in → 替换为真实 dialog（主+子均一致）
#=======================================================================================

import asyncio

from textual.app import ComposeResult
from textual.containers import VerticalScroll, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static, Button, Select, TextArea

from bot.session import sessions, persist_sessions


#=======================================================================================
#.       ChangeModal — 更改权限弹窗
#=======================================================================================

class ChangeModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close")]

    CSS = """
    ChangeModal { align: center middle; }
    #change-shell { width: 40%; height: 25%; border: thick $primary; background: $surface; display: none; opacity: 0%; }
    #change-shell.-visible { display: block; }
    #change-shell.-fade-in { opacity: 100%; transition: opacity 250ms in_out_cubic; }
    #change-dialog { width: 40%; height: 25%; border: thick $primary; background: $surface; padding: 1 2; display: none; }
    #change-dialog.-visible { display: block; }
    #change-title { text-align: center; padding: 1; background: $primary; color: $text; text-style: bold; }
    #change-info { padding: 1; text-align: center; margin: 1 0; }
    #change-btns { height: 3; align: center middle; margin-bottom: 1; }
    #change-btns Button { margin: 0 1; min-width: 12; }
    """

    def __init__(self, uid: int, name: str, current_chk: str):
        super().__init__()
        self._uid = uid
        self._name = name
        self._current = current_chk

    def compose(self) -> ComposeResult:
        labels = {"T": "Premium", "F": "Normal", "D": "Banned"}
        current_label = labels.get(self._current, "Unknown")

        yield VerticalScroll(id="change-shell")
        with VerticalScroll(id="change-dialog"):
            yield Static(f"更改权限: {self._name}", id="change-title")
            yield Static(f"当前: {current_label}", id="change-info")
            with Horizontal(id="change-btns"):
                yield Button("→ Premium ", id="sub-pr", variant="success")
                yield Button("→ Normal ", id="sub-pb", variant="primary")
                yield Button("→ Ban", id="sub-ban", variant="error")
                yield Button(" 取消 ", id="sub-cancel")

    def on_mount(self) -> None:
        shell = self.query_one("#change-shell")
        shell.add_class("-visible")
        self.set_timer(0.03, lambda: shell.add_class("-fade-in"))
        self.set_timer(0.3, self._swap_to_real)

    def _swap_to_real(self) -> None:
        self.query_one("#change-shell").display = False
        self.query_one("#change-dialog").add_class("-visible")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid in ("sub-pr", "sub-pb", "sub-ban"):
            chk = {"sub-pr": "T", "sub-pb": "F", "sub-ban": "D"}[bid]
            if self._uid in sessions:
                sessions[self._uid]["chk"] = chk
                asyncio.create_task(persist_sessions())
            self.dismiss()
        elif bid == "sub-cancel":
            self.dismiss()


#=======================================================================================
#.       DeleteModal — 确认 Ban 弹窗
#=======================================================================================

class DeleteModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close")]

    CSS = """
    DeleteModal { align: center middle; }
    #delete-shell { width: 40%; height: 30%; border: thick $error; background: $surface; display: none; opacity: 0%; }
    #delete-shell.-visible { display: block; }
    #delete-shell.-fade-in { opacity: 100%; transition: opacity 250ms in_out_cubic; }
    #delete-dialog { width: 40%; height: 30%; border: thick $error; background: $surface; padding: 1 2; display: none; }
    #delete-dialog.-visible { display: block; }
    #delete-title { text-align: center; padding: 1; background: $error; color: $text; text-style: bold; }
    #delete-info { padding: 1; text-align: center; margin: 1 0; }
    #delete-btns { height: 3; align: center middle; margin-bottom: 1; }
    #delete-btns Button { margin: 0 1; min-width: 12; }
    """

    def __init__(self, uid: int, name: str, current_chk: str):
        super().__init__()
        self._uid = uid
        self._name = name
        self._current = current_chk

    def compose(self) -> ComposeResult:
        labels = {"T": "Premium", "F": "Normal", "D": "Banned"}
        current_label = labels.get(self._current, "Unknown")

        yield VerticalScroll(id="delete-shell")
        with VerticalScroll(id="delete-dialog"):
            yield Static(f"确认 Ban: {self._name}", id="delete-title")
            yield Static(f"当前权限: {current_label}，Ban 后用户消息将被拦截", id="delete-info")
            with Horizontal(id="delete-btns"):
                yield Button(" 确认 Ban ", id="sub-confirm-delete", variant="error")
                yield Button(" 取消 ", id="sub-cancel", variant="primary")

    def on_mount(self) -> None:
        shell = self.query_one("#delete-shell")
        shell.add_class("-visible")
        self.set_timer(0.03, lambda: shell.add_class("-fade-in"))
        self.set_timer(0.3, self._swap_to_real)

    def _swap_to_real(self) -> None:
        self.query_one("#delete-shell").display = False
        self.query_one("#delete-dialog").add_class("-visible")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "sub-confirm-delete":
            if self._uid in sessions:
                sessions[self._uid]["chk"] = "D"
                asyncio.create_task(persist_sessions())
            self.dismiss()
        elif event.button.id == "sub-cancel":
            self.dismiss()


#=======================================================================================
#.       PermissionModal — 主权限管理界面
#=======================================================================================

class PermissionModal(ModalScreen):

    CSS = """
    PermissionModal { align: center middle; }

    #perm-shell { width: 70%; height: 80%; border: thick $primary; background: $surface; display: none; opacity: 0%; }
    #perm-shell.-visible { display: block; }
    #perm-shell.-fade-in { opacity: 100%; transition: opacity 300ms in_out_cubic; }

    #perm-dialog { width: 70%; height: 80%; border: thick $primary; background: $surface; padding: 1 2; display: none; }
    #perm-dialog.-visible { display: block; }

    #perm-title { text-align: center; padding: 1; background: $primary; color: $text; text-style: bold; }
    #perm-body { height: 1fr; margin: 1 0; overflow-y: auto; }
    #perm-footer { dock: bottom; height: 3; align: right middle; }
    #perm-footer Select { margin: 0 1; width: 16; }
    #perm-footer Button { margin: 0 1; }

    .user-row { height: 3; padding: 0 1; }
    .user-pad-left { width: 10%; }
    .user-pad-right { width: 10%; }
    .user-name { width: 1fr; content-align: left middle; }
    .user-name-pr { width: 1fr; content-align: left middle; color: green; }
    .user-name-de { width: 1fr; content-align: left middle; color: red; }
    .user-buttons { width: auto; align: right middle; }
    .user-buttons Button { margin: 0 1; min-width: 10; }
    """

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self):
        super().__init__()

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="perm-shell")

        with VerticalScroll(id="perm-dialog"):
            yield Static("用户权限管理", id="perm-title")
            with VerticalScroll(id="perm-body"):
                yield from self._build_user_rows()
            with Horizontal(id="perm-footer"):
                yield Select(
                    options=[("关闭确认", "off"), ("仅Public", "public"), ("全部确认", "all")],
                    prompt="发送确认",
                    value=_confirm_mode,
                    id="confirm-select",
                )
                yield Button("Close (Esc)", id="perm-close")

    def _build_user_rows(self):
        if not sessions:
            return [Static("暂无已授权用户")]

        widgets = []
        for uid, info in sessions.items():
            chk = info.get("chk", "F")
            user_name = info.get("name", f"ID: {uid}")
            label = f"[{uid}] {user_name}"
            if chk == "T":
                name_class = "user-name-pr"
            elif chk == "D":
                name_class = "user-name-de"
            else:
                name_class = "user-name"

            row = Horizontal(
                Static("", classes="user-pad-left"),
                Static(label, classes=name_class),
                Horizontal(
                    Button(" 更改 ", id=f"perm-change-{uid}", variant="warning"),
                    Button(" 删除 ", id=f"perm-delete-{uid}", variant="error"),
                    classes="user-buttons",
                ),
                Static("", classes="user-pad-right"),
                classes="user-row",
            )
            widgets.append(row)
        return widgets

    def on_mount(self) -> None:
        shell = self.query_one("#perm-shell")
        shell.add_class("-visible")
        self.set_timer(0.03, lambda: shell.add_class("-fade-in"))
        self.set_timer(0.35, self._swap_to_real)

    def _swap_to_real(self) -> None:
        self.query_one("#perm-shell").display = False
        self.query_one("#perm-dialog").add_class("-visible")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""

        if bid == "perm-close":
            self.dismiss()

        elif bid.startswith("perm-change-"):
            uid = int(bid.replace("perm-change-", ""))
            info = sessions.get(uid, {})
            chk = info.get("chk", "F")
            name = f"[{uid}] {info.get('name', 'Unknown')}"
            self.app.push_screen(ChangeModal(uid, name, chk), callback=self._on_sub_done)

        elif bid.startswith("perm-delete-"):
            uid = int(bid.replace("perm-delete-", ""))
            info = sessions.get(uid, {})
            chk = info.get("chk", "F")
            name = f"[{uid}] {info.get('name', 'Unknown')}"
            self.app.push_screen(DeleteModal(uid, name, chk), callback=self._on_sub_done)

    def on_select_changed(self, event: Select.Changed) -> None:
        """发送确认模式切换。"""
        if event.select.id == "confirm-select":
            set_confirm_mode(event.value)

    def _on_sub_done(self, _=None) -> None:
        """子弹窗关闭后刷新用户列表。"""
        body = self.query_one("#perm-body", VerticalScroll)
        body.remove_children()
        body.mount_all(self._build_user_rows())


#=======================================================================================
#.       ConfirmSendModal — 发送确认弹窗
#=======================================================================================

class ConfirmSendModal(ModalScreen):

    CSS = """
    ConfirmSendModal { align: center middle; }
    #confirm-shell { width: 70%; height: 60%; border: thick $warning; background: $surface; display: none; opacity: 0%; }
    #confirm-shell.-visible { display: block; }
    #confirm-shell.-fade-in { opacity: 100%; transition: opacity 250ms in_out_cubic; }
    #confirm-dialog { width: 70%; height: 60%; border: thick $warning; background: $surface; padding: 1 2; display: none; }
    #confirm-dialog.-visible { display: block; }
    #confirm-title { text-align: center; padding: 1; background: $warning; color: $text; text-style: bold; }
    #confirm-body { height: 1fr; margin: 1 0; }
    #confirm-textarea { width: 100%; height: 100%; }
    #confirm-footer { dock: bottom; height: 3; align: right middle; }
    #confirm-footer Button { margin: 0 1; min-width: 12; }
    """

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, text: str, chat_id: int):
        super().__init__()
        self._text = text
        self._chat_id = chat_id
        self._future: asyncio.Future | None = None

    def set_future(self, future: asyncio.Future) -> None:
        self._future = future

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="confirm-shell")
        with VerticalScroll(id="confirm-dialog"):
            yield Static("发送确认", id="confirm-title")
            with VerticalScroll(id="confirm-body"):
                yield TextArea(self._text, id="confirm-textarea")
            with Horizontal(id="confirm-footer"):
                yield Button(" 取消 ", id="confirm-cancel", variant="error")
                yield Button(" 发送 ", id="confirm-send", variant="success")

    def on_mount(self) -> None:
        shell = self.query_one("#confirm-shell")
        shell.add_class("-visible")
        self.set_timer(0.03, lambda: shell.add_class("-fade-in"))
        self.set_timer(0.3, self._swap_to_real)

    def _swap_to_real(self) -> None:
        self.query_one("#confirm-shell").display = False
        self.query_one("#confirm-dialog").add_class("-visible")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-send":
            text = self.query_one("#confirm-textarea", TextArea).text
            if self._future and not self._future.done():
                self._future.set_result(text)
            self.dismiss()
        elif event.button.id == "confirm-cancel":
            if self._future and not self._future.done():
                self._future.set_result(None)
            self.dismiss()


#=======================================================================================
#.       全局发送确认模式
#.       "off" = 不确认, "public" = 仅 pb 用户确认, "all" = 全部确认
#=======================================================================================

_confirm_mode = "off"


def set_confirm_mode(mode: str) -> None:
    global _confirm_mode
    _confirm_mode = mode


def get_confirm_mode() -> str:
    return _confirm_mode
