from PyQt5.QtGui import QPainter, QPixmap, QPen, QImage, QColor
import PyQt5.QtGui as QtGui
from PyQt5.QtCore import Qt, QRect, QPoint, QLine, QSize, pyqtSignal
from PyQt5.QtWidgets import QGraphicsPixmapItem
from PIL import Image
from data_model.canvas.canvas import Canvas

from ui.image_utils import imageToQImage, qImageToImage 

class PixmapCanvas(Canvas, QGraphicsPixmapItem):
    def __init__(self, config, image):
        super(PixmapCanvas, self).__init__(config, image)
        self._config = config
        self._brushSize = 1
        self._drawing = False

    def addToScene(self, scene):
        zValue = 0
        for item in scene.items():
            zValue = max(zValue, item.zValue() + 1)
        self.setZValue(zValue)
        scene.addItem(self)

    def setImage(self, imageData):
        self._image = None
        if isinstance(imageData, QSize): # Blank initial image:
            pixmap = QPixmap(imageData)
            pixmap.fill(Qt.transparent)
            self.setPixmap(pixmap)
        elif isinstance(imageData, str): # Load from image path:
            self.setPixmap(QPixmap(imageData, "RGBA"))
        elif isinstance(imageData, Image.Image):
            self.setPixmap(QPixmap.fromImage(imageToQImage(imageData)))
        elif isinstance(imageData, QImage):
            self._image = imageData
            self.setPixmap(QPixmap.fromImage(imageData))
        else:
            raise Exception(f"Invalid image param {imageData}")

    def size(self):
        return self.pixmap().size()

    def width(self):
        return self.pixmap().width()

    def height(self):
        return self.pixmap().height()

    def getQImage(self):
        if self._image is None:
            self._image = self.pixmap().toImage()
        return self._image

    def getImage(self):
        return qImageToImage(self.getQImage())

    def getColorAtPoint(self, point):
        if self.getQImage().rect().contains(point):
            return self.getQImage().pixelColor(point)
        return QColor(0, 0, 0, 0)

    def resize(self, size):
        if not isinstance(size, QSize):
            raise Exception(f"Invalid resize param {size}")
        if size != self.size():
            self.setPixmap(self.pixmap().scaled(size))
            self._handleChanges()

    def startStroke(self):
        super().startStroke()
        if self._drawing:
            self.endStroke()
        self._drawing = True

    def endStroke(self):
        if self._drawing:
            self._drawing = False

    def _baseDraw(self, pixmap, pos, color, compositionMode, sizeMultiplier=1.0, sizeOverride = None):
        painter = QPainter(pixmap)
        painter.setCompositionMode(compositionMode)
        size = int(self._brushSize * sizeMultiplier) if sizeOverride is None else int(sizeOverride)
        painter.setPen(QPen(color, size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        if isinstance(pos, QLine):
            painter.drawLine(pos)
        else: # Should be QPoint
            painter.drawPoint(pos)
        painter.end()

    def _draw(self, pos, color, compositionMode, sizeMultiplier=1.0, sizeOverride = None):
        if sizeMultiplier is None:
            sizeMultiplier=1.0
        if not self.enabled():
            return
        pixmap = QPixmap(self.size())
        pixmap.swap(self.pixmap())
        self._baseDraw(pixmap, pos, color, compositionMode, sizeMultiplier, sizeOverride)
        self.setPixmap(pixmap)
        self._handleChanges()

    def drawPoint(self, point, color, sizeMultiplier = 1.0, sizeOverride = None):
        if not self._drawing:
            self.startStroke()
        self._draw(point, color, QPainter.CompositionMode.CompositionMode_SourceOver, sizeMultiplier, sizeOverride)

    def drawLine(self, line, color, sizeMultiplier = 1.0, sizeOverride = None):
        if not self._drawing:
            self.startStroke()
        self._draw(line, color, QPainter.CompositionMode.CompositionMode_SourceOver, sizeMultiplier, sizeOverride)

    def erasePoint(self, point, color, sizeMultiplier = 1.0, sizeOverride = None):
        if not self._drawing:
            self.startStroke()
        self._draw(point, color, QPainter.CompositionMode.CompositionMode_Clear, sizeMultiplier, sizeOverride)

    def eraseLine(self, line, color, sizeMultiplier = 1.0, sizeOverride = None):
        if not self._drawing:
            self.startStroke()
        self._draw(line, color, QPainter.CompositionMode.CompositionMode_Clear, sizeMultiplier, sizeOverride)

    def fill(self, color):
        super().fill(color)
        if not self.enabled():
            print("not enabled for fill")
            return
        if self._drawing:
            self.endStroke()
        pixmap = QPixmap(self.size())
        pixmap.swap(self.pixmap())
        pixmap.fill(color)
        self.setPixmap(pixmap)
        self._handleChanges()
        self.update()

    def clear(self):
        super().clear()
        if self._drawing:
            self.endStroke()
        self.fill(Qt.transparent)

    def _handleChanges(self):
        self._image = None

