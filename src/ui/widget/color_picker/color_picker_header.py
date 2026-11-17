"""The color picker's header: a caller's swatch widget, an editable hex field, and the screen color pick button.

The header is the widget that grabs the mouse while picking a screen color, since it shows wherever the picker does. A
hex entry emits `color_entered`, and a screen pick emits `screen_color_picked`. Both are finished choices.

While picking with a live preview, a message below the row shows the cursor position. It wraps to the header's width,
so it never widens the header. The desktop portal's picker shows its own instructions, so it gets no message unless it
fails.
"""
from typing import Optional

from PySide6.QtCore import Qt, QPoint, QSize, Signal
from PySide6.QtGui import QColor, QIcon, QResizeEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QBoxLayout, QLabel, QToolButton, QApplication, QSizePolicy

from src.ui.widget.color_picker.hex_field import HexField
from src.ui.widget.color_picker.screen_color import ScreenColorWidget
from src.util.layout import add_layout
from src.util.shared_constants import PROJECT_DIR

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.widget.color_picker.color_picker_header'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


PICK_SCREEN_COLOR_TOOLTIP = _tr('Pick a color from anywhere on the screen')
PICK_SCREEN_COLOR_FAILED = _tr('Screen color picking failed: {reason}')
PICK_SCREEN_COLOR_INFO = _tr('Cursor at {x},{y}\nClick to pick, or press Esc to cancel')

ICON_PATH_PICK_SCREEN_COLOR = f'{PROJECT_DIR}/resources/icons/pick_color.svg'
PICK_BUTTON_ICON_SIZE = 24


class _WrappedMessage(QLabel):
    """A word-wrapped message that takes its width from its parent's layout and asks for every line it wraps to.

    A layout gives a wrapped label a height for its width, but measures only its one-line minimum, so a panel planned
    from minimum sizes would not leave room for the other lines. Its minimum height follows its width instead.
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWordWrap(True)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)

    def setText(self, text: str) -> None:  # pylint: disable=invalid-name
        """Shows new text, and asks for the height it wraps to."""
        super().setText(text)
        self._fit_height()

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:  # pylint: disable=invalid-name
        """Asks for the height the text wraps to at the new width."""
        super().resizeEvent(event)
        self._fit_height()

    def _fit_height(self) -> None:
        self.setMinimumHeight(self.heightForWidth(self.width()) if self.text() != '' else 0)


class ColorPickerHeader(ScreenColorWidget):
    """The color picker's header: a caller's swatch widget, an editable hex field, and the screen color pick button."""

    color_entered = Signal(QColor)

    def __init__(self, swatch_widget: Optional[QWidget] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__()
        if parent is not None:
            self.setParent(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        add_layout(layout, self._row)
        self._swatch_widget = swatch_widget
        if swatch_widget is not None:
            swatch_widget.setParent(self)
            self._row.addWidget(swatch_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        self._hex_field = HexField(self)
        self._hex_field.color_entered.connect(self.color_entered)
        self._row.addWidget(self._hex_field, alignment=Qt.AlignmentFlag.AlignCenter)
        self._row.addStretch(1)

        self._pick_button = QToolButton(self)
        self._pick_button.setIcon(QIcon(ICON_PATH_PICK_SCREEN_COLOR))
        self._pick_button.setIconSize(QSize(PICK_BUTTON_ICON_SIZE, PICK_BUTTON_ICON_SIZE))
        self._pick_button.setToolTip(PICK_SCREEN_COLOR_TOOLTIP)
        self._pick_button.clicked.connect(self._start_picking)
        self._row.addWidget(self._pick_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self._picking_label = _WrappedMessage(self)
        self._picking_label.setVisible(False)
        layout.addWidget(self._picking_label)
        self.color_previewed.connect(self._show_picking_preview)
        self.stopped_color_picking.connect(self._clear_picking_preview)
        self.color_picking_failed.connect(self._show_picking_failure)
        self.set_color(QColor(Qt.GlobalColor.black))

    @property
    def pick_button(self) -> QToolButton:
        """The button that starts screen color picking."""
        return self._pick_button

    @property
    def hex_field(self) -> HexField:
        """The current color's hex value, which accepts typed colors."""
        return self._hex_field

    @property
    def picking_label(self) -> QLabel:
        """The screen picking cursor position, shown only while picking."""
        return self._picking_label

    def set_color(self, color: QColor) -> None:
        """Shows the current color's hex value."""
        self._hex_field.set_color(color)

    def set_vertical(self, vertical: bool) -> None:
        """Stacks the swatch widget, hex field and pick button in a column, or lines them up in a row."""
        self._row.setDirection(QBoxLayout.Direction.TopToBottom if vertical else QBoxLayout.Direction.LeftToRight)

    def _start_picking(self) -> None:
        if not self.color_picking_active:
            self.start_screen_color_picking()

    def _show_picking_preview(self, pos: QPoint, unused_color: QColor) -> None:
        """Shows the cursor position while picking a screen color."""
        self._picking_label.setText(PICK_SCREEN_COLOR_INFO.format(x=pos.x(), y=pos.y()))
        self._picking_label.setVisible(True)

    def _show_picking_failure(self, reason: str) -> None:
        """Shows why the system color picker couldn't be used."""
        self._picking_label.setText(PICK_SCREEN_COLOR_FAILED.format(reason=reason))
        self._picking_label.setVisible(True)

    def _clear_picking_preview(self) -> None:
        """Hides the cursor position once screen picking ends."""
        self._picking_label.setText('')
        self._picking_label.setVisible(False)
