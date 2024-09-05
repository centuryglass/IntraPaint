"""Slider meant specifically for picking color luminance."""
from typing import Optional, Any, cast

import numpy as np
from PySide6.QtGui import Qt, QPaintEvent, QMouseEvent, QPixmap, QImage, QColor, QPainter, QPolygon
from PySide6.QtCore import Signal, QRect, QPoint
from PySide6.QtWidgets import QWidget, qDrawShadePanel

from src.util.math_utils import clamp

FRAME_OFFSET = 3
CONTENT_OFFSET = 2


class HsvValuePicker(QWidget):
    """Slider meant specifically for picking color luminance, ported from the Qt library's internal
     QColorLuminancePicker found within QColorDialog."""

    value_changed = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self._val = 100
        self._hue = 100
        self._sat = 100
        self._pixmap: Optional[QPixmap] = None
        self._input_enabled = True

    def set_input_enabled(self, enabled: bool) -> None:
        """Set whether mouse input will change color values."""
        self._input_enabled = enabled

    def set_color(self, hue: int, saturation: int, value: Optional[int]):
        """Updates the widget's current color."""
        if value is None:
            value = self._val
        value_changed = self._val != value
        color_changed = self._hue != hue or self._val != value
        if not value_changed and not color_changed:
            return
        self._hue = hue
        self._sat = saturation
        self._val = value
        if color_changed:
            self._pixmap = None
        self.repaint()

    def paintEvent(self, event: Optional[QPaintEvent]) -> None:
        """Draw the slider, using current hue and saturation."""
        assert event is not None
        w = self.width() - 5
        r = QRect(0, FRAME_OFFSET, w, self.height() - 2 * FRAME_OFFSET)
        wi = r.width() - 2
        hi = r.height() - 2
        if self._pixmap is None or self._pixmap.isNull() or self._pixmap.width() != wi or self._pixmap.height() != hi:
            image = QImage(wi, hi, QImage.Format.Format_ARGB32_Premultiplied)
            np_image: np.ndarray[Any, np.dtype[np.uint8]] = np.ndarray(shape=(image.height(), image.width(), 4),
                                                                       dtype=np.uint8, buffer=image.bits())
            for y in range(hi):
                color = QColor.fromHsv(self._hue, self._sat, self._y2val(y + CONTENT_OFFSET)).toRgb()
                np_image[y, :, 0] = color.blue()
                np_image[y, :, 1] = color.green()
                np_image[y, :, 2] = color.red()
                np_image[y, :, 3] = 255
            self._pixmap = QPixmap(image)
        painter = QPainter(self)
        painter.drawPixmap(1, CONTENT_OFFSET, self._pixmap)
        palette = self.palette()
        qDrawShadePanel(painter, r, palette, True)
        painter.setPen(palette.windowText().color())
        painter.setBrush(palette.windowText())
        a = QPolygon()
        y = self._val2y(self._val)
        a.append(QPoint(w, y))
        a.append(QPoint(w + 5, y + 5))
        a.append(QPoint(w + 5, y - 5))
        painter.eraseRect(w, 0, 5, self.height())
        painter.drawPolygon(a)

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Change the value on click."""
        if not self._input_enabled:
            return
        assert event is not None
        if event.buttons() == Qt.MouseButton.LeftButton:
            self._set_value(self._y2val(event.y()))

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
        """Continue changing the value on click and drag."""
        if not self._input_enabled:
            return
        assert event is not None
        if event.buttons() == Qt.MouseButton.LeftButton:
            self._set_value(self._y2val(event.y()))

    def _y2val(self, y: int) -> int:
        d = self.height() - 2 * CONTENT_OFFSET - 1
        return int(clamp(int(255 - (y - CONTENT_OFFSET) * 255 / d), 0, 255))

    def _val2y(self, val: int) -> int:
        d = self.height() - 2 * CONTENT_OFFSET - 1
        return cast(int, CONTENT_OFFSET + (255 - val) * d / 255)

    def _set_value(self, val: int) -> None:
        val = cast(int, clamp(val, 0, 255))
        if val == self._val:
            return
        self._val = val
        self._pixmap = None
        self.repaint()
        self.value_changed.emit(val)
