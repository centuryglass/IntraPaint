"""Select or deselect rectangular or ellipsoid areas."""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QColor, QBrush, QPainterPath, QPolygonF
from PySide6.QtWidgets import QWidget, QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.tools.base_tool import BaseTool
from src.tools.shape_drag_tool import ShapeDragTool
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.shape_selection_panel import ShapeSelectionPanel
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.selection_mode import SelectionMode, selection_mode_for_gesture, compose_selection_path
from src.util.visual.shape_mode import ShapeMode
from src.util.visual.text_drawing_utils import left_button_hint_text

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.shape_selection_tool'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


ICON_PATH_SHAPE_SELECT_TOOL = f'{PROJECT_DIR}/resources/icons/tools/shape_selection_icon.svg'

SHAPE_SELECTION_LABEL = _tr('Rectangle/Ellipse selection')
SHAPE_SELECTION_TOOLTIP = _tr('Select or deselect rectangles or ellipses')
SHAPE_SELECTION_CONTROL_HINT = _tr('{left_mouse_icon}, drag: select')

ERASING_COLOR = Qt.GlobalColor.white


class ShapeSelectionTool(ShapeDragTool):
    """Select or deselect rectangular or ellipsoid areas."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        super().__init__(KeyConfig.SHAPE_SELECTION_TOOL_KEY, SHAPE_SELECTION_LABEL, SHAPE_SELECTION_TOOLTIP,
                         QIcon(ICON_PATH_SHAPE_SELECT_TOOL), image_viewer)
        self._image_stack = image_stack
        self._control_panel = ShapeSelectionPanel(image_stack.selection_layer, self)
        # The fixed aspect and selection add modifiers share Shift by default, and the press reads it as add:
        self._selection_handler.aspect_modifier_needs_fresh_press = True
        self._gesture_mode = SelectionMode.ADD
        self._icon = QIcon(ICON_PATH_SHAPE_SELECT_TOOL)
        self._color = QColor()
        self._selection_brush = QBrush(QColor(), Qt.BrushStyle.Dense5Pattern)
        self._erasing_brush = QBrush(ERASING_COLOR, Qt.BrushStyle.DiagCrossPattern)

        def _update_mode(mode_str: str) -> None:
            try:
                mode = ShapeMode.from_text(mode_str)
                self._selection_handler.mode = mode
            except KeyError:
                pass
        self._control_panel.tool_mode_changed.connect(_update_mode)

        def _update_color(color_str: str) -> None:
            self._color = QColor(color_str)
            self._color.setAlpha(255)
            self._selection_brush.setColor(self._color)
        _update_color(AppConfig().get(AppConfig.SELECTION_COLOR))
        AppConfig().connect(self, AppConfig.SELECTION_COLOR, _update_color)

        def _update_fixed_aspect(fixed_aspect: bool) -> None:
            self._selection_handler.set_aspect_ratio(1.0 if fixed_aspect else None)
        _update_fixed_aspect(Cache().get(Cache.SHAPE_SELECTION_FIXED_ASPECT))
        Cache().connect(self, Cache.SHAPE_SELECTION_FIXED_ASPECT, _update_fixed_aspect)

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        shape_selection_hint = SHAPE_SELECTION_CONTROL_HINT.format(left_mouse_icon=left_button_hint_text())
        fixed_aspect_hint = BaseTool.fixed_aspect_hint()
        if fixed_aspect_hint:
            shape_selection_hint = f'{shape_selection_hint}, {fixed_aspect_hint}'
        return f'{shape_selection_hint}<br/>{super().get_input_hint()}'

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a panel providing controls for customizing tool behavior, or None if no such panel is needed."""
        return self._control_panel

    def set_shape_mode(self, mode: str) -> None:
        """Switches between rectangle and ellipse selection."""
        shape_mode = ShapeMode.from_text(mode)
        if self._selection_handler.mode == shape_mode:
            return
        if shape_mode not in (ShapeMode.RECTANGLE, ShapeMode.ELLIPSE):
            raise ValueError(f'Unexpected selection mode {mode}')
        self._selection_handler.mode = shape_mode

    def _prepare_drag(self) -> None:
        """Reads the selection mode for the drag, with the modifiers held at the press."""
        self._gesture_mode = selection_mode_for_gesture()
        subtracting = self._gesture_mode == SelectionMode.SUBTRACT
        self._selection_handler.set_brush(self._erasing_brush if subtracting else self._selection_brush)

    def _finish_drag(self, shape: QPolygonF) -> None:
        """Combines the dragged shape with the selection, using the mode read at the press."""
        mode = self._gesture_mode
        if mode.keeps_unrelated_content and not self._image_stack.merged_layer_bounds.intersects(
                shape.boundingRect().toAlignedRect()):
            return
        with self._image_stack.selection_layer.borrow_image() as selection_image:
            shape.translate(-self._image_stack.selection_layer.position)
            path = QPainterPath()
            path.addPolygon(shape)
            compose_selection_path(selection_image, path, self._color, mode)
