"""Widgets along an ImageGraphicsView's edge that draw ruler guide handles and take the gestures that move them.

`GuideHandleBar` holds what a ruler and a handle strip share: mapping image coordinates to positions along the bar,
hit-testing handles, the move and drag-off-delete gestures, and the Delete guide menu. `Ruler` extends it with ticks
and guide creation. `GuideHandleStrip` stands in for a hidden ruler, so guides stay adjustable without the rulers.

A bar maps its own coordinates to the view's through global coordinates, so it can sit anywhere beside or over the
view. It reads the view's scene-to-viewport transform directly, so it assumes the view applies scale and translation
only, with no rotation or shear.
"""
import math
from typing import NamedTuple, Optional

from PySide6.QtCore import Qt, QEvent, QObject, QPoint, QPointF, QRect, Signal
from PySide6.QtGui import QAction, QContextMenuEvent, QMouseEvent, QPainter, QColor, QPaintEvent, QPalette, QRegion
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from src.ui.canvas_extras import CanvasExtraCategory, CanvasExtras
from src.ui.widget.image_graphics_view import ImageGraphicsView
from src.ui.widget.ruler_guides import RulerGuides

# The guide handle's circle is this fraction of the bar's thickness across.
GUIDE_HANDLE_DIAMETER = 0.5
# A guide handle's hit area reaches at least this many pixels to either side of its position along the bar.
MIN_GUIDE_HANDLE_HIT_RADIUS = 8

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.widget.guide_handle_bar'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


MENU_ACTION_DELETE_GUIDE = _tr('Delete guide')


