"""新建/编辑闹钟对话框。"""
import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from geekclock.core import config
from geekclock.system.resources import resource_path

logger = logging.getLogger(__name__)


WEEKDAY_NAMES = ["一", "二", "三", "四", "五", "六", "日"]


class EditAlarmDialog(QDialog):
    """新建/编辑闹钟对话框。

    使用方式：
        # 新建
        dialog = EditAlarmDialog(audio_player=ap)
        if dialog.exec() == QDialog.Accepted:
            new_alarm = dialog.get_alarm()

        # 编辑
        dialog = EditAlarmDialog(audio_player=ap, alarm=existing_alarm)
        ...
    """

    def __init__(self, audio_player=None, alarm: dict | None = None, parent=None):
        super().__init__(parent)
        self._audio_player = audio_player
        self._alarm = alarm or {}
        self._is_edit = alarm is not None

        self.setWindowTitle("编辑闹钟" if self._is_edit else "新建闹钟")
        self.setModal(True)
        self.setMinimumWidth(420)

        self._setup_ui()
        self._load_alarm_data()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("例如：喝水提醒")
        layout.addWidget(self._name_input)

        # 分组
        group_row = QHBoxLayout()
        group_row.addWidget(QLabel("分组"))
        self._group_combo = QComboBox()
        self._group_combo.setEditable(True)
        self._refresh_group_combo()
        group_row.addWidget(self._group_combo, 1)
        layout.addLayout(group_row)

        # 触发方式（三选一）
        layout.addWidget(QLabel("触发方式"))
        type_row = QHBoxLayout()
        self._type_group = QButtonGroup(self)
        self._radio_interval = QRadioButton("间隔重复")
        self._radio_cron = QRadioButton("固定时刻")
        self._radio_date = QRadioButton("单次")
        self._type_group.addButton(self._radio_interval, 0)
        self._type_group.addButton(self._radio_cron, 1)
        self._type_group.addButton(self._radio_date, 2)
        type_row.addWidget(self._radio_interval)
        type_row.addWidget(self._radio_cron)
        type_row.addWidget(self._radio_date)
        type_row.addStretch()
        layout.addLayout(type_row)

        # 三种触发方式的参数面板（互斥显示）
        self._interval_panel = self._build_interval_panel()
        self._cron_panel = self._build_cron_panel()
        self._date_panel = self._build_date_panel()
        layout.addWidget(self._interval_panel)
        layout.addWidget(self._cron_panel)
        layout.addWidget(self._date_panel)

        self._type_group.idToggled.connect(self._on_type_changed)
        self._radio_interval.setChecked(True)

        # 提示文本
        layout.addWidget(QLabel("提示文本"))
        self._message_input = QTextEdit()
        self._message_input.setMaximumHeight(56)
        self._message_input.setPlaceholderText("例如：该喝水啦，起来活动一下")
        layout.addWidget(self._message_input)

        # 音频
        layout.addWidget(QLabel("提示音"))
        audio_row = QHBoxLayout()
        self._audio_combo = QComboBox()
        self._audio_combo.setEditable(False)
        self._populate_audio_list()
        audio_row.addWidget(self._audio_combo, 1)
        browse_btn = QPushButton("浏览…")
        browse_btn.clicked.connect(self._on_browse_audio)
        audio_row.addWidget(browse_btn)
        preview_btn = QPushButton("▶ 试听")
        preview_btn.clicked.connect(self._on_preview)
        audio_row.addWidget(preview_btn)
        layout.addLayout(audio_row)

        # 音量
        volume_row = QHBoxLayout()
        volume_row.addWidget(QLabel("音量"))
        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(60)
        self._volume_label = QLabel("60%")
        self._volume_label.setFixedWidth(40)
        self._volume_slider.valueChanged.connect(
            lambda v: self._volume_label.setText(f"{v}%")
        )
        volume_row.addWidget(self._volume_slider, 1)
        volume_row.addWidget(self._volume_label)
        layout.addLayout(volume_row)

        # 选项开关
        self._fade_in_check = QCheckBox("渐强淡入（3 秒内从静音升到目标音量）")
        self._fade_in_check.setChecked(True)
        layout.addWidget(self._fade_in_check)

        # 播放次数
        repeat_row = QHBoxLayout()
        repeat_row.addWidget(QLabel("重复播放"))
        self._repeat_count = QSpinBox()
        self._repeat_count.setRange(1, 99)
        self._repeat_count.setValue(1)
        self._repeat_count.setSuffix(" 次")
        repeat_row.addWidget(self._repeat_count)
        repeat_row.addStretch()
        layout.addLayout(repeat_row)

        # 最大时长
        duration_row = QHBoxLayout()
        duration_row.addWidget(QLabel("最长时长"))
        self._max_duration = QSpinBox()
        self._max_duration.setRange(0, 999)
        self._max_duration.setValue(0)
        self._max_duration.setSuffix(" 秒（0=不限）")
        duration_row.addWidget(self._max_duration)
        duration_row.addStretch()
        layout.addLayout(duration_row)

        self._snooze_check = QCheckBox("允许延后")
        self._snooze_check.setChecked(True)
        layout.addWidget(self._snooze_check)

        # 底部按钮
        button_row = QHBoxLayout()
        if self._is_edit:
            del_btn = QPushButton("删除")
            del_btn.setStyleSheet("color: #E24B4A;")
            del_btn.clicked.connect(self._on_delete)
            button_row.addWidget(del_btn)
        button_row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        save_btn = QPushButton("保存")
        save_btn.setDefault(True)
        save_btn.setStyleSheet(
            "QPushButton { background: #185FA5; color: white; padding: 6px 16px; "
            "border-radius: 4px; }"
        )
        save_btn.clicked.connect(self._on_save)
        button_row.addWidget(save_btn)
        layout.addLayout(button_row)

        self._delete_requested = False
        self._result_alarm: dict | None = None

    def _build_interval_panel(self) -> QWidget:
        panel = QGroupBox()
        layout = QFormLayout(panel)

        # 每隔
        interval_row = QHBoxLayout()
        self._interval_value = QSpinBox()
        self._interval_value.setRange(1, 999)
        self._interval_value.setValue(20)
        self._interval_unit = QComboBox()
        self._interval_unit.addItems(["秒", "分钟", "小时"])
        self._interval_unit.setCurrentIndex(1)
        interval_row.addWidget(self._interval_value)
        interval_row.addWidget(self._interval_unit)
        interval_row.addStretch()
        layout.addRow("每隔", interval_row)

        # 活动时段
        active_row = QHBoxLayout()
        self._active_start = QTimeEdit()
        self._active_start.setDisplayFormat("HH:mm")
        self._active_start.setTime(QDateTime.fromString("09:00", "HH:mm").time())
        self._active_end = QTimeEdit()
        self._active_end.setDisplayFormat("HH:mm")
        self._active_end.setTime(QDateTime.fromString("18:00", "HH:mm").time())
        active_row.addWidget(self._active_start)
        active_row.addWidget(QLabel("至"))
        active_row.addWidget(self._active_end)
        active_row.addStretch()
        layout.addRow("活动时段", active_row)

        # 工作日复选
        weekday_row = QHBoxLayout()
        self._weekday_checks_interval = []
        for i, name in enumerate(WEEKDAY_NAMES):
            cb = QCheckBox(name)
            cb.setChecked(i < 5)
            self._weekday_checks_interval.append(cb)
            weekday_row.addWidget(cb)
        weekday_row.addStretch()
        layout.addRow("仅在", weekday_row)

        return panel

    def _build_cron_panel(self) -> QWidget:
        panel = QGroupBox()
        layout = QFormLayout(panel)

        self._cron_time = QTimeEdit()
        self._cron_time.setDisplayFormat("HH:mm")
        self._cron_time.setTime(QDateTime.fromString("09:30", "HH:mm").time())
        layout.addRow("时刻", self._cron_time)

        weekday_row = QHBoxLayout()
        self._weekday_checks_cron = []
        for i, name in enumerate(WEEKDAY_NAMES):
            cb = QCheckBox(name)
            cb.setChecked(i < 5)
            self._weekday_checks_cron.append(cb)
            weekday_row.addWidget(cb)
        weekday_row.addStretch()
        layout.addRow("星期", weekday_row)

        return panel

    def _build_date_panel(self) -> QWidget:
        panel = QGroupBox()
        layout = QFormLayout(panel)

        self._date_picker = QDateTimeEdit()
        self._date_picker.setCalendarPopup(True)
        self._date_picker.setDisplayFormat("yyyy-MM-dd HH:mm")
        self._date_picker.setDateTime(QDateTime.currentDateTime().addSecs(3600))
        layout.addRow("触发时间", self._date_picker)

        return panel

    def _on_type_changed(self, type_id: int, checked: bool) -> None:
        if not checked:
            return
        self._interval_panel.setVisible(type_id == 0)
        self._cron_panel.setVisible(type_id == 1)
        self._date_panel.setVisible(type_id == 2)

    def _refresh_group_combo(self) -> None:
        current = self._group_combo.currentText()
        self._group_combo.clear()
        for g in config.get_groups():
            self._group_combo.addItem(g)
        if current:
            idx = self._group_combo.findText(current)
            if idx >= 0:
                self._group_combo.setCurrentIndex(idx)
            else:
                self._group_combo.setEditText(current)

    def _populate_audio_list(self) -> None:
        """扫描 sounds/ 目录，填入下拉。"""
        # 第一项始终是"无音频"
        self._audio_combo.addItem("(无音频，仅弹通知)", "")

        sounds_dir = resource_path("sounds")
        if sounds_dir.exists():
            for f in sorted(sounds_dir.iterdir()):
                if f.suffix.lower() in (".mp3", ".wav", ".ogg", ".flac"):
                    self._audio_combo.addItem(f.name, str(f))

    def _on_browse_audio(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择音频文件", "",
            "音频文件 (*.mp3 *.wav *.ogg *.flac)"
        )
        if path:
            name = Path(path).name
            # 用绝对路径添加
            idx = self._audio_combo.findData(path)
            if idx == -1:
                self._audio_combo.addItem(name, path)
                idx = self._audio_combo.count() - 1
            self._audio_combo.setCurrentIndex(idx)

    def _on_preview(self) -> None:
        """试听当前选中的音频。"""
        if not self._audio_player:
            QMessageBox.information(self, "提示", "试听需要音频播放器，当前不可用")
            return
        path = self._audio_combo.currentData()
        if not path:
            QMessageBox.information(self, "提示", "请先选择音频")
            return
        volume = self._volume_slider.value() / 100.0
        self._audio_player.play(
            path=path,
            volume=volume,
            fade_in=False,  # 试听不渐强，立刻能听到
            max_duration=30,  # 试听时长设置 最多 30 秒
        )

    def _load_alarm_data(self) -> None:
        """如果是编辑模式，把现有数据填入控件。"""
        if not self._alarm:
            return

        a = self._alarm
        self._name_input.setText(a.get("name", ""))
        self._group_combo.setCurrentText(a.get("group", "默认"))
        self._message_input.setPlainText(a.get("message", ""))
        self._volume_slider.setValue(int(a.get("audio_volume", 0.6) * 100))
        self._fade_in_check.setChecked(a.get("fade_in", True))
        self._snooze_check.setChecked(a.get("snooze_enabled", True))
        self._repeat_count.setValue(a.get("repeat_count", 1))
        self._max_duration.setValue(a.get("max_duration", 0))

        # 音频路径回填：先尝试找到匹配的项
        audio = a.get("audio", "")
        if audio:
            for i in range(self._audio_combo.count()):
                if self._audio_combo.itemData(i) == audio or \
                   self._audio_combo.itemData(i).endswith(audio.split("/")[-1]):
                    self._audio_combo.setCurrentIndex(i)
                    break
            else:
                # 没找到就加进去
                self._audio_combo.addItem(audio.split("/")[-1], audio)
                self._audio_combo.setCurrentIndex(self._audio_combo.count() - 1)

        # 触发方式
        t = a["trigger_type"]
        args = a.get("trigger_args", {})
        wds = a.get("weekdays", [1, 2, 3, 4, 5])

        if t == "interval":
            self._radio_interval.setChecked(True)
            if "seconds" in args:
                self._interval_value.setValue(args["seconds"])
                self._interval_unit.setCurrentIndex(0)
            elif "hours" in args:
                self._interval_value.setValue(args["hours"])
                self._interval_unit.setCurrentIndex(2)
            else:
                self._interval_value.setValue(args.get("minutes", 20))
                self._interval_unit.setCurrentIndex(1)

            active = a.get("active_hours", ["09:00", "18:00"])
            self._active_start.setTime(QDateTime.fromString(active[0], "HH:mm").time())
            self._active_end.setTime(QDateTime.fromString(active[1], "HH:mm").time())

            for i, cb in enumerate(self._weekday_checks_interval):
                cb.setChecked((i + 1) in wds)

        elif t == "cron":
            self._radio_cron.setChecked(True)
            h = args.get("hour", 9)
            m = args.get("minute", 30)
            self._cron_time.setTime(QDateTime.fromString(f"{h:02d}:{m:02d}", "HH:mm").time())
            for i, cb in enumerate(self._weekday_checks_cron):
                cb.setChecked((i + 1) in wds)

        elif t == "date":
            self._radio_date.setChecked(True)
            run_str = args.get("run_date", "")
            if run_str:
                dt = QDateTime.fromString(run_str, "yyyy-MM-dd HH:mm:ss")
                if dt.isValid():
                    self._date_picker.setDateTime(dt)

    def _on_save(self) -> None:
        """收集表单数据，校验后接受对话框。"""
        name = self._name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "名称不能为空")
            return

        type_id = self._type_group.checkedId()

        if type_id == 0:  # interval
            unit_map = ["seconds", "minutes", "hours"]
            unit = unit_map[self._interval_unit.currentIndex()]
            trigger_args = {unit: self._interval_value.value()}
            weekdays = [
                i + 1 for i, cb in enumerate(self._weekday_checks_interval)
                if cb.isChecked()
            ]
            if not weekdays:
                QMessageBox.warning(self, "提示", "至少选择一天")
                return
            active_hours = [
                self._active_start.time().toString("HH:mm"),
                self._active_end.time().toString("HH:mm"),
            ]
            self._result_alarm = {
                "trigger_type": "interval",
                "trigger_args": trigger_args,
                "weekdays": weekdays,
                "active_hours": active_hours,
            }

        elif type_id == 1:  # cron
            t = self._cron_time.time()
            weekdays = [
                i + 1 for i, cb in enumerate(self._weekday_checks_cron)
                if cb.isChecked()
            ]
            if not weekdays:
                QMessageBox.warning(self, "提示", "至少选择一天")
                return
            self._result_alarm = {
                "trigger_type": "cron",
                "trigger_args": {"hour": t.hour(), "minute": t.minute()},
                "weekdays": weekdays,
                "active_hours": ["00:00", "23:59"],
            }

        else:  # date
            dt = self._date_picker.dateTime()
            if dt.toPython() <= datetime.now():
                QMessageBox.warning(self, "提示", "时间必须在未来")
                return
            self._result_alarm = {
                "trigger_type": "date",
                "trigger_args": {"run_date": dt.toString("yyyy-MM-dd HH:mm:ss")},
                "weekdays": [1, 2, 3, 4, 5, 6, 7],
                "active_hours": ["00:00", "23:59"],
            }

        # 公共字段
        self._result_alarm.update({
            "name": name,
            "group": self._group_combo.currentText().strip() or "默认",
            "message": self._message_input.toPlainText().strip(),
            "audio": self._audio_combo.currentData() or "",
            "audio_volume": self._volume_slider.value() / 100.0,
            "fade_in": self._fade_in_check.isChecked(),
            "snooze_enabled": self._snooze_check.isChecked(),
            "max_duration": self._max_duration.value(),     # 改成从 UI 取
            "repeat_count": self._repeat_count.value(),     # 新增
            "enabled": self._alarm.get("enabled", True),
        })

        # 保留原 id（编辑模式）
        if self._is_edit and "id" in self._alarm:
            self._result_alarm["id"] = self._alarm["id"]

        self.accept()

    def _on_delete(self) -> None:
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定删除闹钟「{self._alarm.get('name', '')}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._delete_requested = True
            self.accept()

    def get_alarm(self) -> dict:
        return self._result_alarm if self._result_alarm is not None else {}

    def is_delete_requested(self) -> bool:
        """对话框 Accept 后判断是新建/编辑还是删除。"""
        return self._delete_requested
