"""
Absolutely minimal editing window meant for performing a single inpainting operation using GLID3-XL.
"""
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QPoint, QRect, QBuffer
from PyQt5.QtGui import QPainter, QPen
from PIL import Image, ImageOps
import PyQt5.QtGui as QtGui
import io, sys

class QuickEditWindow(QMainWindow):

    def __init__(self, width, height, im):
        super().__init__()
        self._drawing = False
        self._last_point = QPoint()

        try:
            if isinstance(im, str):
                self.qim = QtGui.QImage(im)
            elif isinstance(im, Image.Image):
                self.qim = QtGui.QImage(im.tobytes("raw","RGB"), im.width, im.height, QtGui.QImage.Format_RGB888)
            else:
                raise Exception(f"Invalid source image type: {im}")
        except Exception as err:
            print(f"Error: {err}")
            sys.exit()
        self._image = QtGui.QPixmap.fromImage(self.qim)

        canvas = QtGui.QImage(self.qim.width(), self.qim.height(), QtGui.QImage.Format_ARGB32)
        self._canvas = QtGui.QPixmap.fromImage(canvas)
        self._canvas.fill(Qt.transparent)

        self.setGeometry(0, 0, self.qim.width(), self.qim.height())
        self.resize(self._image.width(), self._image.height())
        self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(QRect(0, 0, self._image.width(), self._image.height()), self._image)
        painter.drawPixmap(QRect(0, 0, self._canvas.width(), self._canvas.height()), self._canvas)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drawing = True
            self._last_point = event.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() and Qt.LeftButton and self._drawing:
            painter = QPainter(self._canvas)
            painter.setPen(QPen(Qt.red, (self.width()+self.height())/20, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawLine(self._last_point, event.pos())
            self._last_point = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button == Qt.LeftButton:
            self._drawing = False

    def get_mask(self):
        image = self._canvas.toImage()
        buffer = QBuffer()
        buffer.open(QBuffer.ReadWrite)
        image.save(buffer, "PNG")
        pil_im = Image.open(io.BytesIO(buffer.data()))
        return pil_im

    def resizeEvent(self, event):
        self._image = QtGui.QPixmap.fromImage(self.qim)
        self._image = self._image.scaled(self.width(), self.height())

        canvas = QtGui.QImage(self.width(), self.height(), QtGui.QImage.Format_ARGB32)
        self._canvas = QtGui.QPixmap.fromImage(canvas)
        self._canvas.fill(Qt.transparent)

def get_drawn_mask(width, height, image):
    """Get the user to draw an image mask, then return it as a PIL Image."""
    print('draw the area for inpainting, then close the window')
    app = QApplication(sys.argv)
    d = QuickEditWindow(width, height, image)
    app.exec_()
    return d.get_mask()