class GuideDrag(NamedTuple):
    """The guide gesture in progress on a bar.

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


class GuideHandleBar(QWidget):
    """A strip along one axis of an ImageGraphicsView that draws a handle for each guide on the other axis and takes
    the gestures that move and delete them.

    A horizontal bar shows the vertical guides. A press on a handle starts a move, unless the guides are locked.
    Releasing more than one bar thickness off the bar across its axis deletes the guide. `guide_drag_changed` fires as
    a gesture starts, moves and ends. `menu_actions` are added to the context menu after a handle's Delete guide
    action.

    Subclasses set `thickness` and pick where handles sit across the bar with `_handle_center_across`.
    """

    guide_drag_changed = Signal()

    def __init__(self, view: ImageGraphicsView, orientation: Qt.Orientation, guides: Optional[RulerGuides],
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._view = view
        self._orientation = orientation
        self._guides = guides
        self._guide_drag: Optional[GuideDrag] = None
        self._menu_actions: list[QAction] = []
        self._thickness = 0
        view.view_changed.connect(self._view_or_guides_changed)
        if guides is not None:
            guides.guides_changed.connect(self._view_or_guides_changed)

    def _view_or_guides_changed(self) -> None:
        """Repaints after the view's transform or the guides change."""
        self.update()

    @property
    def orientation(self) -> Qt.Orientation:
        """Returns whether this bar runs along the horizontal or the vertical axis."""
        return self._orientation

    @property
    def thickness(self) -> int:
        """Returns the bar's size across its axis."""
        return self._thickness

    @property
    def length(self) -> int:
        """Returns the bar's size along its axis."""
        return self.width() if self._orientation == Qt.Orientation.Horizontal else self.height()

    def _view_offset(self) -> QPointF:
        """Returns the view's viewport origin in this bar's coordinates."""
        viewport = self._view.viewport()
        assert viewport is not None
        return self.mapFromGlobal(viewport.mapToGlobal(QPointF(0.0, 0.0)))

    def _axis_mapping(self) -> tuple[float, float]:
        """Returns (scale, origin): bar position = scale * image coordinate + origin."""
        transform = self._view.viewportTransform()
        offset = self._view_offset()
        if self._orientation == Qt.Orientation.Horizontal:
            return transform.m11(), transform.dx() + offset.x()
        return transform.m22(), transform.dy() + offset.y()

    def image_to_position(self, value: float) -> float:
        """Maps an image coordinate on this bar's axis to a position along the bar."""
        scale, origin = self._axis_mapping()
        return scale * value + origin

    def position_to_image(self, position: float) -> float:
        """Maps a position along the bar to an image coordinate on this bar's axis."""
        scale, origin = self._axis_mapping()
        return (position - origin) / scale

    def _span_rect(self, start: float, end: float, inset: int = 0, depth: Optional[int] = None) -> QRect:
        """Returns the rectangle covering [start, end] along the bar, starting `inset` pixels in from the bar's
        bottom or right edge and reaching `depth` pixels further, or to the far edge if `depth` is None."""
        start_px = int(math.floor(start))
        end_px = int(math.ceil(end))
        if depth is None:
            depth = self._thickness - inset
        far_edge = self._thickness - inset - depth
        if self._orientation == Qt.Orientation.Horizontal:
            return QRect(start_px, far_edge, end_px - start_px, depth)
        return QRect(far_edge, start_px, depth, end_px - start_px)

    @property
    def guide_orientation(self) -> Qt.Orientation:
        """Returns the orientation of the guides whose handles this bar shows: the opposite of its own."""
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
        """Returns a bar-local point's position along the bar."""
        return point.x() if self._orientation == Qt.Orientation.Horizontal else point.y()

    def _across(self, point: QPointF | QPoint) -> float:
        """Returns a bar-local point's position across the bar."""
        return point.y() if self._orientation == Qt.Orientation.Horizontal else point.x()

    @property
    def _handle_diameter(self) -> float:
        return self._thickness * GUIDE_HANDLE_DIAMETER

    def _handle_center_across(self) -> float:
        """Returns the handle circles' center, measured across the bar from its top or left edge."""
        raise NotImplementedError()

    def _handle_hit_radius(self) -> float:
        return max(MIN_GUIDE_HANDLE_HIT_RADIUS, self._handle_diameter / 2)

    def _displayed_handles(self) -> list[int]:
        """Returns the coordinates of the guides whose handles are drawn, with a move in progress applied."""
        if self._guides is None:
            return []
        coordinates = self._guides.positions(self.guide_orientation)
        if self._guide_drag is not None and self._guide_drag.original is not None:
            coordinates = self._guide_drag.applied_to(coordinates)
        return coordinates

    def guide_handle_at(self, position: QPointF | QPoint) -> Optional[int]:
        """Returns the coordinate of the guide whose handle is under a bar-local position, or None.

        The hit area is wider than the drawn circle and spans the bar's whole thickness. The nearest handle wins.
        """
        if self._guides is None or not 0 <= self._across(position) <= self._thickness:
            return None
        along = self._along(position)
        nearest: Optional[int] = None
        nearest_distance = self._handle_hit_radius() + 1
        for coordinate in self._guides.positions(self.guide_orientation):
            distance = abs(self.image_to_position(coordinate) - along)
            if distance < nearest_distance:
                nearest, nearest_distance = coordinate, distance
        return nearest

    @staticmethod
    def _clamped_coordinate(value: float, extent: int) -> int:
        return max(0, min(extent, round(value)))

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

    def _press_off_handle(self) -> None:
        """Handles a left press that missed every handle. Bars that create guides override this."""

    def _created_guide_position(self, global_pos: QPointF, orientation: Qt.Orientation) -> Optional[int]:
        """Returns where a guide being created would land for a global cursor position: the whole-pixel image
        coordinate on the guide's fixed axis, clamped to the image, or None if the position is outside the view."""
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

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:  # pylint: disable=invalid-name  # Qt override
        """Starts moving the guide under a left press."""
        if event is None or self._guides is None or event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        event.accept()
        handle = self.guide_handle_at(event.position())
        if handle is None:
            self._press_off_handle()
        elif not self._guides.locked:
            self._set_guide_drag(GuideDrag(self.guide_orientation, handle, handle))

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:  # pylint: disable=invalid-name  # Qt override
        """Updates the guide gesture in progress."""
        drag = self._guide_drag
        if event is None or drag is None:
            super().mouseMoveEvent(event)
            return
        event.accept()
        if drag.original is None:
            position = self._created_guide_position(event.globalPosition(), drag.orientation)
        else:
            across = self._across(event.position())
            distance = -across if across < 0 else across - self._thickness
            if distance > self._thickness:
                position = None
            else:
                position = self._clamped_coordinate(self.position_to_image(self._along(event.position())),
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
        # Cleared before the model changes, so slots on guides_changed see no gesture in progress:
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
        """Returns the context menu for a bar-local position: Delete guide if a handle is there, then the actions in
        `menu_actions`. The caller owns the menu."""
        menu = QMenu(self)
        handle = self.guide_handle_at(position)
        if handle is not None and self._guides is not None:
            guides = self._guides
            orientation = self.guide_orientation
            delete_action = QAction(MENU_ACTION_DELETE_GUIDE, menu)
            delete_action.triggered.connect(lambda: guides.remove(orientation, handle))
            menu.addAction(delete_action)
            if len(self._menu_actions) > 0:
                menu.addSeparator()
        for action in self._menu_actions:
            menu.addAction(action)
        return menu

    def contextMenuEvent(self, event: Optional[QContextMenuEvent]) -> None:  # pylint: disable=invalid-name
        """Opens the context menu for the position under the cursor."""
        if event is None:
            return
        menu = self.build_context_menu(event.pos())
        if not menu.isEmpty():
            menu.exec(event.globalPos())
        menu.deleteLater()

    def _draw_guide_handles(self, painter: QPainter) -> None:
        """Draws a circle for each guide on the other axis, filled with the accent color, or an inert one if
        locked."""
        if self._guides is None:
            return
        palette = self.palette()
        fill = palette.color(QPalette.ColorRole.Mid if self._guides.locked else QPalette.ColorRole.Highlight)
        radius = self._handle_diameter / 2
        center_across = self._handle_center_across()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QColor(0, 0, 0))
        painter.setBrush(fill)
        for coordinate in self._displayed_handles():
            along = self.image_to_position(coordinate) + 0.5
            center = QPointF(along, center_across) if self._orientation == Qt.Orientation.Horizontal \
                else QPointF(center_across, along)
            painter.drawEllipse(center, radius, radius)
        painter.restore()


