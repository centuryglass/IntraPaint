"""Shows image layers, and allows the user to manipulate them."""

from typing import Optional, List, Callable
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QScrollArea, QSizePolicy, QPushButton, QMenu
from PyQt5.QtGui import QPainter, QColor, QPaintEvent, QMouseEvent
from PyQt5.QtCore import Qt, QRect, QSize, QPoint
from PyQt5.QtSvg import QSvgWidget
from src.image.image_layer import ImageLayer
from src.image.layer_stack import LayerStack
from src.ui.util.get_scaled_placement import get_scaled_placement
from src.ui.widget.bordered_widget import BorderedWidget
from src.ui.util.tile_pattern_fill import get_transparency_tile_pixmap

LIST_SPACING = 4
DEFAULT_LIST_ITEM_SIZE = QSize(350, 60)
DEFAULT_LIST_SIZE = QSize(380, 400)
ICON_PATH_VISIBLE_LAYER = 'resources/visible.svg'
ICON_PATH_HIDDEN_LAYER = 'resources/hidden.svg'

WINDOW_TITLE = 'Image Layers'

ADD_BUTTON_LABEL = '+'
ADD_BUTTON_TOOLTIP = 'Create a new layer below the current active layer.'
DELETE_BUTTON_LABEL = '-'
DELETE_BUTTON_TOOLTIP = 'Delete the active layer.'
LAYER_UP_BUTTON_LABEL = '↑'
LAYER_UP_BUTTON_TOOLTIP = 'Move the active layer up.'
LAYER_DOWN_BUTTON_LABEL = '↓'
LAYER_DOWN_BUTTON_TOOLTIP = 'Move the active layer down.'
MERGE_DOWN_BUTTON_LABEL = '⇓'
MERGE_DOWN_BUTTON_TOOLTIP = 'Merge the active layer with the one below it.'
MERGE_BUTTON_LABEL = 'Merge Down'


