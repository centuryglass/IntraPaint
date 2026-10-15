"""Right-button context pin editing, shared by the selection tools and the navigation panel.

A right-button press grabs the pin under the pointer or adds one. Dragging moves it, releasing outside the image
deletes it, and releasing a grabbed pin without having moved it deletes it. Each drag is one undo step.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QMouseEvent

from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.ui.graphics_items.context_pin_item import marker_screen_bounds
from src.ui.image_viewer import ImageViewer

# Screen distance a drag must move before releasing it keeps a grabbed pin instead of removing it:
PIN_DRAG_THRESHOLD_PX = 4
# Extra screen distance around a drawn pin marker where a right-click still grabs that pin:
PIN_HIT_MARGIN_PX = 2


class PinDragState(Enum):
    """What a pin drag is moving."""
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


class ContextPinDragger:
    """Edits the selection layer's context pins from right-button mouse events in one image viewer.

    A tool calls `press`, `move` and `release` from its mouse handlers and returns True when they return True, and
    calls `finish` when it deactivates.
    """

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        self._image_stack = image_stack
        self._image_viewer = image_viewer
        self._pin_drag: Optional[_PinDrag] = None

    @property
    def dragging(self) -> bool:
        """Returns whether a pin drag is in progress."""
        return self._pin_drag is not None

    def press(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Starts a drag if the right button alone was pressed without the pan modifier. Returns whether one started.

        Pressing a pin's marker grabs that pin. Pressing anywhere else in the image adds a pin there and grabs it.
        """
        if event is None or event.buttons() != Qt.MouseButton.RightButton:
            return False
        if self._pin_drag is not None:
            self._finish_drag(False)
        if not self._image_stack.has_image or KeyConfig.modifier_held(KeyConfig.PAN_VIEW_MODIFIER, True):
            return False
        selection_layer = self._image_stack.selection_layer
        press_position = QPointF(event.position())
        grabbed_pin = self._pin_at(press_position)
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

    def move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Moves the dragged pin with the pointer, hiding it while the pointer is outside the image.

        Returns whether the move belongs to the drag. If the right button is no longer down, the release was missed,
        so the drag ends here and the move is not consumed.
        """
        if self._pin_drag is None or event is None:
            return False
        if not event.buttons() & Qt.MouseButton.RightButton:
            self._finish_drag(self._image_stack.bounds.contains(image_coordinates + self._pin_drag.grab_offset))
            return False
        offset = event.position() - self._pin_drag.press_position
        if max(abs(offset.x()), abs(offset.y())) >= PIN_DRAG_THRESHOLD_PX:
            self._pin_drag.moved = True
        self._update_dragged_pin(image_coordinates)
        return True

    def release(self, image_coordinates: QPoint) -> bool:
        """Drops the dragged pin, or removes a grabbed pin that was not moved. Returns whether a drag ended."""
        if self._pin_drag is None:
            return False
        self._update_dragged_pin(image_coordinates)
        self._finish_drag(True)
        return True

    def finish(self) -> None:
        """Drops the dragged pin where it is, if a drag is in progress."""
        if self._pin_drag is not None:
            self._finish_drag(True)

    def _update_dragged_pin(self, image_coordinates: QPoint) -> None:
        """Moves the dragged pin to follow the pointer, or removes it while the pointer is outside the image."""
        assert self._pin_drag is not None
        pin_drag = self._pin_drag
        position = image_coordinates + pin_drag.grab_offset
        pin_drag.pin = position if self._image_stack.bounds.contains(position) else None
        other_pins = pin_drag.other_pins()
        self._image_stack.selection_layer.set_context_pins(
            other_pins if pin_drag.pin is None else [*other_pins, pin_drag.pin], False)

    def _finish_drag(self, keep_dropped_pin: bool) -> None:
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

    def _pin_at(self, widget_point: QPointF) -> Optional[QPoint]:
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
