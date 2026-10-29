"""Context menus for layer list rows and the image strip. They act on the layer they were built for, which isn't always
the active layer."""
from typing import Callable, Optional, cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QMenu

from src.config.key_config import KeyConfig

from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.image_stack_utils import crop_layer_to_selection
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.image.layers.transform_layer import TransformLayer
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.palette_icon import palette_icon

# The QCoreApplication.translate context for strings in this file
TR_ID = 'ui.panel.layer_ui.layer_menu'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


MENU_OPTION_MOVE_UP = _tr('Move up')
MENU_OPTION_MOVE_DOWN = _tr('Move down')
MENU_OPTION_MOVE_TO_TOP = _tr('Move to top')
MENU_OPTION_DUPLICATE = _tr('Duplicate')
MENU_OPTION_DELETE = _tr('Delete')
MENU_OPTION_MERGE_DOWN = _tr('Merge down')
MENU_OPTION_MERGE_GROUP = _tr('Merge group')
MENU_OPTION_MERGE_ALL_VISIBLE = _tr('Merge all visible')
MENU_OPTION_FLATTEN = _tr('Flatten')
MENU_OPTION_RENAME = _tr('Rename')
MENU_OPTION_CLEAR_SELECTED = _tr('Clear selected pixels')
MENU_OPTION_COPY_SELECTED = _tr('Copy selected to new layer')
MENU_OPTION_LAYER_TO_IMAGE_SIZE = _tr('Layer to image size')
MENU_OPTION_CROP_TO_CONTENT = _tr('Crop layer to content')
MENU_OPTION_CROP_TO_SELECTION = _tr('Crop layer to selection')
MENU_OPTION_MIRROR_VERTICAL = _tr('Mirror vertically')
MENU_OPTION_MIRROR_HORIZONTAL = _tr('Mirror horizontally')
MENU_OPTION_ROTATE_CW = _tr('Rotate 90° clockwise')
MENU_OPTION_ROTATE_CCW = _tr('Rotate 90° counter-clockwise')
MENU_OPTION_SELECT_CONTENT = _tr('Select layer contents')
SUBMENU_CROP_AND_RESIZE = _tr('Crop and resize')
SUBMENU_MIRROR_AND_ROTATE = _tr('Mirror and rotate')
COPIED_LAYER_NAME = _tr('{src_layer_name} copied content')

ICON_DIR = f'{PROJECT_DIR}/resources/icons/layer'
ICON_PATH_MOVE_UP = f'{ICON_DIR}/up_icon.svg'
ICON_PATH_MOVE_DOWN = f'{ICON_DIR}/down_icon.svg'
ICON_PATH_DUPLICATE = f'{ICON_DIR}/duplicate_icon.svg'
ICON_PATH_MERGE = f'{ICON_DIR}/merge_icon.svg'
ICON_PATH_DELETE = f'{ICON_DIR}/delete_icon.svg'


def _add_key_hint(action: QAction, config_key: Optional[str]) -> None:
    """Shows the binding stored at a KeyConfig key beside an action's text. The shortcut applies only while the menu
    has focus, so it doesn't compete with the application's own shortcut for the same key."""
    if config_key is None:
        return
    try:
        keys = KeyConfig().get(config_key)
    except KeyError:
        return
    if isinstance(keys, str) and keys != '':
        action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        action.setShortcut(QKeySequence(keys))


