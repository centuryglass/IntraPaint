"""
Brush implementing smudge tool operations.

A smudge stroke is a chain of one-pixel steps. Each step samples the layer under the brush, then draws that sample
over the layer at the next step, so every step depends on the one before it. Input is buffered and drawn in batches
from a timer, so the cost of a stroke is the number of steps times the cost of those two compositing operations.
"""
import time
from typing import Optional

from PySide6.QtCore import Qt, QPoint, QPointF, QTimer, QRect
from PySide6.QtGui import QPainter, QImage, QColor

from src.image.brush.layer_brush import LayerBrush
from src.image.brush.qt_paint_brush import QtPaintBrush
from src.image.layers.image_layer import ImageLayer
from src.util.math_utils import clamp
from src.util.visual.image_utils import create_transparent_image, image_data_as_numpy_8bit

PAINT_BUFFER_DELAY_MS = 50

# Longest a mid-stroke draw should block the event loop. Points left over are drawn on the next event loop pass, so
# the window can repaint and take input during a long stroke.
MAX_DRAW_SECONDS = 0.025
INITIAL_POINTS_PER_DRAW = 64


class SmudgeBrush(LayerBrush):
    """Smudges image layer content along brush strokes."""

    def __init__(self, layer: Optional[ImageLayer] = None) -> None:
        super().__init__(layer)
        self._opacity = 1.0
        self._hardness = 1.0
        self._last_point: Optional[QPointF] = None
        self._last_point_img = QImage()
        self._input_buffer: list['_SmudgePoint'] = []
        self._buffer_timer = QTimer()
        self._buffer_timer.setSingleShot(True)
        self._buffer_timer.timeout.connect(self._draw_buffered_events)
        self._points_per_draw = INITIAL_POINTS_PER_DRAW
        self._mask_cache = QImage()
        self._mask_cache_key: Optional[tuple[int, float, float, bool]] = None
        self._pressure_size = True
        self._pressure_opacity = False
        self._pressure_hardness = False
        self._antialiasing = True

    @property
    def opacity(self) -> float:
        """Access the brush opacity fraction."""
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

    def start_stroke(self) -> None:
        """Finish any stroke in progress, then clear tracked stroke data before starting a new stroke."""
        if self.drawing:
            self.end_stroke()
        self._last_point = None
        self._last_point_img = QImage()
        super().start_stroke()

    def end_stroke(self) -> None:
        """Finishes a brush stroke, drawing all buffered points to the layer."""
        super().end_stroke()
        self._last_point = None
        self._draw_buffered_events()

    def _brush_mask(self, smudge_point: '_SmudgePoint') -> QImage:
        """Returns the brush mask for a smudge point: a black circle with diameter equal to the brush size, highest
           opacity set to the smudge point opacity, and edges faded out based on hardness.

        The mask is cached until a point needs one with different parameters. Callers must not change it.
        """
        cache_key = (smudge_point.rect.width(), smudge_point.opacity, smudge_point.hardness, self._antialiasing)
        if cache_key != self._mask_cache_key:
            self._mask_cache = smudge_point.draw_mask(self._antialiasing)
            self._mask_cache_key = cache_key
        return self._mask_cache

    def _sample_smudge_point(self, smudge_point: '_SmudgePoint', layer_image: QImage) -> QImage:
        """Sample a point from the image, to be drawn over the next smudge point.

        Parameters:
        -----------
        smudge_point: _SmudgePoint
            Data from one smudge tool input event, storing location, brush size, opacity, and hardness.
        layer_image: QImage
            The ARGB32_Premultiplied layer image.

        Returns:
        --------
        A new ARGB32_Premultiplied QImage containing the layer content under the brush mask, or a null QImage if the
        point is entirely outside the layer.
        """
        intersect_bounds = smudge_point.rect.intersected(QRect(QPoint(), layer_image.size()))
        if intersect_bounds.isEmpty():
            return QImage()
        smudge_mask = self._brush_mask(smudge_point).copy()

        # Clear the parts of the brush mask that are outside the layer:
        mask_intersect_bounds = intersect_bounds.translated(-smudge_point.rect.x(), -smudge_point.rect.y())
        if intersect_bounds.size() != smudge_mask.size():
            np_smudge_mask = image_data_as_numpy_8bit(smudge_mask)
            np_smudge_mask[:mask_intersect_bounds.y(), :, :] = 0
            np_smudge_mask[mask_intersect_bounds.y() + mask_intersect_bounds.height():, :, :] = 0
            np_smudge_mask[:, :mask_intersect_bounds.x(), :] = 0
            np_smudge_mask[:, mask_intersect_bounds.x() + mask_intersect_bounds.width():, :] = 0

        painter = QPainter(smudge_mask)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.drawImage(mask_intersect_bounds, layer_image, intersect_bounds)
        painter.end()
        return smudge_mask

    def _draw_buffered_events(self) -> None:
        """Draws buffered smudge points to the layer.

        Mid-stroke, this draws about MAX_DRAW_SECONDS worth of points and schedules the rest for the next event loop
        pass. Once the stroke has ended, it draws every buffered point.
        """
        self._buffer_timer.stop()
        layer = self.layer
        if len(self._input_buffer) == 0 or layer is None:
            return
        if self.drawing:
            point_count = min(len(self._input_buffer), self._points_per_draw)
        else:
            point_count = len(self._input_buffer)
        start_time = time.perf_counter()
        self._draw_points(layer, self._input_buffer[:point_count])
        del self._input_buffer[:point_count]
        if self.drawing:
            elapsed = max(time.perf_counter() - start_time, 1e-6)
            self._points_per_draw = max(1, int(point_count * MAX_DRAW_SECONDS / elapsed))
            if len(self._input_buffer) > 0:
                self._buffer_timer.start(0)

    def _draw_points(self, layer: ImageLayer, points: list['_SmudgePoint']) -> None:
        """Draws a sequence of smudge points to the layer, continuing from the last point drawn."""
        change_bounds = QRect()
        for smudge_point in points:
            change_bounds = change_bounds.united(smudge_point.rect)
        change_bounds = change_bounds.intersected(layer.bounds)
        mask_image = self.input_mask
        with layer.borrow_image(change_bounds) as layer_image:
            assert isinstance(layer_image, QImage)
            img_painter = QPainter(layer_image)
            for smudge_point in points:
                if not self._last_point_img.isNull():  # Draw the sample from the last point over the current one:
                    paint_bounds = QRect(QPoint(), self._last_point_img.size())
                    paint_bounds.moveCenter(smudge_point.rect.center())
                    if mask_image is not None:
                        source_bounds = paint_bounds.intersected(QRect(QPoint(), mask_image.size()))
                        if source_bounds.isEmpty():
                            continue
                        destination_bounds = source_bounds.translated(-paint_bounds.x(), -paint_bounds.y())
                        point_img_painter = QPainter(self._last_point_img)
                        point_img_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
                        point_img_painter.drawImage(destination_bounds, mask_image, source_bounds)
                        point_img_painter.end()
                    img_painter.drawImage(paint_bounds, self._last_point_img)
                self._last_point_img = self._sample_smudge_point(smudge_point, layer_image)
            img_painter.end()

    def _draw(self, x: float, y: float, pressure: Optional[float], x_tilt: Optional[float],
              y_tilt: Optional[float]) -> None:
        """Buffers smudge points along the line from the last input point to this one."""
        if self._last_point is not None and self._last_point.x() == round(x) and self._last_point.y() == round(y):
            return
        size = self.brush_size
        opacity = self.opacity
        hardness = self.hardness
        if pressure is not None:
            if self._pressure_size:
                size = max(round(size * pressure), 1)
            if self._pressure_opacity:
                opacity *= pressure
            if self._pressure_hardness:
                hardness *= pressure
        if self._last_point is None:
            self._input_buffer.append(_SmudgePoint(x, y, size, opacity, hardness))
        else:
            x0 = round(self._last_point.x())
            y0 = round(self._last_point.y())
            dx = round(x) - x0
            dy = round(y) - y0
            if abs(dx) < 2 and abs(dy) < 2:
                self._input_buffer.append(_SmudgePoint(x, y, size, opacity, hardness))
            else:
                step_count = max(abs(dx), abs(dy))
                x_step = dx / step_count
                y_step = dy / step_count
                for i in range(1, step_count + 1):
                    self._input_buffer.append(_SmudgePoint(round(x0 + x_step * i), round(y0 + y_step * i), size,
                                                           opacity, hardness))
        self._last_point = QPointF(x, y)
        if not self._buffer_timer.isActive():
            self._buffer_timer.start(PAINT_BUFFER_DELAY_MS)


class _SmudgePoint:
    """A single point of smudge input data, storing position and size (as rect), opacity, and hardness."""

    def __init__(self, x: float, y: float, size: int, opacity: float, hardness: float):
        self.rect = QRect(0, 0, size, size)
        self.rect.moveCenter(QPoint(round(x), round(y)))
        self.opacity = opacity
        self.hardness = hardness

    def draw_mask(self, antialiasing: bool = False) -> QImage:
        """Creates a mask image for this input point."""
        image = create_transparent_image(self.rect.size())
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, antialiasing)
        image_center = QPointF(self.rect.width() / 2, self.rect.height() / 2)
        QtPaintBrush.paint_segment(painter, self.rect.width(), self.opacity, self.hardness,
                                   QColor(Qt.GlobalColor.black), image_center, None)
        painter.end()
        return image
