"""Use brush strokes to transfer image content over an offset."""
from typing import Optional

from PySide6.QtCore import QPoint, QPointF
from PySide6.QtGui import QIcon, QMouseEvent, Qt
from PySide6.QtWidgets import QApplication, QWidget

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.brush.clone_stamp_brush import CloneStampBrush
from src.image.layers.image_stack import ImageStack
from src.tools.brush_tool import MIN_OUTLINE_DIAMETER, BrushTool
from src.tools.qt_paint_brush_tool import QtPaintBrushTool
from src.ui.brush_crosshair import CrosshairVariant
from src.ui.graphics_items.brush_outline import BrushOutline
from src.ui.graphics_items.crosshair_item import CrosshairItem
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.clone_stamp_tool_panel import CloneStampToolPanel
from src.util.shared_constants import PROJECT_DIR
from src.util.signals_blocked import signals_blocked
from src.util.visual.text_drawing_utils import left_button_hint_text, right_button_hint_text

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.clone_stamp_tool'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


ICON_PATH_CLONE_STAMP_TOOL = f'{PROJECT_DIR}/resources/icons/tools/stamp_icon.svg'

CLONE_STAMP_LABEL = _tr('Clone stamp')
CLONE_STAMP_TOOLTIP = _tr('Copy image content from one area to another')
CLONE_STAMP_CONTROL_HINT = _tr('{right_mouse_icon}: set source - {left_mouse_icon}: draw')


LABEL_TEXT_OFFSET = _tr('Offset:')
LABEL_TEXT_POSITION = _tr('Position:')
LABEL_TEXT_SELECTION_ONLY = _tr('Update selection only')

# Stored `Cache.CLONE_STAMP_TOOL_SOURCE_MODE` values; they must match cache_value_definitions.json and must not be
# translated.
SOURCE_MODE_FIXED_OFFSET = 'Fixed offset'
SOURCE_MODE_DYNAMIC_OFFSET = 'Dynamic offset'
SOURCE_MODE_STATIC = 'Fixed position'


