"""Select or deselect polygonal areas."""
from typing import Optional

from PySide6.QtCore import Qt, QPoint, QPointF, QLineF, QEvent
from PySide6.QtGui import QKeySequence, QIcon, QMouseEvent, QPainter, QPainterPath, QTransform
from PySide6.QtWidgets import QWidget, QApplication

from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.image.layers.image_stack import ImageStack
from src.tools.base_tool import BaseTool
from src.ui.graphics_items.path_creation_item import PathCreationItem
from src.ui.graphics_items.temp_dashed_line_item import TempDashedLineItem
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.brush_selection_panel import TOOL_MODE_DESELECT
from src.ui.panel.tool_control_panels.free_selection_panel import FreeSelectionPanel
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.text_drawing_utils import rich_text_key_hint, left_button_hint_text

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.lasso_selection_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


ICON_PATH_FREE_SELECT_TOOL = f'{PROJECT_DIR}/resources/icons/tools/free_selection_icon.svg'

FREE_SELECTION_LABEL = _tr('Free selection')
FREE_SELECTION_TOOLTIP = _tr('Select or deselect polygonal areas')
FREE_SELECTION_CONTROL_HINT = _tr('{left_mouse_icon}: add or move point<br/>{enter_key}'
                                  ' or {left_mouse_icon}+first point: finish selection<br/>'
                                  '{escape_key}: cancel selection')


class FreeSelectionTool(BaseTool):
    """Select or deselect polygonal areas."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        super().__init__(KeyConfig.FREE_SELECTION_TOOL_KEY, FREE_SELECTION_LABEL, FREE_SELECTION_TOOLTIP,
                         QIcon(ICON_PATH_FREE_SELECT_TOOL))
        scene = image_viewer.scene()
        assert scene is not None
        self._scene = scene
        self._image_stack = image_stack
        self._control_panel = FreeSelectionPanel(image_stack.selection_layer)
        self._path_item = PathCreationItem(self._scene)
        self._preview_line = TempDashedLineItem(scene)
        self._clearing = False

        def _update_clearing(mode: str) -> None:
            self._clearing = mode == TOOL_MODE_DESELECT
        self._control_panel.tool_mode_changed.connect(_update_clearing)

        def _close_on_enter() -> bool:
            if not self.is_active or self._path_item.count < 3:
                return False
            self._close_and_select()
            return True
        HotkeyFilter.instance().register_keybinding('FreeSelectionTool._close_on_enter', _close_on_enter,
                                                    QKeySequence(Qt.Key.Key_Enter, Qt.Key.Key_Return))

        def _cancel_on_escape() -> bool:
            if not self.is_active or self._path_item.count == 0:
                return False
            self._preview_line.set_line(QLineF())
            self._preview_line.setVisible(False)
            self._path_item.clear_points()
            return True
        HotkeyFilter.instance().register_keybinding(f'FreeSelectionTool_{id(self)}_cancel_on_escape',
                                                    _cancel_on_escape, QKeySequence(Qt.Key.Key_Escape))

        self._path_item.first_handle_clicked.connect(self._first_handle_click_slot)

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        selection_hint = FREE_SELECTION_CONTROL_HINT.format(left_mouse_icon=left_button_hint_text(),
                                                            escape_key=rich_text_key_hint('Esc'),
                                                            enter_key=rich_text_key_hint('Enter'))
        return f'{selection_hint}<br/>{super().get_input_hint()}'

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a panel providing controls for customizing tool behavior, or None if no such panel is needed."""
        return self._control_panel

    def _close_and_select(self) -> None:
        polygon = self._path_item.get_path()
        if polygon is None:
            return
        self._preview_line.set_line(QLineF())
        self._preview_line.setVisible(False)
        self._path_item.clear_points()
        layer = self._image_stack.selection_layer
        layer_pos = layer.transformed_bounds.topLeft()
        bounds = polygon.boundingRect().toAlignedRect()
        bounds.translate(-layer_pos.x(), -layer_pos.y())
        bounds = bounds.intersected(layer.bounds)
        with layer.borrow_image(bounds) as selection_img:
            painter = QPainter(selection_img)
            if self._clearing:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.setTransform(QTransform.fromTranslate(-layer_pos.x(), -layer_pos.y()))
            path = QPainterPath()
            path.addPolygon(polygon)
            painter.fillPath(path, Qt.GlobalColor.red)
            painter.end()

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Start selecting on click."""
        assert event is not None
        if KeyConfig.modifier_held(KeyConfig.PAN_VIEW_MODIFIER, True):
            return False
        point_idx = self._path_item.get_point_index(QPointF(image_coordinates))
        if event.buttons() == Qt.MouseButton.LeftButton and point_idx == 0 and self._path_item.count > 2:
            self._close_and_select()
            return True
        if event.buttons() == Qt.MouseButton.LeftButton and point_idx is None:
            self._path_item.add_point(QPointF(image_coordinates))
            self._preview_line.setVisible(True)
            self._preview_line.set_line(QLineF(QPointF(image_coordinates), QPointF(image_coordinates)))
            return True
        return False

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Move the line preview if at least one point has been added."""
        if self._path_item.count > 0:
            line = QLineF(self._path_item.last_point(), QPointF(image_coordinates))
            self._preview_line.set_line(line)
            return True
        return False

        # noinspection PyUnusedLocal

    def mouse_enter(self, event: Optional[QEvent], image_coordinates: QPoint) -> bool:
        """Show the line preview on enter if selecting."""
        if self._path_item.count > 0:
            self._preview_line.setVisible(True)
            return True
        return False

    def mouse_exit(self, event: Optional[QEvent], image_coordinates: QPoint) -> bool:
        """Hide the line preview on exit."""
        self._preview_line.set_line(QLineF())
        self._preview_line.setVisible(False)
        return True

    def _on_activate(self, restoring_after_delegation=False) -> None:
        self._path_item.setVisible(True)

    def _on_deactivate(self) -> None:
        self._path_item.setVisible(False)
        self._preview_line.setVisible(False)

    def _first_handle_click_slot(self) -> None:
        if self._path_item.count > 2:
            self._close_and_select()
