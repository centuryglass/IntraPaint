"""
Performs drawing operations on an image layer using basic Qt drawing operations.
"""
import logging
import time
from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, QPoint, QPointF, QRectF, QTimer, QRect, QSize
from PySide6.QtGui import QPainter, QPen, QImage, QColor, QBrush

from src.image.brush.layer_brush import LayerBrush
from src.image.layers.image_layer import ImageLayer
from src.image.layers.selection_layer import SelectionLayer
from src.util.math_utils import clamp
from src.util.visual.image_utils import create_transparent_image, image_data_as_numpy_8bit, numpy_bounds_index, \
    NpUInt8Array, NpAnyArray

PAINT_BUFFER_DELAY_MS = 50

# Longest a mid-stroke draw should block the event loop. Events left over are drawn on the next event loop pass, so
# the window can repaint and take input during a long stroke.
MAX_DRAW_SECONDS = 0.025
INITIAL_EVENTS_PER_DRAW = 8

# Number of recent input events whose size, opacity and hardness are averaged, smoothing out abrupt pressure changes:
AVG_COUNT = 20
BUFFER_BASE_MARGINS = 256
logger = logging.getLogger(__name__)


def _rolling_average(recent_values: list[float], new_value: float) -> float:
    """Adds a value to a list of the last AVG_COUNT values, and returns their average."""
    recent_values.append(new_value)
    if len(recent_values) > AVG_COUNT:
        del recent_values[0]
    value_sum = 0.0
    # sum() uses compensated float summation, which would change brush output:
    for value in recent_values:
        value_sum += value
    return value_sum / len(recent_values)


def _argb_pixels(np_image: NpUInt8Array) -> NpAnyArray:
    """Returns a 2D uint32 view of an ARGB image array, one element per pixel, so whole pixels can be copied with 2D
       masks."""
    return np_image.view(np.uint32)[:, :, 0]


