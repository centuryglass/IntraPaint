"""Brush class that applies ImageFilter to brush stroke regions.

Within one stroke, every segment filters the layer content from before the stroke, so a pixel's filtered value is fixed
for the whole stroke. `FilterBrush` filters the layer once per tile and reuses the result for every segment that
touches the tile.
"""
import math
from typing import Optional, Any

import numpy as np
from PySide6.QtCore import QRect
from PySide6.QtGui import QImage, QPainter

from src.image.brush.qt_paint_brush import QtPaintBrush
from src.image.filter.filter import ImageFilter
from src.image.layers.image_layer import ImageLayer
from src.util.visual.image_utils import image_data_as_numpy_8bit, numpy_bounds_index

# Edge length in pixels of the layer regions filtered as one unit. Smaller tiles filter less content that no segment
# reaches, larger ones repeat less of the padding that radius filters read around each tile.
FILTER_TILE_SIZE = 128


class FilterBrush(QtPaintBrush):
    """Brush class that applies ImageFilter to brush stroke regions."""

    def __init__(self, image_filter: ImageFilter, layer: Optional[ImageLayer] = None) -> None:
        super().__init__(layer)
        self._filter = image_filter
        filter_params = image_filter.get_parameters()
        self._parameter_values = {self._filter: [param.default_value for param in filter_params]}
        # The layer image from the start of the stroke, which the filter reads:
        self._filter_source = QImage()
        # Filtered content for the tiles marked in _filtered_tiles, in layer coordinates:
        self._filtered_image = QImage()
        self._filtered_tiles = np.zeros((0, 0), dtype=bool)

    @property
    def image_filter(self) -> ImageFilter:
        """Accesses the brush filter object."""
        return self._filter

    @image_filter.setter
    def image_filter(self, new_filter: ImageFilter) -> None:
        self._filter = new_filter
        self._clear_filtered_tiles()
        if new_filter not in self._parameter_values:
            filter_params = new_filter.get_parameters()
            self._parameter_values[new_filter] = [param.default_value for param in filter_params]

    @property
    def parameter_values(self) -> list[Any]:
        """Access the parameter values that will be applied to the filter."""
        return list(self._parameter_values[self._filter])

    @parameter_values.setter
    def parameter_values(self, values: list[Any]) -> None:
        parameters = self._filter.get_parameters()
        if len(values) != len(parameters):
            raise ValueError(f'Expected {len(parameters)} values, got {len(values)}')
        for i, parameter in enumerate(parameters):
            parameter.validate(values[i])
        self._parameter_values[self._filter] = list(values)
        self._clear_filtered_tiles()

    def _clear_filtered_tiles(self) -> None:
        """Discards filtered content, so the next segment filters its tiles again."""
        self._filtered_tiles[:, :] = False

    def start_stroke(self) -> None:
        """Saves the layer image for filtering, and discards content filtered during earlier strokes."""
        super().start_stroke()
        # The layer and the previous image buffer detach from this shared copy when they change, so it keeps the
        # stroke-start content. The previous image buffer can't be used instead, as it is only filled where the stroke
        # has drawn, with a margin that a large filter radius can exceed.
        self._filter_source = self._prev_image_buffer
        tile_size = FILTER_TILE_SIZE
        self._filtered_tiles = np.zeros((math.ceil(self._filter_source.height() / tile_size),
                                         math.ceil(self._filter_source.width() / tile_size)), dtype=bool)
        self._filtered_image = QImage()

    def _ensure_filtered(self, bounds: QRect) -> None:
        """Filters every tile that overlaps the bounds and hasn't been filtered yet this stroke."""
        if self._filtered_image.isNull():
            self._filtered_image = QImage(self._filter_source.size(), QImage.Format.Format_ARGB32_Premultiplied)
        tile_size = FILTER_TILE_SIZE
        rows, columns = self._filtered_tiles.shape
        first_column = max(0, bounds.left() // tile_size)
        last_column = min(columns - 1, bounds.right() // tile_size)
        first_row = max(0, bounds.top() // tile_size)
        last_row = min(rows - 1, bounds.bottom() // tile_size)
        filter_function = self._filter.get_filter()
        parameter_values = self._parameter_values[self._filter]
        np_filtered = image_data_as_numpy_8bit(self._filtered_image)
        for row in range(first_row, last_row + 1):
            for column in range(first_column, last_column + 1):
                if self._filtered_tiles[row, column]:
                    continue
                tile = QRect(column * tile_size, row * tile_size, tile_size, tile_size).intersected(
                    self._filter_source.rect())
                source_bounds = self._filter_bounds(tile)
                filtered = filter_function(self._filter_source.copy(source_bounds), *parameter_values)
                filtered = filtered.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                np_tile = image_data_as_numpy_8bit(filtered)
                if source_bounds != tile:
                    assert source_bounds.contains(tile)
                    np_tile = numpy_bounds_index(np_tile, tile.translated(-source_bounds.x(), -source_bounds.y()))
                numpy_bounds_index(np_filtered, tile)[:, :, :] = np_tile
                self._filtered_tiles[row, column] = True

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
        self._ensure_filtered(bounds)
        np_image = numpy_bounds_index(image_data_as_numpy_8bit(layer_image), bounds)
        np_filtered = numpy_bounds_index(image_data_as_numpy_8bit(self._filtered_image), bounds)

        # Use the brush stroke segment as a mask to select between filtered and original content:
        np_stroke_mask = numpy_bounds_index(image_data_as_numpy_8bit(segment_image), bounds)[:, :, 3]

        # Where the brush stroke mask is 100% opaque, the filter completely overrides the source:
        stroke_alpha_max = np_stroke_mask == 255
        np_image[stroke_alpha_max, :] = np_filtered[stroke_alpha_max, :]

        # Where the brush stroke has partial alpha, fade between filter and source based on mask alpha level:
        partial_mask = (np_stroke_mask > 0) & ~stroke_alpha_max
        if np.any(partial_mask):
            mask_alpha = np_stroke_mask[partial_mask, None].astype(np.uint16)
            blended = (np_filtered[partial_mask, :].astype(np.uint16) * mask_alpha
                       + np_image[partial_mask, :].astype(np.uint16) * (255 - mask_alpha)) // 255
            np_image[partial_mask, :] = blended
