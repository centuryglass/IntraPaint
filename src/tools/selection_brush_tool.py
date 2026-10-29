"""Selects image content for image generation or editing."""
from typing import Optional

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QIcon, QColor, QMouseEvent, QImage
from PySide6.QtWidgets import QWidget, QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.config_entry import RangeKey
from src.config.key_config import KeyConfig
from src.image.brush.qt_paint_brush import QtPaintBrush
from src.image.layers.image_stack import ImageStack
from src.tools.base_tool import ToolGroup
from src.tools.brush_tool import BrushTool
from src.tools.context_pin_dragger import ContextPinDragger
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.brush_selection_panel import BrushSelectionPanel
from src.util.shared_constants import PROJECT_DIR
from src.undo_stack import UndoStack
from src.util.visual.selection_mode import SelectionMode, brush_selection_mode_for_gesture, compose_selection_image
from src.util.visual.text_drawing_utils import left_button_hint_text, right_button_hint_text

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.selection_tool'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


LABEL_TEXT_SELECTION_TOOL = _tr('Selection brush')
TOOLTIP_SELECTION_TOOL = _tr('Draw to select areas for editing or inpainting.')
CONTROL_HINT_SELECTION_TOOL = _tr('{left_mouse_icon}: select - {right_mouse_icon}: add, move or remove context pin')

ICON_PATH_SELECTION_TOOL = f'{PROJECT_DIR}/resources/icons/tools/selection_icon.svg'
CURSOR_PATH_SELECTION_TOOL = f'{PROJECT_DIR}/resources/cursors/selection_cursor.svg'

# Undo gesture that holds a REPLACE or INTERSECT stroke together with the clearing that precedes it:
UNDO_GESTURE = 'SelectionBrushTool.stroke'

class SelectionBrushTool(BrushTool):
    """Selects image content for image generation or editing."""

    TOOL_GROUP = ToolGroup.SELECTION

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        brush = QtPaintBrush(None)
        super().__init__(KeyConfig.SELECTION_BRUSH_TOOL_KEY, LABEL_TEXT_SELECTION_TOOL, TOOLTIP_SELECTION_TOOL,
                         QIcon(ICON_PATH_SELECTION_TOOL), image_stack, image_viewer, brush, False, False)
        self._last_click = None
        self._control_panel = BrushSelectionPanel(image_stack.selection_layer, self)
        self._active = False
        self._drawing = False
        self._pin_dragger = ContextPinDragger(image_stack, image_viewer)
        self._stroke_mode = SelectionMode.ADD
        self._selection_before_stroke: Optional[QImage] = None  # Set only while an INTERSECT stroke is in progress.
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

        def _update_eraser(mode_str: str) -> None:
            self._brush.eraser = mode_str == SelectionMode.SUBTRACT.value
        _update_eraser(Cache().get(Cache.SELECTION_MODE))
        Cache().connect(self, Cache.SELECTION_MODE, _update_eraser)

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        select_hint = CONTROL_HINT_SELECTION_TOOL.format(left_mouse_icon=left_button_hint_text(),
                                                         right_mouse_icon=right_button_hint_text())
        return f'{select_hint}<br/>{BrushTool.brush_control_hints()}<br/>{super().get_input_hint()}'

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns the selection control panel."""
        return self._control_panel

    def _press_claims_fixed_angle_modifier(self) -> bool:
        """Returns whether the press reads the subtract modifier, and that modifier shares a key with the fixed angle
           modifier."""
        if brush_selection_mode_for_gesture(SelectionMode.ADD) != SelectionMode.SUBTRACT:
            return False
        subtract_modifiers = KeyConfig().get_modifier(KeyConfig.SELECTION_SUBTRACT_MODIFIER)
        fixed_angle_modifiers = KeyConfig().get_modifier(KeyConfig.FIXED_ANGLE_MODIFIER)
        subtract_list = subtract_modifiers if isinstance(subtract_modifiers, list) else [subtract_modifiers]
        angle_list = fixed_angle_modifiers if isinstance(fixed_angle_modifiers, list) else [fixed_angle_modifiers]
        return any(subtract & angle != Qt.KeyboardModifier.NoModifier
                   for subtract in subtract_list for angle in angle_list)

    def _before_stroke_start(self) -> None:
        """Applies the selection mode to the stroke about to start, with the subtract modifier read at the press.

        The brush only adds or removes pixels as it draws. REPLACE clears the selection first, and INTERSECT clears it
        while keeping a copy that `_after_stroke_end` intersects with the stroke. Both happen in the undo gesture that
        the stroke's own changes join, so the whole stroke is one undo step.
        """
        self._stroke_mode = brush_selection_mode_for_gesture()
        self._brush.eraser = self._stroke_mode == SelectionMode.SUBTRACT
        if self._stroke_mode in (SelectionMode.REPLACE, SelectionMode.INTERSECT):
            UndoStack().begin_gesture(UNDO_GESTURE)
            if self._stroke_mode == SelectionMode.INTERSECT:
                self._selection_before_stroke = self._image_stack.selection_layer.image
            self._image_stack.selection_layer.clear()

    def _after_stroke_end(self) -> None:
        """Finishes an INTERSECT stroke, and closes the undo gesture opened for REPLACE and INTERSECT strokes."""
        if self._stroke_mode not in (SelectionMode.REPLACE, SelectionMode.INTERSECT):
            return
        if self._selection_before_stroke is not None:
            with self._image_stack.selection_layer.borrow_image() as selection_image:
                compose_selection_image(selection_image, self._selection_before_stroke, SelectionMode.INTERSECT)
            self._selection_before_stroke = None
        UndoStack().end_gesture()
        self._stroke_mode = SelectionMode.ADD

    def set_brush_size(self, new_size: int) -> None:
        """Update the brush size."""
        new_size = min(new_size, Cache().get(Cache.SELECTION_BRUSH_SIZE, RangeKey.MAX))
        super().set_brush_size(new_size)
        Cache().set(Cache.SELECTION_BRUSH_SIZE, max(1, new_size))

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Starts a selection stroke on left-click, or a context pin drag on right-click."""
        if event is None or event.buttons() != Qt.MouseButton.RightButton:
            return super().mouse_click(event, image_coordinates)
        return self._pin_dragger.press(event, image_coordinates)

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Moves a dragged context pin with the pointer, hiding it while it's outside the image."""
        return self._pin_dragger.move(event, image_coordinates) or super().mouse_move(event, image_coordinates)

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Drops a dragged context pin, or removes a grabbed pin that was clicked without moving."""
        return self._pin_dragger.release(image_coordinates) or super().mouse_release(event, image_coordinates)

    def _on_deactivate(self) -> None:
        self._pin_dragger.finish()
        super()._on_deactivate()
