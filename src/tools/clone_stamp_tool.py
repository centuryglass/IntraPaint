"""Use brush strokes to transfer image content over an offset."""
from typing import Optional

from PySide6.QtCore import QPoint
from PySide6.QtGui import QIcon, QCursor, QPixmap, QMouseEvent, Qt
from PySide6.QtWidgets import QApplication, QWidget, QGraphicsPixmapItem

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.brush.clone_stamp_brush import CloneStampBrush
from src.image.layers.image_stack import ImageStack
from src.tools.brush_tool import BrushTool
from src.tools.qt_paint_brush_tool import QtPaintBrushTool
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.clone_stamp_tool_panel import CloneStampToolPanel
from src.util.shared_constants import PROJECT_DIR
from src.util.signals_blocked import signals_blocked
from src.util.visual.text_drawing_utils import left_button_hint_text, right_button_hint_text

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.clone_stamp_tool'


def _tr(key: str, disambiguation: str = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


ICON_PATH_CLONE_STAMP_TOOL = f'{PROJECT_DIR}/resources/icons/tools/stamp_icon.svg'
CURSOR_PATH_CLONE_STAMP_TOOL = f'{PROJECT_DIR}/resources/cursors/stamp_cursor.svg'
IMAGE_PATH_CLONE_SAMPLE_POINT = f'{PROJECT_DIR}/resources/cursors/stamp_cursor_source.svg'

CLONE_STAMP_LABEL = _tr('Clone Stamp')
CLONE_STAMP_TOOLTIP = _tr('Copy image content from one area to another')
CLONE_STAMP_CONTROL_HINT = _tr('{right_mouse_icon}: set source - {left_mouse_icon}: draw')


LABEL_TEXT_OFFSET = _tr('Offset:')
LABEL_TEXT_POSITION = _tr('Position:')
LABEL_TEXT_SELECTION_ONLY = _tr('Update selection only')

SOURCE_MODE_FIXED_OFFSET = QApplication.translate('cache_value', "Fixed offset")
SOURCE_MODE_DYNAMIC_OFFSET = QApplication.translate('cache_value', "Dynamic offset")
SOURCE_MODE_STATIC = QApplication.translate('cache_value', "Fixed position")


class CloneStampTool(QtPaintBrushTool):
    """Use brush strokes to transfer image content over an offset."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        cache = Cache()
        self._source_pos = QPoint()
        self._source_offset = QPoint()
        self._source_mode = cache.get(Cache.CLONE_STAMP_TOOL_SOURCE_MODE)
        self._source_marker_pixmap = QPixmap(IMAGE_PATH_CLONE_SAMPLE_POINT)
        self._source_marker = QGraphicsPixmapItem(self._source_marker_pixmap)
        self._source_marker.setOpacity(0.5)
        self._pending_source_point: Optional[QPoint] = None
        self._view = image_viewer
        scene = image_viewer.scene()
        assert scene is not None
        self._scene = scene
        scene.addItem(self._source_marker)

        super().__init__(KeyConfig.CLONE_STAMP_TOOL_KEY, CLONE_STAMP_LABEL, CLONE_STAMP_TOOLTIP,
                         QIcon(ICON_PATH_CLONE_STAMP_TOOL),
                         image_stack, image_viewer, size_key=Cache.CLONE_STAMP_TOOL_BRUSH_SIZE,
                         pressure_size_key=Cache.CLONE_STAMP_TOOL_PRESSURE_SIZE,
                         opacity_key=Cache.CLONE_STAMP_TOOL_OPACITY,
                         pressure_opacity_key=Cache.CLONE_STAMP_TOOL_PRESSURE_OPACITY,
                         hardness_key=Cache.CLONE_STAMP_TOOL_HARDNESS,
                         pressure_hardness_key=Cache.CLONE_STAMP_TOOL_PRESSURE_HARDNESS,
                         antialias_key=Cache.CLONE_STAMP_TOOL_ANTIALIAS, brush=CloneStampBrush())
        self._control_panel: Optional[CloneStampToolPanel] = None
        self._source_marker.setVisible(False)
        self.set_scaling_icon_cursor(self.load_cursor_icon(CURSOR_PATH_CLONE_STAMP_TOOL))
        cache.connect(self, Cache.CLONE_STAMP_TOOL_SOURCE_MODE, self._update_source_mode)

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
            self._control_panel.source_xy_change.connect(self.update_source_xy)
        return self._control_panel

    def _update_source_mode(self, new_mode: str) -> None:
        if self._source_mode == new_mode:
            return
        last_mode = self._source_mode
        self._source_mode = new_mode
        if self._control_panel is None:
            return
        brush = self.brush
        assert isinstance(brush, CloneStampBrush)
        if new_mode == SOURCE_MODE_STATIC:
            if self._pending_source_point is not None:
                self._source_pos = self._pending_source_point
                self._pending_source_point = None
            with signals_blocked(self._control_panel):
                self._control_panel.source_xy = self._source_pos
                brush.source_pos = self._source_pos
        elif last_mode == SOURCE_MODE_STATIC:
            self._source_offset = QPoint()
            brush.source_offset = self._source_offset
            with signals_blocked(self._control_panel):
                self._control_panel.source_xy = self._source_offset
        self._update_source_marker()

    def update_source_xy(self, source_xy: QPoint) -> None:
        """Update the source xy position or offset in the control panel and brush."""
        brush = self.brush
        assert isinstance(brush, CloneStampBrush)
        if self._source_mode == SOURCE_MODE_STATIC:
            self._source_pos = source_xy
            brush.source_pos = source_xy
        else:
            self._source_offset = source_xy
            brush.source_offset = source_xy
        if self._control_panel is not None:
            with signals_blocked(self._control_panel):
                self._control_panel.source_xy = source_xy
        self._update_source_marker()

    def update_brush_cursor(self) -> None:
        """Adjust the offset marker when the brush cursor changes."""
        super().update_brush_cursor()
        if self.brush_size != self._source_marker.pixmap().width():
            self._update_source_marker()

    def _update_source_marker(self):
        source_marker_size = round(self._source_marker.pixmap().width() * self._source_marker.scale())
        if self.brush_size != source_marker_size:
            new_scale = self.brush_size / self._source_marker.pixmap().width()
            self._source_marker.setScale(new_scale)
        if self._pending_source_point is not None:
            offset_scene_pos = self._pending_source_point
        elif self._source_mode == SOURCE_MODE_STATIC:
            offset_scene_pos = self._source_pos
        else:
            offset_scene_pos = self._view.mapToScene(self._view.mapFromGlobal(QCursor.pos())) + self._source_offset
        offset_cursor_pos = offset_scene_pos - QPoint(source_marker_size // 2, source_marker_size // 2)
        self._source_marker.setPos(offset_cursor_pos)

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Set clone source on right-click, draw from source on left-click."""
        assert event is not None
        if event.buttons() == Qt.MouseButton.RightButton:
            if self._source_mode == SOURCE_MODE_STATIC:
                self.update_source_xy(image_coordinates)
            else:
                self._pending_source_point = image_coordinates
                self._update_source_marker()
            return True
        elif event.buttons() == Qt.MouseButton.LeftButton and self._pending_source_point is not None:
            offset = self._pending_source_point - image_coordinates
            self._pending_source_point = None
            self.update_source_xy(offset)
        return super().mouse_click(event, image_coordinates)

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Update the offset marker if offset is set and the mouse moves."""
        if self._pending_source_point is None and self._source_mode != SOURCE_MODE_STATIC:
            self._update_source_marker()
        elif self._pending_source_point is not None and self._control_panel is not None:
            current_offset = self._pending_source_point - image_coordinates
            with signals_blocked(self._control_panel):
                self._control_panel.source_xy = current_offset
        return super().mouse_move(event, image_coordinates)

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        if self._pending_source_point is None and self._source_mode == SOURCE_MODE_DYNAMIC_OFFSET:
            self._pending_source_point = image_coordinates + self._source_offset
        return super().mouse_release(event, image_coordinates)

    def _on_activate(self, restoring_after_delegation=False) -> None:
        """Show the offset marker when active."""
        self._update_source_marker()
        self._source_marker.setVisible(True)
        super()._on_activate(restoring_after_delegation)

    def _on_deactivate(self) -> None:
        """Hide the offset marker when inactive."""
        self._source_marker.setVisible(False)
        super()._on_deactivate()
