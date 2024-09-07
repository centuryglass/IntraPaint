"""Interface for layers that have a persistent transformation."""
from typing import Tuple, Optional, Callable

from PySide6.QtCore import QObject, Signal, QRect, QPoint, QPointF
from PySide6.QtGui import QPainter, QImage, QTransform

from src.image.layers.layer import Layer
from src.util.visual.geometry_utils import extract_transform_parameters, combine_transform_parameters, map_rect_precise
from src.util.visual.image_utils import create_transparent_image


class TransformLayer(Layer):
    """Interface for layers that have a persistent transformation."""

    transform_changed = Signal(QObject, QTransform)

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self._transform = QTransform()

    # PROPERTY DEFINITIONS:
    # All changes made through property setters are registered in the undo history, and are broadcast through
    # appropriate signals.

    def _get_transform(self) -> QTransform:
        return QTransform(self._transform)

    @property
    def transform(self) -> QTransform:
        """Returns the layer's matrix transformation."""
        return self._get_transform()

    @transform.setter
    def transform(self, new_transform: QTransform) -> None:
        self._apply_combinable_change(new_transform, self._transform, self.set_transform, 'layer.transform')

    @property
    def transformed_bounds(self) -> QRect:
        """Returns the layer's bounds after applying its transformation."""
        bounds = self.bounds
        return map_rect_precise(bounds, self._transform).toAlignedRect()

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
        return map_rect_precise(image_rect, inverse).toAlignedRect()

    def map_to_image(self, layer_point: QPoint) -> QPoint:
        """Map a point in the layer image to its final spot in the top level image."""
        return self.transform.map(layer_point)

    def map_rect_to_image(self, layer_rect: QRect) -> QRect:
        """Map a rectangle in the layer image to its final spot in the top level image."""
        return map_rect_precise(layer_rect, self.transform).toAlignedRect()

    def rotate(self, degrees: int) -> None:
        """Rotate the layer by an arbitrary degree count, on top of any previous transformations."""
        center = QPointF(self.bounds.center())
        x_off, y_off, x_scale, y_scale, base_angle = extract_transform_parameters(self.transform, center)
        angle_offset = degrees if x_scale > 0 and y_scale > 0 else -degrees
        self.transform = combine_transform_parameters(x_off, y_off, x_scale, y_scale, base_angle + angle_offset, center)

    def _flip(self, horizontal: bool = True) -> None:
        # center = self._transform.map(QPolygonF(QRectF(self.bounds))).boundingRect().center()
        center = QPointF(self.bounds.center())
        x_off, y_off, x_scale, y_scale, angle = extract_transform_parameters(self.transform, center)
        if horizontal:
            x_scale *= -1
        else:
            y_scale *= -1
        self.transform = combine_transform_parameters(x_off, y_off, x_scale, y_scale, angle, center)

    def flip_horizontal(self) -> None:
        """Flip the layer horizontally, on top of any previous transformations."""
        self._flip(True)

    def flip_vertical(self) -> None:
        """Flip the layer vertically, on top of any previous transformations."""
        self._flip(False)

    def render(self, base_image: Optional[QImage] = None,
               paint_param_adjuster: Optional[Callable[[int, QImage, QRect, QPainter], Optional[QImage]]]
               = None) -> QImage:
        """Render all layers to a QImage with a custom base image and accepting a function to control layer painting on
        a per-layer basis.

        Parameters
        ----------
        base_image: QImage, optional, default=None.
            The base image that all layer content will be painted onto.  If None, a new image will be created that's
            large enough to fit all layers.
        paint_param_adjuster: Optional[Callable[[int, QImage, QRect, QPainter) -> Optional[QImage]]
            Default=None. If provided, it will be called before each layer is painted, allowing it to directly make
            changes to the image, paint bounds, or painter as needed. Parameters are layer_id, layer_image,
            paint_bounds and layer_painter.  If it returns a QImage, that image will replace the layer image.
        Returns
        -------
        QImage: The final rendered image.
        """
        def _transform_adjuster(layer_id: int, layer_image: QImage, paint_bounds: QRect,
                                painter: QPainter) -> Optional[QImage]:
            painter.setTransform(self.transform)
            if paint_param_adjuster is not None:
                return paint_param_adjuster(layer_id, layer_image, paint_bounds, painter)
            return None
        return super().render(base_image, _transform_adjuster)
