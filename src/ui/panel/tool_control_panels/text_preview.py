"""Draws a text rect's text scaled into a small preview, with its box outlined in red while the text overflows it."""
from typing import Optional

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPalette, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from src.image.text_rect import TextRect
from src.ui.ink_style import signal_color
from src.util.visual.geometry_utils import get_scaled_placement
from src.util.visual.text_drawing_utils import find_text_size

PREVIEW_MARGIN = 4


def text_overflows(text_rect: TextRect) -> bool:
    """Returns whether a text rect's text needs more room than its box."""
    if text_rect.text == '' or text_rect.size.isEmpty():
        return False
    text_size = find_text_size(text_rect.text, text_rect.font)
    return text_size.width() > text_rect.size.width() or text_size.height() > text_rect.size.height()


class TextPreview(QWidget):
    """Draws a text rect's text scaled into the widget, with its box outlined, in red while the text overflows it.

    Its minimum size comes from the font, not from the text it shows."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._text_rect = TextRect()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_text_rect(self, text_rect: TextRect) -> None:
        """Changes the text rect drawn."""
        self._text_rect = TextRect(text_rect)
        self.update()

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns room for three lines of panel text."""
        line = self.fontMetrics().height()
        return QSize(line * 6, line * 3)

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns room for five lines of panel text."""
        line = self.fontMetrics().height()
        return QSize(line * 12, line * 5)

    def paintEvent(self, _event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Fills the widget with the background color, then draws the scaled text and its box."""
        text_rect = self._text_rect
        painter = QPainter(self)
        painter.fillRect(self.rect(), text_rect.background_color)
        box_size = text_rect.size
        text = text_rect.text if text_rect.text != '' else ' '
        content_size = box_size.expandedTo(find_text_size(text, text_rect.font))
        if content_size.isEmpty():
            painter.end()
            return
        placement = get_scaled_placement(self.size(), content_size, PREVIEW_MARGIN)
        scale = placement.width() / content_size.width()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.translate(placement.topLeft())
        painter.scale(scale, scale)
        painter.setFont(text_rect.font)
        painter.setPen(text_rect.text_color)
        painter.drawText(QRect(QPoint(), content_size), text_rect.text, text_rect.text_alignment)
        overflow_color = signal_color()
        outline = (overflow_color if overflow_color is not None else QColor(Qt.GlobalColor.red)) \
            if text_overflows(text_rect) else self.palette().color(QPalette.ColorRole.Mid)
        pen = QPen(outline, 1.5)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRect(QPoint(), box_size))
        painter.end()
