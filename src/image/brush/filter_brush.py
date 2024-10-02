"""Brush class that applies ImageFilter to brush stroke regions."""
import math
from typing import Optional, List, Any

import numpy as np
from PySide6.QtCore import QRect
from PySide6.QtGui import QImage, QPainter

from src.image.brush.qt_paint_brush import QtPaintBrush
from src.image.filter.filter import ImageFilter
from src.image.layers.image_layer import ImageLayer
from src.util.visual.image_utils import image_data_as_numpy_8bit, numpy_bounds_index


class FilterBrush(QtPaintBrush):
    """Brush class that applies ImageFilter to brush stroke regions."""

    def __init__(self, image_filter: ImageFilter, layer: Optional[ImageLayer] = None) -> None:
        super().__init__(layer)
        self._filter = image_filter
        filter_params = image_filter.get_parameters()
        self._parameter_values = {self._filter: [param.default_value for param in filter_params]}

    @property
    def image_filter(self) -> ImageFilter:
        """Accesses the brush filter object."""
        return self._filter

    @image_filter.setter
    def image_filter(self, new_filter: ImageFilter) -> None:
        self._filter = new_filter
        if new_filter not in self._parameter_values:
            filter_params = new_filter.get_parameters()
            self._parameter_values[new_filter] = [param.default_value for param in filter_params]

    @property
    def parameter_values(self) -> List[Any]:
        """Access the parameter values that will be applied to the filter."""
        return list(self._parameter_values[self._filter])

    @parameter_values.setter
    def parameter_values(self, values: List[Any]) -> None:
        parameters = self._filter.get_parameters()
        if len(values) != len(parameters):
            raise ValueError(f'Expected {len(parameters)} values, got {len(values)}')
        for i, parameter in enumerate(parameters):
            parameter.validate(values[i])
        self._parameter_values[self._filter] = list(values)

    def _filter_bounds(self, base_bounds: QRect) -> QRect:
        if self._filter.is_local():
            return QRect(base_bounds)
        filter_bounds = QRect(base_bounds)
        layer = self.layer
        assert layer is not None
        layer_bounds = layer.bounds
        radius = math.ceil(self._filter.radius(self._parameter_values[self._filter]))
        filter_bounds.setX(max(0, filter_bounds.x() - radius))
        filter_bounds.setY(max(0, filter_bounds.y() - radius))
        filter_bounds.setWidth(min(layer_bounds.width() - filter_bounds.x(), filter_bounds.width() + radius))
        filter_bounds.setHeight(min(layer_bounds.height() - filter_bounds.y(), filter_bounds.height() + radius))
        return filter_bounds

    def draw_segment_to_image(self, segment_image: QImage, layer_image: QImage, layer_painter: QPainter,
                              bounds: QRect) -> None:
        """Handles the final drawing operation that copies an input segment to the layer image."""
        copy_bounds = self._filter_bounds(bounds)
        filter_source = self._prev_image_buffer.copy(copy_bounds)
        filtered_image = self._filter.get_filter()(filter_source, *self._parameter_values[self._filter])

        np_image = numpy_bounds_index(image_data_as_numpy_8bit(layer_image), copy_bounds)
        np_filtered = image_data_as_numpy_8bit(filtered_image)

        # Use the brush stroke segment as a mask to select between filtered and original content:
        np_stroke_mask = numpy_bounds_index(image_data_as_numpy_8bit(segment_image), copy_bounds)[:, :, 3] / 255.0

        # Where the brush stroke mask is 100% opaque, the filter completely overrides the source:
        stroke_alpha_max = np_stroke_mask[:, :] == 1.0
        np_image[stroke_alpha_max, :] = np_filtered[stroke_alpha_max, :]

        # Where the brush stroke has partial alpha, fade between filter and source based on mask alpha level:
        partial_mask = (np_stroke_mask[:, :] > 0) & (~stroke_alpha_max)
        if np.any(partial_mask):
            np_image[partial_mask, :] = (np_filtered[partial_mask, :] * np_stroke_mask[partial_mask, None]
                                         + np_image[partial_mask, :] * (1 - np_stroke_mask[partial_mask, None]))
