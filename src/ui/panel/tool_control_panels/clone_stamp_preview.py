"""Stroke preview for the Clone stamp tool panel.

`CloneStampStrokePreview` draws sample strokes with the real `CloneStampBrush` over the shared preview backdrop, then
marks where each stroke copied from, so the preview shows how the source mode relates source and destination:

- Fixed offset: one stroke, with its source outlined and an arrow from the source to the stroke.
- Dynamic offset: two separate strokes whose sources continue one path, with an arrow from each source.
- Fixed position: one stroke, with arrows fanning out from the single source point.

The offset modes point the source in the direction of the panel's X/Y offset. Its length is the offset itself, shrunk
to fit the preview. A fixed position has no anchor in the preview, so its source point sits at a fixed place.
"""
import math
from collections.abc import Hashable
from typing import Optional

from PySide6.QtCore import QLineF, QPoint, QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from src.config.cache import Cache
from src.image.brush.clone_stamp_brush import CloneStampBrush
from src.image.layers.image_layer import ImageLayer
from src.ui.panel.tool_control_panels.preview_backdrop import backdrop_image, backdrop_motif_rect, tile_size
from src.ui.panel.tool_control_panels.stroke_preview import StrokePreview, wave_points
from src.undo_stack import UndoStack

# Stored `Cache.CLONE_STAMP_TOOL_SOURCE_MODE` values; they match `src.tools.clone_stamp_tool` and the options in
# cache_value_definitions.json. Code compares these raw values, never the translated labels.
SOURCE_MODE_FIXED_OFFSET = 'Fixed offset'
SOURCE_MODE_DYNAMIC_OFFSET = 'Dynamic offset'
SOURCE_MODE_STATIC = 'Fixed position'

PREVIEW_MARGIN = 6.0
# Brush diameter cap, wave amplitude and source path width, as fractions of the preview's usable height or width:
MAX_DIAMETER_FRACTION = 0.35
AMPLITUDE_FRACTION = 0.12
SOURCE_PATH_WIDTH_FRACTION = 0.3
STAMP_SPACING = 0.2
# Direction used while the panel's offset is (0, 0), before the tool has a source:
DEFAULT_OFFSET_DIRECTION = QPointF(1.0, 0.0)
OVERLAY_COLOR = QColor(20, 20, 20)
OVERLAY_HALO_COLOR = QColor(255, 255, 255, 200)
OVERLAY_WIDTH = 1.25
OVERLAY_HALO_WIDTH = 3.5
ARROW_HEAD_SIZE = 6.0


def _translated(points: list[QPointF], delta: QPointF) -> list[QPointF]:
    return [point + delta for point in points]


def _bounds(point_lists: list[list[QPointF]], radius: float) -> QRectF:
    """Returns the bounds of every point, grown by `radius`."""
    points = [point for point_list in point_lists for point in point_list]
    left = min(point.x() for point in points)
    top = min(point.y() for point in points)
    right = max(point.x() for point in points)
    bottom = max(point.y() for point in points)
    return QRectF(left, top, right - left, bottom - top).adjusted(-radius, -radius, radius, radius)


class _CloneLayout:
    """Where the preview's strokes go, and where each one copies from.

    `strokes[i]` is drawn with offset `offsets[i]`, or from `source_point` when that is set. `sources[i]` is the path
    `strokes[i]` copies from, empty for a fixed position.
    """

    def __init__(self, diameter: float, strokes: list[list[QPointF]], sources: list[list[QPointF]],
                 offsets: list[QPoint], source_point: Optional[QPoint]) -> None:
        self.diameter = diameter
        self.strokes = strokes
        self.sources = sources
        self.offsets = offsets
        self.source_point = source_point

    def source_center_x(self) -> float:
        """Returns the x-coordinate the backdrop's motif is centered on: the source's middle."""
        if self.source_point is not None:
            return float(self.source_point.x())
        return _bounds(self.sources, 0.0).center().x()


