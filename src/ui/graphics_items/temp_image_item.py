"""A graphics item that briefly displays a message, then removes itself from the scene."""
from typing import Optional

from PySide6.QtCore import QRectF, QTimer, Property, QPropertyAnimation, QRect, QPointF, QSizeF
from PySide6.QtGui import QPainterPath, QPainter, QPixmap, QShowEvent
from PySide6.QtWidgets import QGraphicsObject, QGraphicsView, QStyleOptionGraphicsItem, QWidget

FADE_DURATION_MS = 400
TIMEOUT_MS = 200


class TempImageItem(QGraphicsObject):
    """A graphics item that briefly displays an image, then removes itself from the scene."""

    def __init__(self, image: QPixmap, bounds: QRect | QRectF, view: QGraphicsView) -> None:
        super().__init__()
        self._image = image
        self._bounds = bounds
        self._image_bounds = QRectF(QPointF(), QSizeF(image.size()))
        self._image_bounds.moveCenter(QPointF(bounds.center()))
        self._opacity_percent = 0

        # Set up auto-close timer:
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(TIMEOUT_MS)
        self._timer.timeout.connect(self._fade_out_and_exit)

        # Add to scene:
        scene = view.scene()
        assert scene is not None
        self._scene = scene
        self.setZValue(9999)
        scene.addItem(self)

        self._animation = QPropertyAnimation(self, b"_opacity")
        self._animation.setLoopCount(1)
        self._animation.setStartValue(0)
        self._animation.setEndValue(100)
        self._animation.setDuration(FADE_DURATION_MS)
        self._animation.finished.connect(self._start_delay)
        self._animation.start()

    @property
    def animation_opacity(self) -> float:
        """Current drawn opacity, taking into account the fade in/fade out animation applied to the image."""
        return min(0.01 * max(self._opacity_percent, 1), 1.0)

    def _opacity_getter(self) -> int:
        return self._opacity_percent

    def _opacity_setter(self, opacity: int) -> None:
        self._opacity_percent = opacity

    _opacity = Property(int, _opacity_getter, _opacity_setter)

    def _start_delay(self):
        self._timer.start()

    def _fade_out_and_exit(self):
        self._animation.setStartValue(100)
        self._animation.setEndValue(-100)
        self._animation.finished.disconnect(self._start_delay)
        self._animation.finished.connect(self._remove_self)
        self._animation.start()

    def _remove_self(self):
        self.setVisible(False)
        self._scene.removeItem(self)

    def boundingRect(self) -> QRectF:
        """Returns the item's scene boundary"""
        return self._image_bounds

    def shape(self) -> QPainterPath:
        """Returns the item's bounds as a shape."""
        path = QPainterPath()
        path.addRect(QRectF(self.boundingRect()))
        return path

    def paint(self,
              painter: Optional[QPainter],
              unused_option: Optional[QStyleOptionGraphicsItem],
              unused_widget: Optional[QWidget] = None) -> None:
        """Draws the text over a rounded rectangle."""
        assert painter is not None
        painter.save()
        painter.setOpacity(self.animation_opacity)
        painter.drawPixmap(self._image_bounds.topLeft(), self._image)
        painter.restore()

    def showEvent(self, _: Optional[QShowEvent]) -> None:
        """Starts the animation when the item is shown."""
        self._animation.start()
