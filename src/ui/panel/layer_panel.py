"""Shows image layers, and allows the user to manipulate them."""

from typing import Optional, List, Callable, cast, Any

from PyQt5.QtCore import Qt, QRect, QSize, QPoint
from PyQt5.QtGui import QPainter, QColor, QPaintEvent, QMouseEvent, QIcon, QPixmap
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QScrollArea, QSizePolicy, QPushButton, QMenu, \
    QToolButton, QAction, QSlider, QDoubleSpinBox, QComboBox

from src.config.cache import Cache
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.layer_stack import LayerStack
from src.tools.selection_tool import SELECTION_TOOL_LABEL
from src.ui.widget.bordered_widget import BorderedWidget
from src.ui.input_fields.editable_label import EditableLabel
from src.util.display_size import find_text_size
from src.util.geometry_utils import get_scaled_placement, get_rect_transformation
from src.util.image_utils import get_transparency_tile_pixmap
from src.util.shared_constants import COMPOSITION_MODES

LIST_SPACING = 4
MIN_VISIBLE_LAYERS = 3
PREVIEW_SIZE = QSize(80, 80)
ICON_SIZE = QSize(32, 32)
LAYER_PADDING = 10
MAX_WIDTH = PREVIEW_SIZE.width() + ICON_SIZE.width() + LAYER_PADDING * 2 + 400
ICON_PATH_VISIBLE_LAYER = 'resources/icons/layer/visible.svg'
ICON_PATH_HIDDEN_LAYER = 'resources/icons/layer/hidden.svg'

WINDOW_TITLE = 'Image Layers'

ADD_BUTTON_ICON = 'resources/icons/layer/plus_icon.svg'
ADD_BUTTON_TOOLTIP = 'Create a new layer above the current active layer.'
DELETE_BUTTON_ICON = 'resources/icons/layer/minus_icon.svg'
DELETE_BUTTON_TOOLTIP = 'Delete the active layer.'
LAYER_UP_BUTTON_ICON = 'resources/icons/layer/up_icon.svg'
LAYER_UP_BUTTON_TOOLTIP = 'Move the active layer up.'
LAYER_DOWN_BUTTON_ICON = 'resources/icons/layer/down_icon.svg'
LAYER_DOWN_BUTTON_TOOLTIP = 'Move the active layer down.'
MERGE_DOWN_BUTTON_ICON = 'resources/icons/layer/merge_down_icon.svg'
MERGE_DOWN_BUTTON_TOOLTIP = 'Merge the active layer with the one below it.'
MERGE_BUTTON_LABEL = 'Merge Down'

OPACITY_LABEL_TEXT = 'Opacity:'
MODE_LABEL_TEXT = 'Layer mode:'

