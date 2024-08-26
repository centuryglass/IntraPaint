"""A temporary layer class used to coordinate transformations applied to multiple layers."""
from typing import List

from PySide6.QtCore import QRect
from PySide6.QtGui import QTransform

from src.image.layers.layer import Layer
from src.image.layers.layer_stack import LayerStack
from src.image.layers.transform_layer import TransformLayer


class TransformGroup(TransformLayer):
    """A temporary layer class used to coordinate transformations applied to multiple layers.

    TransformGroups are created as needed when applying transformations across multiple layers. TransformGroups are
    not saved, nor are they added to the layer stack. All transformations applied to them immediately propagate to all
    TransformLayers assigned to them.

    I'm using this approach because storing persistent transforms within a LayerStack is far more trouble than its
    worth, accommodating arbitrary numbers of nested transformations exponentially increases the difficulty of testing
    and maintaining almost every feature.
    """

    def __init__(self, layer_stack: LayerStack) -> None:
        super().__init__(f'TransformGroup-{layer_stack.name}')
        self._groups: List[LayerStack] = []
        self._transform_layers: List[TransformLayer] = []
        self._layer_added_slot(layer_stack)

    def __del__(self) -> None:
        self.remove_all()

    def _get_local_bounds(self) -> QRect:
        bounds = None
        for layer in self._transform_layers:
            if bounds is None:
                bounds = layer.transformed_bounds
            else:
                bounds = bounds.united(layer.transformed_bounds)
        if bounds is None:
            bounds = QRect()
        else:
            bounds = self.transform.inverted()[0].mapRect(bounds)
        if self.size != bounds.size():
            self.set_size(bounds.size())
        return bounds

    @property
    def has_layers(self) -> bool:
        """Returns whether at least one layer or layer group is connected to this group."""
        return len(self._groups) > 0 or len(self._transform_layers) > 0

    def remove_all(self) -> None:
        """Remove all connected layers, leaving transformations in-place."""
        for group in self._groups:
            group.layer_added.disconnect(self._layer_added_slot)
            group.layer_removed.disconnect(self._layer_removed_slot)
        self._groups.clear()
        self._transform_layers.clear()

    def set_transform(self, transform: QTransform, send_signals: bool = True) -> None:
        """Propagate the transformation to all associated layers."""
        last_transform_inverted = self.transform.inverted()[0]
        for layer in self._transform_layers:
            layer.set_transform(layer.transform * last_transform_inverted * transform, send_signals)
        super().set_transform(transform, send_signals)

    def _layer_added_slot(self, layer: Layer) -> None:
        assert isinstance(layer, (TransformLayer, LayerStack))
        if isinstance(layer, TransformLayer):
            if layer not in self._transform_layers:
                layer.set_transform(layer.transform * self.transform)
                self._transform_layers.append(layer)
        else:
            assert isinstance(layer, LayerStack)
            if layer not in self._groups:
                layer.layer_added.connect(self._layer_added_slot)
                layer.layer_removed.connect(self._layer_removed_slot)
                self._groups.append(layer)
                for child in layer.child_layers:
                    self._layer_added_slot(child)
        self._get_local_bounds()  # Updates size, emits size_changed if needed

    def _layer_removed_slot(self, layer: Layer) -> None:
        assert isinstance(layer, (TransformLayer, LayerStack))
        if isinstance(layer, TransformLayer):
            assert layer in self._transform_layers
            layer.set_transform(layer.transform * self.transform.inverted()[0])
            self._transform_layers.remove(layer)
        else:
            assert isinstance(layer, LayerStack)
            assert layer in self._groups
            layer.layer_added.disconnect(self._layer_added_slot)
            layer.layer_removed.disconnect(self._layer_removed_slot)
            self._groups.remove(layer)
            for child in layer.child_layers:
                self._layer_removed_slot(child)
        self._get_local_bounds()  # Updates size, emits size_changed if needed
