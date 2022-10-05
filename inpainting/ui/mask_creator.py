from PyQt5 import QtWidgets
from PyQt5.QtGui import QPainter, QPen, QImage
from PyQt5.QtCore import Qt, QPoint, QLine, QSize, QRect, QBuffer
import PyQt5.QtGui as QtGui
from PIL import Image
from inpainting.ui.layout_utils import getScaledPlacement, QEqualMargins
from inpainting.image_utils import imageToQImage, qImageToImage

class MaskCreator(QtWidgets.QWidget):
    """
    QWidget that shows the selected portion of the edited image, and lets the user draw a mask for inpainting.
    """

    def __init__(self, maskCanvas, sketchCanvas, editedImage):
        super().__init__()
        self._maskCanvas = maskCanvas
        self._sketchCanvas = sketchCanvas
        self._imageSection = None
        self._drawing = False
        self._lastPoint = QPoint()
        self._useEraser=False
        self._sketchMode=False
        self._sketchColor = Qt.black

        maskCanvas.redrawRequired.connect(lambda: self.update())
        sketchCanvas.redrawRequired.connect(lambda: self.update())
        def updateImage():
            if editedImage.hasImage():
                image = editedImage.getSelectionContent()
                self.loadImage(image)
            else:
                self._imageSection = None
                self.resizeEvent(None)
                self.update()
        editedImage.selectionChanged.connect(updateImage)
        updateImage()

    def setSketchMode(self, sketchMode):
        self._sketchMode = sketchMode

    def getSketchColor(self):
        return self._sketchColor

    def setSketchColor(self, sketchColor):
        self._sketchColor = sketchColor

    def setUseEraser(self, useEraser):
        self._useEraser = useEraser

    def clear(self):
        if self._sketchMode:
            if self._sketchCanvas.enabled():
                self._sketchCanvas.clear()
        else:
            if self._maskCanvas.enabled():
                self._maskCanvas.clear()
    
    def fill(self):
        canvas = self._sketchCanvas if self._sketchMode else self._maskCanvas
        color = self._sketchColor if self._sketchMode else Qt.red
        if canvas.enabled():
            canvas.fill(color)

    def loadImage(self, pilImage):
        selectionSize = self._maskCanvas.size()
        self._imageRect = getScaledPlacement(QRect(QPoint(0, 0), self.size()), selectionSize,
                self._borderSize())
        self._imageSection = imageToQImage(pilImage)
        self.resizeEvent(None)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QPen(Qt.black, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawRect(self._imageRect.marginsAdded(QEqualMargins(self._borderSize())))
        if hasattr(self, '_imageSection') and self._imageSection is not None:
            painter.drawImage(self._imageRect, self._imageSection)
        if self._sketchCanvas.hasSketch and self._sketchCanvas.enabled():
            painter.drawPixmap(self._imageRect, self._sketchCanvas.getPixmap())
        if self._maskCanvas.enabled():
            painter.setOpacity(0.6)
            painter.drawPixmap(self._imageRect, self._maskCanvas.getPixmap())

    def _widgetToImageCoords(self, point):
        assert isinstance(point, QPoint)
        scale = self._imageRect.width() / self._maskCanvas.size().width()
        return QPoint(int((point.x() - self._imageRect.x()) / scale),
                int((point.y() - self._imageRect.y()) / scale))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drawing = True
            self._lastPoint = self._widgetToImageCoords(event.pos())

    def mouseMoveEvent(self, event):
        if event.buttons() and Qt.LeftButton and self._drawing:
            canvas = self._sketchCanvas if self._sketchMode else self._maskCanvas
            color = self._sketchColor if self._sketchMode else Qt.red
            newLastPoint = self._widgetToImageCoords(event.pos())
            line = QLine(self._lastPoint, newLastPoint)
            self._lastPoint = newLastPoint
            if self._useEraser:
                canvas.eraseLine(line, color)
            else:
                canvas.drawLine(line, color)

    def mouseReleaseEvent(self, event):
        if event.button == Qt.LeftButton and self._drawing:
            self._drawing = False

    def resizeEvent(self, event):
        if self._maskCanvas.size() == QSize(0, 0):
            self._imageRect = QRect(0, 0, self.width(), self.height())
        else:
            self._imageRect = getScaledPlacement(QRect(QPoint(0, 0), self.size()), self._maskCanvas.size(),
                    self._borderSize())

    def _borderSize(self):
        return (min(self.width(), self.height()) // 40) + 1
