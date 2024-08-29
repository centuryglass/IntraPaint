"""
Draws content to an image layer using basic Qt drawing operations.
"""
from typing import Optional, List

from PySide6.QtCore import Qt, QPoint, QPointF, QRectF, QTimer, QRect
from PySide6.QtGui import QPainter, QPen, QTransform, QImage, QColor

from src.image.canvas.layer_canvas import LayerCanvas
from src.image.layers.image_layer import ImageLayer

PAINT_BUFFER_DELAY_MS = 50


class PixmapLayerCanvas(LayerCanvas):
    """Draws content to an image layer using basic Qt drawing operations."""

    def __init__(self, layer: Optional[ImageLayer] = None) -> None:
        """Initialize a MyPaint surface, and connect to the image layer."""
        super().__init__(layer)
        self._last_point: Optional[QPoint] = None
        self._change_bounds = QRectF()
        self._mask: Optional[QImage] = None
        self._input_buffer: List[PixmapLayerCanvas._InputEvent] = []
        self._buffer_timer = QTimer()
        self._buffer_timer.setInterval(PAINT_BUFFER_DELAY_MS)
        self._buffer_timer.setSingleShot(True)
        self._buffer_timer.timeout.connect(self._draw_buffered_events)

    def start_stroke(self) -> None:
        self._change_bounds = QRectF()
        super().start_stroke()

    def end_stroke(self) -> None:
        """Finishes a brush stroke, copying it back to the layer."""
        super().end_stroke()
        self._last_point = None
        self._draw_buffered_events()

    def set_input_mask(self, mask_image: Optional[QImage]) -> None:
        """Sets a mask image, restricting canvas changes to areas covered by non-transparent mask areas"""
        self._mask = mask_image

    def _draw_input_event(self, input_event: 'PixmapLayerCanvas._InputEvent', painter: QPainter) -> None:
        painter.save()
        if self.eraser:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        pen = QPen(input_event.color, input_event.size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                   Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        if input_event.last_pt is None:
            painter.drawPoint(input_event.change_pt)
        else:
            painter.drawLine(input_event.last_pt, input_event.change_pt)
        painter.restore()

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
                self._draw_input_event(event, painter)
            if buffer is not None:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
                painter.drawImage(QPoint(), self._mask)
            painter.end()

            if buffer is not None and offset is not None:
                final_painter = QPainter(layer_image)
                final_painter.drawImage(offset, self._mask)
                final_painter.end()
            self._input_buffer.clear()

    def _draw(self, x: float, y: float, pressure: Optional[float], x_tilt: Optional[float],
              y_tilt: Optional[float]) -> None:
        """Use active settings to draw to the canvas with the given inputs."""
        layer = self.layer
        assert layer is not None
        input_event = PixmapLayerCanvas._InputEvent(x, y, pressure, self.brush_size, self.brush_color, self._last_point,
                                                    layer)
        self._input_buffer.append(input_event)
        if not self._buffer_timer.isActive():
            self._buffer_timer.start()
        self._last_point = QPointF(x, y)

    class _InputEvent:
        """Delayed drawing input event, buffered to decrease input lag."""

        def __init__(self, x: float, y: float, pressure: Optional[float], size: float, color: QColor,
                     last_point: Optional[QPointF], layer: ImageLayer) -> None:
            layer_bounds = layer.bounds
            self.size = size
            if pressure is not None:
                self.size = max(int(size * pressure), 1)
            self.change_pt = QPointF(x - layer_bounds.x(), y - layer_bounds.y())
            self.last_pt = None if last_point is None else QPointF(last_point.x() - layer_bounds.x(),
                                                                   last_point.y() - layer_bounds.y())
            self.change_bounds = QRectF(self.change_pt.x() - size, self.change_pt.y() - size, size * 2,
                                        size * 2).toAlignedRect()
            if self.last_pt is not None:
                self.change_bounds = self.change_bounds.united(QRectF(self.last_pt.x() - size, self.last_pt.y() - size,
                                                                      size * 2, size * 2).toAlignedRect())
            self.color = color
