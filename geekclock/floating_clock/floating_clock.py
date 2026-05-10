import logging
import sys
from datetime import datetime

from PySide6.QtCore import (
    QObject,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QAction, QColor, QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QVBoxLayout,
    QWidgetAction,
)

from geekclock.common import OpacitySliderWidget
from geekclock.core import config

logger = logging.getLogger(__name__)


CLOCK_STYLE = """
    #floatingFrame {
        background: white;
        border: 1px solid #ddd;
        border-radius: 12px;
    }
    QLabel {
        color: #333;
        background: transparent;
    }
    QLabel#timeLabel {
        font-size: 28px;
        font-weight: 500;
        letter-spacing: 1px;
    }
    QLabel#secLabel {
        font-size: 14px;
        font-weight: 400;
        color: #888;
        padding-bottom: 4px;
    }
    QLabel#dateLabel {
        font-size: 12px;
        color: #888;
    }
    QLabel#nextLabel {
        font-size: 11px;
        color: #888;
    }
    QLabel#dotLabel {
        color: #1D9E75;
        font-size: 14px;
    }
"""


ICON_STYLE = """
    #floatingFrame {
        background: white;
        border: 1px solid #ddd;
        border-radius: 28px;
    }
    QLabel {
        color: #333;
        background: transparent;
    }
    QLabel#iconLabel {
        font-size: 24px;
    }
    QLabel#badgeLabel {
        background: #1D9E75;
        color: white;
        font-size: 10px;
        font-weight: 500;
        border-radius: 9px;
        padding: 2px;
    }
"""


def add_text_shadow(label: QLabel, blur_radius: int = 4) -> QGraphicsDropShadowEffect:
    effect = QGraphicsDropShadowEffect()
    effect.setBlurRadius(blur_radius)
    effect.setOffset(0, 0)
    effect.setColor(QColor(255, 255, 255, 200))
    label.setGraphicsEffect(effect)
    return effect


