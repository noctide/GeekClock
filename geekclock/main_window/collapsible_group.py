"""可折叠分组容器。"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from geekclock.main_window.alarm_card import AlarmCard


class _HeaderFrame(QFrame):
    """可点击的分组标题栏。"""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class CollapsibleGroupWidget(QFrame):
    """可折叠的分组容器，包含标题栏和闹钟卡片区。

    Signals:
        toggle_group_requested(str): 批量切换该组闹钟的启用/禁用
        expanded_changed(str, bool): 用户展开/折叠分组时发出
    """

    toggle_group_requested = Signal(str)
    expanded_changed = Signal(str, bool)

    def __init__(self, group_name: str, color: str, expanded: bool = True, parent=None):
        super().__init__(parent)
        self._group_name = group_name
        self._expanded = expanded

        self.setStyleSheet("background: transparent;")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- 标题栏 ----
        self._header = _HeaderFrame()
        self._header.setFixedHeight(32)
        self._header.setStyleSheet("background: transparent;")
        self._header.clicked.connect(self._on_header_clicked)
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(12, 0, 12, 0)

        self._chevron = QLabel()
        self._chevron.setFixedWidth(14)
        self._chevron.setStyleSheet("font-size: 10px; color: #999;")
        header_layout.addWidget(self._chevron)

        color_dot = QLabel()
        color_dot.setFixedSize(10, 10)
        color_dot.setStyleSheet(f"background: {color}; border-radius: 5px;")
        header_layout.addWidget(color_dot)

        title_lbl = QLabel(group_name)
        title_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #333;")
        header_layout.addWidget(title_lbl)

        header_layout.addStretch()

        self._batch_btn = QPushButton()
        self._batch_btn.setFixedHeight(22)
        self._batch_btn.setStyleSheet(
            "QPushButton { font-size: 11px; padding: 2px 10px; "
            "border: 1px solid #ddd; border-radius: 3px; background: #fff; }"
            "QPushButton:hover { background: #f0f0f0; }"
        )
        # 工厂函数避免闭包延迟绑定
        def _make_handler(gn):
            return lambda: self.toggle_group_requested.emit(gn)
        self._batch_btn.clicked.connect(_make_handler(group_name))
        header_layout.addWidget(self._batch_btn)

        root.addWidget(self._header)

        # ---- 卡片区 ----
        self._content = QFrame()
        self._content.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 2, 0, 4)
        self._content_layout.setSpacing(4)
        root.addWidget(self._content)

        self._apply_expanded_state()

    def _on_header_clicked(self) -> None:
        self.set_expanded(not self._expanded)

    def _apply_expanded_state(self) -> None:
        self._chevron.setText("▼" if self._expanded else "▶")
        self._content.setVisible(self._expanded)

    def set_expanded(self, expanded: bool) -> None:
        if self._expanded == expanded:
            return
        self._expanded = expanded
        self._apply_expanded_state()
        self.expanded_changed.emit(self._group_name, expanded)

    def is_expanded(self) -> bool:
        return self._expanded

    def add_alarm_card(self, card: AlarmCard) -> None:
        self._content_layout.addWidget(card)

    def update_batch_button(self, all_enabled: bool) -> None:
        self._batch_btn.setText("全部暂停" if all_enabled else "全部启用")
