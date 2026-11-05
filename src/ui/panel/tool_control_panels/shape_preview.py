"""Shape preview for the shape tool panel: one sample shape drawn with the tool's current settings over a transparency
tile background.

`ShapePreview` is a `BrushPreview` over the shape tool's `Cache` values. It draws with `QPainter` and the same pen and
brush settings the shape tool reads, so it shows what a drag would paint. The shape tool's `Cache` color sources are
resolved by `src.controller.color_controller`.
"""
from collections.abc import Hashable
from typing import Optional

from PySide6.QtCore import QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QBrush, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from src.config.cache import Cache
from src.controller import color_controller
from src.ui.input_fields.fill_style_combo_box import FillStyleComboBox
from src.ui.input_fields.pen_join_style_combo_box import PenJoinStyleComboBox
from src.ui.input_fields.pen_style_combo_box import PenStyleComboBox
from src.ui.panel.tool_control_panels.brush_preview import BrushPreview
from src.util.visual.image_utils import tile_pattern_fill
from src.util.visual.shape_mode import ShapeMode

PREVIEW_MIN_SIZE = QSize(120, 90)
PREVIEW_MAX_SIZE = QSize(300, 200)
PREVIEW_MARGIN = 6
PREVIEW_CHECKER_TILE_SIZE = 6
# The shape never takes more than this share of the preview's shorter side beyond the margin, so a wide outline leaves
# room for the shape's interior:
MAX_OUTLINE_INSET_FRACTION = 0.35
# A vertex at the top reads as an upright polygon or star:
UPRIGHT_ANGLE = 90.0


def _cache_keys() -> tuple[str, ...]:
    """Returns the `Cache` keys the preview depends on. The key constants exist only once `Cache` has been
    constructed, so they can't be module constants."""
    return (Cache.SHAPE_TOOL_MODE, Cache.SHAPE_TOOL_VERTEX_COUNT, Cache.SHAPE_TOOL_STAR_INNER_POINT_FRACTION,
            Cache.SHAPE_TOOL_LINE_WIDTH, Cache.SHAPE_TOOL_LINE_STYLE, Cache.SHAPE_TOOL_DASH_PATTERN,
            Cache.SHAPE_TOOL_LINE_JOIN_STYLE, Cache.SHAPE_TOOL_LINE_COLOR, Cache.SHAPE_TOOL_LINE_SOURCE,
            Cache.SHAPE_TOOL_FILL_COLOR, Cache.SHAPE_TOOL_FILL_SOURCE, Cache.SHAPE_TOOL_FILL_PATTERN,
            Cache.SHAPE_TOOL_ANTIALIAS, Cache.LAST_BRUSH_COLOR, Cache.BACKGROUND_COLOR)


def parse_dash_pattern(pattern_str: str) -> list[float]:
    """Returns the whole numbers in a space-separated dash pattern, ignoring anything else."""
    return [float(num) for num in pattern_str.split(' ') if num.isnumeric()]


def shape_pen() -> QPen:
    """Returns the pen the shape tool draws outlines with, from the shape tool's `Cache` values."""
    cache = Cache()
    pen = QPen()
    try:
        pen.setStyle(PenStyleComboBox.get_pen_style(cache.get(Cache.SHAPE_TOOL_LINE_STYLE)))
    except KeyError:
        pen.setStyle(Qt.PenStyle.SolidLine)
    pen.setColor(color_controller.shape_line_color())
    pen.setWidth(cache.get(Cache.SHAPE_TOOL_LINE_WIDTH))
    if pen.style() == Qt.PenStyle.CustomDashLine:
        dash_pattern = parse_dash_pattern(cache.get(Cache.SHAPE_TOOL_DASH_PATTERN))
        if len(dash_pattern) > 0 and len(dash_pattern) % 2 == 0:
            pen.setDashPattern(dash_pattern)
    try:
        pen.setJoinStyle(PenJoinStyleComboBox.get_join_style(cache.get(Cache.SHAPE_TOOL_LINE_JOIN_STYLE)))
    except KeyError:
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def shape_brush() -> QBrush:
    """Returns the brush the shape tool fills with, from the shape tool's `Cache` values."""
    brush = QBrush()
    try:
        brush.setStyle(FillStyleComboBox.get_style(Cache().get(Cache.SHAPE_TOOL_FILL_PATTERN)))
    except KeyError:
        brush.setStyle(Qt.BrushStyle.SolidPattern)
    brush.setColor(color_controller.shape_fill_color())
    return brush