class FloatingClock(QFrame):
    mode_change_requested = Signal(str)
    show_main_window_requested = Signal()
    hide_requested = Signal()
    lock_changed = Signal(bool)

    def __init__(self, scheduler=None, parent=None):
        super().__init__(parent)
        self._scheduler = scheduler
        self._settings = config.get_floating_clock_settings()
        self._mode = self._settings["mode"]
        self._drag_offset = None
        self._shadows = []

        self._setup_window()
        self._build_for_mode(self._mode)
        self._setup_timer()
        self._restore_position()

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowOpacity(max(0.05, self._settings["opacity"]))

    def _build_for_mode(self, mode: str) -> None:
        if self.layout() is not None:
            old_layout = self.layout()
            while old_layout.count():
                item = old_layout.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
            old_layout.setParent(None)

        self._mode = mode
        self._shadows.clear()

        if mode == "icon":
            self._build_icon_mode()
        else:
            self._build_clock_mode()

    def _build_clock_mode(self) -> None:
        self.setObjectName("floatingFrame")
        self.setStyleSheet(CLOCK_STYLE)
        self.setFixedSize(180, 110)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 12)
        layout.setSpacing(2)

        time_row = QHBoxLayout()
        time_row.setSpacing(2)
        time_row.setContentsMargins(0, 0, 0, 0)
        time_row.addStretch()

        self._time_label = QLabel("00:00")
        self._time_label.setObjectName("timeLabel")
        self._time_label.setAlignment(
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight
        )
        time_row.addWidget(self._time_label)

        self._sec_label = QLabel(":00")
        self._sec_label.setObjectName("secLabel")
        self._sec_label.setAlignment(
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft
        )
        time_row.addWidget(self._sec_label)
        time_row.addStretch()

        layout.addLayout(time_row)

        self._date_label = QLabel("")
        self._date_label.setObjectName("dateLabel")
        self._date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._date_label)

        layout.addSpacing(2)

        next_row = QHBoxLayout()
        next_row.setSpacing(4)
        next_row.setContentsMargins(0, 0, 0, 0)
        next_row.addStretch()

        dot = QLabel("●")
        dot.setObjectName("dotLabel")
        next_row.addWidget(dot)

        self._next_label = QLabel("无闹钟")
        self._next_label.setObjectName("nextLabel")
        next_row.addWidget(self._next_label)
        next_row.addStretch()

        layout.addLayout(next_row)

        self._shadows = [
            add_text_shadow(self._time_label, 6),
            add_text_shadow(self._sec_label, 4),
            add_text_shadow(self._date_label, 4),
            add_text_shadow(self._next_label, 4),
        ]
        self._update_shadow_strength()

    def _build_icon_mode(self) -> None:
        self.setObjectName("floatingFrame")
        self.setStyleSheet(ICON_STYLE)
        self.setFixedSize(56, 56)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        icon = QLabel("⏰")
        icon.setObjectName("iconLabel")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        self._badge_label = QLabel(self)
        self._badge_label.setObjectName("badgeLabel")
        self._badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge_label.setFixedSize(18, 18)
        self._badge_label.move(36, 2)
        self._badge_label.raise_()

    def _update_shadow_strength(self) -> None:
        opacity = self._settings["opacity"]
        shadow_strength = int((1.0 - opacity) * 255)
        for effect in self._shadows:
            if effect:
                effect.setColor(QColor(255, 255, 255, shadow_strength))

    def _setup_timer(self) -> None:
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._refresh_display)
        self._timer.start()
        self._refresh_display()

    def _refresh_display(self) -> None:
        now = datetime.now()

        if self._mode == "clock":
            if hasattr(self, "_time_label"):
                self._time_label.setText(now.strftime("%H:%M"))
            if hasattr(self, "_sec_label"):
                self._sec_label.setText(now.strftime(":%S"))
            if hasattr(self, "_date_label"):
                weekday = ["一", "二", "三", "四", "五", "六", "日"][now.weekday()]
                self._date_label.setText(
                    f"{now.month} 月 {now.day} 日 周{weekday}"
                )
            if hasattr(self, "_next_label"):
                next_text = self._get_next_alarm_text()
                self._next_label.setText(next_text)
        elif self._mode == "icon":
            if hasattr(self, "_badge_label"):
                count = sum(1 for a in config.get_alarms() if a.get("enabled"))
                if count > 0:
                    self._badge_label.setText(str(count))
                    self._badge_label.show()
                else:
                    self._badge_label.hide()

    def _get_next_alarm_text(self) -> str:
        if not self._scheduler:
            return "无闹钟"

        enabled = [a for a in config.get_alarms() if a.get("enabled")]
        if not enabled:
            return "已暂停"

        nearest_alarm = None
        nearest_time = None
        for alarm in enabled:
            t = self._scheduler.get_next_run_time(alarm["id"])
            if t is None:
                continue
            if nearest_time is None or t < nearest_time:
                nearest_time = t
                nearest_alarm = alarm

        if not nearest_alarm:
            return "已暂停"

        time_str = nearest_time.strftime("%H:%M")
        name = nearest_alarm["name"]
        if len(name) > 6:
            name = name[:5] + "…"
        return f"下次 {time_str} {name}"

    def _restore_position(self) -> None:
        pos = self._settings["position"]
        if pos and pos[0] is not None and pos[1] is not None:
            self.move(pos[0], pos[1])
        else:
            screen = QGuiApplication.primaryScreen()
            if screen:
                geom = screen.availableGeometry()
                x = geom.right() - self.width() - 30
                y = geom.top() + 60
                self.move(x, y)

    def _save_position(self) -> None:
        config.update_floating_clock_settings({
            "position": [self.x(), self.y()],
        })

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._settings["locked"]:
                self._drag_offset = (
                    event.globalPosition().toPoint() - self.pos()
                )
                event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if (
            self._drag_offset is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            new_pos = event.globalPosition().toPoint() - self._drag_offset
            self.move(new_pos)
            event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._drag_offset is not None:
            self._drag_offset = None
            self._save_position()
            event.accept()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.show_main_window_requested.emit()
            event.accept()
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)

        show_main = QAction("显示主窗口", menu)
        show_main.triggered.connect(self.show_main_window_requested.emit)
        menu.addAction(show_main)

        menu.addSeparator()

        if self._mode == "clock":
            switch_action = QAction("切换为小图标", menu)
            switch_action.triggered.connect(lambda: self._switch_mode("icon"))
        else:
            switch_action = QAction("切换为时钟", menu)
            switch_action.triggered.connect(lambda: self._switch_mode("clock"))
        menu.addAction(switch_action)

        opacity_widget = OpacitySliderWidget(self._settings["opacity"])
        opacity_widget.value_changed.connect(self._set_opacity)
        opacity_action = QWidgetAction(menu)
        opacity_action.setDefaultWidget(opacity_widget)
        menu.addAction(opacity_action)

        lock_action = QAction(
            "解锁位置" if self._settings["locked"] else "锁定位置",
            menu,
        )
        lock_action.triggered.connect(self._toggle_lock)
        menu.addAction(lock_action)

        menu.addSeparator()

        hide_action = QAction("隐藏悬浮时钟", menu)
        hide_action.triggered.connect(self.hide_requested.emit)
        menu.addAction(hide_action)

        menu.exec(event.globalPos())

    def _switch_mode(self, new_mode: str) -> None:
        if new_mode == self._mode:
            return
        config.update_floating_clock_settings({"mode": new_mode})
        self._settings["mode"] = new_mode
        self._build_for_mode(new_mode)
        self._restore_position()
        self._refresh_display()

    def _set_opacity(self, value: float) -> None:
        self._settings["opacity"] = value
        actual_opacity = max(0.05, value)
        self.setWindowOpacity(actual_opacity)
        self._update_shadow_strength()
        config.update_floating_clock_settings({"opacity": value})

    def _toggle_lock(self) -> None:
        new_locked = not self._settings["locked"]
        self._settings["locked"] = new_locked
        config.update_floating_clock_settings({"locked": new_locked})

        self._apply_click_through(new_locked)
        self.lock_changed.emit(new_locked)

    def _apply_click_through(self, enabled: bool) -> None:
        was_visible = self.isVisible()
        logger.info(f"应用穿透点击: enabled={enabled}, visible={was_visible}")

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, enabled)

        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes

                hwnd = int(self.winId())

                GWL_EXSTYLE = -20
                WS_EX_TRANSPARENT = 0x00000020
                WS_EX_LAYERED = 0x00080000

                user32 = ctypes.windll.user32
                user32.GetWindowLongW.restype = ctypes.c_long
                user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
                user32.SetWindowLongW.restype = ctypes.c_long
                user32.SetWindowLongW.argtypes = [
                    wintypes.HWND,
                    ctypes.c_int,
                    ctypes.c_long,
                ]

                ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                if enabled:
                    ex_style |= WS_EX_TRANSPARENT | WS_EX_LAYERED
                else:
                    ex_style &= ~WS_EX_TRANSPARENT

                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
            except Exception as e:
                logger.error(f"设置 Win32 穿透失败: {e}")

        if was_visible:
            self.hide()
            self.show()

    def reload_settings(self) -> None:
        self._settings = config.get_floating_clock_settings()
        self.setWindowOpacity(max(0.05, self._settings["opacity"]))
        self._update_shadow_strength()


