"""
Performs drawing operations on an image layer using basic Qt drawing operations.
"""
from typing import Optional, List

from PySide6.QtCore import Qt, QPoint, QPointF, QRectF, QTimer, QRect, QLineF
from PySide6.QtGui import QPainter, QPen, QTransform, QImage, QColor, QBrush, QLinearGradient, QRadialGradient

from src.config.cache import Cache
from src.image.canvas.layer_canvas import LayerCanvas
from src.image.layers.image_layer import ImageLayer
from src.image.layers.selection_layer import SelectionLayer
from src.util.math_utils import clamp
from src.util.visual.image_utils import create_transparent_image, image_data_as_numpy_8bit, numpy_bounds_index

PAINT_BUFFER_DELAY_MS = 50
SIZE_AVG_COUNT = 10


class QtPaintCanvas(LayerCanvas):
    """Draws content to an image layer using basic Qt drawing operations."""

    def __init__(self, layer: Optional[ImageLayer] = None) -> None:
        """Initialize a MyPaint surface, and connect to the image layer."""
        super().__init__(layer)
        self._opacity = 1.0
        self._hardness = 1.0
        self._last_point: Optional[QPoint] = None
        self._last_sizes: List[float] = []
        self._change_bounds = QRectF()
        self._mask: Optional[QImage] = None
        self._input_buffer: List[QtPaintCanvas._InputEvent] = []
        self._buffer_timer = QTimer()
        self._buffer_timer.setInterval(PAINT_BUFFER_DELAY_MS)
        self._buffer_timer.setSingleShot(True)
        self._buffer_timer.timeout.connect(self._draw_buffered_events)
        self._brush_stroke_buffer = QImage()
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
        super().start_stroke()

    def end_stroke(self) -> None:
        """Finishes a brush stroke, copying it back to the layer."""
        super().end_stroke()
        self._last_point = None
        self._last_sizes.clear()
        self._draw_buffered_events()
        if not self._brush_stroke_buffer.isNull():
            self._brush_stroke_buffer.fill(Qt.GlobalColor.transparent)

    def set_input_mask(self, mask_image: Optional[QImage]) -> None:
        """Sets a mask image, restricting canvas changes to areas covered by non-transparent mask areas"""
        self._mask = mask_image

    def _last_size_avg(self, default_size) -> float:
        if len(self._last_sizes) == 0:
            return default_size
        size = 0.0
        for s_val in self._last_sizes:
            size += s_val
        return size / len(self._last_sizes)

    @staticmethod
    def _draw_event_path(painter: QPainter, input_event: 'QtPaintCanvas._InputEvent') -> None:
        painter.save()
        painter.setOpacity(input_event.opacity)
        color = input_event.color
        if input_event.hardness < 1.0:
            if (input_event.last_pt is None or QLineF(input_event.last_pt, input_event.change_pt).length()
                    < input_event.size / 2):
                # painter.restore()
                # return  # Can't use a gradient without knowing the direction
                gradient = QRadialGradient(input_event.change_pt, input_event.size / 2)
                gradient.setColorAt(0, color)
                gradient.setColorAt(input_event.hardness, color)
                step = (1.0 - input_event.hardness) / 10
                grad_iter = input_event.hardness
                alpha = color.alphaF()
                alpha_step = alpha / 10
                while grad_iter < 1.0 and alpha > 0.0:
                    gradient.setColorAt(grad_iter, QColor(color.red(), color.green(), color.blue(), alpha))
                    alpha = alpha - alpha_step
                    grad_iter += step
            else:
                line = QLineF(input_event.last_pt, input_event.change_pt)
                norm = line.normalVector()
                norm.setLength(input_event.size / 2)
                offset = norm.p2() - norm.p1()
                p1 = line.center() - offset
                p2 = line.center() + offset
                gradient = QLinearGradient(p1, p2)
                center_offset = clamp(input_event.hardness / 2, 0.01, 0.49)
                offset_step = (0.5 - center_offset) / 10
                gradient.setColorAt(0.5, color)
                for start, end, step in ((0.0, 0.5 - center_offset, offset_step),
                                         (0.5 + center_offset, 1.0, offset_step)):
                    grad_iter = start
                    alpha = 0.0 if start == 0 else 1.0
                    while grad_iter < end:
                        gradient.setColorAt(grad_iter, QColor(color.red(), color.green(), color.blue(), alpha))
                        alpha = clamp(alpha + 0.1 if start == 0 else -0.1, 0.0, 1.0)
                        grad_iter += step
            brush = QBrush(gradient)
        else:
            brush = input_event.color
        pen = painter.pen()
        pen.setBrush(brush)
        painter.setPen(pen)
        if input_event.last_pt is None:
            painter.drawPoint(input_event.change_pt)
        else:
            painter.drawLine(input_event.last_pt, input_event.change_pt)
        painter.restore()

    def _draw_input_event(self, input_event: 'QtPaintCanvas._InputEvent', layer_painter: QPainter,
                          new_input_painter: QPainter) -> None:
        layer_painter.save()
        pen = QPen(input_event.color, input_event.size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                   Qt.PenJoinStyle.RoundJoin)
        if self.eraser:
            layer_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
        else:
            layer_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        if input_event.opacity < 1.0:
            new_input_painter.setPen(pen)
            new_input_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            self._paint_buffer.fill(Qt.GlobalColor.transparent)
            self._draw_event_path(new_input_painter, input_event)
            new_input_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
            size = max(self._last_size_avg(input_event.size), input_event.size)
            if input_event.last_pt is not None:
                bounds = QRectF(input_event.change_pt,
                                input_event.last_pt).adjusted(-size, -size, size, size).toAlignedRect()
            else:
                bounds = QRectF(input_event.change_pt.x() - size,
                                input_event.change_pt.y() - size,
                                input_event.change_pt.x() + size,
                                input_event.change_pt.y() + size).toAlignedRect()
            bounds = bounds.intersected(QRect(QPoint(), self._paint_buffer.size()))
            if not bounds.isEmpty():
                np_stroke_buffer = numpy_bounds_index(image_data_as_numpy_8bit(self._brush_stroke_buffer), bounds)
                np_buffer = numpy_bounds_index(image_data_as_numpy_8bit(self._paint_buffer), bounds)
                old_content = np_stroke_buffer[:, :, 3] > np_buffer[:, :, 3]
                new_content = ~old_content & (np_buffer[:, :, 3] > 0)
                # for i in range(4):
                #     np_buffer[old_content, i] = np_stroke_buffer[old_content, i]
                np_stroke_buffer[new_content] = np_buffer[new_content]
            layer_painter.drawImage(0, 0, self._paint_buffer)
        else:
            layer_painter.setPen(pen)
            self._draw_event_path(layer_painter, input_event)
        layer_painter.restore()

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
        new_input_painter = QPainter(self._paint_buffer)
        with layer.borrow_image(change_bounds) as layer_image:
            assert isinstance(layer_image, QImage)
            if self._mask is not None:
                buffer: Optional[QImage] = layer_image.copy(change_bounds)
                painter = QPainter(buffer)
                offset: Optional[QPoint] = change_bounds.topLeft()
                assert isinstance(offset, QPoint)
                painter.setTransform(QTransform.fromTranslate(-offset.x(), -offset.y()))
            else:
                buffer = None
                offset = None
                painter = QPainter(layer_image)
            for event in self._input_buffer:
                self._draw_input_event(event, painter, new_input_painter)
                saved_point = event.change_pt
                self._last_sizes.append(event.size)
                self._last_sizes = self._last_sizes[:SIZE_AVG_COUNT]
            if buffer is not None:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
                painter.drawImage(QPoint(), self._mask)
            painter.end()

            if buffer is not None and offset is not None:
                final_painter = QPainter(layer_image)
                final_painter.drawImage(offset, self._mask)
                final_painter.end()
            self._input_buffer.clear()
        new_input_painter.end()

    def _draw(self, x: float, y: float, pressure: Optional[float], x_tilt: Optional[float],
              y_tilt: Optional[float]) -> None:
        """Use active settings to draw to the canvas with the given inputs."""
        layer = self.layer
        assert layer is not None
        input_event = QtPaintCanvas._InputEvent(x, y, pressure, self.brush_size, self.brush_color, self._last_point,
                                                layer, self.opacity, self.hardness)
        self._input_buffer.append(input_event)
        if not self._buffer_timer.isActive():
            self._buffer_timer.start()
        self._last_point = QPointF(x, y)

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
