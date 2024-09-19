"""Fill areas within an image."""
from typing import Optional

from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QIcon, QCursor, QMouseEvent, QKeySequence, QColor, QPainter, QTransform
from PySide6.QtWidgets import QWidget, QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.image.layers.transform_layer import TransformLayer
from src.tools.base_tool import BaseTool
from src.ui.panel.tool_control_panels.fill_selection_panel import FillSelectionPanel
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.image_utils import flood_fill, color_fill
from src.util.visual.text_drawing_utils import left_button_hint_text, right_button_hint_text

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.selection_fill_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


RESOURCES_FILL_ICON = f'{PROJECT_DIR}/resources/icons/tools/selection_fill_icon.svg'
RESOURCES_FILL_CURSOR = f'{PROJECT_DIR}/resources/cursors/selection_fill_cursor.svg'
CURSOR_SIZE = 25

SELECTION_FILL_LABEL = _tr('Selection fill')
SELECTION_FILL_TOOLTIP = _tr('Select areas with solid colors')
SELECTION_FILL_CONTROL_HINT = _tr('{left_mouse_icon}:select, {right_mouse_icon}: deselect')


class SelectionFillTool(BaseTool):
    """Lets the user select image areas with solid colors."""

    def __init__(self, image_stack: ImageStack) -> None:
        super().__init__()
        self._image_stack = image_stack
        self._control_panel = FillSelectionPanel(image_stack.selection_layer)
        self._icon = QIcon(RESOURCES_FILL_ICON)
        self._color = QColor()

        def _update_color(color_str: str) -> None:
            if color_str == self._color.name():
                return
            self._color = QColor(color_str)
            self._color.setAlphaF(1.0)
        _update_color(AppConfig().get(AppConfig.SELECTION_COLOR))
        AppConfig().connect(self, AppConfig.SELECTION_COLOR, _update_color)
        cursor_icon = QIcon(RESOURCES_FILL_CURSOR)
        self.cursor = QCursor(cursor_icon.pixmap(CURSOR_SIZE, CURSOR_SIZE))

    def get_hotkey(self) -> QKeySequence:
        """Returns the hotkey(s) that should activate this tool."""
        return KeyConfig().get_keycodes(KeyConfig.SELECTION_FILL_TOOL_KEY)

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        return SELECTION_FILL_LABEL

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        return SELECTION_FILL_TOOLTIP

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        selection_fill_hint = SELECTION_FILL_CONTROL_HINT.format(left_mouse_icon=left_button_hint_text(),
                                                                 right_mouse_icon=right_button_hint_text())
        return f'{selection_fill_hint}<br/>{super().get_input_hint()}'

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a panel providing controls for customizing tool behavior, or None if no such panel is needed."""
        return self._control_panel

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Fill the region under the mouse on left-click, clear on right-click."""
        assert event is not None
        if QApplication.keyboardModifiers() != Qt.KeyboardModifier.NoModifier:
            return True
        if event.buttons() == Qt.MouseButton.LeftButton or event.buttons() == Qt.MouseButton.RightButton:
            clear_mode = event.buttons() == Qt.MouseButton.RightButton
            layer = self._image_stack.active_layer
            layer_bounds = layer.bounds
            mask_pos = self._image_stack.selection_layer.position
            merged_pos = self._image_stack.merged_layer_bounds.topLeft()
            threshold = Cache().get(Cache.FILL_THRESHOLD)
            sample_merged = Cache().get(Cache.SAMPLE_MERGED)
            fill_by_selection = self._control_panel.fill_by_selection
            if isinstance(layer, TransformLayer):
                layer_pos = layer.map_to_image(layer_bounds.topLeft())
            else:
                layer_pos = layer_bounds.topLeft()
            if fill_by_selection:
                image = self._image_stack.selection_layer.image
                paint_transform = QTransform()
                sample_point = image_coordinates - mask_pos
            elif sample_merged:
                image = self._image_stack.qimage(crop_to_image=False)
                sample_point = image_coordinates - merged_pos
                offset = -mask_pos + merged_pos
                paint_transform = QTransform.fromTranslate(offset.x(), offset.y())
            else:
                image = layer.image
                if isinstance(layer, TransformLayer):
                    sample_point = layer.map_from_image(image_coordinates)
                    paint_transform = layer.transform
                else:
                    paint_transform = QTransform()
                    sample_point = image_coordinates - layer_bounds.topLeft()
                layer_pos_in_mask = layer_pos - mask_pos
                transformed_origin = paint_transform.map(QPoint(0, 0))
                img_offset = layer_pos_in_mask - transformed_origin
                paint_transform *= QTransform.fromTranslate(img_offset.x(), img_offset.y())
            if not QRect(QPoint(), image.size()).contains(sample_point):
                return True
            if Cache().get(Cache.COLOR_SELECT_MODE):
                mask = color_fill(image, image.pixelColor(image_coordinates), threshold)
            else:
                mask = flood_fill(image, sample_point, self._color, threshold, False)
            selection_image = self._image_stack.selection_layer.image
            assert mask is not None
            painter = QPainter(selection_image)
            if clear_mode:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
            painter.setTransform(paint_transform)
            painter.drawImage(QRect(QPoint(), mask.size()), mask)
            painter.end()
            self._image_stack.selection_layer.image = selection_image
            return True
        return False
