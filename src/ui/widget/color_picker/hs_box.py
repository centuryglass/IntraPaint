"""Display the full hue/saturation spectrum in a widget, show a selected color, allow color selection"""
from typing import Optional

from PySide6.QtCore import Signal, QPoint, QLine, QSize
from PySide6.QtGui import QImage, QPaintEvent, QPainter, QPen, Qt, QMouseEvent

from src.ui.widget.image_widget import ImageWidget
from src.util.display_size import get_window_size
from src.util.math_utils import clamp
from src.util.shared_constants import PROJECT_DIR

IMAGE_RESOURCE_HSV_BOX = f'{PROJECT_DIR}/resources/hsv_square.png'


class HSBox(ImageWidget):
    """Display the full hue/saturation spectrum in a widget, show a selected color, allow color selection"""

    color_values_chosen = Signal(float, float)

    def __init__(self):
        super().__init__(QImage(IMAGE_RESOURCE_HSV_BOX))
        self._hue = 0
        self._saturation = 0
        self._draw_cross = True
        self._input_enabled = True

    def sizeHint(self) -> QSize:
        """Set default size at 1/4 image size."""
        window_size = get_window_size()
        min_dim = min(window_size.width(), window_size.height())
        if min_dim > 1200:
            return QSize(320, 256)
        return QSize(160, 128)

    def set_draw_cross(self, should_draw: bool) -> None:
        """Set whether cross-hairs should be drawn over the selected color."""
        if should_draw != self._draw_cross:
            self._draw_cross = should_draw
            self.update()

    def set_input_enabled(self, enabled: bool) -> None:
        """Set whether mouse input will change color values."""
        self._input_enabled = enabled

    def set_components(self, hue: int, saturation: int) -> None:
        """Updates the widget's hue and saturation."""
        if hue == self._hue and saturation == self._saturation:
            return
        self._hue = hue
        self._saturation = saturation
        self.update()

    @property
    def hue(self) -> int:
        """Access the selected hue value."""
        return self._hue

    @hue.setter
    def hue(self, hue: int):
        assert 0 <= hue < 360
        if hue != self._hue:
            self._hue = hue
            self.color_values_chosen.emit(self._hue, self._saturation)
            self.update()

    @property
    def saturation(self) -> int:
        """Access the selected saturation value."""
        return self._saturation

    @saturation.setter
    def saturation(self, saturation: int) -> None:
        assert 0 <= saturation < 256
        if saturation != self._saturation:
            self._saturation = saturation
            self.color_values_chosen.emit(self._hue, self._saturation)
            self.update()

    def paintEvent(self, event: Optional[QPaintEvent]) -> None:
        """Draws the image scaled to widget size, draw cross-hairs over the selection."""
        super().paintEvent(event)
        paint_bounds = self.image_bounds
        hue_x = paint_bounds.x() + clamp(round((1.0 - self._hue / 359) * paint_bounds.width()), 0,
                                         paint_bounds.width() - 1)
        sat_y = paint_bounds.y() + clamp(round((1.0 - self._saturation / 255) * paint_bounds.height()), 0,
                                         paint_bounds.height() - 1)
        if self._draw_cross:
            painter = QPainter(self)
            painter.setPen(QPen(Qt.GlobalColor.white, 3))
            painter.drawLine(QLine(hue_x - 5, sat_y, hue_x + 5, sat_y))
            painter.drawLine(QLine(hue_x, sat_y - 5, hue_x, sat_y + 5))
            painter.setPen(QPen(Qt.GlobalColor.black, 1))
            painter.drawLine(QLine(hue_x - 5, sat_y, hue_x + 5, sat_y))
            painter.drawLine(QLine(hue_x, sat_y - 5, hue_x, sat_y + 5))
            painter.end()

    def _set_clicked_color(self, clicked_pt: QPoint):
        paint_bounds = self.image_bounds
        x = clamp(clicked_pt.x() - paint_bounds.x(), 0, paint_bounds.width())
        y = clamp(clicked_pt.y() - paint_bounds.y(), 0, paint_bounds.height())
        hue = clamp(int(round((1.0 - x / paint_bounds.width()) * 359)), 0, 359)
        sat = clamp(int(round((1.0 - y / paint_bounds.height()) * 255)), 0, 255)
        self.set_components(int(hue), int(sat))
        self.color_values_chosen.emit(self._hue, self._saturation)

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Select a new color when clicked."""
        assert event is not None
        if self._input_enabled and event.buttons() == Qt.MouseButton.LeftButton:
            self._set_clicked_color(event.pos())

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
        """Continue to set color if clicking and dragging."""
        assert event is not None
        if self._input_enabled and event.buttons() == Qt.MouseButton.LeftButton:
            self._set_clicked_color(event.pos())