class CloneStampTool(QtPaintBrushTool):
    """Use brush strokes to transfer image content over an offset."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        cache = Cache()
        self._source_pos = QPoint()
        self._source_offset = QPoint()
        self._source_mode = cache.get(Cache.CLONE_STAMP_TOOL_SOURCE_MODE)
        self._pending_source_point: Optional[QPoint] = None
        self._view = image_viewer
        scene = image_viewer.scene()
        assert scene is not None
        self._scene = scene
        # The source marker is a dashed brush outline with a crosshair at its centre:
        self._source_outline = BrushOutline(scene, dashed=True)
        self._source_crosshair = CrosshairItem(scene, CrosshairVariant.CLONE_SOURCE)

        self._control_panel: Optional[CloneStampToolPanel] = None
        super().__init__(KeyConfig.CLONE_STAMP_TOOL_KEY, CLONE_STAMP_LABEL, CLONE_STAMP_TOOLTIP,
                         QIcon(ICON_PATH_CLONE_STAMP_TOOL),
                         image_stack, image_viewer, size_key=Cache.CLONE_STAMP_TOOL_BRUSH_SIZE,
                         pressure_size_key=Cache.CLONE_STAMP_TOOL_PRESSURE_SIZE,
                         opacity_key=Cache.CLONE_STAMP_TOOL_OPACITY,
                         pressure_opacity_key=Cache.CLONE_STAMP_TOOL_PRESSURE_OPACITY,
                         hardness_key=Cache.CLONE_STAMP_TOOL_HARDNESS,
                         pressure_hardness_key=Cache.CLONE_STAMP_TOOL_PRESSURE_HARDNESS,
                         antialias_key=Cache.CLONE_STAMP_TOOL_ANTIALIAS, brush=CloneStampBrush())
        cache.connect(self, Cache.CLONE_STAMP_TOOL_SOURCE_MODE, self._update_source_mode)
        self.crosshair_variant = CrosshairVariant.CLONE

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        brush_hint = CLONE_STAMP_CONTROL_HINT.format(left_mouse_icon=left_button_hint_text(),
                                                     right_mouse_icon=right_button_hint_text())
        return f'{brush_hint}<br/>{BrushTool.brush_control_hints()}<br/>{BrushTool.get_input_hint(self)}'

    # noinspection PyMethodMayBeStatic
    def get_control_panel(self) -> Optional[QWidget]:
        """Returns the clone stamp tool control panel."""
        if self._control_panel is None:
            self._control_panel = CloneStampToolPanel()
            self._control_panel.source_xy_change.connect(self.update_source_xy)
        return self._control_panel

    def get_reset_config_keys(self) -> list[str]:
        """Returns the brush keys and the source mode."""
        return [*super().get_reset_config_keys(), Cache.CLONE_STAMP_TOOL_SOURCE_MODE]

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

    def _apply_crosshair(self) -> None:
        """Updates the cursor and the source marker's crosshair, which use the plain design when variants are off."""
        super()._apply_crosshair()
        self._source_crosshair.variant = CrosshairVariant.CLONE_SOURCE if AppConfig().get(
            AppConfig.BRUSH_CROSSHAIR_VARIANTS) else CrosshairVariant.PLAIN

    def update_brush_cursor(self) -> None:
        """Updates the source marker along with the brush cursor."""
        super().update_brush_cursor()
        self._update_source_marker()

    def _source_marker_scene_pos(self) -> Optional[QPointF]:
        """Returns the scene position the source marker marks, or None if there is none to show.

        In an offset mode with no pending source point, that is the pointer position plus the offset, which is
        unknown while the pointer is outside the viewer.
        """
        if self._pending_source_point is not None:
            return QPointF(self._pending_source_point) + QPointF(0.5, 0.5)
        if self._source_mode == SOURCE_MODE_STATIC:
            return QPointF(self._source_pos) + QPointF(0.5, 0.5)
        cursor_pos = self._view.cursor_pos
        if cursor_pos is None:
            return None
        return self._view.widget_point_to_scene(cursor_pos) + QPointF(self._source_offset)

    def _update_source_marker(self) -> None:
        """Sizes and places the source marker, showing it only while the tool is active.

        The outline hides when the brush is no wider on screen than MIN_OUTLINE_DIAMETER, leaving only the crosshair.
        """
        scene_pos = self._source_marker_scene_pos() if self.is_active else None
        if scene_pos is None:
            self._source_outline.setVisible(False)
            self._source_crosshair.setVisible(False)
            return
        view_scale = self._view.scene_scale
        self._source_outline.set_size(self.brush_size, view_scale)
        self._source_outline.setPos(scene_pos)
        self._source_outline.setVisible(self.brush_size * view_scale > MIN_OUTLINE_DIAMETER)
        self._source_crosshair.setPos(scene_pos)
        self._source_crosshair.setVisible(True)

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Set clone source on right-click, draw from source on left-click."""
        if self._size_drag_event(event):
            return True
        assert event is not None
        if event.buttons() == Qt.MouseButton.RightButton:
            if self._source_mode == SOURCE_MODE_STATIC:
                self.update_source_xy(image_coordinates)
            else:
                self._pending_source_point = image_coordinates
                self._update_source_marker()
            return True
        if event.buttons() == Qt.MouseButton.LeftButton and self._pending_source_point is not None:
            offset = self._pending_source_point - image_coordinates
            self._pending_source_point = None
            self.update_source_xy(offset)
        return super().mouse_click(event, image_coordinates)

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Update the offset marker if offset is set and the mouse moves."""
        if self._size_drag_event(event):
            return True
        if self._pending_source_point is None and self._source_mode != SOURCE_MODE_STATIC:
            self._update_source_marker()
        elif self._pending_source_point is not None and self._control_panel is not None:
            current_offset = self._pending_source_point - image_coordinates
            with signals_blocked(self._control_panel):
                self._control_panel.source_xy = current_offset
        return super().mouse_move(event, image_coordinates)

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        if self._size_drag_event(event):
            return True
        if self._pending_source_point is None and self._source_mode == SOURCE_MODE_DYNAMIC_OFFSET:
            self._pending_source_point = image_coordinates + self._source_offset
        return super().mouse_release(event, image_coordinates)

    def _on_activate(self, restoring_after_delegation=False) -> None:
        """Show the source marker when active."""
        super()._on_activate(restoring_after_delegation)
        self._update_source_marker()

    def _on_deactivate(self) -> None:
        """Hide the source marker when inactive."""
        super()._on_deactivate()
        self._update_source_marker()
