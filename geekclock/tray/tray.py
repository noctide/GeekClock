"""系统托盘模块。

托盘图标常驻，提供右键菜单快速操作闹钟。
关闭主窗口后程序不退出，通过托盘菜单"退出"才真正结束。
"""
import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon

from geekclock.core import config
from geekclock.system.resources import project_root

logger = logging.getLogger(__name__)


class TrayIcon(QObject):
    """系统托盘图标管理器。

    信号：
    - show_main_window_requested: 用户想打开主窗口
    - new_alarm_requested: 用户想新建闹钟
    - pause_all_requested: 用户想暂停所有闹钟
    - resume_all_requested: 用户想恢复所有闹钟
    - quit_requested: 用户想退出程序
    """

    show_main_window_requested = Signal()
    new_alarm_requested = Signal()
    pause_all_requested = Signal()
    resume_all_requested = Signal()
    quit_requested = Signal()
    toggle_floating_clock_requested = Signal()
    unlock_floating_clock_requested = Signal()
    toggle_timer_requested = Signal()
    toggle_keep_alive_requested = Signal()
    open_settings_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tray = None
        self._clock_action = None
        self._unlock_action = None
        self._timer_action = None
        self._keep_alive_action = None

        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("当前系统不支持系统托盘，托盘功能将不可用")
            return

        self._tray = QSystemTrayIcon()
        self._setup_icon()
        self._setup_menu()
        self._tray.activated.connect(self._on_activated)

    def _setup_icon(self) -> None:
        """设置托盘图标。

        优先使用项目根目录的 icon.ico；找不到则用 Qt 内置图标。
        """
        icon_path = project_root() / "icon.ico"
        if icon_path.exists():
            self._tray.setIcon(QIcon(str(icon_path)))
            logger.info(f"使用自定义图标：{icon_path}")
        else:
            # Qt 自带的标准图标作为兜底
            style = QApplication.instance().style()
            self._tray.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation))
            logger.info("使用 Qt 内置图标（项目根目录可放 icon.ico 自定义）")

        self._update_tooltip()

    def _setup_menu(self) -> None:
        """构建右键菜单。"""
        menu = QMenu()

        # 显示主窗口
        show_action = QAction("显示主窗口", menu)
        show_action.triggered.connect(self.show_main_window_requested.emit)
        menu.addAction(show_action)

        # 设置
        settings_action = QAction("设置…", menu)
        settings_action.triggered.connect(self.open_settings_requested.emit)
        menu.addAction(settings_action)

        # 新建闹钟
        new_action = QAction("新建闹钟", menu)
        new_action.triggered.connect(self.new_alarm_requested.emit)
        menu.addAction(new_action)

        menu.addSeparator()

        # 暂停所有 / 恢复所有
        self._pause_action = QAction("全部暂停", menu)
        self._pause_action.triggered.connect(self.pause_all_requested.emit)
        menu.addAction(self._pause_action)

        self._resume_action = QAction("全部启用", menu)
        self._resume_action.triggered.connect(self.resume_all_requested.emit)
        menu.addAction(self._resume_action)

        # 悬浮时钟切换
        self._clock_action = QAction("显示桌面时钟", menu)
        self._clock_action.triggered.connect(self.toggle_floating_clock_requested.emit)
        menu.addAction(self._clock_action)

        # 解锁悬浮时钟（穿透状态下右键无法触发，所以放托盘菜单）
        self._unlock_action = QAction("解锁悬浮时钟", menu)
        self._unlock_action.triggered.connect(self.unlock_floating_clock_requested.emit)
        self._unlock_action.setVisible(False)  # 默认隐藏，仅在锁定时显示
        menu.addAction(self._unlock_action)

        # 计时器切换
        self._timer_action = QAction("显示倒计时", menu)
        self._timer_action.triggered.connect(self.toggle_timer_requested.emit)
        menu.addAction(self._timer_action)

        # 音响保活切换
        self._keep_alive_action = QAction("启用音响保活", menu)
        self._keep_alive_action.triggered.connect(self.toggle_keep_alive_requested.emit)
        menu.addAction(self._keep_alive_action)

        menu.addSeparator()

        # 退出
        quit_action = QAction("退出 GeekClock", menu)
        quit_action.triggered.connect(self.quit_requested.emit)
        menu.addAction(quit_action)

        self._menu = menu
        self._tray.setContextMenu(menu)

        # 初始化菜单状态
        self.refresh_menu_state()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """托盘图标被点击。"""
        # 双击：打开主窗口
        # Trigger（左键单击）：在 Windows 上也打开主窗口（更直观）
        if reason in (
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.Trigger,
        ):
            self.show_main_window_requested.emit()

    def refresh_menu_state(self) -> None:
        """根据当前闹钟状态更新菜单和提示。

        在每次配置变更后调用。
        """
        alarms = config.get_alarms()
        any_enabled = any(a.get("enabled") for a in alarms)
        all_disabled = not any_enabled

        # 暂停/恢复菜单项的可用性
        self._pause_action.setEnabled(any_enabled)
        self._resume_action.setEnabled(all_disabled and len(alarms) > 0)

        # 音响保活状态
        ka = config.get_keep_alive_settings()
        self.set_keep_alive_enabled(ka["enabled"])

        self._update_tooltip()

    def _update_tooltip(self) -> None:
        """更新托盘工具提示。"""
        alarms = config.get_alarms()
        enabled = sum(1 for a in alarms if a.get("enabled"))
        total = len(alarms)

        if total == 0:
            tip = "GeekClock\n暂无闹钟"
        elif enabled == 0:
            tip = f"GeekClock\n所有闹钟已暂停（共 {total} 个）"
        else:
            tip = f"GeekClock\n{enabled} / {total} 个闹钟已启用"

        if self._tray:
            self._tray.setToolTip(tip)

    def show(self) -> None:
        """显示托盘图标。"""
        if self._tray:
            self._tray.show()

    def hide(self) -> None:
        """隐藏托盘图标。"""
        if self._tray:
            self._tray.hide()

    def show_message(
        self,
        title: str,
        message: str,
        duration_ms: int = 3000,
    ) -> None:
        """通过托盘弹出一个气泡通知（系统级，与悬浮通知不同）。

        用于"程序已最小化到托盘"等系统级提示。
        """
        if self._tray:
            self._tray.showMessage(
                title, message,
                QSystemTrayIcon.MessageIcon.Information,
                duration_ms,
            )

    @property
    def is_available(self) -> bool:
        """系统是否支持托盘。"""
        return self._tray is not None

    def set_floating_clock_visible(self, visible: bool) -> None:
        if self._clock_action is not None:
            self._clock_action.setText(
                "隐藏桌面时钟" if visible else "显示桌面时钟"
            )

    def set_floating_clock_locked(self, locked: bool) -> None:
        if self._unlock_action is not None:
            self._unlock_action.setVisible(locked)

    def set_timer_visible(self, visible: bool) -> None:
        if self._timer_action is not None:
            self._timer_action.setText(
                "隐藏倒计时" if visible else "显示倒计时"
            )

    def set_keep_alive_enabled(self, enabled: bool) -> None:
        if self._keep_alive_action is not None:
            self._keep_alive_action.setText(
                "禁用音响保活" if enabled else "启用音响保活"
            )
