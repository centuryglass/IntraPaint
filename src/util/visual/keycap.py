"""Draws keycaps: rounded `Button`-filled plates with a `Shadow` outline and a hard depth edge below.

`KeyHintLabel` draws its keycap with `draw_keycap`, and `rich_text_key_hint` renders the same plate into inline
images, so the two stay in step with each other and with the theme.
"""
from PySide6.QtCore import QMargins, QRectF, QSize
from PySide6.QtGui import QColor, QFont, QPainter, QPalette, QPen

KEYCAP_RADIUS = 3.0
# The keycap's ink shadow drops this far below it:
KEYCAP_DEPTH = 2
# Space between the key text and the keycap's outline. The bottom margin excludes `KEYCAP_DEPTH`:
KEYCAP_PADDING = QMargins(5, 3, 5, 2)


def keycap_font(base_font: QFont) -> QFont:
    """Returns the bold version of a font, as keycaps draw their text."""
    font = QFont(base_font)
    font.setBold(True)
    return font


def keycap_colors(palette: QPalette) -> tuple[QColor, QColor, QColor]:
    """Returns the (fill, outline, text) colors a palette gives a keycap."""
    return (palette.color(QPalette.ColorRole.Button), palette.color(QPalette.ColorRole.Shadow),
            palette.color(QPalette.ColorRole.ButtonText))


def keycap_size(text_size: QSize) -> QSize:
    """Returns the size of a keycap, including its depth edge, around text of the given size."""
    return QSize(text_size.width() + KEYCAP_PADDING.left() + KEYCAP_PADDING.right(),
                 text_size.height() + KEYCAP_PADDING.top() + KEYCAP_PADDING.bottom() + KEYCAP_DEPTH)


def draw_keycap(painter: QPainter, bounds: QRectF, fill: QColor, outline: QColor) -> None:
    """Draws a keycap filling `bounds`, with its depth edge along the bottom of `bounds`."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    cap = bounds.adjusted(0.5, 0.5, -0.5, -0.5 - KEYCAP_DEPTH)
    painter.setPen(QPen(outline, 1))
    painter.setBrush(outline)
    painter.drawRoundedRect(cap.translated(0, KEYCAP_DEPTH), KEYCAP_RADIUS, KEYCAP_RADIUS)
    painter.setBrush(fill)
    painter.drawRoundedRect(cap, KEYCAP_RADIUS, KEYCAP_RADIUS)
    painter.restore()
