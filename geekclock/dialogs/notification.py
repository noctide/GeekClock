"""非阻塞悬浮通知模块。

设计：
- 通知窗口尺寸固定，永不变化，从根本消除 Windows 渲染残影
- 点击「延后」会弹出独立的 SnoozeDialog 对话框
- 对话框内包含所有延后选项（快捷预设、自定义、特殊时间、具体时间）
"""
import logging
from datetime import datetime, timedelta

from PySide6.QtCore import (
    QDateTime,
    QObject,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QGuiApplication, QIntValidator
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from geekclock.core import config

logger = logging.getLogger(__name__)

NOTIFICATION_WIDTH = 340
NOTIFICATION_HEIGHT = 140

AUTO_CLOSE_DURATION_MS = 8000
PROGRESS_UPDATE_INTERVAL_MS = 50

SCREEN_MARGIN = 20
NOTIFICATION_SPACING = 8


NOTIFICATION_STYLE = """
    #notificationFrame {
        background: white;
        border: 1px solid #ddd;
        border-radius: 8px;
    }
    QLabel {
        color: #333;
        background: transparent;
    }
    QLabel#titleLabel {
        font-size: 14px;
        font-weight: 500;
    }
    QLabel#messageLabel {
        font-size: 13px;
        color: #666;
    }
    QLabel#timeLabel {
        font-size: 11px;
        color: #999;
    }
    QPushButton {
        background: white;
        border: 1px solid #ddd;
        border-radius: 4px;
        padding: 4px 10px;
        font-size: 12px;
        color: #333;
    }
    QPushButton:hover {
        background: #f5f5f5;
    }
    QPushButton#primaryButton {
        background: #185FA5;
        color: white;
        border: 1px solid #185FA5;
    }
    QPushButton#primaryButton:hover {
        background: #0C447C;
    }
    QProgressBar {
        background: #f0f0f0;
        border: none;
        height: 2px;
        border-radius: 1px;
    }
    QProgressBar::chunk {
        background: #185FA5;
        border-radius: 1px;
    }
"""


SNOOZE_DIALOG_STYLE = """
    QDialog {
        background: white;
    }
    QLabel {
        color: #333;
    }
    QLabel#sectionLabel {
        font-size: 12px;
        color: #888;
    }
    QLabel#hintLabel {
        font-size: 11px;
        color: #999;
    }
    QPushButton {
        background: white;
        border: 1px solid #ddd;
        border-radius: 4px;
        padding: 6px 12px;
        font-size: 12px;
        color: #333;
    }
    QPushButton:hover {
        background: #f5f5f5;
    }
    QPushButton#primaryButton {
        background: #185FA5;
        color: white;
        border: 1px solid #185FA5;
    }
    QPushButton#primaryButton:hover {
        background: #0C447C;
    }
    QPushButton#presetButton {
        padding: 10px 4px;
    }
    QPushButton#stepButton {
        padding: 0;
        min-width: 24px;
        max-width: 24px;
        font-size: 14px;
        font-weight: 500;
    }
    QPushButton#listItemButton {
        text-align: left;
        padding: 8px 4px;
        border: none;
        background: transparent;
    }
    QPushButton#listItemButton:hover {
        background: #f5f5f5;
        border-radius: 4px;
    }
    QLineEdit, QComboBox, QDateTimeEdit {
        border: 1px solid #ddd;
        border-radius: 4px;
        padding: 4px 6px;
        font-size: 12px;
        background: white;
        color: #333;
    }
    QLineEdit:focus, QComboBox:focus {
        border: 1px solid #185FA5;
    }
    QFrame#sepLine {
        background: #eee;
        max-height: 1px;
    }
"""


class SnoozeDialog(QDialog):
    """延后选项对话框。

    包含：快捷预设、自定义时长、特殊时间、具体时间选择。
    用户选择后通过 result_time 属性返回 datetime 对象。
    """

    def __init__(self, alarm_name: str, parent=None):
        super().__init__(parent)
        self._notif_settings = config.get_notification_settings()
        self._result_time: datetime | None = None

        self.setWindowTitle(f"延后 - {alarm_name}")
        self.setModal(True)

        # 关键修复：对话框始终置顶，避免被其他窗口盖住找不到
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        self.setStyleSheet(SNOOZE_DIALOG_STYLE)
        self.setFixedWidth(360)

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # 顶部说明
        section_label = QLabel("延后到")
        section_label.setObjectName("sectionLabel")
        layout.addWidget(section_label)

        # 1. 快捷预设
        presets = self._notif_settings["snooze_presets"][:4]
        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)
        for minutes in presets:
            btn = QPushButton(self._format_minutes(minutes))
            btn.setObjectName("presetButton")
            btn.clicked.connect(
                lambda checked=False, m=minutes: self._snooze_minutes(m)
            )
            preset_row.addWidget(btn)
        layout.addLayout(preset_row)

        # 2. 自定义时长
        custom_row = QHBoxLayout()
        custom_row.setSpacing(4)

        minus_btn = QPushButton("−")
        minus_btn.setObjectName("stepButton")
        minus_btn.clicked.connect(self._decrement_value)
        custom_row.addWidget(minus_btn)

        self._value_input = QLineEdit("2")
        self._value_input.setValidator(QIntValidator(1, 999, self))
        self._value_input.setFixedWidth(50)
        self._value_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        custom_row.addWidget(self._value_input)

        plus_btn = QPushButton("+")
        plus_btn.setObjectName("stepButton")
        plus_btn.clicked.connect(self._increment_value)
        custom_row.addWidget(plus_btn)

        self._custom_unit = QComboBox()
        self._custom_unit.addItems(["分钟后", "小时后"])
        self._custom_unit.setCurrentIndex(1)
        custom_row.addWidget(self._custom_unit, 1)

        custom_ok = QPushButton("确定")
        custom_ok.setObjectName("primaryButton")
        custom_ok.clicked.connect(self._snooze_custom)
        custom_row.addWidget(custom_ok)

        layout.addLayout(custom_row)

        # 分隔线
        line = QFrame()
        line.setObjectName("sepLine")
        line.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(line)

        # 3. 特殊时间选项
        layout.addWidget(self._build_list_item(
            "明天上午",
            self._format_tomorrow_morning(),
            self._snooze_tomorrow_morning,
        ))

        layout.addWidget(self._build_list_item(
            "今天稍后",
            self._format_today_later(),
            self._snooze_today_later,
        ))

        layout.addWidget(self._build_list_item(
            "选择具体时间",
            "›",
            self._snooze_pick_datetime,
        ))

        # 4. 取消按钮
        cancel_row = QHBoxLayout()
        cancel_row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        cancel_row.addWidget(cancel_btn)
        layout.addLayout(cancel_row)

    def _build_list_item(self, label: str, hint: str, on_click) -> QPushButton:
        btn = QPushButton()
        btn.setObjectName("listItemButton")
        item_layout = QHBoxLayout(btn)
        item_layout.setContentsMargins(4, 8, 4, 8)

        label_widget = QLabel(label)
        label_widget.setStyleSheet("font-size: 12px; color: #333; background: transparent;")

        hint_widget = QLabel(hint)
        hint_widget.setObjectName("hintLabel")
        hint_widget.setStyleSheet("background: transparent;")

        item_layout.addWidget(label_widget)
        item_layout.addStretch()
        item_layout.addWidget(hint_widget)

        btn.clicked.connect(on_click)
        return btn

    @staticmethod
    def _format_minutes(minutes: int) -> str:
        if minutes >= 60 and minutes % 60 == 0:
            hours = minutes // 60
            return f"{hours} 小时"
        return f"{minutes} 分钟"

    def _format_tomorrow_morning(self) -> str:
        time_str = self._notif_settings["tomorrow_morning_time"]
        return f"明天 {time_str}"

    def _format_today_later(self) -> str:
        offset = self._notif_settings["today_later_offset_hours"]
        target = datetime.now() + timedelta(hours=offset)
        return f"今天 {target.strftime('%H:%M')}"

    def _get_current_value(self) -> int:
        try:
            v = int(self._value_input.text() or "1")
            return max(1, min(999, v))
        except ValueError:
            return 1

    def _set_current_value(self, value: int) -> None:
        self._value_input.setText(str(max(1, min(999, value))))

    def _increment_value(self) -> None:
        self._set_current_value(self._get_current_value() + 1)

    def _decrement_value(self) -> None:
        self._set_current_value(self._get_current_value() - 1)

    def _snooze_minutes(self, minutes: int) -> None:
        target = datetime.now() + timedelta(minutes=minutes)
        self._result_time = target
        self.accept()

    def _snooze_custom(self) -> None:
        value = self._get_current_value()
        unit_index = self._custom_unit.currentIndex()
        if unit_index == 0:
            target = datetime.now() + timedelta(minutes=value)
        else:
            target = datetime.now() + timedelta(hours=value)
        self._result_time = target
        self.accept()

    def _snooze_tomorrow_morning(self) -> None:
        time_str = self._notif_settings["tomorrow_morning_time"]
        h, m = [int(x) for x in time_str.split(":")]
        tomorrow = datetime.now() + timedelta(days=1)
        target = tomorrow.replace(hour=h, minute=m, second=0, microsecond=0)
        self._result_time = target
        self.accept()

    def _snooze_today_later(self) -> None:
        offset = self._notif_settings["today_later_offset_hours"]
        target = datetime.now() + timedelta(hours=offset)
        self._result_time = target
        self.accept()

    def _snooze_pick_datetime(self) -> None:
        """嵌套打开日期时间选择器。"""
        picker = QDialog(self)
        picker.setWindowTitle("选择延后时间")
        picker.setModal(True)

        picker_layout = QVBoxLayout(picker)
        picker_layout.setContentsMargins(16, 16, 16, 16)

        picker_layout.addWidget(QLabel("延后到："))

        dt_edit = QDateTimeEdit()
        dt_edit.setCalendarPopup(True)
        dt_edit.setDateTime(QDateTime.currentDateTime().addSecs(3600))
        dt_edit.setMinimumDateTime(QDateTime.currentDateTime().addSecs(60))
        dt_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        picker_layout.addWidget(dt_edit)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("取消")
        cancel.clicked.connect(picker.reject)
        ok = QPushButton("确定")
        ok.setObjectName("primaryButton")
        ok.clicked.connect(picker.accept)
        btn_row.addWidget(cancel)
        btn_row.addWidget(ok)
        picker_layout.addLayout(btn_row)

        picker.resize(280, 120)

        if picker.exec() == QDialog.DialogCode.Accepted:
            target = dt_edit.dateTime().toPython()
            if target <= datetime.now():
                logger.warning("选择的延后时间已过，忽略")
                return
            self._result_time = target
            self.accept()

    @property
    def result_time(self) -> datetime | None:
        """对话框关闭后获取选择的时间。None 表示取消。"""
        return self._result_time


