"""
Performs drawing operations on an image layer using basic Qt drawing operations.
"""
from typing import Optional, List

import numpy as np
from PySide6.QtCore import Qt, QPoint, QPointF, QRectF, QTimer, QRect
from PySide6.QtGui import QPainter, QPen, QImage, QColor

from src.config.cache import Cache
from src.image.canvas.layer_canvas import LayerCanvas
from src.image.layers.image_layer import ImageLayer
from src.image.layers.selection_layer import SelectionLayer
from src.util.math_utils import clamp
from src.util.visual.image_utils import create_transparent_image, image_data_as_numpy_8bit, numpy_bounds_index, \
    NpUInt8Array

PAINT_BUFFER_DELAY_MS = 50
AVG_COUNT = 20


class QtPaintCanvas(LayerCanvas):
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
        self._mask: Optional[QImage] = None
        self._input_buffer: List[QtPaintCanvas._InputEvent] = []
        self._buffer_timer = QTimer()
        self._buffer_timer.setInterval(PAINT_BUFFER_DELAY_MS)
        self._buffer_timer.setSingleShot(True)
        self._buffer_timer.timeout.connect(self._draw_buffered_events)
        self._brush_stroke_buffer = QImage()
        self._prev_image_buffer = QImage()
        self._paint_buffer = QImage()

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
        self._prev_image_buffer = self.layer.image
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

    def set_input_mask(self, mask_image: Optional[QImage]) -> None:
        """Sets a mask image, restricting canvas changes to areas covered by non-transparent mask areas"""
        self._mask = mask_image

    @staticmethod
    def _input_event_paint_segment(painter: QPainter, input_event: 'QtPaintCanvas._InputEvent') -> None:
        """Paints a single segment from a brush stroke, without any blending."""
        painter.save()
        painter.setOpacity(input_event.opacity)
        pen = QPen(input_event.color, input_event.size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                   Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        if input_event.hardness < 1.0:
            min_size = input_event.size * input_event.hardness
            size_range = round(input_event.size - min_size)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            alpha_step = input_event.opacity / size_range
            alpha = alpha_step
            size = input_event.size - 1
            while size >= min_size:
                pen.setWidth(size)
                painter.setOpacity(alpha)
                painter.setPen(pen)
                if input_event.last_pt is None:
                    painter.drawPoint(input_event.change_pt)
                else:
                    painter.drawLine(input_event.last_pt, input_event.change_pt)
                alpha += alpha_step
                size -= 1
        else:
            if input_event.last_pt is None:
                painter.drawPoint(input_event.change_pt)
            else:
                painter.drawLine(input_event.last_pt, input_event.change_pt)
        painter.restore()

    def _draw_input_event(self,
                          input_event: 'QtPaintCanvas._InputEvent',
                          new_input_painter: QPainter,
                          np_paint_buf: NpUInt8Array,
                          np_stroke_buf: NpUInt8Array,
                          np_mask: Optional[NpUInt8Array],
                          np_image: NpUInt8Array,
                          np_prev_image: NpUInt8Array,
                          img_painter: QPainter):
        """
        Draws a single segment within a brush stroke. This applies size, opacity, and hardness, and blends the segment
        with previous sections in the brush stroke.

        Parameters:
        -----------
        input_event: 'QtPaintCanvas._InputEvent:
            The segment or point to draw, along with associated drawing data.
        new_input_painter: QPainter:
            Painter used to draw the segment onto the paint buffer.
        np_paint_buf: NpUInt8Array:
            The paint buffer is a temporary image used to hold the most recent segment in the brush stroke, used
            to help blend the segment with previous segments
        np_stroke_buf: NpUInt8Array:
            The stroke buffer is a temporary image holding all previous segments in the brush stroke, also used for
            blending.
        np_mask: Optional[NpUInt8Array]:
            An optional input mask, used when painting is only allowed in selected regions.
        np_image: NpUInt8Array:
            The final layer image that we're drawing into.
        np_prev_image: NpUInt8Array:
            A copy of the layer image, taken before the first segment in the brush stroke was drawn.
        img_painter: QPainter:
            Painter used to draw the final adjusted segment onto the layer image.
        """
        if input_event.opacity == 0 or input_event.size == 0:
            return

        # Only operate on numpy images within the change bounds:
        bounds = input_event.change_bounds.intersected(QRect(QPoint(), self._paint_buffer.size()))
        if bounds.isEmpty():
            return
        np_paint_buf = numpy_bounds_index(np_paint_buf, bounds)
        np_stroke_buf = numpy_bounds_index(np_stroke_buf, bounds)
        np_image = numpy_bounds_index(np_image, bounds)
        np_prev_image = numpy_bounds_index(np_prev_image, bounds)
        if np_mask is not None:
            np_mask = numpy_bounds_index(np_mask, bounds)

        # Make sure the paint buffer is clear, draw the most recent segment in the brush stroke:
        np_paint_buf[:, :, :] = 0
        self._input_event_paint_segment(new_input_painter, input_event)

        # find changed pixels.  If a mask is set, remove all changes not covered by the mask.
        changes = np_paint_buf[:, :, 3] > 0
        masked = None if np_mask is None else np_mask[:, :, 3] > 0
        if masked is not None:
            np_paint_buf[changes & ~masked, :] = 0
            changes = changes & masked
        if not np.any(changes):
            return

        # If opacity or hardness is less than 1, handle the overlapping regions:
        if (input_event.color.alphaF() * input_event.opacity) < 1.0 or input_event.hardness < 1.0:
            # For all pixels where np_paint_buf and np_stroke_buf buf overlap, find out which has the highest alpha:
            paint_buf_overrides = changes & (np_paint_buf[:, :, 3] >= np_stroke_buf[:, :, 3])
            stroke_buf_overrides = changes & (np_stroke_buf[:, :, 3] > np_paint_buf[:, :, 3])

            # If paint_buf has higher alpha, clear that pixel in stroke_buf, and reset it to np_prev_image in np_image.
            np_stroke_buf[paint_buf_overrides, :] = 0
            np_image[paint_buf_overrides, :] = np_prev_image[paint_buf_overrides, :]

            # If stroke_buf has higher alpha, clear that pixel in paint_buf.
            np_paint_buf[stroke_buf_overrides, :] = 0
            changes = changes & ~stroke_buf_overrides

        # Draw the last segment to the image:
        if self.eraser:
            img_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
        img_painter.drawImage(bounds, self._paint_buffer, bounds)
        # Add the last paint operation to stroke buffer:
        np_stroke_buf[changes, :] = np_paint_buf[changes, :]

    def _draw_buffered_events(self) -> None:
        self._buffer_timer.stop()
        if len(self._input_buffer) == 0:
            return
        layer = self.layer
        if layer is None:
            return
        change_bounds = QRect()
        for event in self._input_buffer:
            change_bounds = change_bounds.united(event.change_bounds)
        change_bounds = change_bounds.intersected(self.layer.bounds)
        new_input_painter = QPainter(self._paint_buffer)
        with layer.borrow_image(change_bounds) as layer_image:
            img_painter = QPainter(layer_image)
            assert isinstance(layer_image, QImage)
            np_mask = None if self._mask is None else image_data_as_numpy_8bit(self._mask)
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

    def _draw(self, x: float, y: float, pressure: Optional[float], x_tilt: Optional[float],
              y_tilt: Optional[float]) -> None:
        """Use active settings to draw to the canvas with the given inputs."""
        layer = self.layer
        assert layer is not None
        input_event = QtPaintCanvas._InputEvent(x, y, pressure, self.brush_size, self.brush_color, self._last_point,
                                                layer, self.opacity, self.hardness)
        self._last_point = QPointF(x, y)
        self._input_buffer.append(input_event)
        if not self._buffer_timer.isActive():
            self._buffer_timer.start()

    class _InputEvent:
        """Delayed drawing input event, buffered to decrease input lag."""

        def __init__(self, x: float, y: float, pressure: Optional[float], size: float, color: QColor,
                     last_point: Optional[QPointF], layer: ImageLayer, opacity: float, hardness: float) -> None:
            layer_bounds = layer.bounds
            self.layer = layer
            self.size = size
            self.opacity = opacity
            self.hardness = hardness
            if pressure is not None:
                if isinstance(layer, SelectionLayer) or Cache().get(Cache.DRAW_TOOL_PRESSURE_SIZE):
                    self.size = max(int(size * pressure), 1)
                if not isinstance(layer, SelectionLayer):
                    if Cache().get(Cache.DRAW_TOOL_PRESSURE_OPACITY):
                        self.opacity = float(clamp(self.opacity * pressure, 0.0, 1.0))
                    if Cache().get(Cache.DRAW_TOOL_PRESSURE_HARDNESS):
                        self.hardness = float(clamp(self.opacity * pressure, 0.0, 1.0))

            self.change_pt = QPointF(x - layer_bounds.x(), y - layer_bounds.y())
            self.last_pt = None if last_point is None else QPointF(last_point.x() - layer_bounds.x(),
                                                                   last_point.y() - layer_bounds.y())
            self.change_bounds = QRectF(self.change_pt.x() - size, self.change_pt.y() - size, size * 2,
                                        size * 2).toAlignedRect()
            if self.last_pt is not None:
                self.change_bounds = self.change_bounds.united(QRectF(self.last_pt.x() - size, self.last_pt.y() - size,
                                                                      size * 2, size * 2).toAlignedRect())
            self.color = color