class CloneStampStrokePreview(StrokePreview):
    """Previews clone stamping in the source mode in `Cache`, with the panel's source X/Y passed to
    `set_source_xy`."""

    def __init__(self, size_key: str, opacity_key: Optional[str], hardness_key: Optional[str],
                 antialias_key: Optional[str] = None, parent: Optional[QWidget] = None,
                 render_timer: Optional[QTimer] = None) -> None:
        self._source_xy = QPoint()
        super().__init__(size_key, opacity_key, hardness_key, antialias_key, (Cache.CLONE_STAMP_TOOL_SOURCE_MODE,),
                         parent, render_timer)

    def set_source_xy(self, source_xy: QPoint) -> None:
        """Sets the source offset or position shown, scheduling a render if it changed."""
        if source_xy == self._source_xy:
            return
        self._source_xy = QPoint(source_xy)
        self._inputs_changed()

    def _mode(self) -> str:
        return Cache().get(Cache.CLONE_STAMP_TOOL_SOURCE_MODE)

    def _inputs(self) -> Hashable:
        mode = self._mode()
        # A fixed position doesn't change the render, so only the offset modes depend on X/Y:
        source_xy = None if mode == SOURCE_MODE_STATIC else (self._source_xy.x(), self._source_xy.y())
        return super()._inputs(), mode, source_xy

    def _new_brush(self, layer: ImageLayer) -> CloneStampBrush:
        return CloneStampBrush(layer)

    def _backdrop(self, size: QSize, layout: _CloneLayout) -> QImage:
        """Returns the shared backdrop, shifted sideways so a motif sits under the source."""
        tile_width = tile_size(size).width()
        motif_x = backdrop_motif_rect(size).center().x()
        shift = (motif_x - round(layout.source_center_x())) % tile_width
        return backdrop_image(QSize(size.width() + tile_width, size.height())).copy(shift, 0, size.width(),
                                                                                     size.height())

    def _layout(self, size: QSize) -> _CloneLayout:
        """Returns the strokes and sources for the current mode, fit within `size`."""
        width = size.width() - 2 * PREVIEW_MARGIN
        height = size.height() - 2 * PREVIEW_MARGIN
        diameter = max(1.0, min(float(self._value(self._size_key, 1)), max(height, 1.0) * MAX_DIAMETER_FRACTION))
        radius = diameter / 2
        amplitude = max(height, 0.0) * AMPLITUDE_FRACTION
        spacing = max(1.0, diameter * STAMP_SPACING)
        mode = self._mode()
        if mode == SOURCE_MODE_STATIC:
            source_point = QPoint(round(PREVIEW_MARGIN + diameter), size.height() // 2)
            left = source_point.x() + 2 * diameter
            stroke = wave_points(left, size.width() - PREVIEW_MARGIN - radius, size.height() / 2,
                           max(height / 2 - radius, 0.0), spacing)
            return _CloneLayout(diameter, [stroke], [], [], source_point)

        path_width = max(width * SOURCE_PATH_WIDTH_FRACTION, diameter)
        source = wave_points(-path_width / 2, path_width / 2, 0.0, amplitude, spacing)
        if self._source_xy.isNull():
            direction = DEFAULT_OFFSET_DIRECTION
            requested = math.inf
        else:
            requested = math.hypot(self._source_xy.x(), self._source_xy.y())
            direction = QPointF(self._source_xy) / requested
        dynamic = mode == SOURCE_MODE_DYNAMIC_OFFSET
        if dynamic:
            # The second stroke starts away from where the first ended, beside it across the offset's direction:
            middle = len(source) // 2
            source_parts = [source[:middle + 1], source[middle:]]
            jump = QPointF(-direction.y(), direction.x()) * (diameter * 1.5)
        else:
            source_parts = [source]
            jump = QPointF()

        def _strokes(length: float) -> list[list[QPointF]]:
            offset = direction * length
            strokes = [_translated(source_parts[0], -offset)]
            if dynamic:
                strokes.append(_translated(source_parts[1], jump - offset))
            return strokes

        # The longest offset up to the requested one that keeps every stroke and source in the preview:
        max_length = math.hypot(width, height)
        length = min(requested, max_length)
        while length > 1.0 and not _fits(_bounds(_strokes(length) + source_parts, radius), width, height):
            length -= 1.0
        length = max(length, 1.0)
        strokes = _strokes(length)
        bounds = _bounds(strokes + source_parts, radius)
        center = QPointF(size.width() / 2, size.height() / 2)
        to_center = center - bounds.center()
        to_center = QPointF(round(to_center.x()), round(to_center.y()))
        strokes = [_translated(stroke, to_center) for stroke in strokes]
        sources = [_translated(part, to_center) for part in source_parts]
        offsets = [(source_part[0] - stroke[0]).toPoint() for source_part, stroke in zip(sources, strokes)]
        return _CloneLayout(diameter, strokes, sources, offsets, None)

    def _render(self, size: QSize) -> QImage:
        """Draws each stroke with a `CloneStampBrush` on a scratch layer, keeping its edits out of undo history, then
        marks where the strokes copied from."""
        layout = self._layout(size)
        with UndoStack().unrecorded():
            layer = ImageLayer(self._backdrop(size, layout), 'brush preview')
            brush = self._new_brush(layer)
            brush.brush_size = round(layout.diameter)
            self._configure_brush(brush)
            for index, stroke in enumerate(layout.strokes):
                if layout.source_point is not None:
                    brush.source_pos = layout.source_point
                else:
                    brush.source_offset = layout.offsets[index]
                brush.start_stroke()
                for point in stroke:
                    brush.stroke_to(point.x(), point.y(), None, None, None)
                brush.end_stroke()
            brush.connect_to_layer(None)
            image = layer.image
        self._draw_overlay(image, layout)
        return image

    @staticmethod
    def _draw_overlay(image: QImage, layout: _CloneLayout) -> None:
        """Outlines the sources and draws arrows from each source to where its content went."""
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        radius = layout.diameter / 2
        lines: list[QLineF] = []
        if layout.source_point is not None:
            source = QPointF(layout.source_point)
            stroke = layout.strokes[0]
            for point in (stroke[0], stroke[len(stroke) // 4], stroke[3 * len(stroke) // 4]):
                lines.append(QLineF(source, point))
        else:
            for source, stroke, offset in zip(layout.sources, layout.strokes, layout.offsets):
                # Across the gap, from the source's nearest end to the stroke's, so the arrow covers neither:
                direction = QPointF(offset)
                nearest_source = min(source, key=lambda point, delta=direction: QPointF.dotProduct(point, delta))
                nearest_stroke = max(stroke, key=lambda point, delta=direction: QPointF.dotProduct(point, delta))
                lines.append(QLineF(nearest_source, nearest_stroke))
        for halo in (True, False):
            pen = QPen(OVERLAY_HALO_COLOR if halo else OVERLAY_COLOR, OVERLAY_HALO_WIDTH if halo else OVERLAY_WIDTH)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if layout.source_point is not None:
                painter.setPen(pen)
                center = QPointF(layout.source_point)
                painter.drawEllipse(center, radius, radius)
                painter.drawLine(center - QPointF(radius / 2, 0), center + QPointF(radius / 2, 0))
                painter.drawLine(center - QPointF(0, radius / 2), center + QPointF(0, radius / 2))
            else:
                dashed = QPen(pen)
                dashed.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(dashed)
                # The sources are drawn as one path, so a dynamic offset's two sources read as one continued stroke:
                path = layout.sources[0] + [point for part in layout.sources[1:] for point in part[1:]]
                painter.drawPolyline(QPolygonF(path))
                for part in layout.sources:
                    painter.drawEllipse(part[0], radius, radius)
            for line in lines:
                _draw_arrow(painter, line, pen, radius)
        painter.end()


def _fits(bounds: QRectF, width: float, height: float) -> bool:
    return bounds.width() <= width and bounds.height() <= height


def _draw_arrow(painter: QPainter, line: QLineF, pen: QPen, inset: float) -> None:
    """Draws an arrow along `line`, leaving `inset` uncovered at each end so it stops at the brush's edge."""
    if line.length() <= 2 * inset + ARROW_HEAD_SIZE:
        return
    unit = line.unitVector()
    step = QPointF(unit.dx(), unit.dy())
    start = line.p1() + step * inset
    end = line.p2() - step * inset
    painter.setPen(pen)
    painter.drawLine(start, end)
    normal = QPointF(-step.y(), step.x()) * (ARROW_HEAD_SIZE / 2)
    base = end - step * ARROW_HEAD_SIZE
    painter.setBrush(pen.color())
    painter.drawPolygon(QPolygonF([end, base + normal, base - normal]))
    painter.setBrush(Qt.BrushStyle.NoBrush)
