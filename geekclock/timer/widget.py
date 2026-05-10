import logging
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
    QWidgetAction,
)

from geekclock.common import OpacitySliderWidget
from geekclock.core import config
from geekclock.timer.settings_dialog import TimerSettingsDialog

logger = logging.getLogger(__name__)


TIMER_STYLE = """
    #timerFrame {
        background: white;
        border: 1px solid #ddd;
        border-radius: 10px;
    }
    QLabel {
        color: #333;
        background: transparent;
    }
    QLabel#displayLabel {
        font-size: 22px;
        font-weight: 500;
        letter-spacing: 1px;
    }
    QLabel#displayLabel[state="running"] {
        color: #185FA5;
    }
    QLabel#displayLabel[state="paused"] {
        color: #999;
    }
    QLabel#displayLabel[state="finished"] {
        color: #E24B4A;
    }
    QLabel#modeLabel {
        font-size: 9px;
        color: #aaa;
    }
"""


class TimerWidget(QFrame):
    countdown_finished = Signal()
    hide_requested = Signal()
    settings_changed = Signal()

    def __init__(self, audio_player=None, parent=None):
        super().__init__(parent)
        self._audio_player = audio_player
        self._settings = config.get_timer_settings()

        self._mode = self._settings["mode"]
        self._is_running = False
        self._start_time = None
        self._accumulated_secs = 0
        self._countdown_total = self._settings["countdown_seconds"]
        self._drag_offset = None

        self._setup_window()
        self._setup_ui()
        self._setup_timer()
        self._restore_position()
        self._refresh_display()

    def _setup_window(self) -> None:
        flags = (
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        if self._settings["always_on_top"]:
            flags |= Qt.WindowType.WindowStaysOnTopHint

        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowOpacity(max(0.05, self._settings["opacity"]))

    def _setup_ui(self) -> None:
        self.setObjectName("timerFrame")
        self.setStyleSheet(TIMER_STYLE)
        self.setFixedSize(180, 55)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 14, 6)
        layout.setSpacing(8)

        self._display_label = QLabel("00:00")
        self._display_label.setObjectName("displayLabel")
        self._display_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._display_label, 1)

        self._mode_label = QLabel("")
        self._mode_label.setObjectName("modeLabel")
        self._mode_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        self._mode_label.setFixedWidth(28)
        layout.addWidget(self._mode_label)

        self._display_shadow = QGraphicsDropShadowEffect()
        self._display_shadow.setBlurRadius(6)
        self._display_shadow.setOffset(0, 0)
        self._display_shadow.setColor(QColor(255, 255, 255, 0))
        self._display_label.setGraphicsEffect(self._display_shadow)

        self._update_shadow_strength()

    def _setup_timer(self) -> None:
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(100)
        self._refresh_timer.timeout.connect(self._refresh_display)
        self._refresh_timer.start()

    def _update_shadow_strength(self) -> None:
        opacity = self._settings["opacity"]
        strength = int((1.0 - opacity) * 255)
        if hasattr(self, "_display_shadow") and self._display_shadow:
            self._display_shadow.setColor(QColor(255, 255, 255, strength))

    def _refresh_display(self) -> None:
        self._mode_label.setText("倒计时" if self._mode == "countdown" else "秒表")

        if self._mode == "countdown":
            elapsed = self._get_elapsed_seconds()
            remaining = max(0, self._countdown_total - int(elapsed))
            self._display_label.setText(self._format_time(remaining))

            if remaining == 0 and self._is_running:
                self._display_label.setProperty("state", "finished")
                self._on_countdown_finish()
            elif self._is_running:
                self._display_label.setProperty("state", "running")
            else:
                self._display_label.setProperty("state", "paused")
        else:
            elapsed = int(self._get_elapsed_seconds())
            self._display_label.setText(self._format_time(elapsed))
            if self._is_running:
                self._display_label.setProperty("state", "running")
            else:
                self._display_label.setProperty("state", "paused")

        self._display_label.style().unpolish(self._display_label)
        self._display_label.style().polish(self._display_label)

    def _get_elapsed_seconds(self) -> float:
        if self._is_running and self._start_time is not None:
            current = (datetime.now() - self._start_time).total_seconds()
            return self._accumulated_secs + current
        return self._accumulated_secs

    @staticmethod
    def _format_time(total_sec: int) -> str:
        total_sec = max(0, total_sec)
        h, m, s = total_sec // 3600, (total_sec % 3600) // 60, total_sec % 60
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _on_countdown_finish(self) -> None:
        if not self._is_running:
            return
        self._is_running = False
        self._accumulated_secs = self._countdown_total
        self._start_time = None

        audio = self._settings["countdown_audio"]
        if audio and self._audio_player:
            self._audio_player.play(
                path=audio,
                volume=self._settings["countdown_volume"],
                fade_in=True,
                max_duration=20,
            )

        self.countdown_finished.emit()
        logger.info("倒计时结束")

    def _toggle_running(self) -> None:
        if self._is_running:
            self._accumulated_secs = self._get_elapsed_seconds()
            self._start_time = None
            self._is_running = False
            logger.info(f"暂停 ({self._mode})")
        else:
            if self._mode == "countdown" and self._accumulated_secs >= self._countdown_total:
                self._accumulated_secs = 0
            self._start_time = datetime.now()
            self._is_running = True
            logger.info(f"开始 ({self._mode})")

    def _reset(self) -> None:
        self._is_running = False
        self._start_time = None
        self._accumulated_secs = 0
        logger.info(f"重置 ({self._mode})")
        self._refresh_display()

    def _open_settings(self) -> None:
        dialog = TimerSettingsDialog(
            current_seconds=self._countdown_total,
            current_audio=self._settings["countdown_audio"],
            current_volume=self._settings["countdown_volume"],
            audio_player=self._audio_player,
            parent=self,
        )
        if dialog.exec() == TimerSettingsDialog.DialogCode.Accepted:
            new_secs = dialog.get_seconds()
            self._countdown_total = new_secs
            self._settings["countdown_seconds"] = new_secs
            self._settings["countdown_audio"] = dialog.get_audio()
            self._settings["countdown_volume"] = dialog.get_volume()

            config.update_timer_settings({
                "countdown_seconds": new_secs,
                "countdown_audio": dialog.get_audio(),
                "countdown_volume": dialog.get_volume(),
            })

            self._reset()
            self.settings_changed.emit()

    def _switch_mode(self) -> None:
        new_mode = "stopwatch" if self._mode == "countdown" else "countdown"
        self._mode = new_mode
        self._settings["mode"] = new_mode
        config.update_timer_settings({"mode": new_mode})
        self._reset()

    def _toggle_always_on_top(self) -> None:
        new_value = not self._settings["always_on_top"]
        self._settings["always_on_top"] = new_value
        config.update_timer_settings({"always_on_top": new_value})

        flags = (
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        if new_value:
            flags |= Qt.WindowType.WindowStaysOnTopHint

        was_visible = self.isVisible()
        self.setWindowFlags(flags)
        if was_visible:
            self.show()

    def _set_opacity(self, value: float) -> None:
        self._settings["opacity"] = value
        actual = max(0.05, value)
        self.setWindowOpacity(actual)
        self._update_shadow_strength()
        config.update_timer_settings({"opacity": value})

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()
            self._press_pos = event.globalPosition().toPoint()
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
        if event.button() == Qt.MouseButton.LeftButton:
            if hasattr(self, "_press_pos"):
                delta = event.globalPosition().toPoint() - self._press_pos
                if abs(delta.x()) < 3 and abs(delta.y()) < 3:
                    self._toggle_running()
                else:
                    self._save_position()
            self._drag_offset = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._mode == "countdown":
                self._open_settings()
            else:
                self._reset()
            event.accept()
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)

        if self._mode == "countdown":
            mode_action = QAction("切换为秒表", menu)
        else:
            mode_action = QAction("切换为倒计时", menu)
        mode_action.triggered.connect(self._switch_mode)
        menu.addAction(mode_action)

        if self._mode == "countdown":
            settings_action = QAction("倒计时设置…", menu)
            settings_action.triggered.connect(self._open_settings)
            menu.addAction(settings_action)

        reset_action = QAction("重置", menu)
        reset_action.triggered.connect(self._reset)
        menu.addAction(reset_action)

        menu.addSeparator()

        on_top_action = QAction(
            "取消置顶" if self._settings["always_on_top"] else "始终置顶",
            menu,
        )
        on_top_action.triggered.connect(self._toggle_always_on_top)
        menu.addAction(on_top_action)

        opacity_widget = OpacitySliderWidget(self._settings["opacity"])
        opacity_widget.value_changed.connect(self._set_opacity)
        opacity_action = QWidgetAction(menu)
        opacity_action.setDefaultWidget(opacity_widget)
        menu.addAction(opacity_action)

        menu.addSeparator()

        hide_action = QAction("隐藏计时器", menu)
        hide_action.triggered.connect(self.hide_requested.emit)
        menu.addAction(hide_action)

        menu.exec(event.globalPos())

    def _restore_position(self) -> None:
        pos = self._settings["position"]
        if pos and pos[0] is not None and pos[1] is not None:
            self.move(pos[0], pos[1])
        else:
            screen = QGuiApplication.primaryScreen()
            if screen:
                geom = screen.availableGeometry()
                x = geom.right() - self.width() - 30
                y = geom.top() + 180
                self.move(x, y)

    def _save_position(self) -> None:
        config.update_timer_settings({
            "position": [self.x(), self.y()],
        })


