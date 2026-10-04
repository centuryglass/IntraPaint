"""Selects image content for image generation or editing."""
from dataclasses import dataclass
from enum import Enum
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
from src.ui.graphics_items.context_pin_item import marker_screen_bounds
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
CONTROL_HINT_SELECTION_TOOL = _tr('{left_mouse_icon}: select - {right_mouse_icon}: add, move or remove context pin')

ICON_PATH_SELECTION_TOOL = f'{PROJECT_DIR}/resources/icons/tools/selection_icon.svg'
CURSOR_PATH_SELECTION_TOOL = f'{PROJECT_DIR}/resources/cursors/selection_cursor.svg'

# Screen distance a right-button drag must move before releasing it keeps a grabbed pin instead of removing it:
PIN_DRAG_THRESHOLD_PX = 4
# Extra screen distance around a drawn pin marker where a right-click still removes that pin:
PIN_HIT_MARGIN_PX = 2


class PinDragState(Enum):
    """What a right-button drag with the selection brush is moving."""
    DRAGGING_EXISTING = 'existing'
    DRAGGING_NEW = 'new'


@dataclass
class _PinDrag:
    """An in-progress right-button context pin drag."""
    state: PinDragState
    initial_pins: list[QPoint]  # All pins before the drag, used for its undo step.
    initial_pin: QPoint  # The grabbed pin, or the pin the drag added.
    grab_offset: QPoint  # Offset from the pointer's pixel to the dragged pin's pixel.
    press_position: QPointF  # Press position in viewer widget coordinates.
    pin: Optional[QPoint] = None  # Current dragged pin position, or None while it's outside the image.
    moved: bool = False  # Whether the pointer has moved PIN_DRAG_THRESHOLD_PX from the press position.

    def other_pins(self) -> list[QPoint]:
        """Returns the pins from before the drag, minus the grabbed pin."""
        if self.state == PinDragState.DRAGGING_EXISTING:
            return [pin for pin in self.initial_pins if pin != self.initial_pin]
        return list(self.initial_pins)


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
        self._pin_drag: Optional[_PinDrag] = None
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
        """Starts a selection stroke on left-click, or a context pin drag on right-click.

        Right-clicking a pin's marker grabs that pin. Right-clicking anywhere else adds a pin there and grabs it.
        """
        if event is None or event.buttons() != Qt.MouseButton.RightButton:
            return super().mouse_click(event, image_coordinates)
        if self._pin_drag is not None:
            self._finish_pin_drag(False)
        if not self._image_stack.has_image or KeyConfig.modifier_held(KeyConfig.PAN_VIEW_MODIFIER, True):
            return False
        selection_layer = self._image_stack.selection_layer
        press_position = QPointF(event.position())
        grabbed_pin = self._context_pin_at(press_position)
        if grabbed_pin is not None:
            self._pin_drag = _PinDrag(PinDragState.DRAGGING_EXISTING, selection_layer.context_pins, grabbed_pin,
                                      grabbed_pin - image_coordinates, press_position)
        elif self._image_stack.bounds.contains(image_coordinates):
            self._pin_drag = _PinDrag(PinDragState.DRAGGING_NEW, selection_layer.context_pins, image_coordinates,
                                      QPoint(), press_position)
        else:
            return False
        self._update_dragged_pin(image_coordinates)
        return True

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Moves a dragged context pin with the pointer, hiding it while it's outside the image."""
        if self._pin_drag is None or event is None:
            return super().mouse_move(event, image_coordinates)
        if not event.buttons() & Qt.MouseButton.RightButton:
            # The release was missed, such as when it happened outside the window, so finish the drag here:
            self._finish_pin_drag(self._image_stack.bounds.contains(image_coordinates + self._pin_drag.grab_offset))
            return super().mouse_move(event, image_coordinates)
        offset = event.position() - self._pin_drag.press_position
        if max(abs(offset.x()), abs(offset.y())) >= PIN_DRAG_THRESHOLD_PX:
            self._pin_drag.moved = True
        self._update_dragged_pin(image_coordinates)
        return True

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Drops a dragged context pin, or removes a grabbed pin that was clicked without moving."""
        if self._pin_drag is None:
            return super().mouse_release(event, image_coordinates)
        self._update_dragged_pin(image_coordinates)
        self._finish_pin_drag(True)
        return True

    def _update_dragged_pin(self, image_coordinates: QPoint) -> None:
        """Moves the dragged pin to follow the pointer, or removes it while the pointer is outside the image."""
        assert self._pin_drag is not None
        pin_drag = self._pin_drag
        position = image_coordinates + pin_drag.grab_offset
        pin_drag.pin = position if self._image_stack.bounds.contains(position) else None
        other_pins = pin_drag.other_pins()
        self._image_stack.selection_layer.set_context_pins(
            other_pins if pin_drag.pin is None else [*other_pins, pin_drag.pin], False)

    def _finish_pin_drag(self, keep_dropped_pin: bool) -> None:
        """Ends a pin drag, recording its whole change as one undo step.

        The dragged pin is removed if keep_dropped_pin is false, if it was outside the image, or if an existing pin
        was clicked without moving.
        """
        assert self._pin_drag is not None
        pin_drag = self._pin_drag
        self._pin_drag = None
        selection_layer = self._image_stack.selection_layer
        clicked_existing = pin_drag.state == PinDragState.DRAGGING_EXISTING and not pin_drag.moved
        if not keep_dropped_pin or clicked_existing or pin_drag.pin is None:
            selection_layer.set_context_pins(pin_drag.other_pins(), False)
        selection_layer.record_context_pin_change(pin_drag.initial_pins)

    def _context_pin_at(self, widget_point: QPointF) -> Optional[QPoint]:
        """Returns the context pin whose drawn marker is under a point in the image viewer, preferring the closest."""
        marker_bounds = marker_screen_bounds(self._image_viewer.context_pin_marker_size).adjusted(
            -PIN_HIT_MARGIN_PX, -PIN_HIT_MARGIN_PX, PIN_HIT_MARGIN_PX, PIN_HIT_MARGIN_PX)
        closest: Optional[QPoint] = None
        closest_distance = 0.0
        for pin in self._image_stack.selection_layer.context_pins:
            offset = widget_point - QPointF(self._image_viewer.scene_point_to_widget(QPointF(pin) + QPointF(0.5, 0.5)))
            if not marker_bounds.contains(offset):
                continue
            distance = offset.x() ** 2 + offset.y() ** 2
            if closest is None or distance < closest_distance:
                closest = pin
                closest_distance = distance
        return closest

    def _on_deactivate(self) -> None:
        if self._pin_drag is not None:
            self._finish_pin_drag(True)
        super()._on_deactivate()
