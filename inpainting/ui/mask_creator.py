from PyQt5 import QtWidgets
from PyQt5.QtGui import QPainter, QPen, QImage, QColor, QTabletEvent
from PyQt5.QtCore import Qt, QPoint, QLine, QSize, QRect, QBuffer, QEvent
import PyQt5.QtGui as QtGui
from PIL import Image

from inpainting.ui.util.get_scaled_placement import getScaledPlacement
from inpainting.ui.util.equal_margins import getEqualMargins
from inpainting.image_utils import imageToQImage, qImageToImage

class MaskCreator(QtWidgets.QWidget):
    """
    QWidget that shows the selected portion of the edited image, and lets the user draw a mask for inpainting.
    """

    def __init__(self, parent, maskCanvas, sketchCanvas, editedImage, eyedropperCallback=None):
        super().__init__(parent)
        self._maskCanvas = maskCanvas
        self._sketchCanvas = sketchCanvas
        self._imageSection = None
        self._drawing = False
        self._lastPoint = QPoint()
        self._useEraser=False
        self._sketchMode=False
        self._eyedropperMode=False
        self._lineMode=False
        self._eyedropperCallback=eyedropperCallback
        self._sketchColor = QColor(0, 0, 0)
        self._pen_pressure = 1.0
        self._pressureSize = False
        self._pressureOpacity = False
        self._tabletEraser = False

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

    def setPressureSizeMode(self, usePressureSize):
        self._pressureSize = usePressureSize

    def setPressureOpacityMode(self, usePressureOpacity):
        self._pressureOpacity = usePressureOpacity

    def _getSketchOpacity(self):
        return 1.0 if not self._pressureOpacity else (max(0.0, self._pen_pressure - 0.5) * 2)

    def setSketchMode(self, sketchMode):
        self._sketchMode = sketchMode

    def setEyedropperMode(self, eyedropperMode):
        self._eyedropperMode = eyedropperMode

    def setLineMode(self, lineMode):
        self._lineMode = lineMode
        if lineMode:
            self._drawing = False

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
        #painter.drawRect(QRect(0, 0, self.width(), self.height()))
        painter.drawRect(self._imageRect.marginsAdded(getEqualMargins(self._borderSize())))
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

    def getColorAtPoint(self, point):
        sketchColor = QColor(0, 0, 0, 0)
        imageColor = QColor(0, 0, 0, 0)
        if self._sketchCanvas.hasSketch:
            sketchColor = self._sketchCanvas.getColorAtPoint(point)
        if self._imageSection is not None:
            imageColor = self._imageSection.pixelColor(point)
        def getComponent(sketchComp, imageComp):
            return int((sketchComp * sketchColor.alphaF()) + (imageComp * imageColor.alphaF() * (1.0 - sketchColor.alphaF())))
        red = getComponent(sketchColor.red(), imageColor.red())
        green = getComponent(sketchColor.green(), imageColor.green())
        blue = getComponent(sketchColor.blue(), imageColor.blue())
        combined = QColor(red, green, blue)
        return combined

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._eyedropperMode:
                point = self._widgetToImageCoords(event.pos())
                color = self.getColorAtPoint(point)
                if color is not None:
                    self._eyedropperCallback(color)
            else:
                canvas = self._sketchCanvas if self._sketchMode else self._maskCanvas
                color = self._sketchColor if self._sketchMode else Qt.red
                if self._sketchMode and self._pressureOpacity:
                    color.setAlphaF(self._getSketchOpacity())
                sizeMultiplier = self._pen_pressure if self._pressureSize else 1.0
                if self._lineMode:
                    newPoint = self._widgetToImageCoords(event.pos())
                    line = QLine(self._lastPoint, newPoint)
                    self._lastPoint = newPoint
                    # Prevent issues with lines not drawing by setting a minimum multiplier for lineMode only:
                    sizeMultiplier = max(sizeMultiplier, 0.5)
                    if self._useEraser:
                        canvas.eraseLine(line, color, sizeMultiplier)
                    else:
                        canvas.drawLine(line, color, sizeMultiplier)
                else:
                    self._drawing = True
                    self._lastPoint = self._widgetToImageCoords(event.pos())
                    if self._useEraser or self._tabletEraser:
                        canvas.erasePoint(self._lastPoint, color, sizeMultiplier)
                    else:
                        canvas.drawPoint(self._lastPoint, color, sizeMultiplier)

    def mouseMoveEvent(self, event):
        if event.buttons() and Qt.LeftButton and self._drawing and not self._eyedropperMode:
            canvas = self._sketchCanvas if self._sketchMode else self._maskCanvas
            color = self._sketchColor if self._sketchMode else Qt.red
            if self._sketchMode and self._pressureOpacity:
                color.setAlphaF(self._getSketchOpacity())
            sizeMultiplier = self._pen_pressure if self._pressureSize else 1.0
            newLastPoint = self._widgetToImageCoords(event.pos())
            line = QLine(self._lastPoint, newLastPoint)
            self._lastPoint = newLastPoint
            if self._useEraser or self._tabletEraser:
                canvas.eraseLine(line, color, sizeMultiplier)
            else:
                canvas.drawLine(line, color, sizeMultiplier)

    def tabletEvent(self, tabletEvent):
        if tabletEvent.type() == QEvent.TabletRelease:
            self._pen_pressure = 1.0
            self._tabletEraser = False
        elif tabletEvent.type() == QEvent.TabletPress:
            self._tabletEraser = (tabletEvent.pointerType() == QTabletEvent.PointerType.Eraser)
            self._pen_pressure = tabletEvent.pressure()
        else:
            self._pen_pressure = tabletEvent.pressure()

    def mouseReleaseEvent(self, event):
        if event.button == Qt.LeftButton and self._drawing:
            self._drawing = False

    def resizeEvent(self, event):
        if self._maskCanvas.size() == QSize(0, 0):
            self._imageRect = QRect(0, 0, self.width(), self.height())
        else:
            self._imageRect = getScaledPlacement(QRect(QPoint(0, 0), self.size()), self._maskCanvas.size(),
                    self._borderSize())

    def getImageDisplaySize(self):
        return QSize(self._imageRect.width(), self._imageRect.height())

    def _borderSize(self):
        return (min(self.width(), self.height()) // 40) + 1
