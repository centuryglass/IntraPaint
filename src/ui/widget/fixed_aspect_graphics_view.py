"""A QGraphicsView that maintains an aspect ratio and simplifies scene management."""
from typing import Optional
from PyQt5.QtWidgets import QWidget, QGraphicsView, QGraphicsScene
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QTransform, QResizeEvent
from PyQt5.QtCore import Qt, QPoint, QPointF, QRect, QRectF, QSize, QMarginsF, pyqtSignal
from src.ui.util.get_scaled_placement import get_scaled_placement
from src.ui.util.contrast_color import contrast_color
from src.util.validation import assert_type


class FixedAspectGraphicsView(QGraphicsView):
    """A QGraphicsView that maintains an aspect ratio and simplifies scene management."""

    scale_changed = pyqtSignal(float)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene()
        self._content_size: QSize = QSize(0, 0)
        self._content_rect: Optional[QRect] = None
        self._background: Optional[QPixmap] = None

        self._scale = 1.0
        self._scale_adjustment = 0.0
        self._offset = QPointF(0.0, 0.0)

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setCacheMode(QGraphicsView.CacheBackground)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setScene(self._scene)

    @property
    def content_size(self) -> Optional[QSize]:
        """Gets the actual (not displayed) size of the viewed content."""
        return QSize(self._content_size.width(), self._content_size.height())

    @content_size.setter
    def content_size(self, new_size: QSize) -> None:
        """Updates the actual (not displayed) size of the viewed content."""
        assert_type(new_size, QSize)
        if new_size == self._content_size:
            return
        self._content_size.setWidth(new_size.width())
        self._content_size.setHeight(new_size.height())
        self.resizeEvent(None)
        self.resetCachedContent()
        self.update()

    @property
    def displayed_content_size(self) -> Optional[QSize]:
        """Gets the not displayed size of the viewed content."""
        if self._content_rect is None:
            return None
        return self._content_rect.size()

    @property
    def scale(self) -> float:
        """Returns the image content scale."""
        return self._scale + self._scale_adjustment

    @scale.setter
    def scale(self, new_scale: float) -> None:
        """Updates the image content scale, limiting minimum scale to 0.01."""
        new_scale = max(new_scale, 0.001)
        self._scale_adjustment = new_scale - self._scale
        self.resizeEvent(None)
        self.scale_changed.emit(new_scale)

    @property
    def offset(self) -> QPointF:
        """Gets the image offset in pixels."""
        return QPointF(self._offset)

    @offset.setter
    def offset(self, new_offset: QPoint | QPointF) -> None:
        """Updates the image offset."""
        self._offset.setX(float(new_offset.x()))
        self._offset.setY(float(new_offset.y()))
        self.resizeEvent(None)

    @property
    def background(self) -> QPixmap | None:
        """Returns the background image content."""
        return self._background

    @background.setter
    def background(self, new_background: Optional[QImage | QPixmap]) -> None:
        """Updates the background image content."""
        assert_type(new_background, (QImage, QPixmap, None))
        if isinstance(new_background, QImage):
            self._background = QPixmap.fromImage(new_background)
        else:
            self._background = new_background
        self.resetCachedContent()

    def widget_to_scene_coordinates(self, point: QPoint) -> QPointF:
        """Returns a point within the scene content corresponding to some point within the widget bounds."""
        assert_type(point, QPoint)
        return self.mapToScene(point)

    def scene_to_widget_coordinates(self, point: QPoint) -> QPointF:
        """Returns a point within the widget bounds corresponding to some point within the scene content."""
        assert_type(point, QPoint)
        return self.mapFromScene(point)

    def drawBackground(self, painter: Optional[QPainter], rect: QRectF) -> None:
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

    def drawForeground(self, painter: Optional[QPainter], rect: QRectF) -> None:
        """Draws a border around the scene area and blocks out any out-of-bounds content."""
        if painter is None:
            return
        content_rect = self.mapToScene(self._content_rect).boundingRect()
        border_rect = content_rect.adjusted(-5.0, -5.0, 5.0, 5.0)

        # QGraphicsView fails to clip content sometimes, so fill everything outside the scene with the
        # background color, then draw the border:
        pt0 = content_rect.topLeft()
        pt1 = QPointF(pt0.x() + border_rect.width(), pt0.y() + border_rect.height())
        fill_color = self.palette().color(self.backgroundRole())
        border_left = int(pt0.x())
        border_right = int(pt1.x())
        border_top = int(pt0.y())
        border_bottom = int(pt1.y())

        max_size = 20000000  # Large enough to ensure everything is covered, small enough to avoid overflow issues.
        painter.fillRect(border_left - max_size, -(max_size // 2), max_size, max_size, fill_color)
        painter.fillRect(border_right, -(max_size // 2), max_size, max_size, fill_color)
        painter.fillRect(-(max_size // 2), border_top, max_size, -max_size, fill_color)
        painter.fillRect(-(max_size // 2), border_bottom, max_size, max_size, fill_color)

        painter.setPen(QPen(contrast_color(self), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        painter.drawRect(border_rect)
        super().drawForeground(painter, rect)

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """Recalculate content size when the widget is resized."""
        super().resizeEvent(event)
        if self.content_size is None:
            raise RuntimeError('FixedAspectGraphicsView implementations must set content_size in __init__ before the ' +
                               'first resizeEvent is triggered')
        content_rect_f = QRectF(self._offset.x(), self._offset.y(), float(self.content_size.width()),
                                float(self.content_size.height()))
        if content_rect_f != self._scene.sceneRect():
            self._scene.setSceneRect(content_rect_f)

        border_size = self._border_size()
        self._content_rect = get_scaled_placement(QRect(QPoint(0, 0), self.size()), self.content_size, border_size)
        new_scale = self.displayed_content_size.width() / self.content_size.width()
        scale_changed = new_scale != self._scale
        self._scale = new_scale
        adjusted_scale = self._scale + self._scale_adjustment
        transformation = QTransform()
        transformation.scale(adjusted_scale, adjusted_scale)
        self.setTransform(transformation)
        if scale_changed:
            self.scale_changed.emit(adjusted_scale)
        self.update()

    def _border_size(self) -> int:
        return (min(self.width(), self.height()) // 40) + 1

