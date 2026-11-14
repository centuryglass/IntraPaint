"""Brush size drag gesture shared by the brush tools: the size drag modifier plus a right-button drag sets the brush
size.

The brush outline stays at the press point while the drag sets its radius to the pointer's distance from that point,
in image pixels. Release keeps the new size, and `cancel` restores the size from before the drag. Brush size is config,
so the drag records no undo step.
"""
import math
from typing import Optional

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QMouseEvent

from src.config.key_config import KeyConfig
from src.ui.image_viewer import ImageViewer


class BrushSizeDragger:
    """Tracks right-button drags with `KeyConfig.BRUSH_SIZE_DRAG_MODIFIER` held, and the brush size they set.

    A tool calls `press`, `move` and `release` from its mouse handlers before handling the event any other way, and
    returns True when they return True. After each call that returns True it applies `size` if that is not None, through
    the tool's own size setter so the tool's range applies. It calls `cancel` on Escape and when it deactivates, and
    applies the size `cancel` returns.
    """

    def __init__(self, image_viewer: ImageViewer) -> None:
        self._image_viewer = image_viewer
        self._anchor: Optional[QPointF] = None  # Press point in scene coordinates, set while a drag is in progress.
        self._initial_size = 0
        self._size: Optional[int] = None

    @property
    def dragging(self) -> bool:
        """Returns whether a size drag is in progress."""
        return self._anchor is not None

    @property
    def anchor(self) -> Optional[QPointF]:
        """Returns the drag's press point in scene coordinates, or None if no drag is in progress."""
        return self._anchor

    @property
    def size(self) -> Optional[int]:
        """Returns the size the drag has set, unclamped, or None if the pointer has not moved since the press."""
        return self._size

    def press(self, event: Optional[QMouseEvent], current_size: int) -> bool:
        """Starts a drag if the right button was pressed with the size drag modifier held. Returns whether the press
           belongs to a drag.

        Any press during a drag, such as a pen touching down while its side button is held, is consumed so it can't
        paint.
        """
        if event is None:
            return False
        if self._anchor is not None:
            return True
        if event.button() != Qt.MouseButton.RightButton \
                or not KeyConfig.modifier_held(KeyConfig.BRUSH_SIZE_DRAG_MODIFIER, held_modifiers=event.modifiers()):
            return False
        self._anchor = self._image_viewer.widget_point_to_scene(event.position().toPoint())
        self._initial_size = current_size
        self._size = None
        return True

    def move(self, event: Optional[QMouseEvent]) -> bool:
        """Sets `size` from the pointer's distance to the press point. Returns whether the move belongs to a drag.

        If the right button is no longer down, the release was missed, so the drag ends here keeping the size it set.
        """
        if self._anchor is None or event is None:
            return False
        if not event.buttons() & Qt.MouseButton.RightButton:
            self._anchor = None
            self._size = None
            return False
        self._update_size(event)
        return True

    def release(self, event: Optional[QMouseEvent]) -> bool:
        """Ends the drag on a right-button release, keeping the size it set. Returns whether the release belongs to a
           drag.

        Releasing any other button during the drag is consumed and leaves the drag running.
        """
        if self._anchor is None or event is None:
            return False
        if event.button() == Qt.MouseButton.RightButton:
            self._update_size(event)
            self._anchor = None
        return True

    def cancel(self) -> Optional[int]:
        """Ends the drag, returning the size from before it to restore, or None if no drag was in progress."""
        if self._anchor is None:
            return None
        self._anchor = None
        self._size = None
        return self._initial_size

    def _update_size(self, event: QMouseEvent) -> None:
        assert self._anchor is not None
        pointer = self._image_viewer.widget_point_to_scene(event.position().toPoint())
        radius = math.hypot(pointer.x() - self._anchor.x(), pointer.y() - self._anchor.y())
        self._size = max(1, round(radius * 2))
