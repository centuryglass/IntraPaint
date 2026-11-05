"""Draws keycaps: rounded `WindowText`-filled plates with `Shadow` text and outline, and a hard depth edge below.

Keycap widgets draw their row of keycaps with `draw_keycap_row`, and `rich_text_key_hint` renders the same plate and
text into inline images, so every key hint stays in step with the others and with the theme. The labels come from
`src.util.visual.key_hint_text.key_hint_labels`.
"""
from typing import Sequence

from PySide6.QtCore import QMargins, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPalette, QPen

KEYCAP_RADIUS = 3.0
# The keycap's ink shadow drops this far below it:
KEYCAP_DEPTH = 2
# Space between the key text and the keycap's outline. The bottom margin excludes `KEYCAP_DEPTH`:
KEYCAP_PADDING = QMargins(2, 2, 2, 1)


def keycap_font(base_font: QFont) -> QFont:
    """Returns the semi-bold version of a font, as keycaps draw their text."""
    font = QFont(base_font)
    font.setWeight(QFont.Weight.DemiBold)
    return font


def keycap_colors(palette: QPalette) -> tuple[QColor, QColor, QColor]:
    """Returns the (fill, outline, text) colors a palette gives a keycap.

    The light `WindowText` fill and dark `Shadow` text stay legible on the darker `Window` and `ToolTipBase` backgrounds
    keycaps appear on, in a theme that keeps those roles far apart.
    """
    shadow = palette.color(QPalette.ColorRole.Shadow)
    return palette.color(QPalette.ColorRole.WindowText), shadow, shadow


def keycap_text_size(text: str, font: QFont) -> QSize:
    """Returns the size of the box a keycap gives its text, in the keycap font."""
    metrics = QFontMetrics(font)
    size = metrics.boundingRect(text).size()
    return QSize(size.width() + 2, max(size.height(), metrics.ascent() + metrics.descent()) + 2)


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


def draw_keycap_text(painter: QPainter, bounds: QRectF, text_size: QSize, font: QFont, text: str,
                     color: QColor) -> None:
    """Draws `text` on a keycap filling `bounds`, the same `bounds` passed to `draw_keycap`.

    The text is positioned `KEYCAP_PADDING.left()`/`.top()` in from `bounds`' top-left corner, in a box sized to
    `text_size`, so the gap on each side of the text matches `KEYCAP_PADDING` exactly.
    """
    painter.save()
    painter.setFont(font)
    painter.setPen(color)
    text_rect = QRectF(bounds.left() + KEYCAP_PADDING.left(), bounds.top() + KEYCAP_PADDING.top(),
                       text_size.width(), text_size.height())
    painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)
    painter.restore()


# Drawn between the keycaps of alternative key bindings:
KEYCAP_SEPARATOR = ', '


def keycap_row_size(labels: Sequence[str], font: QFont) -> QSize:
    """Returns the size of a row of keycaps for `labels` in the keycap `font`, with `KEYCAP_SEPARATOR` between them."""
    if len(labels) == 0:
        return QSize(0, 0)
    sizes = [keycap_size(keycap_text_size(label, font)) for label in labels]
    separator_width = QFontMetrics(font).horizontalAdvance(KEYCAP_SEPARATOR)
    return QSize(sum(size.width() for size in sizes) + separator_width * (len(labels) - 1),
                 max(size.height() for size in sizes))


def draw_keycap_row(painter: QPainter, top_left: QPointF, labels: Sequence[str], font: QFont, palette: QPalette,
                    draw_text: bool = True) -> None:
    """Draws a keycap for each of `labels` in the keycap `font`, left to right from `top_left`, at the size
    `keycap_row_size` returns. `KEYCAP_SEPARATOR` between keycaps takes the keycap fill color, the palette's text
    color. With `draw_text` false, only the plates are drawn."""
    fill, outline, text_color = keycap_colors(palette)
    row_height = keycap_row_size(labels, font).height()
    separator_width = QFontMetrics(font).horizontalAdvance(KEYCAP_SEPARATOR)
    x = top_left.x()
    for index, label in enumerate(labels):
        if index > 0:
            if draw_text:
                painter.save()
                painter.setFont(font)
                painter.setPen(fill)
                # Placed like keycap text, so the separator sits on the keycap text's baseline:
                painter.drawText(QRectF(x, top_left.y() + KEYCAP_PADDING.top(), separator_width,
                                        row_height - KEYCAP_PADDING.top() - KEYCAP_PADDING.bottom() - KEYCAP_DEPTH),
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, KEYCAP_SEPARATOR)
                painter.restore()
            x += separator_width
        text_size = keycap_text_size(label, font)
        size = keycap_size(text_size)
        bounds = QRectF(x, top_left.y(), size.width(), size.height())
        draw_keycap(painter, bounds, fill, outline)
        if draw_text:
            draw_keycap_text(painter, bounds, text_size, font, label, text_color)
        x += size.width()
