"""The Layers panel: the selected-layer header (`LayerProperties`), the layer list (`LayerList`) and the action bar.

It is a `DockPanel`, so it shows as much as fits the space its dock reports:

- A side panel stacks the header over the list, and the list takes the spare height. A strip puts the header beside
  the list, so the list stays vertical in its own column. The action bar stays below as the footer.
- Required: the panel header, the eye, thumbnail and name of each row, the selection, opacity, mode and the lock
  toggles. Mode and opacity share a row when it fits across, and stack otherwise.
- The action bar takes the largest of `BAR_FORMS` that fits across the panel: icons with text labels, standard icons,
  or small icons. New layer, New group and Duplicate sit at its left, the moves and Merge down in the middle, and
  Delete alone at the right edge.
- Optional, placed first: the rows' meta line (`META_PRIORITY`). Then the large form (`LARGE_PRIORITY`): text labels
  on the toggles and, with the thumbnail size on Auto, large thumbnails. A fixed thumbnail size
  (`Cache.LAYER_THUMBNAIL_SIZE`) sets the rows' thumbnails whatever the form.
- A strip needs room to read the start of a layer name beside the header (`LayerList.set_readable_names`), and its
  columns stay at the left edge. A strip that would scroll more than a sliver sideways gives way to a side panel
  (`STRIP_SCROLL_LIMIT`).
- The panel header counts the layers under the root. While the panel floats, its title bar shows the name and the
  count (the title note), so the header hides (`apply_header_form`).

All layer changes go through `ImageStack`.
"""
from dataclasses import dataclass
from typing import Any, Callable, Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QApplication, QComboBox, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
                               QToolButton, QVBoxLayout, QWidget)

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.ui.layout.dock_panel import QWIDGETSIZE_MAX, DockPanel
from src.ui.layout.panel_fit import REQUIRED, STRIP_SECTION_MAX_WIDTH, FitItem, Orientation, fresh_minimum_size
from src.ui.panel.layer_ui.layer_list import LayerList
from src.ui.panel.layer_ui.layer_properties import LayerProperties
from src.ui.panel.layer_ui.layer_row import LARGE_THUMBNAIL_SIZE, MEDIUM_THUMBNAIL_SIZE, SMALL_THUMBNAIL_SIZE
from src.ui.widget.shortcut_tooltip import set_shortcut_tooltip
from src.util.shared_constants import APP_ICON_PATH, PROJECT_DIR, SMALL_ICON_SIZE
from src.util.visual.palette_icon import palette_icon
from src.util.visual.text_drawing_utils import get_key_display_string

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
DUPLICATE_BUTTON_TITLE = _tr('Duplicate layer')
DUPLICATE_BUTTON_TOOLTIP = _tr('Create a duplicate of the active layer above it.')
DELETE_BUTTON_TITLE = _tr('Delete layer')
DELETE_BUTTON_TOOLTIP = _tr('Delete the active layer.')
LAYER_UP_BUTTON_TITLE = _tr('Move layer up')
LAYER_UP_BUTTON_TOOLTIP = _tr('Move the active layer up.')
LAYER_DOWN_BUTTON_TITLE = _tr('Move layer down')
LAYER_DOWN_BUTTON_TOOLTIP = _tr('Move the active layer down.')
MERGE_DOWN_BUTTON_TITLE = _tr('Merge down')
MERGE_DOWN_BUTTON_TOOLTIP = _tr('Merge the active layer with the one below it.')
# The action bar's button text in its labeled form:
ADD_BUTTON_LABEL = _tr('New')
ADD_GROUP_BUTTON_LABEL = _tr('Group')
DUPLICATE_BUTTON_LABEL = _tr('Duplicate')
LAYER_UP_BUTTON_LABEL = _tr('Up')
LAYER_DOWN_BUTTON_LABEL = _tr('Down')
MERGE_DOWN_BUTTON_LABEL = _tr('Merge')
DELETE_BUTTON_LABEL = _tr('Delete')
THUMBNAIL_SIZE_LABEL = _tr('Thumbnails:')
SELECT_PREVIOUS_LABEL = _tr('Select previous layer')
SELECT_NEXT_LABEL = _tr('Select next layer')
SHOW_WINDOW_LABEL = _tr('Show layer window')

