"""
A PyQt5 widget wrapper for the LayerStack class.
"""
import math
from typing import Optional

from PyQt5.QtCore import Qt, QRect, QRectF, QSize, QPoint, QPointF, QEvent
from PyQt5.QtGui import QPen, QPainter, QMouseEvent, QPixmap
from PyQt5.QtWidgets import QWidget, QSizePolicy, QGraphicsPixmapItem, QApplication

from src.image.image_layer import ImageLayer
from src.image.layer_stack import LayerStack
from src.ui.util.tile_pattern_fill import get_transparency_tile_pixmap
from src.ui.widget.fixed_aspect_graphics_view import FixedAspectGraphicsView
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
                """Keep the graphics item pixmap in sync with the layer."""
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
        self.background = get_transparency_tile_pixmap()
        self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        self.installEventFilter(self)

        # Selection and border rectangle setup:
        self._selection_item = QGraphicsPixmapItem()
        self._selection_pixmap: Optional[QPixmap] = None
        self.scene().addItem(self._selection_item)

        self._border_item = QGraphicsPixmapItem()
        self._border_pixmap: Optional[QPixmap] = None
        self.scene().addItem(self._border_item)

        # Selection offset handling:
        self._drag_pt: Optional[QPoint] = None

        # Connect layer stack event handlers:
        layer_stack.visible_content_changed.connect(self.update)

        def set_size(new_size: QSize) -> None:
            """Update bounds and background when the image size changes."""
            if new_size.width() <= 0 or new_size.height() <= 0:
                return
            self.content_size = new_size
            self._update_drawn_borders()
            self.resizeEvent(None)

        layer_stack.size_changed.connect(set_size)
        set_size(self.content_size)

        def update_selection(new_rect: QRect, unused_last_rect: Optional[QRect]) -> None:
            """Update the viewer content when the selection changes."""
            self._selection = new_rect
            self._update_drawn_borders()
            self.resetCachedContent()
            self.update()

        layer_stack.selection_bounds_changed.connect(update_selection)

        def add_layer(new_layer: ImageLayer, index: int) -> None:
            """Adds an image layer into the view."""
            layer_item = ImageViewer.LayerItem(new_layer)
            layer_item.setZValue(index)
            self._layer_items[new_layer] = layer_item
            self.scene().addItem(layer_item)
            self._selection_item.setZValue(max(self._selection_item.zValue(), index + 1))
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
        update_selection(layer_stack.selection, None)

    def _update_border_rect_item(self, scene_item: QGraphicsPixmapItem, pixmap: Optional[QPixmap],
                                 rect: QRect) -> QPixmap:
        """Move and redraw a pixmap item so that it outlines a rectangle in the scene."""
        scene_item.setPos(rect.x() - 5, rect.y() - 5)
        if pixmap is not None and pixmap.size() == self._selection.size():
            return pixmap
        pixmap = QPixmap(QSize(rect.width() + 10, rect.height() + 10))
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        line_pen = QPen(Qt.black, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(line_pen)
        painter_rect = QRect(0, 0, pixmap.width(), pixmap.height())
        painter.drawRect(painter_rect)
        line_pen.setColor(Qt.white)
        painter.setPen(line_pen)
        painter_rect.adjust(2, 2, -2, -2)
        painter.drawRect(painter_rect)
        line_pen.setColor(Qt.black)
        painter.setPen(line_pen)
        painter_rect.adjust(2, 2, -2, -2)
        painter.drawRect(painter_rect)
        scene_item.setPixmap(pixmap)
        return pixmap

    def _update_drawn_borders(self):
        """Make sure that the selection and image borders are in the right place in the scene."""
        self._selection_pixmap = self._update_border_rect_item(self._selection_item, self._selection_pixmap,
                                                               self._selection)
        self._border_pixmap = self._update_border_rect_item(self._border_item, self._border_pixmap,
                                                            QRect(QPoint(0, 0), self.content_size))

    def sizeHint(self) -> QSize:
        """Returns image size as ideal widget size."""
        return self.content_size

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Select the area in the image to be edited."""
        if not self._layer_stack.has_image or event is None:
            return
        key_modifiers = QApplication.keyboardModifiers()
        if event.buttons() == Qt.MouseButton.MiddleButton or (event.buttons() == Qt.MouseButton.LeftButton
                                                              and key_modifiers == Qt.ControlModifier):
            self._drag_pt = event.pos()
        elif event.button() == Qt.LeftButton and self._layer_stack.has_image:
            image_coordinates = self.widget_to_scene_coordinates(event.pos())
            selection = self._layer_stack.selection
            selection.moveTopLeft(image_coordinates.toPoint())
            self._layer_stack.selection = selection

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
        """Adjust the offset when the widget is dragged with ctrl+LMB or MMB."""
        if self._drag_pt is not None and event is not None:
            key_modifiers = QApplication.keyboardModifiers()
            if event.buttons() == Qt.MouseButton.MiddleButton or (event.buttons() == Qt.MouseButton.LeftButton
                                                                  and key_modifiers == Qt.ControlModifier):
                mouse_pt = event.pos()
                scale = self.scale
                x_off = (self._drag_pt.x() - mouse_pt.x()) / scale
                y_off = (self._drag_pt.y() - mouse_pt.y()) / scale
                distance = math.sqrt(x_off**2 + y_off**2)
                if distance < 1:
                    return
                self.offset = QPointF(self.offset.x() + x_off, self.offset.y() + y_off)
                self._drag_pt = mouse_pt
            else:
                self._drag_pt = None

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        """Draw the background as a fixed size tiling image."""
        if painter is None:
            return
        painter.drawTiledPixmap(rect, self.background)

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        """Don't draw borders around the image content."""
        return

    def eventFilter(self, source, event: QEvent):
        """Intercept mouse wheel events, use for scrolling in zoom mode:"""
        if event.type() == QEvent.Wheel:
            if event.angleDelta().y() > 0:
                self.scale = self.scale + 0.05
            elif event.angleDelta().y() < 0 and self.scale > 0.05:
                self.scale = self.scale - 0.05
            self.resizeEvent(None)
            return True
        return super().eventFilter(source, event)
