"""Shows a dialog's starting color beside its new color. Clicking the starting color emits `revert_requested`."""
from typing import Optional

from PySide6.QtCore import Qt, QRect, QSize, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPalette, QPen
from PySide6.QtWidgets import QWidget, QApplication, QSizePolicy

from src.util.visual.image_utils import tile_pattern_fill

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.widget.color_picker.color_comparison'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


COMPARISON_TOOLTIP = _tr('Left: the starting color, click to go back to it. Right: the new color.')

SWATCH_WIDTH = 32
SWATCH_HEIGHT = 40
CHECKER_TILE_SIZE = 4


class ColorComparison(QWidget):
    """Shows a dialog's starting color beside its new color. Clicking the starting color emits `revert_requested`."""

    revert_requested = Signal(QColor)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._original = QColor(Qt.GlobalColor.black)
        self._color = QColor(Qt.GlobalColor.black)
        self.setFixedSize(SWATCH_WIDTH * 2, SWATCH_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setToolTip(COMPARISON_TOOLTIP)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self) -> QSize:
        """The widget has a fixed size."""
        return self.size()

    def original_bounds(self) -> QRect:
        """Returns the starting color's bounds, in widget coordinates."""
        return QRect(0, 0, self.width() // 2, self.height())

    def set_original(self, color: QColor) -> None:
        """Sets the starting color."""
        self._original = QColor(color)
        self.update()

    def set_color(self, color: QColor) -> None:
        """Sets the new color."""
        self._color = QColor(color)
        self.update()

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
        """Clicking the starting color requests a revert to it."""
        assert event is not None
        if event.button() == Qt.MouseButton.LeftButton and self.original_bounds().contains(event.position().toPoint()):
            self.revert_requested.emit(QColor(self._original))

    def paintEvent(self, unused_event: Optional[QPaintEvent]) -> None:
        """Draws both colors over a checkerboard, with an outline."""
        painter = QPainter(self)
        bounds = self.rect().adjusted(0, 0, -1, -1)
        tile_pattern_fill(painter, bounds, CHECKER_TILE_SIZE, Qt.GlobalColor.lightGray, Qt.GlobalColor.darkGray)
        original_bounds = self.original_bounds()
        painter.fillRect(original_bounds, self._original)
        painter.fillRect(QRect(original_bounds.right() + 1, 0, self.width() - original_bounds.width(), self.height()),
                         self._color)
        painter.setPen(QPen(self.palette().color(QPalette.ColorRole.WindowText), 1))
        painter.drawRect(bounds)
        painter.end()
