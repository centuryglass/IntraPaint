"""Shows image layers, and allows the user to manipulate them."""
import logging
from typing import Optional, List, Callable, Any

from PySide6.QtCore import Qt, QSize, QPointF, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QScrollArea, QToolButton, QSlider, \
    QDoubleSpinBox, QComboBox, QApplication, QSizePolicy

from src.config.cache import Cache
from src.image.composite_mode import CompositeMode
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer, LayerParent
from src.image.layers.layer_group import LayerGroup
from src.ui.panel.layer_ui.layer_group_widget import LayerGroupWidget
from src.ui.panel.layer_ui.layer_widget import PREVIEW_SIZE, LAYER_PADDING, MAX_WIDTH, LayerWidget
from src.util.shared_constants import PROJECT_DIR, APP_ICON_PATH, SMALL_ICON_SIZE

logger = logging.getLogger(__name__)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.layer_ui.layer_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


LIST_SPACING = 4

WINDOW_TITLE = _tr('Image Layers')
ADD_BUTTON_TOOLTIP = _tr('Create a new layer above the current active layer.')
ADD_GROUP_BUTTON_TOOLTIP = _tr('Create a new layer group above the current active layer.')
DELETE_BUTTON_TOOLTIP = _tr('Delete the active layer.')
LAYER_UP_BUTTON_TOOLTIP = _tr('Move the active layer up.')
LAYER_DOWN_BUTTON_TOOLTIP = _tr('Move the active layer down.')
MERGE_DOWN_BUTTON_TOOLTIP = _tr('Merge the active layer with the one below it.')
OPACITY_LABEL_TEXT = _tr('Opacity:')
MODE_LABEL_TEXT = _tr('Layer mode:')

ICON_PATH_ADD_BUTTON = f'{PROJECT_DIR}/resources/icons/layer/plus_icon.svg'
ICON_PATH_ADD_GROUP_BUTTON = f'{PROJECT_DIR}/resources/icons/layer/plus_group_icon.svg'
ICON_PATH_DELETE_BUTTON = f'{PROJECT_DIR}/resources/icons/layer/minus_icon.svg'
ICON_PATH_LAYER_UP_BUTTON = f'{PROJECT_DIR}/resources/icons/layer/up_icon.svg'
ICON_PATH_LAYER_DOWN_BUTTON = f'{PROJECT_DIR}/resources/icons/layer/down_icon.svg'
ICON_PATH_MERGE_BUTTON = f'{PROJECT_DIR}/resources/icons/layer/merge_down_icon.svg'

SCROLL_TIMER_INTERVAL_MS = 50


