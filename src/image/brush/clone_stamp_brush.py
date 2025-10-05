"""
Brush implementing the clone stamp tool, copying image content from one spot to another.
"""
import math
from typing import Optional

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QPainter, QImage

from src.image.brush.qt_paint_brush import QtPaintBrush
from src.image.layers.image_layer import ImageLayer
from src.util.math_utils import clamp
from src.util.visual.image_utils import create_transparent_image, image_data_as_numpy_8bit, numpy_bounds_index, \
    NpAnyArray, numpy_intersect, np_composite_with_mask


class CloneStampBrush(QtPaintBrush):
    """Brush implementing the clone stamp tool, copying image content from one spot to another."""

    def __init__(self, layer: Optional[ImageLayer] = None) -> None:
        super().__init__(layer)
        self._source_offset: Optional[QPoint] = None
        self._source_pos: Optional[QPoint] = None
        self._last_segment_params: Optional[QtPaintBrush._InputEvent] = None

    @property
    def source_offset(self) -> Optional[QPoint]:
        """Accesses the clone source offset. This value will be None if using a fixed source point. Setting this value
           will set source_pos to None."""
        return self._source_pos

    @source_offset.setter
    def source_offset(self, source_offset: QPoint) -> None:
        self._source_offset = source_offset
        self._source_pos = None

    @property
    def source_pos(self) -> Optional[QPoint]:
        """Accesses the clone source position. This value will be None if using a source offset. Setting this value
           will set source_offset to None."""
        return self._source_pos

    @source_pos.setter
    def source_pos(self, source_pos: QPoint) -> None:
        self._source_pos = source_pos
        self._source_offset = None

    def _input_event_paint_segment(self, painter: QPainter, input_event: 'QtPaintBrush._InputEvent') -> None:
        """Cache segment drawing params so we can reuse them to help with fixed point clone stamping."""
        self._last_segment_params = input_event
        QtPaintBrush.paint_segment(painter, round(input_event.size), input_event.opacity, input_event.hardness,
                                   input_event.color, input_event.change_pt, input_event.last_pt)

    def draw_segment_to_image(self, segment_image: QImage, layer_image: QImage, layer_painter: QPainter,
                              bounds: QRect) -> None:
        """Handles the final drawing operation that copies an input segment to the layer image."""
        if self._source_pos is not None:
            self._draw_segment_with_fixed_source(segment_image, layer_image)
        elif self._source_offset is not None:
            self._draw_segment_with_offset_source(segment_image, layer_image, bounds)

    def _get_stamp_source_image(self, source_bounds: QRect) -> tuple[QImage, NpAnyArray]:
        layer = self.layer
        assert layer is not None
        if layer.bounds.contains(source_bounds):
            sample_source = self._prev_image_buffer.copy(source_bounds)
            np_source = image_data_as_numpy_8bit(sample_source)
        else:
            sample_source = create_transparent_image(source_bounds.size())
            np_source = image_data_as_numpy_8bit(sample_source)
            overlap = layer.bounds.intersected(source_bounds)
            if not overlap.isEmpty():
                sample_intersect_bounds = overlap.translated(-source_bounds.x(), -source_bounds.y())
                sample_source_intersect = numpy_bounds_index(np_source, sample_intersect_bounds)
                prev_image_intersect = numpy_bounds_index(image_data_as_numpy_8bit(self._prev_image_buffer), overlap)
                sample_source_intersect[:, :, :] = prev_image_intersect[:, :, :]
        return sample_source, np_source

    def _draw_segment_with_offset_source(self, segment_image: QImage, layer_image: QImage, bounds: QRect) -> None:
        if self._source_offset is None or self._source_offset.isNull():
            return
        source_bounds = bounds.translated(self._source_offset.x(), self._source_offset.y())
        source_image, np_source = self._get_stamp_source_image(source_bounds)

        # Use the brush stroke segment as a mask to select between cloned and original content:
        np_image = numpy_bounds_index(image_data_as_numpy_8bit(layer_image), bounds)
        np_stroke_mask = numpy_bounds_index(image_data_as_numpy_8bit(segment_image), bounds)
        np_composite_with_mask(np_source, np_image, np_stroke_mask)

    def _draw_segment_with_fixed_source(self, segment_image: QImage, layer_image: QImage) -> None:
        assert self._source_pos is not None
        brush_radius = math.ceil(self.brush_size / 2)
        source_bounds = QRect(self._source_pos.x() - brush_radius, self._source_pos.y() - brush_radius,
                              brush_radius * 2, brush_radius * 2)
        if self._last_segment_params is None:
            return
        source_image, np_source = self._get_stamp_source_image(source_bounds)
        # When using a fixed source point, the clone stamp tool works basically the same way as the smudge brush,
        # except that the point sampled for drawing is fixed.
        if self._last_segment_params.last_pt is None:
            point_list = [QPoint(self._last_segment_params.change_pt.toPoint())]
        else:
            point_list = []
            x0 = round(self._last_segment_params.last_pt.x())
            y0 = round(self._last_segment_params.last_pt.y())
            x1 = round(self._last_segment_params.change_pt.x())
            y1 = round(self._last_segment_params.change_pt.y())
            dx = x1 - x0
            dy = y1 - y0
            if abs(dx) < 2 and abs(dy) < 2:
                point_list.append(QPoint(self._last_segment_params.last_pt.toPoint()))
                point_list.append(QPoint(self._last_segment_params.change_pt.toPoint()))
            else:
                step_count = max(abs(dx), abs(dy))
                x_step = clamp(dx / step_count, -1.0, 1.0)
                y_step = clamp(dy / step_count, -1.0, 1.0)
                for i in range(0, step_count, 1):
                    xi = round(x0 + x_step * i)
                    yi = round(y0 + y_step * i)
                    point_list.append(QPoint(xi, yi))
        np_segment_image = image_data_as_numpy_8bit(segment_image)
        np_layer_image = image_data_as_numpy_8bit(layer_image)
        layer = self.layer
        assert layer is not None
        layer_bounds = layer.bounds
        for draw_pt in point_list:
            pt_bounds = QRect(draw_pt.x() - brush_radius, draw_pt.y() - brush_radius,
                              brush_radius * 2, brush_radius * 2).intersected(layer_bounds)
            if pt_bounds.isEmpty():
                continue
            np_segment_img_pt: Optional[NpAnyArray] = numpy_bounds_index(np_segment_image, pt_bounds)
            np_layer_img_pt: Optional[NpAnyArray] = numpy_bounds_index(np_layer_image, pt_bounds)
            assert np_segment_img_pt is not None and np_layer_img_pt is not None
            np_segment_img_pt, cropped_np_source = numpy_intersect(np_segment_img_pt, np_source)
            if np_segment_img_pt is None or cropped_np_source is None:
                continue
            np_layer_img_pt, cropped_np_source = numpy_intersect(np_layer_img_pt, cropped_np_source)
            if np_layer_img_pt is None or cropped_np_source is None:
                continue
            np_composite_with_mask(cropped_np_source, np_layer_img_pt, np_segment_img_pt)


