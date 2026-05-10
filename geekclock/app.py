import logging
import signal
import sys
from datetime import datetime

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from geekclock.core import config
from geekclock.core.audio_player import AudioPlayer
from geekclock.core.scheduler import AlarmScheduler, SchedulerWithSnooze
from geekclock.dialogs.edit_alarm import EditAlarmDialog
from geekclock.dialogs.notification import NotificationManager
from geekclock.dialogs.settings import SettingsDialog
from geekclock.floating_clock.floating_clock import FloatingClockManager
from geekclock.main_window.window import MainWindow
from geekclock.system.autostart import is_autostart_enabled, set_autostart
from geekclock.system.logging_setup import (
    setup_global_exception_handler,
    setup_logging,
)
from geekclock.system.single_instance import SingleInstance
from geekclock.timer.widget import TimerManager
from geekclock.tray.tray import TrayIcon

log_file_path = setup_logging()
logger = logging.getLogger("main")
logger.info(f"日志文件位置：{log_file_path}")


def make_handler(audio_player: AudioPlayer, notif_manager: NotificationManager):
    def handler(alarm: dict) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{now}] 闹钟触发 → {alarm['name']}")

        audio_path = alarm.get("audio")
        if audio_path:
            audio_player.play(
                path=audio_path,
                volume=alarm.get("audio_volume", 0.6),
                fade_in=alarm.get("fade_in", True),
                max_duration=alarm.get("max_duration", 0),
                repeat_count=alarm.get("repeat_count", 1),
            )

        notif_manager.show(alarm)
    return handler


def start_keep_alive(scheduler: AlarmScheduler, audio_player: AudioPlayer) -> None:
    settings = config.get_keep_alive_settings()

    def keep_alive_callback() -> None:
        now = datetime.now().time()
        raw_from = settings.get("active_from", "08:00")
        raw_to = settings.get("active_to", "22:00")

        def _parse(s: str):
            h, m = s.split(":")
            return datetime.strptime(f"{h}:{m}", "%H:%M").time()

        try:
            from_time = _parse(raw_from)
            to_time = _parse(raw_to)
        except (ValueError, AttributeError):
            from_time = _parse("00:00")
            to_time = _parse("23:59")

        if from_time <= to_time:
            if not (from_time <= now <= to_time):
                return
        else:
            if not (now >= from_time or now <= to_time):
                return

        audio_player.play(
            path="sounds/bell1.mp3",
            volume=settings["volume"],
            fade_in=False,
            max_duration=1,
            repeat_count=1,
        )

    scheduler.setup_keep_alive(
        enabled=settings["enabled"],
        interval_minutes=settings["interval_minutes"],
        callback=keep_alive_callback,
    )


def sync_autostart_state() -> None:
    cfg_enabled = config.get_global_settings().get("autostart", False)
    reg_enabled = is_autostart_enabled()
    if cfg_enabled != reg_enabled:
        logger.info(f"开机自启状态同步：配置={cfg_enabled}, 注册表={reg_enabled}")
        set_autostart(cfg_enabled)


