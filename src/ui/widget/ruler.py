"""Rulers that label an ImageGraphicsView's image coordinates along one edge.

A Ruler is laid out beside its view, not inside it, and maps its own coordinates to the view's through global
coordinates. It reads the view's scene-to-viewport transform directly, so it assumes the view applies scale and
translation only, with no rotation or shear.

With a RulerGuides model, a ruler also draws handles for the guides on the other axis and handles the mouse gestures
that create, move and delete guides. Guide lines in the image are drawn by the owner of the model, which follows
`Ruler.guide_drag`.
"""
import math
from typing import NamedTuple, Optional

from PySide6.QtCore import Qt, QPoint, QPointF, QRect, QSize, Signal
from PySide6.QtGui import QAction, QContextMenuEvent, QMouseEvent, QPainter, QColor, QPaintEvent, QPalette, QFont, \
    QFontMetrics, QPolygonF
from PySide6.QtWidgets import QApplication, QMenu, QWidget, QSizePolicy

from src.config.application_config import AppConfig
from src.ui.widget.image_graphics_view import ImageGraphicsView
from src.ui.widget.ruler_guides import RulerGuides
from src.util.visual.contrast_color import with_min_contrast

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

# Highlight bars are this fraction of the label font's height thick, and at least MIN_HIGHLIGHT_BAR_THICKNESS pixels.
HIGHLIGHT_BAR_SCALE = 0.4
MIN_HIGHLIGHT_BAR_THICKNESS = 4
# Highlight colors are adjusted to at least this WCAG contrast ratio against the ruler background.
MIN_HIGHLIGHT_CONTRAST = 4.5
# The cursor marker's arrow reaches this fraction of the ruler's thickness in from the edge next to the view, and is
# as wide as it is deep.
CURSOR_ARROW_DEPTH = 0.6
# The guide handle's circle is this fraction of the ruler's thickness across.
GUIDE_HANDLE_DIAMETER = 0.5
# A guide handle's hit area reaches at least this many pixels to either side of its position along the ruler.
MIN_GUIDE_HANDLE_HIT_RADIUS = 8

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.widget.ruler'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


MENU_ACTION_DELETE_GUIDE = _tr('Delete guide')


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
    """A span of image coordinates to mark on a ruler, from `start` up to but not including `end`.

    `lane` picks the highlight bar's row, counting out from the edge next to the view, and must be less than the
    ruler's `highlight_lanes`. `color` is drawn opaque, with its lightness adjusted to contrast with the ruler.
    """
    start: float
    end: float
    color: QColor
    lane: int


class GuideDrag(NamedTuple):
    """The guide gesture in progress on a ruler.

    `orientation` is the dragged guide's orientation. `original` is the coordinate of the guide being moved, or None
    when the gesture creates a guide. `position` is where the guide would end up if released now, or None if release
    would not leave a guide there (a create outside the view, or a move that would delete the guide).
    """
    orientation: Qt.Orientation
    original: Optional[int]
    position: Optional[int]

    def applied_to(self, coordinates: list[int]) -> list[int]:
        """Returns the coordinates of the guides with this orientation as they would be drawn mid-gesture: the moved
        guide at its new coordinate, a guide pending deletion left out, and a guide being created added."""
        result = list(coordinates)
        if self.original is None:
            if self.position is not None:
                result.append(self.position)
        elif self.original in result:
            index = result.index(self.original)
            if self.position is None:
                del result[index]
            else:
                result[index] = self.position
        return result


