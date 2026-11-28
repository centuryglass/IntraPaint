"""Names the image-state requirements menu actions declare with `@menu_action(requires=...)`, and computes them.

`AppController._update_enabled_actions` passes `met_requirements` to `MenuBuilder.update_required_actions`, which
enables each action only while every requirement it declares is met.
"""
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer_group import LayerGroup
from src.image.layers.non_destructive_layer import NonDestructiveLayer
from src.image.layers.text_layer import TextLayer

SELECTION = 'selection'
"""The selection is not empty."""
UNLOCKED_LAYER = 'unlocked_layer'
"""The active layer and all of its parents are unlocked."""
HAS_PREVIOUS_LAYER = 'has_previous_layer'
"""The active layer has a previous layer in list order. The root layer stack doesn't count as one."""
HAS_NEXT_LAYER = 'has_next_layer'
"""The active layer has a next layer in list order. The root layer stack meets it while it holds any layers."""
NOT_LAYER_STACK = 'not_layer_stack'
"""The active layer is not the root layer stack."""
NOT_FLAT = 'not_flat'
"""The active layer is not flat (`ImageStack.layer_is_flat`)."""
LAYER_GROUP = 'layer_group'
"""The active layer is a `LayerGroup`."""
NOT_LAYER_GROUP = 'not_layer_group'
"""The active layer is not a `LayerGroup`."""
NOT_TEXT_LAYER = 'not_text_layer'
"""The active layer is not a `TextLayer`."""
PAINTABLE_LAYER = 'paintable_layer'
"""The active layer's pixels can be drawn on: it is an `ImageLayer` or a `NonDestructiveLayer`."""


def met_requirements(image_stack: ImageStack) -> set[str]:
    """Returns the requirement names that `image_stack`'s current selection and active layer meet."""
    active_layer = image_stack.active_layer
    layer_stack = image_stack.layer_stack
    is_group = isinstance(active_layer, LayerGroup)
    conditions = {
        SELECTION: not image_stack.selection_layer.empty,
        UNLOCKED_LAYER: not (active_layer.locked or active_layer.parent_locked),
        HAS_PREVIOUS_LAYER: image_stack.prev_layer(active_layer) not in (None, layer_stack),
        HAS_NEXT_LAYER: image_stack.next_layer(active_layer) is not None,
        NOT_LAYER_STACK: active_layer != layer_stack,
        NOT_FLAT: not image_stack.layer_is_flat(active_layer),
        LAYER_GROUP: is_group,
        NOT_LAYER_GROUP: not is_group,
        NOT_TEXT_LAYER: not isinstance(active_layer, TextLayer),
        PAINTABLE_LAYER: isinstance(active_layer, (ImageLayer, NonDestructiveLayer)),
    }
    return {name for name, met in conditions.items() if met}
