"""QGraphicsObject parent for classes that draw animated dash patterns."""
import sys
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtGui import QPen, QColor, Qt
from PySide6.QtWidgets import QGraphicsObject, QGraphicsItem

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


def is_shown_in_scene(item: QGraphicsItem) -> bool:
    """Returns whether a graphics item is visible and in a scene.

    Graphics items never receive `showEvent` or `hideEvent`, so animated items track this through `itemChange`.
    """
    return item.isVisible() and item.scene() is not None


class AnimatedDashItem(QGraphicsObject):
    """QGraphicsObject parent for classes that draw animated dash patterns.

    The dashes animate only while the item is shown in a scene and `has_dashes` is true. A subclass whose content
    changes calls `sync_animation` afterwards.
    """

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
        self.sync_animation()

    def has_dashes(self) -> bool:
        """Returns whether the item currently draws any dashes."""
        return True

    def sync_animation(self) -> None:
        """Runs the dash animation only while the item is animated, shown in a scene, and has dashes to draw."""
        sync_animation_timer(self._animation_timer, self._animated, is_shown_in_scene(self) and self.has_dashes())

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:  # pylint: disable=invalid-name
        """Starts or stops the animation as the item is shown, hidden, added to a scene or removed from one."""
        if change in (QGraphicsItem.GraphicsItemChange.ItemVisibleHasChanged,
                      QGraphicsItem.GraphicsItemChange.ItemSceneHasChanged):
            self.sync_animation()
        return super().itemChange(change, value)
