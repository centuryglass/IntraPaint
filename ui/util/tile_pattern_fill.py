"""Fill a QPixmap with an alternating tile pattern."""
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QColor, QPainter


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

