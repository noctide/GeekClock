"""单条闹钟卡片组件。"""
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from geekclock.core.config import get_group_color

# 闹钟类型 → (背景色, 边框色, 图标色, 类型徽章文本)
TYPE_COLORS = {
    "interval": ("#E1F5EE", "#5DCAA5", "#0F6E56", "间隔"),
    "cron":     ("#EEEDFE", "#AFA9EC", "#534AB7", "定时"),
    "date":     ("#FAEEDA", "#FAC775", "#854F0B", "单次"),
}


def format_trigger_summary(alarm: dict) -> str:
    """根据闹钟配置生成简短的触发描述。"""
    t = alarm["trigger_type"]
    args = alarm.get("trigger_args", {})

    if t == "interval":
        if "seconds" in args:
            return f"每 {args['seconds']} 秒"
        if "minutes" in args:
            return f"每 {args['minutes']} 分钟"
        if "hours" in args:
            return f"每 {args['hours']} 小时"
        return "间隔"

    if t == "cron":
        h = args.get("hour", "?")
        m = args.get("minute", 0)
        wds = alarm.get("weekdays", [1, 2, 3, 4, 5, 6, 7])
        if len(wds) == 7:
            return f"每天 {h:02d}:{m:02d}"
        if wds == [1, 2, 3, 4, 5]:
            return f"工作日 {h:02d}:{m:02d}"
        if wds == [6, 7]:
            return f"周末 {h:02d}:{m:02d}"
        names = ["一", "二", "三", "四", "五", "六", "日"]
        labels = "".join(names[d - 1] for d in sorted(wds))
        return f"周{labels} {h:02d}:{m:02d}"

    if t == "date":
        run = args.get("run_date", "")
        return f"单次 {run[:16]}" if run else "单次"

    return "未知"


def format_next_run(next_run_dt) -> str:
    """格式化下次触发时间显示。"""
    if not next_run_dt:
        return "未启用"
    now = datetime.now(next_run_dt.tzinfo) if next_run_dt.tzinfo else datetime.now()
    delta = next_run_dt - now
    secs = int(delta.total_seconds())

    if secs < 0:
        return "即将触发"
    if secs < 60:
        return f"{secs} 秒后"
    if secs < 3600:
        return f"{secs // 60} 分钟后"
    if next_run_dt.date() == now.date():
        return f"今天 {next_run_dt.strftime('%H:%M')}"
    return next_run_dt.strftime("%m-%d %H:%M")


