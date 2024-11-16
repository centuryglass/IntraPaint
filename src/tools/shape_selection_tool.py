"""Select or deselect rectangular or ellipsoid areas."""
from typing import Optional

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QIcon, QMouseEvent, QPainter, QColor, QBrush, QPainterPath, QCursor
from PySide6.QtWidgets import QWidget, QApplication

from src.config.application_config import AppConfig
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.tools.base_tool import BaseTool
from src.ui.graphics_items.click_and_drag_selection import ClickAndDragSelection
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.shape_selection_panel import ShapeSelectionPanel
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.shape_mode import ShapeMode
from src.util.visual.text_drawing_utils import left_button_hint_text, right_button_hint_text

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.shape_selection_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


ICON_PATH_SHAPE_SELECT_TOOL = f'{PROJECT_DIR}/resources/icons/tools/shape_selection_icon.svg'

SHAPE_SELECTION_LABEL = _tr('Rectangle/Ellipse selection')
SHAPE_SELECTION_TOOLTIP = _tr('Select or deselect rectangles or ellipses')
SHAPE_SELECTION_CONTROL_HINT = _tr('{left_mouse_icon}, drag: select - {right_mouse_icon}, drag: deselect')

ERASING_COLOR = Qt.GlobalColor.white


class ShapeSelectionTool(BaseTool):
    """Select or deselect rectangular or ellipsoid areas."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        super().__init__(KeyConfig.SHAPE_SELECTION_TOOL_KEY, SHAPE_SELECTION_LABEL, SHAPE_SELECTION_TOOLTIP,
                         QIcon(ICON_PATH_SHAPE_SELECT_TOOL))
        self.cursor = QCursor(Qt.CursorShape.CrossCursor)
        scene = image_viewer.scene()
        assert scene is not None
        self._scene = scene
        self._image_stack = image_stack
        self._control_panel = ShapeSelectionPanel(image_stack.selection_layer, self)
        self._selection_handler = ClickAndDragSelection(scene)
        self._dragging = False
        self._clearing = False
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

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        shape_selection_hint = SHAPE_SELECTION_CONTROL_HINT.format(left_mouse_icon=left_button_hint_text(),
                                                                   right_mouse_icon=right_button_hint_text())
        return f'{shape_selection_hint}<br/>{BaseTool.fixed_aspect_hint()}<br/>{super().get_input_hint()}'

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
        if self._image_stack.merged_layer_bounds.intersects(selection.boundingRect().toAlignedRect()):
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
