"""A graphics item that briefly displays a message, then removes itself from the scene."""
from typing import Optional

from PySide6.QtCore import QPoint, QRectF, QTimer
from PySide6.QtGui import QFont, QPainterPath, QPainter, Qt
from PySide6.QtWidgets import QGraphicsObject, QGraphicsView, QStyleOptionGraphicsItem, QWidget

from src.util.visual.text_drawing_utils import find_text_size, max_font_size

TIMEOUT_MS = 1000


class ToastMessageItem(QGraphicsObject):
    """A graphics item that briefly displays a message, then removes itself from the scene."""

    def __init__(self, message: str, view: QGraphicsView) -> None:
        super().__init__()
        self._message = message

        # Text size and bounds calculations:
        view_scene_bounds = QRectF(view.mapToScene(QPoint()), view.mapToScene(QPoint(view.width(), view.height())))
        horizontal_margin = view_scene_bounds.width() / 6
        vertical_margin = view_scene_bounds.height() / 6
        bounds = view_scene_bounds.adjusted(horizontal_margin, vertical_margin, -horizontal_margin,
                                            -vertical_margin)
        self._font = QFont()
        pt_size = max_font_size(message, self._font, bounds.size().toSize())
        self._font.setPointSize(pt_size)
        cropped_size = find_text_size(self._message, self._font)
        center = bounds.center()
        bounds.setWidth(min(cropped_size.width() + 30, int(view_scene_bounds.width())))
        bounds.setHeight(min(cropped_size.height() + 30, int(view_scene_bounds.height())))
        bounds.moveCenter(center)
        self._bounds = bounds

        # Set up auto-close timer:
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(TIMEOUT_MS)
        self._timer.timeout.connect(self._remove_self)
        self._timer.start()

        # Add to scene:
        scene = view.scene()
        assert scene is not None
        self._scene = scene
        self.setZValue(9999)
        scene.addItem(self)

    def _remove_self(self):
        self.setVisible(False)
        self._scene.removeItem(self)

    def boundingRect(self) -> QRectF:
        """Returns the item's scene boundary"""
        return self._bounds

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
        corner_radius = self._bounds.height() // 5
        text_background = QPainterPath()
        text_background.addRoundedRect(QRectF(self._bounds), corner_radius, corner_radius)
        painter.fillPath(text_background, Qt.GlobalColor.black)
        painter.setPen(Qt.GlobalColor.white)
        painter.drawPath(text_background)
        painter.setFont(self._font)
        painter.drawText(self._bounds, Qt.AlignmentFlag.AlignCenter, self._message)
        painter.restore()