def main() -> int:
    logger.info("=" * 50)
    logger.info("闹钟程序启动")
    setup_global_exception_handler()
    logger.info("=" * 50)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    instance = SingleInstance()
    if instance.is_already_running():
        logger.warning("GeekClock 已在运行，通知它显示主窗口后退出")
        instance.notify_first_instance("show")
        return 0

    if not instance.start_listening():
        logger.error("单实例锁启动失败，仍继续运行")

    sync_autostart_state()

    audio_player = AudioPlayer()
    notif_manager = NotificationManager()

    scheduler = AlarmScheduler(
        on_trigger=make_handler(audio_player, notif_manager)
    )
    snooze_helper = SchedulerWithSnooze(scheduler)

    def on_snooze(alarm: dict, target_time) -> None:
        audio_player.stop()
        snooze_helper.add_snooze(alarm, target_time)

    notif_manager.snooze_until_requested.connect(on_snooze)

    scheduler.start()
    start_keep_alive(scheduler, audio_player)

    main_window = MainWindow(audio_player=audio_player, scheduler=scheduler)
    main_window.set_close_to_tray(True)

    tray = TrayIcon()
    if not tray.is_available:
        logger.warning("系统不支持托盘，关闭主窗口将直接退出程序")
        main_window.set_close_to_tray(False)
        app.setQuitOnLastWindowClosed(True)

    floating_clock = FloatingClockManager(scheduler=scheduler)
    timer_manager = TimerManager(audio_player=audio_player)

    def on_config_changed():
        scheduler.reload()
        start_keep_alive(scheduler, audio_player)
        if tray.is_available:
            tray.refresh_menu_state()

    main_window.config_changed.connect(on_config_changed)

    def on_keep_alive_toggled():
        start_keep_alive(scheduler, audio_player)
        if tray.is_available:
            tray.refresh_menu_state()

    main_window.keep_alive_toggled.connect(on_keep_alive_toggled)

    def show_main_window():
        main_window.show()
        main_window.raise_()
        main_window.activateWindow()

    tray.show_main_window_requested.connect(show_main_window)
    instance.show_main_window_requested.connect(show_main_window)

    def open_settings():
        dialog = SettingsDialog(parent=main_window if main_window.isVisible() else None)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted:
            on_config_changed()
            if main_window.isVisible():
                main_window._refresh()

    tray.open_settings_requested.connect(open_settings)

    def on_new_alarm_from_tray():
        dialog = EditAlarmDialog(audio_player=audio_player)
        if dialog.exec() == EditAlarmDialog.DialogCode.Accepted:
            new_alarm = dialog.get_alarm()
            if config.add_alarm(new_alarm):
                on_config_changed()
                if main_window.isVisible():
                    main_window._refresh()

    tray.new_alarm_requested.connect(on_new_alarm_from_tray)

    def pause_all():
        config.set_all_alarms_enabled(False)
        on_config_changed()
        if main_window.isVisible():
            main_window._refresh()

    def resume_all():
        config.set_all_alarms_enabled(True)
        on_config_changed()
        if main_window.isVisible():
            main_window._refresh()

    tray.pause_all_requested.connect(pause_all)
    tray.resume_all_requested.connect(resume_all)

    def toggle_clock():
        floating_clock.toggle()

    tray.toggle_floating_clock_requested.connect(toggle_clock)

    def unlock_clock_from_tray():
        if floating_clock.is_visible and floating_clock._clock:
            floating_clock._clock._toggle_lock()
            tray.set_floating_clock_locked(False)

    tray.unlock_floating_clock_requested.connect(unlock_clock_from_tray)
    floating_clock.show_main_window_requested.connect(show_main_window)
    floating_clock.lock_changed.connect(tray.set_floating_clock_locked)
    floating_clock.visibility_changed.connect(tray.set_floating_clock_visible)

    def toggle_timer():
        timer_manager.toggle()

    tray.toggle_timer_requested.connect(toggle_timer)

    def toggle_keep_alive():
        current = config.get_keep_alive_settings()
        new_enabled = not current["enabled"]
        config.update_keep_alive_settings({"enabled": new_enabled})
        start_keep_alive(scheduler, audio_player)
        if tray.is_available:
            tray.set_keep_alive_enabled(new_enabled)

    tray.toggle_keep_alive_requested.connect(toggle_keep_alive)

    timer_manager.countdown_finished.connect(notif_manager.show)
    timer_manager.visibility_changed.connect(tray.set_timer_visible)

    _hint_shown = False

    def on_closed_to_tray():
        nonlocal _hint_shown
        if not _hint_shown and tray.is_available:
            tray.show_message(
                "GeekClock 仍在运行",
                "程序已最小化到托盘，闹钟会继续工作。\n双击托盘图标可重新打开窗口。",
            )
            _hint_shown = True

    main_window.closed_to_tray.connect(on_closed_to_tray)

    if tray.is_available:
        tray.show()
        ka = config.get_keep_alive_settings()
        tray.set_keep_alive_enabled(ka["enabled"])

    is_minimized_start = "--minimized" in sys.argv

    if not is_minimized_start:
        main_window.show()

    if config.get_floating_clock_settings()["enabled"]:
        floating_clock.show()
        tray.set_floating_clock_visible(True)

    if config.get_timer_settings()["enabled"]:
        timer_manager.show()
        tray.set_timer_visible(True)

    def shutdown(*args):
        if args and isinstance(args[0], int):
            try:
                sig_name = signal.Signals(args[0]).name
            except (ValueError, AttributeError):
                sig_name = str(args[0])
            logger.info(f"收到系统信号 {sig_name}，正在关闭...")
        else:
            logger.info("收到退出信号（来自托盘/UI），正在关闭...")
        scheduler.stop()
        audio_player.stop()
        floating_clock.hide()
        timer_manager.hide()
        if tray.is_available:
            tray.hide()
        instance.cleanup()
        app.quit()

    tray.quit_requested.connect(shutdown)

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)

    keepalive_timer = QTimer()
    keepalive_timer.timeout.connect(lambda: None)
    keepalive_timer.start(200)

    logger.info("程序已启动")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