class QtPaintBrush(LayerBrush):
    """Draws content to an image layer using basic Qt drawing operations."""

    def __init__(self, layer: Optional[ImageLayer] = None) -> None:
        """Initializes stroke buffers and settings, then connects to the image layer if one is given."""
        self._opacity = 1.0
        self._hardness = 1.0
        self._last_point: Optional[QPoint] = None
        self._last_sizes: list[float] = []
        self._last_opacity: list[float] = []
        self._last_hardness: list[float] = []
        self._change_bounds = QRectF()
        self._input_buffer: list[QtPaintBrush._InputEvent] = []
        self._buffer_timer = QTimer()
        self._buffer_timer.setSingleShot(True)
        self._buffer_timer.timeout.connect(self._draw_buffered_events)
        self._events_per_draw = INITIAL_EVENTS_PER_DRAW
        self._brush_stroke_buffer = QImage()
        self._prev_image_buffer = QImage()
        self._paint_buffer = QImage()
        self._image_buffer_bounds = QRect()
        self._pattern_brush: Optional[QBrush] = None
        self._pressure_size = True
        self._pressure_opacity = False
        self._pressure_hardness = False
        self._antialiasing = False
        # LayerBrush.__init__ calls connect_to_layer, which replaces the buffers above, so it must run last.
        super().__init__(layer)

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

    @property
    def antialiasing(self) -> bool:
        """Access whether antialiasing is applied to brush strokes."""
        return self._antialiasing

    @antialiasing.setter
    def antialiasing(self, antialias: bool) -> None:
        self._antialiasing = antialias

    def set_pattern_brush(self, brush: Optional[QBrush]) -> None:
        """Sets a QBrush that defines the shape (but not color) of brush strokes."""
        self._pattern_brush = brush

    def connect_to_layer(self, new_layer: Optional[ImageLayer]):
        """Disconnects from the current layer, and connects to a new one."""
        last_layer = self.layer
        if last_layer is not None:
            last_layer.size_changed.disconnect(self._layer_size_change_slot)
        super().connect_to_layer(new_layer)
        self._image_buffer_bounds = QRect()
        if new_layer is not None:
            layer_size = new_layer.size
            self._brush_stroke_buffer = QImage(layer_size, QImage.Format.Format_ARGB32_Premultiplied)
            self._paint_buffer = QImage(layer_size, QImage.Format.Format_ARGB32_Premultiplied)
            self._prev_image_buffer = QImage(layer_size, QImage.Format.Format_ARGB32_Premultiplied)
            new_layer.size_changed.connect(self._layer_size_change_slot)
        else:
            self._brush_stroke_buffer = QImage()
            self._paint_buffer = QImage()
            self._prev_image_buffer = QImage()
        if self.drawing:
            self._cancel_stroke()

    def _layer_size_change_slot(self, layer: ImageLayer, size: QSize) -> None:
        if layer != self.layer:
            layer.size_changed.disconnect(self._layer_size_change_slot)
            return
        layer_size = size
        self._brush_stroke_buffer = QImage(layer_size, QImage.Format.Format_ARGB32_Premultiplied)
        self._paint_buffer = QImage(layer_size, QImage.Format.Format_ARGB32_Premultiplied)
        self._prev_image_buffer = QImage(layer_size, QImage.Format.Format_ARGB32_Premultiplied)
        self._image_buffer_bounds = QRect()
        if self.drawing:
            self._cancel_stroke()

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
        self._change_bounds = QRectF()
        self._image_buffer_bounds = QRect()

    def _cancel_stroke(self) -> None:
        """Cancels an in-progress brush stroke, ensuring we don't enter into an error state if layer changes happen
           mid-stroke."""
        self._input_buffer.clear()
        self.end_stroke()

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
            while size >= min_size:
                pen.setWidth(size)
                painter.setOpacity(alpha)
                painter.setPen(pen)
                if last_pt is None:
                    painter.drawPoint(change_pt)
                else:
                    painter.drawLine(last_pt, change_pt)
                alpha = min(alpha + alpha_step, opacity)
                size -= 1
        else:
            if last_pt is None:
                painter.drawPoint(change_pt)
            else:
                painter.drawLine(last_pt, change_pt)
        painter.restore()

    def _input_event_paint_segment(self, painter: QPainter, input_event: 'QtPaintBrush._InputEvent') -> None:
        QtPaintBrush.paint_segment(painter, round(input_event.size), input_event.opacity, input_event.hardness,
                                   input_event.color, input_event.change_pt, input_event.last_pt)

    def _update_image_buffer_bounds(self) -> None:
        # To avoid excessive image copying, refresh buffer contents as change bounds adjust.
        assert self.layer is not None
        layer_size = self.layer.size
        if self._change_bounds.isNull() or layer_size.isNull():
            self._image_buffer_bounds = QRect()
            return
        if self._image_buffer_bounds.contains(self._change_bounds.toAlignedRect()):
            return

        layer_bounds = QRect(0, 0, layer_size.width(), layer_size.height())
        new_buffer_bounds = self._change_bounds.adjusted(-BUFFER_BASE_MARGINS, -BUFFER_BASE_MARGINS,
                                                         BUFFER_BASE_MARGINS, BUFFER_BASE_MARGINS
                                                         ).intersected(layer_bounds).toAlignedRect()
        if not self._image_buffer_bounds.isNull():
            if self._image_buffer_bounds.contains(new_buffer_bounds):
                return
            new_buffer_bounds = new_buffer_bounds.united(self._image_buffer_bounds)
        np_stroke_buffer = numpy_bounds_index(image_data_as_numpy_8bit(self._brush_stroke_buffer), new_buffer_bounds)
        np_paint_buffer = numpy_bounds_index(image_data_as_numpy_8bit(self._paint_buffer), new_buffer_bounds)
        np_prev_image_buffer = numpy_bounds_index(image_data_as_numpy_8bit(self._prev_image_buffer), new_buffer_bounds)
        if not self._image_buffer_bounds.isNull():
            # Buffers are expanding, update edge content:
            old_buffer_local_bounds = self._image_buffer_bounds.translated(-new_buffer_bounds.topLeft())

            old_bottom_local = old_buffer_local_bounds.y() + old_buffer_local_bounds.height()
            old_right_local = old_buffer_local_bounds.x() + old_buffer_local_bounds.width()
            top_edge = QRect(0, 0, new_buffer_bounds.width(), old_buffer_local_bounds.y())
            bottom_edge = QRect(0, old_bottom_local,
                                new_buffer_bounds.width(), new_buffer_bounds.height() - old_bottom_local)
            left_right_y = top_edge.y() + top_edge.height()
            left_right_height = bottom_edge.y() - left_right_y
            left_edge = QRect(0, left_right_y, old_buffer_local_bounds.x(), left_right_height)
            right_edge = QRect(old_right_local, left_right_y, new_buffer_bounds.width() - old_right_local,
                               left_right_height)
            for draw_buffer in (np_stroke_buffer, np_paint_buffer):
                for edge_rect in (top_edge, bottom_edge, left_edge, right_edge):
                    if edge_rect.isEmpty():
                        continue
                    buffer_edge = numpy_bounds_index(draw_buffer, edge_rect)
                    buffer_edge[:, :, :] = 0
            assert self.layer is not None
            with self.layer.borrow_image(new_buffer_bounds) as layer_image:
                np_image = image_data_as_numpy_8bit(layer_image)
                np_image = numpy_bounds_index(np_image, new_buffer_bounds)
                for edge_rect in (top_edge, bottom_edge, left_edge, right_edge):
                    if edge_rect.isEmpty():
                        continue
                    image_edge = numpy_bounds_index(np_image, edge_rect)
                    buffer_edge = numpy_bounds_index(np_prev_image_buffer, edge_rect)
                    buffer_edge[:, :, :] = image_edge[:, :, :]
        else:
            # Initializing buffers for the first time this brush stroke:
            for draw_buffer in (np_stroke_buffer, np_paint_buffer):
                draw_buffer[:, :, :] = 0
            assert self.layer is not None
            with self.layer.borrow_image(new_buffer_bounds) as layer_image:
                np_image = image_data_as_numpy_8bit(layer_image)
                np_image = numpy_bounds_index(np_image, new_buffer_bounds)
                np_prev_image_buffer[:, :, :] = np_image[:, :, :]
        self._image_buffer_bounds = new_buffer_bounds

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
        layer = self.layer
        assert layer is not None
        layer_bounds = layer.bounds
        if (layer_bounds.y() + layer_bounds.height()) != np_image.shape[0] \
                or (layer_bounds.x() + layer_bounds.width()) != np_image.shape[1]:
            logger.error(f'bounds mismatch: layer image is shape {np_image.shape}, but layer bounds'
                         f' are {layer_bounds}')
            return
        bounds = input_event.change_bounds.intersected(layer_bounds)
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

        new_input_painter.setRenderHint(QPainter.RenderHint.Antialiasing, self._antialiasing)
        self._input_event_paint_segment(new_input_painter, input_event)

        # Find the pixels this segment changes. Pixels outside the input mask are never changed.
        changes = np_paint_buf[:, :, 3] > 0
        if np_mask is not None:
            changes &= np_mask[:, :, 3] > 0
        if not np.any(changes):
            return

        # If opacity or hardness is less than 1, segments in the same stroke don't build up opacity where they
        # overlap: each pixel keeps whichever segment drew it with the highest alpha. Where this segment wins, the
        # layer pixel is reset to its state before the stroke, so the segment replaces earlier ones.
        if (input_event.color.alphaF() * input_event.opacity) < 1.0 or input_event.hardness < 1.0:
            changes &= np_paint_buf[:, :, 3] >= np_stroke_buf[:, :, 3]
            np.copyto(_argb_pixels(np_image), _argb_pixels(np_prev_image), where=changes)

        # Clear unchanged pixels from the paint buffer, and add the changes to the stroke buffer:
        paint_pixels = _argb_pixels(np_paint_buf)
        np.copyto(paint_pixels, 0, where=~changes)
        np.copyto(_argb_pixels(np_stroke_buf), paint_pixels, where=changes)

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
        """Draws buffered input events to the layer.

        Mid-stroke, this draws about MAX_DRAW_SECONDS worth of events and schedules the rest for the next event loop
        pass. Once the stroke has ended, it draws every buffered event.
        """
        self._buffer_timer.stop()
        layer = self.layer
        if len(self._input_buffer) == 0 or layer is None:
            return
        if self.drawing:
            event_count = min(len(self._input_buffer), self._events_per_draw)
        else:
            event_count = len(self._input_buffer)
        start_time = time.perf_counter()
        self._draw_events(layer, self._input_buffer[:event_count])
        del self._input_buffer[:event_count]
        if self.drawing:
            elapsed = max(time.perf_counter() - start_time, 1e-6)
            self._events_per_draw = max(1, int(event_count * MAX_DRAW_SECONDS / elapsed))
            if len(self._input_buffer) > 0:
                self._buffer_timer.start(0)

    def _draw_events(self, layer: ImageLayer, events: list['QtPaintBrush._InputEvent']) -> None:
        """Smooths size, opacity and hardness over recent events, then draws a sequence of events to the layer,
           continuing the current stroke."""
        for event in events:
            event.size = _rolling_average(self._last_sizes, event.size)
            event.opacity = _rolling_average(self._last_opacity, event.opacity)
            event.hardness = _rolling_average(self._last_hardness, event.hardness)
        change_bounds = QRect()
        for event in events:
            change_bounds = change_bounds.united(event.change_bounds)
        change_bounds = change_bounds.intersected(layer.bounds)
        if change_bounds.isEmpty():
            return
        new_input_painter = QPainter(self._paint_buffer)
        with layer.borrow_image(change_bounds) as layer_image:
            assert isinstance(layer_image, QImage)
            bounds = layer.bounds
            assert layer_image.size() == bounds.size(), (f'Size mismatch, layer bounds are {bounds} but'
                                                         f' image is size {layer_image.size()}')
            self._change_bounds = self._change_bounds.united(change_bounds)
            self._update_image_buffer_bounds()
            img_painter = QPainter(layer_image)
            np_mask = None if self.input_mask is None else image_data_as_numpy_8bit(self.input_mask)
            np_paint_buf = image_data_as_numpy_8bit(self._paint_buffer)
            np_stroke_buf = image_data_as_numpy_8bit(self._brush_stroke_buffer)
            np_image = image_data_as_numpy_8bit(layer_image)
            np_prev_image = image_data_as_numpy_8bit(self._prev_image_buffer)
            for event in events:
                self._draw_input_event(event, new_input_painter, np_paint_buf, np_stroke_buf, np_mask, np_image,
                                       np_prev_image, img_painter)
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
            self._buffer_timer.start(PAINT_BUFFER_DELAY_MS)

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
