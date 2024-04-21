from PyQt5.QtGui import QPainter, QPixmap, QPen, QImage, QColor
import PyQt5.QtGui as QtGui
from PyQt5.QtCore import Qt, QObject, QRect, QPoint, QLine, QSize, pyqtSignal
from PyQt5.QtWidgets import QGraphicsPixmapItem
from PIL import Image

from ui.image_utils import imageToQImage, qImageToImage 

class _SignalWrapper(QObject):
    enabledStateChanged = pyqtSignal(bool)

class Canvas():
    def __init__(self, config, image):
        super().__init__()
        self._config = config
        self._brushSize = 1
        self._image = None
        self._signalWrapper = _SignalWrapper()
        self.enabledStateChanged = self._signalWrapper.enabledStateChanged
        if image is not None:
            self.setImage(image)
        else:
            self.setImage(config.get('editSize'))
        self._enabled = True


    def enabled(self):
        return self._enabled

    def setEnabled(self, isEnabled):
        if isEnabled != self._enabled:
            self._enabled = isEnabled
            self.setVisible(isEnabled)
            self.enabledStateChanged.emit(isEnabled)
        
    def brushSize(self):
        return self._brushSize

    def setBrushSize(self, newSize):
        self._brushSize = newSize

    def addToScene(self, scene):
        raise Exception("Canvas.addToScene not implemented")

    def setImage(self, initData):
        raise Exception("Canvas.setImage() not implemented")
    
    def size(self):
        raise Exception("Canvas.size() not implemented")

    def width(self):
        raise Exception("Canvas.width() not implemented")

    def height(self):
        raise Exception("Canvas.height() not implemented")

    def getQImage(self):
        raise Exception("Canvas.getQImage() not implemented")

    def getImage(self):
        return qImageToImage(self.getQImage())

    def getColorAtPoint(self, point):
        if self.getQImage().rect().contains(point):
            return self.getQImage().pixelColor(point)
        return QColor(0, 0, 0, 0)

    def resize(self, size):
        raise Exception("Canvas.resize() not implemented")

    def startStroke(self):
        raise Exception("Canvas.startStroke() not implemented")

    def endStroke(self):
        raise Exception("Canvas.endStroke() not implemented")

    def drawPoint(self, point, color, sizeMultiplier = 1.0, sizeOverride = None):
        raise Exception("Canvas.drawPoint() not implemented")

    def drawLine(self, line, color, sizeMultiplier = 1.0, sizeOverride = None):
        raise Exception("Canvas.drawLine() not implemented")

    def erasePoint(self, point, color, sizeMultiplier = 1.0, sizeOverride = None):
        raise Exception("Canvas.erasePoint() not implemented")

    def eraseLine(self, line, color, sizeMultiplier = 1.0, sizeOverride = None):
        raise Exception("Canvas.eraseLine() not implemented")

    def fill(self, color):
        raise Exception("Canvas.fill() not implemented")

    def clear(self):
        raise Exception("Canvas.clear() not implemented")
