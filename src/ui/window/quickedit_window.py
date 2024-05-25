"""
Minimal editing window meant for performing a single inpainting operation using GLID-3-XL.
"""
from typing import Optional
import io
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import Qt, QPoint, QRect, QBuffer
from PyQt5.QtGui import QPainter, QPen, QPixmap, QImage, QPaintEvent, QMouseEvent, QResizeEvent
from PIL import Image


class QuickEditWindow(QMainWindow):
    """A minimal editing window meant for performing a single inpainting operation using GLID-3-XL."""

    def __init__(self, im: Image.Image | str) -> None:
        """Create the window at a given size and load an image for inpainting.

        Parameters
        ----------
        im : str or PIL image
            An image or image path to edit
        """
        super().__init__()
        self._drawing = False
        self._last_point = QPoint()

        if isinstance(im, str):
            self.qim = QImage(im)
        elif isinstance(im, Image.Image):
            self.qim = QImage(im.tobytes('raw', 'RGB'), im.width, im.height, QImage.Format_RGB888)
        else:
            raise TypeError(f'Invalid source image type: {im}')
        self._image = QPixmap.fromImage(self.qim)

        canvas = QImage(self.qim.width(), self.qim.height(), QImage.Format_ARGB32)
        self._canvas = QPixmap.fromImage(canvas)
        self._canvas.fill(Qt.GlobalColor.transparent)

        self.setGeometry(0, 0, self.qim.width(), self.qim.height())
        self.resize(self._image.width(), self._image.height())
        self.show()

    def paintEvent(self, unused_event: Optional[QPaintEvent]) -> None:
        """Draws the image and mask canvas in the window."""
        painter = QPainter(self)
        painter.drawPixmap(QRect(0, 0, self._image.width(), self._image.height()), self._image)
        painter.drawPixmap(QRect(0, 0, self._canvas.width(), self._canvas.height()), self._canvas)

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Start drawing the mask on left-click."""
        if event is None:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._drawing = True
            self._last_point = event.pos()

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
        """Draw to the mask on mouse move when the left mouse button is held."""
        if event is None:
            return
        if event.buttons() == Qt.MouseButton.LeftButton and self._drawing:
            painter = QPainter(self._canvas)
            painter.setPen(QPen(Qt.red, (self.width() + self.height()) / 20, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawLine(self._last_point, event.pos())
            self._last_point = event.pos()
            self.update()

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
        """Stop drawing when the left mouse button is released."""
        if event is None:
            return
        if event.button == Qt.LeftButton:
            self._drawing = False

    def get_mask(self) -> Image.Image:
        """Returns the image mask as a PIL Image."""
        image = self._canvas.toImage()
        buffer = QBuffer()
        buffer.open(QBuffer.ReadWrite)
        image.save(buffer, 'PNG')
        pil_im = Image.open(io.BytesIO(buffer.data()))
        return pil_im

    def resizeEvent(self, unused_event: Optional[QResizeEvent]) -> None:
        """adjust image and canvas scale on resize."""
        self._image = QPixmap.fromImage(self.qim)
        self._image = self._image.scaled(self.width(), self.height())

        canvas = QImage(self.width(), self.height(), QImage.Format_ARGB32)
        self._canvas = QPixmap.fromImage(canvas)
        self._canvas.fill(Qt.GlobalColor.transparent)


def get_drawn_mask(image: Image.Image | str) -> Image.Image:
    """Get the user to draw an image mask, then return it as a PIL Image."""
    print('draw the area for inpainting, then close the window')
    app = QApplication(sys.argv)
    d = QuickEditWindow(image)
    app.exec_()
    return d.get_mask()
