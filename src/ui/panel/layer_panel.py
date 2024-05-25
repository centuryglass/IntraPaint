"""Shows image layers, and allows the user to manipulate them."""

from typing import Optional, List
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QScrollArea, QSizePolicy
from PyQt5.QtGui import QPainter, QColor, QPaintEvent, QMouseEvent
from PyQt5.QtCore import Qt, QRect, QSize
from PyQt5.QtSvg import QSvgWidget
from src.image.image_layer import ImageLayer
from src.image.layer_stack import LayerStack
from src.ui.util.get_scaled_placement import get_scaled_placement
from src.ui.util.contrast_color import LUMINANCE_THRESHOLD, relative_luminance

LIST_SPACING = 4
DEFAULT_LIST_ITEM_SIZE = QSize(350, 100)
DEFAULT_LIST_SIZE = QSize(380, 600)
ICON_PATH_VISIBLE_LAYER = 'resources/visible.svg'
ICON_PATH_HIDDEN_LAYER = 'resources/hidden.svg'

WINDOW_TITLE = 'Image Layers'


class LayerItem(QWidget):
    """A single layer's representation in the list"""

    def __init__(self, layer: ImageLayer, parent: QWidget) -> None:
        super().__init__(parent)
        self._layer = layer
        self._layout = QHBoxLayout(self)
        self._layout.addStretch(50)
        self._layout.addSpacing(50)
        self._label = QLabel(layer.name, self)
        self._layout.addWidget(self._label, stretch=40)
        self._layer.content_changed.connect(self.update)
        self._layer.visibility_changed.connect(self.update)
        self.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding))
        palette = self.palette()
        bg_color = palette.color(self.backgroundRole())
        luminance = relative_luminance(bg_color)
        if luminance < LUMINANCE_THRESHOLD:
            bg_color = bg_color.lighter()
        else:
            bg_color = bg_color.darker()
        palette.setColor(self.backgroundRole(), bg_color)
        self.setAutoFillBackground(True)
        self.setPalette(palette)

        def get_layer_visibility_icon_path(layer):
            return ICON_PATH_VISIBLE_LAYER if layer.visible else ICON_PATH_HIDDEN_LAYER

        class VisibilityButton(QSvgWidget):
            """Show/hide layer button."""

            def __init__(self, layer) -> None:
                """Connect to the layer and load the initial icon."""
                super().__init__()
                self._layer = layer
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

    def paintEvent(self, unused_event: Optional[QPaintEvent]) -> None:
        """Draws the scaled layer contents to the widget."""
        pixmap = self._layer.pixmap
        pixmap_bounds = QRect(0, 0, self._label.x(), self.height())
        pixmap_bounds = get_scaled_placement(pixmap_bounds, pixmap.size(), 2)
        pixmap_bounds.moveLeft(LIST_SPACING)
        painter = QPainter(self)
        painter.drawPixmap(pixmap_bounds, pixmap)
        if not self._layer.visible:
            painter.fillRect(pixmap_bounds, QColor.fromRgb(0, 0, 0, 100))

    def sizeHint(self) -> QSize:
        """Returns a reasonable default size."""
        return DEFAULT_LIST_ITEM_SIZE

    @property
    def layer(self) -> ImageLayer:
        """Return the connected layer."""
        return self._layer


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

        # Build the scrolling layer list:
        self._layer_list = QWidget(self)
        self._scroll_area = QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setWidget(self._layer_list)
        self._list_layout = QVBoxLayout(self._layer_list)
        self._list_layout.setSpacing(LIST_SPACING)
        self._layout.addWidget(self._layer_list)

        def add_layer(layer: ImageLayer, layer_idx: int) -> None:
            """Add a layer to the list"""
            widget = self._layer_widget(layer)
            self._list_layout.insertWidget(layer_idx, widget)

        self._layer_stack.layer_added.connect(add_layer)
        for i in range(self._layer_stack.count()):
            add_layer(self._layer_stack.get_layer(i), i)

    @property
    def _layer_widgets(self) -> List[LayerItem]:
        """Returns all layer widgets in order."""
        items = [self._list_layout.children()[i] for i in reversed(range(self._list_layout.count()))]
        return [item.widget() for item in items if isinstance(item.widget(), ImageLayer)]

    def _layer_widget(self, layer: ImageLayer) -> LayerItem:
        """Returns the layer widget for the given layer, or creates and returns a new one if none exists."""
        for widget in self._layer_widgets:
            if widget.layer == layer:
                return widget
        return LayerItem(layer, self)

    def sizeHint(self) -> QSize:
        """Returns a reasonable default size."""
        return DEFAULT_LIST_SIZE
