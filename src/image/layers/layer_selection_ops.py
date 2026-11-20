"""Commands that act on every selected layer: duplicate, delete, move, and selection changes.

The selection is `ImageStack.selected_layers`. Each bulk command acts on `ImageStack.effective_selected_layers` and is
one undo step. Undoing it restores the selection it acted on, although changing the selection is not an undo step by
itself. With one layer selected, each command calls the single-layer `ImageStack` method, so it behaves as that method
does.
"""
from typing import Optional

from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.undo_stack import UndoStack


def _restore_selection_on_undo(image_stack: ImageStack, action_type: str) -> None:
    """Commits a step whose undo restores the current selection. A bulk command commits it before its first change, so
    its undo runs after every other step's undo, once the selected layers are back in the stack."""
    selected = image_stack.selected_layers_in_order()
    active = image_stack.active_layer
    UndoStack().commit_action(lambda: None, lambda: image_stack.apply_layer_selection(selected, active), action_type)


def _apply_selection(image_stack: ImageStack, layers: list[Layer], active: Layer, action_type: str) -> None:
    """Commits a step that selects layers, and does nothing on undo. A bulk command commits it after its last change."""
    UndoStack().commit_action(lambda: image_stack.apply_layer_selection(layers, active), lambda: None, action_type)


def duplicate_selected_layers(image_stack: ImageStack) -> None:
    """Copies each selected layer just above its original. The copies become the selection, with the topmost copy
    active."""
    layers = image_stack.effective_selected_layers()
    if len(layers) == 1:
        image_stack.copy_layer(layers[0])
        return
    action_type = 'layer_selection_ops.duplicate_selected_layers'
    with UndoStack().combining_actions(action_type):
        _restore_selection_on_undo(image_stack, action_type)
        copies: list[Layer] = []
        for layer in layers:
            parent = layer.layer_parent
            assert isinstance(parent, LayerGroup)
            index = parent.get_layer_index(layer)
            image_stack.copy_layer(layer)
            copy = parent.get_layer_by_index(index)
            assert copy is not layer
            copies.append(copy)
        _apply_selection(image_stack, copies, copies[0], action_type)


def _next_unselected(image_stack: ImageStack, layer: Layer, removed: list[Layer], below: bool) -> Optional[Layer]:
    """Returns the nearest layer below or above a layer that isn't removed or inside a removed group, or None."""
    candidate: Optional[Layer] = layer
    while candidate is not None:
        candidate = image_stack.next_layer(candidate) if below else image_stack.prev_layer(candidate)
        if candidate is None or candidate is image_stack.layer_stack:
            return None
        if not any(candidate is removed_layer or (isinstance(removed_layer, LayerGroup)
                                                  and removed_layer.contains_recursive(candidate))
                   for removed_layer in removed):
            return candidate
    return None


def delete_selected_layers(image_stack: ImageStack) -> None:
    """Removes the selected layers, or changes nothing and shows the locked-layer error if any of them is locked.

    The new active layer is the one just below the lowest deleted layer, then the one above the topmost, then the
    root.
    """
    layers = image_stack.effective_selected_layers()
    if len(layers) == 1:
        image_stack.remove_layer(layers[0])
        return
    if not all(image_stack.validate_layer_showing_errors(layer) for layer in layers):
        return
    next_active = _next_unselected(image_stack, layers[-1], layers, below=True)
    if next_active is None:
        next_active = _next_unselected(image_stack, layers[0], layers, below=False)
    if next_active is None:
        next_active = image_stack.layer_stack
    action_type = 'layer_selection_ops.delete_selected_layers'
    with UndoStack().combining_actions(action_type):
        _restore_selection_on_undo(image_stack, action_type)
        for layer in layers:
            image_stack.remove_layer(layer)
        _apply_selection(image_stack, [next_active], next_active, action_type)


