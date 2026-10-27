"""The Layers panel: the selected-layer header (`LayerProperties`), the layer list (`LayerList`) and the action bar.

It is a `DockPanel`, so it shows as much as fits the space its dock reports:

- A side panel stacks the header over the list, and the list takes the spare height. A strip puts the header beside
  the list, so the list stays vertical in its own column. The action bar stays below as the footer.
- Required: the panel header, the eye, thumbnail and name of each row, the selection, opacity, mode and the lock
  toggles. Mode and opacity share a row when it fits across, and stack otherwise.
- Optional, placed first: the rows' meta line (`META_PRIORITY`). Then the large form (`LARGE_PRIORITY`): text labels
  on the toggles and large thumbnails.
- The panel header counts the layers under the root.

All layer changes go through `ImageStack`.
"""
from typing import Any, Callable, Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QGridLayout, QHBoxLayout, QSizePolicy, QToolButton, QWidget

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.ui.layout.dock_panel import QWIDGETSIZE_MAX, DockPanel
from src.ui.layout.panel_fit import REQUIRED, STRIP_SECTION_MAX_WIDTH, FitItem, Orientation
from src.ui.panel.layer_ui.layer_list import LayerList
from src.ui.panel.layer_ui.layer_properties import LayerProperties
from src.ui.widget.shortcut_tooltip import set_shortcut_tooltip
from src.util.shared_constants import APP_ICON_PATH, PROJECT_DIR, SMALL_ICON_SIZE
from src.util.visual.palette_icon import palette_icon

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.layer_ui.layer_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


WINDOW_TITLE = _tr('Image Layers')
PANEL_TITLE = _tr('Layers')
ONE_LAYER_DESCRIPTION = _tr('1 layer')
LAYER_COUNT_DESCRIPTION = _tr('{count} layers')
ADD_BUTTON_TITLE = _tr('Add layer')
ADD_BUTTON_TOOLTIP = _tr('Create a new layer above the current active layer.')
ADD_GROUP_BUTTON_TITLE = _tr('Add layer group')
ADD_GROUP_BUTTON_TOOLTIP = _tr('Create a new layer group above the current active layer.')
DELETE_BUTTON_TITLE = _tr('Delete layer')
DELETE_BUTTON_TOOLTIP = _tr('Delete the active layer.')
LAYER_UP_BUTTON_TITLE = _tr('Move layer up')
LAYER_UP_BUTTON_TOOLTIP = _tr('Move the active layer up.')
LAYER_DOWN_BUTTON_TITLE = _tr('Move layer down')
LAYER_DOWN_BUTTON_TOOLTIP = _tr('Move the active layer down.')
MERGE_DOWN_BUTTON_TITLE = _tr('Merge down')
MERGE_DOWN_BUTTON_TOOLTIP = _tr('Merge the active layer with the one below it.')

ICON_PATH_PANEL = f'{PROJECT_DIR}/resources/icons/tabs/layers.svg'
ICON_PATH_ADD_BUTTON = f'{PROJECT_DIR}/resources/icons/layer/plus_icon.svg'
ICON_PATH_ADD_GROUP_BUTTON = f'{PROJECT_DIR}/resources/icons/layer/plus_group_icon.svg'
ICON_PATH_DELETE_BUTTON = f'{PROJECT_DIR}/resources/icons/layer/minus_icon.svg'
ICON_PATH_LAYER_UP_BUTTON = f'{PROJECT_DIR}/resources/icons/layer/up_icon.svg'
ICON_PATH_LAYER_DOWN_BUTTON = f'{PROJECT_DIR}/resources/icons/layer/down_icon.svg'
ICON_PATH_MERGE_BUTTON = f'{PROJECT_DIR}/resources/icons/layer/merge_down_icon.svg'

# Optional items, in fill order:
META_PRIORITY = 1
LARGE_PRIORITY = 2
# Forms of the mode and opacity row:
CONTROLS_ONE_ROW = 0
CONTROLS_STACKED = 1


