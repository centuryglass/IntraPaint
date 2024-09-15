"""
Canvas implementing smudge tool operations.
"""
import math
from typing import Optional, List

import numpy as np
from PySide6.QtCore import Qt, QPoint, QPointF, QRectF, QTimer, QRect, QLineF
from PySide6.QtGui import QPainter, QPen, QImage, QColor

from src.image.canvas.layer_canvas import LayerCanvas
from src.image.layers.image_layer import ImageLayer
from src.image.layers.selection_layer import SelectionLayer
from src.util.math_utils import clamp
from src.util.visual.image_utils import create_transparent_image, image_data_as_numpy_8bit, numpy_bounds_index, \
    NpUInt8Array

PAINT_BUFFER_DELAY_MS = 50
AVG_COUNT = 20


class SmudgeCanvas(LayerCanvas):
    """Draws content to an image layer using basic Qt drawing operations."""

    def __init__(self, layer: Optional[ImageLayer] = None) -> None:
        """Initialize a MyPaint surface, and connect to the image layer."""
        super().__init__(layer)
        self._opacity = 1.0
        self._hardness = 1.0
        self._last_point: Optional[QPoint] = None
        self._last_sizes: List[float] = []
        self._last_opacity: List[float] = []
        self._last_hardness: List[float] = []
        self._change_bounds = QRectF()
        self._input_buffer: List[QRect] = []
        self._buffer_timer = QTimer()
        self._buffer_timer.setInterval(PAINT_BUFFER_DELAY_MS)
        self._buffer_timer.setSingleShot(True)
        self._buffer_timer.timeout.connect(self._draw_buffered_events)
        self._brush_stroke_buffer = QImage()
        self._prev_image_buffer = QImage()
        self._paint_buffer = QImage()
        self._pressure_size = True
        self._pressure_opacity = False
        self._pressure_hardness = False

    @property
    def opacity(self) -> float:
        """Access the brush hardness fraction."""
        return self._opacity

    @opacity.setter
    def opacity(self, opacity: float) -> None:
        self._opacity = float(clamp(opacity, 0.0, 1.0))

    @property
    def hardness(self) -> float:
        """Access the brush hardness fraction."""
        return self._hardness

    @hardness.setter
    def hardness(self, hardness: float) -> None:
        self._hardness = float(clamp(hardness, 0.0, 1.0))

    @property
    def pressure_size(self) -> bool:
        """Access whether pressure data controls brush size."""
        return self._pressure_size

    @pressure_size.setter
    def pressure_size(self, pressure_sets_size: bool) -> None:
        self._pressure_size = pressure_sets_size

    @property
    def pressure_opacity(self) -> bool:
        """Access whether pressure data controls brush opacity."""
        return self._pressure_opacity

    @pressure_opacity.setter
    def pressure_opacity(self, pressure_sets_opacity: bool) -> None:
        self._pressure_opacity = pressure_sets_opacity

    @property
    def pressure_hardness(self) -> bool:
        """Access whether pressure data controls brush hardness."""
        return self._pressure_hardness

    @pressure_hardness.setter
    def pressure_hardness(self, pressure_sets_hardness: bool) -> None:
        self._pressure_hardness = pressure_sets_hardness

    def connect_to_layer(self, new_layer: Optional[ImageLayer]):
        """Disconnects from the current layer, and connects to a new one."""
        super().connect_to_layer(new_layer)
        if new_layer is not None:
            self._brush_stroke_buffer = create_transparent_image(new_layer.size)
            self._paint_buffer = create_transparent_image(new_layer.size)
        else:
            self._brush_stroke_buffer = QImage()
            self._paint_buffer = QImage()

    def start_stroke(self) -> None:
        self._change_bounds = QRectF()
        self._last_point = None
        self._last_sizes.clear()
        self._last_opacity.clear()
        self._last_hardness.clear()
        layer = self.layer
        assert layer is not None
        self._prev_image_buffer = layer.image
        super().start_stroke()

    def end_stroke(self) -> None:
        """Finishes a brush stroke, copying it back to the layer."""
        super().end_stroke()
        self._last_point = None
        self._draw_buffered_events()
        self._last_sizes.clear()
        self._last_opacity.clear()
        self._last_hardness.clear()
        if not self._brush_stroke_buffer.isNull():
            self._brush_stroke_buffer.fill(Qt.GlobalColor.transparent)

    def _draw_buffered_events(self) -> None:
        self._buffer_timer.stop()
        if len(self._input_buffer) == 0:
            return
        layer = self.layer
        if layer is None:
            return
        change_bounds = QRect()
        for rect in self._input_buffer:
            change_bounds = change_bounds.united(rect)
        change_bounds = change_bounds.intersected(layer.bounds)
        new_input_painter = QPainter(self._paint_buffer)
        with layer.borrow_image(change_bounds) as layer_image:
            img_painter = QPainter(layer_image)
            assert isinstance(layer_image, QImage)
            np_mask = None if self.input_mask is None else image_data_as_numpy_8bit(self.input_mask)
            np_paint_buf = image_data_as_numpy_8bit(self._paint_buffer)
            np_stroke_buf = image_data_as_numpy_8bit(self._brush_stroke_buffer)
            np_image = image_data_as_numpy_8bit(layer_image)
            np_prev_image = image_data_as_numpy_8bit(self._prev_image_buffer)
            for event in self._input_buffer:
                def _update_rolling_avg_list(values: List[float], new_value: float) -> None:
                    values.append(new_value)
                    while len(values) > AVG_COUNT:
                        values.pop(0)

                _update_rolling_avg_list(self._last_sizes, event.size)
                _update_rolling_avg_list(self._last_opacity, event.opacity)
                _update_rolling_avg_list(self._last_hardness, event.hardness)

                def _float_avg(values: List[float], default_value: float) -> float:
                    if len(values) == 0:
                        return default_value
                    value_sum = 0.0
                    for value in values:
                        value_sum += value
                    a = value_sum / len(values)
                    return a

                event.size = _float_avg(self._last_sizes, event.size)
                event.opacity = _float_avg(self._last_opacity, event.opacity)
                event.hardness = _float_avg(self._last_hardness, event.hardness)
                self._draw_input_event(event, new_input_painter, np_paint_buf, np_stroke_buf, np_mask, np_image,
                                       np_prev_image, img_painter)
            self._input_buffer.clear()
            img_painter.end()
        new_input_painter.end()

    def _point_rect(self, pos: QPoint, size: int) -> QRect:
        rect = QRect(0, 0, size, size)
        rect.moveCenter(pos)
        return rect

    def _draw(self, x: float, y: float, pressure: Optional[float], x_tilt: Optional[float],
              y_tilt: Optional[float]) -> None:
        """Use active settings to draw to the canvas with the given inputs."""
        layer = self.layer
        assert layer is not None
        if pressure is not None:
            size = round(self.brush_size * pressure)
        else:
            size = self.brush_size
        if self._last_point is None:
            self._input_buffer.append(self._point_rect(QPoint(round(x), round(y)), size))
        else:
            start = QPointF(self._last_point)
            end = QPointF(x, y)
            line = QLineF(start, end)
            length = line.length()
            last_x = -1
            last_y = -1
            for i in range(math.ceil(length)):
                line.setLength(i)
                xi = round(line.x2())
                yi = round(line.y2())
                if xi == last_x and yi == last_y:
                    continue
                self._input_buffer.append(self._point_rect(QPoint(xi, yi), size))
                last_x = xi
                last_y = yi
        self._last_point = QPointF(x, y)
        if not self._buffer_timer.isActive():
            self._buffer_timer.start()