class ShapePreview(BrushPreview):
    """Previews the shape the tool would draw: its type, outline and fill, over a transparency tile background.

    Where the shape has no fixed proportions, the ellipse and rectangle fill the preview and the polygon and star fit
    a circle inside it, as a drag would size them.
    """

    def __init__(self, parent: Optional[QWidget] = None, render_timer: Optional[QTimer] = None) -> None:
        super().__init__(_cache_keys(), parent, render_timer)
        self.setMinimumSize(PREVIEW_MIN_SIZE)
        self.setMaximumSize(PREVIEW_MAX_SIZE)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the smallest size the preview is drawn at."""
        return PREVIEW_MIN_SIZE

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the smallest size the preview is drawn at."""
        return PREVIEW_MIN_SIZE

    def _inputs(self) -> Hashable:
        cache = Cache()
        pen = shape_pen()
        brush = shape_brush()
        return (cache.get(Cache.SHAPE_TOOL_MODE), cache.get(Cache.SHAPE_TOOL_VERTEX_COUNT),
                cache.get(Cache.SHAPE_TOOL_STAR_INNER_POINT_FRACTION), pen.width(), int(pen.style().value),
                tuple(pen.dashPattern()), int(pen.joinStyle().value), pen.color().name(pen.color().NameFormat.HexArgb),
                int(brush.style().value), brush.color().name(brush.color().NameFormat.HexArgb),
                bool(cache.get(Cache.SHAPE_TOOL_ANTIALIAS)))

    def _render(self, size: QSize) -> QImage:
        """Draws the sample shape with the shape tool's pen and brush over the transparency tiles."""
        cache = Cache()
        image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
        painter = QPainter(image)
        tile_pattern_fill(painter, image.rect(), PREVIEW_CHECKER_TILE_SIZE, Qt.GlobalColor.lightGray,
                          Qt.GlobalColor.darkGray)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, bool(cache.get(Cache.SHAPE_TOOL_ANTIALIAS)))
        try:
            mode = ShapeMode.from_text(cache.get(Cache.SHAPE_TOOL_MODE))
        except ValueError:
            mode = ShapeMode.ELLIPSE
        pen = shape_pen()
        brush = shape_brush()
        bounds = self._shape_bounds(size, pen.width())
        if bounds.width() > 0 and bounds.height() > 0:
            path = self._shape_path(mode, bounds)
            painter.fillPath(path, brush)
            if pen.width() > 0:
                painter.setPen(pen)
                painter.drawPath(path)
        painter.end()
        return image

    @staticmethod
    def _shape_bounds(size: QSize, line_width: int) -> QRect:
        """Returns the rectangle the shape is drawn in: the preview less its margin and half the outline's width."""
        shorter = min(size.width(), size.height())
        inset = min(PREVIEW_MARGIN + line_width / 2, shorter * MAX_OUTLINE_INSET_FRACTION)
        return QRectF(0, 0, size.width(), size.height()).adjusted(inset, inset, -inset, -inset).toAlignedRect()

    @staticmethod
    def _shape_path(mode: ShapeMode, bounds: QRect) -> QPainterPath:
        cache = Cache()
        if mode == ShapeMode.ELLIPSE:
            # A drag draws an ellipse over the whole rectangle, where `ShapeMode.painter_path` draws a circle:
            path = QPainterPath()
            path.addEllipse(QRectF(bounds))
            return path
        radius = min(bounds.width(), bounds.height()) / 2
        inner_radius = radius * cache.get(Cache.SHAPE_TOOL_STAR_INNER_POINT_FRACTION)
        return mode.painter_path(bounds, radius, cache.get(Cache.SHAPE_TOOL_VERTEX_COUNT), inner_radius,
                                 UPRIGHT_ANGLE)
