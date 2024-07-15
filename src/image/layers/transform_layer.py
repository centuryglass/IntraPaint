"""Interface for layers that have a persistent transformation."""
from typing import Tuple

from PyQt6.QtCore import QObject, pyqtSignal, QRect, QPoint, QRectF, QPointF
from PyQt6.QtGui import QPainter, QImage, QTransform, QPolygonF

from src.image.layers.layer import Layer
from src.util.image_utils import create_transparent_image


class TransformLayer(Layer):
    """Interface for layers that have a persistent transformation."""

    transform_changed = pyqtSignal(QObject, QTransform)

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self._transform = QTransform()

    # PROPERTY DEFINITIONS:
    # All changes made through property setters are registered in the undo history, and are broadcast through
    # appropriate signals.

    @property
    def transform(self) -> QTransform:
        """Returns the layer's matrix transformation."""
        return QTransform(self._transform)

    @transform.setter
    def transform(self, new_transform: QTransform) -> None:
        self._apply_combinable_change(new_transform, self._transform, self.set_transform, 'layer.transform')

    @property
    def transformed_bounds(self) -> QRect:
        """Returns the layer's bounds after applying its transformation."""
        bounds = self.bounds
        return self._transform.map(QPolygonF(QRectF(bounds))).boundingRect().toAlignedRect()

    def set_transform(self, transform: QTransform, send_signals: bool = True) -> None:
        """Updates the layer's matrix transformation."""
        if transform != self._transform:
            assert transform.isInvertible(), f'layer {self.name}:{self.id} given non-invertible transform'
            self._transform = transform
            if send_signals:
                self.transform_changed.emit(self, transform)

    def transformed_image(self) -> Tuple[QImage, QTransform]:
        """Apply all non-translating transformations to a copy of the image, returning it with the final translation."""
        bounds = self.transformed_bounds
        layer_transform = self.transform
        offset = bounds.topLeft()
        final_transform = QTransform()
        final_transform.translate(offset.x(), offset.y())
        if final_transform == layer_transform:
            return self.image, self.transform
        image = create_transparent_image(bounds.size())
        painter = QPainter(image)
        paint_transform = layer_transform * QTransform.fromTranslate(-offset.x(), -offset.y())
        painter.setTransform(paint_transform)
        painter.drawImage(self.bounds, self.get_qimage())
        painter.end()
        return image, final_transform

    def map_from_image(self, image_point: QPoint | QPointF) -> QPoint:
        """Map a top level image point to the appropriate spot in the layer image."""
        inverse, invert_success = self.transform.inverted()
        assert invert_success
        assert isinstance(inverse, QTransform)
        return inverse.map(image_point)

    def map_rect_from_image(self, image_rect: QRect) -> QRect:
        """Map a top level image rectangle to the appropriate spot in the layer image."""
        inverse, invert_success = self.transform.inverted()
        assert invert_success
        assert isinstance(inverse, QTransform)
        return inverse.map(QPolygonF(QRectF(image_rect))).boundingRect().toAlignedRect()

    def map_to_image(self, layer_point: QPoint) -> QPoint:
        """Map a point in the layer image to its final spot in the top level image."""
        return self.transform.map(layer_point)

    def map_rect_to_image(self, layer_rect: QRect) -> QRect:
        """Map a rectangle in the layer image to its final spot in the top level image."""
        return self.transform.map(QPolygonF(QRectF(layer_rect))).boundingRect().toAlignedRect()