class TimerManager(QObject):
    countdown_finished = Signal(dict)
    show_main_window_requested = Signal()
    visibility_changed = Signal(bool)

    def __init__(self, audio_player=None, parent=None):
        super().__init__(parent)
        self._audio_player = audio_player
        self._widget = None

    def show(self) -> None:
        if self._widget is None:
            self._widget = TimerWidget(audio_player=self._audio_player)
            self._widget.hide_requested.connect(self.hide)
            self._widget.countdown_finished.connect(self._on_countdown_finish)
        self._widget.show()
        config.update_timer_settings({"enabled": True})
        self.visibility_changed.emit(True)

    def hide(self) -> None:
        if self._widget is not None:
            self._widget.hide()
        config.update_timer_settings({"enabled": False})
        self.visibility_changed.emit(False)

    def toggle(self) -> None:
        if self._widget is not None and self._widget.isVisible():
            self.hide()
        else:
            self.show()

    def _on_countdown_finish(self) -> None:
        fake_alarm = {
            "id": "_countdown_finished",
            "name": "倒计时结束",
            "message": "您设置的倒计时已结束",
            "snooze_enabled": False,
        }
        self.countdown_finished.emit(fake_alarm)

    @property
    def is_visible(self) -> bool:
        return self._widget is not None and self._widget.isVisible()
