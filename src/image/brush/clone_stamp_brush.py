"""
Brush implementing the clone stamp tool, copying image content from one spot to another.
"""
from typing import Optional

import numpy as np
from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QPainter, QImage

from src.image.brush.qt_paint_brush import QtPaintBrush
from src.image.layers.image_layer import ImageLayer
from src.util.visual.image_utils import create_transparent_image, image_data_as_numpy_8bit, numpy_bounds_index


class CloneStampBrush(QtPaintBrush):
    """Brush implementing the clone stamp tool, copying image content from one spot to another."""

    def __init__(self, layer: Optional[ImageLayer] = None) -> None:
        super().__init__(layer)
        self._offset = QPoint()

    @property
    def offset(self) -> QPoint:
        """Access the brush sampling offset."""
        return self._offset

    @offset.setter
    def offset(self, offset: QPoint) -> None:
        self._offset = offset

    def draw_segment_to_image(self, segment_image: QImage, layer_image: QImage, layer_painter: QPainter,
                              bounds: QRect) -> None:
        """Handles the final drawing operation that copies an input segment to the layer image."""
        if self._offset.isNull():
            return
        np_image = numpy_bounds_index(image_data_as_numpy_8bit(layer_image), bounds)
        offset_bounds = bounds.translated(self._offset.x(), self._offset.y())
        layer = self.layer
        assert layer is not None
        if layer.bounds.contains(offset_bounds):
            sample_source = self._prev_image_buffer.copy(offset_bounds)
            np_source = image_data_as_numpy_8bit(sample_source)
        else:
            sample_source = create_transparent_image(offset_bounds.size())
            np_source = image_data_as_numpy_8bit(sample_source)
            overlap = layer.bounds.intersected(offset_bounds)
            if not overlap.isEmpty():
                sample_intersect_bounds = overlap.translated(-offset_bounds.x(), -offset_bounds.y())
                sample_source_intersect = numpy_bounds_index(np_source, sample_intersect_bounds)
                prev_image_intersect = numpy_bounds_index(image_data_as_numpy_8bit(self._prev_image_buffer), overlap)
                sample_source_intersect[:, :, :] = prev_image_intersect[:, :, :]

        # Use the brush stroke segment as a mask to select between cloned and original content:
        np_stroke_mask = numpy_bounds_index(image_data_as_numpy_8bit(segment_image), bounds)[:, :, 3] / 255.0

        # Where the brush stroke mask is 100% opaque, the clone stamp completely overrides the source:
        stroke_alpha_max = np_stroke_mask[:, :] == 1.0
        np_image[stroke_alpha_max, :] = np_source[stroke_alpha_max, :]

        # Where the brush stroke has partial alpha, fade between clone stamp and original based on mask alpha level:
        partial_mask = (np_stroke_mask[:, :] > 0) & (~stroke_alpha_max)
        if np.any(partial_mask):
            np_image[partial_mask, :] = (np_source[partial_mask, :] * np_stroke_mask[partial_mask, None]
                                         + np_image[partial_mask, :] * (1 - np_stroke_mask[partial_mask, None]))

