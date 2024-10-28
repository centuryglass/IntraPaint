"""Draws various geometric shapes."""
from typing import Optional

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QIcon, QMouseEvent, QPainter, QColor, QBrush, QPainterPath, QPen, QCursor, QPainterPathStroker
from PySide6.QtWidgets import QWidget, QApplication

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.tools.base_tool import BaseTool
from src.ui.graphics_items.click_and_drag_selection import ClickAndDragSelection
from src.ui.image_viewer import ImageViewer
from src.ui.input_fields.fill_style_combo_box import FillStyleComboBox
from src.ui.input_fields.pen_join_style_combo_box import PenJoinStyleComboBox
from src.ui.input_fields.pen_style_combo_box import PenStyleComboBox
from src.ui.panel.tool_control_panels.shape_tool_panel import ShapeToolPanel
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.shape_mode import ShapeMode
from src.util.visual.text_drawing_utils import left_button_hint_text, right_button_hint_text

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.shape_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


ICON_PATH_SHAPE_TOOL = f'{PROJECT_DIR}/resources/icons/tools/shape_icon.svg'

SHAPE_TOOL_LABEL = _tr('Draw Shapes')
SHAPE_TOOL_TOOLTIP = _tr('Create rectangles, ellipses, and other polygons')
SHAPE_TOOL_CONTROL_HINT = _tr('{left_mouse_icon}, drag: draw shape')


