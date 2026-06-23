"""Displays polygon outlines as animated dashes with subtle color changes."""
import sys
from typing import Optional

from PySide6.QtCore import Qt, Property, QPropertyAnimation, QObject, QPointF, SignalInstance
from PySide6.QtGui import QPen, QColor, QShowEvent, QHideEvent, QPolygonF, QTransform, QBrush, QPixmap, \
    QPainterPath, QImage, QPainter
from PySide6.QtWidgets import QGraphicsItem, QGraphicsView, QGraphicsScene, \
    QGraphicsPathItem

from src.util.shared_constants import TIMELAPSE_MODE_FLAG, PROJECT_DIR
from src.util.visual.contrast_color import contrast_color
from src.util.visual.image_utils import create_transparent_image

PEN_WIDTH = 3
MAX_DASH_OFFSET = 560
FILL_OFFSET = 2.0
ANIM_DURATION = 36000
SCALE_MULTIPLIER = 0.1
SELECTION_PATTERN_0_RESOURCE = f'{PROJECT_DIR}/resources/animated_fill_pattern_0.png'
SELECTION_PATTERN_1_RESOURCE = f'{PROJECT_DIR}/resources/animated_fill_pattern_1.png'


class PolygonOutline(QGraphicsPathItem):
    """Displays polygon outlines as animated dashes with subtle color changes."""

    def __init__(self,
                 view: QGraphicsView,
                 polygons: Optional[list[QPolygonF]] = None,
                 parent: Optional[QGraphicsItem] = None):
        super().__init__(parent)
        self._offset = QPointF()
        self._height_offset = 0.0
        self._view = view
        self._animated_outline = True
        self._animation_offset = 0
        self._animated_fill = True
        self._scene: Optional[QGraphicsScene] = None
        self._transform_scale = SCALE_MULTIPLIER

        def _update_scale(new_scale):
            inverse_scale = min(1.0 / new_scale, 1.0) * SCALE_MULTIPLIER
            if self._transform_scale != inverse_scale:
                self._transform_scale = inverse_scale
                self._update_pen_and_brush()

        if hasattr(view, 'scale_changed'):
            assert isinstance(view.scale_changed, SignalInstance)
            view.scale_changed.connect(_update_scale)

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
            animation_offset = Property(int, animation_offset_getter, animation_offset_setter)

        self._animator = _Animator(self)

        self._pen = QPen()
        self._pen.setDashPattern([4, 4, 8, 4, 4, 4])
        self._pen.setCosmetic(True)
        self._pen.setWidth(PEN_WIDTH)

        self._fill_pattern_0 = QImage(SELECTION_PATTERN_0_RESOURCE)
        self._fill_pattern_1 = QImage(SELECTION_PATTERN_1_RESOURCE)
        self._fill_color_0 = QColor()
        self._fill_color_1 = QColor()
        self._fill_pixmap = QPixmap()

        self._line_color = QColor(Qt.GlobalColor.black)
        if polygons is not None:
            self.load_polygons(polygons)
        self._update_pen_and_brush()
        scene = view.scene()
        assert scene is not None
        scene.addItem(self)
        if TIMELAPSE_MODE_FLAG in sys.argv:
            self._animator.animation.stop()
            self._animated_outline = False

    def _update_pen_and_brush(self) -> None:
        offset = self._animation_offset
        max_color = 0.6
        min_color = 0.2
        anim_range = MAX_DASH_OFFSET / 2
        fraction = (offset % anim_range) / anim_range
        if offset < anim_range:
            cmp = min_color + (fraction * (max_color - min_color))
        else:
            cmp = max_color - (fraction * (max_color - min_color))
        self._line_color.setRgbF(cmp, cmp, cmp)
        if self._animated_outline:
            self._pen.setDashOffset(self._animation_offset)
        self._pen.setColor(self._line_color)
        self.setPen(self._pen)

        brush = QBrush(self._fill_pixmap)
        brush_transform = QTransform.fromScale(self._transform_scale, self._transform_scale)
        if self._animated_fill:
            texture_height = self._fill_pixmap.height()
            self._height_offset += FILL_OFFSET
            if self._height_offset > texture_height:
                self._height_offset = 0.0
            brush_transform.translate(self._height_offset, self._height_offset)
        brush.setTransform(brush_transform)
        self.setBrush(brush)

    def move_to(self, pos: QPointF) -> None:
        """Updates the path's position."""
        transform = QTransform()
        offset = pos + self.pos()
        transform.translate(offset.x(), offset.y())
        self.setTransform(transform)

    def load_polygons(self, polygons: list[QPolygonF]):
        """Replace the current outline polygons with new ones."""
        scene = self._view.scene()
        assert scene is not None
        path = QPainterPath()
        path.setFillRule(Qt.FillRule.OddEvenFill)
        for polygon in polygons:
            path.addPolygon(polygon)
        self.setPath(path)
        if (self._animated_outline or self._animated_fill) and not self.path().isEmpty():
            self._animator.animation.start()
        else:
            self._animator.animation.stop()

    @property
    def fill_color(self) -> QColor:
        """Returns the primary fill color."""
        return QColor(self._fill_color_0)

    @fill_color.setter
    def fill_color(self, fill_color: QColor) -> None:
        """Updates the primary fill color."""
        if fill_color == self._fill_color_0:
            return
        self._fill_color_0 = fill_color
        self._fill_color_1 = contrast_color(fill_color)
        self._fill_color_1.setAlpha(self._fill_color_0.alpha())

        fill_main = self._fill_pattern_0.copy()
        fill_main_painter = QPainter(fill_main)
        fill_main_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        fill_main_painter.fillRect(fill_main.rect(), self._fill_color_0)
        fill_main_painter.end()

        fill_contrast = self._fill_pattern_1.copy()
        fill_contrast_painter = QPainter(fill_contrast)
        fill_contrast_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        fill_contrast_painter.fillRect(fill_contrast.rect(), self._fill_color_1)
        fill_contrast_painter.end()

        recolored_pattern = create_transparent_image(self._fill_pattern_0.size())
        painter = QPainter(recolored_pattern)
        painter.drawImage(0, 0, fill_main)
        painter.drawImage(0, 0, fill_contrast)
        painter.end()
        self._fill_pixmap = QPixmap(recolored_pattern)
        self._update_pen_and_brush()

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
        self._update_pen_and_brush()
        self.update()

    @property
    def animated_outline(self) -> bool:
        """Returns whether dotted lines are animated."""
        return self._animated_outline

    @animated_outline.setter
    def animated_outline(self, should_animate: bool) -> None:
        """Sets whether dotted lines are animated."""
        if TIMELAPSE_MODE_FLAG in sys.argv:
            return
        self._animated_outline = should_animate
        self._start_or_stop_animation()

    def _start_or_stop_animation(self):
        if TIMELAPSE_MODE_FLAG in sys.argv or self.path().isEmpty():
            self._animator.animation.stop()
            return
        if self._animated_outline or self._animated_fill:
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
        if TIMELAPSE_MODE_FLAG in sys.argv:
            return
        self._animated_fill = should_animate
        self._start_or_stop_animation()
        self._update_pen_and_brush()

    # noinspection PyPep8Naming
    def showEvent(self, _: Optional[QShowEvent]) -> None:
        """Starts the animation when the outline is shown."""
        if self._animated_outline:
            self._animator.animation.start()

    # noinspection PyPep8Naming
    def hideEvent(self, _: Optional[QHideEvent]) -> None:
        """Stops the animation when the outline is hidden."""
        self._animator.animation.stop()