def selected_layers_can_move_into(image_stack: ImageStack, layer: Layer, new_parent: LayerGroup) -> bool:
    """Returns whether dragging a layer's row may drop the layers it moves into a group: refused when the group is one
    of them, or inside one."""
    for moved in moved_by_drag(image_stack, layer):
        if new_parent is moved or (isinstance(moved, LayerGroup) and moved.contains_recursive(new_parent)):
            return False
    return True


def moved_by_drag(image_stack: ImageStack, layer: Layer) -> list[Layer]:
    """Returns the layers that dragging a layer's row moves: the effective selection if the layer is selected, and
    otherwise the layer alone."""
    if image_stack.is_layer_selected(layer):
        return image_stack.effective_selected_layers()
    return [layer]


def move_selected_layers(image_stack: ImageStack, new_parent: LayerGroup, index: int) -> None:
    """Moves the selected layers, in order, to an index in a group's layer list as it is before the move. The
    selection and active layer stay as they were."""
    move_layers(image_stack, image_stack.effective_selected_layers(), new_parent, index)


def move_layers(image_stack: ImageStack, layers: list[Layer], new_parent: LayerGroup, index: int) -> None:
    """Moves layers, in stack order, to an index in a group's layer list as it is before the move.

    A list of more than one layer must be `ImageStack.effective_selected_layers`, which stays selected. `moved_by_drag`
    returns a list that qualifies."""
    if len(layers) == 1:
        layer = layers[0]
        if new_parent is layer.layer_parent:
            current_index = new_parent.get_layer_index(layer)
            assert current_index is not None
            if index > current_index:
                index -= 1
            if index == current_index:
                return
        image_stack.move_layer(layer, new_parent, index)
        return
    assert all(selected_layers_can_move_into(image_stack, layer, new_parent) for layer in layers)
    if not all(image_stack.validate_layer_showing_errors(layer, allow_lock=True) for layer in layers):
        return
    # Each layer lands just above the first layer at or after the index that isn't moving, or at the group's end:
    anchor: Optional[Layer] = next((child for child in new_parent.child_layers[index:] if child not in layers), None)
    if all(layer.layer_parent is new_parent for layer in layers):
        # Layers that already sit together just above the anchor stay put:
        children = new_parent.child_layers
        first = children.index(layers[0])
        end = first + len(layers)
        if children[first:end] == layers and (children[end] if end < len(children) else None) is anchor:
            return
    selected = image_stack.selected_layers_in_order()
    active = image_stack.active_layer
    action_type = 'layer_selection_ops.move_selected_layers'
    with UndoStack().combining_actions(action_type):
        _restore_selection_on_undo(image_stack, action_type)
        for layer in layers:
            current_index = new_parent.get_layer_index(layer) if layer.layer_parent is new_parent else None
            if anchor is None:
                target = new_parent.count - (1 if current_index is not None else 0)
            else:
                target = new_parent.get_layer_index(anchor)
                assert target is not None
                if current_index is not None and current_index < target:
                    target -= 1
            image_stack.move_layer(layer, new_parent, target)
        _apply_selection(image_stack, selected, active, action_type)


def select_all_layers(image_stack: ImageStack) -> None:
    """Selects every layer under the root. The active layer stays active, unless it is the root."""
    layers = image_stack.layer_stack.recursive_child_layers
    if len(layers) == 0:
        return
    active = image_stack.active_layer
    image_stack.select_layers(layers, None if active is image_stack.layer_stack else active)


def extend_layer_selection(image_stack: ImageStack, offset: int) -> None:
    """Adds the layer above (offset -1) or below (offset 1) the active layer to the selection, and makes it active.
    Does nothing at either end of the stack, since the root can't join a multi-selection."""
    assert offset in (1, -1), f'Unexpected offset {offset}'
    active = image_stack.active_layer
    if active is image_stack.layer_stack:
        return
    layer = image_stack.next_layer(active) if offset == 1 else image_stack.prev_layer(active)
    if layer is None or layer is image_stack.layer_stack:
        return
    image_stack.select_layers([*image_stack.selected_layers_in_order(), layer], layer)