class Ruler(QWidget):
    """Labels one axis of an ImageGraphicsView's image coordinates, marking the cursor and any highlighted spans.

    Thickness is the label height, set by AppConfig.RULER_FONT_SIZE, plus a strip of highlight bar lanes along the
    edge next to the view. Ticks start above that strip, so highlights never cover them.

    A ruler built with `guides` draws a handle for each guide on the other axis (a horizontal ruler shows the vertical
    guides), and `guide_drag_changed` fires as a guide gesture starts, moves and ends. `guide_menu_actions` are added
    to the context menu after the guide's own Delete action.
    """

    thickness_changed = Signal(int)
    guide_drag_changed = Signal()

    def __init__(self, view: ImageGraphicsView, orientation: Qt.Orientation, parent: Optional[QWidget] = None,
                 guides: Optional[RulerGuides] = None) -> None:
        super().__init__(parent)
        self._view = view
        self._orientation = orientation
        self._guides = guides
        self._guide_drag: Optional[GuideDrag] = None
        self._menu_actions: list[QAction] = []
        self._highlights: list[RulerHighlight] = []
        self._cursor_position: Optional[float] = None
        self._label_font = QFont(self.font())
        self._thickness = 0
        self._highlight_lanes = 0
        self._bar_thickness = MIN_HIGHLIGHT_BAR_THICKNESS
        if orientation == Qt.Orientation.Horizontal:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        else:
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        AppConfig().connect(self, AppConfig.RULER_FONT_SIZE, self._set_font_size)
        self._set_font_size(AppConfig().get(AppConfig.RULER_FONT_SIZE))
        view.view_changed.connect(self.update)
        view.cursor_moved.connect(self._cursor_moved_slot)
        if guides is not None:
            guides.guides_changed.connect(self.update)

    def _set_font_size(self, point_size: int) -> None:
        """Applies a new label font size, resizing the ruler to fit it."""
        self._label_font.setPointSize(point_size)
        self._update_thickness()

    def _update_thickness(self) -> None:
        """Resizes the ruler to fit its labels and highlight lanes."""
        font_height = QFontMetrics(self._label_font).height()
        self._bar_thickness = max(MIN_HIGHLIGHT_BAR_THICKNESS, round(font_height * HIGHLIGHT_BAR_SCALE))
        self._thickness = font_height + LABEL_PADDING * 2 + self._highlight_strip_thickness
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
    def highlight_lanes(self) -> int:
        """Returns the number of highlight bar rows reserved along the edge next to the view."""
        return self._highlight_lanes

    @highlight_lanes.setter
    def highlight_lanes(self, lanes: int) -> None:
        """Reserves room for a number of highlight bar rows, resizing the ruler."""
        if lanes != self._highlight_lanes:
            self._highlight_lanes = lanes
            self._update_thickness()

    @property
    def _highlight_strip_thickness(self) -> int:
        """Returns the space reserved for highlight bars, including the gap above them."""
        return 0 if self._highlight_lanes == 0 else self._highlight_lanes * self._bar_thickness + 1

    @property
    def _tick_base(self) -> int:
        """Returns the distance from the edge next to the view to where ticks start."""
        return 1 + self._highlight_strip_thickness

    def highlight_color(self, highlight: RulerHighlight) -> QColor:
        """Returns the opaque color a highlight's bar is drawn with, adjusted to contrast with the background."""
        background = self.palette().color(QPalette.ColorRole.Button)
        return with_min_contrast(highlight.color, background, MIN_HIGHLIGHT_CONTRAST)

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

    def _span_rect(self, start: float, end: float, inset: int = 0, depth: Optional[int] = None) -> QRect:
        """Returns the rectangle covering [start, end] along the ruler, starting `inset` pixels in from the edge next
        to the view and reaching `depth` pixels further, or to the far edge if `depth` is None."""
        start_px = int(math.floor(start))
        end_px = int(math.ceil(end))
        if depth is None:
            depth = self.thickness - inset
        far_edge = self.thickness - inset - depth
        if self._orientation == Qt.Orientation.Horizontal:
            return QRect(start_px, far_edge, end_px - start_px, depth)
        return QRect(far_edge, start_px, depth, end_px - start_px)

    def _draw_highlights(self, painter: QPainter, cap_color: QColor) -> None:
        """Draws each highlight as a bar in its lane, then end caps across every lane so span edges show at any color.

        Caps go on after every bar, so a bar in another lane can't cover them.
        """
        spans: list[tuple[int, int]] = []
        for highlight in self._highlights:
            if highlight.lane >= self._highlight_lanes:
                continue
            start = round(self.image_to_ruler(highlight.start))
            end = round(self.image_to_ruler(highlight.end))
            inset = 1 + highlight.lane * self._bar_thickness
            painter.fillRect(self._span_rect(start, end, inset, self._bar_thickness), self.highlight_color(highlight))
            spans.append((start, end))
        strip_depth = self._highlight_lanes * self._bar_thickness
        for start, end in spans:
            for cap_position in (start, end - 1):
                painter.fillRect(self._span_rect(cap_position, cap_position + 1, 1, strip_depth), cap_color)

    @property
    def guide_orientation(self) -> Qt.Orientation:
        """Returns the orientation of the guides whose handles this ruler shows: the opposite of its own."""
        if self._orientation == Qt.Orientation.Horizontal:
            return Qt.Orientation.Vertical
        return Qt.Orientation.Horizontal

    @property
    def guide_drag(self) -> Optional[GuideDrag]:
        """Returns the guide gesture in progress, or None."""
        return self._guide_drag

    @property
    def menu_actions(self) -> list[QAction]:
        """Returns the actions added to the context menu after Delete guide."""
        return list(self._menu_actions)

    @menu_actions.setter
    def menu_actions(self, actions: list[QAction]) -> None:
        self._menu_actions = list(actions)

    def _along(self, point: QPointF | QPoint) -> float:
        """Returns a ruler-local point's position along the ruler."""
        return point.x() if self._orientation == Qt.Orientation.Horizontal else point.y()

    def _across(self, point: QPointF | QPoint) -> float:
        """Returns a ruler-local point's position across the ruler."""
        return point.y() if self._orientation == Qt.Orientation.Horizontal else point.x()

    def _handle_hit_radius(self) -> float:
        return max(MIN_GUIDE_HANDLE_HIT_RADIUS, self._thickness * GUIDE_HANDLE_DIAMETER / 2)

    def guide_handle_at(self, position: QPointF | QPoint) -> Optional[int]:
        """Returns the coordinate of the guide whose handle is under a ruler-local position, or None.

        The hit area is wider than the drawn circle and spans the ruler's whole thickness. The nearest handle wins.
        """
        if self._guides is None or not 0 <= self._across(position) <= self._thickness:
            return None
        along = self._along(position)
        nearest: Optional[int] = None
        nearest_distance = self._handle_hit_radius() + 1
        for coordinate in self._guides.positions(self.guide_orientation):
            distance = abs(self.image_to_ruler(coordinate) - along)
            if distance < nearest_distance:
                nearest, nearest_distance = coordinate, distance
        return nearest

    def _clamped_coordinate(self, value: float, extent: int) -> int:
        return max(0, min(extent, round(value)))

    def _guide_position_at_view(self, global_pos: QPointF, orientation: Qt.Orientation) -> Optional[int]:
        """Returns the whole-pixel image coordinate under a global position on the fixed axis of a guide with the given
        orientation, clamped to the image, or None if the position is outside the view."""
        size = self._view.content_size
        viewport = self._view.viewport()
        if size is None or viewport is None:
            return None
        viewport_pos = viewport.mapFromGlobal(global_pos)
        if not viewport.rect().contains(viewport_pos.toPoint()):
            return None
        scene_pos = self._view.mapToScene(viewport_pos.toPoint())
        if orientation == Qt.Orientation.Horizontal:
            return self._clamped_coordinate(scene_pos.y(), size.height())
        return self._clamped_coordinate(scene_pos.x(), size.width())

    def _guide_extent(self) -> int:
        size = self._view.content_size
        if size is None:
            return 0
        return size.height() if self.guide_orientation == Qt.Orientation.Horizontal else size.width()

    def _set_guide_drag(self, drag: Optional[GuideDrag]) -> None:
        if drag != self._guide_drag:
            self._guide_drag = drag
            self.update()
            self.guide_drag_changed.emit()

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:  # pylint: disable=invalid-name  # Qt override
        """Starts moving the guide under a left press, or creating a guide on a press elsewhere on the ruler."""
        if event is None or self._guides is None or event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        event.accept()
        handle = self.guide_handle_at(event.position())
        if handle is not None:
            if not self._guides.locked:
                self._set_guide_drag(GuideDrag(self.guide_orientation, handle, handle))
        else:
            # A guide created from this ruler runs along it: the top ruler makes horizontal guides.
            self._set_guide_drag(GuideDrag(self._orientation, None, None))

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:  # pylint: disable=invalid-name  # Qt override
        """Updates the guide gesture in progress."""
        drag = self._guide_drag
        if event is None or drag is None:
            super().mouseMoveEvent(event)
            return
        event.accept()
        if drag.original is None:
            position = self._guide_position_at_view(event.globalPosition(), drag.orientation)
        else:
            across = self._across(event.position())
            distance = -across if across < 0 else across - self._thickness
            if distance > self._thickness:
                position = None
            else:
                position = self._clamped_coordinate(self.ruler_to_image(self._along(event.position())),
                                                    self._guide_extent())
        self._set_guide_drag(drag._replace(position=position))

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:  # pylint: disable=invalid-name  # Qt override
        """Finishes the guide gesture: creates, moves or deletes a guide."""
        drag = self._guide_drag
        if event is None or drag is None or event.button() != Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)
            return
        event.accept()
        assert self._guides is not None
        self._guide_drag = None
        if drag.original is None:
            if drag.position is not None:
                self._guides.add(drag.orientation, drag.position)
        elif drag.position is None:
            self._guides.remove(drag.orientation, drag.original)
        else:
            self._guides.move(drag.orientation, drag.original, drag.position)
        self.update()
        self.guide_drag_changed.emit()

    def build_context_menu(self, position: QPoint) -> QMenu:
        """Returns the context menu for a ruler-local position: Delete guide if a handle is there, then the actions
        in `menu_actions`. The caller owns the menu."""
        menu = QMenu(self)
        handle = self.guide_handle_at(position)
        if handle is not None and self._guides is not None:
            guides = self._guides
            orientation = self.guide_orientation
            delete_action = QAction(MENU_ACTION_DELETE_GUIDE, menu)
            delete_action.triggered.connect(lambda: guides.remove(orientation, handle))
            menu.addAction(delete_action)
            menu.addSeparator()
        for action in self._menu_actions:
            menu.addAction(action)
        return menu

    def contextMenuEvent(self, event: Optional[QContextMenuEvent]) -> None:  # pylint: disable=invalid-name
        """Opens the context menu for the position under the cursor."""
        if event is None:
            return
        menu = self.build_context_menu(event.pos())
        menu.exec(event.globalPos())
        menu.deleteLater()

    def _draw_guide_handles(self, painter: QPainter) -> None:
        """Draws a circle for each guide on the other axis, against the ruler's inner edge."""
        if self._guides is None:
            return
        palette = self.palette()
        fill = palette.color(QPalette.ColorRole.Mid if self._guides.locked else QPalette.ColorRole.Highlight)
        coordinates = self._guides.positions(self.guide_orientation)
        if self._guide_drag is not None and self._guide_drag.original is not None:
            coordinates = self._guide_drag.applied_to(coordinates)
        diameter = self._thickness * GUIDE_HANDLE_DIAMETER
        center_across = self._thickness - 1 - diameter / 2
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QColor(0, 0, 0))
        painter.setBrush(fill)
        for coordinate in coordinates:
            along = self.image_to_ruler(coordinate) + 0.5
            center = QPointF(along, center_across) if self._orientation == Qt.Orientation.Horizontal \
                else QPointF(center_across, along)
            painter.drawEllipse(center, diameter / 2, diameter / 2)
        painter.restore()

    def paintEvent(self, unused_event: Optional[QPaintEvent]) -> None:
        """Draws the background, highlighted spans, ticks, labels and cursor marker."""
        palette = self.palette()
        painter = QPainter(self)
        painter.fillRect(self.rect(), palette.color(QPalette.ColorRole.Button))
        text_color = palette.color(QPalette.ColorRole.ButtonText)
        self._draw_highlights(painter, text_color)

        painter.setPen(text_color)
        painter.setFont(self._label_font)
        ascent = QFontMetrics(self._label_font).ascent()
        for tick in self.ticks():
            position = round(tick.position)
            tick_space = self.thickness - self._tick_base
            depth = round(tick_space * tick.length)
            base = self.thickness - self._tick_base
            if self._orientation == Qt.Orientation.Horizontal:
                painter.drawLine(position, base - depth, position, base)
                if tick.label is not None:
                    painter.drawText(position + LABEL_PADDING, LABEL_PADDING + ascent, tick.label)
            else:
                painter.drawLine(base - depth, position, base, position)
                if tick.label is not None:
                    # Rotated labels read bottom to top, placed just below their tick:
                    label_width = painter.fontMetrics().horizontalAdvance(tick.label)
                    painter.save()
                    painter.translate(LABEL_PADDING + ascent, position + LABEL_PADDING + label_width)
                    painter.rotate(-90)
                    painter.drawText(0, 0, tick.label)
                    painter.restore()

        self._draw_guide_handles(painter)

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
