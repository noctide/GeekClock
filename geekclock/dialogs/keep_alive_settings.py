"""音响保活设置弹窗。"""

from PySide6.QtCore import Qt, QTime
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
)

from geekclock.core import config


class KeepAliveSettingsDialog(QDialog):
    """音响保活设置弹窗。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("音响保活设置")
        self.setModal(True)
        self.setMinimumWidth(360)

        self._setup_ui()
        self._load_data()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        self._enabled_cb = QCheckBox("启用音响保活（定期激活音频设备，防止休眠）")
        layout.addWidget(self._enabled_cb)

        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("激活间隔"))
        self._interval_sb = QSpinBox()
        self._interval_sb.setRange(1, 60)
        self._interval_sb.setSuffix(" 分钟")
        interval_row.addWidget(self._interval_sb)
        interval_row.addStretch()
        layout.addLayout(interval_row)

        volume_row = QHBoxLayout()
        volume_row.addWidget(QLabel("激活音量"))
        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_label = QLabel("0%")
        self._volume_label.setFixedWidth(40)
        self._volume_slider.valueChanged.connect(
            lambda v: self._volume_label.setText(f"{v}%")
        )
        volume_row.addWidget(self._volume_slider, 1)
        volume_row.addWidget(self._volume_label)
        layout.addLayout(volume_row)

        time_row = QHBoxLayout()
        time_row.addWidget(QLabel("激活时段"))
        self._from_time = QTimeEdit()
        self._from_time.setDisplayFormat("HH:mm")
        time_row.addWidget(self._from_time)
        time_row.addWidget(QLabel("至"))
        self._to_time = QTimeEdit()
        self._to_time.setDisplayFormat("HH:mm")
        time_row.addWidget(self._to_time)
        time_row.addStretch()
        layout.addLayout(time_row)

        hint = QLabel("建议设为 0%（静音激活），避免听到声音")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._enabled_cb.toggled.connect(self._interval_sb.setEnabled)
        self._enabled_cb.toggled.connect(self._volume_slider.setEnabled)
        self._enabled_cb.toggled.connect(self._from_time.setEnabled)
        self._enabled_cb.toggled.connect(self._to_time.setEnabled)

        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        save_btn = QPushButton("保存")
        save_btn.setStyleSheet(
            "QPushButton { background: #185FA5; color: white; "
            "padding: 6px 18px; border-radius: 4px; }"
        )
        save_btn.clicked.connect(self._on_save)
        button_row.addWidget(save_btn)
        layout.addLayout(button_row)

    def _load_data(self) -> None:
        ka = config.get_keep_alive_settings()
        self._enabled_cb.setChecked(ka["enabled"])
        self._interval_sb.setValue(ka["interval_minutes"])
        self._volume_slider.setValue(int(ka["volume"] * 100))
        self._interval_sb.setEnabled(ka["enabled"])
        self._volume_slider.setEnabled(ka["enabled"])
        self._from_time.setTime(
            QTime.fromString(ka.get("active_from", "08:00"), "HH:mm")
        )
        self._to_time.setTime(
            QTime.fromString(ka.get("active_to", "22:00"), "HH:mm")
        )
        self._from_time.setEnabled(ka["enabled"])
        self._to_time.setEnabled(ka["enabled"])

    def _on_save(self) -> None:
        config.update_keep_alive_settings({
            "enabled": self._enabled_cb.isChecked(),
            "interval_minutes": self._interval_sb.value(),
            "volume": self._volume_slider.value() / 100.0,
            "active_from": self._from_time.time().toString("HH:mm"),
            "active_to": self._to_time.time().toString("HH:mm"),
        })
        self.accept()
