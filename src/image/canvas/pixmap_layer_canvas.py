"""
Draws content to an image layer using basic Qt drawing operations.
"""
from typing import Optional, List

from PySide6.QtCore import QRect, Qt, QPoint, QPointF, QRectF
from PySide6.QtGui import QPainter, QPixmap, QPen, QTransform, QImage
from PySide6.QtWidgets import QGraphicsScene, QGraphicsItem

from src.image.canvas.layer_canvas import LayerCanvas
from src.image.composite_mode import CompositeMode
from src.image.layers.image_layer import ImageLayer
from src.ui.graphics_items.pixmap_item import PixmapItem


class PixmapLayerCanvas(LayerCanvas):
    """Draws content to an image layer using basic Qt drawing operations."""

    def __init__(self, scene: QGraphicsScene, layer: Optional[ImageLayer] = None) -> None:
        """Initialize a MyPaint surface, and connect to the image layer."""
        super().__init__(scene, layer)
        self._pixmap_item: Optional[PixmapItem] = None
        self._last_point: Optional[QPoint] = None
        self._scene = scene
        self._change_bounds = QRectF()
        self._mask: Optional[QImage] = None
        self._active_opacity = 1.0
        self._inactive_opacity = 1.0

    @property
    def active_opacity(self) -> float:
        """Returns the canvas opacity while drawing is in progress."""
        return self._active_opacity

    @active_opacity.setter
    def active_opacity(self, opacity: float) -> None:
        self._active_opacity = opacity
        if self.drawing and self._pixmap_item is not None:
            self._pixmap_item.setOpacity(opacity)

    @property
    def inactive_opacity(self) -> float:
        """Returns the canvas opacity while drawing is not in progress."""
        return self._inactive_opacity

    @inactive_opacity.setter
    def inactive_opacity(self, inactive_opacity: float) -> None:
        self._inactive_opacity = inactive_opacity
        if not self.drawing and self._pixmap_item is not None:
            self._pixmap_item.setOpacity(inactive_opacity)

    def start_stroke(self) -> None:
        self._change_bounds = QRectF()
        super().start_stroke()
        if self._pixmap_item is not None:
            self._pixmap_item.setOpacity(self.active_opacity)

    def end_stroke(self) -> None:
        """Finishes a brush stroke, copying it back to the layer."""
        super().end_stroke()
        self._last_point = None
        self._change_bounds = QRectF()
        if self._pixmap_item is not None:
            self._pixmap_item.setOpacity(self.inactive_opacity)

    def scene_items(self) -> List[QGraphicsItem]:
        """Returns all graphics items present in the scene that belong to the canvas."""
        return [self._pixmap_item] if self._pixmap_item is not None else []

    def set_input_mask(self, mask_image: Optional[QImage]) -> None:
        """Sets a mask image, restricting canvas changes to areas covered by non-transparent mask areas"""
        self._mask = mask_image

    def _update_canvas_transform(self, layer: ImageLayer, transform: QTransform) -> None:
        """Updates the canvas transformation within the graphics scene."""
        assert self._pixmap_item is not None
        self._pixmap_item.setTransform(layer.transform)

    def _set_z_value(self, z_value: int) -> None:
        """Updates the level where content will be shown in a GraphicsScene."""
        super()._set_z_value(z_value)
        if self._pixmap_item is not None:
            self._pixmap_item.setZValue(z_value)
            self._pixmap_item.update()

    def _update_scene_content_bounds(self, new_bounds: QRect) -> None:
        """Resize the internal graphics representation."""
        pixmap = QPixmap(new_bounds.size())
        pixmap.fill(Qt.GlobalColor.transparent)
        if self._pixmap_item is None:
            self._pixmap_item = PixmapItem(pixmap)
            self._pixmap_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemStacksBehindParent, True)
            self._pixmap_item.setZValue(self.z_value)
            self._pixmap_item.setOpacity(self._inactive_opacity)
            self._scene.addItem(self._pixmap_item)
        self._pixmap_item.setPixmap(pixmap)
        self._pixmap_item.setPos(QPointF(new_bounds.topLeft()))

    def _draw(self, x: float, y: float, pressure: Optional[float], x_tilt: Optional[float],
              y_tilt: Optional[float]) -> None:
        """Use active settings to draw to the canvas with the given inputs."""
        layer = self.layer
        if self._pixmap_item is None or layer is None:
            return
        layer_bounds = layer.bounds
        pixmap = QPixmap(self._pixmap_item.pixmap().size())
        pixmap.swap(self._pixmap_item.pixmap())
        size = self.brush_size
        if pressure is not None:
            size = max(int(size * pressure), 1)

        change_pt = QPointF(x - layer_bounds.x(), y - layer_bounds.y())
        last_pt = None if self._last_point is None else QPointF(self._last_point.x() - layer_bounds.x(),
                                                                self._last_point.y() - layer_bounds.y())
        change_bounds = QRectF(change_pt.x() - size, change_pt.y() - size, size * 2, size * 2)
        if self._mask is not None:
            buffer: Optional[QPixmap] = pixmap.copy(change_bounds.toAlignedRect())
            painter = QPainter(buffer)
            offset: Optional[QPoint] = change_bounds.toAlignedRect().topLeft()
            assert isinstance(offset, QPoint)
            painter.setTransform(QTransform.fromTranslate(-offset.x(), -offset.y()))
        else:
            buffer = None
            offset = None
            painter = QPainter(pixmap)
        if self.eraser:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        pen = QPen(self.brush_color, size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        if last_pt is None:
            painter.drawPoint(change_pt)
        else:
            painter.drawLine(last_pt, change_pt)
        if self._change_bounds.isEmpty():
            self._change_bounds = change_bounds
        else:
            self._change_bounds = self._change_bounds.united(change_bounds)
        if buffer is not None:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            painter.drawImage(QPoint(), self._mask)
        painter.end()

        if buffer is not None and offset is not None:
            final_painter = QPainter(pixmap)
            final_painter.drawImage(offset, self._mask)
            final_painter.end()
        self._last_point = QPoint(int(x), int(y))
        self._pixmap_item.setPixmap(pixmap)

    def _layer_content_change_slot(self, layer: Optional[ImageLayer]) -> None:
        """Refreshes the layer content within the canvas, or clears it if the layer is hidden."""
        assert self._layer == layer, f'change from:{layer}, but connected to {self.layer}'
        if self._pixmap_item is None:
            return
        if layer is not None and layer.visible:
            pixmap = QPixmap.fromImage(layer.image)
        else:
            pixmap = QPixmap(self._pixmap_item.pixmap().size())
            pixmap.fill(Qt.GlobalColor.transparent)
        self._pixmap_item.setPixmap(pixmap)

    def _layer_composition_mode_change_slot(self, layer: ImageLayer, mode: CompositeMode) -> None:
        assert layer == self.layer
        assert self._pixmap_item is not None
        self._pixmap_item.composition_mode = mode

    def _layer_z_value_change_slot(self, layer: ImageLayer, z_value: int) -> None:
        super()._layer_z_value_change_slot(layer, z_value)
        if self._pixmap_item is not None:
            self._pixmap_item.setZValue(z_value)

    def _copy_changes_to_layer(self, layer: ImageLayer):
        """Copies content back to the connected layer."""
        if self.layer is not None and self.layer.visible and self._pixmap_item is not None:
            layer = self.layer
            change_bounds = self._change_bounds.toAlignedRect().intersected(layer.bounds)
            if change_bounds.isEmpty():
                return
            image = self._pixmap_item.pixmap().toImage().copy(change_bounds)

            self.disconnect_layer_signals()
            layer.insert_image_content(image, change_bounds, register_to_undo_history=True)
            self.connect_layer_signals()