class LayerItem(BorderedWidget):
    """A single layer's representation in the list"""

    # Shared transparency background pixmap. The first LayerItem created initializes it, after that access is strictly
    # read-only.
    _layer_transparency_background = None

    def __init__(self, layer: ImageLayer, layer_stack: LayerStack, parent: QWidget) -> None:
        super().__init__(parent)
        self._layer = layer
        self._layer_stack = layer_stack
        self._layout = QHBoxLayout(self)
        self._layout.addStretch(50)
        self._layout.addSpacing(50)
        self._label = QLabel(layer.name, self)
        self._layout.addWidget(self._label, stretch=40)
        self._layer.content_changed.connect(self.update)
        self._layer.visibility_changed.connect(self.update)
        self._active = False
        self._active_color = self.color
        self._inactive_color = self._active_color.darker() if self._active_color.lightness() > 100 \
            else self._active_color.lighter()
        self.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed))
        if LayerItem._layer_transparency_background is None:
            LayerItem._layer_transparency_background = get_transparency_tile_pixmap(QSize(64, 64))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)

        class VisibilityButton(QSvgWidget):
            """Show/hide layer button."""

            def __init__(self, connected_layer: ImageLayer) -> None:
                """Connect to the layer and load the initial icon."""
                super().__init__()
                self._layer = connected_layer
                layer.visibility_changed.connect(self._update_icon)
                self._update_icon()

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
        pixmap = self._layer.pixmap
        pixmap_bounds = QRect(0, 0, self._label.x(), self.height())
        pixmap_bounds = get_scaled_placement(pixmap_bounds, pixmap.size(), 2)
        pixmap_bounds.moveLeft(LIST_SPACING)
        painter = QPainter(self)
        if self._layer != self._layer_stack.mask_layer:
            painter.drawTiledPixmap(pixmap_bounds, LayerItem._layer_transparency_background)
        else:
            painter.setPen(Qt.black)
            painter.drawRect(pixmap_bounds)
        painter.drawPixmap(pixmap_bounds, pixmap)
        if not self._layer.visible:
            painter.fillRect(pixmap_bounds, QColor.fromRgb(0, 0, 0, 100))
        super().paintEvent(event)

    def sizeHint(self) -> QSize:
        """Returns a reasonable default size."""
        return DEFAULT_LIST_ITEM_SIZE

    @property
    def layer(self) -> ImageLayer:
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
        if not self.active and event.button() == Qt.MouseButton.LeftButton:
            self._layer_stack.active_layer = self._layer
            self.active = True
            self.update()

    def _menu(self, pos: QPoint) -> None:
        menu = QMenu()
        menu.setTitle(self._layer.name)
        if self._layer != self._layer_stack.mask_layer:
            index = self._layer_stack.get_layer_index(self._layer)

            if index > 0:
                up_option = menu.addAction('Move up')
                up_option.triggered.connect(lambda: self._layer_stack.move_layer(-1, self.layer))

            if index < self._layer_stack.count - 1:
                down_option = menu.addAction('Move down')
                down_option.triggered.connect(lambda: self._layer_stack.move_layer(1, self.layer))

            copy_option = menu.addAction('Copy')
            copy_option.triggered.connect(lambda: self._layer_stack.copy_layer(self.layer))

            delete_option = menu.addAction('Delete')
            delete_option.triggered.connect(lambda: self._layer_stack.remove_layer(self.layer))

            if index < self._layer_stack.count - 1:
                merge_option = menu.addAction('Merge down')
                merge_option.triggered.connect(lambda: self._layer_stack.merge_layer_down(self.layer))

            clear_option = menu.addAction('Clear masked')
            clear_option.triggered.connect(lambda: self._layer_stack.cut_masked(self.layer))

            copy_masked_option = menu.addAction('Copy masked to new layer')

            def do_copy() -> None:
                """Make the copy, then add it as a new layer."""
                masked = self._layer_stack.copy_masked(self.layer)
                self._layer_stack.create_layer(self._layer.name + ' content', masked, layer_index=index)

            copy_masked_option.triggered.connect(do_copy)

            resize_option = menu.addAction('Layer to image size')
            resize_option.triggered.connect(lambda: self._layer_stack.layer_to_image_size(self.layer))

            crop_content_option = menu.addAction('Crop layer to content')
            crop_content_option.triggered.connect(self._layer.crop_to_content)
        else:
            clear_mask_option = menu.addAction('Clear mask')
            clear_mask_option.triggered.connect(self._layer_stack.mask_layer.clear)
            if self._layer_stack.active_layer_index is not None:
                mask_active_option = menu.addAction('Mask all in active layer')

                def mask_active() -> None:
                    """Draw the layer into the mask, then let MaskLayer automatically convert it to red/transparent."""
                    layer_image = self._layer_stack.get_layer_by_index(
                        self._layer_stack.active_layer_index).qimage.copy()
                    with self._layer_stack.mask_layer.borrow_image() as mask_image:
                        painter = QPainter(mask_image)
                        painter.setCompositionMode(QPainter.CompositionMode_Source)
                        painter.drawImage(QRect(0, 0, mask_image.width(), mask_image.height()), layer_image)
                        painter.end()

                mask_active_option.triggered.connect(mask_active)

        mirror_horiz_option = menu.addAction('Mirror horizontally')
        mirror_horiz_option.triggered.connect(self.layer.flip_horizontal)

        mirror_vert_option = menu.addAction('Mirror vertically')
        mirror_vert_option.triggered.connect(self.layer.flip_vertical)

        menu.exec_(self.mapToGlobal(pos))


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

    All actual functionality is provided by LayerStack.
    """

    def __init__(self, layer_stack: LayerStack, parent: Optional[QWidget] = None) -> None:
        """Connect to the LayerStack and build control layout."""
        super().__init__(parent)
        self.setWindowTitle(WINDOW_TITLE)
        self._layout = QVBoxLayout(self)
        self._layer_stack = layer_stack
        self._layer_widgets: List[LayerItem] = []

        # Build the scrolling layer list:
        self._layer_list = BorderedWidget(self)
        self._list_layout = QVBoxLayout(self._layer_list)
        self._list_layout.setSpacing(LIST_SPACING)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        self._scroll_area = QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self._scroll_area.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self._scroll_area.setWidget(self._layer_list)

        self._layer_list.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding))
        self._scroll_area.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Expanding))
        self._layout.addWidget(self._scroll_area, stretch=10)

        def _add_layer_widget(layer: ImageLayer, layer_idx: int) -> None:
            widget = self._layer_widget(layer)
            self._layer_widgets.append(widget)
            self._list_layout.insertWidget(layer_idx + 1, widget)
        self._layer_stack.layer_added.connect(_add_layer_widget)
        _add_layer_widget(layer_stack.mask_layer, -1)
        for i in range(self._layer_stack.count):
            _add_layer_widget(self._layer_stack.get_layer_by_index(i), i + 1)

        def _delete_layer_widget(layer: ImageLayer) -> None:
            layer_widget = self._layer_widget(layer)
            if layer_widget is not None:
                self._list_layout.removeWidget(layer_widget)
                layer_widget.setParent(None)
                self._layer_widgets.remove(layer_widget)
                self.update()
        self._layer_stack.layer_removed.connect(_delete_layer_widget)

        def _activate_layer(layer_id: Optional[int], _=None) -> None:
            for widget in self._layer_widgets:
                widget.active = layer_id == widget.layer.id
        self._layer_stack.active_layer_changed.connect(_activate_layer)
        if self._layer_stack.active_layer is not None:
            _activate_layer(self._layer_stack.active_layer.id)

        # BUTTON BAR:
        self._button_bar = QWidget()
        self._layout.addWidget(self._button_bar)
        self._button_bar_layout = QHBoxLayout(self._button_bar)

        def _create_button(text: str, tooltip: str, action: Callable[[], None]) -> QPushButton:
            button = QPushButton()
            button.setText(text)
            button.setToolTip(tooltip)
            button.clicked.connect(lambda: action())
            self._button_bar_layout.addWidget(button)
            return button

        self._add_button = _create_button(ADD_BUTTON_LABEL, ADD_BUTTON_TOOLTIP, self._layer_stack.create_layer)
        self._delete_button = _create_button(DELETE_BUTTON_LABEL, DELETE_BUTTON_TOOLTIP, self._layer_stack.remove_layer)
        self._move_up_button = _create_button(LAYER_UP_BUTTON_LABEL, LAYER_UP_BUTTON_TOOLTIP,
                                              lambda: self._layer_stack.move_layer(-1))
        self._move_up_button = _create_button(LAYER_DOWN_BUTTON_LABEL, LAYER_DOWN_BUTTON_TOOLTIP,
                                              lambda: self._layer_stack.move_layer(1))

        self._merge_down_button = _create_button(MERGE_DOWN_BUTTON_LABEL, MERGE_DOWN_BUTTON_TOOLTIP,
                                                 self._layer_stack.merge_layer_down)

    def _layer_widget(self, layer: ImageLayer) -> LayerItem:
        """Returns the layer widget for the given layer, or creates and returns a new one if none exists."""
        for widget in self._layer_widgets:
            if widget.layer == layer:
                return widget
        return LayerItem(layer, self._layer_stack, self)

    def sizeHint(self) -> QSize:
        """Returns a reasonable default size."""
        return DEFAULT_LIST_SIZE
