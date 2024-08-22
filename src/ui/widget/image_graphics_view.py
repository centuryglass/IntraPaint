"""A QGraphicsView meant for displaying image content without using scrollbars."""
import math
from typing import Optional, List, cast

from PySide6.QtCore import Qt, QObject, QPoint, QPointF, QRect, QRectF, QSize, QMarginsF, Signal, QEvent
from PySide6.QtGui import (QPixmap, QImage, QPainter, QPen, QTransform, QResizeEvent, QMouseEvent, QCursor, QWheelEvent,
                           QEnterEvent, QSurfaceFormat)
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QWidget, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QSizePolicy

from src.config.application_config import AppConfig
from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.util.contrast_color import contrast_color
from src.util.geometry_utils import get_scaled_placement

CURSOR_ITEM_Z_LEVEL = 9999
BASE_ZOOM_OFFSET = 0.05


class ImageGraphicsView(QGraphicsView):
    """A QGraphicsView meant for displaying image content without using scrollbars."""

    scale_changed = Signal(float)
    offset_changed = Signal(QPoint)

    def __init__(self, parent: Optional[QWidget] = None, use_keybindings=True) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene()
        self._content_size: QSize = QSize(0, 0)
        self._content_rect: Optional[QRect] = None
        self._background: Optional[QPixmap] = None
        self._event_filters: List[QObject] = []
        self._last_cursor_pos: Optional[QPoint] = None
        self._last_scene_cursor_pos: Optional[QPointF] = None
        self._cursor_pixmap: Optional[QPixmap] = None
        self._cursor_pixmap_item: Optional[QGraphicsPixmapItem] = None
        self._centered_on = QPointF(self.width() // 2, self.height() // 2)
        self._mouse_navigation_enabled = True

        self._scale = 1.0
        self._scale_adjustment = 0.0
        self._offset = QPointF(0.0, 0.0)
        self._drag_pt: Optional[QPoint] = None

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._opengl_view: Optional[QOpenGLWidget] = None

        def _update_render_mode(use_opengl: bool) -> None:
            if use_opengl and self._opengl_view is None:
                self._opengl_view = QOpenGLWidget()
                surface_format = QSurfaceFormat()
                surface_format.setSamples(4)
                self._opengl_view.setFormat(surface_format)
                self.setViewport(self._opengl_view)
            elif not use_opengl and self._opengl_view is not None:
                self.setViewport(None)
                self._opengl_view = None
        _update_render_mode(AppConfig().get(AppConfig.OPENGL_ACCELERATION))
        AppConfig().connect(self, AppConfig.OPENGL_ACCELERATION, _update_render_mode)

        self.setScene(self._scene)
        self.installEventFilter(self)

        if use_keybindings:
            # Bind directional navigation and image generation area keys:
            zoom_key = KeyConfig().get_keycodes(KeyConfig.ZOOM_TOGGLE)

            def _toggle_zoom_if_visible() -> bool:
                if not self.isVisible():
                    return False
                self.toggle_zoom()
                return True
            HotkeyFilter.instance().register_keybinding(_toggle_zoom_if_visible, zoom_key)
            for pan_key, scroll_key, offset in ((KeyConfig.PAN_LEFT, KeyConfig.MOVE_LEFT, (-1.0, 0.0)),
                                                (KeyConfig.PAN_RIGHT, KeyConfig.MOVE_RIGHT, (1.0, 0.0)),
                                                (KeyConfig.PAN_UP, KeyConfig.MOVE_UP, (0.0, -1.0)),
                                                (KeyConfig.PAN_DOWN, KeyConfig.MOVE_DOWN, (0.0, 1.0))):
                dx, dy = offset
                # Bind view panning:

                def _pan(mult, x=dx, y=dy) -> bool:
                    if not self.isVisible():
                        return False
                    self.offset = QPointF(self.offset.x() + x * mult, self.offset.y() + y * mult)
                    self.resizeEvent(None)
                    return True

                HotkeyFilter.instance().register_speed_modified_keybinding(_pan, pan_key)

                # Bind to abstract content scrolling method:
                def _scroll(mult, x=dx, y=dy) -> bool:
                    if not self.isVisible():
                        return False
                    return self.scroll_content(x * mult, y * mult)

                HotkeyFilter.instance().register_speed_modified_keybinding(_scroll, scroll_key)

            # Bind zoom keys:
            for config_key, direction in ((KeyConfig.ZOOM_IN, 1), (KeyConfig.ZOOM_OUT, -1)):
                zoom_offset = BASE_ZOOM_OFFSET * direction

                def _zoom(mult, change=zoom_offset) -> bool:
                    if not self.isVisible():
                        return False
                    self.scene_scale = self.scene_scale + change * mult
                    self.resizeEvent(None)
                    return True

                HotkeyFilter.instance().register_speed_modified_keybinding(_zoom, config_key)

    @property
    def mouse_navigation_enabled(self) -> bool:
        """Returns whether mouse events should pan through the scene or move the image generation area."""
        return self._mouse_navigation_enabled

    @mouse_navigation_enabled.setter
    def mouse_navigation_enabled(self, enabled: bool) -> None:
        self._mouse_navigation_enabled = enabled

    def center_on_point(self, pos: QPointF) -> None:
        """Cache the center point whenever it changes."""
        super().centerOn(pos)
        self._centered_on.setX(int(pos.x()))
        self._centered_on.setY(int(pos.y()))

    def set_cursor(self, new_cursor: QCursor | QPixmap | None):
        """Sets the cursor over the scene, optionally with custom rendering for large cursors.

        Parameters
        ----------
        new_cursor: QCursor or QPixmap or None
            If a QCursor is given, the cursor will be applied normally.  If None is given, the default cursor will be
            applied. If a QPixmap is given, a cross cursor will be used, and the pixmap will be drawn over the
            last mouse coordinates, centered on the mouse pointer. This allows extra large cursors to be used, which
            can cause problems with some windowing systems if applied normally.
        """
        scene = self.scene()
        assert scene is not None
        if isinstance(new_cursor, QPixmap):
            if self._cursor_pixmap_item is None:
                self._cursor_pixmap_item = QGraphicsPixmapItem(new_cursor)
                self._cursor_pixmap_item.setZValue(CURSOR_ITEM_Z_LEVEL)
            else:
                self._cursor_pixmap_item.setPixmap(new_cursor)
            if self._cursor_pixmap_item.scene() is None:
                scene.addItem(self._cursor_pixmap_item)
            self._cursor_pixmap_item.setScale(1 / self.scene_scale)
            self._cursor_pixmap_item.setVisible(self._last_cursor_pos is not None)
            if self._last_cursor_pos is not None:
                self.set_cursor_pos(self._last_cursor_pos)
            self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        else:
            if self._cursor_pixmap_item is not None and self._cursor_pixmap_item.scene() is not None:
                scene.removeItem(self._cursor_pixmap_item)
                self._cursor_pixmap_item.setVisible(False)
            if new_cursor is None:
                new_cursor = QCursor()
            self.setCursor(new_cursor)
        self.update()

    def set_cursor_pos(self, cursor_pos: Optional[QPoint | QPointF]) -> None:
        """Updates the last cursor position within the widget so that pixmap cursor rendering stays active."""
        if isinstance(cursor_pos, QPointF):
            cursor_pos = cursor_pos.toPoint()
        self._last_cursor_pos = cursor_pos
        scene_cursor_pos = None if cursor_pos is None else self.mapToScene(cursor_pos)
        self._last_scene_cursor_pos = scene_cursor_pos
        if self._cursor_pixmap_item is not None and self._cursor_pixmap_item.scene() is not None:
            self._cursor_pixmap_item.setVisible(cursor_pos is not None)
            if scene_cursor_pos is None:
                return
            self._cursor_pixmap_item.setPos(scene_cursor_pos.x() - self._cursor_pixmap_item.pixmap().width()
                                            * self._cursor_pixmap_item.scale() / 2,
                                            scene_cursor_pos.y() - self._cursor_pixmap_item.pixmap().height()
                                            * self._cursor_pixmap_item.scale() / 2)

    def reset_scale(self) -> None:
        """Resets the scale to fit content in the view and re-centers the scene."""
        scale_will_change = self._scale_adjustment != 0.0
        self._scale_adjustment = 0.0
        self.offset = QPoint(0, 0)
        self.center_on_point(QPointF(self._content_size.width() / 2, self._content_size.height() / 2))
        self._update_scale_and_transform()
        if scale_will_change:
            self.scale_changed.emit(self.scene_scale)

    @property
    def is_at_default_view(self) -> bool:
        """Returns whether the scale and offsets are both at default values."""
        return self._scale_adjustment == 0.0 and self._offset == QPointF(0.0, 0.0)

    @property
    def content_size(self) -> Optional[QSize]:
        """Gets the actual (not displayed) size of the viewed content."""
        return QSize(self._content_size.width(), self._content_size.height())

    @content_size.setter
    def content_size(self, new_size: QSize) -> None:
        """Updates the actual (not displayed) size of the viewed content."""
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
    def displayed_content_size(self) -> Optional[QSize]:
        """Gets the not displayed size of the viewed content."""
        if self._content_rect is None:
            return None
        return self._content_rect.size()

    @property
    def scene_scale(self) -> float:
        """Returns the image content scale."""
        return self._scale + self._scale_adjustment

    @scene_scale.setter
    def scene_scale(self, new_scale: float) -> None:
        """Updates the image content scale, limiting minimum scale to 0.01."""
        initial_scale = self.scene_scale
        mouse_scene_point = self._last_scene_cursor_pos
        new_scale = max(new_scale, 0.001)
        self._scale_adjustment = new_scale - self._scale

        # Zoom so that the mouse pointer stays over the same scene pixel:
        if mouse_scene_point is not None:
            assert self._last_cursor_pos is not None
            last_cursor_pos = self._last_cursor_pos
            scale_change = new_scale / initial_scale
            widget_cursor_pos = QPointF(last_cursor_pos)
            widget_center = QPointF(self.width() / 2, self.height() / 2)
            cursor_to_center = widget_center - widget_cursor_pos
            cursor_to_center.setX(cursor_to_center.x() / scale_change)
            cursor_to_center.setY(cursor_to_center.y() / scale_change)
            new_widget_center = widget_cursor_pos + cursor_to_center
            new_scene_center = self.mapToScene(new_widget_center.toPoint())
            self.center_on_point(new_scene_center)
            self._update_scale_and_transform()

            new_mouse_scene_point = QPointF(self.mapToScene(last_cursor_pos))
            rounding_error = new_mouse_scene_point - mouse_scene_point
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

        else:
            self.center_on_point(QPointF(self._content_size.width() / 2 + self._offset.x(),
                                         self._content_size.height() / 2 + self._offset.y()))
        self._update_scale_and_transform()
        self.scale_changed.emit(new_scale)

    @property
    def offset(self) -> QPointF:
        """Gets the image offset in pixels."""
        return QPointF(self._offset)

    @offset.setter
    def offset(self, new_offset: QPoint | QPointF) -> None:
        """Updates the image offset."""
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

    def drawForeground(self, painter: Optional[QPainter], unused_rect: QRectF) -> None:
        """Draws cursor pixmap over the scene if one is installed."""
        if painter is None or self._cursor_pixmap is None or self._last_cursor_pos is None:
            return
        center_point = self.mapToScene(self._last_cursor_pos)
        scale = self.scene_scale
        pixmap_rect = QRectF(0.0, 0.0, self._cursor_pixmap.width() / scale,
                             self._cursor_pixmap.height() / scale).toRect()
        pixmap_rect.moveCenter(center_point.toPoint())
        painter.drawPixmap(pixmap_rect, self._cursor_pixmap)

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
        scale_changed = new_scale != self._scale
        self._scale = new_scale

        # Apply scale changes and offset on top of the default scale. This approach means that changes to content size
        # will adjust the overall scale, while leaving the offset relative to the default scale unchanged:
        adjusted_scale = self._scale + self._scale_adjustment

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
        self.update()

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """Recalculate content size when the widget is resized."""
        super().resizeEvent(event)
        self._update_scale_and_transform()

    def _border_size(self) -> int:
        return (min(self.width(), self.height()) // 40) + 1

    def installEventFilter(self, event_filter: Optional[QObject]) -> None:
        """Extend default event filter management to deal with QGraphicsView mouse event oddities."""
        if event_filter is not None and event_filter not in self._event_filters:
            self._event_filters.append(event_filter)
        super().installEventFilter(event_filter)

    def removeEventFilter(self, event_filter: Optional[QObject]) -> None:
        """Extend default event filter management to deal with QGraphicsView mouse event oddities."""
        if event_filter in self._event_filters:
            self._event_filters.remove(event_filter)
        super().removeEventFilter(event_filter)

    def _pixmap_cursor_update(self, cursor_point: QPoint) -> None:
        """If a pixmap cursor is in use, keep last cursor point updated and force a redraw when the mouse moves."""
        if cursor_point != self._last_cursor_pos:
            self._last_cursor_pos = cursor_point
        if self._cursor_pixmap is not None:
            self.update()

    def mousePressEvent(self, event: Optional[QMouseEvent], get_result=False) -> Optional[bool]:
        """Custom mousePress handler to deal with QGraphicsView oddities. Child classes must call this implementation
           first with get_result=True, then exit without further action if it returns true."""
        assert event is not None
        self.set_cursor_pos(event.pos())
        super().mousePressEvent(event)
        if event.buttons() == Qt.MouseButton.MiddleButton or (event.buttons() == Qt.MouseButton.LeftButton
                                                              and KeyConfig.modifier_held(KeyConfig.PAN_VIEW_MODIFIER,
                                                                                          True)):
            self._drag_pt = event.pos()
        return False if get_result else None

    def mouseMoveEvent(self, event: Optional[QMouseEvent], get_result=False) -> Optional[bool]:
        """Custom mouseMove handler to deal with QGraphicsView oddities. Child classes must call this implementation
           first with get_result=True, then exit without further action if it returns true."""
        assert event is not None
        self.set_cursor_pos(event.pos())
        super().mouseMoveEvent(event)
        if self._mouse_navigation_enabled and self._drag_pt is not None and event is not None:
            if (event.buttons() == Qt.MouseButton.MiddleButton or
                    (event.buttons() == Qt.MouseButton.LeftButton
                     and KeyConfig.modifier_held(KeyConfig.PAN_VIEW_MODIFIER))):
                mouse_pt = event.pos()
                scale = self.scene_scale
                x_off = (self._drag_pt.x() - mouse_pt.x()) / scale
                y_off = (self._drag_pt.y() - mouse_pt.y()) / scale
                distance = math.sqrt(x_off**2 + y_off**2)
                if distance < 1:
                    return None
                self.offset = QPointF(self.offset.x() + x_off, self.offset.y() + y_off)
                self._drag_pt = mouse_pt
            else:
                self._drag_pt = None
        for event_filter in self._event_filters:
            if event_filter.eventFilter(self, event):
                return True if get_result else None
        return False if get_result else None

    def mouseReleaseEvent(self, event: Optional[QMouseEvent], get_result=False) -> Optional[bool]:
        """Custom mouseRelease handler to deal with QGraphicsView oddities. Child classes must call this implementation
           first with get_result=True, then exit without further action if it returns true."""
        assert event is not None
        self.set_cursor_pos(event.pos())
        super().mouseReleaseEvent(event)
        for event_filter in self._event_filters:
            if event_filter.eventFilter(self, event):
                return True if get_result else None
        return False if get_result else None

    def eventFilter(self, source, event: Optional[QEvent]):
        """Intercept mouse wheel events, use for scrolling in zoom mode:"""
        assert event is not None
        if event.type() == QEvent.Type.Leave:
            self.set_cursor_pos(None)
        elif event.type() == QEvent.Type.Enter:
            event = cast(QEnterEvent, event)
            self.set_cursor_pos(event.position())
        elif event.type() == QEvent.Type.Wheel:
            event = cast(QWheelEvent, event)
            if event.angleDelta().y() == 0:
                return False
            if event.angleDelta().y() > 0:
                self.scene_scale = self.scene_scale + 0.05
            elif event.angleDelta().y() < 0 and self.scene_scale > 0.05:
                self.scene_scale = self.scene_scale - 0.05
            self._update_scale_and_transform()
        return False

    def leaveEvent(self, event: Optional[QEvent]):
        """Clear the pixmap mouse cursor on leave."""
        self._last_cursor_pos = None
        super().leaveEvent(event)

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
        self._scale_adjustment = (get_scaled_placement(self.size(), bounds.size(), 0).width()
                                  / (bounds.width() + margin)) - self._scale
        self.scale_changed.emit(self.scene_scale)
        self.center_on_point(QPointF(self._content_size.width() / 2 + self._offset.x(),
                                     self._content_size.height() / 2 + self._offset.y()))
        self._update_scale_and_transform()
