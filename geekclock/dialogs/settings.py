"""全局设置对话框。

包含：
- 勿扰时段
- 通知设置（快捷预设、明天上午时间、今天稍后偏移）
- 开机自启
"""
import logging
import re

from PySide6.QtCore import QTime
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
)

from geekclock.core import config
from geekclock.system.autostart import set_autostart

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """全局设置对话框。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GeekClock 设置")
        self.setModal(True)
        self.setMinimumWidth(420)

        self._setup_ui()
        self._load_data()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        # ---- 勿扰时段 ----
        dnd_group = QGroupBox("勿扰时段")
        dnd_layout = QVBoxLayout(dnd_group)

        self._dnd_enabled = QCheckBox("启用勿扰时段（此时段内闹钟不响）")
        dnd_layout.addWidget(self._dnd_enabled)

        time_row = QHBoxLayout()
        time_row.addWidget(QLabel("从"))
        self._dnd_start = QTimeEdit()
        self._dnd_start.setDisplayFormat("HH:mm")
        time_row.addWidget(self._dnd_start)
        time_row.addWidget(QLabel("至"))
        self._dnd_end = QTimeEdit()
        self._dnd_end.setDisplayFormat("HH:mm")
        time_row.addWidget(self._dnd_end)
        time_row.addStretch()
        dnd_layout.addLayout(time_row)

        # 联动：勾选时启用时间编辑
        self._dnd_enabled.toggled.connect(self._dnd_start.setEnabled)
        self._dnd_enabled.toggled.connect(self._dnd_end.setEnabled)

        layout.addWidget(dnd_group)

        # ---- 通知设置 ----
        notif_group = QGroupBox("通知设置")
        notif_form = QFormLayout(notif_group)

        # 延后快捷预设
        self._snooze_input = QLineEdit()
        self._snooze_input.setPlaceholderText("例如：5,15,30,60")
        notif_form.addRow(
            QLabel("延后快捷预设（分钟，逗号分隔，最多 4 个）"),
        )
        notif_form.addRow(self._snooze_input)

        # 明天上午时间
        self._tomorrow_time = QTimeEdit()
        self._tomorrow_time.setDisplayFormat("HH:mm")
        notif_form.addRow("「明天上午」具体时间", self._tomorrow_time)

        # 今天稍后偏移
        self._today_offset = QSpinBox()
        self._today_offset.setRange(1, 12)
        self._today_offset.setSuffix(" 小时")
        notif_form.addRow("「今天稍后」延后", self._today_offset)

        layout.addWidget(notif_group)

        # ---- 系统设置 ----
        sys_group = QGroupBox("系统")
        sys_layout = QVBoxLayout(sys_group)

        self._autostart = QCheckBox("开机自启动（Windows）")
        sys_layout.addWidget(self._autostart)

        autostart_hint = QLabel(
            "勾选后下次开机时自动启动 GeekClock，最小化到托盘运行。"
        )
        autostart_hint.setStyleSheet("color: #888; font-size: 11px;")
        autostart_hint.setWordWrap(True)
        sys_layout.addWidget(autostart_hint)

        layout.addWidget(sys_group)

        # ---- 底部按钮 ----
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
        """从配置加载数据填入控件。"""
        g = config.get_global_settings()

        self._dnd_enabled.setChecked(g.get("dnd_enabled", False))
        self._dnd_start.setTime(QTime.fromString(g.get("dnd_start", "22:00"), "HH:mm"))
        self._dnd_end.setTime(QTime.fromString(g.get("dnd_end", "08:00"), "HH:mm"))
        self._dnd_start.setEnabled(self._dnd_enabled.isChecked())
        self._dnd_end.setEnabled(self._dnd_enabled.isChecked())

        notif = config.get_notification_settings()
        self._snooze_input.setText(",".join(str(x) for x in notif["snooze_presets"]))
        self._tomorrow_time.setTime(
            QTime.fromString(notif["tomorrow_morning_time"], "HH:mm")
        )
        self._today_offset.setValue(notif["today_later_offset_hours"])

        self._autostart.setChecked(g.get("autostart", False))

    def _on_save(self) -> None:
        """保存设置。"""
        # 校验快捷预设格式
        snooze_text = self._snooze_input.text().strip()
        if not re.fullmatch(r"\s*\d+(\s*,\s*\d+){0,3}\s*", snooze_text):
            QMessageBox.warning(
                self, "格式错误",
                "延后快捷预设格式不对。\n"
                "请输入 1-4 个数字，用英文逗号分隔，例如：5,15,30,60",
            )
            return

        snooze_presets = [int(x.strip()) for x in snooze_text.split(",")]

        # 写入配置
        config.update_global_settings({
            "dnd_enabled": self._dnd_enabled.isChecked(),
            "dnd_start": self._dnd_start.time().toString("HH:mm"),
            "dnd_end": self._dnd_end.time().toString("HH:mm"),
            "notification": {
                "snooze_presets": snooze_presets,
                "tomorrow_morning_time": self._tomorrow_time.time().toString("HH:mm"),
                "today_later_offset_hours": self._today_offset.value(),
            },
            "autostart": self._autostart.isChecked(),
        })

        # 应用开机自启变化
        try:
            set_autostart(self._autostart.isChecked())
        except Exception as e:
            logger.error(f"设置开机自启失败：{e}")
            QMessageBox.warning(
                self, "开机自启设置失败",
                f"无法修改开机自启设置：{e}\n"
                "其他设置已保存。",
            )

        logger.info("设置已保存")
        self.accept()
