"""Widget for selecting color values by HSV components."""
from typing import Optional

from PySide6.QtWidgets import QWidget, QHBoxLayout
from PySide6.QtCore import Signal, QPoint
from PySide6.QtGui import QColor, QResizeEvent

from src.ui.widget.color_picker.hs_box import HSBox
from src.ui.widget.color_picker.hsv_value_picker import HsvValuePicker
from src.ui.widget.color_picker.screen_color import ScreenColorWidget


class HsvPicker(QWidget):
    """Widget for selecting color values by HSV components."""

    color_selected = Signal(QColor)

    def __init__(self):
        super().__init__()
        self._layout = QHBoxLayout(self)
        self._color = QColor()
        self._hs_box = HSBox()
        self._layout.addWidget(self._hs_box)
        self._hs_box.color_values_chosen.connect(self._hs_change_slot)
        self._value_picker = HsvValuePicker()
        self._layout.addWidget(self._value_picker)
        self._value_picker.setMaximumWidth(20)
        self._value_picker.setMinimumWidth(20)
        self._value_picker.value_changed.connect(self._value_change_slot)

    def connect_screen_color_picker(self, screen_color_picker: ScreenColorWidget) -> None:
        """Connect signal handlers for a screen color picker."""
        screen_color_picker.started_color_picking.connect(self._started_color_picking_slot)
        screen_color_picker.stopped_color_picking.connect(self._stopped_color_picking_slot)
        screen_color_picker.color_previewed.connect(self._color_preview_slot)
        screen_color_picker.color_selected.connect(self._screen_color_selected_slot)

    def disconnect_screen_color_picker(self, screen_color_picker: ScreenColorWidget) -> None:
        """Disconnect signal handlers for a screen color picker."""
        screen_color_picker.started_color_picking.disconnect(self._started_color_picking_slot)
        screen_color_picker.stopped_color_picking.disconnect(self._stopped_color_picking_slot)
        screen_color_picker.color_previewed.disconnect(self._color_preview_slot)
        screen_color_picker.color_selected.disconnect(self._screen_color_selected_slot)

    @property
    def color(self) -> QColor:
        """Access the current selected color."""
        return self._color.toRgb()

    @color.setter
    def color(self, color: QColor) -> None:
        color = color.toHsv()
        if color == self._color:
            return
        self._color = color
        self._hs_box.color_values_chosen.disconnect(self._hs_change_slot)
        self._hs_box.set_components(color.hsvHue(), self._color.saturation())
        self._hs_box.color_values_chosen.connect(self._hs_change_slot)

        self._value_picker.value_changed.disconnect(self._value_change_slot)
        self._value_picker.set_color(self._color.hue(), self._color.saturation(), self._color.value())
        self._value_picker.value_changed.connect(self._value_change_slot)
        self.update()
        self.color_selected.emit(self.color)

    def _hs_change_slot(self, hue: int, saturation: int) -> None:
        if hue == self._color.hue() and saturation == self._color.saturation():
            return
        self.color = QColor.fromHsv(hue, saturation, self._color.value())

    def _value_change_slot(self, value: int) -> None:
        if value == self._color.value():
            return
        self.color = QColor.fromHsv(self._color.hue(), self._color.saturation(), value)

    def _started_color_picking_slot(self) -> None:
        self._hs_box.set_input_enabled(False)
        self._value_picker.set_input_enabled(False)

    def _color_preview_slot(self, pos: QPoint, color: QColor) -> None:
        hsv_image_bounds = self._hs_box.image_bounds.translated(self._hs_box.x(), self._hs_box.y())
        self._hs_box.set_draw_cross(hsv_image_bounds.contains(self.mapFromGlobal(pos)))
        hsv_color = color.toHsv()
        self._hs_box.set_components(hsv_color.hue(), hsv_color.saturation())
        self._value_picker.set_color(hsv_color.hue(), hsv_color.saturation(), hsv_color.value())

    def _screen_color_selected_slot(self, color: QColor) -> None:
        self._color = color

    def _stopped_color_picking_slot(self):
        self._hs_box.set_draw_cross(True)
        hsv_color = self._color.toHsv()
        self._hs_box.set_components(hsv_color.hue(), hsv_color.saturation())
        self._value_picker.set_color(hsv_color.hue(), hsv_color.saturation(), hsv_color.value())
        self._hs_box.set_input_enabled(True)
        self._value_picker.set_input_enabled(True)
