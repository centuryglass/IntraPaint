"""
Draws content to an image layer using basic Qt drawing operations.
"""
from typing import Optional

from PyQt5.QtCore import QRect, Qt, QPoint, QPointF, QRectF
from PyQt5.QtGui import QPainter, QPixmap, QPen
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsPixmapItem

from src.image.canvas.layer_canvas import LayerCanvas
from src.image.image_layer import ImageLayer
from src.undo_stack import commit_action

ACTIVE_PIXMAP_OPACITY = 0.4

INACTIVE_PIXMAP_OPACITY = 0.2


class PixmapLayerCanvas(LayerCanvas):
    """Draws content to an image layer using basic Qt drawing operations."""

    def __init__(self, scene: QGraphicsScene, layer: Optional[ImageLayer] = None,
                 edit_region: Optional[QRect] = None) -> None:
        """Initialize a MyPaint surface, and connect to the image layer."""
        super().__init__(scene, layer, edit_region)
        self._pixmap_item: Optional[QGraphicsPixmapItem] = None
        self._last_point: Optional[QPoint] = None
        self._scene = scene
        self.edit_region = edit_region
        self._change_bounds = QRectF()

    def start_stroke(self) -> None:
        self._change_bounds = QRectF()
        super().start_stroke()
        if self._pixmap_item is not None:
            self._pixmap_item.setOpacity(ACTIVE_PIXMAP_OPACITY)

    def end_stroke(self) -> None:
        """Finishes a brush stroke, copying it back to the layer."""
        super().end_stroke()
        self._last_point = None
        self._change_bounds = QRectF()
        if self._pixmap_item is not None:
            self._pixmap_item.setOpacity(INACTIVE_PIXMAP_OPACITY)

    def _update_canvas_position(self, _, new_position: QPoint) -> None:
        """Updates the canvas position within the graphics scene."""
        assert self._pixmap_item is not None
        self._pixmap_item.setPos(new_position)

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
            self._pixmap_item = QGraphicsPixmapItem(pixmap)
            self._pixmap_item.setZValue(self.z_value)
            self._pixmap_item.setOpacity(INACTIVE_PIXMAP_OPACITY)
            self._scene.addItem(self._pixmap_item)
        self._pixmap_item.setPixmap(pixmap)
        self._pixmap_item.setPos(new_bounds.topLeft())

    def _draw(self, x: float, y: float, pressure: Optional[float], x_tilt: Optional[float],
              y_tilt: Optional[float]) -> None:
        """Use active settings to draw to the canvas with the given inputs."""
        if self._pixmap_item is None or self.edit_region is None:
            return
        pixmap = QPixmap(self._pixmap_item.pixmap().size())
        pixmap.swap(self._pixmap_item.pixmap())
        painter = QPainter(pixmap)
        if self.eraser:
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
        size = self.brush_size
        if pressure is not None:
            size = max(int(size * pressure), 1)
        pen = QPen(self.brush_color, size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        change_pt = QPointF(x - self.edit_region.x(), y - self.edit_region.y())
        last_pt = None if self._last_point is None else QPointF(self._last_point.x() - self.edit_region.x(),
                                                                self._last_point.y() - self.edit_region.y())
        if last_pt is None:
            painter.drawPoint(change_pt)
        else:
            painter.drawLine(last_pt, change_pt)
        change_bounds = QRectF(change_pt.x() - size, change_pt.y() - size, size * 2, size * 2)
        if self._change_bounds.isEmpty():
            self._change_bounds = change_bounds
        else:
            self._change_bounds = self._change_bounds.united(change_bounds)
        painter.end()
        self._last_point = QPoint(int(x), int(y))
        self._pixmap_item.setPixmap(pixmap)

    def _load_layer_content(self, layer: Optional[ImageLayer]) -> None:
        """Refreshes the layer content within the canvas, or clears it if the layer is hidden."""
        assert self._layer == layer and self._edit_region is not None
        if self._pixmap_item is None:
            return
        if layer is not None and layer.visible:
            pixmap = QPixmap.fromImage(layer.cropped_image_content(self._edit_region))
        else:
            pixmap = QPixmap(self._edit_region.size())
            pixmap.fill(Qt.GlobalColor.transparent)
        self._pixmap_item.setPixmap(pixmap)

    def _copy_changes_to_layer(self, use_stroke_bounds: bool = False):
        """Copies content back to the connected layer."""
        if self._layer is not None and self._layer.visible and self._pixmap_item is not None \
                and self._edit_region is not None and not self._edit_region.isEmpty():
            change_bounds = self._change_bounds.toAlignedRect().intersected(self._edit_region)
            if change_bounds.isEmpty():
                return
            image = self._pixmap_item.pixmap().toImage().copy(change_bounds)
            prev_image = self._layer.cropped_image_content(change_bounds)
            layer = self._layer

            def apply():
                """Copy the change into the image."""
                layer.insert_image_content(image, change_bounds)

            def reverse():
                """To undo, copy in the cached previous image data."""
                layer.insert_image_content(prev_image, change_bounds)
                self._load_layer_content(layer)

            self._layer.visibility_changed.disconnect(self._load_layer_content)
            self._layer.content_changed.disconnect(self._load_layer_content)
            commit_action(apply, reverse)
            self._layer.visibility_changed.connect(self._load_layer_content)
            self._layer.content_changed.connect(self._load_layer_content)
