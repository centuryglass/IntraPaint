"""QGraphicsObject parent for classes that draw animated dash patterns."""
import sys
from typing import Optional

from PySide6.QtCore import QPropertyAnimation, Property
from PySide6.QtGui import QPen, QColor, Qt, QShowEvent, QHideEvent
from PySide6.QtWidgets import QGraphicsObject

from src.config.application_config import AppConfig
from src.util.shared_constants import TIMELAPSE_MODE_FLAG

PEN_WIDTH = 3
MAX_DASH_OFFSET = 560
ANIM_DURATION = 36000


class AnimatedDashItem(QGraphicsObject):
    """QGraphicsObject parent for classes that draw animated dash patterns."""

    def __init__(self) -> None:
        super().__init__()
        self._animated = AppConfig().get(AppConfig.ANIMATE_OUTLINES)

        def _set_anim(should_animate: bool) -> None:
            self.animated = should_animate
        AppConfig().connect(self, AppConfig.ANIMATE_OUTLINES, _set_anim)
        self._dash_offset = 0
        self._animation = QPropertyAnimation(self, b"dash_offset")
        self._animation.setLoopCount(-1)
        self._animation.setStartValue(0)
        self._animation.setEndValue(MAX_DASH_OFFSET)
        self._animation.setDuration(ANIM_DURATION)
        self._pen = QPen()
        self._pen.setDashPattern([4, 4, 8, 4, 4, 4])
        self._pen.setCosmetic(True)
        self._pen.setWidth(PEN_WIDTH)
        self._color = QColor(Qt.GlobalColor.black)
        if TIMELAPSE_MODE_FLAG in sys.argv:
            self._animation.stop()
            self._animated = False

    def dash_offset_getter(self) -> int:
        """Access the animation offset value."""
        return self._dash_offset

    def dash_offset_setter(self, offset: int) -> None:
        """Updates the animation offset value."""
        self._dash_offset = offset
        self.update()

    dash_offset = Property(int, dash_offset_getter, dash_offset_setter)

    def get_pen(self) -> QPen:
        """Get the pen used to draw dashed lines."""
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
            self._animation.start()
        else:
            self._animation.stop()

    def showEvent(self, _: Optional[QShowEvent]) -> None:
        """Starts the animation when the item is shown."""
        if self._animated:
            self._animation.start()

    def hideEvent(self, _: Optional[QHideEvent]) -> None:
        """Stops the animation when the item is hidden."""
        self._animation.stop()

