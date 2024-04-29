from PyQt5.QtGui import QPainter, QPixmap, QPen, QImage, QColor
import PyQt5.QtGui as QtGui
from PyQt5.QtCore import Qt, QObject, QRect, QPoint, QLine, QSize, pyqtSignal
from PyQt5.QtWidgets import QGraphicsPixmapItem
from PIL import Image
import math

from data_model.canvas.brushlib import Brushlib
from data_model.canvas.canvas import Canvas
from ui.image_utils import imageToQImage, qImageToImage 

class BrushlibCanvas(Canvas):
    def __init__(self, config, image):
        super().__init__(config, image)
        config.connect(self, 'sketchBrushSize', lambda size: self.setBrushSize(size))
        self.setBrushSize(config.get('sketchBrushSize'))
        self._size = config.get('editSize')
        Brushlib.setSurfaceSize(config.get('editSize'))
        self._drawing = False
        self._scene = None
        self._scale = 1.0
        self.hasSketch = False
        self._savedBrushSize = None
        Brushlib.loadBrush(config.get('brush_default'))

    def setBrush(self, brushPath):
        Brushlib.loadBrush(brushPath)
        self.setBrushSize(self.brushSize())

    def setBrushSize(self, newSize):
        super().setBrushSize(newSize)
        # TODO:
        newSize_log_radius = math.log(newSize / 2)
        Brushlib.set_radius(newSize_log_radius)

    def addToScene(self, scene, zValue=None):
        self._scene = scene
        Brushlib.addToScene(scene, zValue)

    def setImage(self, imageData):
        Brushlib.clearSurface()
        if isinstance(imageData, QSize):
            if self.size() != imageData:
                Brushlib.setSurfaceSize(imageData)
        elif isinstance(imageData, str):
            image = QImage(imageData)
            if self.size() != image.size():
                Brushlib.setSurfaceSize(image.size())
            Brushlib.loadImage(image)
        elif isinstance(imageData, Image.Image):
            image = imageToQImage(imageData)
            if self.size() != image.size():
                Brushlib.setSurfaceSize(image.size())
            Brushlib.loadImage(image)
        elif isinstance(imageData, QImage):
            if self.size() != imageData.size():
                Brushlib.setSurfaceSize(imageData.size())
            Brushlib.loadImage(imageData)
        else:
            raise Exception(f"Invalid image param {imageData}")
    
    def size(self):
        return Brushlib.surfaceSize()

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
            image = self.getQImage().scaled(size)
            self.setImage(image)

    def startStroke(self):
        super().startStroke()
        Brushlib.startStroke()
        self._drawing = True

    def endStroke(self):
        Brushlib.endStroke()
        self._drawing = False
        if self._savedBrushSize is not None:
            self.setBrushSize(self._savedBrushSize)
            self._savedBrushSize = None

    def _draw(self, pos, color, sizeMultiplier, sizeOverride = None):
        if sizeOverride is not None:
            if self._savedBrushSize is None:
                self._savedBrushSize = self.brushSize()
            self.setBrushSize(sizeOverride)
        self.hasSketch = True
        Brushlib.setBrushColor(color)
        if not self._drawing:
            self.startStroke()
            if isinstance(pos, QLine):
                if sizeMultiplier is None:
                    Brushlib.basicStrokeTo(float(pos.x1()), float(pos.y1()))
                else:
                    Brushlib.strokeTo(float(pos.x1()), float(pos.y1()), sizeMultiplier, 0.0, 0.0)
        if isinstance(pos, QLine):
                if sizeMultiplier is None:
                    Brushlib.basicStrokeTo(float(pos.x2()), float(pos.y2()))
                else:
                    Brushlib.strokeTo(float(pos.x2()), float(pos.y2()), sizeMultiplier, 0.0, 0.0)
        else: #QPoint
            if sizeMultiplier is None:
                Brushlib.basicStrokeTo(float(pos.x()), float(pos.y()))
            else:
                Brushlib.strokeTo(float(pos.x()), float(pos.y()), sizeMultiplier, 0.0, 0.0)

    def drawPoint(self, point, color, sizeMultiplier, sizeOverride = None):
        Brushlib.set_eraser(0.0)
        self._draw(point, color, sizeMultiplier, sizeOverride)

    def drawLine(self, line, color, sizeMultiplier, sizeOverride = None):
        Brushlib.set_eraser(0.0)
        self._draw(line, color, sizeMultiplier, sizeOverride)

    def erasePoint(self, point, color, sizeMultiplier, sizeOverride = None):
        Brushlib.set_eraser(1.0)
        self._draw(point, color, sizeMultiplier, sizeOverride)

    def eraseLine(self, line, color, sizeMultiplier, sizeOverride = None):
        Brushlib.set_eraser(1.0)
        self._draw(line, color, sizeMultiplier, sizeOverride)

    def fill(self, color):
        super().fill(color)
        self.hasSketch = True
        size = self.size()
        image = QImage(size, QImage.Format_ARGB32)
        painter = QPainter(image)
        painter.fillRect(0, 0, size.width(), size.height(), color)
        painter.end()
        Brushlib.loadImage(image)

    def clear(self):
        super().clear()
        self.hasSketch = False
        Brushlib.clearSurface()

