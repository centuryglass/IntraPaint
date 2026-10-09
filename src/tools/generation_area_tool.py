"""An image editing tool that moves the selected editing region."""

from typing import Optional, cast

from PySide6.QtCore import Qt, QRect, QPoint, QSize, QPointF
from PySide6.QtGui import QMouseEvent, QKeyEvent, QCursor, QIcon
from PySide6.QtWidgets import QWidget, QApplication

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.controller.generation_area_controller import record_generation_area_size
from src.image.layers.image_stack import ImageStack
from src.tools.base_tool import BaseTool
from src.ui.graphics_items.area_resize_handle import AreaResizeHandle
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.generation_area_tool_panel import GenerationAreaToolPanel
from src.util.generation_area_utils import area_handle_positions, resize_area_from_handle, CORNER_HANDLES, \
    EDGE_HANDLES, HANDLE_TOP_LEFT, HANDLE_BOTTOM_RIGHT, HANDLE_TOP_RIGHT, HANDLE_BOTTOM_LEFT, HANDLE_LEFT, \
    HANDLE_RIGHT, HANDLE_TOP, HANDLE_BOTTOM
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.geometry_utils import closest_point_keeping_aspect_ratio
from src.util.visual.text_drawing_utils import left_button_hint_text, right_button_hint_text

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.generation_area_tool'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


ICON_PATH_GEN_AREA_TOOL = f'{PROJECT_DIR}/resources/icons/tools/gen_area_icon.svg'
GENERATION_AREA_LABEL = _tr('Set Image Generation Area')
GENERATION_AREA_TOOLTIP = _tr('Select an image region for AI image generation')
GEN_AREA_CONTROL_HINT = _tr('{left_mouse_icon}: move area - {right_mouse_icon}: resize area')
GEN_AREA_HANDLE_CONTROL_HINT = _tr('{left_mouse_icon}: move area, or drag a handle to resize - {right_mouse_icon}: '
                                   'resize area')
GEN_AREA_HANDLE_ASPECT_HINT = _tr('{modifier_or_modifiers}: free aspect ratio on corner handles, fixed aspect ratio '
                                  'with {right_mouse_icon}')

# Pointer distance in screen pixels within which a press grabs a resize handle:
HANDLE_GRAB_RADIUS = 8
# Z-value for resize handles, above the generation area outline and the image layers:
HANDLE_Z_VALUE = 100

_HANDLE_CURSOR_SHAPES = {
    HANDLE_TOP_LEFT: Qt.CursorShape.SizeFDiagCursor,
    HANDLE_BOTTOM_RIGHT: Qt.CursorShape.SizeFDiagCursor,
    HANDLE_TOP_RIGHT: Qt.CursorShape.SizeBDiagCursor,
    HANDLE_BOTTOM_LEFT: Qt.CursorShape.SizeBDiagCursor,
    HANDLE_LEFT: Qt.CursorShape.SizeHorCursor,
    HANDLE_RIGHT: Qt.CursorShape.SizeHorCursor,
    HANDLE_TOP: Qt.CursorShape.SizeVerCursor,
    HANDLE_BOTTOM: Qt.CursorShape.SizeVerCursor
}


