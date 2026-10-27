"""Context menus for layer list rows and the image strip. They act on the layer they were built for, which isn't always
the active layer."""
from typing import Callable, Optional, cast

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu

from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.image_stack_utils import crop_layer_to_selection
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.image.layers.transform_layer import TransformLayer

# The QCoreApplication.translate context for strings in this file
TR_ID = 'ui.panel.layer_ui.layer_menu'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


MENU_OPTION_MOVE_UP = _tr('Move up')
MENU_OPTION_MOVE_DOWN = _tr('Move down')
MENU_OPTION_COPY = _tr('Copy')
MENU_OPTION_DELETE = _tr('Delete')
MENU_OPTION_MERGE_DOWN = _tr('Merge down')
MENU_OPTION_MERGE_GROUP = _tr('Merge group')
MENU_OPTION_MERGE_ALL_VISIBLE = _tr('Merge all visible')
MENU_OPTION_FLATTEN = _tr('Flatten')
MENU_OPTION_RENAME = _tr('Rename')
MENU_OPTION_CLEAR_SELECTED = _tr('Clear selected')
MENU_OPTION_COPY_SELECTED = _tr('Copy selected to new layer')
MENU_OPTION_LAYER_TO_IMAGE_SIZE = _tr('Layer to image size')
MENU_OPTION_CROP_TO_CONTENT = _tr('Crop layer to content')
MENU_OPTION_CROP_TO_SELECTION = _tr('Crop layer to selection')
MENU_OPTION_MIRROR_VERTICAL = _tr('Mirror vertically')
MENU_OPTION_MIRROR_HORIZONTAL = _tr('Mirror horizontally')
MENU_OPTION_SELECT_CONTENT = _tr('Select layer contents')
COPIED_LAYER_NAME = _tr('{src_layer_name} copied content')


def build_layer_menu(layer: Layer, image_stack: ImageStack, rename: Callable[[], None]) -> QMenu:
    """Returns the context menu for a layer. For the root group it holds only rename, crop to selection and mirror,
    which the image strip's menu offers. `rename` starts editing the layer's name."""
    menu = QMenu()
    menu.setTitle(layer.name)
    editable = not layer.locked and not layer.parent_locked

    def _add_action(name: str, action_callback: Callable[..., None], disable_if_locked=False) -> QAction:
        new_action = menu.addAction(name)
        assert new_action is not None
        new_action.triggered.connect(action_callback)
        if disable_if_locked:
            new_action.setEnabled(editable)
        return new_action

    _add_action(MENU_OPTION_RENAME, rename, disable_if_locked=True)

    if layer.layer_parent is not None:
        parent = cast(LayerGroup, layer.layer_parent)
        index = parent.get_layer_index(layer)

        if index is not None:
            # Moving a layer can take it out of its group, so only the ends of the top-level list block moves:
            is_top_level = parent == image_stack.layer_stack
            if not is_top_level or index > 0:
                _add_action(MENU_OPTION_MOVE_UP, lambda: image_stack.move_layer_by_offset(-1, layer))
            if not is_top_level or index < parent.count - 1:
                _add_action(MENU_OPTION_MOVE_DOWN, lambda: image_stack.move_layer_by_offset(1, layer))

        _add_action(MENU_OPTION_COPY, lambda: image_stack.copy_layer(layer))
        _add_action(MENU_OPTION_DELETE, lambda: image_stack.remove_layer(layer), True)

        if index is not None:
            merge_option = _add_action(MENU_OPTION_MERGE_DOWN, lambda: image_stack.merge_layer_down(layer), True)
            if not isinstance(layer, TransformLayer):
                merge_option.setEnabled(False)
            else:
                next_layer = image_stack.next_layer(layer)
                if next_layer is None or next_layer.locked or next_layer.parent_locked or not next_layer.shown \
                        or not isinstance(next_layer, TransformLayer):
                    merge_option.setEnabled(False)

        if isinstance(layer, LayerGroup):
            merge_group_option = _add_action(MENU_OPTION_MERGE_GROUP, lambda: image_stack.merge_group(layer), True)
            if image_stack.layer_is_flat(layer):
                merge_group_option.setEnabled(False)

        merge_visible_option = _add_action(MENU_OPTION_MERGE_ALL_VISIBLE, image_stack.merge_all_visible)
        visible_top_layers = [top_layer for top_layer in image_stack.layer_stack.child_layers if top_layer.shown]
        can_merge_visible = len(visible_top_layers) > 1 or (len(visible_top_layers) == 1
                                                            and isinstance(visible_top_layers[0], LayerGroup)
                                                            and visible_top_layers[0].count > 0)
        merge_visible_option.setEnabled(can_merge_visible)

        flatten_action = _add_action(MENU_OPTION_FLATTEN, lambda: image_stack.flatten_layer(layer), True)
        if image_stack.layer_is_flat(layer):
            flatten_action.setEnabled(False)
        _add_action(MENU_OPTION_CLEAR_SELECTED, lambda: image_stack.cut_selected(layer), True)

        def do_copy() -> None:
            """Make the copy, then add it as a new layer."""
            masked = image_stack.copy_selected(layer)
            image_stack.create_layer(COPIED_LAYER_NAME.format(src_layer_name=layer.name), masked, layer_index=index)
        _add_action(MENU_OPTION_COPY_SELECTED, do_copy)
        if isinstance(layer, ImageLayer):
            _add_action(MENU_OPTION_LAYER_TO_IMAGE_SIZE, lambda: image_stack.layer_to_image_size(layer), True)

        _add_action(MENU_OPTION_SELECT_CONTENT, lambda: image_stack.select_layer_content(layer))

    if isinstance(layer, ImageLayer):
        _add_action(MENU_OPTION_CROP_TO_CONTENT, layer.crop_to_content, True)
    _add_action(MENU_OPTION_CROP_TO_SELECTION, lambda: crop_layer_to_selection(image_stack, layer), True)

    mirror_actions = [_add_action(MENU_OPTION_MIRROR_HORIZONTAL, layer.flip_horizontal, True),
                      _add_action(MENU_OPTION_MIRROR_VERTICAL, layer.flip_vertical, True)]
    if isinstance(layer, LayerGroup) and any(child.locked for child in layer.recursive_child_layers):
        for action in mirror_actions:
            action.setEnabled(False)
    return menu
