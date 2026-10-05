"""Rulers that label an ImageGraphicsView's image coordinates along one edge.

A Ruler is laid out beside its view, not inside it, and maps its own coordinates to the view's through global
coordinates. It reads the view's scene-to-viewport transform directly, so it assumes the view applies scale and
translation only, with no rotation or shear.
"""
import math
from typing import NamedTuple, Optional

from PySide6.QtCore import Qt, QPoint, QPointF, QRect, QSize, Signal
from PySide6.QtGui import QPainter, QColor, QPaintEvent, QPalette, QFont, QFontMetrics, QPolygonF
from PySide6.QtWidgets import QWidget, QSizePolicy

from src.config.application_config import AppConfig
from src.ui.widget.image_graphics_view import ImageGraphicsView

# Major tick steps are a base from this list times a power of ten.
TICK_STEP_BASES = (1, 2, 5)
# Minor ticks divide a major step into this many parts, using the first count that keeps them far enough apart.
MINOR_TICK_DIVISIONS = (10, 5, 4, 2)
MIN_MINOR_TICK_SPACING = 5.0
LABEL_PADDING = 3

# Tick lengths, as fractions of the ruler's thickness:
MAJOR_TICK_LENGTH = 1.0
MID_TICK_LENGTH = 0.5
MINOR_TICK_LENGTH = 0.25

HIGHLIGHT_ALPHA = 90
# The cursor marker's arrow reaches this fraction of the ruler's thickness in from the edge next to the view, and is
# as wide as it is deep.
CURSOR_ARROW_DEPTH = 0.6


def major_tick_step(scale: float, min_spacing: float) -> int:
    """Returns the smallest 1/2/5 x 10^n step, in image pixels, whose ticks are at least `min_spacing` screen pixels
    apart at the given scale."""
    assert scale > 0
    magnitude = 1
    while True:
        for base in TICK_STEP_BASES:
            step = base * magnitude
            if step * scale >= min_spacing:
                return step
        magnitude *= 10


def minor_tick_step(major_step: int, scale: float, min_spacing: float = MIN_MINOR_TICK_SPACING) -> int:
    """Returns the step between minor ticks, in image pixels, or `major_step` if no division fits.

    Minor steps are whole pixels that evenly divide `major_step`, at least `min_spacing` screen pixels apart.
    """
    for divisions in MINOR_TICK_DIVISIONS:
        if major_step % divisions != 0:
            continue
        step = major_step // divisions
        if step * scale >= min_spacing:
            return step
    return major_step


def tick_values(start: float, end: float, step: int) -> list[int]:
    """Returns every multiple of `step` within [start, end]."""
    first = math.ceil(start / step) * step
    return list(range(first, math.floor(end) + 1, step))


class RulerTick(NamedTuple):
    """One tick mark: its image coordinate, its position along the ruler, its length fraction, and its label."""
    value: int
    position: float
    length: float
    label: Optional[str]


class RulerHighlight(NamedTuple):
    """A span of image coordinates to shade on a ruler, from `start` up to but not including `end`."""
    start: float
    end: float
    color: QColor


