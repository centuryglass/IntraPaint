"""Renders a layer group into a QGraphicsScene."""
from typing import Dict, Optional, List

from PyQt5.QtCore import QRect, QPointF
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QGraphicsItemGroup, QGraphicsItem

from src.image.layers.image_layer import ImageLayer
from src.image.layers.layer import Layer
from src.image.layers.layer_stack import LayerStack
from src.ui.graphics_items.layer_graphics_item import LayerGraphicsItem
from src.util.validation import assert_type


class LayerStackGraphicsItem(QGraphicsItemGroup):
    """Renders an image layer into a QGraphicsScene."""

    def __init__(self, layer: LayerStack):
        super().__init__()
        assert_type(layer, LayerStack)
        self._child_layers: Dict[int, LayerGraphicsItem | LayerStackGraphicsItem] = {}
        self._layer = layer
        self._hidden = False
        self.composition_mode = layer.composition_mode

        layer.visibility_changed.connect(self._update_visibility)
        layer.content_changed.connect(self.update)
        layer.opacity_changed.connect(self._update_opacity)
        layer.transform_changed.connect(self._update_transform)
        layer.z_value_changed.connect(lambda _, z_value: self.setZValue(z_value))
        layer.composition_mode_changed.connect(self._update_mode)
        self.setOpacity(layer.opacity)
        self.setTransform(layer.full_image_transform)
        self.setVisible(layer.visible)
        layer.layer_added.connect(self._layer_added)
        layer.layer_removed.connect(self._layer_removed)
        for child in layer.child_layers:
            self._layer_added(child)

    def __del__(self):
        self._layer.visibility_changed.disconnect(self._update_visibility)
        self._layer.content_changed.disconnect(self.update)
        self._layer.opacity_changed.disconnect(self._update_opacity)
        self._layer.transform_changed.disconnect(self._update_transform)
        self._layer.composition_mode_changed.disconnect(self._update_mode)

    @property
    def layer(self) -> LayerStack:
        """Returns the rendered image layer."""
        return self._layer

    def find_layer_item(self, layer_id: int) -> Optional[QGraphicsItem]:
        """Returns a layer graphics item with the associated layer id, or None if no such layer is found."""
        groups_to_search: List[LayerStackGraphicsItem] = [self]
        while len(groups_to_search) > 0:
            layer_group_item = groups_to_search.pop()
            group = layer_group_item.layer
            if group.id == layer_id:
                return layer_group_item
            if layer_id in layer_group_item._child_layers:
                return layer_group_item._child_layers[layer_id]
            for group_item in layer_group_item._child_layers.values():
                if isinstance(group_item, LayerStackGraphicsItem):
                    groups_to_search.append(group_item)
        return None

    @property
    def hidden(self) -> bool:
        """Returns whether this layer is currently hidden."""
        return self._hidden

    @hidden.setter
    def hidden(self, hidden: bool) -> None:
        """Sets whether the layer should be hidden in the view regardless of layer visibility."""
        self._hidden = hidden
        self.setVisible(self._layer.visible and not hidden)

    def _update_visibility(self, _, visible: bool) -> None:
        self.setVisible(visible and not self.hidden)

    def _update_opacity(self, _, opacity: float) -> None:
        self.setOpacity(opacity)

    def _update_mode(self, _, mode: QPainter.CompositionMode) -> None:
        self.composition_mode = mode

    def _layer_added(self, new_layer: Layer):
        if isinstance(new_layer, ImageLayer):
            layer_item = LayerGraphicsItem(new_layer)
        elif isinstance(new_layer, LayerStack):
            layer_item = LayerStackGraphicsItem(new_layer)
        else:
            raise TypeError(f'Unexpected layer type {new_layer.__class__}')
        self.addToGroup(layer_item)
        if layer_item.pos() != QPointF():
            # When the item is flipped, something somewhere tries to compensate for that, but we don't want
            # that:
            layer_item.prepareGeometryChange()
            layer_item.setPos(QPointF())
            layer_item.setTransform(new_layer.transform)
            layer_item.update()

        self._child_layers[new_layer.id] = layer_item

    def _layer_removed(self, removed_layer: Layer):
        assert removed_layer.id in self._child_layers
        layer_item = self._child_layers[removed_layer.id]
        self.removeFromGroup(layer_item)
        scene = layer_item.scene()
        if scene is not None:
            scene.removeItem(layer_item)
        del self._child_layers[removed_layer.id]

    # noinspection PyUnusedLocal
    def _update_transform(self, *args) -> None:
        self.setTransform(self._layer.transform)
