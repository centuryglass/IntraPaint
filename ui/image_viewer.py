"""
A PyQt5 widget wrapper for data_model/layer_stack.
"""
from typing import Optional
from PyQt5.QtWidgets import QWidget, QSizePolicy, QGraphicsPixmapItem
from PyQt5.QtGui import QPen, QPainter
from PyQt5.QtCore import Qt, QRect, QRectF, QSize, QPoint, QEvent

from ui.widget.fixed_aspect_graphics_view import FixedAspectGraphicsView
from data_model.layer_stack import LayerStack
from data_model.image_layer import ImageLayer
from util.validation import assert_type

class ImageViewer(FixedAspectGraphicsView):
    """Shows the image being edited, and allows the user to select sections."""

    class LayerItem(QGraphicsPixmapItem):
        """Renders an image layer into a QGraphicsScene."""

        def __init__(self, layer: ImageLayer):
            super().__init__()
            assert_type(layer, ImageLayer)
            self._layer = layer
            layer.pixmap_changed.connect(self.setPixmap)
            layer.visibility_changed.connect(self.setVisible)
            layer.content_changed.connect(self.update)
            self.setVisible(layer.visible)


    def __init__(self, parent: Optional[QWidget], layer_stack: LayerStack):
        super().__init__(parent)
        self._layer_stack = layer_stack
        self._selection = layer_stack.selection
        self._layer_items = {}
        self.content_size = layer_stack.size
        self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))

        # Connect layer stack event handlers:
        layer_stack.visible_content_changed.connect(self.update)

        def set_size(new_size: QSize):
            self.content_size = new_size
        layer_stack.size_changed.connect(set_size)

        def update_selection(new_rect: QRect, unused_last_rect: QRect):
            self._selection = new_rect
            self.resetCachedContent()
            self.update()
        layer_stack.selection_bounds_changed.connect(update_selection)

        def add_layer(layer: ImageLayer, index: int):
            layer_item = ImageViewer.LayerItem(layer)
            layer_item.setZValue(index)
            self._layer_items[layer] = layer_item
            self.scene().addItem(layer_item)
            if layer_item.isVisible():
                self.update()
        layer_stack.layer_added.connect(add_layer)

        def remove_layer(layer: ImageLayer):
            layer_item = self._layer_items[layer]
            self.scene().removeItem(layer_item)
            for item in self._layer_items.values():
                if item.zValue() > layer_item.zValue():
                    item.setZValue(item.zValue() - 1)
            del self._layer_items[layer]
            if layer_item.visible():
                self.update()
        layer_stack.layer_removed.connect(remove_layer)
        self.resizeEvent(None)

        for i in range(layer_stack.count()):
            layer = self._layer_stack.get_layer(i)
            add_layer(layer, i)


    def sizeHint(self) -> QSize:
        """Returns image size as ideal widget size."""
        return self.content_size


    def mousePressEvent(self, event: QEvent):
        """Select the area in in the image to be edited."""
        if event.button() == Qt.LeftButton and self._layer_stack.has_image:
            image_coords = self.widget_to_scene_coords(event.pos())
            selection = self._layer_stack.selection
            selection.moveTopLeft(image_coords.toPoint())
            self._layer_stack.selection = selection

    def drawForeground(self, painter: QPainter, rect: QRectF):
        """Draws the selection rect over the image content."""
        super().drawForeground(painter, rect)
        if self._layer_stack.has_image:
            selection = self._layer_stack.selection
            scene_top_left = QPoint(selection.x(), selection.y())
            painter_top_left = self.scene_point_to_painter_coords(scene_top_left, rect)
            scene_bottom_right = QPoint(selection.x() + selection.width(), selection.y() + selection.height())
            painter_bottom_right = self.scene_point_to_painter_coords(scene_bottom_right, rect)
            painter_rect = QRectF(painter_top_left.x(), painter_top_left.y(),
                    painter_bottom_right.x() - painter_top_left.x(),
                    painter_bottom_right.y() - painter_top_left.y())
            painter_rect.adjust(-2.0, -2.0, 2.0, 2.0)
            line_pen = QPen(Qt.black, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(line_pen)
            painter.drawRect(painter_rect)
