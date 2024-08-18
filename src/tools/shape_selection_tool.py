"""Select or deselect rectangular or ellipsoid areas."""
from typing import Optional

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QKeySequence, QIcon, QMouseEvent, QPainter, QColor, QBrush, QPainterPath
from PySide6.QtWidgets import QWidget, QLayout, QApplication

from src.config.application_config import AppConfig
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.tools.base_tool import BaseTool
from src.ui.graphics_items.click_and_drag_selection import ClickAndDragSelection, SELECTION_MODE_RECT, \
    SELECTION_MODE_ELLIPSE
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.shape_selection_panel import ShapeSelectionPanel
from src.util.shared_constants import PROJECT_DIR

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.shape_selection_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


RESOURCES_SHAPE_SELECT_ICON = f'{PROJECT_DIR}/resources/icons/tools/shape_selection_icon.svg'

SHAPE_SELECTION_LABEL = _tr('Rectangle/Ellipse selection')
SHAPE_SELECTION_TOOLTIP = _tr('Select or de-select rectangles or ellipses')
SHAPE_SELECTION_CONTROL_HINT = _tr('LMB:select - RMB:deselect - ')

GRAPHICS_ITEM_OPACITY = 0.6
ERASING_COLOR = Qt.GlobalColor.white


class ShapeSelectionTool(BaseTool):
    """Select or deselect rectangular or ellipsoid areas."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        super().__init__()
        scene = image_viewer.scene()
        assert scene is not None
        self._scene = scene
        self._image_stack = image_stack
        self._control_panel = ShapeSelectionPanel(image_stack.selection_layer)
        self._control_layout: Optional[QLayout] = None
        self._selection_handler = ClickAndDragSelection(scene)
        self._dragging = False
        self._clearing = False
        self._icon = QIcon(RESOURCES_SHAPE_SELECT_ICON)
        self._color = QColor()
        self._selection_brush = QBrush(QColor(), Qt.BrushStyle.Dense5Pattern)
        self._erasing_brush = QBrush(ERASING_COLOR, Qt.BrushStyle.DiagCrossPattern)

        def _update_mode(mode_str: str) -> None:
            self._selection_handler.mode = mode_str
        self._control_panel.tool_mode_changed.connect(_update_mode)

        def _update_color(color_str: str) -> None:
            self._color = QColor(color_str)
            self._color.setAlpha(255)
            self._selection_brush.setColor(self._color)
        _update_color(AppConfig().get(AppConfig.SELECTION_COLOR))
        AppConfig().connect(self, AppConfig.SELECTION_COLOR, _update_color)

    def get_hotkey(self) -> QKeySequence:
        """Returns the hotkey(s) that should activate this tool."""
        return KeyConfig().get_keycodes(KeyConfig.SHAPE_SELECTION_TOOL_KEY)

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        return SHAPE_SELECTION_LABEL

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        return SHAPE_SELECTION_TOOLTIP

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        return f'{SHAPE_SELECTION_CONTROL_HINT}{BaseTool.fixed_aspect_hint()}{super().get_input_hint()}'

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a panel providing controls for customizing tool behavior, or None if no such panel is needed."""
        return self._control_panel

    def set_shape_mode(self, mode: str) -> None:
        """Switches between rectangle and ellipse selection."""
        if self._selection_handler.mode == mode:
            return
        if mode not in (SELECTION_MODE_ELLIPSE, SELECTION_MODE_RECT):
            raise ValueError(f'Unexpected selection mode {mode}')
        self._selection_handler.mode = mode

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Start selecting on click."""
        assert event is not None
        if KeyConfig.modifier_held(KeyConfig.PAN_VIEW_MODIFIER, True):
            return False
        if event.buttons() == Qt.MouseButton.RightButton:
            self._clearing = True
        elif event.buttons() == Qt.MouseButton.LeftButton:
            self._clearing = False
        else:
            return False
        self._selection_handler.set_brush(self._erasing_brush if self._clearing else self._selection_brush)
        self._selection_handler.start_selection(image_coordinates)
        self._dragging = True
        return True

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Continue selection while buttons are held."""
        assert event is not None
        if not self._dragging:
            return False
        if event.buttons() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            self._selection_handler.drag_to(image_coordinates)
        else:
            self._end_drag(image_coordinates)
        return True

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Finishes the selection/deselection."""
        if not self._dragging:
            return False
        self._end_drag(image_coordinates)
        return True

    def _end_drag(self, image_coordinates: QPoint) -> None:
        assert self._dragging and self._selection_handler.selecting
        selection = self._selection_handler.end_selection(image_coordinates)
        with self._image_stack.selection_layer.borrow_image() as selection_image:
            selection.translate(-self._image_stack.selection_layer.position)
            path = QPainterPath()
            path.addPolygon(selection)
            painter = QPainter(selection_image)
            fill_color = self._color
            if self._clearing:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillPath(path, fill_color)
            painter.end()
        self._clearing = False
        self._dragging = False

    def _on_deactivate(self) -> None:
        if self._selection_handler.selecting:
            self._selection_handler.end_selection(QPoint())
        self._clearing = False
        self._dragging = False