class NotificationWidget(QFrame):
    """单个通知 Toast 窗口。

    尺寸固定，永远不变，无任何渲染残影问题。
    """

    snooze_until_requested = Signal(object)
    dismissed = Signal()

    def __init__(self, alarm: dict, parent=None):
        super().__init__(parent)
        self._alarm = alarm
        self._closed = False
        self._remaining_ms = AUTO_CLOSE_DURATION_MS
        self._manager_ref = None

        self._setup_window()
        self._setup_ui()
        self._setup_timers()

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedSize(NOTIFICATION_WIDTH, NOTIFICATION_HEIGHT)

    def _setup_ui(self) -> None:
        self.setObjectName("notificationFrame")
        self.setStyleSheet(NOTIFICATION_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(8)

        # 顶部：标题 + 时间
        header = QHBoxLayout()
        title = QLabel(self._alarm["name"])
        title.setObjectName("titleLabel")
        time_label = QLabel(datetime.now().strftime("%H:%M"))
        time_label.setObjectName("timeLabel")
        time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(time_label)
        layout.addLayout(header)

        # 消息
        message = QLabel(self._alarm.get("message", ""))
        message.setObjectName("messageLabel")
        message.setWordWrap(True)
        layout.addWidget(message)

        layout.addStretch()

        # 按钮行：延后 + 知道了
        button_row = QHBoxLayout()
        button_row.setSpacing(6)

        if self._alarm.get("snooze_enabled", True):
            snooze_btn = QPushButton("延后…")
            snooze_btn.clicked.connect(self._open_snooze_dialog)
            button_row.addWidget(snooze_btn)

        dismiss_btn = QPushButton("知道了")
        dismiss_btn.setObjectName("primaryButton")
        dismiss_btn.clicked.connect(self._on_dismiss)
        button_row.addWidget(dismiss_btn)

        layout.addLayout(button_row)

        # 倒计时进度条
        self._progress = QProgressBar()
        self._progress.setMinimum(0)
        self._progress.setMaximum(AUTO_CLOSE_DURATION_MS)
        self._progress.setValue(AUTO_CLOSE_DURATION_MS)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(2)
        layout.addWidget(self._progress)

    def _setup_timers(self) -> None:
        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setInterval(PROGRESS_UPDATE_INTERVAL_MS)
        self._auto_close_timer.timeout.connect(self._on_progress_tick)
        self._auto_close_timer.start()

    def _open_snooze_dialog(self) -> None:
        """打开延后对话框。"""
        self._auto_close_timer.stop()

        dialog = SnoozeDialog(self._alarm["name"])

        # 屏幕正中央，远离右下角通知
        screen = QGuiApplication.primaryScreen()
        if screen:
            screen_geom = screen.availableGeometry()
            dialog.show()
            dialog_geom = dialog.frameGeometry()
            x = screen_geom.center().x() - dialog_geom.width() // 2
            y = screen_geom.center().y() - dialog_geom.height() // 2
            dialog.move(x, y)
            # 关键修复：主动激活并置前
            dialog.raise_()
            dialog.activateWindow()

        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted and dialog.result_time:
            target = dialog.result_time
            label = target.strftime("%Y-%m-%d %H:%M")
            logger.info(f"延后到 {label}：{self._alarm['name']}")
            self.snooze_until_requested.emit(target)
            self._close_immediately()
        else:
            if not self._closed:
                self._remaining_ms = AUTO_CLOSE_DURATION_MS
                self._progress.setValue(AUTO_CLOSE_DURATION_MS)
                self._auto_close_timer.start()

    def _on_progress_tick(self) -> None:
        self._remaining_ms -= PROGRESS_UPDATE_INTERVAL_MS
        if self._remaining_ms <= 0:
            self._on_dismiss()
            return
        self._progress.setValue(self._remaining_ms)

    def _on_dismiss(self) -> None:
        if self._closed:
            return
        self.dismissed.emit()
        self._close_immediately()

    def _close_immediately(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._auto_close_timer.stop()

        if self._manager_ref:
            self._manager_ref._on_widget_closing(self)

        self.hide()
        self.close()
        self.deleteLater()

    def enterEvent(self, event) -> None:
        self._auto_close_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if not self._closed:
            self._auto_close_timer.start()
        super().leaveEvent(event)

    def show_animated(self) -> None:
        self.show()


class NotificationManager(QObject):
    """通知管理器。"""

    snooze_until_requested = Signal(dict, object)
    _show_requested = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._notifications = []
        self._show_requested.connect(
            self._do_show, Qt.ConnectionType.QueuedConnection
        )

    def show(self, alarm: dict) -> None:
        self._show_requested.emit(alarm)

    def _do_show(self, alarm: dict) -> None:
        widget = NotificationWidget(alarm)
        widget._manager_ref = self

        widget.snooze_until_requested.connect(
            lambda target_time, a=alarm: self.snooze_until_requested.emit(a, target_time)
        )

        self._notifications.append(widget)
        self._reposition_all()
        widget.show_animated()

        logger.info(f"显示通知：{alarm['name']}")

    def _on_widget_closing(self, widget) -> None:
        if widget in self._notifications:
            self._notifications.remove(widget)
            self._reposition_all()

    def _reposition_all(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return
        screen_geom = screen.availableGeometry()

        x = screen_geom.right() - NOTIFICATION_WIDTH - SCREEN_MARGIN
        y_bottom = screen_geom.bottom() - SCREEN_MARGIN

        accumulated_height = 0
        for widget in reversed(self._notifications):
            accumulated_height += widget.height()
            y = y_bottom - accumulated_height
            widget.move(x, y)
            accumulated_height += NOTIFICATION_SPACING