def build_layer_menu(layer: Layer, image_stack: ImageStack, rename: Callable[[], None]) -> QMenu:
    """Returns the context menu for a layer. Its groups, in order, are rename; move; duplicate; merge and flatten;
    selection commands; the crop and mirror submenus; delete. For the root group it holds only rename, crop to
    selection and mirror, which the image strip's menu offers. `rename` starts editing the layer's name."""
    menu = QMenu()
    menu.setTitle(layer.name)
    editable = not layer.locked and not layer.parent_locked

    def _add_action(name: str, action_callback: Callable[..., None], disable_if_locked=False,
                    config_key: Optional[str] = None, icon_path: Optional[str] = None,
                    target: Optional[QMenu] = None) -> QAction:
        new_action = (menu if target is None else target).addAction(name)
        assert new_action is not None
        new_action.triggered.connect(action_callback)
        if disable_if_locked:
            new_action.setEnabled(editable)
        _add_key_hint(new_action, config_key)
        if icon_path is not None:
            new_action.setIcon(palette_icon(icon_path))
        return new_action

    def _new_group() -> None:
        """Starts a new group of actions, unless the menu is empty or already ends with a separator."""
        actions = menu.actions()
        if len(actions) > 0 and not actions[-1].isSeparator():
            menu.addSeparator()

    def _mirror_actions(target: Optional[QMenu]) -> list[QAction]:
        mirror_actions = [_add_action(MENU_OPTION_MIRROR_HORIZONTAL, layer.flip_horizontal, True,
                                      'layer_mirror_horizontal_shortcut', target=target),
                          _add_action(MENU_OPTION_MIRROR_VERTICAL, layer.flip_vertical, True,
                                      'layer_mirror_vertical_shortcut', target=target)]
        if isinstance(layer, LayerGroup) and any(child.locked for child in layer.recursive_child_layers):
            for action in mirror_actions:
                action.setEnabled(False)
        return mirror_actions

    _add_action(MENU_OPTION_RENAME, rename, True, 'rename_layer_shortcut')

    if layer.layer_parent is None:
        # The root group:
        _add_action(MENU_OPTION_CROP_TO_SELECTION, lambda: crop_layer_to_selection(image_stack, layer), True,
                    'crop_layer_to_selection_shortcut')
        _mirror_actions(None)
        return menu

    parent = cast(LayerGroup, layer.layer_parent)
    index = parent.get_layer_index(layer)
    is_top_level = parent == image_stack.layer_stack

    if index is not None:
        _new_group()
        # Moving a layer can take it out of its group, so only the ends of the top-level list block moves:
        if not is_top_level or index > 0:
            _add_action(MENU_OPTION_MOVE_UP, lambda: image_stack.move_layer_by_offset(-1, layer),
                        config_key='move_layer_up_shortcut', icon_path=ICON_PATH_MOVE_UP)
        if not is_top_level or index < parent.count - 1:
            _add_action(MENU_OPTION_MOVE_DOWN, lambda: image_stack.move_layer_by_offset(1, layer),
                        config_key='move_layer_down_shortcut', icon_path=ICON_PATH_MOVE_DOWN)
        move_to_top = _add_action(MENU_OPTION_MOVE_TO_TOP,
                                  lambda: image_stack.move_layer(layer, image_stack.layer_stack, 0),
                                  config_key='move_layer_to_top_shortcut')
        move_to_top.setEnabled(not (is_top_level and index == 0))

    _new_group()
    _add_action(MENU_OPTION_DUPLICATE, lambda: image_stack.copy_layer(layer), config_key='copy_layer_shortcut',
                icon_path=ICON_PATH_DUPLICATE)

    _new_group()
    if index is not None:
        merge_option = _add_action(MENU_OPTION_MERGE_DOWN, lambda: image_stack.merge_layer_down(layer), True,
                                   'merge_layer_down_shortcut', ICON_PATH_MERGE)
        if not isinstance(layer, TransformLayer):
            merge_option.setEnabled(False)
        else:
            next_layer = image_stack.next_layer(layer)
            if next_layer is None or next_layer.locked or next_layer.parent_locked or not next_layer.shown \
                    or not isinstance(next_layer, TransformLayer):
                merge_option.setEnabled(False)
    if isinstance(layer, LayerGroup):
        merge_group_option = _add_action(MENU_OPTION_MERGE_GROUP, lambda: image_stack.merge_group(layer), True,
                                         'merge_group_shortcut')
        if image_stack.layer_is_flat(layer):
            merge_group_option.setEnabled(False)
    merge_visible_option = _add_action(MENU_OPTION_MERGE_ALL_VISIBLE, image_stack.merge_all_visible,
                                       config_key='merge_all_visible_shortcut')
    visible_top_layers = [top_layer for top_layer in image_stack.layer_stack.child_layers if top_layer.shown]
    can_merge_visible = len(visible_top_layers) > 1 or (len(visible_top_layers) == 1
                                                        and isinstance(visible_top_layers[0], LayerGroup)
                                                        and visible_top_layers[0].count > 0)
    merge_visible_option.setEnabled(can_merge_visible)
    flatten_action = _add_action(MENU_OPTION_FLATTEN, lambda: image_stack.flatten_layer(layer), True,
                                 'flatten_layer_shortcut')
    if image_stack.layer_is_flat(layer):
        flatten_action.setEnabled(False)

    _new_group()
    _add_action(MENU_OPTION_CLEAR_SELECTED, lambda: image_stack.cut_selected(layer), True)

    def do_copy() -> None:
        """Make the copy, then add it as a new layer."""
        masked = image_stack.copy_selected(layer)
        image_stack.create_layer(COPIED_LAYER_NAME.format(src_layer_name=layer.name), masked, layer_index=index)
    _add_action(MENU_OPTION_COPY_SELECTED, do_copy)
    _add_action(MENU_OPTION_SELECT_CONTENT, lambda: image_stack.select_layer_content(layer), False,
                'select_layer_content_shortcut')

    _new_group()
    crop_menu = menu.addMenu(SUBMENU_CROP_AND_RESIZE)
    assert crop_menu is not None
    if isinstance(layer, ImageLayer):
        _add_action(MENU_OPTION_LAYER_TO_IMAGE_SIZE, lambda: image_stack.layer_to_image_size(layer), True,
                    'layer_to_image_size_shortcut', target=crop_menu)
        _add_action(MENU_OPTION_CROP_TO_CONTENT, layer.crop_to_content, True, 'crop_to_content_shortcut',
                    target=crop_menu)
    _add_action(MENU_OPTION_CROP_TO_SELECTION, lambda: crop_layer_to_selection(image_stack, layer), True,
                'crop_layer_to_selection_shortcut', target=crop_menu)
    mirror_menu = menu.addMenu(SUBMENU_MIRROR_AND_ROTATE)
    assert mirror_menu is not None
    _mirror_actions(mirror_menu)
    def _rotate_callback(degrees: int) -> Callable[[], None]:
        # A default argument would receive the `checked` flag that `triggered` passes:
        return lambda: cast(TransformLayer, layer).rotate(degrees)

    # Groups don't rotate:
    rotatable = isinstance(layer, TransformLayer)
    for text, degrees, config_key in ((MENU_OPTION_ROTATE_CW, 90, 'layer_rotate_cw_shortcut'),
                                      (MENU_OPTION_ROTATE_CCW, -90, 'layer_rotate_ccw_shortcut')):
        rotate_action = _add_action(text, _rotate_callback(degrees), True, config_key, target=mirror_menu)
        rotate_action.setEnabled(rotate_action.isEnabled() and rotatable)

    _new_group()
    _add_action(MENU_OPTION_DELETE, lambda: image_stack.remove_layer(layer), True, 'delete_layer_shortcut',
                ICON_PATH_DELETE)
    return menu
