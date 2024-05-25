"""
A PyQt5 widget wrapper for the LayerStack class.
"""
from typing import Optional
from PyQt5.QtWidgets import QWidget, QSizePolicy, QGraphicsPixmapItem
from PyQt5.QtGui import QPen, QPainter, QMouseEvent
from PyQt5.QtCore import Qt, QRect, QRectF, QSize, QPoint

from src.ui.util.tile_pattern_fill import get_transparency_tile_pixmap
from src.ui.widget.fixed_aspect_graphics_view import FixedAspectGraphicsView
from src.image.layer_stack import LayerStack
from src.image.image_layer import ImageLayer
from src.util.validation import assert_type



class ImageViewer(FixedAspectGraphicsView):
    """Shows the image being edited, and allows the user to select sections."""

    class LayerItem(QGraphicsPixmapItem):
        """Renders an image layer into a QGraphicsScene."""

        def __init__(self, layer: ImageLayer):
            super().__init__()
            assert_type(layer, ImageLayer)
            self._layer = layer
            def update_pixmap() -> None:
                self.setPixmap(layer.pixmap)
                self.update()
            layer.visibility_changed.connect(self.setVisible)
            layer.content_changed.connect(update_pixmap)
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

        def set_size(new_size: QSize) -> None:
            """Update bounds and background when the image size changes."""
            if new_size.width() <= 0 or new_size.height() <= 0:
                return
            self.content_size = new_size
            self.background = get_transparency_tile_pixmap()
            self.resizeEvent(None)

        layer_stack.size_changed.connect(set_size)
        set_size(self.content_size)

        def update_selection(new_rect: QRect, unused_last_rect: QRect) -> None:
            """Update the viewer content when the selection changes."""
            self._selection = new_rect
            self.resetCachedContent()
            self.update()

        layer_stack.selection_bounds_changed.connect(update_selection)

        def add_layer(new_layer: ImageLayer, index: int) -> None:
            """Adds an image layer into the view."""
            layer_item = ImageViewer.LayerItem(new_layer)
            layer_item.setZValue(index)
            self._layer_items[new_layer] = layer_item
            self.scene().addItem(layer_item)
            if layer_item.isVisible():
                self.resetCachedContent()
                self.update()

        layer_stack.layer_added.connect(add_layer)
        for i in range(layer_stack.count()):
            add_layer(layer_stack.get_layer(i), i)

        def remove_layer(removed_layer: ImageLayer) -> None:
            """Removes an image layer from the view."""
            layer_item = self._layer_items[removed_layer]
            self.scene().removeItem(layer_item)
            for item in self._layer_items.values():
                if item.zValue() > layer_item.zValue():
                    item.setZValue(item.zValue() - 1)
            del self._layer_items[removed_layer]
            if layer_item.visible():
                self.update()

        layer_stack.layer_removed.connect(remove_layer)
        self.resizeEvent(None)
        # Add initial layers to the view:
        for i in range(layer_stack.count()):
            layer = self._layer_stack.get_layer(i)
            add_layer(layer, i)

    def sizeHint(self) -> QSize:
        """Returns image size as ideal widget size."""
        return self.content_size

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Select the area in the image to be edited."""
        if event.button() == Qt.LeftButton and self._layer_stack.has_image:
            image_coordinates = self.widget_to_scene_coordinates(event.pos())
            selection = self._layer_stack.selection
            selection.moveTopLeft(image_coordinates.toPoint())
            self._layer_stack.selection = selection

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        """Draw the background as a fixed size tiling image."""
        if painter is None:
            return
        painter.save()
        painter.scale(rect.width() / self.width(), rect.height() / self.height())
        painter.drawTiledPixmap(painter.viewport(), self.background)
        painter.restore()

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        """Draws the selection rect over the image content."""
        super().drawForeground(painter, rect)
        if self._layer_stack.has_image:
            selection = self._layer_stack.selection
            scene_top_left = QPoint(selection.x(), selection.y())
            painter_top_left = self.scene_point_to_painter_coordinates(scene_top_left, rect)
            scene_bottom_right = QPoint(selection.x() + selection.width(), selection.y() + selection.height())
            painter_bottom_right = self.scene_point_to_painter_coordinates(scene_bottom_right, rect)
            painter_rect = QRectF(painter_top_left.x(), painter_top_left.y(),
                                  painter_bottom_right.x() - painter_top_left.x(),
                                  painter_bottom_right.y() - painter_top_left.y())
            painter_rect.adjust(-2.0, -2.0, 2.0, 2.0)
            line_pen = QPen(Qt.black, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(line_pen)
            painter.drawRect(painter_rect)
