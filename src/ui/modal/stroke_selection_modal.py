"""Popup modal window that sets the width, color and position of the line Edit > Stroke selection draws.

Width and position start from their last confirmed values in `Cache`, and are saved back only when the stroke is
confirmed. The color starts as the foreground color each time.
"""
from typing import Optional

from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QApplication, QDialog, QFormLayout, QVBoxLayout, QWidget

from src.config.cache import Cache
from src.controller import color_controller
from src.image.layers.image_stack import StrokePosition
from src.ui.input_fields.field_factory import create_control_widget
from src.ui.input_fields.segmented_control import DisplayMode, SegmentedControl
from src.ui.modal.dialog_footer import DialogFooter
from src.ui.modal.modal_parent import modal_parent
from src.ui.widget.color_button import ColorButton
from src.util.layout import add_layout
from src.util.shared_constants import APP_ICON_PATH

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.modal.stroke_selection_modal'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


WINDOW_TITLE = _tr('Stroke selection')
COLOR_LABEL = _tr('Color:')
COLOR_BUTTON_TEXT = _tr('Select color')
COLOR_BUTTON_TOOLTIP = _tr('Select the color of the line')
POSITION_INSIDE = _tr('Inside')
POSITION_CENTER = _tr('Centered')
POSITION_OUTSIDE = _tr('Outside')
POSITION_INSIDE_TOOLTIP = _tr('Draw the line inside the selection edge.')
POSITION_CENTER_TOOLTIP = _tr('Center the line on the selection edge.')
POSITION_OUTSIDE_TOOLTIP = _tr('Draw the line outside the selection edge.')
STROKE_BUTTON_LABEL = _tr('Stroke selection')


class StrokeSelectionModal(QDialog):
    """Popup modal window that sets the width, color and position of a selection outline stroke."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(modal_parent(parent))
        self._confirmed = False
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setModal(True)
        cache = Cache()

        self._width_field = create_control_widget(cache, Cache.STROKE_SELECTION_WIDTH, connect_to_config=False)

        self._color_button = ColorButton(config_key=None, parent=self)
        self._color_button.setText(COLOR_BUTTON_TEXT)
        self._color_button.setToolTip(COLOR_BUTTON_TOOLTIP)
        self._color_button.color = color_controller.foreground()

        self._position_control = SegmentedControl.from_enum(
            StrokePosition,
            {StrokePosition.INSIDE: POSITION_INSIDE, StrokePosition.CENTER: POSITION_CENTER,
             StrokePosition.OUTSIDE: POSITION_OUTSIDE},
            tooltips={StrokePosition.INSIDE: POSITION_INSIDE_TOOLTIP, StrokePosition.CENTER: POSITION_CENTER_TOOLTIP,
                      StrokePosition.OUTSIDE: POSITION_OUTSIDE_TOOLTIP},
            display_mode=DisplayMode.LABEL, parent=self)
        self._position_control.set_value(cache.get(Cache.STROKE_SELECTION_POSITION))
        self._position_control.setToolTip(cache.get_tooltip(Cache.STROKE_SELECTION_POSITION))

        layout = QVBoxLayout(self)
        form = QFormLayout()
        add_layout(layout, form)
        form.addRow(cache.get_label(Cache.STROKE_SELECTION_WIDTH), self._width_field)
        form.addRow(COLOR_LABEL, self._color_button)
        form.addRow(cache.get_label(Cache.STROKE_SELECTION_POSITION), self._position_control)

        footer = DialogFooter(STROKE_BUTTON_LABEL, self)
        footer.accepted.connect(self._confirm)
        footer.rejected.connect(self.hide)

        layout.addStretch(1)
        layout.addWidget(footer)

    @property
    def stroke_width(self) -> int:
        """Returns the line width in pixels."""
        return int(self._width_field.value())

    @property
    def stroke_color(self) -> QColor:
        """Returns the line color."""
        return self._color_button.color

    @property
    def stroke_position(self) -> StrokePosition:
        """Returns where the line sits relative to the selection edge."""
        return StrokePosition(self._position_control.value())

    def _confirm(self) -> None:
        self._confirmed = True
        Cache().set(Cache.STROKE_SELECTION_WIDTH, self.stroke_width)
        Cache().set(Cache.STROKE_SELECTION_POSITION, self.stroke_position.value)
        self.hide()

    def show_stroke_modal(self) -> Optional[tuple[QColor, int, StrokePosition]]:
        """Shows this modal, returning the color, width and position if the stroke is confirmed."""
        self.exec()
        result = (self.stroke_color, self.stroke_width, self.stroke_position) if self._confirmed else None
        self.deleteLater()
        return result
