"""A small raised keycap showing fixed key text, for panel section headers and panel headers.

Unlike `KeyHintLabel`, it reads no config: the owner passes the text and updates it when the binding changes. It
paints from the palette, so it follows palette changes without caching colors.
"""
from typing import Optional

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QFontMetrics, QPainter, QPaintEvent
from PySide6.QtWidgets import QSizePolicy, QWidget

from src.util.visual.keycap import KEYCAP_DEPTH, KEYCAP_PADDING, draw_keycap, keycap_colors, keycap_font, keycap_size


class KeycapBadge(QWidget):
    """Draws a short text, such as a key name, on a keycap."""

    def __init__(self, text: str = '', parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._text = text
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    @property
    def text(self) -> str:
        """Returns the key text."""
        return self._text

    def set_text(self, text: str) -> None:
        """Changes the key text and resizes the badge to fit."""
        if text != self._text:
            self._text = text
            self.updateGeometry()
            self.update()

    def sizeHint(self) -> QSize:
        """Returns the size of the key text in bold, plus the keycap's margins."""
        metrics = QFontMetrics(keycap_font(self.font()))
        return keycap_size(QSize(metrics.horizontalAdvance(self._text), metrics.height()))

    def minimumSizeHint(self) -> QSize:
        """Returns the same size as `sizeHint`."""
        return self.sizeHint()

    def _paint_text(self, painter: QPainter, bounds: QRectF) -> None:
        painter.setFont(keycap_font(self.font()))
        painter.drawText(bounds, Qt.AlignmentFlag.AlignCenter, self._text)

    def paintEvent(self, _event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draws the keycap and its text in the palette's button colors."""
        painter = QPainter(self)
        fill, outline, text_color = keycap_colors(self.palette())
        bounds = QRectF(self.rect())
        draw_keycap(painter, bounds, fill, outline)
        painter.setPen(text_color)
        self._paint_text(painter, bounds.adjusted(KEYCAP_PADDING.left(), KEYCAP_PADDING.top(),
                                                  -KEYCAP_PADDING.right(), -KEYCAP_PADDING.bottom() - KEYCAP_DEPTH))
        painter.end()
