"""Renders an image layer into a QGraphicsScene."""
from PyQt5.QtGui import QPainter

from src.image.layers.image_layer import ImageLayer
from src.ui.graphics_items.pixmap_item import PixmapItem
from src.util.validation import assert_type


class LayerGraphicsItem(PixmapItem):
    """Renders an image layer into a QGraphicsScene."""

    def __init__(self, layer: ImageLayer):
        super().__init__()
        assert_type(layer, ImageLayer)
        self._layer = layer
        self._hidden = False
        self.composition_mode = layer.composition_mode

        layer.visibility_changed.connect(self._update_visibility)
        layer.content_changed.connect(self._update_pixmap)
        layer.opacity_changed.connect(self._update_opacity)
        layer.transform_changed.connect(self._update_transform)
        layer.z_value_changed.connect(lambda _, z_value: self.setZValue(z_value))
        layer.composition_mode_changed.connect(self._update_mode)
        self.setFlag(LayerGraphicsItem.GraphicsItemFlag.ItemStacksBehindParent, True)
        self.setOpacity(layer.opacity)
        self.setTransform(layer.full_image_transform)
        self.setVisible(layer.visible)
        self.setZValue(layer.z_value)
        self._update_pixmap(layer)

    def __del__(self):
        self._layer.visibility_changed.disconnect(self._update_visibility)
        self._layer.content_changed.disconnect(self._update_pixmap)
        self._layer.opacity_changed.disconnect(self._update_opacity)
        self._layer.transform_changed.disconnect(self._update_transform)
        self._layer.composition_mode_changed.disconnect(self._update_mode)

    @property
    def layer(self) -> ImageLayer:
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

    def _update_pixmap(self, _) -> None:
        self.setPixmap(self._layer.pixmap)
        self.composition_mode = self._layer.composition_mode
        self.update()

    def _update_visibility(self, _, visible: bool) -> None:
        self.setVisible(visible and not self.hidden)

    def _update_opacity(self, _, opacity: float) -> None:
        self.setOpacity(opacity)

    def _update_mode(self, _, mode: QPainter.CompositionMode) -> None:
        self.composition_mode = mode

    # noinspection PyUnusedLocal
    def _update_transform(self, *args) -> None:
        self.setTransform(self._layer.transform)