class GuideHandleStrip(GuideHandleBar):
    """Guide handles drawn over one edge of the view's viewport, for use while the rulers are hidden.

    The strip lays itself over the viewport's top edge (horizontal) or left edge (vertical), with each handle flush
    against that edge. It must be a sibling of the view or one of its ancestors' children, raised above the view.
    A mask limits it to the handles' hit areas, so presses anywhere else reach the view and its tools. It shows only
    while `shown` is set, a handle is in view, and the `GUIDES` category of `canvas_extras` (if given) is shown.
    """

    def __init__(self, view: ImageGraphicsView, orientation: Qt.Orientation, guides: RulerGuides,
                 parent: Optional[QWidget] = None, canvas_extras: Optional[CanvasExtras] = None) -> None:
        super().__init__(view, orientation, guides, parent)
        self._shown = False
        self._guides_category_shown = True
        if canvas_extras is not None:
            self._guides_category_shown = canvas_extras.is_shown(CanvasExtraCategory.GUIDES)
            canvas_extras.shown_changed.connect(self._canvas_extras_shown_changed)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.hide()
        view.installEventFilter(self)
        viewport = view.viewport()
        assert viewport is not None
        viewport.installEventFilter(self)
        self.guide_drag_changed.connect(self._update_mask)

    @property
    def thickness(self) -> int:
        """Returns the strip's size across its axis, which also sets the handle size."""
        return self._thickness

    @thickness.setter
    def thickness(self, thickness: int) -> None:
        if thickness != self._thickness:
            self._thickness = thickness
            self._update_geometry()

    @property
    def shown(self) -> bool:
        """Returns whether the strip shows when a handle is in view."""
        return self._shown

    @shown.setter
    def shown(self, shown: bool) -> None:
        if shown != self._shown:
            self._shown = shown
            self._update_geometry()

    def _canvas_extras_shown_changed(self, category: CanvasExtraCategory, shown: bool) -> None:
        if category == CanvasExtraCategory.GUIDES:
            self._guides_category_shown = shown
            self._update_mask()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # pylint: disable=invalid-name  # Qt override
        """Follows the viewport's geometry.

        The view's own resize event arrives before it resizes the viewport, so the viewport is watched for size and
        the view for position."""
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Move, QEvent.Type.Show) \
                and (watched is self._view or watched is self._view.viewport()):
            self._update_geometry()
        return super().eventFilter(watched, event)

    def _view_or_guides_changed(self) -> None:
        """Repaints and moves the mask after the view's transform or the guides change."""
        super()._view_or_guides_changed()
        self._update_mask()

    def _update_geometry(self) -> None:
        """Covers the viewport's edge, then refreshes the mask."""
        viewport = self._view.viewport()
        parent = self.parentWidget()
        if viewport is None or parent is None:
            return
        origin = viewport.mapTo(parent, QPoint(0, 0))
        if self._orientation == Qt.Orientation.Horizontal:
            self.setGeometry(QRect(origin.x(), origin.y(), viewport.width(), self._thickness))
        else:
            self.setGeometry(QRect(origin.x(), origin.y(), self._thickness, viewport.height()))
        self._update_mask()

    def handle_region(self) -> QRegion:
        """Returns the union of the hit areas of the handles in view, in strip coordinates."""
        region = QRegion()
        radius = self._handle_hit_radius()
        for coordinate in self._displayed_handles():
            along = self.image_to_position(coordinate)
            span = self._span_rect(along - radius, along + radius + 1)
            region = region.united(QRegion(span.intersected(self.rect())))
        return region

    def _update_mask(self) -> None:
        """Limits input to the handles' hit areas, and hides the strip when none are in view.

        During a gesture the strip stays visible, since hiding it would end its mouse grab, and drops its mask so the
        dragged handle draws wherever it goes.
        """
        if self._guide_drag is not None:
            self.clearMask()
            return
        region = self.handle_region()
        # An empty mask would remove masking, so the strip hides instead:
        if not self._shown or not self._guides_category_shown or region.isEmpty():
            self.hide()
            return
        self.setMask(region)
        self.show()
        self.raise_()

    def _handle_center_across(self) -> float:
        """Places each handle's outline against the viewport's edge."""
        return self._handle_diameter / 2 + 0.5

    def paintEvent(self, unused_event: Optional[QPaintEvent]) -> None:
        """Draws the handles over the view."""
        painter = QPainter(self)
        self._draw_guide_handles(painter)
        painter.end()
