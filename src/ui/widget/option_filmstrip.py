"""A row of thumbnails of a batch's generated options, each labeled with the digit key that opens it.

The generated image selector shows it under its single view. It draws from the images it is given and holds no batch
state.
"""
from typing import Optional

from PySide6.QtCore import QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QImage, QMouseEvent, QPainter, QPaintEvent, QPalette, QPen, QPixmap, \
    QResizeEvent, QWheelEvent
from PySide6.QtWidgets import QSizePolicy, QWidget

from src.util.visual.keycap import KEYCAP_DEPTH, draw_keycap, keycap_colors, keycap_font, keycap_size

THUMB_SIZE = 64
SPACING = 8
# Options past this index have no digit key:
MAX_DIGIT_KEY = 9
BACKGROUND = QColor(8, 9, 10)
PLACEHOLDER_FILL = QColor(36, 38, 42)


class OptionFilmstrip(QWidget):
    """A row of thumbnails of every option, each with its digit key, under the single view. Clicking one focuses it.

    When the thumbnails don't fit the width, the row scrolls with the mouse wheel and follows the focused option.
    """

    option_clicked = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self._images: list[QImage] = []
        self._ready: list[bool] = []
        self._pixmaps: dict[int, tuple[int, QPixmap]] = {}
        self._focus = 0
        self._thumb_size = THUMB_SIZE
        self._scroll = 0
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

    def set_options(self, images: list[QImage], ready: list[bool], focus: int) -> None:
        """Shows thumbnails of `images`, a loading state for each one that isn't `ready`, and marks `focus`."""
        if [id(image) for image in images] != [id(image) for image in self._images]:
            self._pixmaps.clear()
        self._images = list(images)
        self._ready = list(ready)
        self._focus = focus
        self._scroll_to_focus()
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

    def _thumb_width(self) -> int:
        image_size = self._images[0].size()
        return max(1, round(self._thumb_size * image_size.width() / max(image_size.height(), 1)))

    def _total_width(self) -> int:
        """Returns the width of the whole row of thumbnails."""
        if len(self._images) == 0:
            return 0
        count = len(self._images)
        return count * self._thumb_width() + (count - 1) * SPACING

    def _max_scroll(self) -> int:
        return max(0, self._total_width() - (self.width() - SPACING * 2))

    def _set_scroll(self, scroll: int) -> None:
        scroll = max(0, min(scroll, self._max_scroll()))
        if scroll != self._scroll:
            self._scroll = scroll
            self.update()

    def _scroll_to_focus(self) -> None:
        """Scrolls the row just far enough to show the focused thumbnail."""
        if len(self._images) == 0:
            return
        width = self._thumb_width()
        left = self._focus * (width + SPACING)
        visible = self.width() - SPACING * 2
        if left < self._scroll:
            self._set_scroll(left)
        elif left + width > self._scroll + visible:
            self._set_scroll(left + width - visible)
        else:
            self._set_scroll(self._scroll)

    def _thumb_rects(self) -> list[QRect]:
        if len(self._images) == 0:
            return []
        width = self._thumb_width()
        height = self._thumb_size
        total = self._total_width()
        x = SPACING - self._scroll if total > self.width() - SPACING * 2 else (self.width() - total) // 2
        y = (self.height() - height) // 2
        return [QRect(x + i * (width + SPACING), y, width, height) for i in range(len(self._images))]

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:  # pylint: disable=invalid-name
        """Keeps the focused thumbnail visible as the width changes."""
        super().resizeEvent(event)
        self._scroll_to_focus()

    def wheelEvent(self, event: Optional[QWheelEvent]) -> None:  # pylint: disable=invalid-name
        """Scrolls the row, when it overflows, by either wheel axis."""
        if event is None or self._max_scroll() == 0:
            super().wheelEvent(event)
            return
        delta = event.angleDelta()
        step = delta.x() if abs(delta.x()) > abs(delta.y()) else delta.y()
        self._set_scroll(self._scroll - step)
        event.accept()

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
        max_scroll = self._max_scroll()
        if max_scroll > 0:
            # A thin scroll indicator along the bottom edge:
            track = self.width() - SPACING * 2
            thumb_width = max(16, track * track // (track + max_scroll))
            thumb_x = SPACING + (track - thumb_width) * self._scroll // max_scroll
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.palette().color(QPalette.ColorRole.Highlight))
            painter.drawRoundedRect(QRectF(thumb_x, self.height() - 4, thumb_width, 3), 1.5, 1.5)
        painter.end()

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:  # pylint: disable=invalid-name
        """Focuses the clicked option."""
        if event is None:
            return
        for i, rect in enumerate(self._thumb_rects()):
            if rect.contains(event.position().toPoint()):
                self.option_clicked.emit(i)
                return