MENU_OPTION_MOVE_UP = 'Move up'
MENU_OPTION_MOVE_DOWN = 'Move down'
MENU_OPTION_COPY = 'Copy'
MENU_OPTION_DELETE = 'Delete'
MENU_OPTION_MERGE_DOWN = 'Merge down'
MENU_OPTION_CLEAR_SELECTED = 'Clear selected'
MENU_OPTION_COPY_SELECTED = 'Copy selected to new layer'
MENU_OPTION_LAYER_TO_IMAGE_SIZE = 'Layer to image size'
MENU_OPTION_CROP_TO_CONTENT = 'Crop layer to content'
MENU_OPTION_CLEAR_SELECTION = 'Clear selection'
MENU_OPTION_SELECT_ALL = 'Select all in active layer'
MENU_OPTION_INVERT_SELECTION = "Invert selection"


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
        self._layout = QVBoxLayout(self)
        self._image_stack = image_stack
        self._layer_widgets: List[_LayerItem] = []

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
        if active_layer is not None:
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
        for mode_name, mode in COMPOSITION_MODES.items():
            self._mode_box.addItem(mode_name, mode)
        self._mode_box.currentIndexChanged.connect(self._mode_change_slot)

        # Build the scrolling layer list:
        self._layer_list = BorderedWidget(self)
        self._list_layout = QVBoxLayout(self._layer_list)
        self._list_layout.setSpacing(LIST_SPACING)
        self._layer_list.contents_margin = LAYER_PADDING
        self._list_layout.setAlignment(cast(Qt.Alignment, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop))

        self._scroll_area = QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        horizontal_scroll_bar = self._scroll_area.horizontalScrollBar()
        assert horizontal_scroll_bar is not None
        horizontal_scroll_bar.rangeChanged.connect(self.resizeEvent)
        horizontal_scroll_bar.setMinimum(0)
        horizontal_scroll_bar.setMaximum(0)
        self._scroll_area.setAlignment(cast(Qt.Alignment, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop))
        self._scroll_area.setWidget(self._layer_list)

        self._layer_list.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred))
        self._scroll_area.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred))
        self._layout.addWidget(self._scroll_area, stretch=10)

        def _add_layer_widget(new_layer: Layer) -> None:
            layer_idx = -new_layer.z_value
            widget = self._layer_widget(new_layer)
            self._layer_widgets.append(widget)
            self._list_layout.insertWidget(layer_idx + 1, widget)
            self.resizeEvent(None)
        self._image_stack.layer_added.connect(_add_layer_widget)
        _add_layer_widget(image_stack.selection_layer)
        for layer in self._image_stack.layers:
            _add_layer_widget(layer)

        def _delete_layer_widget(deleted_layer: Layer) -> None:
            layer_widget = self._layer_widget(deleted_layer)
            if layer_widget is not None:
                self._list_layout.removeWidget(layer_widget)
                layer_widget.setParent(None)
                if layer_widget in self._layer_widgets:
                    self._layer_widgets.remove(layer_widget)
                self.resizeEvent(None)
        self._image_stack.layer_removed.connect(_delete_layer_widget)

        def _activate_layer(new_active_layer: Optional[Layer], _=None) -> None:
            layer_id = None if new_active_layer is None else new_active_layer.id
            for widget in self._layer_widgets:
                widget.active = layer_id == widget.layer.id
            if new_active_layer is not None:
                self._update_opacity_slot(new_active_layer.opacity)
                image_mode = new_active_layer.composition_mode
                mode_index = self._mode_box.findData(image_mode)
                if mode_index >= 0:
                    self._mode_box.setCurrentIndex(mode_index)
        self._image_stack.active_layer_changed.connect(_activate_layer)
        if self._image_stack.active_layer is not None:
            _activate_layer(self._image_stack.active_layer)

        # BUTTON BAR:
        self._button_bar = QWidget()
        self._layout.addWidget(self._button_bar)
        self._button_bar_layout = QHBoxLayout(self._button_bar)
        self._button_bar_layout.setSpacing(0)
        self._button_bar_layout.setContentsMargins(0, 0, 0, 0)

        def _create_button(icon_path: str, tooltip: str, action: Callable[..., Any]) -> QPushButton:
            button = QToolButton()
            button.setToolTip(tooltip)
            button.setContentsMargins(0, 0, 0, 0)
            icon = QIcon(icon_path)
            button.setIcon(icon)
            button.setToolButtonStyle(Qt.ToolButtonIconOnly)
            button.clicked.connect(lambda: action())
            self._button_bar_layout.addWidget(button)
            return button

        self._add_button = _create_button(ADD_BUTTON_ICON, ADD_BUTTON_TOOLTIP, self._image_stack.create_layer)
        self._delete_button = _create_button(DELETE_BUTTON_ICON, DELETE_BUTTON_TOOLTIP, self._image_stack.remove_layer)
        self._move_up_button = _create_button(LAYER_UP_BUTTON_ICON, LAYER_UP_BUTTON_TOOLTIP,
                                              lambda: self._image_stack.move_layer(-1))
        self._move_up_button = _create_button(LAYER_DOWN_BUTTON_ICON, LAYER_DOWN_BUTTON_TOOLTIP,
                                              lambda: self._image_stack.move_layer(1))

        self._merge_down_button = _create_button(MERGE_DOWN_BUTTON_ICON, MERGE_DOWN_BUTTON_TOOLTIP,
                                                 self._image_stack.merge_layer_down)

    def resizeEvent(self, event):
        """Keep a fixed number of layers visible."""
        if len(self._layer_widgets) > 0:
            self._scroll_area.setMinimumHeight((self._layer_widgets[0].height() + LIST_SPACING)
                                               * min(MIN_VISIBLE_LAYERS, len(self._layer_widgets)))
        min_scroll_width = self._layer_list.sizeHint().width()
        vertical_scrollbar = self._scroll_area.verticalScrollBar()
        if vertical_scrollbar is not None:
            min_scroll_width += vertical_scrollbar.sizeHint().width()
        horizontal_scrollbar = self._scroll_area.horizontalScrollBar()
        if horizontal_scrollbar is not None:
            horizontal_scrollbar.setRange(0, 0)
        self._scroll_area.setMinimumWidth(min_scroll_width)

    def sizeHint(self) -> QSize:
        """Returns a reasonable default size."""
        layer_width = 0
        layer_height = 0
        for layer_widget in self._layer_widgets:
            size = find_text_size(layer_widget.layer.name)
            layer_width = max(layer_width, size.width())
            layer_height = max(layer_height, size.height())
        layer_width += PREVIEW_SIZE.width() + ICON_SIZE.width() + 2 * LAYER_PADDING
        layer_height = max(layer_height, ICON_SIZE.height(), PREVIEW_SIZE.height())
        width = min(MAX_WIDTH, layer_width + LAYER_PADDING)
        height = layer_height * min(MIN_VISIBLE_LAYERS, len(self._layer_widgets)) + LAYER_PADDING
        scrollbar = self._scroll_area.verticalScrollBar()
        if scrollbar is not None:
            width += scrollbar.sizeHint().width()

        bar_size = self._button_bar.sizeHint()
        height += bar_size.height() + LAYER_PADDING * 2
        width = max(bar_size.width(), width)
        return QSize(width, height)

    def _layer_widget(self, layer: Layer) -> 'LayerGraphicsItem':
        """Returns the layer widget for the given layer, or creates and returns a new one if none exists."""
        for widget in self._layer_widgets:
            if widget.layer == layer:
                return widget
        return _LayerItem(layer, self._image_stack, self)

    def _update_opacity_slot(self, opacity: int | float) -> None:
        if isinstance(opacity, int):
            opacity_percent = opacity
            opacity_fraction = opacity / 100
        else:
            opacity_percent = int(opacity * 100)
            opacity_fraction = opacity
        active_layer = self._image_stack.active_layer
        if active_layer is not None and active_layer.opacity != opacity_fraction:
            active_layer.opacity = opacity_fraction
        for input_widget, value in ((self._opacity_slider, opacity_percent),
                                    (self._opacity_spinbox, opacity_fraction)):
            if input_widget.value() != value:
                input_widget.valueChanged.disconnect(self._update_opacity_slot)
                input_widget.setValue(value)
                input_widget.valueChanged.connect(self._update_opacity_slot)

    def _mode_change_slot(self, _) -> None:
        mode_text = self._mode_box.currentText()
        assert mode_text in COMPOSITION_MODES
        mode = COMPOSITION_MODES[mode_text]
        active_layer = self._image_stack.active_layer
        if active_layer is not None and active_layer.composition_mode != mode:
            active_layer.composition_mode = mode


