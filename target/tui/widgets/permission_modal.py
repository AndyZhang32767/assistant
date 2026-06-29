#=======================================================================================
#.       tui/widgets/permission_modal.py — 用户权限管理界面
#.
#.       主界面：所有 sessions 用户列表，每人 3 行，pr=绿 / de=红 / pb=默认
#.              右侧 更改（黄）/ 删除（红）
#.       二级弹窗：ChangeModal（选 pr/pb/ban）、DeleteModal（确认 Ban）
#.       ConfirmMessageModal：独立弹窗，Premium/Normal 开关 + 消息队列
#.       动画方案：空壳 fade-in → 替换为真实 dialog（主+子均一致）
#=======================================================================================

import asyncio
import logging

from textual.app import ComposeResult
from textual.containers import VerticalScroll, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static, Button, TextArea, Switch, Checkbox

from bot.session import sessions, persist_sessions

logger = logging.getLogger("bot.session")


PREMIUM = False
NORMAL = True

#=======================================================================================
#.       ChangeModal — 更改权限弹窗
#=======================================================================================

class ChangeModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close")]

    CSS = """
    ChangeModal { align: center middle; }

    #change-shell {
        width: 40%; height: 35%;
        border: thick $primary; background: $surface;
        display: none; opacity: 0%;
    }
    #change-shell.-visible { display: block; }
    #change-shell.-fade-in { opacity: 100%; transition: opacity 250ms in_out_cubic; }

    #change-dialog {
        width: 40%; height:35%;
        border: thick $primary; background: $surface;
        padding: 1 2; display: none;
    }
    #change-dialog.-visible { display: block; }

    #change-title { text-align: center; padding: 1; background: $primary; color: $text; text-style: bold; }
    #change-info  { padding: 1; text-align: center; margin: 1 0; }
    #change-btns  { height: 3; align: center middle; margin-bottom: 1; }
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
                yield Button("→ Premium", id="sub-pr",     variant="success")
                yield Button("→ Normal",  id="sub-pb",     variant="primary")
                yield Button("→ Ban",     id="sub-ban",    variant="error")
                yield Button("取消",      id="sub-cancel")

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

    #delete-shell {
        width: 40%; height: 30%;
        border: thick $error; background: $surface;
        display: none; opacity: 0%;
    }
    #delete-shell.-visible { display: block; }
    #delete-shell.-fade-in { opacity: 100%; transition: opacity 250ms in_out_cubic; }

    #delete-dialog {
        width: 40%; height: 30%;
        border: thick $error; background: $surface;
        padding: 1 2; display: none;
    }
    #delete-dialog.-visible { display: block; }

    #delete-title { text-align: center; padding: 1; background: $error; color: $text; text-style: bold; }
    #delete-info  { padding: 1; text-align: center; margin: 1 0; }
    #delete-btns  { height: 3; align: center middle; margin-bottom: 1; }
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
                yield Button("确认 Ban", id="sub-confirm-delete", variant="error")
                yield Button("取消",     id="sub-cancel",         variant="primary")

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
#.
#.       footer 右侧新增「消息确认」按钮，点击弹出 ConfirmMessageModal
#=======================================================================================

class PermissionModal(ModalScreen):

    CSS = """
    PermissionModal { align: center middle; }

    #perm-shell {
        width: 70%; height: 80%;
        border: thick $primary; background: $surface;
        display: none; opacity: 0%;
    }
    #perm-shell.-visible { display: block; }
    #perm-shell.-fade-in { opacity: 100%; transition: opacity 300ms in_out_cubic; }

    #perm-dialog {
        width: 70%; height: 80%;
        border: thick $primary; background: $surface;
        padding: 1 2; display: none;
    }
    #perm-dialog.-visible { display: block; }

    #perm-title { text-align: center; padding: 1; background: $primary; color: $text; text-style: bold; }

    #perm-body  { height: 1fr; margin: 1 0; overflow-y: auto; }

    #perm-footer { dock: bottom; height: 3; align: right middle; }
    #perm-footer Button { margin: 0 1; }

    .user-row     { height: 3; padding: 0 1; }
    .user-pad-left  { width: 10%; }
    .user-pad-right { width: 10%; }
    .user-name      { width: 1fr; content-align: left middle; }
    .user-name-pr   { width: 1fr; content-align: left middle; color: green; }
    .user-name-de   { width: 1fr; content-align: left middle; color: red; }
    .user-buttons   { width: auto; align: right middle; }
    .user-buttons Button { margin: 0 1; min-width: 10; }
    """

    BINDINGS = [("escape", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="perm-shell")
        with VerticalScroll(id="perm-dialog"):
            yield Static("用户权限管理", id="perm-title")
            with VerticalScroll(id="perm-body"):
                yield from self._build_user_rows()
            with Horizontal(id="perm-footer"):
                # ← 消息确认入口改为独立按钮，弹出专用 Modal
                yield Button("消息确认", id="perm-confirm-msgs", variant="warning")
                yield Button("Close (Esc)", id="perm-close")

    def _build_user_rows(self):
        if not sessions:
            return [Static("暂无已授权用户")]

        widgets = []
        for uid, info in sessions.items():
            chk = info.get("chk", "F")
            user_name = info.get("name", f"ID: {uid}")
            label = f"[{uid}] {user_name}"
            name_class = (
                "user-name-pr" if chk == "T" else
                "user-name-de" if chk == "D" else
                "user-name"
            )
            row = Horizontal(
                Static("",    classes="user-pad-left"),
                Static(label, classes=name_class),
                Horizontal(
                    Button("更改", id=f"perm-change-{uid}", variant="warning"),
                    Button("删除", id=f"perm-delete-{uid}", variant="error"),
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

        elif bid == "perm-confirm-msgs":
            self.app.push_screen(ConfirmMessageModal())

        elif bid.startswith("perm-change-"):
            uid  = int(bid.replace("perm-change-", ""))
            info = sessions.get(uid, {})
            name = f"[{uid}] {info.get('name', 'Unknown')}"
            self.app.push_screen(
                ChangeModal(uid, name, info.get("chk", "F")),
                callback=self._on_sub_done,
            )

        elif bid.startswith("perm-delete-"):
            uid  = int(bid.replace("perm-delete-", ""))
            info = sessions.get(uid, {})
            name = f"[{uid}] {info.get('name', 'Unknown')}"
            self.app.push_screen(
                DeleteModal(uid, name, info.get("chk", "F")),
                callback=self._on_sub_done,
            )

    def _on_sub_done(self, _=None) -> None:
        body = self.query_one("#perm-body", VerticalScroll)
        body.remove_children()
        body.mount_all(self._build_user_rows())


#=======================================================================================
#.       ConfirmMessageModal — 消息确认管理弹窗（独立）
#.
#.       布局（从上到下）：
#.         title
#.         settings 行：[☑ Premium 确认]  [☑ Normal 确认]        ← Checkbox 横排
#.         分割线
#.         消息队列（滚动，左右各留 5%）
#.           每条消息：header / 可编辑 TextArea / [拦截] [发送]
#.           时间旧 → 新（即 pending 队列自然顺序）
#.         footer：Close (Esc)
#.
#.       关键设计：
#.         · 拦截不阻塞——直接从队列移除，不 await bot 任何操作
#.         · 发送通过 asyncio.create_task 非阻塞投递
#.         · 每 3 秒非破坏性刷新：只增删差异卡片，保留编辑状态
#=======================================================================================


class ConfirmMessageModal(ModalScreen):

    CSS = """
    ConfirmMessageModal { align: center middle; }

    /* ── 动画壳 ── */
    #confirm-shell {
        width: 85%; height: 85%;
        border: thick $warning; background: $surface;
        display: none; opacity: 0%;
    }
    #confirm-shell.-visible { display: block; }
    #confirm-shell.-fade-in { opacity: 100%; transition: opacity 300ms in_out_cubic; }

    /* ── 真实对话框 ── */
    #confirm-dialog {
        width: 85%; height: 85%;
        border: thick $warning; background: $surface;
        padding: 1 2; display: none;
    }
    #confirm-dialog.-visible { display: block; }

    /* ── title ── */
    #confirm-title {
        text-align: center; padding: 1;
        background: $warning; color: $text; text-style: bold;
    }

    /* ── 设置行：Checkbox 横排 ── */
    #confirm-settings {
        height: 4;
        align: left middle;
        padding: 0 1;
        border-bottom: solid $surface-lighten-1;
    }
    #confirm-settings Checkbox { margin: 0 3 0 0; }


    /* ── 消息队列：VerticalScroll 直接承担滚动，margin 实现左右留白 ── */
    #msg-queue {
        height: 1fr;
        overflow-y: auto;
        margin: 1 4;
    }


    /* ── 消息卡片 ── */
    .msg-card {
        border: solid $primary-darken-2;
        height: auto;
        padding: 1 1 0 1;
        margin: 1 0;
    }
    .msg-header {
        text-style: bold;
        padding: 0 0 1 0;
    }
    .msg-textarea {
        height: 15;
        border: solid $surface-lighten-1;
        margin: 0 0 1 0;
    }
    .msg-buttons {
        height: 3;
        align: right middle;
        margin-bottom: 1;
    }
    .msg-buttons Button { margin: 0 1; min-width: 8; }

    /* ── 空状态 ── */
    #msg-empty {
        text-align: center;
        color: $text-disabled;
        padding: 4;
    }

    /* ── footer ── */
    #confirm-footer {
        dock: bottom;
        height: 3;
        align: right middle;
    }
    """

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self):
        super().__init__()
        self._refresh_timer = None

    # ──────────────────────────────────────────────
    #   compose
    # ──────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        from bot.session import get_confirm_settings, get_pending_messages
        premium_on, normal_on = get_confirm_settings()

        yield VerticalScroll(id="confirm-shell")

        with VerticalScroll(id="confirm-dialog"):
            yield Static("消息确认管理", id="confirm-title")

            # 设置行：两个 Checkbox 横排
            with Horizontal(id="confirm-settings"):
                yield Checkbox("Premium 确认", value=premium_on, id="chk-premium")
                yield Checkbox("Normal 确认",  value=normal_on,  id="chk-normal")

            # 消息队列（旧→新，自然顺序）
            # VerticalScroll 直接作为队列容器，margin 实现左右留白
            with VerticalScroll(id="msg-queue"):
                pending = get_pending_messages()
                if pending:
                    for msg in pending:
                        yield self._build_card(msg)
                else:
                    yield Static("暂无待确认消息", id="msg-empty")

            with Horizontal(id="confirm-footer"):
                yield Button("Close (Esc)", id="confirm-close-btn")

    # ──────────────────────────────────────────────
    #   动画
    # ──────────────────────────────────────────────

    def on_mount(self) -> None:
        shell = self.query_one("#confirm-shell")
        shell.add_class("-visible")
        self.set_timer(0.03, lambda: shell.add_class("-fade-in"))
        self.set_timer(0.35, self._swap_to_real)
        self._refresh_timer = self.set_interval(3.0, self._refresh_queue)

    def _swap_to_real(self) -> None:
        self.query_one("#confirm-shell").display = False
        self.query_one("#confirm-dialog").add_class("-visible")

    def on_unmount(self) -> None:
        if self._refresh_timer:
            self._refresh_timer.stop()

    # ──────────────────────────────────────────────
    #   构建单条消息卡片
    # ──────────────────────────────────────────────

    def _build_card(self, msg):
        ts        = msg.timestamp.strftime("%H:%M:%S")
        user_type = "Premium" if msg.chk == "T" else "Normal"
        return Vertical(
            Static(f"[{ts}]  Chat {msg.chat_id}  ({user_type})", classes="msg-header"),
            TextArea(msg.text, classes="msg-textarea", id=f"ta-{msg.msg_id}"),
            Horizontal(
                Button("拦截", id=f"block-{msg.msg_id}", variant="error"),
                Button("发送", id=f"send-{msg.msg_id}",  variant="success"),
                classes="msg-buttons",
            ),
            id=f"msg-card-{msg.msg_id}",
            classes="msg-card",
        )

    # ──────────────────────────────────────────────
    #   非破坏性刷新：只增删差异卡片，保留编辑中的 TextArea
    # ──────────────────────────────────────────────

    def _refresh_queue(self) -> None:
        from bot.session import get_pending_messages
        pending = get_pending_messages()

        try:
            queue = self.query_one("#msg-queue", VerticalScroll)
        except Exception:
            return

        # 当前渲染的卡片
        rendered: dict[str, object] = {}
        for child in list(queue.children):
            if child.id and child.id.startswith("msg-card-"):
                rendered[child.id] = child

        pending_ids = {f"msg-card-{m.msg_id}" for m in pending}

        # 移除已处理的卡片
        for card_id, child in list(rendered.items()):
            if card_id not in pending_ids:
                child.remove()

        # 追加新到达的卡片（append 到末尾，保持时间旧→新）
        for msg in pending:
            card_id = f"msg-card-{msg.msg_id}"
            if card_id not in rendered:
                queue.mount(self._build_card(msg))

        # 空状态管理
        has_cards = any(
            c.id and c.id.startswith("msg-card-")
            for c in queue.children
        )
        try:
            empty = queue.query_one("#msg-empty")
        except Exception:
            empty = None

        if not pending and not has_cards and empty is None:
            queue.mount(Static("暂无待确认消息", id="msg-empty"))
        elif pending and has_cards and empty is not None:
            empty.remove()

    # ──────────────────────────────────────────────
    #   按钮事件
    # ──────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        from bot.session import remove_pending_message
        bid = event.button.id or ""

        if bid.startswith("send-"):
            msg_id = bid[len("send-"):]
            # 先读取编辑后的文本
            try:
                edited_text = self.query_one(f"#ta-{msg_id}", TextArea).text
            except Exception:
                edited_text = ""
            # 从队列取出——不阻塞
            msg = remove_pending_message(msg_id)
            if msg and msg.message:
                logger.info(f"[发送确认] chat_id={msg.chat_id}")
                # 同步更新 history：用编辑后的文本替换最后一条 model 回复
                self._sync_history(msg.chat_id, edited_text)
                asyncio.create_task(msg.message.reply_text(edited_text))
            self._remove_card(msg_id)

        elif bid.startswith("block-"):
            msg_id = bid[len("block-"):]
            # 拦截：直接从队列移除，不做任何 bot 操作
            # → 后续对话照常生成，不阻塞
            msg = remove_pending_message(msg_id)
            if msg:
                logger.info(f"[拦截] chat_id={msg.chat_id} msg_id={msg_id} 已静默丢弃")
            self._remove_card(msg_id)

        elif bid == "confirm-close-btn":
            self.dismiss()

    def _remove_card(self, msg_id: str) -> None:
        """移除卡片并在队列为空时显示空状态提示。"""
        try:
            self.query_one(f"#msg-card-{msg_id}").remove()
        except Exception:
            pass
        # 检查是否清空
        try:
            queue = self.query_one("#msg-queue", VerticalScroll)
            has_cards = any(
                c.id and c.id.startswith("msg-card-")
                for c in queue.children
            )
            if not has_cards:
                try:
                    queue.query_one("#msg-empty")
                except Exception:
                    queue.mount(Static("暂无待确认消息", id="msg-empty"))
        except Exception:
            pass

    # ──────────────────────────────────────────────
    #   History 同步：用编辑后的文本替换最后一条 model 回复
    # ──────────────────────────────────────────────

    def _sync_history(self, chat_id: int, edited_text: str) -> None:
        """将 save_history 中该 chat 的最后一条 model 角色文本替换为编辑后的版本。"""
        from bot.session import save_history
        from google.genai import types

        history = save_history.get(chat_id, [])
        if not history:
            return
        for i in range(len(history) - 1, -1, -1):
            if getattr(history[i], 'role', '') == 'model':
                history[i] = types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=edited_text)],
                )
                break

    # ──────────────────────────────────────────────
    #   Checkbox 事件：更新确认设置
    # ──────────────────────────────────────────────

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        from bot.session import get_confirm_settings, set_confirm_settings
        premium, normal = get_confirm_settings()
        if event.checkbox.id == "chk-premium":
            set_confirm_settings(event.value, normal)
        elif event.checkbox.id == "chk-normal":
            set_confirm_settings(premium, event.value)
        