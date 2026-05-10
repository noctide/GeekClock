from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

OPACITY_SLIDER_STYLE = """
    QWidget { background: transparent; }
    QLabel {
        color: #333; background: transparent;
        font-size: 12px; padding: 4px 12px 0 12px;
    }
    QLabel#valueLabel {
        color: #888; font-size: 11px;
        padding: 0 12px 4px 12px;
    }
    QSlider { margin: 4px 12px 8px 12px; }
    QSlider::groove:horizontal {
        height: 4px; background: #e0e0e0; border-radius: 2px;
    }
    QSlider::handle:horizontal {
        background: #185FA5; width: 14px; height: 14px;
        margin: -5px 0; border-radius: 7px;
    }
    QSlider::sub-page:horizontal {
        background: #185FA5; border-radius: 2px;
    }
"""


class OpacitySliderWidget(QWidget):
    value_changed = Signal(float)

    def __init__(self, current_opacity: float, parent=None):
        super().__init__(parent)
        self.setStyleSheet(OPACITY_SLIDER_STYLE)
        self.setFixedWidth(180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("透明度")
        layout.addWidget(title)

        self._value_label = QLabel(self._format_value(current_opacity))
        self._value_label.setObjectName("valueLabel")
        layout.addWidget(self._value_label)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(100)
        self._slider.setValue(int(current_opacity * 100))
        self._slider.valueChanged.connect(self._on_value_changed)
        layout.addWidget(self._slider)

    @staticmethod
    def _format_value(opacity: float) -> str:
        pct = int(opacity * 100)
        if pct == 0:
            return f"{pct}% （几乎透明）"
        if pct == 100:
            return f"{pct}% （完全不透明）"
        return f"{pct}%"

    def _on_value_changed(self, value: int) -> None:
        opacity = value / 100.0
        self._value_label.setText(self._format_value(opacity))
        self.value_changed.emit(opacity)
