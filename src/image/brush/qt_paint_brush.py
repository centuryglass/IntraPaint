"""
Performs drawing operations on an image layer using basic Qt drawing operations.
"""
from typing import Optional, List

import numpy as np
from PySide6.QtCore import Qt, QPoint, QPointF, QRectF, QTimer, QRect
from PySide6.QtGui import QPainter, QPen, QImage, QColor, QBrush

from src.image.brush.layer_brush import LayerBrush
from src.image.layers.image_layer import ImageLayer
from src.image.layers.selection_layer import SelectionLayer
from src.util.math_utils import clamp
from src.util.visual.image_utils import create_transparent_image, image_data_as_numpy_8bit, numpy_bounds_index, \
    NpUInt8Array

PAINT_BUFFER_DELAY_MS = 50
AVG_COUNT = 20


class QtPaintBrush(LayerBrush):
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
        self._input_buffer: List[QtPaintBrush._InputEvent] = []
        self._buffer_timer = QTimer()
        self._buffer_timer.setInterval(PAINT_BUFFER_DELAY_MS)
        self._buffer_timer.setSingleShot(True)
        self._buffer_timer.timeout.connect(self._draw_buffered_events)
        self._brush_stroke_buffer = QImage()
        self._prev_image_buffer = QImage()
        self._paint_buffer = QImage()
        self._pattern_brush: Optional[QBrush] = None
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

    def set_pattern_brush(self, brush: Optional[QBrush]) -> None:
        """Sets a QBrush that defines the shape (but not color) of brush strokes."""
        self._pattern_brush = brush

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

    @staticmethod
    def paint_segment(painter: QPainter, size: int, opacity: float, hardness: float, color: QColor, change_pt: QPointF,
                      last_pt: Optional[QPointF]) -> None:
        """Paints a single segment from a brush stroke, without any blending between segments."""
        painter.save()
        painter.setOpacity(opacity)
        pen = QPen(color, size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        min_size = max(size * hardness, 1.0)
        size_range = round(size - min_size)
        if size_range > 0:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            alpha_step = opacity / size_range
            alpha = alpha_step
            size = size - 1
            while size >= min_size:
                pen.setWidth(size)
                painter.setOpacity(alpha)
                painter.setPen(pen)
                if last_pt is None:
                    painter.drawPoint(change_pt)
                else:
                    painter.drawLine(last_pt, change_pt)
                alpha += alpha_step
                size -= 1
        else:
            if last_pt is None:
                painter.drawPoint(change_pt)
            else:
                painter.drawLine(last_pt, change_pt)
        painter.restore()

    @staticmethod
    def _input_event_paint_segment(painter: QPainter, input_event: 'QtPaintBrush._InputEvent') -> None:
        QtPaintBrush.paint_segment(painter, round(input_event.size), input_event.opacity, input_event.hardness,
                                   input_event.color, input_event.change_pt, input_event.last_pt)

    def _draw_input_event(self,
                          input_event: 'QtPaintBrush._InputEvent',
                          new_input_painter: QPainter,
                          np_paint_buf: NpUInt8Array,
                          np_stroke_buf: NpUInt8Array,
                          np_mask: Optional[NpUInt8Array],
                          np_image: NpUInt8Array,
                          np_prev_image: NpUInt8Array,
                          layer_painter: QPainter):
        """
        Draws a single segment within a brush stroke. This applies size, opacity, and hardness, and blends the segment
        with previous sections in the brush stroke.

        Parameters:
        -----------
        input_event: 'QtPaintBrush._InputEvent:
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
        layer_painter: QPainter:
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
        np_prev_image = numpy_bounds_index(np_prev_image, bounds)
        np_image = numpy_bounds_index(np_image, bounds)
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

        # Add the last paint operation to stroke buffer:
        np_stroke_buf[changes, :] = np_paint_buf[changes, :]

        if self._pattern_brush is not None:
            # Apply the pattern to the brush stroke segment:
            new_input_painter.save()
            new_input_painter.setOpacity(1.0)
            new_input_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            new_input_painter.fillRect(bounds, self._pattern_brush)
            new_input_painter.restore()

        # Draw the last segment to the image:
        layer_image = layer_painter.device()
        assert isinstance(layer_image, QImage)
        self.draw_segment_to_image(self._paint_buffer, layer_image, layer_painter, bounds)

    def draw_segment_to_image(self, segment_image: QImage, layer_image: QImage, layer_painter: QPainter,
                              bounds: QRect) -> None:
        """Handles the final drawing operation that copies an input segment to the layer image."""
        if self.eraser:
            layer_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
        layer_painter.drawImage(bounds, segment_image, bounds)

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
        change_bounds = change_bounds.intersected(layer.bounds)
        new_input_painter = QPainter(self._paint_buffer)
        with layer.borrow_image(change_bounds) as layer_image:
            self._change_bounds = self._change_bounds.united(change_bounds)
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

    def _draw(self, x: float, y: float, pressure: Optional[float], x_tilt: Optional[float],
              y_tilt: Optional[float]) -> None:
        """Use active settings to draw with the brush using the given inputs."""
        layer = self.layer
        assert layer is not None
        input_event = QtPaintBrush._InputEvent(x, y, pressure, self.brush_size, self.brush_color, self._last_point,
                                               layer, self.opacity, self.hardness, self.pressure_size,
                                               self.pressure_opacity, self.pressure_hardness)
        self._last_point = QPointF(x, y)
        self._input_buffer.append(input_event)
        if not self._buffer_timer.isActive():
            self._buffer_timer.start()

    class _InputEvent:
        """Delayed drawing input event, buffered to decrease input lag."""

        def __init__(self, x: float, y: float, pressure: Optional[float], size: float, color: QColor,
                     last_point: Optional[QPointF], layer: ImageLayer, opacity: float, hardness: float,
                     pressure_size: bool, pressure_opacity: bool, pressure_hardness: bool) -> None:
            layer_bounds = layer.bounds
            self.layer = layer
            self.size = size
            self.opacity = opacity
            self.hardness = hardness
            if pressure is not None:
                if isinstance(layer, SelectionLayer) or pressure_size:
                    self.size = max(int(size * pressure), 1)
                if not isinstance(layer, SelectionLayer):
                    if pressure_opacity:
                        self.opacity = float(clamp(self.opacity * pressure, 0.0, 1.0))
                    if pressure_hardness:
                        self.hardness = float(clamp(self.hardness * pressure, 0.0, 1.0))

            self.change_pt = QPointF(x - layer_bounds.x(), y - layer_bounds.y())
            self.last_pt = None if last_point is None else QPointF(last_point.x() - layer_bounds.x(),
                                                                   last_point.y() - layer_bounds.y())
            self.change_bounds = QRectF(self.change_pt.x() - size, self.change_pt.y() - size, size * 2,
                                        size * 2).toAlignedRect()
            if self.last_pt is not None:
                self.change_bounds = self.change_bounds.united(QRectF(self.last_pt.x() - size, self.last_pt.y() - size,
                                                                      size * 2, size * 2).toAlignedRect())
            self.color = color
