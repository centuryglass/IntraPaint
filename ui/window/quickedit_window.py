from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QPoint, QRect, QBuffer
from PyQt5.QtGui import QPainter, QPen
from PIL import Image, ImageOps
import PyQt5.QtGui as QtGui
import io, sys

class QuickEditWindow(QMainWindow):

    def __init__(self, width, height, im):
        super().__init__()
        self.drawing = False
        self.lastPoint = QPoint()

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
        self.image = QtGui.QPixmap.fromImage(self.qim)

        canvas = QtGui.QImage(self.qim.width(), self.qim.height(), QtGui.QImage.Format_ARGB32)
        self.canvas = QtGui.QPixmap.fromImage(canvas)
        self.canvas.fill(Qt.transparent)

        self.setGeometry(0, 0, self.qim.width(), self.qim.height())
        self.resize(self.image.width(), self.image.height())
        self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(QRect(0, 0, self.image.width(), self.image.height()), self.image)
        painter.drawPixmap(QRect(0, 0, self.canvas.width(), self.canvas.height()), self.canvas)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drawing = True
            self.lastPoint = event.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() and Qt.LeftButton and self.drawing:
            painter = QPainter(self.canvas)
            painter.setPen(QPen(Qt.red, (self.width()+self.height())/20, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawLine(self.lastPoint, event.pos())
            self.lastPoint = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button == Qt.LeftButton:
            self.drawing = False

    def getMask(self):
        image = self.canvas.toImage()
        buffer = QBuffer()
        buffer.open(QBuffer.ReadWrite)
        image.save(buffer, "PNG")
        pil_im = Image.open(io.BytesIO(buffer.data()))
        return pil_im

    def resizeEvent(self, event):
        self.image = QtGui.QPixmap.fromImage(self.qim)
        self.image = self.image.scaled(self.width(), self.height())

        canvas = QtGui.QImage(self.width(), self.height(), QtGui.QImage.Format_ARGB32)
        self.canvas = QtGui.QPixmap.fromImage(canvas)
        self.canvas.fill(Qt.transparent)

def getDrawnMask(width, height, image):
    """Get the user to draw an image mask, then return it as a PIL Image."""
    print('draw the area for inpainting, then close the window')
    app = QApplication(sys.argv)
    d = QuickEditWindow(width, height, image)
    app.exec_()
    return d.getMask()