class Ruler(QWidget):
    """Labels one axis of an ImageGraphicsView's image coordinates, marking the cursor and any highlighted spans.

    Label size comes from AppConfig.RULER_FONT_SIZE, and the ruler's thickness follows it.
    """

    thickness_changed = Signal(int)

    def __init__(self, view: ImageGraphicsView, orientation: Qt.Orientation, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._view = view
        self._orientation = orientation
        self._highlights: list[RulerHighlight] = []
        self._cursor_position: Optional[float] = None
        self._label_font = QFont(self.font())
        self._thickness = 0
        if orientation == Qt.Orientation.Horizontal:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        else:
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        AppConfig().connect(self, AppConfig.RULER_FONT_SIZE, self._set_font_size)
        self._set_font_size(AppConfig().get(AppConfig.RULER_FONT_SIZE))
        view.view_changed.connect(self.update)
        view.cursor_moved.connect(self._cursor_moved_slot)

    def _set_font_size(self, point_size: int) -> None:
        """Applies a new label font size, resizing the ruler to fit it."""
        self._label_font.setPointSize(point_size)
        self._thickness = QFontMetrics(self._label_font).height() + LABEL_PADDING * 2
        if self._orientation == Qt.Orientation.Horizontal:
            self.setFixedHeight(self._thickness)
        else:
            self.setFixedWidth(self._thickness)
        self.update()
        self.thickness_changed.emit(self._thickness)

    @property
    def orientation(self) -> Qt.Orientation:
        """Returns whether this ruler labels the horizontal or the vertical axis."""
        return self._orientation

    @property
    def thickness(self) -> int:
        """Returns the ruler's fixed size across its axis."""
        return self._thickness

    @property
    def length(self) -> int:
        """Returns the ruler's size along its axis."""
        return self.width() if self._orientation == Qt.Orientation.Horizontal else self.height()

    @property
    def cursor_position(self) -> Optional[float]:
        """Returns the cursor marker's position along the ruler, or None if the cursor is outside the view."""
        return self._cursor_position

    def sizeHint(self) -> QSize:
        """Returns the fixed thickness across the axis, with no preferred length."""
        if self._orientation == Qt.Orientation.Horizontal:
            return QSize(0, self._thickness)
        return QSize(self._thickness, 0)

    @property
    def highlights(self) -> list[RulerHighlight]:
        """Returns the shaded spans."""
        return list(self._highlights)

    def set_highlights(self, highlights: list[RulerHighlight]) -> None:
        """Replaces the shaded spans."""
        if highlights != self._highlights:
            self._highlights = list(highlights)
            self.update()

    def _view_offset(self) -> QPointF:
        """Returns the view's viewport origin in this ruler's coordinates."""
        viewport = self._view.viewport()
        assert viewport is not None
        return self.mapFromGlobal(viewport.mapToGlobal(QPointF(0.0, 0.0)))

    def _axis_mapping(self) -> tuple[float, float]:
        """Returns (scale, origin): ruler position = scale * image coordinate + origin."""
        transform = self._view.viewportTransform()
        offset = self._view_offset()
        if self._orientation == Qt.Orientation.Horizontal:
            return transform.m11(), transform.dx() + offset.x()
        return transform.m22(), transform.dy() + offset.y()

    def image_to_ruler(self, value: float) -> float:
        """Maps an image coordinate on this ruler's axis to a position along the ruler."""
        scale, origin = self._axis_mapping()
        return scale * value + origin

    def ruler_to_image(self, position: float) -> float:
        """Maps a position along the ruler to an image coordinate on this ruler's axis."""
        scale, origin = self._axis_mapping()
        return (position - origin) / scale

    def _min_label_spacing(self, start: float, end: float) -> float:
        """Returns the screen spacing major ticks need so the widest visible label fits between them."""
        digits = len(str(int(max(abs(start), abs(end)))))
        widest_label = '-' + '8' * digits
        return QFontMetrics(self._label_font).horizontalAdvance(widest_label) + LABEL_PADDING * 2

    def ticks(self) -> list[RulerTick]:
        """Returns the tick marks visible along the ruler, in order."""
        scale, _ = self._axis_mapping()
        if scale <= 0 or self.length <= 0:
            return []
        start = self.ruler_to_image(0)
        end = self.ruler_to_image(self.length)
        major_step = major_tick_step(scale, self._min_label_spacing(start, end))
        minor_step = minor_tick_step(major_step, scale)
        mid_step = major_step // 2 if major_step % 2 == 0 and minor_step < major_step // 2 else None
        ticks = []
        for value in tick_values(start, end, minor_step):
            if value % major_step == 0:
                length = MAJOR_TICK_LENGTH
                label: Optional[str] = str(value)
            elif mid_step is not None and value % mid_step == 0:
                length = MID_TICK_LENGTH
                label = None
            else:
                length = MINOR_TICK_LENGTH
                label = None
            ticks.append(RulerTick(value, self.image_to_ruler(value), length, label))
        return ticks

    def _cursor_moved_slot(self, view_pos: Optional[QPoint]) -> None:
        """Moves the cursor marker to the view's cursor position, repainting only the old and new marker areas."""
        if view_pos is None:
            new_position = None
        else:
            ruler_pos = self.mapFromGlobal(self._view.mapToGlobal(QPointF(view_pos)))
            new_position = ruler_pos.x() if self._orientation == Qt.Orientation.Horizontal else ruler_pos.y()
        if new_position == self._cursor_position:
            return
        margin = self._thickness * CURSOR_ARROW_DEPTH / 2 + 2
        for position in (self._cursor_position, new_position):
            if position is not None:
                self.update(self._span_rect(position - margin, position + margin))
        self._cursor_position = new_position

    def _cursor_arrow(self, position: float) -> QPolygonF:
        """Returns the cursor marker's arrow, pointing at the view from the ruler's inner edge."""
        depth = self._thickness * CURSOR_ARROW_DEPTH
        half_width = depth / 2
        edge = float(self._thickness)
        if self._orientation == Qt.Orientation.Horizontal:
            return QPolygonF([QPointF(position, edge), QPointF(position - half_width, edge - depth),
                              QPointF(position + half_width, edge - depth)])
        return QPolygonF([QPointF(edge, position), QPointF(edge - depth, position - half_width),
                          QPointF(edge - depth, position + half_width)])

    def _span_rect(self, start: float, end: float, length: float = 1.0) -> QRect:
        """Returns the rectangle covering [start, end] along the ruler, reaching `length` of the thickness in from the
        edge next to the view."""
        start_px = int(math.floor(start))
        end_px = int(math.ceil(end))
        depth = max(1, round(self.thickness * length))
        if self._orientation == Qt.Orientation.Horizontal:
            return QRect(start_px, self.thickness - depth, end_px - start_px, depth)
        return QRect(self.thickness - depth, start_px, depth, end_px - start_px)

    def paintEvent(self, unused_event: Optional[QPaintEvent]) -> None:
        """Draws the background, highlighted spans, ticks, labels and cursor marker."""
        palette = self.palette()
        painter = QPainter(self)
        painter.fillRect(self.rect(), palette.color(QPalette.ColorRole.Button))
        for highlight in self._highlights:
            color = QColor(highlight.color)
            color.setAlpha(HIGHLIGHT_ALPHA)
            painter.fillRect(self._span_rect(self.image_to_ruler(highlight.start),
                                             self.image_to_ruler(highlight.end)), color)

        text_color = palette.color(QPalette.ColorRole.ButtonText)
        painter.setPen(text_color)
        painter.setFont(self._label_font)
        ascent = QFontMetrics(self._label_font).ascent()
        for tick in self.ticks():
            position = round(tick.position)
            depth = round(self.thickness * tick.length)
            if self._orientation == Qt.Orientation.Horizontal:
                painter.drawLine(position, self.thickness - depth, position, self.thickness)
                if tick.label is not None:
                    painter.drawText(position + LABEL_PADDING, LABEL_PADDING + ascent, tick.label)
            else:
                painter.drawLine(self.thickness - depth, position, self.thickness, position)
                if tick.label is not None:
                    # Rotated labels read bottom to top, placed just below their tick:
                    label_width = painter.fontMetrics().horizontalAdvance(tick.label)
                    painter.save()
                    painter.translate(LABEL_PADDING + ascent, position + LABEL_PADDING + label_width)
                    painter.rotate(-90)
                    painter.drawText(0, 0, tick.label)
                    painter.restore()

        if self._cursor_position is not None:
            position = round(self._cursor_position)
            painter.setPen(text_color)
            if self._orientation == Qt.Orientation.Horizontal:
                painter.drawLine(position, 0, position, self.thickness)
            else:
                painter.drawLine(0, position, self.thickness, position)
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(palette.color(QPalette.ColorRole.Button))
            painter.setBrush(text_color)
            painter.drawPolygon(self._cursor_arrow(position + 0.5))
            painter.restore()

        painter.setPen(palette.color(QPalette.ColorRole.Mid))
        if self._orientation == Qt.Orientation.Horizontal:
            painter.drawLine(0, self.thickness - 1, self.width(), self.thickness - 1)
        else:
            painter.drawLine(self.thickness - 1, 0, self.thickness - 1, self.height())
        painter.end()
