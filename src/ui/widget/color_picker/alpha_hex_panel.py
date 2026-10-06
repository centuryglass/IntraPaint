"""A color control with the alpha slider and hex field below it, kept in sync.

The control can be any widget with `set_color(QColor)` and `color_changed` / `color_committed` signals. The panel
re-emits both: `color_changed` while browsing, `color_committed` on a finished choice.
"""
from typing import Optional, Protocol

from PySide6.QtCore import Qt, Signal, SignalInstance
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout

from src.ui.widget.color_picker.alpha_hex_row import AlphaHexRow


class ColorControl(Protocol):
    """A widget that edits a color, as AlphaHexPanel expects."""
    color_changed: SignalInstance
    color_committed: SignalInstance

    def set_color(self, color: QColor) -> None:
        """Sets the color without emitting signals."""


class AlphaHexPanel(QWidget):
    """A color control with the alpha slider and hex field below it, kept in sync."""

    color_changed = Signal(QColor)
    color_committed = Signal(QColor)

    def __init__(self, control: QWidget, parent: Optional[QWidget] = None, control_stretch: int = 1) -> None:
        super().__init__(parent)
        self._color = QColor(Qt.GlobalColor.black)
        self._control = control
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        control.setParent(self)
        layout.addWidget(control, stretch=control_stretch)
        self._alpha_hex_row = AlphaHexRow(self)
        layout.addWidget(self._alpha_hex_row)
        if control_stretch == 0:
            layout.addStretch(1)

        typed_control: ColorControl = control  # type: ignore[assignment]
        typed_control.color_changed.connect(self._control_changed)
        typed_control.color_committed.connect(self.color_committed)
        self._alpha_hex_row.color_changed.connect(self._alpha_hex_changed)
        self._alpha_hex_row.color_committed.connect(self.color_committed)
        self.set_color(QColor(Qt.GlobalColor.black))

    @property
    def alpha_hex_row(self) -> AlphaHexRow:
        """The alpha slider and hex field."""
        return self._alpha_hex_row

    def selected_color(self) -> QColor:
        """Returns the selected color."""
        return QColor(self._color)

    def set_color(self, color: QColor) -> None:
        """Sets the selected color without emitting signals."""
        self._color = color.toRgb()
        typed_control: ColorControl = self._control  # type: ignore[assignment]
        typed_control.set_color(color)
        self._alpha_hex_row.set_color(color)

    def _control_changed(self, color: QColor) -> None:
        self._color = color.toRgb()
        self._alpha_hex_row.set_color(color)
        self.color_changed.emit(color)

    def _alpha_hex_changed(self, color: QColor) -> None:
        self._color = color.toRgb()
        typed_control: ColorControl = self._control  # type: ignore[assignment]
        typed_control.set_color(color)
        self.color_changed.emit(color)
