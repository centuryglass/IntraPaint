"""An image editing tool that moves the selected editing region."""

from typing import Optional, cast

from PySide6.QtCore import Qt, QRect, QPoint, QSize, QPointF
from PySide6.QtGui import QMouseEvent, QKeyEvent, QCursor, QIcon
from PySide6.QtWidgets import QWidget, QApplication

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.tools.base_tool import BaseTool
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.generation_area_tool_panel import GenerationAreaToolPanel
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.geometry_utils import closest_point_keeping_aspect_ratio
from src.util.visual.text_drawing_utils import left_button_hint_text, right_button_hint_text

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.generation_area_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


RESOURCES_GENERATION_AREA_ICON = f'{PROJECT_DIR}/resources/icons/tools/gen_area_icon.svg'
GENERATION_AREA_LABEL = _tr('Set Image Generation Area')
GENERATION_AREA_TOOLTIP = _tr('Select an image region for AI image generation')
GEN_AREA_CONTROL_HINT = _tr('{left_mouse_icon}: move area - {right_mouse_icon}: resize area')


class GenerationAreaTool(BaseTool):
    """An image editing tool that moves the selected editing region."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        super().__init__(KeyConfig.GENERATION_AREA_TOOL_KEY, GENERATION_AREA_LABEL, GENERATION_AREA_TOOLTIP,
                         QIcon(RESOURCES_GENERATION_AREA_ICON))
        self._image_stack = image_stack
        self._image_viewer = image_viewer
        self._resizing = False
        self.cursor = QCursor(Qt.CursorShape.CrossCursor)
        self._control_panel = GenerationAreaToolPanel(image_stack)

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        gen_area_hint = GEN_AREA_CONTROL_HINT.format(left_mouse_icon=left_button_hint_text(),
                                                     right_mouse_icon=right_button_hint_text())
        return f'{gen_area_hint}<br/>{BaseTool.fixed_aspect_hint()}<br/>{super().get_input_hint()}'

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a panel providing controls for customizing tool behavior, or None if no such panel is needed."""
        return self._control_panel

    def _move_generation_area(self, selection_pt: QPoint) -> None:
        """Updates the image generation area's location in the image."""
        self._image_stack.generation_area = QRect(selection_pt, self._image_stack.generation_area.size())

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
        """Move the image generation area on left-click, start resizing on right-click."""
        assert event is not None
        if event.buttons() == Qt.MouseButton.LeftButton:
            if QApplication.keyboardModifiers() != Qt.KeyboardModifier.NoModifier:
                return False
            self._move_generation_area(image_coordinates)
        elif event.buttons() == Qt.MouseButton.RightButton:
            self._image_viewer.follow_generation_area = False
            self._resizing = True
            self._resize_generation_area(image_coordinates)
        else:
            return False
        return True

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """If resizing, dynamically adjust the image generation area if the new size would be non-empty."""
        assert event is not None
        if event.buttons() == Qt.MouseButton.LeftButton:
            return self.mouse_click(event, image_coordinates)
        if event.buttons() == Qt.MouseButton.RightButton and self._resizing:
            self._resize_generation_area(image_coordinates)
            return True
        return False

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """If resizing, finish on mouse_release."""
        self._resizing = False
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
