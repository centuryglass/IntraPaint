"""Icons for the color picker's tabs, drawn in color so they read on light and dark themes."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QConicalGradient, QIcon, QLinearGradient, QPainter, QPen, QPixmap

ICON_SIZE = 64


def _new_icon_pixmap() -> tuple[QPixmap, QPainter]:
    pixmap = QPixmap(ICON_SIZE, ICON_SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    return pixmap, painter


def wheel_icon() -> QIcon:
    """A hue ring around a small gray square."""
    pixmap, painter = _new_icon_pixmap()
    center = QPointF(ICON_SIZE / 2, ICON_SIZE / 2)
    gradient = QConicalGradient(center, 0.0)
    for step in range(7):
        gradient.setColorAt(step / 6, QColor.fromHsvF((step % 6) / 6, 1.0, 1.0))
    ring_width = ICON_SIZE * 0.16
    painter.setPen(QPen(gradient, ring_width))
    inset = ring_width / 2 + 2
    painter.drawEllipse(QRectF(inset, inset, ICON_SIZE - inset * 2, ICON_SIZE - inset * 2))
    square_side = ICON_SIZE * 0.36
    square = QRectF(center.x() - square_side / 2, center.y() - square_side / 2, square_side, square_side)
    square_gradient = QLinearGradient(square.topLeft(), square.bottomRight())
    square_gradient.setColorAt(0.0, QColor(Qt.GlobalColor.white))
    square_gradient.setColorAt(1.0, QColor(Qt.GlobalColor.black))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.fillRect(square, square_gradient)
    painter.end()
    return QIcon(pixmap)


def sliders_icon() -> QIcon:
    """Three gradient bars, black to red, green and blue."""
    pixmap, painter = _new_icon_pixmap()
    bar_height = ICON_SIZE * 0.2
    gap = (ICON_SIZE - bar_height * 3) / 4
    painter.setPen(Qt.PenStyle.NoPen)
    for index, color in enumerate((QColor(Qt.GlobalColor.red), QColor(Qt.GlobalColor.green),
                                   QColor(Qt.GlobalColor.blue))):
        top = gap + index * (bar_height + gap)
        bar_rect = QRectF(2, top, ICON_SIZE - 4, bar_height)
        gradient = QLinearGradient(bar_rect.topLeft(), bar_rect.topRight())
        gradient.setColorAt(0.0, QColor(Qt.GlobalColor.black))
        gradient.setColorAt(1.0, color)
        painter.setBrush(gradient)
        painter.drawRoundedRect(bar_rect, bar_height / 3, bar_height / 3)
    painter.end()
    return QIcon(pixmap)


def palettes_icon() -> QIcon:
    """A two by two grid of swatches."""
    pixmap, painter = _new_icon_pixmap()
    gap = ICON_SIZE * 0.08
    side = (ICON_SIZE - gap * 3) / 2
    painter.setPen(Qt.PenStyle.NoPen)
    colors = ('#e03c31', '#f2c12e', '#2f6fdb', '#3aa655')
    for index, color in enumerate(colors):
        left = gap + (index % 2) * (side + gap)
        top = gap + (index // 2) * (side + gap)
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(QRectF(left, top, side, side), side / 6, side / 6)
    painter.end()
    return QIcon(pixmap)


def alpha_icon() -> QIcon:
    """A checkerboard faded into an opaque color."""
    pixmap, painter = _new_icon_pixmap()
    cell = ICON_SIZE / 4
    for row in range(4):
        for column in range(4):
            color = QColor(Qt.GlobalColor.white) if (row + column) % 2 == 0 else QColor(Qt.GlobalColor.lightGray)
            painter.fillRect(QRectF(column * cell, row * cell, cell, cell), color)
    gradient = QLinearGradient(QPointF(0, 0), QPointF(ICON_SIZE, 0))
    gradient.setColorAt(0.0, QColor(47, 111, 219, 0))
    gradient.setColorAt(1.0, QColor(47, 111, 219, 255))
    painter.fillRect(QRectF(0, 0, ICON_SIZE, ICON_SIZE), gradient)
    painter.end()
    return QIcon(pixmap)
