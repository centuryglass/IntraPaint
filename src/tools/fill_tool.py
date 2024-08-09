"""Fill areas within an image."""
from typing import Optional

from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QIcon, QCursor, QMouseEvent, QKeySequence, QColor, QPainter, QTransform
from PySide6.QtWidgets import QWidget, QFormLayout, QApplication

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.tools.base_tool import BaseTool
from src.tools.brush_tool import COLOR_PICK_HINT
from src.ui.widget.brush_color_button import BrushColorButton
from src.util.image_utils import flood_fill, create_transparent_image
from src.util.shared_constants import PROJECT_DIR

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.fill_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


RESOURCES_FILL_ICON = f'{PROJECT_DIR}/resources/icons/tools/fill_icon.svg'
RESOURCES_FILL_CURSOR = f'{PROJECT_DIR}/resources/cursors/fill_cursor.svg'
CURSOR_SIZE = 50

FILL_LABEL = _tr('Color fill')
FILL_TOOLTIP = _tr('Fill areas with solid colors')
FILL_CONTROL_HINT = _tr('LMB:fill - ')
FILL_BUTTON_TOOLTIP = _tr('Set fill color')


class FillTool(BaseTool):
    """Lets the user fill image areas with solid colors."""

    def __init__(self, image_stack: ImageStack) -> None:
        super().__init__()
        cache = Cache()
        self._control_panel: Optional[QWidget] = None
        self._image_stack = image_stack
        self._icon = QIcon(RESOURCES_FILL_ICON)
        self._color = QColor(cache.get(Cache.LAST_BRUSH_COLOR))
        self._threshold = cache.get(Cache.FILL_THRESHOLD)
        self._sample_merged = cache.get(Cache.SAMPLE_MERGED)
        cursor_icon = QIcon(RESOURCES_FILL_CURSOR)
        self.cursor = QCursor(cursor_icon.pixmap(CURSOR_SIZE, CURSOR_SIZE), 0, CURSOR_SIZE)
        cache.connect(self, Cache.LAST_BRUSH_COLOR, self._update_color)
        cache.connect(self, Cache.FILL_THRESHOLD, self._update_threshold)
        cache.connect(self, Cache.SAMPLE_MERGED, self._update_sample_merged)

        self._layer = image_stack.active_layer
        self._layer.lock_changed.connect(self._layer_lock_change_slot)
        image_stack.active_layer_changed.connect(self._active_layer_change_slot)
        self._layer_lock_change_slot(self._layer, self._layer.locked)

    def get_hotkey(self) -> QKeySequence:
        """Returns the hotkey(s) that should activate this tool."""
        return KeyConfig().get_keycodes(KeyConfig.FILL_TOOL_KEY)

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        return FILL_LABEL

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        return FILL_TOOLTIP

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        return (f'{FILL_CONTROL_HINT}{BaseTool.modifier_hint(KeyConfig.EYEDROPPER_TOOL_KEY, COLOR_PICK_HINT)}'
                f'{super().get_input_hint()}')

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a panel providing controls for customizing tool behavior, or None if no such panel is needed."""
        if self._control_panel is not None:
            return self._control_panel
        cache = Cache()
        self._control_panel = QWidget()
        layout = QFormLayout(self._control_panel)
        color_button = BrushColorButton()
        layout.addRow(color_button)
        threshold_slider = cache.get_control_widget(Cache.FILL_THRESHOLD)
        layout.addRow(cache.get_label(Cache.FILL_THRESHOLD), threshold_slider)
        sample_merged_checkbox = cache.get_control_widget(Cache.SAMPLE_MERGED)
        layout.addRow(sample_merged_checkbox)
        selection_only_checkbox = cache.get_control_widget(Cache.PAINT_SELECTION_ONLY)
        layout.addRow(selection_only_checkbox)
        return self._control_panel

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Copy the color under the mouse on left-click."""
        assert event is not None
        if event.buttons() == Qt.MouseButton.LeftButton:
            layer = self._layer
            if not isinstance(layer, ImageLayer) or layer.locked:
                return False
            layer_point = layer.map_from_image(image_coordinates)
            if not layer.bounds.contains(layer_point):
                return True
            if self._sample_merged:
                merged_image_bounds = self._image_stack.merged_layer_bounds
                full_image = self._image_stack.qimage(crop_to_image=False)
                projected_image_content = create_transparent_image(layer.size)
                painter = QPainter(projected_image_content)
                transform = QTransform.fromTranslate(merged_image_bounds.x(),
                                                     merged_image_bounds.y()) * layer.transform.inverted()[0]
                painter.setTransform(transform)
                painter.drawImage(0, 0, full_image)
                painter.end()
                fill_image = projected_image_content
                layer_image = layer.image
            else:
                fill_image = layer.image
                layer_image = fill_image
            mask = flood_fill(fill_image, layer_point, self._color, self._threshold, False)
            assert mask is not None
            if Cache().get(Cache.PAINT_SELECTION_ONLY):
                selection_mask = self._image_stack.get_layer_mask(layer)
                mask_painter = QPainter(mask)
                mask_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
                mask_painter.drawImage(0, 0, selection_mask)
                mask_painter.end()
            painter = QPainter(layer_image)
            painter.drawImage(QRect(QPoint(), layer.size), mask)

            painter.end()
            layer.image = layer_image
            return True
        return False

    def _active_layer_change_slot(self, active_layer: Layer) -> None:
        if self._layer != active_layer:
            self._layer.lock_changed.disconnect(self._layer_lock_change_slot)
            active_layer.lock_changed.connect(self._layer_lock_change_slot)
            self._layer = active_layer
            self._layer_lock_change_slot(self._layer, self._layer.locked)

    def _layer_lock_change_slot(self, layer: Layer, locked: bool) -> None:
        if self._control_panel is not None:
            self._control_panel.setEnabled(isinstance(layer, ImageLayer) and not locked)

    def _update_color(self, color_str: str) -> None:
        self._color = QColor(color_str)

    def _update_threshold(self, threshold: float) -> None:
        self._threshold = threshold

    def _update_sample_merged(self, sample_merged: bool) -> None:
        self._sample_merged = sample_merged
