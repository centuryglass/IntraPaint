"""
Animated graphics item used to indicate a loading state.
"""
from typing import Optional
from PyQt5.QtWidgets import QGraphicsObject, QStyleOptionGraphicsItem, QWidget
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QPainterPath
from PyQt5.QtCore import Qt, QRect, QRectF, QPointF, pyqtProperty, QPropertyAnimation

from src.util.font_size import max_font_size

ANIM_DURATION_MS = 2000

BACKGROUND_COLOR = Qt.GlobalColor.black
BACKGROUND_OPACITY = 0.4
TEXT_COLOR = Qt.GlobalColor.white
ELLIPSE_SCENE_FRACTION = 1 / 6
WHEEL_LINE_COLOR = Qt.GlobalColor.darkGray
LINE_WIDTH = 4
WHEEL_FILL_COLOR = QColor(0, 0, 0, 200)
SPINNER_COLOR = Qt.GlobalColor.white


class LoadingSpinner(QGraphicsObject):
    """Show an animated loading indicator, with an optional message."""

    def __init__(self, message: str = ""):
        super().__init__()
        self._message = message
        self._rotation = 0
        self._font_size: Optional[int] = None
        self._anim = QPropertyAnimation(self, b"rotation")
        self._anim.setLoopCount(-1)
        self._anim.setStartValue(0)
        self._anim.setEndValue(359)
        self._anim.setDuration(ANIM_DURATION_MS)

    @property
    def message(self) -> str:
        """Returns the current loading message."""
        return self._message

    @message.setter
    def message(self, message: str) -> None:
        """Sets the loading message displayed."""
        self._message = message
        self._font_size = None
        self.update()

    @pyqtProperty(int)
    def rotation(self) -> int:
        """Returns the current animation rotation in degrees."""
        return self._rotation

    @rotation.setter
    def rotation(self, rotation: int) -> None:
        """Sets the current animation rotation in degrees."""
        self._rotation = rotation % 360
        self.update()

    @property
    def visible(self) -> bool:
        """Returns whether the loading spinner is showing."""
        return self.isVisible()

    @visible.setter
    def visible(self, visible: bool) -> None:
        """Shows or hides the loading spinner."""
        self.setVisible(visible)
        if visible:
            self._anim.start()
        else:
            self._anim.stop()

    def boundingRect(self) -> QRectF:
        """Returns the scene boundaries as the loading spinner bounds."""
        scene = self.scene()
        if scene is None:
            return QRectF()
        return scene.sceneRect()

    def shape(self) -> QPainterPath:
        """Returns the outline's bounds as a shape."""
        path = QPainterPath()
        path.addRect(QRectF(self.boundingRect()))
        return path

    def paint(self,
              painter: Optional[QPainter],
              unused_option: Optional[QStyleOptionGraphicsItem],
              unused_widget: Optional[QWidget] = None) -> None:
        """Draws a background overlay, a circle with optional message text, and an animated indicator."""
        scene = self.scene()
        if painter is None or scene is None:
            return
        painter.save()
        background_color = QColor(BACKGROUND_COLOR)
        background_color.setAlphaF(BACKGROUND_OPACITY)
        painter.fillRect(scene.sceneRect(), background_color)
        ellipse_radius = int(min(scene.sceneRect().width(), scene.sceneRect().height())
                             * ELLIPSE_SCENE_FRACTION)
        ellipse_x = int(scene.width() / 2 - ellipse_radius)
        ellipse_y = int(scene.height() / 2 - ellipse_radius)
        paint_bounds = QRect(ellipse_x, ellipse_y, ellipse_radius * 2, ellipse_radius * 2)

        # draw background circle:
        painter.setPen(QPen(WHEEL_LINE_COLOR, 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(QBrush(WHEEL_FILL_COLOR, Qt.BrushStyle.SolidPattern))
        painter.drawEllipse(paint_bounds)

        # Write text:
        painter.setPen(QPen(SPINNER_COLOR, LINE_WIDTH, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(QBrush(TEXT_COLOR, Qt.BrushStyle.SolidPattern))
        text_bounds = QRect(int(scene.sceneRect().x()), ellipse_y + ellipse_radius * 2,
                            int(scene.width()), ellipse_radius // 4)
        font = painter.font()
        if self._font_size is None:
            self._font_size = max(1, min(font.pointSize(), max_font_size(self._message, font, text_bounds)))
        font.setPointSize(self._font_size)
        painter.setFont(font)
        painter.drawText(text_bounds, Qt.AlignmentFlag.AlignCenter, self._message)

        # Draw animated indicator:
        painter.translate(QPointF(ellipse_x + ellipse_radius, ellipse_y + ellipse_radius))
        painter.rotate(self._rotation)
        painter.drawEllipse(QRect(0, ellipse_radius, ellipse_radius // 10, ellipse_radius // 10))
        painter.restore()