class _LayerItem(BorderedWidget):
    """A single layer's representation in the list"""

    # Shared transparency background pixmap. The first LayerGraphicsItem created initializes it, after that access is strictly
    # read-only.
    _layer_transparency_background: Optional[QPixmap] = None

    def __init__(self, layer: Layer, image_stack: ImageStack, parent: QWidget) -> None:
        super().__init__(parent)
        self._layer = layer
        self._image_stack = image_stack
        self._layout = QHBoxLayout(self)
        self._layout.addSpacing(PREVIEW_SIZE.width())
        if layer == image_stack.selection_layer:
            self._label = QLabel(layer.name, self)
        else:
            self._label = EditableLabel(layer.name, self)
            self._label.text_changed.connect(self.rename_layer)
        text_alignment = Qt.AlignmentFlag.AlignCenter
        self._label.setAlignment(text_alignment)
        self._label.setWordWrap(True)

        self._layout.addWidget(self._label, stretch=40)
        self._layer.content_changed.connect(self.update)
        self._layer.visibility_changed.connect(self.update)
        self._layer.transform_changed.connect(self._update_all)
        self._layer.size_changed.connect(self._update_all)
        self._active = False
        self._active_color = self.color
        self._inactive_color = self._active_color.darker() if self._active_color.lightness() > 100 \
            else self._active_color.lighter()
        self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum))
        if _LayerItem._layer_transparency_background is None:
            _LayerItem._layer_transparency_background = get_transparency_tile_pixmap(QSize(64, 64))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)

        class VisibilityButton(QSvgWidget):
            """Show/hide layer button."""

            def __init__(self, connected_layer: Layer) -> None:
                """Connect to the layer and load the initial icon."""
                super().__init__()
                self.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
                self._layer = connected_layer
                layer.visibility_changed.connect(self._update_icon)
                self._update_icon()

            def sizeHint(self):
                """Use a fixed size for icons."""
                return ICON_SIZE

            def _update_icon(self):
                """Loads the open eye icon if the layer is visible, the closed eye icon otherwise."""
                self.load(ICON_PATH_VISIBLE_LAYER if self._layer.visible else ICON_PATH_HIDDEN_LAYER)
                self.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
                self.update()

            def mousePressEvent(self, unused_event: Optional[QMouseEvent]) -> None:
                """Toggle visibility on click."""
                self._layer.visible = not self._layer.visible

        self._visibility_button = VisibilityButton(self._layer)
        self._layout.addWidget(self._visibility_button, stretch=10)

    def paintEvent(self, event: Optional[QPaintEvent]) -> None:
        """Draws the scaled layer contents to the widget."""
        content_bounds = self._image_stack.merged_layer_bounds
        image_bounds = self._image_stack.bounds
        layer_bounds = self._layer.full_image_bounds
        pixmap = self._layer.pixmap
        paint_bounds = QRect(LAYER_PADDING, LAYER_PADDING, self._label.x() - LAYER_PADDING * 2,
                             self.height() - LAYER_PADDING * 2)
        paint_bounds = get_scaled_placement(paint_bounds, content_bounds.size(), 2)
        painter = QPainter(self)
        if self._layer != self._image_stack.selection_layer:
            assert _LayerItem._layer_transparency_background is not None
            painter.drawTiledPixmap(paint_bounds, _LayerItem._layer_transparency_background)
        else:
            painter.fillRect(paint_bounds, Qt.GlobalColor.darkGray)
        if not any(rect.isEmpty() for rect in (content_bounds, image_bounds, layer_bounds, paint_bounds)):
            transformation = get_rect_transformation(content_bounds, paint_bounds)
            painter.setTransform(transformation)
            painter.setPen(Qt.black)
            painter.drawRect(content_bounds)
            painter.setTransform(self._layer.full_image_transform, True)
            painter.save()
            painter.setOpacity(self._layer.opacity)
            painter.setCompositionMode(self._layer.composition_mode)
            painter.drawPixmap(self._layer.local_bounds, pixmap)
            painter.restore()
            painter.drawRect(image_bounds)
            painter.drawRect(layer_bounds)
            if not self._layer.visible:
                painter.fillRect(content_bounds, QColor.fromRgb(0, 0, 0, 100))
        painter.end()
        super().paintEvent(event)

    def rename_layer(self, new_name: str) -> None:
        """Update the layer name."""
        self._layer.name = new_name

    def sizeHint(self) -> QSize:
        """Returns a reasonable default size."""
        text_size = find_text_size(self.layer.name)
        layer_width = text_size.width()
        layer_height = text_size.height()
        layer_width += PREVIEW_SIZE.width() + ICON_SIZE.width()
        layer_width = min(layer_width, MAX_WIDTH)
        layer_height = max(layer_height, ICON_SIZE.height(), PREVIEW_SIZE.height())
        return QSize(layer_width, layer_height)

    @property
    def layer(self) -> Layer:
        """Return the connected layer."""
        return self._layer

    @property
    def active(self) -> bool:
        """Returns whether this layer is active."""
        return self._active

    @active.setter
    def active(self, is_active: bool) -> None:
        """Updates whether this layer is active."""
        self.color = self._active_color if is_active else self._inactive_color
        self.line_width = 10 if is_active else 1
        self._active = is_active

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Activate layer on click."""
        assert event is not None
        if self._layer == self._image_stack.selection_layer:
            Cache().set(Cache.LAST_ACTIVE_TOOL, SELECTION_TOOL_LABEL)
        elif not self.active and event.button() == Qt.MouseButton.LeftButton:
            self._image_stack.active_layer = self._layer
            self.active = True
            self.update()

    def _update_all(self) -> None:
        parent = self.parent()
        if parent is None:
            return
        for child in parent.findChildren(QWidget):
            child.update()

    def _menu(self, pos: QPoint) -> None:
        menu = QMenu()
        menu.setTitle(self._layer.name)

        def _new_action(name: str) -> QAction:
            action = menu.addAction(name)
            assert action is not None
            return action

        if self._layer != self._image_stack.selection_layer and self._layer.parent is not None:
            index = None
            parent = cast(LayerStack, self._layer.parent)
            if parent is not None:
                index = parent.get_layer_index(self._layer)

            if index is not None:
                up_option = _new_action(MENU_OPTION_MOVE_UP)
                up_option.triggered.connect(lambda: self._image_stack.move_layer(-1, self.layer))

                if index < self._image_stack.count - 1:
                    down_option = _new_action(MENU_OPTION_MOVE_DOWN)
                    down_option.triggered.connect(lambda: self._image_stack.move_layer(1, self.layer))

            copy_option = _new_action(MENU_OPTION_COPY)
            copy_option.triggered.connect(lambda: self._image_stack.copy_layer(self.layer))

            delete_option = _new_action(MENU_OPTION_DELETE)
            delete_option.triggered.connect(lambda: self._image_stack.remove_layer(self.layer))

            if index is not None and index < self._image_stack.count - 1:
                merge_option = _new_action(MENU_OPTION_MERGE_DOWN)
                merge_option.triggered.connect(lambda: self._image_stack.merge_layer_down(self.layer))

            clear_option = _new_action(MENU_OPTION_CLEAR_SELECTED)
            clear_option.triggered.connect(lambda: self._image_stack.cut_selected(self.layer))

            copy_masked_option = _new_action(MENU_OPTION_COPY_SELECTED)

            def do_copy() -> None:
                """Make the copy, then add it as a new layer."""
                masked = self._image_stack.copy_selected(self.layer)
                self._image_stack.create_layer(self._layer.name + ' content', masked, layer_index=index)

            copy_masked_option.triggered.connect(do_copy)

            resize_option = _new_action(MENU_OPTION_LAYER_TO_IMAGE_SIZE)
            resize_option.triggered.connect(lambda: self._image_stack.layer_to_image_size(self.layer))

            crop_content_option = _new_action(MENU_OPTION_CROP_TO_CONTENT)
            crop_content_option.triggered.connect(lambda: print('TODO: crop layer to content'))
        else:
            invert_option = _new_action(MENU_OPTION_INVERT_SELECTION)
            invert_option.triggered.connect(self._image_stack.selection_layer.invert_selection)
            clear_mask_option = _new_action(MENU_OPTION_CLEAR_SELECTION)
            clear_mask_option.triggered.connect(self._image_stack.selection_layer.clear)
            if self._image_stack.has_image:
                mask_active_option = _new_action(MENU_OPTION_SELECT_ALL)

                def mask_active() -> None:
                    """Draw the layer into the mask, then let SelectionLayer automatically convert it to
                       red/transparent."""
                    active_layer = self._image_stack.active_layer
                    assert active_layer is not None
                    layer_image, offset_transform = active_layer.transformed_image()
                    with self._image_stack.selection_layer.borrow_image() as mask_image:
                        assert mask_image is not None
                        painter = QPainter(mask_image)
                        painter.setCompositionMode(QPainter.CompositionMode_Source)
                        painter.setTransform(offset_transform)
                        painter.drawImage(QRect(0, 0, mask_image.width(), mask_image.height()), layer_image)
                        painter.end()

                mask_active_option.triggered.connect(mask_active)

        if isinstance(self.layer, ImageLayer):
            mirror_horizontal_option = _new_action('Mirror horizontally')
            mirror_horizontal_option.triggered.connect(self.layer.flip_horizontal)

            mirror_vert_option = _new_action('Mirror vertically')
            mirror_vert_option.triggered.connect(self.layer.flip_vertical)

        menu.exec_(self.mapToGlobal(pos))

