"""Fill areas within an image."""
from typing import Optional

from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QIcon, QCursor, QMouseEvent, QColor, QPainter, QTransform, QBrush
from PySide6.QtWidgets import QWidget, QApplication

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.tools.base_tool import BaseTool
from src.ui.input_fields.fill_style_combo_box import FillStyleComboBox
from src.ui.panel.tool_control_panels.fill_tool_panel import FillToolPanel
from src.util.shared_constants import PROJECT_DIR, COLOR_PICK_HINT
from src.util.visual.image_utils import flood_fill, create_transparent_image
from src.util.visual.text_drawing_utils import left_button_hint_text

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.fill_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


ICON_PATH_FILL_TOOL = f'{PROJECT_DIR}/resources/icons/tools/fill_icon.svg'
CURSOR_PATH_FILL_TOOL = f'{PROJECT_DIR}/resources/cursors/fill_cursor.svg'
CURSOR_SIZE = 50

FILL_LABEL = _tr('Color fill')
FILL_TOOLTIP = _tr('Fill areas with solid colors')
FILL_CONTROL_HINT = _tr('{left_mouse_icon}: fill')


class FillTool(BaseTool):
    """Lets the user fill image areas with solid colors."""

    def __init__(self, image_stack: ImageStack) -> None:
        super().__init__(KeyConfig.FILL_TOOL_KEY, FILL_LABEL, FILL_TOOLTIP, QIcon(ICON_PATH_FILL_TOOL))
        cache = Cache()
        self._control_panel: Optional[FillToolPanel] = None
        self._image_stack = image_stack
        self._color = cache.get_color(Cache.LAST_BRUSH_COLOR, Qt.GlobalColor.black)
        self._threshold = cache.get(Cache.FILL_THRESHOLD)
        self._sample_merged = cache.get(Cache.SAMPLE_MERGED)
        cursor_icon = QIcon(CURSOR_PATH_FILL_TOOL)
        self.cursor = QCursor(cursor_icon.pixmap(CURSOR_SIZE, CURSOR_SIZE), 0, CURSOR_SIZE)
        cache.connect(self, Cache.LAST_BRUSH_COLOR, self._update_color)
        cache.connect(self, Cache.FILL_THRESHOLD, self._update_threshold)
        cache.connect(self, Cache.SAMPLE_MERGED, self._update_sample_merged)

        self._layer = image_stack.active_layer
        self._layer.lock_changed.connect(self._layer_lock_change_slot)
        image_stack.active_layer_changed.connect(self._active_layer_change_slot)
        self._layer_lock_change_slot(self._layer, self._layer.locked or self._layer.parent_locked)

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        fill_hint = FILL_CONTROL_HINT.format(left_mouse_icon=left_button_hint_text())
        eyedropper_hint = BaseTool.modifier_hint(KeyConfig.EYEDROPPER_OVERRIDE_MODIFIER, COLOR_PICK_HINT)
        if len(eyedropper_hint) > 0:
            eyedropper_hint = ' - ' + eyedropper_hint
        return f'{fill_hint}{eyedropper_hint}<br/>{super().get_input_hint()}'

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a panel providing controls for customizing tool behavior, or None if no such panel is needed."""
        if self._control_panel is None:
            self._control_panel = FillToolPanel()
        return self._control_panel

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Copy the color under the mouse on left-click."""
        assert event is not None
        if event.buttons() == Qt.MouseButton.LeftButton:
            layer = self._layer
            if not self.validate_layer(layer, image_stack=self._image_stack):
                return False
            assert isinstance(layer, ImageLayer)
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
            fill_pattern = Cache().get(Cache.FILL_TOOL_BRUSH_PATTERN)
            fill_brush = QBrush()
            try:
                fill_brush.setStyle(FillStyleComboBox.get_style(fill_pattern))
            except KeyError:
                fill_brush.setStyle(Qt.BrushStyle.SolidPattern)
            selection_only = Cache().get(Cache.PAINT_SELECTION_ONLY)
            if selection_only or fill_brush.style() != Qt.BrushStyle.SolidPattern:
                mask_painter = QPainter(mask)
                mask_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
                if selection_only:
                    selection_mask = self._image_stack.get_layer_selection_mask(layer)
                    mask_painter.drawImage(0, 0, selection_mask)
                if fill_brush.style() != Qt.BrushStyle.SolidPattern:
                    fill_brush.setColor(self._color)
                    mask_painter.fillRect(QRect(QPoint(), mask.size()), fill_brush)
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
            self._layer_lock_change_slot(self._layer, self._layer.locked or self._layer.parent_locked)

    def _layer_lock_change_slot(self, layer: Layer, locked: bool) -> None:
        assert layer == self._layer or layer.contains_recursive(self._layer)
        should_enable = isinstance(self._layer, ImageLayer) and not locked
        if self._control_panel is not None:
            self._control_panel.setEnabled(should_enable)
        self.set_disabled_cursor(not should_enable)

    def _update_color(self, color_str: str) -> None:
        self._color = QColor(color_str)

    def _update_threshold(self, threshold: float) -> None:
        self._threshold = threshold

    def _update_sample_merged(self, sample_merged: bool) -> None:
        self._sample_merged = sample_merged
