"""Base for tools that drag out a rectangle, ellipse or other shape, and act on it when the drag ends."""
from typing import Optional

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QIcon, QMouseEvent, QCursor, QPolygonF

from src.config.key_config import KeyConfig
from src.tools.base_tool import BaseTool
from src.ui.graphics_items.click_and_drag_selection import ClickAndDragSelection
from src.ui.image_viewer import ImageViewer


class ShapeDragTool(BaseTool):
    """Base for tools that drag out a rectangle, ellipse or other shape, and act on it when the drag ends.

    A left-button drag draws the shape with `_selection_handler`. Subclasses override `_can_start_drag` and
    `_prepare_drag` to check and set up a drag at the press, and `_finish_drag` to act on the finished shape.
    """

    def __init__(self, activation_config_key: str, label_text: str, tooltip_text: str, icon: QIcon,
                 image_viewer: ImageViewer) -> None:
        super().__init__(activation_config_key, label_text, tooltip_text, icon)
        self.cursor = QCursor(Qt.CursorShape.CrossCursor)
        scene = image_viewer.scene()
        assert scene is not None
        self._scene = scene
        self._selection_handler = ClickAndDragSelection(scene)
        self._dragging = False

    def _can_start_drag(self) -> bool:
        """Returns whether a left-button press may start a drag."""
        return True

    def _prepare_drag(self) -> None:
        """Called at the press that starts a drag, before the shape starts."""

    def _finish_drag(self, shape: QPolygonF) -> None:
        """Acts on a finished drag's shape, in image coordinates."""

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Starts a drag on left-click."""
        assert event is not None
        if KeyConfig.modifier_held(KeyConfig.PAN_VIEW_MODIFIER, True) \
                or event.buttons() != Qt.MouseButton.LeftButton or not self._can_start_drag():
            return False
        self._prepare_drag()
        self._selection_handler.start_selection(image_coordinates)
        self._dragging = True
        return True

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Continues the drag while the left button is held, or finishes it if a release was missed."""
        assert event is not None
        if not self._dragging:
            return False
        if event.buttons() == Qt.MouseButton.LeftButton:
            self._selection_handler.drag_to(image_coordinates)
        else:
            self._end_drag(image_coordinates)
        return True

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Finishes the drag."""
        if not self._dragging:
            return False
        self._end_drag(image_coordinates)
        return True

    def _end_drag(self, image_coordinates: QPoint) -> None:
        assert self._dragging and self._selection_handler.selecting
        self._dragging = False
        self._finish_drag(self._selection_handler.end_selection(image_coordinates))

    def _cancel_drag(self) -> None:
        """Discards any drag in progress without acting on it."""
        if self._selection_handler.selecting:
            self._selection_handler.end_selection(QPoint())
        self._dragging = False

    def _on_deactivate(self) -> None:
        self._cancel_drag()