class GenerationAreaTool(BaseTool):
    """An image editing tool that moves and resizes the image generation area.

    Left-dragging inside the area moves it by the pointer's offset, and left-pressing outside centers it on the
    pointer before dragging from there. With `show_handles`, eight resize handles on the area's outline resize it.
    Corner handles keep the area's aspect ratio unless the fixed aspect modifier is held. Right-dragging resizes with
    the top left corner fixed, keeping the generation resolution's aspect ratio while the modifier is held. Each
    left-drag starts a new undo step.
    """

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer, show_handles: bool = True) -> None:
        super().__init__(KeyConfig.GENERATION_AREA_TOOL_KEY, GENERATION_AREA_LABEL, GENERATION_AREA_TOOLTIP,
                         QIcon(ICON_PATH_GEN_AREA_TOOL))
        self._image_stack = image_stack
        self._image_viewer = image_viewer
        self._resizing = False
        self._default_cursor = QCursor(Qt.CursorShape.CrossCursor)
        self._cursor_shape = self._default_cursor.shape()
        self.cursor = self._default_cursor
        self._control_panel = GenerationAreaToolPanel(image_stack)

        # Left-drag state: the area's top left corner minus the pointer while moving, or the handle and the handle's
        # offset from the pointer while resizing.
        self._move_offset: Optional[QPoint] = None
        self._drag_handle: Optional[str] = None
        self._handle_offset = QPointF()
        self._drag_start_area = QRect()
        self._drag_changed_area = False

        self._handles: dict[str, AreaResizeHandle] = {}
        if show_handles:
            scene = image_viewer.scene()
            assert scene is not None
            for handle_id in (*CORNER_HANDLES, *EDGE_HANDLES):
                handle = AreaResizeHandle()
                handle.setZValue(HANDLE_Z_VALUE)
                handle.setVisible(False)
                scene.addItem(handle)
                self._handles[handle_id] = handle
            image_stack.generation_area_bounds_changed.connect(self._update_handle_positions)
            self._update_handle_positions()

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        if len(self._handles) > 0:
            gen_area_hint = GEN_AREA_HANDLE_CONTROL_HINT.format(left_mouse_icon=left_button_hint_text(),
                                                                right_mouse_icon=right_button_hint_text())
            aspect_hint = BaseTool.modifier_hint(KeyConfig.FIXED_ASPECT_MODIFIER, GEN_AREA_HANDLE_ASPECT_HINT
                                                 .replace('{right_mouse_icon}', right_button_hint_text()))
        else:
            gen_area_hint = GEN_AREA_CONTROL_HINT.format(left_mouse_icon=left_button_hint_text(),
                                                         right_mouse_icon=right_button_hint_text())
            aspect_hint = BaseTool.fixed_aspect_hint()
        return f'{gen_area_hint}<br/>{aspect_hint}<br/>{super().get_input_hint()}'

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a panel providing controls for customizing tool behavior, or None if no such panel is needed."""
        return self._control_panel

    def _on_activate(self, restoring_after_delegation=False) -> None:
        for handle in self._handles.values():
            handle.setVisible(True)

    def _on_deactivate(self) -> None:
        self._end_left_drag()
        for handle in self._handles.values():
            handle.setVisible(False)
        self._set_cursor_shape(self._default_cursor.shape())

    def _update_handle_positions(self, *_args) -> None:
        positions = area_handle_positions(self._image_stack.generation_area)
        for handle_id, handle in self._handles.items():
            handle.move_center(positions[handle_id])

    def _handle_at(self, event: QMouseEvent) -> Optional[str]:
        """Returns the id of the resize handle under the pointer, preferring corners, or None if there isn't one."""
        if len(self._handles) == 0 or not self.is_active:
            return None
        scene_point = self._image_viewer.widget_point_to_scene(event.position())
        radius = HANDLE_GRAB_RADIUS / self._image_viewer.scene_scale
        positions = area_handle_positions(self._image_stack.generation_area)
        for handle_id in (*CORNER_HANDLES, *EDGE_HANDLES):
            handle_pos = positions[handle_id]
            if abs(handle_pos.x() - scene_point.x()) <= radius and abs(handle_pos.y() - scene_point.y()) <= radius:
                return handle_id
        return None

    def _set_cursor_shape(self, shape: Qt.CursorShape) -> None:
        if shape != self._cursor_shape:
            self._cursor_shape = shape
            self.cursor = QCursor(shape)

    def _update_hover_cursor(self, event: QMouseEvent) -> None:
        handle_id = self._handle_at(event)
        if handle_id is None:
            self._set_cursor_shape(self._default_cursor.shape())
        else:
            self._set_cursor_shape(_HANDLE_CURSOR_SHAPES[handle_id])

    def _set_area_in_drag(self, area: QRect) -> None:
        """Sets the generation area during a left-drag, starting a new undo step with the drag's first change."""
        initial_area = self._image_stack.generation_area
        self._image_stack.set_generation_area(area, merge_with_last=self._drag_changed_area)
        if self._image_stack.generation_area != initial_area:
            self._drag_changed_area = True

    def _move_generation_area(self, image_coordinates: QPoint) -> None:
        """Moves the generation area so that it keeps its offset from the pointer."""
        assert self._move_offset is not None
        self._set_area_in_drag(QRect(image_coordinates + self._move_offset, self._image_stack.generation_area.size()))

    def _drag_resize_handle(self, event: QMouseEvent) -> None:
        """Resizes the generation area from the dragged handle."""
        assert self._drag_handle is not None
        scene_point = self._image_viewer.widget_point_to_scene(event.position()) + self._handle_offset
        keep_aspect = not KeyConfig.modifier_held(KeyConfig.FIXED_ASPECT_MODIFIER, held_modifiers=event.modifiers())
        area = resize_area_from_handle(self._drag_start_area, self._drag_handle, scene_point.toPoint(), keep_aspect,
                                       self._image_stack.bounds, self._image_stack.min_generation_area_size,
                                       self._image_stack.max_generation_area_size)
        self._set_area_in_drag(area)

    def _end_left_drag(self) -> None:
        if self._drag_handle is not None and self._drag_changed_area:
            record_generation_area_size(self._image_stack.generation_area.size())
        self._move_offset = None
        self._drag_handle = None
        self._drag_changed_area = False

    def _resize_generation_area(self, bottom_right: QPoint) -> None:
        """Updates the image generation area's size in the image."""
        generation_area = self._image_stack.generation_area
        width = min(self._image_stack.width - generation_area.x(), bottom_right.x() - generation_area.x())
        height = min(self._image_stack.height - generation_area.y(), bottom_right.y() - generation_area.y())
        if width > 0 and height > 0:
            if KeyConfig.modifier_held(KeyConfig.FIXED_ASPECT_MODIFIER):
                gen_size = cast(QSize, Cache().get(Cache.GENERATION_SIZE))
                aspect_ratio = gen_size.width() / gen_size.height()
                bottom_right = closest_point_keeping_aspect_ratio(QPointF(bottom_right),
                                                                  QPointF(generation_area.topLeft()),
                                                                  aspect_ratio)
                width = round(bottom_right.x() - generation_area.x())
                height = round(bottom_right.y() - generation_area.y())
            generation_area.setSize(QSize(width, height))
            self._image_stack.generation_area = QRect(generation_area.x(), generation_area.y(), width, height)

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Start moving or resizing the image generation area on left-click, start resizing on right-click."""
        assert event is not None
        if event.buttons() == Qt.MouseButton.LeftButton:
            self._end_left_drag()
            modifiers = event.modifiers()
            handle_id = None
            if modifiers == Qt.KeyboardModifier.NoModifier or KeyConfig.modifier_held(
                    KeyConfig.FIXED_ASPECT_MODIFIER, exclusive=True, held_modifiers=modifiers):
                handle_id = self._handle_at(event)
            if handle_id is not None:
                self._image_viewer.follow_generation_area = False
                self._drag_handle = handle_id
                self._drag_start_area = self._image_stack.generation_area
                handle_pos = area_handle_positions(self._drag_start_area)[handle_id]
                self._handle_offset = handle_pos - self._image_viewer.widget_point_to_scene(event.position())
                return True
            if modifiers != Qt.KeyboardModifier.NoModifier:
                return False
            area = self._image_stack.generation_area
            if area.contains(image_coordinates):
                self._move_offset = area.topLeft() - image_coordinates
            else:
                self._move_offset = QPoint(-(area.width() // 2), -(area.height() // 2))
                self._move_generation_area(image_coordinates)
        elif event.buttons() == Qt.MouseButton.RightButton:
            self._image_viewer.follow_generation_area = False
            self._resizing = True
            self._resize_generation_area(image_coordinates)
        else:
            return False
        return True

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Continue a left-drag move or handle resize, or a right-drag resize. Update the cursor over handles."""
        assert event is not None
        if event.buttons() == Qt.MouseButton.LeftButton:
            if self._drag_handle is not None:
                self._drag_resize_handle(event)
                return True
            if self._move_offset is not None:
                self._move_generation_area(image_coordinates)
                return True
            return False
        if event.buttons() == Qt.MouseButton.RightButton and self._resizing:
            self._resize_generation_area(image_coordinates)
            return True
        if event.buttons() == Qt.MouseButton.NoButton:
            self._update_hover_cursor(event)
        return False

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Finish any drag, recording the new size if the area was resized."""
        if self._resizing:
            record_generation_area_size(self._image_stack.generation_area.size())
        self._resizing = False
        self._end_left_drag()
        return False

    def key_event(self, event: Optional[QKeyEvent]) -> bool:
        """Move image generation area with arrow keys."""
        assert event is not None
        translation = QPoint(0, 0)
        multiplier = 10 if KeyConfig().modifier_held(KeyConfig.SPEED_MODIFIER) else 1
        match event.key():
            case Qt.Key.Key_Left:
                translation.setX(-1 * multiplier)
            case Qt.Key.Key_Right:
                translation.setX(1 * multiplier)
            case Qt.Key.Key_Up:
                translation.setY(-1 * multiplier)
            case Qt.Key.Key_Down:
                translation.setY(1 * multiplier)
            case _:
                return False
        self._image_stack.generation_area = self._image_stack.generation_area.translated(translation)
        return True
