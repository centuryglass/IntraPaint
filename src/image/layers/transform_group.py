"""A temporary layer class used to coordinate transformations applied to multiple layers."""
from typing import List

from PySide6.QtCore import QRect, Signal
from PySide6.QtGui import QTransform

from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.image.layers.transform_layer import TransformLayer


class TransformGroup(TransformLayer):
    """A temporary layer class used to coordinate transformations applied to multiple layers.

    TransformGroups are created as needed when applying transformations across multiple layers. TransformGroups are
    not saved, nor are they added to the layer group. All transformations applied to them immediately propagate to all
    TransformLayers assigned to them.

    I'm using this approach because storing persistent transforms within a LayerGroup is far more trouble than its
    worth, accommodating arbitrary numbers of nested transformations exponentially increases the difficulty of testing
    and maintaining almost every feature.
    """

    bounds_changed = Signal(QRect)

    def __init__(self, layer_group: LayerGroup) -> None:
        self._bounds = QRect()
        super().__init__(f'TransformGroup-{layer_group.name}')
        self._primary_group = layer_group
        self._groups: List[LayerGroup] = []
        self._transform_layers: List[TransformLayer] = []
        self._layer_added_slot(layer_group)
        layer_group.lock_changed.connect(lambda _, locked: self.set_locked(locked))

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
        if bounds != self._bounds:
            self._bounds = QRect(bounds)
            self.bounds_changed.emit(bounds)
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

    def set_transform(self, transform: QTransform) -> None:
        """Propagate the transformation to all associated layers."""
        last_transform_inverted = self.transform.inverted()[0]
        with self._primary_group.all_signals_delayed():
            for layer in self._transform_layers:
                layer.set_transform(layer.transform * last_transform_inverted * transform)
        super().set_transform(transform)

    # noinspection PyUnusedLocal
    def _layer_locked_slot(self, _, locked: bool) -> None:
        if locked:
            self.set_locked(True)
        elif not any((inner_layer.locked or inner_layer.parent_locked
                      for inner_layer in (self._groups + self._transform_layers))):
            self.set_locked(False)

    def _layer_added_slot(self, layer: Layer) -> None:
        assert isinstance(layer, (TransformLayer, LayerGroup))
        if isinstance(layer, TransformLayer):
            if layer not in self._transform_layers:
                layer.set_transform(layer.transform * self.transform)
                self._transform_layers.append(layer)
                layer.size_changed.connect(self._handle_external_changes)
                layer.transform_changed.connect(self._handle_external_changes)
        else:
            assert isinstance(layer, LayerGroup)
            if layer not in self._groups:
                layer.layer_added.connect(self._layer_added_slot)
                layer.layer_removed.connect(self._layer_removed_slot)
                layer.size_changed.connect(self._handle_external_changes)
                layer.bounds_changed.connect(self._handle_external_changes)
                self._groups.append(layer)
                for child in layer.child_layers:
                    self._layer_added_slot(child)
        layer.lock_changed.connect(self._layer_locked_slot)
        if layer.locked or layer.parent_locked:
            self.set_locked(True)
        self._get_local_bounds()  # Updates size, emits size_changed if needed

    def _layer_removed_slot(self, layer: Layer) -> None:
        assert isinstance(layer, (TransformLayer, LayerGroup))
        if isinstance(layer, TransformLayer):
            if layer in self._transform_layers:
                layer.set_transform(layer.transform * self.transform.inverted()[0])
                layer.size_changed.disconnect(self._handle_external_changes)
                layer.transform_changed.disconnect(self._handle_external_changes)
                layer.lock_changed.disconnect(self._layer_locked_slot)
                self._transform_layers.remove(layer)
        else:
            assert isinstance(layer, LayerGroup)
            if layer in self._groups:
                layer.layer_added.disconnect(self._layer_added_slot)
                layer.layer_removed.disconnect(self._layer_removed_slot)
                layer.size_changed.disconnect(self._handle_external_changes)
                layer.bounds_changed.disconnect(self._handle_external_changes)
                layer.lock_changed.disconnect(self._layer_locked_slot)
                self._groups.remove(layer)
                for child in layer.child_layers:
                    self._layer_removed_slot(child)
        self._get_local_bounds()  # Updates size, emits size_changed if needed

    # noinspection PyUnusedLocal
    def _handle_external_changes(self, layer: Layer, _) -> None:
        self._get_local_bounds()  # Updates size, emits size_changed if needed
