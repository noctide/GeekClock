"""主窗口：闹钟列表管理。"""

import hashlib
import logging
import re
from collections import defaultdict
from urllib.parse import urlparse

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from geekclock.core import config
from geekclock.dialogs.edit_alarm import EditAlarmDialog
from geekclock.main_window.alarm_card import AlarmCard

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """主窗口。

    信号：
    - config_changed: 用户修改了闹钟配置（增删改、启用切换），主程序需要 reload 调度器
    """

    config_changed = Signal()
    closed_to_tray = Signal()
    keep_alive_toggled = Signal()

    # 修改参数的密码哈希（默认密码: "0000"）
    # 想改密码：把新密码用 hashlib.sha256(b"你的密码").hexdigest() 算出来替换
    # python -c "import hashlib; print(hashlib.sha256(b'0000').hexdigest())"
    _NICKNAME_PASSWORD_HASH = "9af15b336e6a9619928537df30b2e6a2376569fcf9d7e773eccede65606529a0"


    def __init__(self, audio_player=None, scheduler=None, parent=None):
        super().__init__(parent)
        self._audio_player = audio_player
        self._scheduler = scheduler
        self._expanded_groups: set[str] = set()

        self.setWindowTitle("GeekClock")
        self.setMinimumWidth(120)
        self.resize(560, 600)

        self._setup_ui()
        self._refresh()

        # 每分钟刷新一次"下次触发"显示
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(60 * 1000)
        self._refresh_timer.timeout.connect(self._refresh)
        self._refresh_timer.start()

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部工具栏
        toolbar = QWidget()
        toolbar.setFixedHeight(56)
        toolbar.setStyleSheet("background: white; border-bottom: 1px solid #eee;")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(16, 0, 16, 0)

        self._title_label = QLabel("我的闹钟")
        self._title_label.setStyleSheet("font-size: 16px; font-weight: 500;")
        toolbar_layout.addWidget(self._title_label)

        self._count_label = QLabel("")
        self._count_label.setStyleSheet("font-size: 12px; color: #999; margin-left: 8px;")
        toolbar_layout.addWidget(self._count_label)

        toolbar_layout.addStretch()

        # 设置按钮
        settings_btn = QPushButton("⚙ 设置")
        settings_btn.setStyleSheet(
            "QPushButton { padding: 6px 14px; border: 1px solid #ddd; "
            "border-radius: 4px; font-size: 13px; background: white; }"
            "QPushButton:hover { background: #f5f5f5; }"
        )
        settings_btn.clicked.connect(self._on_open_settings)
        toolbar_layout.addWidget(settings_btn)

        self._pause_all_btn = QPushButton("全部暂停")
        self._pause_all_btn.setStyleSheet(
            "QPushButton { padding: 6px 14px; border: 1px solid #ddd; "
            "border-radius: 4px; font-size: 13px; background: white; }"
            "QPushButton:hover { background: #f5f5f5; }"
        )
        self._pause_all_btn.clicked.connect(self._on_pause_all)
        toolbar_layout.addWidget(self._pause_all_btn)

        new_btn = QPushButton("+ 新建闹钟")
        new_btn.setStyleSheet(
            "QPushButton { padding: 6px 14px; background: #185FA5; "
            "color: white; border: none; border-radius: 4px; font-size: 13px; }"
            "QPushButton:hover { background: #0C447C; }"
        )
        new_btn.clicked.connect(self._on_new_alarm)
        toolbar_layout.addWidget(new_btn)

        layout.addWidget(toolbar)

        # 列表滚动区
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setStyleSheet("background: #fafafa; border: none;")

        self._list_widget = QWidget()
        self._list_widget.setStyleSheet("background: #fafafa;")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(8, 8, 8, 8)
        self._list_layout.setSpacing(4)
        self._list_layout.addStretch()
        self._scroll.setWidget(self._list_widget)

        layout.addWidget(self._scroll, 1)

        # 底部状态栏
        statusbar = QWidget()
        statusbar.setFixedHeight(30)
        statusbar.setStyleSheet("background: white; border-top: 1px solid #eee;")
        status_layout = QHBoxLayout(statusbar)
        status_layout.setContentsMargins(16, 0, 16, 0)

        # 音响保活图标按钮（最左侧）
        self._keep_alive_btn = QPushButton("\U0001F4E2")
        self._keep_alive_btn.setFixedSize(28, 28)
        self._keep_alive_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._keep_alive_btn.setToolTip("音响保活设置")
        self._keep_alive_btn.setStyleSheet(
            "QPushButton { border: none; background: transparent; font-size: 14px; }"
            "QPushButton:hover { background: #f0f0f0; border-radius: 4px; }"
        )
        self._keep_alive_btn.clicked.connect(self._on_keep_alive_btn_clicked)
        status_layout.addWidget(self._keep_alive_btn)

        # 勿扰提示（保活图标右侧）
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(
            "font-size: 11px; color: #999; background: transparent;"
        )
        status_layout.addWidget(self._status_label)

        status_layout.addStretch()

        # 右下角参数（右侧）
        # 单击：选中文字（普通文字）/ 单击链接：打开
        # 双击：输入密码后编辑
        self._nickname_label = QLabel()
        self._nickname_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.LinksAccessibleByMouse
            | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._nickname_label.setOpenExternalLinks(True)
        self._nickname_label.setStyleSheet("""
            QLabel {
                color: #aaa;
                font-size: 11px;
                background: transparent;
                padding: 0;
            }
        """)
        self._nickname_label.installEventFilter(self)
        status_layout.addWidget(self._nickname_label)

        layout.addWidget(statusbar)

        # 初始化参数显示
        self._refresh_nickname()

    def _refresh(self) -> None:
        """重新渲染闹钟列表。"""
        # 清除现有卡片（保留末尾的 stretch）
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        alarms = config.get_alarms()
        enabled_count = sum(1 for a in alarms if a.get("enabled"))

        # 标题区
        self._count_label.setText(f"{enabled_count} 个已启用 / 共 {len(alarms)}")

        # 暂停按钮文字根据状态切换
        if enabled_count > 0:
            self._pause_all_btn.setText("全部暂停")
        else:
            self._pause_all_btn.setText("全部启用")

        # 状态栏
        global_settings = config.get_global_settings()
        if global_settings.get("dnd_enabled"):
            dnd_text = (
                f"勿扰时段 {global_settings.get('dnd_start')} – "
                f"{global_settings.get('dnd_end')} 已开启"
            )
        else:
            dnd_text = "勿扰时段未开启"
        self._status_label.setText(dnd_text)

        # 渲染卡片（按分组）
        if not alarms:
            empty = QLabel("还没有闹钟，点击右上角新建")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #aaa; font-size: 13px; padding: 40px;")
            self._list_layout.insertWidget(self._list_layout.count() - 1, empty)
            return

        from geekclock.core.config import get_group_color as _get_group_color
        from geekclock.main_window.collapsible_group import CollapsibleGroupWidget

        grouped = defaultdict(list)
        for alarm in alarms:
            grouped[alarm.get("group", "默认")].append(alarm)

        group_names = sorted(grouped.keys(), key=lambda g: (g != "默认", g))

        for group_name in group_names:
            group_alarms = grouped[group_name]
            color = _get_group_color(group_name)
            all_enabled = all(a.get("enabled") for a in group_alarms)
            expanded = group_name in self._expanded_groups

            group_widget = CollapsibleGroupWidget(
                group_name, color, expanded=expanded
            )
            group_widget.set_alarm_count(len(group_alarms))
            group_widget.update_batch_button(all_enabled)
            group_widget.toggle_group_requested.connect(self._on_toggle_group)

            # 记录展开状态
            def _make_collapse_handler(gn):
                return lambda exp: (
                    self._expanded_groups.add(gn) if exp
                    else self._expanded_groups.discard(gn)
                )
            group_widget.expanded_changed.connect(
                _make_collapse_handler(group_name)
            )

            for alarm in group_alarms:
                next_run = (
                    self._scheduler.get_next_run_time(alarm["id"])
                    if self._scheduler else None
                )
                card = AlarmCard(alarm, next_run=next_run)
                card.edit_requested.connect(self._on_edit_alarm)
                card.delete_requested.connect(self._on_delete_alarm)
                card.toggle_changed.connect(self._on_toggle_alarm)
                group_widget.add_alarm_card(card)

            self._list_layout.insertWidget(
                self._list_layout.count() - 1, group_widget
            )

        self._refresh_keep_alive_icon()

    def _on_new_alarm(self) -> None:
        dialog = EditAlarmDialog(audio_player=self._audio_player, parent=self)
        if dialog.exec() == EditAlarmDialog.DialogCode.Accepted:
            new_alarm = dialog.get_alarm()
            if config.add_alarm(new_alarm):
                self._notify_config_changed()

    def _on_edit_alarm(self, alarm_id: str) -> None:
        # 找到这条闹钟
        target = next(
            (a for a in config.get_alarms() if a.get("id") == alarm_id),
            None,
        )
        if not target:
            return

        dialog = EditAlarmDialog(
            audio_player=self._audio_player, alarm=target, parent=self
        )
        if dialog.exec() == EditAlarmDialog.DialogCode.Accepted:
            if dialog.is_delete_requested():
                config.delete_alarm(alarm_id)
            else:
                config.update_alarm(alarm_id, dialog.get_alarm())
            self._notify_config_changed()

    def _on_delete_alarm(self, alarm_id: str) -> None:
        target = next(
            (a for a in config.get_alarms() if a.get("id") == alarm_id),
            None,
        )
        if not target:
            return
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定删除闹钟「{target['name']}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            config.delete_alarm(alarm_id)
            self._notify_config_changed()

    def _on_toggle_alarm(self, alarm_id: str, enabled: bool) -> None:
        config.toggle_alarm(alarm_id, enabled)
        self._notify_config_changed()

    def _on_pause_all(self) -> None:
        alarms = config.get_alarms()
        any_enabled = any(a.get("enabled") for a in alarms)
        config.set_all_alarms_enabled(not any_enabled)
        self._notify_config_changed()

    def _on_toggle_group(self, group_name: str) -> None:
        alarms = [a for a in config.get_alarms() if a.get("group", "默认") == group_name]
        any_enabled = any(a.get("enabled") for a in alarms)
        config.toggle_group(group_name, not any_enabled)
        self._notify_config_changed()

    def _notify_config_changed(self) -> None:
        """通知主程序：配置变了，需要重载调度器和重绘界面。"""
        self.config_changed.emit()
        self._refresh()

    # 关闭窗口的行为由 main.py 控制
    # 设置 _close_to_tray = True 时，关闭按钮变成隐藏到托盘
    _close_to_tray = False

    def set_close_to_tray(self, enabled: bool) -> None:
        """设置关闭按钮的行为。

        True: 关闭=隐藏到托盘（程序继续运行）
        False: 关闭=退出程序
        """
        self._close_to_tray = enabled

    def closeEvent(self, event) -> None:
        """关闭主窗口的处理。

        - 托盘可用 + 启用了 close_to_tray：隐藏到托盘
        - 否则：默认退出行为
        """
        if self._close_to_tray:
            event.ignore()
            self.hide()
            # 触发信号让外部决定是否提示
            self.closed_to_tray.emit()
        else:
            super().closeEvent(event)

    # ============================================================
    # 昵称参数显示配置
    # ============================================================
    # 修改下面这一行可以改前缀符号
    # 常见选项："❄"（雪花）、"@"、"·"、"🔗"、"by"、""（无前缀）
    _NICKNAME_PREFIX = "❄ "

    # URL 过长时的显示策略：
    #   "domain"   - 只显示域名（推荐）
    #   "truncate" - 截断显示（最多 30 字符）
    #   "full"     - 完整显示（不处理）
    _URL_DISPLAY_MODE = "domain"
    # ============================================================

    def _refresh_nickname(self) -> None:
        """刷新参数显示。

        支持的输入格式：
        - 空字符串：显示「双击设置参数」
        - 纯文本：显示为灰色普通文字（如 "张三"）
        - 纯 URL：自动识别为蓝色链接（如 "https://github.com"）
        - 混合内容：文字 + URL（如 "张三 https://github.com"）
                    自动识别其中的 URL 部分作为链接
        """
        nickname = config.get_user_nickname()
        if not nickname:
            content = "可以下载 https://github.com/srwi/EverythingToolbar 辅助使用"
        else:
            content = nickname

        html, full_urls = self._render_nickname_html(content)
        self._nickname_label.setText(f"{self._NICKNAME_PREFIX}{html}")

        # tooltip 显示完整 URL（如果有）
        if full_urls:
            tooltip_lines = ["双击修改"]
            for url in full_urls:
                tooltip_lines.append(f"链接：{url}")
            self._nickname_label.setToolTip("\n".join(tooltip_lines))
        else:
            self._nickname_label.setToolTip("双击修改")

    def _render_nickname_html(self, text: str) -> tuple[str, list[str]]:
        """把文本中的 URL 部分包装为 <a> 标签。

        Returns:
            (html_text, [完整URL列表])
        """
        # URL 匹配正则：http/https + 非空白字符
        url_pattern = re.compile(r"(https?://[^\s]+)")

        full_urls = []
        parts = []
        last_end = 0

        for match in url_pattern.finditer(text):
            # 添加 URL 之前的普通文字
            if match.start() > last_end:
                plain = text[last_end:match.start()]
                # HTML 转义
                plain = plain.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                parts.append(plain)

            full_url = match.group(1)
            full_urls.append(full_url)

            # 根据配置决定显示文本
            display_text = self._format_url_display(full_url)
            display_text = display_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            # 包装成 <a> 标签，指定颜色
            parts.append(
                f'<a href="{full_url}" style="color:#185FA5;">{display_text}</a>'
            )
            last_end = match.end()

        # 添加最后剩余的文字
        if last_end < len(text):
            plain = text[last_end:]
            plain = plain.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            parts.append(plain)

        return "".join(parts), full_urls

    def _format_url_display(self, url: str) -> str:
        """根据配置格式化 URL 显示文本。"""
        if self._URL_DISPLAY_MODE == "domain":
            # 只显示域名
            try:
                parsed = urlparse(url)
                domain = parsed.netloc
                # 去掉 www. 前缀让显示更简洁
                if domain.startswith("www."):
                    domain = domain[4:]
                return domain or url
            except Exception:
                return url
        elif self._URL_DISPLAY_MODE == "truncate":
            return url if len(url) <= 30 else url[:27] + "..."
        else:  # "full"
            return url

    def _on_nickname_edit(self) -> None:
        """双击参数：先输入密码，验证通过后才能编辑。"""
        # 第一步：输密码
        password, ok = QInputDialog.getText(
            self,
            "请输入密码",
            "修改参数需要输入密码：",
            QLineEdit.EchoMode.Password,
        )
        if not ok or not password:
            return

        # 验证密码
        password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
        if password_hash != self._NICKNAME_PASSWORD_HASH:
            QMessageBox.warning(self, "密码错误", "密码不正确，无法修改参数。")
            return

        # 第二步：输新参数
        current = config.get_user_nickname()
        new_nickname, ok = QInputDialog.getText(
            self,
            "修改参数",
            "请输入新参数（可输入网址作为超链接）：",
            QLineEdit.EchoMode.Normal,
            current,
        )
        if not ok:
            return

        new_nickname = new_nickname.strip()
        if config.set_user_nickname(new_nickname):
            self._refresh_nickname()
            logger.info(f"默认参数已更新为：{new_nickname}")

    def _on_open_settings(self) -> None:
        """打开全局设置对话框。"""
        from geekclock.dialogs.settings import SettingsDialog
        dialog = SettingsDialog(parent=self)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted:
            self.config_changed.emit()  # 触发调度器重载
            self._refresh()

    def _refresh_keep_alive_icon(self) -> None:
        """更新保活图标的状态色。"""
        ka = config.get_keep_alive_settings()
        enabled = ka["enabled"]
        color = "#1D9E75" if enabled else "#aaa"
        self._keep_alive_btn.setStyleSheet(
            f"QPushButton {{ border: none; background: transparent; "
            f"font-size: 14px; color: {color}; }}"
            f"QPushButton:hover {{ background: #f0f0f0; border-radius: 4px; }}"
        )

    def _on_keep_alive_btn_clicked(self) -> None:
        """点击保活图标打开设置弹窗。"""
        from geekclock.dialogs.keep_alive_settings import KeepAliveSettingsDialog
        dialog = KeepAliveSettingsDialog(parent=self)
        if dialog.exec() == KeepAliveSettingsDialog.DialogCode.Accepted:
            self._refresh_keep_alive_icon()
            self.keep_alive_toggled.emit()

    def eventFilter(self, watched, event):
        """捕获参数标签双击。"""
        from PySide6.QtCore import QEvent
        if watched is self._nickname_label and event.type() == QEvent.Type.MouseButtonDblClick:
            self._on_nickname_edit()
            return True
        return super().eventFilter(watched, event)