class ToggleSwitch(QPushButton):
    """简易开关按钮，绿色=开，灰色=关。"""

    def __init__(self, checked: bool = True, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(36, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style()
        self.toggled.connect(lambda _: self._update_style())

    def _update_style(self) -> None:
        if self.isChecked():
            self.setStyleSheet("""
                QPushButton {
                    background: #1D9E75;
                    border: none;
                    border-radius: 10px;
                    text-align: right;
                    padding-right: 4px;
                    color: white;
                    font-size: 9px;
                }
            """)
            self.setText("●")
        else:
            self.setStyleSheet("""
                QPushButton {
                    background: #ccc;
                    border: none;
                    border-radius: 10px;
                    text-align: left;
                    padding-left: 4px;
                    color: white;
                    font-size: 9px;
                }
            """)
            self.setText("●")


class AlarmCard(QFrame):
    """单条闹钟卡片。"""

    edit_requested = Signal(str)
    delete_requested = Signal(str)
    toggle_changed = Signal(str, bool)

    def __init__(self, alarm: dict, next_run=None, parent=None):
        super().__init__(parent)
        self._alarm = alarm
        self._setup_ui(next_run)

    def _setup_ui(self, next_run) -> None:
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("""
            AlarmCard {
                background: white;
                border-radius: 6px;
            }
            AlarmCard:hover {
                background: #f9f9f9;
            }
        """)
        self.setFixedHeight(64)

        # 主水平布局：图标 + 中部 + 操作按钮组
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        t = self._alarm["trigger_type"]
        bg, border, icon_color, badge_text = TYPE_COLORS.get(t, TYPE_COLORS["interval"])

        # 类型图标方块
        icon = QLabel()
        icon.setFixedSize(36, 36)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setText({"interval": "⏱", "cron": "📅", "date": "★"}.get(t, "?"))
        icon.setStyleSheet(f"""
            background: {bg};
            border-radius: 6px;
            color: {icon_color};
            font-size: 16px;
        """)
        layout.addWidget(icon)

        # 中部：标题行 + 详情行
        center = QVBoxLayout()
        center.setSpacing(2)
        center.setContentsMargins(0, 0, 0, 0)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_row.setContentsMargins(0, 0, 0, 0)

        name_label = QLabel(self._alarm["name"])
        if self._alarm.get("enabled", True):
            name_label.setStyleSheet("font-size: 14px; font-weight: 500;")
        else:
            name_label.setStyleSheet("font-size: 14px; font-weight: 500; color: #aaa;")
        title_row.addWidget(name_label)

        # 分组色点
        group_dot = QLabel()
        group_dot.setFixedSize(8, 8)
        color = get_group_color(self._alarm.get("group", "默认"))
        group_dot.setStyleSheet(f"background: {color}; border-radius: 4px;")
        title_row.addWidget(group_dot)

        badge = QLabel(format_trigger_summary(self._alarm))
        badge.setStyleSheet(f"""
            background: {bg};
            color: {icon_color};
            font-size: 11px;
            padding: 1px 8px;
            border-radius: 9px;
        """)
        title_row.addWidget(badge)
        title_row.addStretch()
        center.addLayout(title_row)

        # 详情行：动作描述 · 下次 xx
        next_text = format_next_run(next_run) if self._alarm.get("enabled") else "已禁用"
        action_type = self._alarm.get("action_type", "audio")
        if action_type == "open_file":
            file_path = self._alarm.get("file_path", "")
            file_name = file_path.replace("\\", "/").split("/")[-1] or "无文件"
            detail_text = f"打开 {file_name} · 下次 {next_text}"
        else:
            audio_path = self._alarm.get("audio", "") or ""
            audio_name = audio_path.replace("\\", "/").split("/")[-1] or "无音频"
            detail_text = f"{audio_name} · 下次 {next_text}"
        if len(detail_text) > 40:
            detail_text = detail_text[:38] + "…"
        detail = QLabel(detail_text)
        detail.setStyleSheet("font-size: 12px; color: #999;")
        center.addWidget(detail)

        layout.addLayout(center, 1)  # 中部占满剩余空间

        # 操作按钮组：编辑 + 删除 + 开关，捆绑成固定宽度的横向布局
        actions = QHBoxLayout()
        actions.setSpacing(4)
        actions.setContentsMargins(0, 0, 0, 0)

        edit_btn = QPushButton("编辑")
        edit_btn.setFixedSize(40, 24)
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none;
                color: #999; font-size: 12px;
            }
            QPushButton:hover { color: #185FA5; }
        """)
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(self._alarm["id"]))
        actions.addWidget(edit_btn)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(20, 24)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none;
                color: #ccc; font-size: 13px;
            }
            QPushButton:hover { color: #E24B4A; }
        """)
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self._alarm["id"]))
        actions.addWidget(del_btn)

        toggle = ToggleSwitch(checked=self._alarm.get("enabled", True))
        toggle.toggled.connect(
            lambda checked: self.toggle_changed.emit(self._alarm["id"], checked)
        )
        actions.addWidget(toggle)

        # 把操作组放进固定宽度的容器，确保不会被裁切
        action_container = QFrame()
        action_container.setLayout(actions)
        action_container.setFixedWidth(108)  # 40 + 4 + 20 + 4 + 36 + 余量
        action_container.setStyleSheet("background: transparent;")
        layout.addWidget(action_container)
