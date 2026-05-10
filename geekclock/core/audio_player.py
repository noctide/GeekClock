"""音频播放模块。

播放控制：
- 完整播放一次（默认）
- 重复播放指定次数
- 限定播放时长（到时停止，可能在中间）

跨线程安全：play() 可从任意线程调用。
"""
import logging
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from geekclock.system.resources import resource_path

logger = logging.getLogger(__name__)

FADE_IN_DURATION_MS = 3000
FADE_STEP_MS = 100


class AudioPlayer(QObject):
    """音频播放器。

    使用方式：
        player = AudioPlayer()

        # 完整播放一次（默认）
        player.play("sound.mp3", volume=0.6)

        # 重复播放 3 次
        player.play("sound.mp3", volume=0.6, repeat_count=3)

        # 限定 30 秒（不管播完没播完）
        player.play("sound.mp3", volume=0.6, max_duration=30)

        # 停止
        player.stop()
    """

    _play_requested = Signal(str, float, bool, int, int)
    _stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)

        # 渐强用的定时器
        self._fade_timer = QTimer(self)
        self._fade_timer.setInterval(FADE_STEP_MS)
        self._fade_timer.timeout.connect(self._on_fade_step)
        self._fade_target_volume = 0.0
        self._fade_current_volume = 0.0

        # 超时停止用的定时器
        self._max_duration_timer = QTimer(self)
        self._max_duration_timer.setSingleShot(True)
        self._max_duration_timer.timeout.connect(self._do_stop)

        # 重复播放计数
        self._repeat_remaining = 0  # 还剩几次循环
        self._current_path = ""

        # 监听播放状态变化（用于循环播放）
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)
        self._player.errorOccurred.connect(self._on_error)

        # 跨线程信号路由
        self._play_requested.connect(self._do_play, Qt.ConnectionType.QueuedConnection)
        self._stop_requested.connect(self._do_stop, Qt.ConnectionType.QueuedConnection)

    def play(
        self,
        path: str,
        volume: float = 0.6,
        fade_in: bool = True,
        max_duration: int = 0,
        repeat_count: int = 1,
    ) -> bool:
        """请求播放音频。

        Args:
            path: 文件路径
            volume: 目标音量 0.0-1.0
            fade_in: 是否渐强淡入
            max_duration: 最长播放秒数。0 = 不限制
            repeat_count: 重复播放次数（>=1）。1 = 播一次

        Returns:
            是否成功提交请求
        """
        audio_path = Path(path)
        if not audio_path.is_absolute():
            audio_path = resource_path(audio_path)

        if not audio_path.exists():
            logger.error(f"音频文件不存在：{audio_path}")
            return False

        if not audio_path.is_file():
            logger.error(f"路径不是文件：{audio_path}")
            return False

        # 校验参数
        repeat_count = max(1, min(99, repeat_count))
        max_duration = max(0, max_duration)

        self._play_requested.emit(
            str(audio_path), volume, fade_in, max_duration, repeat_count
        )
        return True

    def stop(self) -> None:
        """停止播放。"""
        self._stop_requested.emit()

    @Slot(str, float, bool, int, int)
    def _do_play(
        self,
        absolute_path: str,
        volume: float,
        fade_in: bool,
        max_duration: int,
        repeat_count: int,
    ) -> None:
        """实际的播放逻辑，必须在主线程执行。"""
        self._do_stop()

        # 记录信息
        self._current_path = absolute_path
        self._repeat_remaining = repeat_count - 1  # 第一次播放算 1 次，剩 N-1 次

        url = QUrl.fromLocalFile(absolute_path)
        self._player.setSource(url)

        target = max(0.0, min(1.0, volume))
        if fade_in:
            self._fade_target_volume = target
            self._fade_current_volume = 0.0
            self._audio_output.setVolume(0.0)
            self._fade_timer.start()
        else:
            self._audio_output.setVolume(target)

        # 只有当 max_duration > 0 时才启用超时定时器
        if max_duration > 0:
            self._max_duration_timer.start(max_duration * 1000)

        self._player.play()
        logger.info(
            f"开始播放：{Path(absolute_path).name} "
            f"(音量 {int(target * 100)}%, 渐强 {fade_in}, "
            f"超时 {max_duration if max_duration > 0 else '无限制'}s, "
            f"重复 {repeat_count} 次)"
        )

    @Slot()
    def _do_stop(self) -> None:
        """实际的停止逻辑，必须在主线程执行。"""
        if self._player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            self._player.stop()
            logger.debug("音频已停止")

        self._fade_timer.stop()
        self._max_duration_timer.stop()
        self._fade_current_volume = 0.0
        self._repeat_remaining = 0
        self._current_path = ""

    @Slot(QMediaPlayer.MediaStatus)
    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        """监听播放状态。EndOfMedia 表示一次播放结束。"""
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self._repeat_remaining > 0:
                # 还要循环
                self._repeat_remaining -= 1
                logger.info(f"重复播放，剩余 {self._repeat_remaining + 1} 次")
                self._player.setPosition(0)
                self._player.play()
            else:
                # 全部播完
                logger.info("音频播放完成")
                self._max_duration_timer.stop()  # 已自然结束，关闭超时定时器

    @Slot()
    def _on_fade_step(self) -> None:
        step = self._fade_target_volume / (FADE_IN_DURATION_MS / FADE_STEP_MS)
        self._fade_current_volume += step

        if self._fade_current_volume >= self._fade_target_volume:
            self._fade_current_volume = self._fade_target_volume
            self._fade_timer.stop()

        self._audio_output.setVolume(self._fade_current_volume)

    @Slot(QMediaPlayer.Error, str)
    def _on_error(self, error: QMediaPlayer.Error, error_string: str) -> None:
        if error != QMediaPlayer.Error.NoError:
            logger.error(f"音频播放错误：{error_string}")
