"""Renders an image layer into a QGraphicsScene."""
from typing import Optional

from PySide6.QtCore import QRect, QObject, QPoint, QRectF, Qt
from PySide6.QtGui import QTransform, QPixmap, QPainter, QPainterPath
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget

from src.image.composite_mode import CompositeMode
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.image.layers.selection_layer import SelectionLayer
from src.image.layers.transform_layer import TransformLayer
from src.ui.graphics_items.pixmap_item import PixmapItem


class LayerGraphicsItem(PixmapItem):
    """Renders an image layer or text layer into a QGraphicsScene.

    A LayerGroup's pixmap is its finished composite, with the group's own opacity and composition mode already
    applied, so the item shows it at full opacity in Normal mode.

    The item keeps its own pixmap, separate from `Layer.pixmap` and from QGraphicsPixmapItem's storage, so it is the
    pixmap's only owner and a content change paints just the changed area into it. Any other reference held while a
    change arrives makes that paint copy the whole pixmap first.
    """

    def __init__(self, layer: Layer):
        super().__init__()
        self._layer = layer
        self._pixmap = QPixmap()
        # The layer position the pixmap's top left corner shows, in the coordinates content_changed uses:
        self._pixmap_origin = QPoint()
        self._hidden = False
        self._pending_bounds = QRect()
        self.composition_mode = self._display_mode()

        # The item isn't a QObject, so Qt can't drop these connections when it's deleted. See disconnect_layer.
        self._connections = [
            layer.visibility_changed.connect(self._update_visibility),
            layer.content_changed.connect(self._update_pixmap),
            layer.opacity_changed.connect(self._update_opacity),
            layer.z_value_changed.connect(lambda _, z_value: self.setZValue(z_value)),
            layer.composition_mode_changed.connect(self._update_mode)
        ]
        if isinstance(layer, TransformLayer):
            self._connections.append(layer.transform_changed.connect(self._update_transform))
        elif isinstance(layer, LayerGroup):
            self._connections.append(layer.bounds_changed.connect(self._update_bounds))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemStacksBehindParent, True)

        self.setOpacity(self._display_opacity())
        if isinstance(layer, TransformLayer):
            self.setTransform(layer.transform)
        elif isinstance(layer, LayerGroup):
            bounds = layer.bounds
            self.setTransform(QTransform.fromTranslate(bounds.x(), bounds.y()))
        self.setVisible(layer.visible)
        self.setZValue(layer.z_value)
        self._update_pixmap(layer)

    @property
    def layer(self) -> Layer:
        """Returns the rendered image layer."""
        return self._layer

    def disconnect_layer(self) -> None:
        """Stops following the layer's changes. Call this before deleting the item or removing it from its scene.

        Connections left in place keep the item alive, and the layer's signals keep updating it after its scene deleted
        it.
        """
        for connection in self._connections:
            QObject.disconnect(connection)
        self._connections.clear()

    @property
    def hidden(self) -> bool:
        """Returns whether this layer is currently hidden."""
        return self._hidden

    @hidden.setter
    def hidden(self, hidden: bool) -> None:
        """Sets whether the layer should be hidden in the view regardless of layer visibility."""
        self._hidden = hidden
        self.setVisible(self._layer.visible and not hidden)

    def pixmap(self) -> QPixmap:
        """Returns a shallow copy of the displayed pixmap. Holding it makes the next content change copy the pixmap."""
        return QPixmap(self._pixmap)

    def boundingRect(self) -> QRectF:
        """Returns the pixmap's area, in item coordinates."""
        return QRectF(self._pixmap.rect())

    def shape(self) -> QPainterPath:
        """Returns the pixmap's area as the item's shape, ignoring transparency."""
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def _paint_pixmap(self,
                      painter: QPainter,
                      option: Optional[QStyleOptionGraphicsItem],
                      widget: Optional[QWidget]) -> None:
        """Draws the item's own pixmap the way QGraphicsPixmapItem draws its stored one."""
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,
                              self.transformationMode() == Qt.TransformationMode.SmoothTransformation)
        painter.drawPixmap(QPoint(), self._pixmap)

    def _update_pixmap(self, _layer: Optional[Layer] = None, changed_rect: Optional[QRect] = None) -> None:
        """Updates the pixmap from the layer's image, repainting only changed_rect while its size and origin hold.

        Empty or missing changed_rect rebuilds the whole pixmap, so content outside a non-empty changed_rect must be
        unchanged.
        """
        if isinstance(self._layer, SelectionLayer):
            return  # Nothing is drawn for the selection layer, so building its full-size pixmap would be wasted.
        image = self._layer.get_qimage()
        # A group's image covers its bounds and reports changes in image coordinates. Other layers use their own.
        origin = self._layer.bounds.topLeft() if isinstance(self._layer, LayerGroup) else QPoint()
        if changed_rect is None or changed_rect.isEmpty() or self._pixmap.isNull() \
                or image.size() != self._pixmap.size() or origin != self._pixmap_origin:
            if image.size() != self._pixmap.size():
                self.prepareGeometryChange()
            # fromImage shares the image's data, and a group paints its next renders into that image, so sharing
            # would make both sides copy it in full on their next paint.
            self._pixmap = QPixmap() if image.isNull() else QPixmap.fromImage(image.copy())
            self._pixmap_origin = QPoint(origin)
            self.update()
        else:
            area = changed_rect.translated(-origin).intersected(self._pixmap.rect())
            if not area.isEmpty():
                painter = QPainter(self._pixmap)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
                painter.drawImage(area.topLeft(), image, area)
                painter.end()
                # Smooth scaling blends each pixel with its neighbors, so the view changes one pixel past the area.
                self.update(QRectF(area.adjusted(-1, -1, 1, 1)))
        if not self._pending_bounds.isNull() and self._pending_bounds.size() == self._pixmap.size():
            self.setTransform(QTransform.fromTranslate(self._pending_bounds.x(), self._pending_bounds.y()))
            self._pending_bounds = QRect()
        mode = self._display_mode()
        if mode != self.composition_mode:
            self.composition_mode = mode

    def _update_visibility(self, _, visible: bool) -> None:
        self.setVisible(visible and not self.hidden)

    def _display_opacity(self) -> float:
        if isinstance(self._layer, SelectionLayer):
            return 0.0  # The mask is never displayed. SelectionOutline shows the selection.
        if isinstance(self._layer, LayerGroup):
            return 1.0
        return self._layer.opacity

    def _display_mode(self) -> CompositeMode:
        if isinstance(self._layer, LayerGroup):
            return CompositeMode.NORMAL
        return self._layer.composition_mode

    def _update_opacity(self, *_args) -> None:
        self.setOpacity(self._display_opacity())

    def _update_mode(self, *_args) -> None:
        self.composition_mode = self._display_mode()

    # noinspection PyUnusedLocal
    def _update_transform(self, *_args) -> None:
        assert isinstance(self._layer, TransformLayer)
        self.setTransform(self._layer.transform)

    # noinspection PyUnusedLocal
    def _update_bounds(self, *_args) -> None:
        bounds = self._layer.bounds
        if bounds.size() == self._pixmap.size():
            self._pending_bounds = QRect()
            self.setTransform(QTransform.fromTranslate(bounds.x(), bounds.y()))
        else:
            self._pending_bounds = QRect(bounds)  # Wait for the pixmap to update
