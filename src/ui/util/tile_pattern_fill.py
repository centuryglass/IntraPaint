"""Fill a QPixmap with an alternating tile pattern."""
from typing import Optional
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QColor, QPainter

TRANSPARENCY_PATTERN_BACKGROUND_DIM = 640
TRANSPARENCY_PATTERN_TILE_DIM = 16


def tile_pattern_fill(pixmap: QPixmap,
                      tile_size: int,
                      tile_color_1: QColor | Qt.GlobalColor,
                      tile_color_2: QColor | Qt.GlobalColor) -> None:
    """Draws an alternating tile pattern onto a QPixmap."""
    fill_pixmap_size = tile_size * 2
    fill_pixmap = QPixmap(QSize(fill_pixmap_size, fill_pixmap_size))
    fill_pixmap.fill(tile_color_1)
    painter = QPainter(fill_pixmap)
    for x in range(tile_size, fill_pixmap_size + tile_size, tile_size):
        for y in range(tile_size, fill_pixmap_size + tile_size, tile_size):
            if (x % (tile_size * 2)) == (y % (tile_size * 2)):
                continue
            painter.fillRect(x - tile_size, y - tile_size, tile_size, tile_size, tile_color_2)
    painter.end()
    painter = QPainter(pixmap)
    painter.drawTiledPixmap(0, 0, pixmap.width(), pixmap.height(), fill_pixmap)
    painter.end()


def get_transparency_tile_pixmap(size: Optional[QSize] = None) -> QPixmap:
    """Returns a tiling pixmap used to represent transparency."""
    if size is None:
        size = QSize(TRANSPARENCY_PATTERN_BACKGROUND_DIM, TRANSPARENCY_PATTERN_BACKGROUND_DIM)
    transparency_pixmap = QPixmap(size)
    tile_pattern_fill(transparency_pixmap, TRANSPARENCY_PATTERN_TILE_DIM, Qt.GlobalColor.lightGray,
                      Qt.GlobalColor.darkGray)
    return transparency_pixmap
