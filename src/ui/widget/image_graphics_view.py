"""A QGraphicsView meant for displaying image content without using scrollbars."""
import math
from typing import Optional, cast
from weakref import ref

from PySide6.QtCore import Qt, QObject, QPoint, QPointF, QRect, QRectF, QSize, QMarginsF, Signal, QEvent, QMimeData
from PySide6.QtGui import (QPixmap, QImage, QPainter, QPen, QTransform, QResizeEvent, QMouseEvent, QCursor, QWheelEvent,
                           QEnterEvent, QSurfaceFormat, QDragEnterEvent, QDragMoveEvent, QDragLeaveEvent, QDropEvent)
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QWidget, QGraphicsView, QGraphicsScene, QSizePolicy

from src.config.application_config import AppConfig
from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.util.math_utils import clamp
from src.util.visual.contrast_color import contrast_color
from src.util.visual.geometry_utils import get_scaled_placement

MIN_IMAGE_ZOOM = 0.05
MAX_IMAGE_ZOOM = 64.0
ZOOM_FACTOR = 1.1
# Pixels moved by the "move more" keys:
MOVE_MORE_STEPS = 10


class ImageGraphicsView(QGraphicsView):
    """A QGraphicsView meant for displaying image content without using scrollbars."""

    scale_changed = Signal(float)
    offset_changed = Signal(QPoint)
    # Emitted after any change to the scene-to-widget mapping, including resizes, which emit neither signal above.
    view_changed = Signal()
    # Emitted with the cursor's widget position whenever set_cursor_pos runs, or None when the cursor leaves.
    cursor_moved = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None, use_keybindings=True) -> None:
        super().__init__(parent)
        # The view owns its scene: deleting the view deletes the scene and every item in it.
        self._scene = QGraphicsScene(self)
        self._content_size: QSize = QSize(0, 0)
        self._content_rect: Optional[QRect] = None
        self._background: Optional[QPixmap] = None
        # Weak references, excluding this view, which filters its own events:
        self._event_filters: list[ref[QObject]] = []
        self._last_widget_cursor_pos: Optional[QPoint] = None
        self._last_scene_cursor_pos: Optional[QPointF] = None
        self._centered_on = QPointF(self.width() // 2, self.height() // 2)
        self._mouse_navigation_enabled = True

        self._default_content_scale = 1.0
        self._content_scale_adjustment = 0.0
        self._offset = QPointF(0.0, 0.0)
        self._widget_drag_point: Optional[QPoint] = None
        # Space-held panning: whether the pan key is down, whether a left-button drag started while it was, and the
        # cursor to restore when the hold ends:
        self._pan_key_held = False
        self._key_pan_drag = False
        self._cursor_before_pan: Optional[QCursor] = None

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

        self._opengl_view: Optional[QOpenGLWidget] = None

        def _update_render_mode(use_opengl: bool) -> None:
            if use_opengl and self._opengl_view is None:
                self._opengl_view = QOpenGLWidget()
                surface_format = QSurfaceFormat()
                surface_format.setSamples(4)
                self._opengl_view.setFormat(surface_format)
                self.setViewport(self._opengl_view)
            elif not use_opengl and self._opengl_view is not None:
                # noinspection PyTypeChecker
                self.setViewport(None)
                self._opengl_view = None
        _update_render_mode(AppConfig().get(AppConfig.OPENGL_ACCELERATION))
        AppConfig().connect(self, AppConfig.OPENGL_ACCELERATION, _update_render_mode)

        self.setScene(self._scene)
        self.installEventFilter(self)
        self._register_pan_key()

        if use_keybindings:
            # Bind directional navigation and generation area keys:
            def _toggle_zoom_if_visible() -> bool:
                if not self.isVisible():
                    return False
                self.toggle_zoom()
                return True
            HotkeyFilter.instance().register_config_keybinding(f'ImageGraphicsView_{id(self)}_toggle_zoom',
                                                               _toggle_zoom_if_visible, KeyConfig.ZOOM_TOGGLE)
            for pan_key, scroll_key, scroll_more_key, offset in (
                    (KeyConfig.PAN_LEFT, KeyConfig.MOVE_LEFT, KeyConfig.MOVE_LEFT_MORE, (-1.0, 0.0)),
                    (KeyConfig.PAN_RIGHT, KeyConfig.MOVE_RIGHT, KeyConfig.MOVE_RIGHT_MORE, (1.0, 0.0)),
                    (KeyConfig.PAN_UP, KeyConfig.MOVE_UP, KeyConfig.MOVE_UP_MORE, (0.0, -1.0)),
                    (KeyConfig.PAN_DOWN, KeyConfig.MOVE_DOWN, KeyConfig.MOVE_DOWN_MORE, (0.0, 1.0))):
                dx, dy = offset
                # Bind view panning:

                def _pan(x=dx, y=dy) -> bool:
                    if not self.isVisible():
                        return False
                    self.offset = QPointF(self.offset.x() + x, self.offset.y() + y)
                    self.resizeEvent(None)
                    return True
                binding_id = f'ImageGraphicsView_{id(self)}_{pan_key}'
                HotkeyFilter.instance().register_config_keybinding(binding_id, _pan, pan_key)

                # Bind to abstract content scrolling method:
                for config_key, steps in ((scroll_key, 1), (scroll_more_key, MOVE_MORE_STEPS)):
                    def _scroll(x=dx * steps, y=dy * steps) -> bool:
                        if not self.isVisible():
                            return False
                        return self.scroll_content(x, y)
                    binding_id = f'ImageGraphicsView_{id(self)}_{config_key}'
                    HotkeyFilter.instance().register_config_keybinding(binding_id, _scroll, config_key)

            # Bind zoom keys:
            for config_key, multiplier in ((KeyConfig.ZOOM_IN, ZOOM_FACTOR), (KeyConfig.ZOOM_OUT, 1.0 / ZOOM_FACTOR)):
                def _zoom(change=multiplier) -> bool:
                    if not self.isVisible():
                        return False
                    self._zoom_step(change)
                    return True
                binding_id = f'ImageGraphicsView_{id(self)}_{config_key}'
                HotkeyFilter.instance().register_config_keybinding(binding_id, _zoom, config_key)


    def _register_pan_key(self) -> None:
        """Tracks the pan key, which pans on left-button drags while it is held. Every view does this, including the
        ones without keybindings, so Space pans in the navigation window too. The binding holds the view weakly, and
        goes away with it."""
        view_ref = ref(self)

        def _set_held(held: bool) -> None:
            view = view_ref()
            if view is not None:
                view.set_pan_key_held(held)

        def _is_visible() -> bool:
            view = view_ref()
            return view is not None and view.isVisible()
        binding_id = f'ImageGraphicsView_{id(self)}_pan_key'
        HotkeyFilter.instance().register_held_key(binding_id, _set_held, KeyConfig.PAN_VIEW_KEY, _is_visible)
        self.destroyed.connect(lambda: HotkeyFilter.instance().remove_keybinding(binding_id))

    @property
    def mouse_navigation_enabled(self) -> bool:
        """Returns whether mouse events should be allowed to pan and zoom within the scene."""
        return self._mouse_navigation_enabled

    @mouse_navigation_enabled.setter
    def mouse_navigation_enabled(self, enabled: bool) -> None:
        self._mouse_navigation_enabled = enabled

    def scene_point_to_widget(self, scene_point: QPointF | QPoint) -> QPoint:
        """Maps a point from scene to widget coordinates."""
        if isinstance(scene_point, QPoint):
            scene_point = scene_point.toPointF()
        view_point = self.mapFromScene(scene_point)
        return self.viewport().mapTo(self, view_point)

    def widget_point_to_scene(self, widget_point: QPoint | QPointF) -> QPointF:
        """Maps a point from widget to scene coordinates."""
        if isinstance(widget_point, QPointF):
            widget_point = widget_point.toPoint()
        view_point = self.viewport().mapFromParent(widget_point)
        return self.mapToScene(view_point)

    def scene_rect_to_widget_rect(self, scene_rect: QRectF) -> QRect:
        """Maps a rectangle from scene to widget coordinates."""
        return QRect(self.scene_point_to_widget(scene_rect.topLeft()),
                     self.scene_point_to_widget(scene_rect.bottomRight()))

    def widget_rect_to_scene_rect(self, widget_rect: QRect) -> QRectF:
        """Maps a rectangle from widget to scene coordinates."""
        top_left = widget_rect.topLeft()
        bottom_right = QPoint(top_left.x() + widget_rect.width(), top_left.y() + widget_rect.height())
        return QRectF(self.widget_point_to_scene(top_left), self.widget_point_to_scene(bottom_right))

    @property
    def visible_scene_bounds(self) -> QRectF:
        """Returns the actual scene bounds currently shown within the image view."""
        widget_bounds = self.rect()
        return self.widget_rect_to_scene_rect(widget_bounds)

    @property
    def widget_content_bounds(self) -> QRect:
        """Return the bounds where the main scene content appears within the widget."""
        scene_coordinates = QRectF(QPointF(), self._content_size.toSizeF())
        view_coordinates = self.mapFromScene(scene_coordinates).boundingRect().toRectF()
        final_coordinates = QRect(self.viewport().mapTo(self, view_coordinates.topLeft()).toPoint(),
                                  self.viewport().mapTo(self, view_coordinates.bottomRight()).toPoint())
        return final_coordinates

    def center_on_point(self, scene_pt: QPointF) -> None:
        """Scroll content to center scene point pos within the view.

        The offset setter moves the view relative to the stored center, so it keeps full precision: rounding it would
        add the rounding error to every pan step."""
        super().centerOn(scene_pt)
        self._centered_on = QPointF(scene_pt)

    def set_cursor(self, new_cursor: Optional[QCursor]) -> None:
        """Sets the cursor over the scene, or restores the default cursor if None. While the pan key is held, the hand
        cursor stays and the new cursor takes effect when the hold ends."""
        cursor = QCursor() if new_cursor is None else new_cursor
        if self._pan_key_held:
            self._cursor_before_pan = cursor
        else:
            self.setCursor(cursor)

    @property
    def pan_key_held(self) -> bool:
        """Returns whether the pan key is held, so that a left-button drag pans the view."""
        return self._pan_key_held

    def set_pan_key_held(self, held: bool) -> None:
        """Starts or ends a pan key hold, showing an open hand cursor while it lasts. The pan key binding calls this. A
        hold that ends mid-drag lets the drag finish."""
        if held == self._pan_key_held:
            return
        self._pan_key_held = held
        if held:
            if self._cursor_before_pan is None:
                self._cursor_before_pan = self.cursor()
            self.setCursor(Qt.CursorShape.ClosedHandCursor if self._key_pan_drag else Qt.CursorShape.OpenHandCursor)
        elif not self._key_pan_drag:
            self._restore_cursor_after_pan()

    def _restore_cursor_after_pan(self) -> None:
        cursor = self._cursor_before_pan
        self._cursor_before_pan = None
        if cursor is not None:
            self.setCursor(cursor)

    @property
    def cursor_pos(self) -> Optional[QPoint]:
        """Returns the last cursor position within the widget, or None if the cursor is outside it."""
        return self._last_widget_cursor_pos

    def set_cursor_pos(self, widget_cursor_pos: Optional[QPoint | QPointF]) -> None:
        """Records the cursor position within the widget, or None when it leaves, and emits cursor_moved."""
        if isinstance(widget_cursor_pos, QPointF):
            widget_cursor_pos = widget_cursor_pos.toPoint()
        self._last_widget_cursor_pos = widget_cursor_pos
        scene_cursor_pos = None if widget_cursor_pos is None else self.widget_point_to_scene(widget_cursor_pos)
        self._last_scene_cursor_pos = scene_cursor_pos
        self.cursor_moved.emit(widget_cursor_pos)

    def reset_scale(self) -> None:
        """Resets the scale to fit content in the view and re-centers the scene."""
        scale_will_change = self._content_scale_adjustment != 0.0
        self._content_scale_adjustment = 0.0
        self.offset = QPoint(0, 0)
        self.center_on_point(QPointF(self._content_size.width() / 2, self._content_size.height() / 2))
        self._update_scale_and_transform()
        if scale_will_change:
            self.scale_changed.emit(self.scene_scale)

    def zoom_to_actual_size(self) -> None:
        """Shows the content at 100% scale."""
        self.scene_scale = 1.0

    @property
    def is_at_default_view(self) -> bool:
        """Returns whether the scale and offsets are both at default values."""
        return self._content_scale_adjustment == 0.0 and self._offset == QPointF(0.0, 0.0)

    @property
    def content_size(self) -> Optional[QSize]:
        """Gets the actual (not displayed) size of the viewed image content."""
        return QSize(self._content_size.width(), self._content_size.height())

    @content_size.setter
    def content_size(self, new_size: QSize) -> None:
        """Updates the actual (not displayed) size of the viewed image content."""
        assert isinstance(new_size, QSize)
        if new_size == self._content_size:
            return
        self._content_size.setWidth(new_size.width())
        self._content_size.setHeight(new_size.height())
        self.center_on_point(QPointF(new_size.width() / 2, new_size.height() / 2))
        self._update_scale_and_transform()
        self.resetCachedContent()
        self.update()

    @property
    def scene_scale(self) -> float:
        """Returns the image content scale."""
        return self._default_content_scale + self._content_scale_adjustment

    @scene_scale.setter
    def scene_scale(self, new_scale: float) -> None:
        """Updates the image content scale, limiting minimum scale to 0.01.

        The scene point under the cursor stays in place, wherever the cursor is in the view. With no cursor position,
        the content center stays in place."""
        initial_scale = self.scene_scale
        new_scale = max(new_scale, 0.01)
        self._content_scale_adjustment = new_scale - self._default_content_scale

        view_content_bounds = self.widget_content_bounds
        if self._last_scene_cursor_pos is not None and self._last_widget_cursor_pos is not None:
            fixed_scene_pos = self._last_scene_cursor_pos
            fixed_widget_pos = self._last_widget_cursor_pos
        else:
            fixed_scene_pos = QPointF(self._content_size.width() / 2, self._content_size.height() / 2)
            fixed_widget_pos = view_content_bounds.center()

        scale_change = new_scale / initial_scale
        widget_center = QPointF(self.width() / 2, self.height() / 2)
        center_offset = widget_center - fixed_widget_pos
        center_offset.setX(center_offset.x() / scale_change)
        center_offset.setY(center_offset.y() / scale_change)
        new_widget_center = fixed_widget_pos + center_offset.toPoint()
        new_scene_center = self.widget_point_to_scene(new_widget_center)
        self.center_on_point(new_scene_center)
        self._update_scale_and_transform()

        new_fixed_scene_point = self.widget_point_to_scene(fixed_widget_pos)
        rounding_error = new_fixed_scene_point - fixed_scene_pos

        # Tweak offset/scale to deal with rounding errors:
        if abs(rounding_error.x()) > 0.01 or abs(rounding_error.y() > 0.01):
            horizontal_scroll = self.horizontalScrollBar()
            vertical_scroll = self.verticalScrollBar()
            x_scroll = int(horizontal_scroll.value() - rounding_error.x())
            y_scroll = int(vertical_scroll.value() - rounding_error.y())
            if horizontal_scroll.minimum() <= x_scroll <= horizontal_scroll.maximum() \
                    and vertical_scroll.minimum() <= y_scroll <= vertical_scroll.maximum():
                self.horizontalScrollBar().setValue(x_scroll)
                self.verticalScrollBar().setValue(y_scroll)
                self._offset -= rounding_error
                self._centered_on -= rounding_error
                self.offset_changed.emit(self._offset.toPoint())
            else:
                self.offset -= rounding_error
        self._update_scale_and_transform()
        self.scale_changed.emit(new_scale)

    def scale_without_fixed_scene_point(self, new_scale: float) -> None:
        """Updates image content scale without fixing any particular scene point within the view."""
        new_scale = max(new_scale, 0.01)
        self._content_scale_adjustment = new_scale - self._default_content_scale
        self.center_on_point(QPointF(self._content_size.width() / 2 + self._offset.x(),
                                     self._content_size.height() / 2 + self._offset.y()))
        self._update_scale_and_transform()
        self.scale_changed.emit(new_scale)

    @property
    def offset(self) -> QPointF:
        """Gets the image offset in image/scene pixels."""
        return QPointF(self._offset)

    @offset.setter
    def offset(self, new_offset: QPoint | QPointF) -> None:
        """Updates the image offset, moving the view center by the change.

        The change applies to the stored center, not one read back from the view, which would add up to a widget pixel
        of rounding to each call and send slow pan drags in the wrong direction."""
        change = (QPointF(new_offset) if isinstance(new_offset, QPoint) else new_offset) - self._offset
        self._offset.setX(float(new_offset.x()))
        self._offset.setY(float(new_offset.y()))
        self.center_on_point(self._centered_on + change)
        self.offset_changed.emit(self._offset.toPoint())
        self._update_scale_and_transform()

    @property
    def background(self) -> QPixmap | None:
        """Returns the background image content."""
        return self._background

    @background.setter
    def background(self, new_background: Optional[QImage | QPixmap]) -> None:
        """Updates the background image content."""
        if isinstance(new_background, QImage):
            self._background = QPixmap.fromImage(new_background)
        else:
            self._background = new_background
        self.resetCachedContent()

    def drawBackground(self, painter: Optional[QPainter], unused_rect: QRectF) -> None:
        """Renders any background image behind all scene contents."""
        if painter is None or self._background is None or self._content_rect is None:
            return
        content_rect = self.mapToScene(self._content_rect).boundingRect()
        if self._background is not None:
            painter.drawPixmap(content_rect, self._background, QRectF(self._background.rect()))
        border_size = float(self._border_size())
        margins = QMarginsF(border_size, border_size, border_size, border_size)
        border_rect = content_rect.marginsAdded(margins)
        painter.setPen(QPen(contrast_color(self), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        painter.drawRect(border_rect)

    def _update_scale_and_transform(self):
        if self.content_size is None:
            raise RuntimeError('ImageGraphicsView implementations must set content_size in __init__ before the ' +
                               'first resizeEvent is triggered')
        # Calculate default scale: Scene content is centered in the widget, and scaled evenly to the largest size with
        # the same aspect ratio that would fit within the widget bounds while leaving `self._border_size()` px empty:
        border_size = self._border_size()
        content_size = self._content_size
        if content_size is None:
            return
        self._content_rect = get_scaled_placement(self.size(), content_size, border_size)
        displayed_content_size = self._content_rect.size()
        new_scale = displayed_content_size.width() / content_size.width()
        scale_changed = new_scale != self._default_content_scale
        self._default_content_scale = new_scale

        # Apply scale changes and offset on top of the default scale. This approach means that changes to content size
        # will adjust the overall scale, while leaving the offset relative to the default scale unchanged:
        adjusted_scale = self._default_content_scale + self._content_scale_adjustment

        # Adjust the scene viewpoint/scrolling based on scale and offset:
        scene_window_width = displayed_content_size.width() / adjusted_scale
        scene_window_height = displayed_content_size.height() / adjusted_scale
        content_rect_f = QRectF(self._centered_on.x() - scene_window_width / 2,
                                self._centered_on.y() - scene_window_height // 2,
                                scene_window_width, scene_window_height)
        if content_rect_f != self._scene.sceneRect():
            self._scene.setSceneRect(content_rect_f)
        self.setTransform(QTransform.fromTranslate(self._offset.x(), self._offset.y())
                          * QTransform.fromScale(adjusted_scale, adjusted_scale))
        if scale_changed:
            self.scale_changed.emit(adjusted_scale)
        self.view_changed.emit()
        self.update()

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """Recalculate content size when the widget is resized."""
        super().resizeEvent(event)
        self._update_scale_and_transform()

    @property
    def border_size(self) -> int:
        """Returns the empty margin in pixels that the default scale leaves around the content."""
        return self._border_size()

    def _border_size(self) -> int:
        return (min(self.width(), self.height()) // 40) + 1

    def installEventFilter(self, event_filter: Optional[QObject]) -> None:
        """Extend default event filter management to deal with QGraphicsView mouse event oddities."""
        if event_filter is not None and event_filter is not self and event_filter not in self._live_event_filters():
            self._event_filters.append(ref(event_filter))
        super().installEventFilter(event_filter)

    def removeEventFilter(self, event_filter: Optional[QObject]) -> None:
        """Extend default event filter management to deal with QGraphicsView mouse event oddities."""
        self._event_filters = [filter_ref for filter_ref in self._event_filters
                               if filter_ref() is not None and filter_ref() is not event_filter]
        super().removeEventFilter(event_filter)

    def _live_event_filters(self) -> list[QObject]:
        return [event_filter for event_filter in (filter_ref() for filter_ref in self._event_filters)
                if event_filter is not None]

    def accepts_mime_data(self, mime_data: Optional[QMimeData]) -> bool:  # pylint: disable=unused-argument
        """Returns whether this view claims a drag with `mime_data` and handles its drop itself.

        The base view claims nothing, so every drag passes to the widgets above it. The
        future canvas drop feature returns True for the formats it applies.
        """
        return False

    def dragEnterEvent(self, event: Optional[QDragEnterEvent]) -> None:  # pylint: disable=invalid-name
        """Claims drags `accepts_mime_data` accepts, and passes all others up the widget chain.

        `QGraphicsScene.dragEnterEvent` accepts every drag enter, and
        `QApplication.notify` stops a drag's parent walk at the first widget that accepts.
        Forwarding every drag to the scene would make the viewport claim Qt's Wayland dock
        drag before it reaches the `QMainWindow`, so no dock could drop over a canvas.
        """
        if event is not None and self.accepts_mime_data(event.mimeData()):
            event.acceptProposedAction()
        elif event is not None:
            event.ignore()

    def dragMoveEvent(self, event: Optional[QDragMoveEvent]) -> None:  # pylint: disable=invalid-name
        """Keeps a claimed drag accepted, or passes an unclaimed one up the widget chain."""
        if event is not None and self.accepts_mime_data(event.mimeData()):
            event.acceptProposedAction()
        elif event is not None:
            event.ignore()

    def dragLeaveEvent(self, event: Optional[QDragLeaveEvent]) -> None:  # pylint: disable=invalid-name
        """Leaves the drag unaccepted; a drag `dragEnterEvent` never claimed never entered
        the scene, so the base handler has no state to clear."""
        if event is not None:
            event.ignore()

    def dropEvent(self, event: Optional[QDropEvent]) -> None:  # pylint: disable=invalid-name
        """Accepts a claimed drop, or passes one the view never claimed up the widget chain.

        The feature whose `accepts_mime_data` returns True applies the drop, usually by
        overriding this method."""
        if event is not None and self.accepts_mime_data(event.mimeData()):
            event.acceptProposedAction()
        elif event is not None:
            event.ignore()

    def mousePressEvent(self, event: Optional[QMouseEvent], get_result=False) -> Optional[bool]:
        """Custom mousePress handler to deal with QGraphicsView oddities. Child classes must call this implementation
           first with get_result=True, then exit without further action if it returns true.

        A left press while the pan key is held starts a pan drag, and no scene item or event filter sees it."""
        assert event is not None
        self.set_cursor_pos(self._view_event(event).position())
        if self._mouse_navigation_enabled and self._pan_key_held and event.buttons() == Qt.MouseButton.LeftButton:
            self._key_pan_drag = True
            self._widget_drag_point = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return True if get_result else None
        super().mousePressEvent(event)
        if event.buttons() == Qt.MouseButton.MiddleButton and self._mouse_navigation_enabled:
            self._widget_drag_point = event.position().toPoint()
        # A press accepted by a scene item belongs to that item, so filters only see presses the scene ignored.
        handled = False if event.isAccepted() else self._forward_to_event_filters(event)
        return handled if get_result else None

    def mouseMoveEvent(self, event: Optional[QMouseEvent], get_result=False) -> Optional[bool]:
        """Custom mouseMove handler to deal with QGraphicsView oddities. Child classes must call this implementation
           first with get_result=True, then exit without further action if it returns true."""
        assert event is not None
        self.set_cursor_pos(self._view_event(event).position())
        if self._key_pan_drag:
            if event.buttons() == Qt.MouseButton.LeftButton:
                self._pan_to(event.position().toPoint())
                event.accept()
                return True if get_result else None
            self._end_key_pan_drag()
        super().mouseMoveEvent(event)
        if self._mouse_navigation_enabled and self._widget_drag_point is not None and event is not None:
            if event.buttons() == Qt.MouseButton.MiddleButton:
                if not self._pan_to(event.position().toPoint()):
                    return None
            else:
                self._widget_drag_point = None
        handled = self._forward_to_event_filters(event)
        return handled if get_result else None

    def _pan_to(self, mouse_pt: QPoint) -> bool:
        """Pans by the distance the mouse has moved since the last pan step, returning whether the view moved."""
        assert self._widget_drag_point is not None
        scale = self.scene_scale
        x_off = (self._widget_drag_point.x() - mouse_pt.x()) / scale
        y_off = (self._widget_drag_point.y() - mouse_pt.y()) / scale
        distance = math.sqrt(x_off**2 + y_off**2)
        if distance < 1:
            return False
        self.offset = QPointF(self.offset.x() + x_off, self.offset.y() + y_off)
        self._widget_drag_point = mouse_pt
        return True

    def _end_key_pan_drag(self) -> None:
        """Ends a pan drag started with the pan key, restoring the cursor unless the key is still held."""
        self._key_pan_drag = False
        self._widget_drag_point = None
        if self._pan_key_held:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self._restore_cursor_after_pan()

    def mouseReleaseEvent(self, event: Optional[QMouseEvent], get_result=False) -> Optional[bool]:
        """Custom mouseRelease handler to deal with QGraphicsView oddities. Child classes must call this implementation
           first with get_result=True, then exit without further action if it returns true."""
        assert event is not None
        self.set_cursor_pos(self._view_event(event).position())
        if self._key_pan_drag:
            self._end_key_pan_drag()
            event.accept()
            return True if get_result else None
        super().mouseReleaseEvent(event)
        handled = self._forward_to_event_filters(event)
        return handled if get_result else None

    def wheelEvent(self, event: Optional[QWheelEvent]) -> None:  # pylint: disable=invalid-name  # Qt override
        """Offers wheel events to the other filters in installEventFilter's list before the scroll area forwards them
           to its scroll bars.

        This view filters its scroll bars' events, so its zoom handling in eventFilter runs when a wheel event reaches
        a scroll bar. A scroll bar that accepts the event stops it from reaching this view's filters, so they would
        never see it otherwise. An event no filter handles here can reach them a second time through normal
        propagation.
        """
        assert event is not None
        for event_filter in self._live_event_filters():
            if event_filter.eventFilter(self, event):
                event.accept()
                return
        super().wheelEvent(event)

    def _view_event(self, viewport_event: QMouseEvent) -> QMouseEvent:
        """Returns a copy of a mouse event the viewport received, positioned in this view's coordinates."""
        viewport = self.viewport()
        assert viewport is not None
        view_pos = viewport_event.position() + QPointF(viewport.pos())
        return QMouseEvent(viewport_event.type(), view_pos, viewport_event.scenePosition(),
                           viewport_event.globalPosition(), viewport_event.button(), viewport_event.buttons(),
                           viewport_event.modifiers(), viewport_event.pointingDevice())

    def _forward_to_event_filters(self, viewport_event: QMouseEvent) -> bool:
        """Passes a viewport mouse event to the filters in installEventFilter's list, in view coordinates, and returns
           whether one handled it.

        The event is accepted afterward so it doesn't also propagate to this view, where Qt would pass it to the same
        filters a second time.
        """
        view_event = self._view_event(viewport_event)
        viewport_event.accept()
        for event_filter in (self, *self._live_event_filters()):
            if event_filter.eventFilter(self, view_event):
                return True
        return False

    def _zoom_step(self, adjusted_multiplier: float, integer_scaling: bool = True):
        last_scale = self.scene_scale
        new_scale = last_scale * adjusted_multiplier
        if integer_scaling:
            if new_scale > last_scale:
                if new_scale > 1.0 > last_scale:
                    new_scale = 1.0
                elif new_scale > 2.0:
                    if math.floor(new_scale) == math.floor(last_scale):
                        new_scale = math.floor(last_scale) + 1.0
                    else:
                        new_scale = float(math.floor(new_scale))
            else:
                if last_scale > 1.0 > new_scale:
                    new_scale = 1.0
                elif new_scale > 2.0:
                    if math.ceil(new_scale) == math.ceil(last_scale):
                        new_scale = float(math.ceil(new_scale)) - 1.0
                    else:
                        new_scale = float(math.ceil(new_scale))
        self.scene_scale = clamp(new_scale, MIN_IMAGE_ZOOM, MAX_IMAGE_ZOOM)

    def zoom_in(self, multiplier: float = 1.0, integer_scaling: bool = True) -> None:
        """
        Zoom in towards view content by one step, optionally applying an extra multiplier and clamping to integer scale
         when appropriate."""
        self._zoom_step(multiplier * ZOOM_FACTOR, integer_scaling)

    def zoom_out(self, multiplier: float = 1.0, integer_scaling: bool = True) -> None:
        """
        Zoom out from view content by one step, optionally applying an extra multiplier and clamping to integer scale
         when appropriate."""
        self._zoom_step(1.0 / (multiplier * ZOOM_FACTOR), integer_scaling)

    def eventFilter(self, _source, event: Optional[QEvent]):
        """Intercept mouse wheel events, use for scrolling in zoom mode:"""
        assert event is not None
        if event.type() == QEvent.Type.Leave:
            self.set_cursor_pos(None)
        elif event.type() == QEvent.Type.Enter:
            event = cast(QEnterEvent, event)
            self.set_cursor_pos(event.position())
        elif event.type() == QEvent.Type.Wheel and self._mouse_navigation_enabled:
            event = cast(QWheelEvent, event)
            if event.angleDelta().y() == 0:
                return False
            if event.angleDelta().y() > 0:
                self.zoom_in()
            elif event.angleDelta().y() < 0 and self.scene_scale > MIN_IMAGE_ZOOM:
                self.zoom_out()
            self._update_scale_and_transform()
        return False

    # Naming conventions must match Qt:
    # pylint: disable=invalid-name
    def leaveEvent(self, event: Optional[QEvent]):
        """Clear the pixmap mouse cursor on leave."""
        self._last_widget_cursor_pos = None
        self.cursor_moved.emit(None)
        super().leaveEvent(event)

    def scrollContentsBy(self, dx: int, dy: int) -> None:  # pylint: disable=invalid-name  # Qt override
        """Report scrolling as a view change, since centering on a point scrolls without a transform update."""
        super().scrollContentsBy(dx, dy)
        self.view_changed.emit()

    def scroll_content(self, unused_dx: int | float, unused_dy: int | float) -> bool:
        """Scroll content by the given offset, returning whether content was able to move."""
        return False

    def toggle_zoom(self) -> None:
        """Zoom in on some area of focus, or back to the full scene. Bound to the 'Toggle Zoom' key."""
        raise NotImplementedError()

    def zoom_to_bounds(self, bounds: QRect) -> None:
        """Adjust viewport scale and offset to center a selected area in the view."""
        self.reset_scale()  # Reset zoom without clearing 'follow_generation_area' flag.
        margin = max(int(bounds.width() / 20), int(bounds.height() / 20), 10)
        content_size = self.content_size
        assert content_size is not None
        self.offset = QPoint(int(bounds.center().x() - (content_size.width() // 2)),
                             int(bounds.center().y() - (content_size.height() // 2)))
        self._content_scale_adjustment = (get_scaled_placement(self.size(), bounds.size(), 0).width()
                                          / (bounds.width() + margin)) - self._default_content_scale
        self.center_on_point(QPointF(self._content_size.width() / 2 + self._offset.x(),
                                     self._content_size.height() / 2 + self._offset.y()))
        self._update_scale_and_transform()
        self.scale_changed.emit(self.scene_scale)
