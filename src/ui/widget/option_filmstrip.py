"""A row of thumbnails of a batch's generated options, each labeled with the digit key that opens it.

The generated image selector shows it under its single view. It draws from the images it is given and holds no batch
state.
"""
from typing import Optional

from PySide6.QtCore import QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QImage, QMouseEvent, QPainter, QPaintEvent, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from src.util.visual.keycap import KEYCAP_DEPTH, draw_keycap, keycap_colors, keycap_font, keycap_size

THUMB_SIZE = 64
SPACING = 8
# Options past this index have no digit key:
MAX_DIGIT_KEY = 9
BACKGROUND = QColor(8, 9, 10)
PLACEHOLDER_FILL = QColor(36, 38, 42)


class OptionFilmstrip(QWidget):
    """A row of thumbnails of every option, each with its digit key, under the single view. Clicking one focuses it."""

    option_clicked = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self._images: list[QImage] = []
        self._ready: list[bool] = []
        self._pixmaps: dict[int, tuple[int, QPixmap]] = {}
        self._focus = 0
        self._thumb_size = THUMB_SIZE
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

    def set_options(self, images: list[QImage], ready: list[bool], focus: int) -> None:
        """Shows thumbnails of `images`, a loading state for each one that isn't `ready`, and marks `focus`."""
        if [id(image) for image in images] != [id(image) for image in self._images]:
            self._pixmaps.clear()
        self._images = list(images)
        self._ready = list(ready)
        self._focus = focus
        self.update()

    def set_thumb_size(self, size: int) -> None:
        """Sets the height of each thumbnail."""
        if size != self._thumb_size:
            self._thumb_size = size
            self._pixmaps.clear()
            self.updateGeometry()
            self.update()

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the thumbnail height plus spacing, at any width."""
        return QSize(0, self._thumb_size + SPACING * 2)

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the same size as `sizeHint`."""
        return self.sizeHint()

    def _thumb_rects(self) -> list[QRect]:
        if len(self._images) == 0:
            return []
        image_size = self._images[0].size()
        height = self._thumb_size
        width = max(1, round(height * image_size.width() / max(image_size.height(), 1)))
        count = len(self._images)
        total = count * width + (count - 1) * SPACING
        available = self.width() - SPACING * 2
        if total > available > 0:
            scale = available / total
            width = max(1, int(width * scale))
            height = max(1, int(height * scale))
            total = count * width + (count - 1) * SPACING
        x = (self.width() - total) // 2
        y = (self.height() - height) // 2
        return [QRect(x + i * (width + SPACING), y, width, height) for i in range(count)]

    def paintEvent(self, _event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draws each thumbnail, its digit key, and the focus ring."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), BACKGROUND)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = keycap_font(self.font())
        metrics = QFontMetrics(font)
        fill, outline, text_color = keycap_colors(self.palette())
        for i, rect in enumerate(self._thumb_rects()):
            if self._ready[i]:
                cached = self._pixmaps.get(i)
                if cached is None or cached[0] != rect.width():
                    cached = (rect.width(), QPixmap.fromImage(self._images[i].scaled(
                        rect.size(), Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)))
                    self._pixmaps[i] = cached
                painter.drawPixmap(rect, cached[1])
            else:
                painter.fillRect(rect, PLACEHOLDER_FILL)
            if i <= MAX_DIGIT_KEY:
                cap_size = keycap_size(QSize(metrics.horizontalAdvance(str(i)), metrics.height()))
                cap = QRectF(rect.left() + 2, rect.bottom() - cap_size.height() - 1, cap_size.width(),
                             cap_size.height())
                draw_keycap(painter, cap, fill, outline)
                painter.setPen(text_color)
                painter.setFont(font)
                painter.drawText(cap.adjusted(0, 0, 0, -KEYCAP_DEPTH), Qt.AlignmentFlag.AlignCenter, str(i))
            if i == self._focus:
                painter.setPen(QPen(self.palette().color(QPalette.ColorRole.Highlight), 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(QRectF(rect).adjusted(-2, -2, 2, 2), 3, 3)
        painter.end()

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:  # pylint: disable=invalid-name
        """Focuses the clicked option."""
        if event is None:
            return
        for i, rect in enumerate(self._thumb_rects()):
            if rect.contains(event.position().toPoint()):
                self.option_clicked.emit(i)
                return
