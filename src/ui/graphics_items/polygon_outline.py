"""Displays polygon outlines as animated dashes with subtle color changes."""
import sys, os
from typing import Optional

from PySide6.QtCore import Qt, Property, QPropertyAnimation, QObject, QPointF
from PySide6.QtGui import QPen, QColor, QShowEvent, QHideEvent, QPolygonF, QTransform, QBitmap, QBrush, QPixmap, \
    QPainterPath
from PySide6.QtWidgets import QGraphicsItem, QGraphicsView, QGraphicsItemGroup, QGraphicsPolygonItem, QGraphicsScene, \
    QGraphicsPathItem

from src.config.application_config import AppConfig
from src.util.shared_constants import TIMELAPSE_MODE_FLAG, PROJECT_DIR

PEN_WIDTH = 3
MAX_DASH_OFFSET = 560
ANIM_DURATION = 36000
SELECTION_ANIM_PREFIX = f'{PROJECT_DIR}/resources/selection_anim_'
SELECTION_ANIM_EXT = '.pbm'


class PolygonOutline(QGraphicsItemGroup):
    """Displays polygon outlines as animated dashes with subtle color changes."""

    def __init__(self,
                 view: QGraphicsView,
                 polygons: Optional[list[QPolygonF]] = None,
                 parent: Optional[QGraphicsItem] = None):
        super().__init__(parent)
        self._polygons: list[QGraphicsPathItem] = []
        self._offset = QPointF()
        self._view = view
        self._animated = True
        self._animation_offset = 0
        self._animated_fill = True
        self._scene: Optional[QGraphicsScene] = None
        self._bitmaps: list[QBitmap] = []

        bitmap_idx = 0
        bitmap_path = f'{SELECTION_ANIM_PREFIX}{bitmap_idx}{SELECTION_ANIM_EXT}'
        while os.path.isfile(bitmap_path):
            bitmap = QBitmap(bitmap_path)
            self._bitmaps.append(bitmap)
            bitmap_idx += 1
            bitmap_path = f'{SELECTION_ANIM_PREFIX}{bitmap_idx}{SELECTION_ANIM_EXT}'

        class _Animator(QObject):
            def __init__(self, parent_outline: PolygonOutline) -> None:
                super().__init__()
                self._parent = parent_outline
                # noinspection PyTypeChecker
                self._anim = QPropertyAnimation(self, b"animation_offset")
                self._anim.setLoopCount(-1)
                self._anim.setStartValue(0)
                self._anim.setEndValue(MAX_DASH_OFFSET)
                self._anim.setDuration(ANIM_DURATION)

            @property
            def animation(self) -> QPropertyAnimation:
                """Access the wrapped PropertyAnimation."""
                return self._anim

            def animation_offset_getter(self) -> int:
                """Access the animation offset value."""
                return self._parent.animation_offset

            def animation_offset_setter(self, offset: int) -> None:
                """Updates the animation offset value."""
                self._parent.animation_offset = offset

            # noinspection PyTypeChecker
            animation_offset = Property(int, animation_offset_getter, animation_offset_setter, None, '')

        self._animator = _Animator(self)

        self._pen = QPen()
        self._pen.setDashPattern([4, 4, 8, 4, 4, 4])
        self._pen.setCosmetic(True)
        self._pen.setWidth(PEN_WIDTH)
        self._color = QColor(Qt.GlobalColor.black)
        if polygons is not None:
            self.load_polygons(polygons)
        scene = view.scene()
        assert scene is not None
        scene.addItem(self)
        if TIMELAPSE_MODE_FLAG in sys.argv:
            self._animator.animation.stop()
            self._animated = False

    def _get_pen(self) -> QPen:
        offset = self._animation_offset
        max_color = 0.6
        min_color = 0.2
        anim_range = MAX_DASH_OFFSET / 2
        fraction = (offset % anim_range) / anim_range
        if offset < anim_range:
            cmp = min_color + (fraction * (max_color - min_color))
        else:
            cmp = max_color - (fraction * (max_color - min_color))
        self._color.setRgbF(cmp, cmp, cmp)
        self._pen.setDashOffset(self._animation_offset)
        self._pen.setColor(self._color)
        return self._pen

    def move_to(self, pos: QPointF) -> None:
        """Updates the group position, ensuring the offset is applied to all polygons."""
        transform = QTransform()
        offset = pos + self.pos()
        transform.translate(offset.x(), offset.y())
        for poly in self._polygons:
            poly.setTransform(transform)

    def load_polygons(self, polygons: list[QPolygonF]):
        """Replace the current outline polygons with new ones."""
        scene = self._view.scene()
        assert scene is not None
        for polygon_item in self._polygons:
            self.removeFromGroup(polygon_item)
            scene.removeItem(polygon_item)
        self._polygons.clear()
        pen = self._get_pen()
        path = QPainterPath()
        path.setFillRule(Qt.FillRule.OddEvenFill)
        for polygon in polygons:
            path.addPolygon(polygon)
        polygon_item = QGraphicsPathItem(path)
        polygon_item.setBrush(QBrush(self._fill_color()))
        polygon_item.setPen(pen)
        self.addToGroup(polygon_item)
        self._polygons.append(polygon_item)
        if len(self._polygons) > 0 and self._animated:
            self._animator.animation.start()
        else:
            self._animator.animation.stop()

    @property
    def animation_offset(self) -> int:
        """Animate dash offset and optionally fill style to make the selection more visible."""
        return self._animation_offset

    @animation_offset.setter
    def animation_offset(self, offset: int) -> None:
        # Check scene state, stop animation when removed from the scene:
        scene = self.scene()
        if scene is None and self._scene is not None:
            self._animator.animation.stop()
            self._scene = None
            return
        if self._scene is None and scene is not None:
            self._scene = scene
        self._animation_offset = offset
        pen = self._get_pen()
        brush = QBrush(self._fill_color())
        if self._animated_fill and len(self._bitmaps) > 1:
            bitmap_idx = offset % len(self._bitmaps)
            bitmap = self._bitmaps[bitmap_idx]
            brush.setTexture(bitmap)
        for polygon_item in self._polygons:
            polygon_item.setPen(pen)
            polygon_item.setBrush(brush)
        self.update()

    @property
    def animated(self) -> bool:
        """Returns whether dotted lines are animated."""
        return self._animated

    @animated.setter
    def animated(self, should_animate: bool) -> None:
        """Sets whether dotted lines are animated."""
        if TIMELAPSE_MODE_FLAG in sys.argv:
            return
        self._animated = should_animate
        if self._animated and self.isVisible():
            self._animator.animation.start()
        else:
            self._animator.animation.stop()

    @property
    def animated_fill(self) -> bool:
        """Returns whether the outline should be filled with an animated texture"""
        return self._animated_fill

    @animated_fill.setter
    def animated_fill(self, should_animate: bool) -> None:
        """Sets whether the outline should be filled with an animated texture."""
        self._animated_fill = should_animate
        fill_color = self._fill_color()
        for polygon_item in self._polygons:
            brush = polygon_item.brush()
            brush.setColor(fill_color)
            if not should_animate:
                brush.setStyle(Qt.BrushStyle.SolidPattern)
            else:
                brush.setStyle(Qt.BrushStyle.TexturePattern)

    def _fill_color(self) -> QColor:
        if self.animated_fill:
            return AppConfig().get_color(AppConfig.SELECTION_COLOR, Qt.GlobalColor.black)
        return QColor(Qt.GlobalColor.black)

    # noinspection PyPep8Naming
    def showEvent(self, _: Optional[QShowEvent]) -> None:
        """Starts the animation when the outline is shown."""
        if self._animated:
            self._animator.animation.start()

    # noinspection PyPep8Naming
    def hideEvent(self, _: Optional[QHideEvent]) -> None:
        """Stops the animation when the outline is hidden."""
        self._animator.animation.stop()
