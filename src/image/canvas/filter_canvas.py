"""Canvas class that functions by applying an ImageFilter to brush stroke regions."""
import math
from typing import Optional, List, Any

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QImage, QPainter

from src.image.canvas.qt_paint_canvas import QtPaintCanvas
from src.image.filter.filter import ImageFilter
from src.image.layers.image_layer import ImageLayer


class FilterCanvas(QtPaintCanvas):
    """Canvas class that functions by applying an ImageFilter to brush stroke regions."""

    def __init__(self, image_filter: ImageFilter, layer: Optional[ImageLayer] = None) -> None:
        super().__init__(layer)
        self._filter = image_filter
        filter_params = image_filter.get_parameters()
        self._last_point: Optional[QPoint] = None
        self._parameter_values = {self._filter: [param.default_value for param in filter_params]}

    @property
    def image_filter(self) -> ImageFilter:
        """Accesses the canvas filter object."""
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

    @property
    def pressure_size(self) -> bool:
        """Access whether pressure data controls brush size."""
        return self._pressure_size

    @pressure_size.setter
    def pressure_size(self, pressure_sets_size: bool) -> None:
        self._pressure_size = pressure_sets_size

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
        filter_source = layer_image.copy(copy_bounds)
        final_source_bounds = bounds.translated(-copy_bounds.x() + bounds.x() - copy_bounds.x(),
                                                -copy_bounds.y() + bounds.y() - copy_bounds.y())
        filtered_image = self._filter.get_filter()(filter_source, *self._parameter_values[self._filter])
        filter_painter = QPainter(filtered_image)
        filter_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        filter_painter.drawImage(final_source_bounds, segment_image, bounds)
        filter_painter.end()
        layer_painter.save()
        layer_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        layer_painter.drawImage(bounds, filtered_image, final_source_bounds)
        layer_painter.restore()

    def end_stroke(self) -> None:
        """Re-apply the filter across the entire stroke for consistency."""
        self._draw_buffered_events()
        bounds = self._change_bounds.toAlignedRect()
        filter_bounds = self._filter_bounds(bounds)
        prev_content = self._prev_image_buffer.copy(filter_bounds)
        layer = self.layer
        assert layer is not None
        with layer.borrow_image(filter_bounds) as layer_image:
            layer_painter = QPainter(layer_image)
            layer_painter.drawImage(filter_bounds, prev_content)
            self.draw_segment_to_image(self._brush_stroke_buffer, layer_image, layer_painter, bounds)
            layer_painter.end()
        super().end_stroke()
