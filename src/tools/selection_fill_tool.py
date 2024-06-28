"""Fill areas within an image."""
from typing import Optional

from PyQt5.QtCore import Qt, QPoint, QRect
from PyQt5.QtGui import QIcon, QCursor, QMouseEvent, QKeySequence, QColor, QPainter
from PyQt5.QtWidgets import QWidget, QFormLayout, QApplication

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layer_stack import LayerStack
from src.tools.base_tool import BaseTool
from src.ui.input_fields.check_box import CheckBox
from src.ui.input_fields.slider_spinbox import FloatSliderSpinbox
from src.ui.widget.brush_color_button import BrushColorButton
from src.util.image_utils import flood_fill

RESOURCES_FILL_ICON = 'resources/icons/selection_fill_icon.svg'
RESOURCES_FILL_CURSOR = 'resources/cursors/selection_fill_cursor.svg'
CURSOR_SIZE = 25

SELECTION_FILL_LABEL = 'Selection fill'
SELECTION_FILL_TOOLTIP = "Select areas with solid colors"
SELECTION_FILL_CONTROL_HINT = "LMB:select - RMB:deselect -"

class SelectionFillTool(BaseTool):
    """Lets the user select image areas with solid colors."""

    def __init__(self, layer_stack: LayerStack) -> None:
        super().__init__()
        cache = Cache.instance()
        self._layer_stack = layer_stack
        self._control_panel: Optional[QWidget] = None
        self._icon = QIcon(RESOURCES_FILL_ICON)
        self._color = QColor(Qt.red)
        self._threshold = cache.get(Cache.FILL_THRESHOLD)
        self._sample_merged = cache.get(Cache.SAMPLE_MERGED)
        cursor_icon = QIcon(RESOURCES_FILL_CURSOR)
        self.cursor = QCursor(cursor_icon.pixmap(CURSOR_SIZE, CURSOR_SIZE))
        cache.connect(self, Cache.FILL_THRESHOLD, self._update_threshold)
        cache.connect(self, Cache.SAMPLE_MERGED, self._update_sample_merged)

    def get_hotkey(self) -> QKeySequence:
        """Returns the hotkey(s) that should activate this tool."""
        return KeyConfig.instance().get_keycodes(KeyConfig.SELECTION_FILL_TOOL_KEY)

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        return SELECTION_FILL_LABEL

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        return SELECTION_FILL_TOOLTIP

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        return f'{SELECTION_FILL_CONTROL_HINT} {super().get_input_hint()}'

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a panel providing controls for customizing tool behavior, or None if no such panel is needed."""
        if self._control_panel is not None:
            return self._control_panel
        cache = Cache.instance()
        self._control_panel = QWidget()
        layout = QFormLayout(self._control_panel)
        threshold_slider = cache.get_control_widget(Cache.FILL_THRESHOLD)
        layout.addRow(cache.get_label(Cache.FILL_THRESHOLD), threshold_slider)
        sample_merged_checkbox = cache.get_control_widget(Cache.SAMPLE_MERGED)
        layout.addRow(sample_merged_checkbox)
        return self._control_panel

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Copy the color under the mouse on left-click."""
        assert event is not None
        if QApplication.keyboardModifiers() != Qt.KeyboardModifier.NoModifier:
            return True
        if event.buttons() == Qt.LeftButton or event.buttons() == Qt.RightButton:
            clear_mode = event.buttons() == Qt.RightButton
            layer = self._layer_stack.active_layer
            if layer is None:
                return False
            if not layer.geometry.contains(image_coordinates):
                return True
            if self._sample_merged:
                image = self._layer_stack.qimage(crop_to_bounds=False)
                layer_bounds = self._layer_stack.merged_layer_geometry.intersected(layer.geometry)
                image = image.copy(layer_bounds)
                selection_image = self._layer_stack.selection_layer.qimage
            else:
                image = layer.qimage
                selection_image = self._layer_stack.selection_layer.qimage
            mask = flood_fill(image, image_coordinates - layer.position, self._color, self._threshold, False)
            painter = QPainter(selection_image)
            if clear_mode:
                painter.setCompositionMode(QPainter.CompositionMode_DestinationOut)
            painter.drawImage(QRect(QPoint(), layer.size), mask)
            painter.end()
            self._layer_stack.selection_layer.set_image(selection_image)
            return True
        return False

    def _update_threshold(self, threshold: float) -> None:
        self._threshold = threshold

    def _update_sample_merged(self, sample_merged: bool) -> None:
        self._sample_merged = sample_merged
