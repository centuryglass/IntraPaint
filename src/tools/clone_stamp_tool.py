"""Use brush strokes to transfer image content over an offset."""
from typing import Optional

from PySide6.QtCore import QPoint, QSize
from PySide6.QtGui import QIcon, QCursor, QPixmap, QMouseEvent, Qt
from PySide6.QtWidgets import QApplication, QWidget, QGraphicsPixmapItem

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.brush.clone_stamp_brush import CloneStampBrush
from src.image.layers.image_stack import ImageStack
from src.tools.brush_tool import BrushTool, CURSOR_PATH_BRUSH_DEFAULT
from src.tools.qt_paint_brush_tool import QtPaintBrushTool
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.clone_stamp_tool_panel import CloneStampToolPanel
from src.util.shared_constants import PROJECT_DIR
from src.util.signals_blocked import signals_blocked
from src.util.visual.text_drawing_utils import left_button_hint_text, right_button_hint_text

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.clone_stamp_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


ICON_PATH_CLONE_STAMP_TOOL = f'{PROJECT_DIR}/resources/icons/tools/stamp_icon.svg'
CURSOR_PATH_CLONE_STAMP_TOOL = f'{PROJECT_DIR}/resources/cursors/stamp_cursor.svg'
IMAGE_PATH_CLONE_SAMPLE_POINT = f'{PROJECT_DIR}/resources/cursors/stamp_cursor_source.svg'

CLONE_STAMP_LABEL = _tr('Clone Stamp')
CLONE_STAMP_TOOLTIP = _tr('Copy image content from one area to another')
CLONE_STAMP_CONTROL_HINT = _tr('{right_mouse_icon}: set source - {left_mouse_icon}: draw')


class CloneStampTool(QtPaintBrushTool):
    """Use brush strokes to transfer image content over an offset."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        self._offset = QPoint()
        self._offset_source_pixmap = QPixmap(IMAGE_PATH_CLONE_SAMPLE_POINT)
        self._offset_marker = QGraphicsPixmapItem(self._offset_source_pixmap)
        self._offset_marker.setOpacity(0.5)
        self._pending_offset_point: Optional[QPoint] = None
        self._view = image_viewer
        scene = image_viewer.scene()
        assert scene is not None
        self._scene = scene
        scene.addItem(self._offset_marker)
        super().__init__(KeyConfig.CLONE_STAMP_TOOL_KEY, CLONE_STAMP_LABEL, CLONE_STAMP_TOOLTIP,
                         QIcon(ICON_PATH_CLONE_STAMP_TOOL),
                         image_stack, image_viewer, size_key=Cache.CLONE_STAMP_TOOL_BRUSH_SIZE,
                         pressure_size_key=Cache.CLONE_STAMP_TOOL_PRESSURE_SIZE,
                         opacity_key=Cache.CLONE_STAMP_TOOL_OPACITY,
                         pressure_opacity_key=Cache.CLONE_STAMP_TOOL_PRESSURE_OPACITY,
                         hardness_key=Cache.CLONE_STAMP_TOOL_HARDNESS,
                         pressure_hardness_key=Cache.CLONE_STAMP_TOOL_PRESSURE_HARDNESS, brush=CloneStampBrush())
        self._control_panel: Optional[CloneStampToolPanel] = None
        self._offset_marker.setVisible(False)
        self.set_scaling_icon_cursor(QIcon(CURSOR_PATH_CLONE_STAMP_TOOL))

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        brush_hint = CLONE_STAMP_CONTROL_HINT.format(left_mouse_icon=left_button_hint_text(),
                                                     right_mouse_icon=right_button_hint_text())
        return f'{brush_hint}<br/>{BrushTool.brush_control_hints()}<br/>{BrushTool.get_input_hint(self)}'

    # noinspection PyMethodMayBeStatic
    def get_control_panel(self) -> Optional[QWidget]:
        """Returns the blur tool control panel."""
        if self._control_panel is None:
            self._control_panel = CloneStampToolPanel()
            self._control_panel.offset_changed.connect(self.update_offset)
        return self._control_panel

    def update_offset(self, offset: QPoint) -> None:
        """Update the offset in the control panel and brush."""
        self._offset = offset
        brush = self.brush
        assert isinstance(brush, CloneStampBrush)
        brush.offset = offset
        if self._control_panel is not None:
            with signals_blocked(self._control_panel):
                self._control_panel.offset = offset
        self._update_offset_cursor()

    def update_brush_cursor(self) -> None:
        """Adjust the offset marker when the brush cursor changes."""
        super().update_brush_cursor()
        if self.brush_size != self._offset_marker.pixmap().width():
            self._update_offset_cursor()

    def _update_offset_cursor(self):
        cursor_size = round(self._offset_marker.pixmap().width() * self._offset_marker.scale())
        if self.brush_size != cursor_size:
            new_scale = self.brush_size / self._offset_marker.pixmap().width()
            self._offset_marker.setScale(new_scale)
        if self._pending_offset_point is not None:
            offset_scene_pos = self._pending_offset_point
        else:
            offset_scene_pos = self._view.mapToScene(self._view.mapFromGlobal(QCursor.pos())) + self._offset
        offset_cursor_pos = offset_scene_pos - QPoint(cursor_size // 2, cursor_size // 2)
        self._offset_marker.setPos(offset_cursor_pos)

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Set offset source on right-click, offset on left-click."""
        assert event is not None
        if event.buttons() == Qt.MouseButton.RightButton:
            self._pending_offset_point = image_coordinates
            self._update_offset_cursor()
        elif self._pending_offset_point is not None and event.buttons() == Qt.MouseButton.LeftButton:
            offset = self._pending_offset_point - image_coordinates
            self._pending_offset_point = None
            self.update_offset(offset)
        return super().mouse_click(event, image_coordinates)

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Update the offset marker if offset is set and the mouse moves."""
        if self._pending_offset_point is None:
            self._update_offset_cursor()
        return super().mouse_move(event, image_coordinates)

    def _on_activate(self, restoring_after_delegation=False) -> None:
        """Show the offset marker when active."""
        self._update_offset_cursor()
        self._offset_marker.setVisible(True)
        super()._on_activate(restoring_after_delegation)

    def _on_deactivate(self) -> None:
        """Hide the offset marker when inactive."""
        self._offset_marker.setVisible(False)
        super()._on_deactivate()
