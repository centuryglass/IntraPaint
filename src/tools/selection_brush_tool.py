"""Selects image content for image generation or editing."""
from typing import Optional

from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QIcon, QColor, QMouseEvent
from PySide6.QtWidgets import QWidget, QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.config_entry import RangeKey
from src.config.key_config import KeyConfig
from src.image.brush.qt_paint_brush import QtPaintBrush
from src.image.layers.image_stack import ImageStack
from src.tools.brush_tool import BrushTool
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.brush_selection_panel import TOOL_MODE_DESELECT, BrushSelectionPanel
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.text_drawing_utils import left_button_hint_text, right_button_hint_text

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.selection_tool'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


LABEL_TEXT_SELECTION_TOOL = _tr('Selection Brush')
TOOLTIP_SELECTION_TOOL = _tr('Draw to select areas for editing or inpainting.')
CONTROL_HINT_SELECTION_TOOL = _tr('{left_mouse_icon}: select - {right_mouse_icon}: add/remove context pin -'
                                  ' {right_mouse_icon} drag: 1px select')

ICON_PATH_SELECTION_TOOL = f'{PROJECT_DIR}/resources/icons/tools/selection_icon.svg'
CURSOR_PATH_SELECTION_TOOL = f'{PROJECT_DIR}/resources/cursors/selection_cursor.svg'

# Screen distance a right-button press must move to draw a 1px line instead of toggling a context pin:
PIN_DRAG_THRESHOLD_PX = 4
# Screen distance from an existing pin within which a right-click removes that pin:
PIN_REMOVE_RADIUS_PX = 8


class SelectionBrushTool(BrushTool):
    """Selects image content for image generation or editing."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        brush = QtPaintBrush(None)
        super().__init__(KeyConfig.SELECTION_BRUSH_TOOL_KEY, LABEL_TEXT_SELECTION_TOOL, TOOLTIP_SELECTION_TOOL,
                         QIcon(ICON_PATH_SELECTION_TOOL), image_stack, image_viewer, brush, False, False)
        self._last_click = None
        self._control_panel = BrushSelectionPanel(image_stack.selection_layer, self)
        self._control_panel.tool_mode_changed.connect(self._tool_toggle_slot)
        self._active = False
        self._drawing = False
        self._cached_size: Optional[int] = None
        self._pin_press: Optional[tuple[QPoint, QPointF]] = None
        self.set_scaling_icon_cursor(self.load_cursor_icon(CURSOR_PATH_SELECTION_TOOL))

        # Setup brush, load size from config
        self.brush_color = QColor()

        def _update_color(color_str: str) -> None:
            if color_str == self.brush_color.name():
                return
            color = QColor(color_str)
            color.setAlphaF(1.0)
            self.brush_color = color
        _update_color(AppConfig().get(AppConfig.SELECTION_COLOR))
        AppConfig().connect(self, AppConfig.SELECTION_COLOR, _update_color)

        self.brush_size = Cache().get(Cache.SELECTION_BRUSH_SIZE)
        Cache().connect(self, Cache.SELECTION_BRUSH_SIZE, self.set_brush_size)
        self.layer = image_stack.selection_layer
        self.update_brush_cursor()

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        select_hint = CONTROL_HINT_SELECTION_TOOL.format(left_mouse_icon=left_button_hint_text(),
                                                         right_mouse_icon=right_button_hint_text())
        return f'{select_hint}<br/>{BrushTool.brush_control_hints()}<br/>{super().get_input_hint()}'

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns the selection control panel."""
        return self._control_panel

    def _tool_toggle_slot(self, selected_tool_label: str):
        """Switches the mask tool between draw and erase modes."""
        self._brush.eraser = selected_tool_label == TOOL_MODE_DESELECT

    def set_brush_size(self, new_size: int) -> None:
        """Update the brush size."""
        new_size = min(new_size, Cache().get(Cache.SELECTION_BRUSH_SIZE, RangeKey.MAX))
        super().set_brush_size(new_size)
        Cache().set(Cache.SELECTION_BRUSH_SIZE, max(1, new_size))

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Holds back right-button strokes until the pointer moves, so a right-click can toggle a context pin.

        With the line modifier held, the right button draws a line immediately, as BrushTool does.
        """
        self._pin_press = None
        if event is None or event.buttons() != Qt.MouseButton.RightButton \
                or KeyConfig.modifier_held(KeyConfig.LINE_MODIFIER) or not self._image_stack.has_image \
                or KeyConfig.modifier_held(KeyConfig.PAN_VIEW_MODIFIER, True) \
                or not self.validate_layer(self._layer, image_stack=self._image_stack):
            return super().mouse_click(event, image_coordinates)
        self._pin_press = (QPoint(image_coordinates), QPointF(event.position()))
        return True

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Starts the held-back 1px stroke from the press point once the pointer moves far enough."""
        if self._pin_press is not None and event is not None:
            press_point, press_position = self._pin_press
            if event.buttons() != Qt.MouseButton.RightButton:
                self._pin_press = None
                return False
            offset = event.position() - press_position
            if max(abs(offset.x()), abs(offset.y())) < PIN_DRAG_THRESHOLD_PX:
                return True
            self._pin_press = None
            super().mouse_click(event, press_point)
        return super().mouse_move(event, image_coordinates)

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Toggles a context pin when a right-click is released without moving."""
        if self._pin_press is not None:
            press_point = self._pin_press[0]
            self._pin_press = None
            self._toggle_context_pin(press_point)
            return True
        return super().mouse_release(event, image_coordinates)

    def _toggle_context_pin(self, image_point: QPoint) -> None:
        """Removes the context pin nearest a point if one is close on screen, or adds a pin there otherwise."""
        selection_layer = self._image_stack.selection_layer
        max_distance = PIN_REMOVE_RADIUS_PX / max(self._image_viewer.scene_scale, 0.001)
        nearby_pin = selection_layer.context_pin_near(QPointF(image_point) + QPointF(0.5, 0.5), max_distance)
        if nearby_pin is not None:
            selection_layer.remove_context_pin(nearby_pin)
        elif self._image_stack.bounds.contains(image_point):
            selection_layer.add_context_pin(image_point)

    def _on_deactivate(self) -> None:
        self._pin_press = None
        super()._on_deactivate()