class LayerPanel(QWidget):
    """
    Shows image layers, and allows the user to manipulate them.

    Layers are displayed in a vertical scrolling list. Through context menus, buttons, and drag and drop, the user
    can do the following:
    - Select the active layer
    - Show/hide layers
    - Add new layers
    - Copy existing layers
    - Delete existing layers
    - Change layer order
    - Merge layers

    All actual functionality is provided by ImageStack.
    """

    def __init__(self, image_stack: ImageStack, parent: Optional[QWidget] = None) -> None:
        """Connect to the ImageStack and build control layout."""
        super().__init__(parent)
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        if self.isWindow():
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._layout = QVBoxLayout(self)
        self._image_stack = image_stack
        self._active_layer: Optional[Layer] = None
        self._parent_group_item = LayerGroupWidget(self._image_stack.layer_stack, self._image_stack)
        self._parent_group_item.dragging.connect(self._layer_drag_slot)
        self._parent_group_item.drag_ended.connect(self._layer_drag_end_slot)

        # Layer opacity slider:
        self._opacity_layout = QHBoxLayout()
        self._opacity_layout.setSpacing(0)
        self._opacity_layout.setContentsMargins(0, 0, 0, 0)
        self._opacity_layout.addWidget(QLabel(OPACITY_LABEL_TEXT))
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_layout.addWidget(self._opacity_slider)
        self._opacity_spinbox = QDoubleSpinBox()
        self._opacity_layout.addWidget(self._opacity_spinbox)
        self._layout.addLayout(self._opacity_layout)
        self._opacity_slider.setRange(0, 100)
        self._opacity_spinbox.setRange(0.0, 1.0)
        active_layer = image_stack.active_layer
        self._opacity_slider.setValue(int(active_layer.opacity * 100))
        self._opacity_spinbox.setValue(active_layer.opacity)

        self._opacity_slider.valueChanged.connect(self._update_opacity_slot)
        self._opacity_spinbox.valueChanged.connect(self._update_opacity_slot)

        self._mode_layout = QHBoxLayout()
        self._mode_layout.setSpacing(0)
        self._mode_layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addLayout(self._mode_layout)
        self._mode_layout.addWidget((QLabel(MODE_LABEL_TEXT)))
        self._mode_box = QComboBox()
        self._mode_layout.addWidget(self._mode_box)
        for mode_name in CompositeMode:
            mode = CompositeMode(mode_name)
            qt_mode = mode.qt_composite_mode()
            self._mode_box.addItem(mode_name, qt_mode)
        self._mode_box.currentIndexChanged.connect(self._mode_change_slot)

        # Scrolling layer list:
        self._scroll_area = QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        horizontal_scroll_bar = self._scroll_area.horizontalScrollBar()
        assert horizontal_scroll_bar is not None
        horizontal_scroll_bar.rangeChanged.connect(self.resizeEvent)
        horizontal_scroll_bar.setMinimum(0)
        horizontal_scroll_bar.setMaximum(0)
        self._scroll_area.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self._scroll_area.setWidget(self._parent_group_item)
        self._layout.addWidget(self._scroll_area, stretch=10)
        self._scroll_timer = QTimer()
        self._scroll_timer.timeout.connect(self._scroll_timer_slot)
        self._scroll_offset = 0

        # BUTTON BAR:
        self._button_bar = QWidget(self)
        self._layout.addWidget(self._button_bar)
        self._button_bar_layout = QHBoxLayout(self._button_bar)
        self._button_bar_layout.setSpacing(0)
        self._button_bar_layout.setContentsMargins(0, 0, 0, 0)

        def _create_button(icon_path: str, tooltip: str, action: Callable[..., Any]) -> QToolButton:
            button = QToolButton()
            button.setToolTip(tooltip)
            button.setContentsMargins(2, 2, 2, 2)
            icon = QIcon(icon_path)
            button.setIcon(icon)
            button.setIconSize(QSize(SMALL_ICON_SIZE, SMALL_ICON_SIZE))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            button.clicked.connect(lambda: action())
            self._button_bar_layout.addWidget(button)
            return button

        self._add_button = _create_button(ICON_PATH_ADD_BUTTON, ADD_BUTTON_TOOLTIP, self._image_stack.create_layer)
        self._add_group_button = _create_button(ICON_PATH_ADD_GROUP_BUTTON, ADD_GROUP_BUTTON_TOOLTIP,
                                                self._image_stack.create_layer_group)
        self._delete_button = _create_button(ICON_PATH_DELETE_BUTTON, DELETE_BUTTON_TOOLTIP, self._image_stack.remove_layer)
        self._move_up_button = _create_button(ICON_PATH_LAYER_UP_BUTTON, LAYER_UP_BUTTON_TOOLTIP,
                                              lambda: self._image_stack.move_layer_by_offset(-1))
        self._move_up_button = _create_button(ICON_PATH_LAYER_DOWN_BUTTON, LAYER_DOWN_BUTTON_TOOLTIP,
                                              lambda: self._image_stack.move_layer_by_offset(1))

        self._merge_down_button = _create_button(ICON_PATH_MERGE_BUTTON, MERGE_DOWN_BUTTON_TOOLTIP,
                                                 self._image_stack.merge_layer_down)

        self._image_stack.active_layer_changed.connect(self._active_layer_change_slot)
        self._image_stack.layer_added.connect(self._layer_added_slot)
        self._active_layer_change_slot(self._image_stack.active_layer)
        self._image_stack.layer_order_changed.connect(self._update_order_slot)

    def _scroll_timer_slot(self) -> None:
        if self._scroll_offset == 0:
            self._scroll_timer.stop()
            return
        scroll_bar = self._scroll_area.verticalScrollBar()
        assert scroll_bar is not None
        if self._scroll_offset < 0:
            if scroll_bar.value() > scroll_bar.minimum():
                scroll_bar.setValue(max(scroll_bar.value() + self._scroll_offset, scroll_bar.minimum()))
            else:
                self._scroll_offset = 0
                self._scroll_timer.stop()
        else:
            if scroll_bar.value() < scroll_bar.maximum():
                scroll_bar.setValue(min(scroll_bar.value() + self._scroll_offset, scroll_bar.maximum()))
            else:
                self._scroll_offset = 0
                self._scroll_timer.stop()

    def _layer_drag_slot(self, position: QPointF) -> None:
        local_pos = self.mapFromGlobal(self._parent_group_item.mapToGlobal(position))
        top_threshold = self._scroll_area.y() + (self.height() // 8)
        bottom_threshold = self._button_bar.y() - (self.height() // 8)
        scroll_bar = self._scroll_area.verticalScrollBar()
        assert scroll_bar is not None
        if scroll_bar.value() > scroll_bar.minimum() and local_pos.y() < top_threshold:
            self._scroll_offset = -1
            if local_pos.y() < (top_threshold - self.height() // 16):
                self._scroll_offset -= 1
            if not self._scroll_timer.isActive():
                self._scroll_timer.start(SCROLL_TIMER_INTERVAL_MS)
        elif scroll_bar.value() < scroll_bar.maximum() and local_pos.y() > bottom_threshold:
            self._scroll_offset = 1
            if local_pos.y() > (bottom_threshold + self.height() // 16):
                self._scroll_offset += 1
            if not self._scroll_timer.isActive():
                self._scroll_timer.start(SCROLL_TIMER_INTERVAL_MS)
        else:
            self._scroll_offset = 0
            if self._scroll_timer.isActive():
                self._scroll_timer.stop()

    def _layer_drag_end_slot(self) -> None:
        if self._scroll_timer.isActive():
            self._scroll_timer.stop()

    def resizeEvent(self, event):
        """Keep at least one layer visible, block horizontal scrolling."""
        self._scroll_area.setMinimumHeight(self._parent_group_item.layer_item.sizeHint().height() + LIST_SPACING)
        min_scroll_width = self._parent_group_item.sizeHint().width()
        vertical_scrollbar = self._scroll_area.verticalScrollBar()
        if vertical_scrollbar is not None:
            min_scroll_width += vertical_scrollbar.sizeHint().width()
        horizontal_scrollbar = self._scroll_area.horizontalScrollBar()
        if horizontal_scrollbar is not None:
            horizontal_scrollbar.setRange(0, 0)
        self._scroll_area.setMinimumWidth(min_scroll_width)
        if self.isVisible() and self.isWindow():
            Cache().save_bounds(Cache.SAVED_LAYER_WINDOW_POS, self)

    def sizeHint(self) -> QSize:
        """At minimum, always show one layer."""
        layer_width = PREVIEW_SIZE.width() + SMALL_ICON_SIZE + 2 * LAYER_PADDING
        layer_height = max(SMALL_ICON_SIZE, PREVIEW_SIZE.height())
        width = min(MAX_WIDTH, layer_width + LAYER_PADDING)
        height = layer_height + LAYER_PADDING
        scrollbar = self._scroll_area.verticalScrollBar()
        if scrollbar is not None:
            width += scrollbar.sizeHint().width()

        bar_size = self._button_bar.sizeHint()
        height += bar_size.height() + LAYER_PADDING * 2
        width = max(bar_size.width(), width)
        return QSize(width, height)

    def minimumSizeHint(self) -> QSize:
        """At minimum, always show one layer."""
        return self.sizeHint()

    def _update_order_slot(self) -> None:
        self._parent_group_item.reorder_child_layers()

    def _update_opacity_slot(self, opacity: int | float) -> None:
        if isinstance(opacity, int):
            opacity_percent = opacity
            opacity_fraction = opacity / 100
        else:
            opacity_percent = int(opacity * 100)
            opacity_fraction = opacity
        active_layer = self._image_stack.active_layer
        if active_layer.opacity != opacity_fraction:
            active_layer.opacity = opacity_fraction
        for input_widget, value in ((self._opacity_slider, opacity_percent),
                                    (self._opacity_spinbox, opacity_fraction)):
            if input_widget.value() != value:
                input_widget.valueChanged.disconnect(self._update_opacity_slot)
                input_widget.setValue(value)
                input_widget.valueChanged.connect(self._update_opacity_slot)

    def _mode_change_slot(self, _) -> None:
        mode_text = self._mode_box.currentText()
        mode = CompositeMode(mode_text)
        active_layer = self._image_stack.active_layer
        if active_layer.composition_mode != mode:
            active_layer.composition_mode = mode

    def _find_layer_parent_widgets(self, layer: Layer) -> List[LayerGroupWidget]:
        """Returns a list of all LayerGroupWidgets connected to layers that contain the given layer"""
        parent_layers: List[LayerGroup] = []
        # Iterate through parent/child pairs, starting with layer.layer_parent and layer, and continue up the tree
        # until the topmost layer group is reached. For each pair, insert (parent, child_index) into parent_map
        # at the start.
        parent_iter: Optional[LayerParent] = layer.layer_parent
        while parent_iter is not None:
            assert isinstance(parent_iter, LayerGroup)
            parent_layers.insert(0, parent_iter)
            parent_iter = parent_iter.layer_parent
        assert len(parent_layers) == 0 or parent_layers[0] == self._image_stack.layer_stack

        # Follow the parent map in reverse through the layer widget tree, appending each parent layer widget to a list:
        parent_widgets: List[LayerGroupWidget] = []
        widget_iter: LayerGroupWidget = self._parent_group_item
        assert isinstance(widget_iter, LayerGroupWidget)
        for i, parent_layer in enumerate(parent_layers):
            assert widget_iter.layer == parent_layer
            assert isinstance(widget_iter, LayerGroupWidget)
            parent_widgets.append(widget_iter)
            if i < (len(parent_layers) - 1):
                child_item = widget_iter.get_child_item(parent_layers[i + 1])
                assert isinstance(child_item, LayerGroupWidget)
                widget_iter = child_item
        return parent_widgets

    def _open_parent_groups(self, layer: Layer) -> None:
        parent_widget_list = self._find_layer_parent_widgets(layer)
        for parent in parent_widget_list:
            if not parent.is_expanded():
                parent.set_expanded(True)

    def _active_layer_change_slot(self, new_active_layer: Layer) -> None:
        if self._active_layer is not None:
            self._active_layer.lock_changed.disconnect(self._lock_change_slot)
        self._active_layer = new_active_layer
        self._open_parent_groups(new_active_layer)
        new_active_layer.lock_changed.connect(self._lock_change_slot)
        self._lock_change_slot(new_active_layer, new_active_layer.locked)
        layer_id = new_active_layer.id
        layer_groups: List[LayerGroupWidget] = [self._parent_group_item]
        while len(layer_groups) > 0:
            group = layer_groups.pop()
            group.layer_item.active = group.layer_item.layer.id == layer_id
            for child in group.child_items:
                if isinstance(child, LayerGroupWidget):
                    layer_groups.append(child)
                else:
                    assert isinstance(child, LayerWidget)
                    child.active = child.layer.id == layer_id
        if new_active_layer is not None:
            self._update_opacity_slot(new_active_layer.opacity)
            image_mode = new_active_layer.composition_mode
            mode_index = self._mode_box.findText(image_mode)
            if mode_index >= 0:
                self._mode_box.setCurrentIndex(mode_index)

    def _layer_added_slot(self, new_layer: Layer) -> None:
        self._open_parent_groups(new_layer)

    def _lock_change_slot(self, layer: Layer, is_locked: bool) -> None:
        assert layer == self._image_stack.active_layer or layer.contains_recursive(self._image_stack.active_layer)
        for widget in (self._opacity_spinbox,
                       self._opacity_slider,
                       self._mode_box,
                       self._merge_down_button,
                       self._delete_button):
            widget.setEnabled(not is_locked)
