"""The sample image under the Smudge, Filter and Clone stamp previews.

Those brushes change existing pixels, so their previews need content to act on. `backdrop_image` draws one shared
sample with procedural `QPainter` calls, so it has no binary assets and does not depend on theme or fonts. A tile
has a fixed 2:1 aspect and is repeated across the preview's width, so it never looks stretched. Each tile holds:

- Three saturated bands with hard edges and a luminance ramp over them, for smudging and color filters.
- A fine checker, for blur and sharpen.
- An asymmetric motif (`backdrop_motif_rect`), for telling what the clone stamp copied and where it went.
"""
from functools import lru_cache

from PySide6.QtCore import QPointF, QRect, QSize, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPolygonF

TILE_ASPECT = 2
MIN_TILE_HEIGHT = 8
BAND_COLORS = (QColor(230, 90, 40), QColor(40, 170, 140), QColor(170, 60, 200))
CHECKER_DARK = QColor(30, 30, 30)
CHECKER_LIGHT = QColor(235, 235, 235)
MOTIF_BASE = QColor(250, 200, 40)
MOTIF_ACCENT = QColor(30, 40, 120)
BACKDROP_BASE = QColor(245, 245, 245)

# Tile layout as fractions of the tile's width.
BANDS_END = 0.45
CHECKER_END = 0.70


def tile_size(size: QSize) -> QSize:
    """Returns the size of one backdrop tile for a preview of `size`: full height at the fixed aspect."""
    height = max(size.height(), MIN_TILE_HEIGHT)
    return QSize(height * TILE_ASPECT, height)


def backdrop_motif_rect(size: QSize) -> QRect:
    """Returns the motif's bounds within the first tile of a backdrop for a preview of `size`."""
    tile = tile_size(size)
    left = round(tile.width() * CHECKER_END)
    inset = tile.height() // 8
    return QRect(left + inset, inset, tile.width() - left - 2 * inset, tile.height() - 2 * inset)


def backdrop_image(size: QSize) -> QImage:
    """Returns a new opaque ARGB32_Premultiplied image of `size` holding the repeated backdrop tile."""
    if size.isEmpty():
        return QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    return _cached_backdrop(size.width(), size.height()).copy()


@lru_cache(maxsize=8)
def _cached_backdrop(width: int, height: int) -> QImage:
    """Draws the backdrop once per size. `backdrop_image` hands out copies, so callers never alter the cache."""
    size = QSize(width, height)
    tile = _draw_tile(size)
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(BACKDROP_BASE)
    painter = QPainter(image)
    for x in range(0, width, tile.width()):
        painter.drawImage(x, 0, tile)
    painter.end()
    return image


def _draw_tile(size: QSize) -> QImage:
    tile_dim = tile_size(size)
    tile = QImage(tile_dim, QImage.Format.Format_ARGB32_Premultiplied)
    tile.fill(BACKDROP_BASE)
    painter = QPainter(tile)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    _draw_bands(painter, tile_dim)
    _draw_checker(painter, tile_dim)
    _draw_motif(painter, backdrop_motif_rect(size))
    painter.end()
    return tile


def _draw_bands(painter: QPainter, tile: QSize) -> None:
    band_area = round(tile.width() * BANDS_END)
    edges = [round(band_area * i / len(BAND_COLORS)) for i in range(len(BAND_COLORS) + 1)]
    for color, left, right in zip(BAND_COLORS, edges, edges[1:]):
        painter.fillRect(left, 0, right - left, tile.height(), color)
    # Light at the top fading to dark at the bottom, so each band spans a range of brightness.
    ramp = QLinearGradient(0, 0, 0, tile.height())
    ramp.setColorAt(0.0, QColor(255, 255, 255, 110))
    ramp.setColorAt(0.5, QColor(255, 255, 255, 0))
    ramp.setColorAt(1.0, QColor(0, 0, 0, 130))
    painter.fillRect(0, 0, band_area, tile.height(), ramp)


def _draw_checker(painter: QPainter, tile: QSize) -> None:
    left = round(tile.width() * BANDS_END)
    right = round(tile.width() * CHECKER_END)
    cell = max(2, tile.height() // 16)
    for row, y in enumerate(range(0, tile.height(), cell)):
        for column, x in enumerate(range(left, right, cell)):
            color = CHECKER_DARK if (row + column) % 2 == 0 else CHECKER_LIGHT
            painter.fillRect(x, y, min(cell, right - x), min(cell, tile.height() - y), color)


def _draw_motif(painter: QPainter, bounds: QRect) -> None:
    """Draws a disc with a triangular notch in one corner and a small dot opposite it, with no mirror symmetry."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    diameter = min(bounds.width(), bounds.height())
    disc = QRect(bounds.left() + (bounds.width() - diameter) // 2, bounds.top() + (bounds.height() - diameter) // 2,
                 diameter, diameter)
    painter.setBrush(MOTIF_BASE)
    painter.drawEllipse(disc)
    clip = QPainterPath()
    clip.addEllipse(disc)
    painter.setClipPath(clip)
    painter.setBrush(MOTIF_ACCENT)
    center = QPointF(disc.center())
    right = disc.right() + 1
    painter.drawPolygon(QPolygonF([center, QPointF(right, disc.top()), QPointF(right, center.y())]))
    painter.setClipping(False)
    dot = max(2, diameter // 5)
    painter.drawEllipse(disc.left() + diameter // 5, disc.bottom() - diameter // 5 - dot, dot, dot)
