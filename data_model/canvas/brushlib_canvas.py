from PyQt5.QtGui import QPainter, QPixmap, QPen, QImage, QColor
import PyQt5.QtGui as QtGui
from PyQt5.QtCore import Qt, QObject, QRect, QPoint, QLine, QSize, pyqtSignal
from PyQt5.QtWidgets import QGraphicsPixmapItem
from PIL import Image

from data_model.canvas.brushlib import Brushlib
from data_model.canvas.canvas import Canvas

class BrushlibCanvas(Canvas):
    def __init__(self, config, image):
        super().__init__(config, image)
        self._size = config.get('editSize')
        Brushlib.setSurfaceSize(config.get('editSize'))
        self._drawing = False
        self._scene = None
        self._scale = 1.0

    def setBrushSize(self, newSize):
        super().setBrushSize(newSize)
        # TODO:
        # newSize_log_radius = ???
        # Brushlib.set_radius(newSize_log_radius

    def addToScene(self, scene):
        self._scene = scene
        Brushlib.addToScene(scene)

    def setImage(self, initData):
        if isinstance(initData, QSize):
            Brushlib.setSurfaceSize(initData)
        elif isinstance(initData, str):
            image = QImage(initData)
            Brushlib.setSurfaceSize(image.size())
            Brushlib.loadImage(image)
        elif isinstance(initData, Image.Image):
            image = imageToQImage(initData)
            Brushlib.setSurfaceSize(image.size())
            Brushlib.loadImage(image)
        elif isinstance(initData, QImage):
            Brushlib.setSurfaceSize(initData.size())
            Brushlib.loadImage(initData)
        else:
            raise Exception(f"Invalid image param {initData}")
    
    def size(self):
        return self._size

    def width(self):
        return self._size.width()

    def height(self):
        return self._size.height()

    def getQImage(self):
        image = Brushlib.renderImage()
        if image.size() != self.size():
            image = image.scaled(self.size())
        return image

    def resize(self, size):
        self._size = size
        size = QSize(int(size.width() * self._scale), int(size.height() * self._scale))
        if size != Brushlib.surfaceSize():
            Brushlib.setSurfaceSize(size)

    def startStroke(self):
        Brushlib.startStroke()
        self._drawing = True

    def endStroke(self):
        Brushlib.endStroke()
        self._drawing = False

    def _draw(self, pos, color, sizeMultiplier = 1.0, sizeOverride = None):
        Brushlib.setBrushColor(color)
        if not self._drawing:
            self.startStroke()
            if isinstance(pos, QLine):
                Brushlib.strokeTo(float(pos.x1()), float(pos.y1()), sizeMultiplier, 0.0, 0.0)
        if isinstance(pos, QLine):
            Brushlib.strokeTo(float(pos.x2()), float(pos.y2()), sizeMultiplier, 0.0, 0.0)
        else: #QPoint
            Brushlib.strokeTo(float(pos.x()), float(pos.y()), sizeMultiplier, 0.0, 0.0)

    def drawPoint(self, point, color, sizeMultiplier = 1.0, sizeOverride = None):
        if Brushlib.eraser() != 0.0:
            Brushlib.set_eraser(0.0)
        self._draw(point, color, sizeMultiplier, sizeOverride)

    def drawLine(self, line, color, sizeMultiplier = 1.0, sizeOverride = None):
        if Brushlib.eraser() != 0.0:
            Brushlib.set_eraser(0.0)
        self._draw(line, color, sizeMultiplier, sizeOverride)

    def erasePoint(self, point, color, sizeMultiplier = 1.0, sizeOverride = None):
        if Brushlib.eraser() != 1.0:
            Brushlib.set_eraser(1.0)
        self._draw(point, color, sizeMultiplier, sizeOverride)

    def eraseLine(self, line, color, sizeMultiplier = 1.0, sizeOverride = None):
        if Brushlib.eraser() != 1.0:
            Brushlib.set_eraser(1.0)
        self._draw(line, color, sizeMultiplier, sizeOverride)

    def fill(self, color):
        size = self.size()
        image = QImage(size, QImage.Format_ARGB32)
        painter = QPainter(image)
        painter.fillRect(0, 0, size.width(), size.height(), color)
        painter.end()
        Brushlib.loadImage(image)

    def clear(self):
        Brushlib.clearSurface()