class LayerPanel(DockPanel):
    """Shows the image's layers, and edits the active layer. See the module docstring."""

    def __init__(self, image_stack: ImageStack, parent: Optional[QWidget] = None) -> None:
        """Connects to the ImageStack and builds the panel."""
        self._image_stack = image_stack
        super().__init__(PANEL_TITLE, QIcon(ICON_PATH_PANEL), parent=parent)
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.header.reset_button.hide()

        self._properties = LayerProperties(image_stack)
        self._layer_list = LayerList(image_stack)
        self._content = QWidget()
        self._content_layout = QGridLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.insertWidget(0, self._content, stretch=1)

        self._button_bar = QWidget()
        self._button_bar_layout = QHBoxLayout(self._button_bar)
        self._button_bar_layout.setSpacing(0)
        self._button_bar_layout.setContentsMargins(0, 0, 0, 0)
        self._add_button = self._create_button(ICON_PATH_ADD_BUTTON, ADD_BUTTON_TITLE, ADD_BUTTON_TOOLTIP,
                                               image_stack.create_layer, KeyConfig.NEW_LAYER_SHORTCUT, stretch=1)
        self._add_group_button = self._create_button(ICON_PATH_ADD_GROUP_BUTTON, ADD_GROUP_BUTTON_TITLE,
                                                     ADD_GROUP_BUTTON_TOOLTIP, image_stack.create_layer_group,
                                                     KeyConfig.NEW_LAYER_GROUP_SHORTCUT, stretch=1)
        self._move_up_button = self._create_button(ICON_PATH_LAYER_UP_BUTTON, LAYER_UP_BUTTON_TITLE,
                                                   LAYER_UP_BUTTON_TOOLTIP, self._move_up,
                                                   KeyConfig.MOVE_LAYER_UP_SHORTCUT, stretch=1)
        self._move_down_button = self._create_button(ICON_PATH_LAYER_DOWN_BUTTON, LAYER_DOWN_BUTTON_TITLE,
                                                     LAYER_DOWN_BUTTON_TOOLTIP, self._move_down,
                                                     KeyConfig.MOVE_LAYER_DOWN_SHORTCUT, stretch=1)
        self._merge_down_button = self._create_button(ICON_PATH_MERGE_BUTTON, MERGE_DOWN_BUTTON_TITLE,
                                                      MERGE_DOWN_BUTTON_TOOLTIP, image_stack.merge_layer_down,
                                                      KeyConfig.MERGE_LAYER_DOWN_SHORTCUT, stretch=10)
        self._delete_button = self._create_button(ICON_PATH_DELETE_BUTTON, DELETE_BUTTON_TITLE, DELETE_BUTTON_TOOLTIP,
                                                  image_stack.remove_layer, KeyConfig.DELETE_LAYER_SHORTCUT,
                                                  signal=True)
        self.set_footer(self._button_bar)

        self.add_fit_item(FitItem(REQUIRED, 2), self._apply_controls_form)
        self.add_fit_item(FitItem(META_PRIORITY), self._apply_meta_form)
        self.add_fit_item(FitItem(LARGE_PRIORITY), self._apply_large_form)

        self._active_layer: Optional[Layer] = None
        image_stack.active_layer_changed.connect(self._active_layer_change_slot)
        image_stack.layer_added.connect(self._layer_count_change_slot)
        image_stack.layer_removed.connect(self._layer_count_change_slot)
        self._active_layer_change_slot(image_stack.active_layer)
        self._layer_count_change_slot()
        self.arrange(Orientation.SIDE)

    def _create_button(self, icon_path: str, title: str, tooltip: str, action: Callable[..., Any],
                       shortcut_key: str, signal: bool = False, stretch: Optional[int] = None) -> QToolButton:
        button = QToolButton()
        set_shortcut_tooltip(button, title, shortcut_key, description=tooltip)
        button.setContentsMargins(2, 2, 2, 2)
        button.setIcon(palette_icon(icon_path, signal=signal))
        button.setIconSize(QSize(SMALL_ICON_SIZE, SMALL_ICON_SIZE))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        # The lambda drops the checked argument that `clicked` passes:
        button.clicked.connect(lambda: action())  # pylint: disable=unnecessary-lambda
        self._button_bar_layout.addWidget(button)
        if stretch is not None:
            self._button_bar_layout.addStretch(stretch)
        return button

    def _move_up(self) -> None:
        self._image_stack.move_layer_by_offset(-1)

    def _move_down(self) -> None:
        self._image_stack.move_layer_by_offset(1)

    @property
    def properties(self) -> LayerProperties:
        """The selected-layer header."""
        return self._properties

    @property
    def layer_list(self) -> LayerList:
        """The image strip and layer rows."""
        return self._layer_list

    # Layout:

    def arrange(self, orientation: Orientation) -> None:
        """Puts the selected-layer header over the list in a side panel, and beside it in a strip."""
        super().arrange(orientation)
        layout = self._content_layout
        for widget in (self._properties, self._layer_list):
            layout.removeWidget(widget)
        for index in range(2):
            layout.setRowStretch(index, 0)
            layout.setColumnStretch(index, 0)
        if orientation == Orientation.SIDE:
            layout.addWidget(self._properties, 0, 0)
            layout.addWidget(self._layer_list, 1, 0)
            layout.setRowStretch(1, 1)
            self._properties.setMaximumWidth(QWIDGETSIZE_MAX)
            self._layer_list.setMaximumWidth(QWIDGETSIZE_MAX)
            layout.setAlignment(self._properties, Qt.AlignmentFlag(0))
        else:
            layout.addWidget(self._properties, 0, 0)
            layout.addWidget(self._layer_list, 0, 1)
            layout.setColumnStretch(1, 1)
            layout.setRowStretch(0, 1)
            self._properties.setMaximumWidth(STRIP_SECTION_MAX_WIDTH)
            self._layer_list.setMaximumWidth(STRIP_SECTION_MAX_WIDTH)
            layout.setAlignment(self._properties, Qt.AlignmentFlag.AlignTop)
        self._properties.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def _apply_controls_form(self, form: Optional[int]) -> None:
        self._properties.set_stacked(form == CONTROLS_STACKED)

    def _apply_meta_form(self, form: Optional[int]) -> None:
        self._layer_list.set_meta_shown(form is not None)

    def _apply_large_form(self, form: Optional[int]) -> None:
        large = form is not None
        self._properties.set_labeled(large)
        self._layer_list.set_large(large)

    def resizeEvent(self, event) -> None:  # pylint: disable=invalid-name
        """Plans for the new size, and saves the panel's bounds when it's a separate window."""
        super().resizeEvent(event)
        if self.isVisible() and self.isWindow():
            Cache().save_bounds(Cache.SAVED_LAYER_WINDOW_POS, self)

    # Layer state:

    def _layer_count_change_slot(self, *_args) -> None:
        count = len(self._image_stack.layer_stack.recursive_child_layers)
        self.header.set_description(ONE_LAYER_DESCRIPTION if count == 1
                                    else LAYER_COUNT_DESCRIPTION.format(count=count))

    def _active_layer_change_slot(self, new_active_layer: Layer) -> None:
        if self._active_layer is not None:
            self._active_layer.lock_changed.disconnect(self._lock_change_slot)
        self._active_layer = new_active_layer
        new_active_layer.lock_changed.connect(self._lock_change_slot)
        for button in (self._move_up_button, self._move_down_button):
            button.setEnabled(new_active_layer != self._image_stack.layer_stack)
        self._lock_change_slot()

    def _lock_change_slot(self, *_args) -> None:
        # The signal's arguments may describe a parent group's lock, so read the lock state from the layer instead.
        active_layer = self._image_stack.active_layer
        editable = not active_layer.locked and not active_layer.parent_locked
        for widget in (self._merge_down_button, self._delete_button):
            widget.setEnabled(editable and active_layer != self._image_stack.layer_stack)