ICON_PATH_PANEL = f'{PROJECT_DIR}/resources/icons/tabs/layers.svg'
ICON_PATH_ADD_BUTTON = f'{PROJECT_DIR}/resources/icons/layer/plus_icon.svg'
ICON_PATH_DUPLICATE_BUTTON = f'{PROJECT_DIR}/resources/icons/layer/duplicate_icon.svg'
ICON_PATH_ADD_GROUP_BUTTON = f'{PROJECT_DIR}/resources/icons/layer/plus_group_icon.svg'
ICON_PATH_DELETE_BUTTON = f'{PROJECT_DIR}/resources/icons/layer/delete_icon.svg'
ICON_PATH_LAYER_UP_BUTTON = f'{PROJECT_DIR}/resources/icons/layer/up_icon.svg'
ICON_PATH_LAYER_DOWN_BUTTON = f'{PROJECT_DIR}/resources/icons/layer/down_icon.svg'
ICON_PATH_MERGE_BUTTON = f'{PROJECT_DIR}/resources/icons/layer/merge_icon.svg'

# Optional items, in fill order:
META_PRIORITY = 1
LARGE_PRIORITY = 2
# The largest share of a strip that may be out of view sideways, since a strip scrolled past the layer list shows only
# the header:
STRIP_SCROLL_LIMIT = 0.1
# Thumbnail sizes of the Cache.LAYER_THUMBNAIL_SIZE choices other than Auto:
THUMBNAIL_SIZE_AUTO = 'Auto'
THUMBNAIL_SIZES = {'Small': SMALL_THUMBNAIL_SIZE, 'Medium': MEDIUM_THUMBNAIL_SIZE, 'Large': LARGE_THUMBNAIL_SIZE}
# Forms of the mode and opacity row:
CONTROLS_ONE_ROW = 0
CONTROLS_STACKED = 1


@dataclass(frozen=True)
class BarForm:
    """How the action bar's buttons look: their icon size, and whether they show text beside the icon."""
    icon_size: int
    labeled: bool = False


# The action bar's forms, largest first:
BAR_FORMS = (BarForm(SMALL_ICON_SIZE, labeled=True), BarForm(SMALL_ICON_SIZE), BarForm(22))


