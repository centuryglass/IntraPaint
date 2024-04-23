from PyQt5.QtGui import QPainter, QPixmap, QPen, QImage, QColor
import PyQt5.QtGui as QtGui
from PyQt5.QtCore import Qt, QObject, QRect, QPoint, QLine, QSize, pyqtSignal
from PyQt5.QtWidgets import QGraphicsPixmapItem
from PIL import Image
from datetime import datetime

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
        self._undoStack = []
        self._redoStack = []
        if image is not None:
            self.setImage(image)
        else:
            self.setImage(config.get('editSize'))
        self._enabled = True

    def _saveUndoState(self, clearRedoStack=True):
        image = self.getQImage().copy()
        self._undoStack.append(image)
        maxUndoCount = self._config.get('maxUndo')
        if len(self._undoStack) > maxUndoCount:
            self._undoStack = self._undoStack[-maxUndoCount:]
        if clearRedoStack:
            self._redoStack.clear()

    def undo(self):
        if len(self._undoStack) == 0:
            return
        image = self.getQImage().copy()
        self._redoStack.append(image)
        newImage = self._undoStack.pop()
        if newImage.size() != self.size():
            newImage = newImage.scaled(self.size())
        self.setImage(newImage)

    def redo(self):
        if len(self._redoStack) == 0:
            return
        self._saveUndoState(False)
        image = self._redoStack.pop()
        if image.size() != self.size():
            image = image.scaled(self.size())
        self.setImage(image)


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

    def setImage(self, imageData):
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
        self._saveUndoState()

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
        self._saveUndoState()

    def clear(self):
        self._saveUndoState()
