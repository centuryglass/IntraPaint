from PyQt5.QtGui import QPainter, QPixmap, QPen, QImage
import PyQt5.QtGui as QtGui
from PyQt5.QtCore import Qt, QObject, QRect, QPoint, QLine, QSize, pyqtSignal
from PIL import Image

from inpainting.image_utils import imageToQImage, qImageToImage 

class BaseCanvas(QObject):
    redrawRequired = pyqtSignal()
    onEnabledChange = pyqtSignal(bool)

    def __init__(self, config, image):
        super().__init__()
        self._config = config
        self._brushSize = 1
        if image is not None:
            self.setImage(image)
        else:
            self.setImage(config.get('maxEditSize'))
        self._enabled = True

    def enabled(self):
        return self._enabled

    def setEnabled(self, isEnabled):
        if isEnabled != self._enabled:
            self._enabled = isEnabled
            self.onEnabledChange.emit(isEnabled)
        
    def brushSize(self):
        return self._brushSize

    def setBrushSize(self, newSize):
        self._brushSize = newSize

    def setImage(self, initData):
        if isinstance(initData, QSize): # Blank initial image:
            self._pixmap = QPixmap(initData)
            self._pixmap.fill(Qt.transparent)
        elif isinstance(initData, str): # Load from image path:
            self._pixmap = QPixmap(initData, "RGB")
        elif isinstance(initData, Image.Image):
            self._pixmap = QPixmap.fromImage(imageToQImage(initData))
        elif isinstance(initData, QImage):
            self._pixmap = QPixmap.fromImage(initData)
        else:
            raise Exception(f"Invalid image param {initData}")
        self.redrawRequired.emit()

    def size(self):
        return self._pixmap.size()
    
    def getPixmap(self):
        return self._pixmap

    def getImage(self):
        return qImageToImage(self._pixmap.toImage())

    def resize(self, size):
        if not isinstance(size, QSize):
            raise Exception(f"Invalid resize param {size}")
        if size != self._pixmap.size():
            self._pixmap = self._pixmap.scaled(size)
            self.redrawRequired.emit()

    def _draw(self, pos, color, compositionMode):
        if not self.enabled():
            return
        painter = QPainter(self._pixmap)
        painter.setCompositionMode(compositionMode)
        painter.setPen(QPen(color, self._brushSize, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        if isinstance(pos, QLine):
            painter.drawLine(pos)
        else: # Should be QPoint
            painter.drawPoint(pos)
        self.redrawRequired.emit()

    def drawPoint(self, point, color):
        self._draw(point, color, QPainter.CompositionMode.CompositionMode_SourceOver)

    def drawLine(self, line, color):
        self._draw(line, color, QPainter.CompositionMode.CompositionMode_SourceOver)

    def eraseLine(self, line, color):
        self._draw(line, color, QPainter.CompositionMode.CompositionMode_Clear)

    def fill(self, color):
        if not self.enabled():
            return
        self._pixmap.fill(color)
        self.redrawRequired.emit()

    def clear(self):
        self.fill(Qt.transparent)

