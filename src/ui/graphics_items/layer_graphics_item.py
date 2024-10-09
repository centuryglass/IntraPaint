"""Renders an image layer into a QGraphicsScene."""
from PySide6.QtGui import QTransform
from PySide6.QtWidgets import QGraphicsItem

from src.image.composite_mode import CompositeMode
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.image.layers.transform_layer import TransformLayer
from src.ui.graphics_items.pixmap_item import PixmapItem


class LayerGraphicsItem(PixmapItem):
    """Renders an image layer or text layer into a QGraphicsScene."""

    def __init__(self, layer: Layer):
        super().__init__()
        self._layer = layer
        self._hidden = False
        self.composition_mode = layer.composition_mode

        layer.visibility_changed.connect(self._update_visibility)
        layer.content_changed.connect(self._update_pixmap)
        layer.opacity_changed.connect(self._update_opacity)
        if isinstance(layer, TransformLayer):
            layer.transform_changed.connect(self._update_transform)
        elif isinstance(layer, LayerGroup):
            layer.bounds_changed.connect(self._update_bounds)
        layer.z_value_changed.connect(lambda _, z_value: self.setZValue(z_value))
        layer.composition_mode_changed.connect(self._update_mode)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemStacksBehindParent, True)
        self.setOpacity(layer.opacity)
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

    @property
    def hidden(self) -> bool:
        """Returns whether this layer is currently hidden."""
        return self._hidden

    @hidden.setter
    def hidden(self, hidden: bool) -> None:
        """Sets whether the layer should be hidden in the view regardless of layer visibility."""
        self._hidden = hidden
        self.setVisible(self._layer.visible and not hidden)

    # noinspection PyUnusedLocal
    def _update_pixmap(self, *args) -> None:
        self.setPixmap(self._layer.pixmap)
        self.composition_mode = self._layer.composition_mode
        self.update()

    def _update_visibility(self, _, visible: bool) -> None:
        self.setVisible(visible and not self.hidden)

    def _update_opacity(self, _, opacity: float) -> None:
        self.setOpacity(opacity)

    def _update_mode(self, _, mode: CompositeMode) -> None:
        self.composition_mode = mode

    # noinspection PyUnusedLocal
    def _update_transform(self, *args) -> None:
        assert isinstance(self._layer, TransformLayer)
        self.setTransform(self._layer.transform)

    # noinspection PyUnusedLocal
    def _update_bounds(self, *args) -> None:
        bounds = self._layer.bounds
        self.setTransform(QTransform.fromTranslate(bounds.x(), bounds.y()))