class FloatingClockManager(QObject):
    show_main_window_requested = Signal()
    lock_changed = Signal(bool)
    visibility_changed = Signal(bool)

    def __init__(self, scheduler=None, parent=None):
        super().__init__(parent)
        self._scheduler = scheduler
        self._clock = None

    def show(self) -> None:
        if self._clock is None:
            self._clock = FloatingClock(scheduler=self._scheduler)
            self._clock.show_main_window_requested.connect(
                self.show_main_window_requested.emit
            )
            self._clock.hide_requested.connect(self.hide)
            self._clock.lock_changed.connect(self._on_clock_lock_changed)

        self._clock.show()
        config.update_floating_clock_settings({"enabled": True})

        if self._clock._settings["locked"]:
            self._clock._apply_click_through(True)
            self.lock_changed.emit(True)

        self.visibility_changed.emit(True)

    def _on_clock_lock_changed(self, locked: bool) -> None:
        logger.info(f"悬浮时钟锁定状态变化: locked={locked}")
        self.lock_changed.emit(locked)

    def hide(self) -> None:
        if self._clock is not None:
            self._clock.hide()
        config.update_floating_clock_settings({"enabled": False})
        self.visibility_changed.emit(False)

    def toggle(self) -> None:
        if self._clock is not None and self._clock.isVisible():
            self.hide()
        else:
            self.show()

    @property
    def is_visible(self) -> bool:
        return self._clock is not None and self._clock.isVisible()
