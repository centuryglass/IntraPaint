"""QGraphicsObject parent for classes that draw animated dash patterns."""
import sys
from typing import Optional

from PySide6.QtCore import QTimer
from PySide6.QtGui import QPen, QColor, Qt, QShowEvent, QHideEvent
from PySide6.QtWidgets import QGraphicsObject

from src.config.application_config import AppConfig
from src.util.shared_constants import TIMELAPSE_MODE_FLAG

PEN_WIDTH = 3
MAX_DASH_OFFSET = 560
ANIM_DURATION = 36000
# ~15 frames per second: the dash fade reads the same as Qt's animation timer at 60 fps, at a quarter of the repaints.
DASH_ANIMATION_INTERVAL_MS = 66


def sync_animation_timer(timer: QTimer, animated: bool, visible: bool) -> None:
    """Runs `timer` only while its item is animated and visible."""
    if animated and visible:
        if not timer.isActive():
            timer.start()
    elif timer.isActive():
        timer.stop()


class AnimatedDashItem(QGraphicsObject):
    """QGraphicsObject parent for classes that draw animated dash patterns."""

    def __init__(self) -> None:
        super().__init__()
        self._animated = AppConfig().get(AppConfig.ANIMATE_OUTLINES_AND_PREVIEWS)

        def _set_anim(should_animate: bool) -> None:
            self.animated = should_animate
        AppConfig().connect(self, AppConfig.ANIMATE_OUTLINES_AND_PREVIEWS, _set_anim)
        self._dash_offset = 0
        # A timer instead of a QPropertyAnimation: the animation would otherwise tick every frame while the item is
        # visible, repainting it at the full frame rate even when nothing else changed.
        self._animation_timer = QTimer(self)
        self._animation_timer.setInterval(DASH_ANIMATION_INTERVAL_MS)
        self._animation_timer.timeout.connect(self._advance_dash_offset)
        self._pen = QPen()
        self._pen.setDashPattern([4, 4, 8, 4, 4, 4])
        self._pen.setCosmetic(True)
        self._pen.setWidth(PEN_WIDTH)
        self._color = QColor(Qt.GlobalColor.black)
        if TIMELAPSE_MODE_FLAG in sys.argv:
            self._animation_timer.stop()
            self._animated = False

    def _advance_dash_offset(self) -> None:
        """Moves the dash offset one step, repainting only this item."""
        step = max(1, round(MAX_DASH_OFFSET * DASH_ANIMATION_INTERVAL_MS / ANIM_DURATION))
        self._dash_offset = (self._dash_offset + step) % MAX_DASH_OFFSET
        self.update()

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
        sync_animation_timer(self._animation_timer, self._animated, self.isVisible())

    def showEvent(self, _: Optional[QShowEvent]) -> None:
        """Starts the animation when the item is shown."""
        sync_animation_timer(self._animation_timer, self._animated, self.isVisible())

    def hideEvent(self, _: Optional[QHideEvent]) -> None:
        """Stops the animation when the item is hidden."""
        sync_animation_timer(self._animation_timer, self._animated, self.isVisible())
