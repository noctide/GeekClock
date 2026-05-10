"""倒计时设置对话框。

用于设置倒计时时长、提示音、音量。
"""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)

from geekclock.system.resources import resource_path


class TimerSettingsDialog(QDialog):
    """倒计时设置对话框。

    使用方式：
        dialog = TimerSettingsDialog(
            current_seconds=1500,
            current_audio="sounds/bell.mp3",
            current_volume=0.6,
            audio_player=ap,
        )
        if dialog.exec() == QDialog.Accepted:
            seconds = dialog.get_seconds()
            audio = dialog.get_audio()
            volume = dialog.get_volume()
    """

    def __init__(
        self,
        current_seconds: int = 900,
        current_audio: str = "",
        current_volume: float = 0.6,
        audio_player=None,
        parent=None,
    ):
        super().__init__(parent)
        self._audio_player = audio_player

        self.setWindowTitle("倒计时设置")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setMinimumWidth(360)

        self._setup_ui(current_seconds, current_audio, current_volume)

    def _setup_ui(self, secs: int, audio: str, volume: float) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # 时长设置
        layout.addWidget(QLabel("倒计时时长"))
        time_row = QHBoxLayout()

        h, m, s = secs // 3600, (secs % 3600) // 60, secs % 60

        self._hours = QSpinBox()
        self._hours.setRange(0, 23)
        self._hours.setValue(h)
        self._hours.setSuffix(" 小时")
        time_row.addWidget(self._hours)

        self._minutes = QSpinBox()
        self._minutes.setRange(0, 59)
        self._minutes.setValue(m)
        self._minutes.setSuffix(" 分")
        time_row.addWidget(self._minutes)

        self._seconds = QSpinBox()
        self._seconds.setRange(0, 59)
        self._seconds.setValue(s)
        self._seconds.setSuffix(" 秒")
        time_row.addWidget(self._seconds)

        layout.addLayout(time_row)

        # 快捷预设
        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)
        for label, total_sec in [
            ("5 分钟", 300),
            ("15 分钟", 900),
            ("25 分钟", 1500),
            ("45 分钟", 2700),
            ("1 小时", 3600),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(
                lambda checked=False, sec=total_sec: self._set_seconds(sec)
            )
            preset_row.addWidget(btn)
        layout.addLayout(preset_row)

        # 提示音
        layout.addSpacing(8)
        layout.addWidget(QLabel("提示音"))
        audio_row = QHBoxLayout()

        self._audio_combo = QComboBox()
        self._populate_audio_list()

        # 选中当前音频
        self._set_current_audio(audio)
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
        self._volume_slider.setValue(int(volume * 100))
        self._volume_label = QLabel(f"{int(volume * 100)}%")
        self._volume_label.setFixedWidth(40)
        self._volume_slider.valueChanged.connect(
            lambda v: self._volume_label.setText(f"{v}%")
        )
        volume_row.addWidget(self._volume_slider, 1)
        volume_row.addWidget(self._volume_label)
        layout.addLayout(volume_row)

        # 底部按钮
        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        ok_btn = QPushButton("确定")
        ok_btn.setStyleSheet(
            "QPushButton { background: #185FA5; color: white; "
            "padding: 6px 18px; border-radius: 4px; }"
        )
        ok_btn.clicked.connect(self._on_accept)
        button_row.addWidget(ok_btn)
        layout.addLayout(button_row)

    def _populate_audio_list(self) -> None:
        """扫描 sounds/ 目录。"""
        self._audio_combo.addItem("(无音频，仅弹通知)", "")

        sounds_dir = resource_path("sounds")
        if sounds_dir.exists():
            for f in sorted(sounds_dir.iterdir()):
                if f.suffix.lower() in (".mp3", ".wav", ".ogg", ".flac"):
                    self._audio_combo.addItem(f.name, str(f))

    def _set_current_audio(self, audio: str) -> None:
        """选中下拉里匹配 audio 的项。"""
        if not audio:
            self._audio_combo.setCurrentIndex(0)
            return

        for i in range(self._audio_combo.count()):
            data = self._audio_combo.itemData(i) or ""
            if data == audio or data.endswith(audio.replace("\\", "/").split("/")[-1]):
                self._audio_combo.setCurrentIndex(i)
                return

        # 没找到就加进去
        self._audio_combo.addItem(audio.split("/")[-1], audio)
        self._audio_combo.setCurrentIndex(self._audio_combo.count() - 1)

    def _set_seconds(self, total_sec: int) -> None:
        """快捷预设按钮回调。"""
        self._hours.setValue(total_sec // 3600)
        self._minutes.setValue((total_sec % 3600) // 60)
        self._seconds.setValue(total_sec % 60)

    def _on_browse_audio(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择音频文件", "",
            "音频文件 (*.mp3 *.wav *.ogg *.flac)"
        )
        if path:
            name = Path(path).name
            idx = self._audio_combo.findData(path)
            if idx == -1:
                self._audio_combo.addItem(name, path)
                idx = self._audio_combo.count() - 1
            self._audio_combo.setCurrentIndex(idx)

    def _on_preview(self) -> None:
        if not self._audio_player:
            return
        path = self._audio_combo.currentData()
        if not path:
            return
        self._audio_player.play(
            path=path,
            volume=self._volume_slider.value() / 100.0,
            fade_in=False,
            max_duration=5, # 倒计时响铃试听时长设置    时长 5 秒
        )

    def _on_accept(self) -> None:
        if self.get_seconds() <= 0:
            return  # 不允许 0 秒
        self.accept()

    def get_seconds(self) -> int:
        return (
            self._hours.value() * 3600
            + self._minutes.value() * 60
            + self._seconds.value()
        )

    def get_audio(self) -> str:
        return self._audio_combo.currentData() or ""

    def get_volume(self) -> float:
        return self._volume_slider.value() / 100.0