class LayerPanel(DockPanel):
    """Shows the image's layers, and edits the active layer. See the module docstring."""

    def __init__(self, image_stack: ImageStack, parent: Optional[QWidget] = None,
                 show_window: Optional[Callable[[], None]] = None) -> None:
        """Connects to the ImageStack and builds the panel. `show_window` opens the separate layer window, which the
        More popover offers when it is given."""
        self._image_stack = image_stack
        self._show_window = show_window
        # Whether the large form applies, which sets the thumbnail size while it is on Auto:
        self._large_form = False
        # Whether the panel's dock floats, which hides the header:
        self._floating = False
        # The index in `BAR_FORMS` of the action bar's current form:
        self._bar_form = len(BAR_FORMS) - 1
        # The action bar's minimum width in its narrowest form, as of the latest time that form applied:
        self._narrow_bar_width = 0
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
        self._add_button = self._create_button(ICON_PATH_ADD_BUTTON, ADD_BUTTON_TITLE, ADD_BUTTON_LABEL,
                                               ADD_BUTTON_TOOLTIP, image_stack.create_layer,
                                               KeyConfig.NEW_LAYER_SHORTCUT)
        self._add_group_button = self._create_button(ICON_PATH_ADD_GROUP_BUTTON, ADD_GROUP_BUTTON_TITLE,
                                                     ADD_GROUP_BUTTON_LABEL, ADD_GROUP_BUTTON_TOOLTIP,
                                                     image_stack.create_layer_group,
                                                     KeyConfig.NEW_LAYER_GROUP_SHORTCUT)
        self._duplicate_button = self._create_button(ICON_PATH_DUPLICATE_BUTTON, DUPLICATE_BUTTON_TITLE,
                                                     DUPLICATE_BUTTON_LABEL, DUPLICATE_BUTTON_TOOLTIP,
                                                     image_stack.copy_layer, KeyConfig.COPY_LAYER_SHORTCUT)
        self._button_bar_layout.addStretch(1)
        self._move_up_button = self._create_button(ICON_PATH_LAYER_UP_BUTTON, LAYER_UP_BUTTON_TITLE,
                                                   LAYER_UP_BUTTON_LABEL, LAYER_UP_BUTTON_TOOLTIP, self._move_up,
                                                   KeyConfig.MOVE_LAYER_UP_SHORTCUT)
        self._move_down_button = self._create_button(ICON_PATH_LAYER_DOWN_BUTTON, LAYER_DOWN_BUTTON_TITLE,
                                                     LAYER_DOWN_BUTTON_LABEL, LAYER_DOWN_BUTTON_TOOLTIP,
                                                     self._move_down, KeyConfig.MOVE_LAYER_DOWN_SHORTCUT)
        self._merge_down_button = self._create_button(ICON_PATH_MERGE_BUTTON, MERGE_DOWN_BUTTON_TITLE,
                                                      MERGE_DOWN_BUTTON_LABEL, MERGE_DOWN_BUTTON_TOOLTIP,
                                                      image_stack.merge_layer_down,
                                                      KeyConfig.MERGE_LAYER_DOWN_SHORTCUT)
        self._button_bar_layout.addStretch(1)
        self._delete_button = self._create_button(ICON_PATH_DELETE_BUTTON, DELETE_BUTTON_TITLE, DELETE_BUTTON_LABEL,
                                                  DELETE_BUTTON_TOOLTIP, image_stack.remove_layer,
                                                  KeyConfig.DELETE_LAYER_SHORTCUT, signal=True)
        self._bar_buttons = [self._add_button, self._add_group_button, self._duplicate_button, self._move_up_button,
                             self._move_down_button, self._merge_down_button, self._delete_button]
        # Planning picks a larger form where there is room, so the panel starts with the one that needs the least:
        self._apply_bar_form(len(BAR_FORMS) - 1)
        self.set_footer(self._button_bar)
        self._build_more_content()

        self.add_fit_item(FitItem(REQUIRED, 2), self._apply_controls_form)
        self.add_fit_item(FitItem(REQUIRED, len(BAR_FORMS), fit_width=True), self._apply_bar_form)
        self.add_fit_item(FitItem(META_PRIORITY), self._apply_meta_form)
        self.add_fit_item(FitItem(LARGE_PRIORITY), self._apply_large_form)
        self.set_strip_scroll_limit(STRIP_SCROLL_LIMIT)
        Cache().connect(self, Cache.LAYER_THUMBNAIL_SIZE, self._thumbnail_size_change_slot)
        self._apply_thumbnail_size()

        self._active_layer: Optional[Layer] = None
        image_stack.active_layer_changed.connect(self._active_layer_change_slot)
        image_stack.layer_added.connect(self._layer_count_change_slot)
        image_stack.layer_removed.connect(self._layer_count_change_slot)
        self._active_layer_change_slot(image_stack.active_layer)
        self._layer_count_change_slot()
        self.arrange(Orientation.SIDE)

    def _create_button(self, icon_path: str, title: str, label: str, tooltip: str, action: Callable[..., Any],
                       shortcut_key: str, signal: bool = False) -> QToolButton:
        button = QToolButton()
        set_shortcut_tooltip(button, title, shortcut_key, description=tooltip)
        button.setContentsMargins(2, 2, 2, 2)
        button.setIcon(palette_icon(icon_path, signal=signal))
        button.setText(label)
        button.setAccessibleName(title)
        button.setIconSize(QSize(SMALL_ICON_SIZE, SMALL_ICON_SIZE))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        # The lambda drops the checked argument that `clicked` passes:
        button.clicked.connect(lambda: action())  # pylint: disable=unnecessary-lambda
        self._button_bar_layout.addWidget(button)
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

    def start_rename(self) -> None:
        """Starts editing the active layer's name in its row, or in the image strip for the root."""
        self._layer_list.start_rename(self._image_stack.active_layer)

    # More popover:

    def _build_more_content(self) -> None:
        """Builds the More popover: the thumbnail size, selecting the previous or next layer, and the layer window."""
        self._more_content = QWidget()
        layout = QVBoxLayout(self._more_content)
        layout.setContentsMargins(0, 0, 0, 0)
        cache = Cache()
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel(THUMBNAIL_SIZE_LABEL))
        self._thumbnail_size_box = QComboBox()
        for option in cache.get_options(Cache.LAYER_THUMBNAIL_SIZE):
            self._thumbnail_size_box.addItem(cache.get_option_display(option), option)
        self._thumbnail_size_box.setCurrentIndex(cache.get_option_index(Cache.LAYER_THUMBNAIL_SIZE))
        self._thumbnail_size_box.activated.connect(self._thumbnail_size_chosen_slot)
        size_row.addWidget(self._thumbnail_size_box)
        layout.addLayout(size_row)
        self._select_previous_button = self._add_more_button(
            SELECT_PREVIOUS_LABEL, KeyConfig.SELECT_PREVIOUS_LAYER_SHORTCUT, lambda: self._select_offset(-1), layout)
        self._select_next_button = self._add_more_button(
            SELECT_NEXT_LABEL, KeyConfig.SELECT_NEXT_LAYER_SHORTCUT, lambda: self._select_offset(1), layout)
        self._show_window_button: Optional[QPushButton] = None
        if self._show_window is not None:
            self._show_window_button = self._add_more_button(SHOW_WINDOW_LABEL, KeyConfig.SHOW_LAYER_MENU_SHORTCUT,
                                                             self._show_window, layout)

    def _add_more_button(self, text: str, key_config_key: str, action: Callable[[], None],
                         layout: QVBoxLayout) -> QPushButton:
        keys = KeyConfig().get(key_config_key)
        button = QPushButton(f'{text} ({get_key_display_string(keys, rich_text=False)})' if keys != '' else text)
        button.setFlat(True)
        button.clicked.connect(self.header.popover.hide)
        button.clicked.connect(lambda: action())  # pylint: disable=unnecessary-lambda
        layout.addWidget(button)
        return button

    def _select_offset(self, offset: int) -> None:
        self._image_stack.offset_active_selection(offset)

    def _thumbnail_size_chosen_slot(self, index: int) -> None:
        Cache().set(Cache.LAYER_THUMBNAIL_SIZE, self._thumbnail_size_box.itemData(index))

    def more_content(self) -> Optional[QWidget]:
        """Returns the More popover, which the panel always has."""
        return self._more_content

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
            self._content.setMaximumWidth(QWIDGETSIZE_MAX)
            self._layer_list.set_readable_names(False)
            layout.setAlignment(self._properties, Qt.AlignmentFlag(0))
        else:
            layout.addWidget(self._properties, 0, 0)
            layout.addWidget(self._layer_list, 0, 1)
            layout.setColumnStretch(1, 1)
            layout.setRowStretch(0, 1)
            self._properties.setMaximumWidth(STRIP_SECTION_MAX_WIDTH)
            self._layer_list.setMaximumWidth(STRIP_SECTION_MAX_WIDTH)
            # The columns end where their widgets' widths do, and the body's layout keeps them at its left edge:
            self._content.setMaximumWidth(2 * STRIP_SECTION_MAX_WIDTH + max(layout.horizontalSpacing(), 0))
            self._layer_list.set_readable_names(True)
            layout.setAlignment(self._properties, Qt.AlignmentFlag.AlignTop)
        self._properties.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def host_floating_changed(self, floating: bool) -> None:
        """Hides the header while the panel floats, since its title bar shows the name and the layer count."""
        if floating != self._floating:
            self._floating = floating
            self.refit()

    def apply_header_form(self, collapsed: bool) -> None:
        """Hides the header while the panel floats, and otherwise wherever `DockPanel` collapses it."""
        super().apply_header_form(collapsed or self._floating)

    def _apply_bar_form(self, form: Optional[int]) -> None:
        assert form is not None
        self._bar_form = form
        bar_form = BAR_FORMS[form]
        style = (Qt.ToolButtonStyle.ToolButtonTextBesideIcon if bar_form.labeled
                 else Qt.ToolButtonStyle.ToolButtonIconOnly)
        for button in self._bar_buttons:
            button.setIconSize(QSize(bar_form.icon_size, bar_form.icon_size))
            button.setToolButtonStyle(style)
        if form == len(BAR_FORMS) - 1:
            self._narrow_bar_width = fresh_minimum_size(self._button_bar).width()

    @property
    def button_bar_style(self) -> Qt.ToolButtonStyle:
        """Returns the tool button style the action bar's buttons have in its current form."""
        return self._add_button.toolButtonStyle()

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the minimum size, with the width the panel has when the action bar is in its narrowest form.

        The labeled bar forms are wider, so a minimum width that included the applied form would keep the dock from
        shrinking the panel, and the panel could never plan for the narrower size. The height stays as the applied
        form measures it, since the forms differ in height as well. Reading the hint changes no widget, since a
        change would post layout requests that repeat while the window is idle.
        """
        hint = super().minimumSizeHint()
        bar_width = self._button_bar.minimumSizeHint().width()
        # The width the rest of the panel needs, when it is wider than the bar in its narrowest form. The scrolled
        # content sits inside the body's margins, beside a side panel's vertical scroll bar:
        margins = self.content_margins()
        content_width = self._content.layout().minimumSize().width() + margins.left() + margins.right()
        if self.content_scrolls and self.orientation == Orientation.SIDE:
            content_width += self.scroll_bar_extent()
        other = max(content_width, self.header.minimumSizeHint().width(), self._narrow_bar_width)
        reduction = bar_width - other
        if reduction <= 0 or hint.width() < bar_width:
            return hint
        return QSize(hint.width() - reduction, hint.height())

    def _apply_controls_form(self, form: Optional[int]) -> None:
        self._properties.set_stacked(form == CONTROLS_STACKED)

    def _apply_meta_form(self, form: Optional[int]) -> None:
        self._layer_list.set_meta_shown(form is not None)

    def _apply_large_form(self, form: Optional[int]) -> None:
        self._large_form = form is not None
        self._properties.set_labeled(self._large_form)
        self._apply_thumbnail_size()

    def _apply_thumbnail_size(self) -> None:
        """Sets the rows' thumbnails to the chosen size, or on Auto to large while the large form applies."""
        choice = Cache().get(Cache.LAYER_THUMBNAIL_SIZE)
        auto_size = LARGE_THUMBNAIL_SIZE if self._large_form else SMALL_THUMBNAIL_SIZE
        self._layer_list.set_thumbnail_size(THUMBNAIL_SIZES.get(choice, auto_size))

    def _thumbnail_size_change_slot(self, *_args) -> None:
        self._apply_thumbnail_size()
        if self.available_size is not None:
            self.refit()

    def resizeEvent(self, event) -> None:  # pylint: disable=invalid-name
        """Plans for the new size, and saves the panel's bounds when it's a separate window."""
        super().resizeEvent(event)
        if self.isVisible() and self.isWindow():
            Cache().save_bounds(Cache.SAVED_LAYER_WINDOW_POS, self)

    # Layer state:

    def _layer_count_change_slot(self, *_args) -> None:
        count = len(self._image_stack.layer_stack.recursive_child_layers)
        description = ONE_LAYER_DESCRIPTION if count == 1 else LAYER_COUNT_DESCRIPTION.format(count=count)
        self.header.set_description(description)
        self.set_title_note(description)
        # The list's minimum height follows its row count (`LayerList.minimumSizeHint`):
        if self.available_size is not None:
            self.refit()

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
