"""Interface for layers that have a persistent transformation."""
from typing import Optional, Callable

from PySide6.QtCore import QObject, Signal, QRect, QPoint, QPointF, QRectF
from PySide6.QtGui import QPainter, QImage, QTransform

from src.image.layers.layer import Layer
from src.util.visual.geometry_utils import (extract_transform_parameters, combine_transform_parameters,
                                           map_rect_precise, transform_needs_smooth_sampling)
from src.util.visual.image_utils import create_transparent_image


class TransformLayer(Layer):
    """Interface for layers that have a persistent transformation."""

    transform_changed = Signal(QObject, QTransform)

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self._transform = QTransform()
        self._raster: Optional[tuple[QPoint, QImage]] = None

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

    def set_transform(self, transform: QTransform) -> None:
        """Updates the layer's matrix transformation, reporting both the old and new areas as changed."""
        if transform != self._transform:
            assert transform.isInvertible(), f'layer {self.name}:{self.id} given non-invertible transform'
            old_transform = self._transform
            self._transform = transform
            self._raster = None
            self.transform_changed.emit(self, transform)
            if self.visible and self.opacity > 0.0:
                self.signal_content_changed(self.transform_change_bounds(old_transform))

    def map_changed_rect_to_image(self, layer_rect: QRect) -> QRect:
        """Returns the image area that changing layer_rect can affect, given the layer's current transform.

        Under a transform that needs smooth sampling, the area extends one pixel past the mapped rect.
        """
        return self._changed_image_area(layer_rect, self._transform)

    def transform_change_bounds(self, old_transform: QTransform) -> QRect:
        """Returns a rect in layer coordinates that covers the layer's area under both old_transform and its current
           transform, once mapped with map_changed_rect_to_image."""
        old_area = self._changed_image_area(self.bounds, old_transform)
        return self.bounds.united(self.map_rect_from_image(old_area))

    @staticmethod
    def _changed_image_area(layer_rect: QRect, transform: QTransform) -> QRect:
        image_rect = map_rect_precise(layer_rect, transform).toAlignedRect()
        if transform_needs_smooth_sampling(transform):
            image_rect.adjust(-1, -1, 1, 1)
        return image_rect

    def transformed_image(self) -> tuple[QImage, QTransform]:
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
        if transform_needs_smooth_sampling(paint_transform):
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
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
        """Rotate the layer clockwise on the canvas about its center, on top of any previous transformations."""
        center = QRectF(self.bounds).center()
        x_off, y_off, x_scale, y_scale, base_angle = extract_transform_parameters(self.transform, center)
        self.transform = combine_transform_parameters(x_off, y_off, x_scale, y_scale, base_angle + degrees, center)

    def _flip(self, horizontal: bool = True) -> None:
        center = QRectF(self.bounds).center()
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

    def render(self, base_image: QImage, transform: Optional[QTransform] = None,
               image_bounds: Optional[QRect] = None, z_max: Optional[int] = None,
               image_adjuster: Optional[Callable[['Layer', QImage], QImage]] = None,
               returned_mask: Optional[QImage] = None) -> None:
        """Renders the layer to QImage, optionally specifying render bounds, transformation, a z-level cutoff, and/or
           a final image transformation function.

        Parameters
        ----------
        base_image: QImage, optional, default=None.
            The base image that all layer content will be painted onto.
        transform: QTransform, optional, default=None
            Optional transformation to apply to image content before rendering.
        image_bounds: QRect, optional, default=None.
            Optional bounds that should be rendered within the base image. If None, the intersection of the base and the
            transformed layer will be used.  If base_image was None, image content will be translated so that the
            position of the bounded region is at (0, 0) within the new base image.
        z_max: int, optional, default=None
            If not None, rendering will be blocked at z-levels above this number.
        image_adjuster: Callable[[Layer, QImage], QImage], optional, default=None
            If not None, apply this final transformation function to the rendered image and return the result.
        returned_mask: QImage, optional, default=None
            If not None, draw the rendered bounds onto this image, to use when determining what parts of the base image
            were rendered onto.
        """
        raster_offset = self._integer_translation(transform)
        if raster_offset is not None and image_adjuster is None and transform_needs_smooth_sampling(self._transform):
            raster = self._image_space_raster()
            if raster is not None:
                origin, raster_image = raster
                self._render_image(raster_image, QRect(QPoint(), raster_image.size()), base_image,
                                   QTransform.fromTranslate(origin.x() + raster_offset.x(),
                                                            origin.y() + raster_offset.y()),
                                   image_bounds, z_max, None, returned_mask)
                return
        if transform is None:
            transform = self.transform
        else:
            transform = self.transform * transform
        super().render(base_image, transform, image_bounds, z_max, image_adjuster, returned_mask)

    @staticmethod
    def _integer_translation(transform: Optional[QTransform]) -> Optional[QPoint]:
        """Returns the offset if transform is None or a whole-pixel translation, and None for anything else."""
        if transform is None:
            return QPoint()
        if transform == QTransform.fromTranslate(transform.dx(), transform.dy()) \
                and transform.dx() == round(transform.dx()) and transform.dy() == round(transform.dy()):
            return QPoint(round(transform.dx()), round(transform.dy()))
        return None

    def signal_content_changed(self, change_bounds: QRect) -> None:
        """Updates the cached raster to match the change before reporting it."""
        self._update_raster(change_bounds)
        super().signal_content_changed(change_bounds)

    def invalidate_pixmap(self) -> None:
        """Marks the cached pixmap and the cached raster as out of date."""
        self._raster = None
        super().invalidate_pixmap()

    def _paint_raster(self, raster_image: QImage, origin: QPoint, area: QRect) -> None:
        """Redraws the part of the raster inside area (in raster coordinates) from the layer image."""
        painter = QPainter(raster_image)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.setClipRect(area)
        painter.setTransform(self._transform * QTransform.fromTranslate(-origin.x(), -origin.y()))
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawImage(self.bounds, self.get_qimage())
        painter.end()

    def _image_space_raster(self) -> Optional[tuple[QPoint, QImage]]:
        """Returns the layer image drawn through its transform, with the image position of its top left corner.

        Scaled and rotated layers are composited from this image with whole-pixel translations, so every pixel is
        sampled once from the layer image, whatever region of the canvas is being rendered. The raster is rebuilt
        when the transform changes, and its changed area is redrawn when the layer content changes.
        """
        if self._raster is None:
            layer_image = self.get_qimage()
            if layer_image is None or layer_image.isNull():
                return None
            area = self._changed_image_area(self.bounds, self._transform)
            if area.isEmpty():
                return None
            raster_image = create_transparent_image(area.size())
            origin = area.topLeft()
            self._paint_raster(raster_image, origin, QRect(QPoint(), area.size()))
            self._raster = (origin, raster_image)
        return self._raster

    def _update_raster(self, layer_change_bounds: QRect) -> None:
        """Redraws the part of the cached raster that a layer content change affects, dropping it if the layer
           size changed."""
        if self._raster is None:
            return
        origin, raster_image = self._raster
        if self._changed_image_area(self.bounds, self._transform).size() != raster_image.size():
            self._raster = None
            return
        area = self._changed_image_area(layer_change_bounds, self._transform).translated(-origin)
        area = area.intersected(QRect(QPoint(), raster_image.size()))
        if not area.isEmpty():
            self._paint_raster(raster_image, origin, area)

    def render_to_new_image(self, transform: Optional[QTransform] = None,
                            inner_bounds: Optional[QRect] = None, z_max: Optional[int] = None,
                            image_adjuster: Optional[Callable[['Layer', QImage], QImage]] = None) -> QImage:
        """Render the layer to a new image, adjusting offset so that layer content fits exactly into the image."""

        if transform is None:
            transform = self.transform
        else:
            transform = self.transform * transform
        bounds = map_rect_precise(self.bounds, transform).toAlignedRect()
        if inner_bounds is not None:
            bounds = bounds.intersected(inner_bounds)
        if not bounds.topLeft().isNull():
            if transform is None:
                transform = QTransform.fromTranslate(-bounds.x(), -bounds.y())
            else:
                transform = transform * QTransform.fromTranslate(-bounds.x(), -bounds.y())
        base_image = create_transparent_image(bounds.size())
        super().render(base_image, transform, image_bounds=bounds.translated(-bounds.x(), -bounds.y()),
                       z_max=z_max,
                       image_adjuster=image_adjuster)
        return base_image
