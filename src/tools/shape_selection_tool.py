"""Select or deselect rectangular or ellipsoid areas."""
from typing import Optional

from PyQt6.QtCore import Qt, QPoint, QRect, QRectF, QSizeF, QPointF
from PyQt6.QtGui import QKeySequence, QIcon, QMouseEvent, QPainter
from PyQt6.QtWidgets import QWidget, QLayout, QApplication, QHBoxLayout, QGraphicsRectItem, \
    QGraphicsEllipseItem

from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.tools.base_tool import BaseTool
from src.ui.image_viewer import ImageViewer
from src.ui.input_fields.dual_toggle import DualToggle
from src.util.shared_constants import PROJECT_DIR

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.shape_selection_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


RESOURCES_SHAPE_SELECT_ICON = f'{PROJECT_DIR}/resources/icons/shape_selection_icon.svg'

SHAPE_SELECTION_LABEL = _tr('Rectangle/Ellipse selection')
SHAPE_SELECTION_TOOLTIP = _tr('Select or de-select rectangles or ellipses')
SHAPE_SELECTION_CONTROL_HINT = _tr('LMB:select - RMB:deselect - Ctrl:fixed aspect -')

MODE_RECT = _tr('Rectangle')
MODE_ELLIPSE = _tr('Ellipse')
GRAPHICS_ITEM_OPACITY = 0.6


class ShapeSelectionTool(BaseTool):
    """Select or deselect rectangular or ellipsoid areas."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        super().__init__()
        scene = image_viewer.scene()
        assert scene is not None
        self._scene = scene
        self._image_stack = image_stack
        self._control_panel = QWidget()
        self._control_layout: Optional[QLayout] = None
        self._selection_shape: Optional[QGraphicsRectItem | QGraphicsEllipseItem] = None
        self._dragging = False
        self._clearing = False
        self._icon = QIcon(RESOURCES_SHAPE_SELECT_ICON)
        self._mode = MODE_RECT

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
        return f'{SHAPE_SELECTION_CONTROL_HINT} {super().get_input_hint()}'

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a panel providing controls for customizing tool behavior, or None if no such panel is needed."""
        if self._control_layout is not None:
            return self._control_panel
        self._control_layout = QHBoxLayout(self._control_panel)
        self._control_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        mode_toggle = DualToggle(self._control_panel, [MODE_RECT, MODE_ELLIPSE], Qt.Orientation.Horizontal)
        mode_toggle.setValue(MODE_RECT)
        mode_toggle.valueChanged.connect(self.set_shape_mode)
        self._control_layout.addWidget(mode_toggle)
        return self._control_panel

    def set_shape_mode(self, mode: str) -> None:
        """Switches between rectangle and ellipse selection."""
        if self._mode == mode:
            return
        if mode not in (MODE_ELLIPSE, MODE_RECT):
            raise ValueError(f'Unexpected selection mode {mode}')
        self._mode = mode

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Start selecting on click."""
        if self._selection_shape is not None:
            self._scene.removeItem(self._selection_shape)
            self._selection_shape = None
        if event.buttons() == Qt.MouseButton.RightButton:
            self._clearing = True
        elif event.buttons() == Qt.MouseButton.LeftButton:
            self._clearing = False
        else:
            return False
        self._selection_shape = QGraphicsRectItem(QRectF(QPointF(image_coordinates), QSizeF(0, 0))) \
                if self._mode == MODE_RECT \
                else QGraphicsEllipseItem(image_coordinates.x(), image_coordinates.y(), 0, 0)
        self._selection_shape.setBrush(Qt.GlobalColor.red)
        self._selection_shape.setOpacity(GRAPHICS_ITEM_OPACITY)
        self._scene.addItem(self._selection_shape)
        self._dragging = True
        return True

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Continue selection while buttons are held."""
        if not self._dragging:
            return False
        assert self._selection_shape is not None
        rect = self._selection_shape.rect()
        rect.setCoords(rect.x(), rect.y(), image_coordinates.x(), image_coordinates.y())
        self._selection_shape.setRect(rect)
        return True

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Finishes the selection/deselection."""
        if not self._dragging:
            return False
        self.mouse_move(event, image_coordinates)
        assert self._selection_shape is not None
        rect = self._selection_shape.rect()
        with self._image_stack.selection_layer.borrow_image() as selection_image:
            rect = QRect(rect.topLeft().toPoint() - self._image_stack.selection_layer.position, rect.size().toSize())
            painter = QPainter(selection_image)
            fill_color = Qt.GlobalColor.red
            if self._clearing:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            if self._mode == MODE_RECT:
                painter.fillRect(rect, fill_color)
            else:
                painter.setBrush(fill_color)
                painter.drawEllipse(rect)
            painter.end()
        self._scene.removeItem(self._selection_shape)
        self._selection_shape = None
        self._clearing = False
        self._dragging = False
        return True

    def _on_deactivate(self) -> None:
        if self._selection_shape is not None:
            self._scene.removeItem(self._selection_shape)
        self._clearing = False
        self._dragging = False