class ShapeTool(BaseTool):
    """Draws various geometric shapes."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        super().__init__(KeyConfig.SHAPE_TOOL_KEY, SHAPE_TOOL_LABEL, SHAPE_TOOL_TOOLTIP, QIcon(ICON_PATH_SHAPE_TOOL))
        self.cursor = QCursor(Qt.CursorShape.CrossCursor)
        cache = Cache()
        scene = image_viewer.scene()
        assert scene is not None
        self._scene = scene
        self._image_stack = image_stack
        self._control_panel: Optional[ShapeToolPanel] = None
        self._selection_handler = ClickAndDragSelection(scene)
        self._layer: Optional[ImageLayer] = None
        image_stack.active_layer_changed.connect(self._active_layer_change_slot)
        self._active_layer_change_slot(image_stack.active_layer)

        # load mode:
        try:
            self._selection_handler.mode = ShapeMode.from_text(cache.get(Cache.SHAPE_TOOL_MODE))
        except ValueError:
            self._selection_handler.mode = ShapeMode.ELLIPSE
        self._selection_handler.inner_radius_fraction = cache.get(Cache.SHAPE_TOOL_STAR_INNER_POINT_FRACTION)
        self._selection_handler.vertex_count = cache.get(Cache.SHAPE_TOOL_VERTEX_COUNT)
        self._dragging = False

        # load brush:
        self._brush = QBrush()
        try:
            self._brush.setStyle(FillStyleComboBox.get_style(cache.get(Cache.SHAPE_TOOL_FILL_PATTERN)))
        except KeyError:
            self._brush.setStyle(Qt.BrushStyle.SolidPattern)
        self._brush.setColor(cache.get_color(Cache.SHAPE_TOOL_FILL_COLOR, Qt.GlobalColor.white))
        self._selection_handler.set_brush(self._brush)

        # load pen:
        self._pen = QPen()
        try:
            self._pen.setStyle(PenStyleComboBox.get_pen_style(cache.get(Cache.SHAPE_TOOL_LINE_STYLE)))
        except KeyError:
            self._pen.setStyle(Qt.PenStyle.SolidLine)
        self._pen.setColor(cache.get_color(Cache.SHAPE_TOOL_LINE_COLOR, Qt.GlobalColor.black))
        self._pen.setWidth(cache.get(Cache.SHAPE_TOOL_LINE_WIDTH))
        if self._pen.style() == Qt.PenStyle.CustomDashLine:
            dash_pattern = _parse_dash_pattern(cache.get(Cache.SHAPE_TOOL_DASH_PATTERN))
            if len(dash_pattern) > 0 and (len(dash_pattern) % 2) == 0:
                self._pen.setDashPattern(dash_pattern)
        try:
            self._pen.setJoinStyle(PenJoinStyleComboBox.get_join_style(cache.get(Cache.SHAPE_TOOL_LINE_JOIN_STYLE)))
        except KeyError:
            self._pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self._selection_handler.set_pen(self._pen)

        for key, handler in ((Cache.SHAPE_TOOL_MODE, self._shape_mode_update_slot),
                             (Cache.SHAPE_TOOL_VERTEX_COUNT, self._shape_mode_vertex_count_update_slot),
                             (Cache.SHAPE_TOOL_STAR_INNER_POINT_FRACTION,
                              self._shape_mode_inner_radius_fraction_update_slot),
                             (Cache.SHAPE_TOOL_LINE_COLOR, self._line_color_update_slot),
                             (Cache.SHAPE_TOOL_LINE_STYLE, self._line_style_update_slot),
                             (Cache.SHAPE_TOOL_LINE_JOIN_STYLE, self._line_join_style_update_slot),
                             (Cache.SHAPE_TOOL_DASH_PATTERN, self._dash_pattern_update_slot),
                             (Cache.SHAPE_TOOL_LINE_WIDTH, self._line_width_update_slot),
                             (Cache.SHAPE_TOOL_FILL_PATTERN, self._fill_pattern_update_slot),
                             (Cache.SHAPE_TOOL_FILL_COLOR, self._fill_color_update_slot)):
            cache.connect(self, key, handler)

        # When the tool is active, changes to the primary brush color will propagate to the last shape mode tool that
        # changes.
        self._last_color_changed = Cache.SHAPE_TOOL_FILL_COLOR

        def _update_last_color(color_str: str) -> None:
            if self.is_active and QColor.isValidColor(color_str):
                cache.set(self._last_color_changed, color_str)
        cache.connect(self, Cache.LAST_BRUSH_COLOR, _update_last_color)

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        shape_selection_hint = SHAPE_TOOL_CONTROL_HINT.format(left_mouse_icon=left_button_hint_text(),
                                                              right_mouse_icon=right_button_hint_text())
        return f'{shape_selection_hint}<br/>{BaseTool.fixed_aspect_hint()}<br/>{super().get_input_hint()}'

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a panel providing controls for customizing tool behavior, or None if no such panel is needed."""
        if self._control_panel is None:
            self._control_panel = ShapeToolPanel()
            self._control_panel.setEnabled(self._layer is not None and not self._layer.locked
                                           and not self._layer.parent_locked)
        return self._control_panel

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Start selecting on click."""
        assert event is not None
        if KeyConfig.modifier_held(KeyConfig.PAN_VIEW_MODIFIER, True) \
                or event.buttons() != Qt.MouseButton.LeftButton \
                or not self.validate_layer(self._layer):
            return False
        self._selection_handler.set_brush(self._brush)
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
        self._dragging = False
        path = QPainterPath()
        path.addPolygon(self._selection_handler.end_selection(image_coordinates))
        if not isinstance(self._layer, ImageLayer):
            return
        line_width = self._pen.width()
        if line_width > 0:
            stroke_creator = QPainterPathStroker(self._pen)
            stroked_path = stroke_creator.createStroke(path)
            bounds = stroked_path.boundingRect().toAlignedRect()
        else:
            bounds = path.boundingRect().toAlignedRect()
        intersect_bounds = bounds.intersected(self._layer.bounds)
        if not intersect_bounds.isEmpty():
            with self._layer.borrow_image(intersect_bounds) as layer_image:
                painter = QPainter(layer_image)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, Cache().get(Cache.SHAPE_TOOL_ANTIALIAS))
                painter.setTransform(self._layer.transform.inverted()[0])
                painter.fillPath(path, self._brush)
                if self._pen.width() > 0:
                    painter.setPen(self._pen)
                    painter.drawPath(path)
                painter.end()

    def _on_activate(self, restoring_after_delegation=False) -> None:
        if self._control_panel is not None:
            self._control_panel.setEnabled(self._layer is not None and not self._layer.locked
                                           and not self._layer.parent_locked)

    def _on_deactivate(self) -> None:
        if self._selection_handler.selecting:
            self._selection_handler.end_selection(QPoint())
        self._dragging = False

    def _shape_mode_update_slot(self, shape_str: str) -> None:
        try:
            mode = ShapeMode.from_text(shape_str)
        except KeyError:
            return
        self._selection_handler.mode = mode

    def _shape_mode_vertex_count_update_slot(self, count: int) -> None:
        self._selection_handler.vertex_count = count

    def _shape_mode_inner_radius_fraction_update_slot(self, radius_fraction: float) -> None:
        self._selection_handler.inner_radius_fraction = radius_fraction

    def _line_color_update_slot(self, color_str: str) -> None:
        self._last_color_changed = Cache.SHAPE_TOOL_LINE_COLOR
        if QColor.isValidColor(color_str):
            color = QColor(color_str)
            if self._pen.color() == color:
                return
            self._pen.setColor(color)
            self._selection_handler.set_pen(self._pen)

    def _line_style_update_slot(self, style_str: str) -> None:
        try:
            pen_style = PenStyleComboBox.get_pen_style(style_str)
        except KeyError:
            return
        if pen_style == self._pen.style():
            return
        self._pen.setStyle(pen_style)
        if self._pen.style() == Qt.PenStyle.CustomDashLine:
            dash_pattern = _parse_dash_pattern(Cache().get(Cache.SHAPE_TOOL_DASH_PATTERN))
            if len(dash_pattern) > 0 and (len(dash_pattern) % 2) == 0:
                self._pen.setDashPattern(dash_pattern)
        self._selection_handler.set_pen(self._pen)

    def _line_join_style_update_slot(self, style_str: str) -> None:
        try:
            join_style = PenJoinStyleComboBox.get_join_style(style_str)
        except KeyError:
            return
        if join_style == self._pen.joinStyle():
            return
        self._pen.setJoinStyle(join_style)
        self._selection_handler.set_pen(self._pen)

    def _dash_pattern_update_slot(self, pattern_str: str) -> None:
        if self._pen.style() != Qt.PenStyle.CustomDashLine:
            return
        dash_pattern = _parse_dash_pattern(pattern_str)
        if len(dash_pattern) > 0 and (len(dash_pattern) % 2) == 0 and dash_pattern != self._pen.dashPattern():
            self._pen.setDashPattern(dash_pattern)
            self._selection_handler.set_pen(self._pen)

    def _line_width_update_slot(self, width: int) -> None:
        if width == self._pen.width():
            return
        self._pen.setWidth(width)
        self._selection_handler.set_pen(self._pen)

    def _fill_pattern_update_slot(self, pattern_str: str) -> None:
        try:
            fill_pattern = FillStyleComboBox.get_style(pattern_str)
        except KeyError:
            return
        if fill_pattern == self._brush.style():
            return
        self._brush.setStyle(fill_pattern)
        self._selection_handler.set_brush(self._brush)

    def _fill_color_update_slot(self, color_str: str) -> None:
        self._last_color_changed = Cache.SHAPE_TOOL_FILL_COLOR
        if not QColor.isValidColor(color_str):
            return
        color = QColor(color_str)
        if color == self._brush.color():
            return
        self._brush.setColor(color)
        self._selection_handler.set_brush(self._brush)

    def _active_layer_change_slot(self, active_layer: Optional[Layer]) -> None:
        if not isinstance(active_layer, ImageLayer):
            active_layer = None
        if self._layer == active_layer:
            return
        if self._layer != active_layer and self._layer is not None:
            self._layer.lock_changed.disconnect(self._layer_lock_slot)
        self._layer = active_layer
        if self.is_active and self._control_panel is not None:
            self._control_panel.setEnabled(active_layer is not None)
            self.set_disabled_cursor(active_layer is None)
        if active_layer is not None:
            active_layer.lock_changed.connect(self._layer_lock_slot)

    def _layer_lock_slot(self, layer: Layer, locked: bool) -> None:
        assert self._layer is not None
        assert layer == self._layer or layer.contains_recursive(self._layer)
        self.set_disabled_cursor(locked or not isinstance(self._layer, ImageLayer))
        if self.is_active and self._control_panel is not None:
            self._control_panel.setEnabled(not locked and isinstance(self._layer, ImageLayer))
        if locked and self._selection_handler.selecting:
            self._selection_handler.end_selection(QPoint())
            self._dragging = False


def _parse_dash_pattern(pattern_str) -> list[float]:
    return [float(num) for num in pattern_str.split(' ') if num.isnumeric()]
