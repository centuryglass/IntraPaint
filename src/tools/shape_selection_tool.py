"""Select or deselect rectangular or ellipsoid areas."""
from typing import Optional

from PySide6.QtCore import Qt, QPoint, QRect, QRectF, QSizeF, QPointF, QLineF
from PySide6.QtGui import QKeySequence, QIcon, QMouseEvent, QPainter, QColor
from PySide6.QtWidgets import QWidget, QLayout, QApplication, QGraphicsRectItem, \
    QGraphicsEllipseItem

from src.config.application_config import AppConfig
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.tools.base_tool import BaseTool
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.shape_selection_panel import ShapeSelectionPanel, MODE_RECT, MODE_ELLIPSE
from src.util.shared_constants import PROJECT_DIR, FLOAT_MAX

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
        self._selection_shape: Optional[QGraphicsRectItem | QGraphicsEllipseItem] = None
        self._dragging = False
        self._clearing = False
        self._icon = QIcon(RESOURCES_SHAPE_SELECT_ICON)
        self._mode = MODE_RECT
        self._color = QColor()

        def _update_mode(mode_str: str) -> None:
            self._mode = mode_str
        self._control_panel.tool_mode_changed.connect(_update_mode)

        def _update_color(color_str: str) -> None:
            if color_str == self._color.name():
                return
            self._color = QColor(color_str)
            self._color.setAlphaF(1.0)
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
        if self._mode == mode:
            return
        if mode not in (MODE_ELLIPSE, MODE_RECT):
            raise ValueError(f'Unexpected selection mode {mode}')
        self._mode = mode

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Start selecting on click."""
        assert event is not None
        if KeyConfig.modifier_held(KeyConfig.PAN_VIEW_MODIFIER, True):
            return False
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
        self._selection_shape.setBrush(self._color)
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
        if KeyConfig.modifier_held(KeyConfig.FIXED_ASPECT_MODIFIER):
            x_size = image_coordinates.x() - rect.x()
            y_size = image_coordinates.y() - rect.y()
            point_options = [
                QPointF(image_coordinates.x(), rect.y() + x_size),
                QPointF(image_coordinates.x(), rect.y() - x_size),
                QPointF(rect.x() + y_size, image_coordinates.y()),
                QPointF(rect.x() - y_size, image_coordinates.y())
            ]
            min_distance = FLOAT_MAX
            bottom_right = None
            for point in point_options:
                distance_from_mouse = QLineF(QPointF(image_coordinates), point).length()
                if distance_from_mouse < min_distance:
                    min_distance = distance_from_mouse
                    bottom_right = point
            assert bottom_right is not None
        else:
            bottom_right = image_coordinates
        rect.setCoords(rect.x(), rect.y(), bottom_right.x(), bottom_right.y())
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
            fill_color = self._color
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
