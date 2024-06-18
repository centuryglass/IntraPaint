"""Displays polygon outlines as animated dashes with subtle color changes."""
from typing import Optional, List

from PyQt5.QtCore import Qt, pyqtProperty, QPropertyAnimation, QObject, QPointF
from PyQt5.QtGui import QPen, QColor, QShowEvent, QHideEvent, QPolygonF, QTransform
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsView, QGraphicsItemGroup, QGraphicsPolygonItem

PEN_WIDTH = 3

MAX_DASH_OFFSET = 560
ANIM_DURATION = 36000


class PolygonOutline(QGraphicsItemGroup):
    """Displays polygon outlines as animated dashes with subtle color changes."""

    def __init__(self,
                 view: QGraphicsView,
                 polygons: Optional[List[QPolygonF]] = None,
                 parent: Optional[QGraphicsItem] = None):
        super().__init__(parent)
        self._polygons: List[QGraphicsPolygonItem] = []
        self._offset = QPointF()
        self._view = view
        self._animated = True
        self._dash_offset = 0

        class _Animator(QObject):
            def __init__(self, parent_outline: PolygonOutline) -> None:
                super().__init__()
                self._parent = parent_outline
                self._anim = QPropertyAnimation(self, b"dash_offset")
                self._anim.setLoopCount(-1)
                self._anim.setStartValue(0)
                self._anim.setEndValue(MAX_DASH_OFFSET)
                self._anim.setDuration(ANIM_DURATION)

            @property
            def animation(self) -> QPropertyAnimation:
                """Access the wrapped PropertyAnimation."""
                return self._anim

            @pyqtProperty(int)
            def dash_offset(self) -> int:
                """Access the animation offset value."""
                return self._parent.dash_offset

            @dash_offset.setter
            def dash_offset(self, offset: int) -> None:
                self._parent.dash_offset = offset

        self._animator = _Animator(self)
        self._pen = QPen()
        self._pen.setDashPattern([4, 4, 8, 4, 4, 4])
        self._pen.setCosmetic(True)
        self._pen.setWidth(PEN_WIDTH)
        self._color = QColor(Qt.GlobalColor.black)
        if polygons is not None:
            self.load_polygons(polygons)
        view.scene().addItem(self)

    def _get_pen(self) -> QPen:
        offset = self._dash_offset
        max_color = 0.6
        min_color = 0.2
        anim_range = MAX_DASH_OFFSET / 2
        fraction = (offset % anim_range) / anim_range
        if offset < anim_range:
            cmp = min_color + (fraction * (max_color - min_color))
        else:
            cmp = max_color - (fraction * (max_color - min_color))
        self._color.setRgbF(cmp, cmp, cmp)
        self._pen.setDashOffset(self._dash_offset)
        self._pen.setColor(self._color)
        return self._pen

    def move_to(self, pos: QPointF) -> None:
        transform = QTransform()
        offset = pos + self.pos()
        transform.translate(offset.x(), offset.y())
        for poly in self._polygons:
            poly.setTransform(transform)

    def load_polygons(self, polygons: List[QPolygonF]):
        """Replace the current outline polygons with new ones."""
        scene = self._view.scene()
        assert scene is not None
        for polygon_item in self._polygons:
            self.removeFromGroup(polygon_item)
        self._polygons.clear()
        pen = self._get_pen()
        for polygon in polygons:
            polygon_item = QGraphicsPolygonItem(polygon)
            polygon_item.setBrush(Qt.transparent)
            polygon_item.setPen(pen)
            self.addToGroup(polygon_item)
            self._polygons.append(polygon_item)
        if len(self._polygons) > 0 and self._animated:
            self._animator.animation.start()
        else:
            self._animator.animation.stop()

    @property
    def dash_offset(self) -> int:
        """Animate dash offset to make the selection more visible."""
        return self._dash_offset

    @dash_offset.setter
    def dash_offset(self, offset: int) -> None:
        self._dash_offset = offset
        pen = self._get_pen()
        for polygon_item in self._polygons:
            polygon_item.setPen(pen)
        self.update()

    @property
    def animated(self) -> bool:
        """Returns whether dotted lines are animated."""
        return self._animated

    @animated.setter
    def animated(self, should_animate: bool) -> None:
        """Sets whether dotted lines are animated."""
        self._animated = should_animate
        if self._animated and self.isVisible():
            self._animator.animation.start()
        else:
            self._animator.animation.stop()

    def showEvent(self, _: Optional[QShowEvent]) -> None:
        """Starts the animation when the outline is shown."""
        if self._animated:
            self._animator.animation.start()

    def hideEvent(self, _: Optional[QHideEvent]) -> None:
        """Stops the animation when the outline is hidden."""
        self._animator.animation.stop()
