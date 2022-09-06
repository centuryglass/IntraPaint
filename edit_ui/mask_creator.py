from PyQt5 import QtWidgets
from PyQt5.QtGui import QPainter, QPen, QImage
from PyQt5.QtCore import Qt, QPoint, QSize, QRect, QBuffer
import PyQt5.QtGui as QtGui
from PIL import Image
from edit_ui.ui_utils import getScaledPlacement, imageToQImage, qImageToImage, QEqualMargins

class MaskCreator(QtWidgets.QWidget):
    """
    QWidget that shows the selected portion of the edited image, and lets the user draw a mask for inpainting.
    """

    def __init__(self, pilImage):
        """
        Parameters:
        pilImage : Image, optional
            Initial image area selected for editing.
        """
        super().__init__()
        assert pilImage is None or isinstance(pilImage, Image.Image)
        
        self._drawing = False
        self._lastPoint = QPoint()
        self._brushSize = 40
        self._selectionSize = QSize(0, 0)
        self._useEraser=False
        self._maskCanvas = None
        self._sketchCanvas = None
        self._sketchMode=False
        self._sketchColor = Qt.black
        self._hasSketch=False
        if pilImage is not None:
            self.loadImage(pilImage)

    def selectionWidth(self):
        return self._selectionSize.width()

    def selectionHeight(self):
        return self._selectionSize.height()

    def setSelectionSize(self, size):
        """Set the dimensions(in pixels) of the edited image area."""
        if size != self._selectionSize:
            self._selectionSize = size
            self.resizeEvent(None)

    def setSketchMode(self, sketchMode):
        self._sketchMode = sketchMode

    def getSketchColor(self):
        return self._sketchColor

    def setSketchColor(self, sketchColor):
        self._sketchColor = sketchColor

    def setBrushSize(self, newSize):
        self._brushSize = newSize

    def setUseEraser(self, useEraser):
        self._useEraser = useEraser

    def getBrushSize(self):
        return self._brushSize

    def clear(self):
        if self._sketchMode:
            if self._sketchCanvas is not None:
                self._sketchCanvas.fill(Qt.transparent)
                self._hasSketch = False
        elif self._maskCanvas is not None:
            self._maskCanvas.fill(Qt.transparent)
        self.update()

    def loadMaskImage(self, imagePath):
        maskQImage = QImage(imagePath)
        self._maskCanvas = QtGui.QPixmap.fromImage(maskQImage)
        self.resizeEvent(None)
        self.update()

    def loadImage(self, pilImage):
        # Use a canvas that's large enough to look decent even editing scale changes,
        # it'll just get resized to selection size on inpainting anyway.
        canvasSize = QSize(512, 512)
        if self._maskCanvas is None:
            canvas_image = QImage(canvasSize, QtGui.QImage.Format_ARGB32)
            self._maskCanvas = QtGui.QPixmap.fromImage(canvas_image)
            self._maskCanvas.fill(Qt.transparent)
        if self._sketchCanvas is None:
            canvas_image = QImage(canvasSize, QtGui.QImage.Format_ARGB32)
            self._sketchCanvas = QtGui.QPixmap.fromImage(canvas_image)
            self._sketchCanvas.fill(Qt.transparent)
        if self._selectionSize != QSize(pilImage.width, pilImage.height):
            self._selectionSize = QSize(pilImage.width, pilImage.height)
    

        self._imageRect = getScaledPlacement(QRect(QPoint(0, 0), self.size()), self._selectionSize,
                self._borderSize())
        self._qimage = imageToQImage(pilImage)
        self._pixmap = QtGui.QPixmap.fromImage(self._qimage).scaled(self._imageRect.size())
        self.resizeEvent(None)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QPen(Qt.black, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawRect(self._imageRect.marginsAdded(QEqualMargins(self._borderSize())))
        if hasattr(self, '_pixmap') and self._pixmap is not None:
            painter.drawPixmap(self._imageRect, self._pixmap)
        if self._sketchCanvas is not None and self._hasSketch:
            painter.drawPixmap(self._imageRect, self._sketchCanvas)
        if hasattr(self, '_maskCanvas') and self._maskCanvas is not None:
            painter.setOpacity(0.6)
            painter.drawPixmap(self._imageRect, self._maskCanvas)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and (self._sketchMode and self._sketchCanvas is not None) \
                or (not self._sketchMode and self._maskCanvas is not None):
            self._drawing = True
            self._lastPoint = event.pos() - self._imageRect.topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() and Qt.LeftButton and self._drawing \
                and (self._sketchMode and self._sketchCanvas is not None) \
                or (not self._sketchMode and self._maskCanvas is not None):
            painter = QPainter(self._sketchCanvas) if self._sketchMode else QPainter(self._maskCanvas)
            color = self._sketchColor if self._sketchMode else Qt.red
            if self._useEraser:
                painter.setCompositionMode(QPainter.CompositionMode_Clear)
            scaledBrushSize = self._imageRect.width() / self._selectionSize.width() * self._brushSize
            painter.setPen(QPen(color, scaledBrushSize, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawLine(self._lastPoint, event.pos() - self._imageRect.topLeft())
            self._lastPoint = event.pos() - self._imageRect.topLeft()
            if self._sketchMode:
                self._hasSketch = True
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button == Qt.LeftButton and self._drawing:
            self._drawing = False

    def getMask(self):
        if self._maskCanvas is None:
            return None
        canvasImage = self._maskCanvas.toImage().scaled(self._selectionSize)
        return qImageToImage(canvasImage)

    def getSketch(self):
        if self._sketchCanvas is None or not self._hasSketch:
            return None
        canvasImage = self._sketchCanvas.toImage().scaled(self._selectionSize)
        return qImageToImage(canvasImage)

    def resizeEvent(self, event):
        if self._selectionSize == QSize(0, 0):
            self._imageRect = QRect(0, 0, self.width(), self.height())
        else:
            self._imageRect = getScaledPlacement(QRect(QPoint(0, 0), self.size()), self._selectionSize,
                    self._borderSize())
        if self._maskCanvas:
            self._maskCanvas = self._maskCanvas.scaled(self._imageRect.size())
        if self._sketchCanvas:
            self._sketchCanvas = self._sketchCanvas.scaled(self._imageRect.size())

    def _borderSize(self):
        return (min(self.width(), self.height()) // 40) + 1
