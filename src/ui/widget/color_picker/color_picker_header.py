"""The color picker's header: a caller's swatch widget, the current hex value, and the screen color pick button.

The header only displays. `TabbedColorPicker` connects its pick button and feeds it colors and screen picking
previews.
"""
from typing import Optional

from PySide6.QtCore import Qt, QPoint, QSize
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QBoxLayout, QLabel, QToolButton, QApplication

from src.ui.widget.color_picker.alpha_hex_row import format_hex_color
from src.util.shared_constants import PROJECT_DIR

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.widget.color_picker.color_picker_header'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


PICK_SCREEN_COLOR_TOOLTIP = _tr('Pick a color from anywhere on the screen')
PICK_SCREEN_COLOR_INFO = _tr('Cursor at {x},{y}\nClick to pick, or press Esc to cancel')
HEX_LABEL_TOOLTIP = _tr('Current color, as a hex code')

ICON_PATH_PICK_SCREEN_COLOR = f'{PROJECT_DIR}/resources/icons/tools/eyedropper_icon.svg'
PICK_BUTTON_ICON_SIZE = 24


class ColorPickerHeader(QWidget):
    """The color picker's header: a caller's swatch widget, the current hex value, and the screen color pick button."""

    def __init__(self, swatch_widget: Optional[QWidget] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        layout.addLayout(self._row)
        self._swatch_widget = swatch_widget
        if swatch_widget is not None:
            swatch_widget.setParent(self)
            self._row.addWidget(swatch_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        self._hex_label = QLabel(self)
        self._hex_label.setToolTip(HEX_LABEL_TOOLTIP)
        self._hex_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._row.addWidget(self._hex_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self._row.addStretch(1)

        self._pick_button = QToolButton(self)
        self._pick_button.setIcon(QIcon(ICON_PATH_PICK_SCREEN_COLOR))
        self._pick_button.setIconSize(QSize(PICK_BUTTON_ICON_SIZE, PICK_BUTTON_ICON_SIZE))
        self._pick_button.setToolTip(PICK_SCREEN_COLOR_TOOLTIP)
        self._row.addWidget(self._pick_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self._picking_label = QLabel(self)
        self._picking_label.setVisible(False)
        layout.addWidget(self._picking_label)
        self.set_color(QColor(Qt.GlobalColor.black))

    @property
    def pick_button(self) -> QToolButton:
        """The button that starts screen color picking."""
        return self._pick_button

    @property
    def hex_label(self) -> QLabel:
        """The current color's hex value."""
        return self._hex_label

    @property
    def picking_label(self) -> QLabel:
        """The screen picking cursor position, shown only while picking."""
        return self._picking_label

    def set_color(self, color: QColor) -> None:
        """Shows the current color's hex value."""
        self._hex_label.setText(format_hex_color(color))

    def set_vertical(self, vertical: bool) -> None:
        """Stacks the swatch widget, hex value and pick button in a column, or lines them up in a row."""
        self._row.setDirection(QBoxLayout.Direction.TopToBottom if vertical else QBoxLayout.Direction.LeftToRight)

    def show_picking_preview(self, pos: QPoint, unused_color: QColor) -> None:
        """Shows the cursor position while picking a screen color."""
        self._picking_label.setText(PICK_SCREEN_COLOR_INFO.format(x=pos.x(), y=pos.y()))
        self._picking_label.setVisible(True)

    def clear_picking_preview(self) -> None:
        """Hides the cursor position once screen picking ends."""
        self._picking_label.setText('')
        self._picking_label.setVisible(False)
