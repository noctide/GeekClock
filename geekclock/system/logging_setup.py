import logging
import sys
import traceback
from logging.handlers import TimedRotatingFileHandler

from geekclock.system.resources import project_root

logger = logging.getLogger(__name__)


def setup_logging():
    log_dir = project_root() / "logs"
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / "GeekClock.log"

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.suffix = "%y%m%d"
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    return log_file


def setup_global_exception_handler():
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        error_msg = "".join(
            traceback.format_exception(exc_type, exc_value, exc_traceback)
        )
        logger.error("Unhandled exception\n%s", error_msg)

        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            if QApplication.instance():
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Icon.Critical)
                msg.setWindowTitle("GeekClock error")
                msg.setText("The program encountered an unexpected error.")
                msg.setInformativeText(str(exc_value))
                msg.setDetailedText(error_msg)
                msg.exec()
        except Exception:
            pass

    sys.excepthook = handle_exception
