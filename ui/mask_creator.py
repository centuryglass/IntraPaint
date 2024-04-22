from PyQt5.QtGui import QPainter, QPen, QImage, QPixmap, QColor, QTabletEvent, QTransform
from PyQt5.QtCore import Qt, QPoint, QLine, QSize, QRect, QRectF, QBuffer, QEvent, QMarginsF
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem
import PyQt5.QtGui as QtGui
from PIL import Image

from ui.util.get_scaled_placement import getScaledPlacement
from ui.util.equal_margins import getEqualMargins
from ui.util.contrast_color import contrastColor
from ui.image_utils import imageToQImage, qImageToImage

class MaskCreator(QGraphicsView):
    """
    QWidget that shows the selected portion of the edited image, and lets the user draw a mask for inpainting.
    """

    def __init__(self, parent, maskCanvas, sketchCanvas, editedImage, eyedropperCallback=None):
        super().__init__(parent)
        self._maskCanvas = maskCanvas
        self._sketchCanvas = sketchCanvas
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
        selectionSize = self._maskCanvas.size()
        self._imageRect = getScaledPlacement(QRect(QPoint(0, 0), self.size()), selectionSize,
                self._borderSize())

        # Setup scene with layers:
        self.setAlignment(Qt.AlignCenter)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setCacheMode(QGraphicsView.CacheBackground)
        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self._scene = QGraphicsScene()
        self.setScene(self._scene)

        selectionSize = self._maskCanvas.size()
        selectionRectF = QRectF(0.0, 0.0, float(selectionSize.width()), float(selectionSize.height()))
        margins = QMarginsF(5, 5, 5, 5)
        borderRect = selectionRectF.marginsAdded(margins)
        self._borderRect = QGraphicsRectItem()
        self._borderRect.setRect(borderRect)
        self._borderRect.setPen(QPen(contrastColor(self), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self._scene.setSceneRect(selectionRectF)
        self._scene.addItem(self._borderRect)

        self._imagePixmap = QGraphicsPixmapItem()
        self._setEmptyImageSection()
        self._scene.addItem(self._imagePixmap)
        sketchCanvas.addToScene(self._scene)
        maskCanvas.addToScene(self._scene)
        self.resizeEvent(None)

        def updateImage():
            if editedImage.hasImage():
                image = editedImage.getSelectionContent()
                self.loadImage(image)
            else:
                self._setEmptyImageSection()
                self.resizeEvent(None)
                self.update()
        editedImage.selectionChanged.connect(updateImage)
        updateImage()

    def _setEmptyImageSection(self):
        blank = QPixmap(self._maskCanvas.size())
        blank.fill(Qt.transparent)
        self._imageSection = blank.toImage()
        self._imagePixmap.setPixmap(blank)

    def setPressureSizeMode(self, usePressureSize):
        self._pressureSize = usePressureSize

    def setPressureOpacityMode(self, usePressureOpacity):
        self._pressureOpacity = usePressureOpacity

    def _getSketchOpacity(self):
        return 1.0 if not self._pressureOpacity else min(1, self._pen_pressure * 1.25)

    def setSketchMode(self, sketchMode):
        self._sketchMode = sketchMode
        self._maskCanvas.setOpacity(0.4 if sketchMode else 0.6)

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
        selectionRectF = QRectF(0.0, 0.0, float(selectionSize.width()), float(selectionSize.height()))
        margins = QMarginsF(5, 5, 5, 5)
        borderRect = selectionRectF.marginsAdded(margins)
        self._borderRect.setRect(borderRect)
        self._scene.setSceneRect(selectionRectF)
        self._imageSection = imageToQImage(pilImage)
        self._imagePixmap.setPixmap(QPixmap.fromImage(self._imageSection))
        self.resizeEvent(None)
        self.update()

    def _widgetToImageCoords(self, point):
        assert isinstance(point, QPoint)
        scale = max(self.getImageDisplaySize().width(), 1) / max(self._maskCanvas.size().width(), 1)
        return QPoint(int((point.x() - self._imageRect.x()) / scale),
                 int((point.y() - self._imageRect.y()) / scale))


    def getColorAtPoint(self, point):
        sketchColor = QColor(0, 0, 0, 0)
        imageColor = QColor(0, 0, 0, 0)
        if self._sketchCanvas.hasSketch:
            sketchColor = self._sketchCanvas.getColorAtPoint(point)
        imageColor = self._imageSection.pixelColor(point)
        def getComponent(sketchComp, imageComp):
            return int((sketchComp * sketchColor.alphaF()) + (imageComp * imageColor.alphaF() * (1.0 - sketchColor.alphaF())))
        red = getComponent(sketchColor.red(), imageColor.red())
        green = getComponent(sketchColor.green(), imageColor.green())
        blue = getComponent(sketchColor.blue(), imageColor.blue())
        combined = QColor(red, green, blue)
        return combined

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton or event.button() == Qt.RightButton:
            sizeOverride = 1 if event.button() == Qt.RightButton else None
            if self._eyedropperMode:
                point = self._widgetToImageCoords(event.pos())
                color = self.getColorAtPoint(point)
                if color is not None:
                    self._eyedropperCallback(color)
            else:
                canvas = self._sketchCanvas if self._sketchMode else self._maskCanvas
                color = QColor(self._sketchColor if self._sketchMode else Qt.red)
                if self._sketchMode and self._pressureOpacity:
                    color.setAlphaF(self._getSketchOpacity())
                sizeMultiplier = self._pen_pressure if self._pressureSize else 1.0
                if self._lineMode:
                    canvas.startStroke()
                    newPoint = self._widgetToImageCoords(event.pos())
                    line = QLine(self._lastPoint, newPoint)
                    self._lastPoint = newPoint
                    # Prevent issues with lines not drawing by setting a minimum multiplier for lineMode only:
                    sizeMultiplier = max(sizeMultiplier, 0.5)
                    if self._useEraser:
                        canvas.eraseLine(line, color, sizeMultiplier, sizeOverride)
                    else:
                        canvas.drawLine(line, color, sizeMultiplier, sizeOverride)
                    canvas.endStroke()
                else:
                    canvas.startStroke()
                    self._drawing = True
                    self._maskCanvas.setOpacity(0.8 if canvas == self._maskCanvas else 0.2)

                    self._lastPoint = self._widgetToImageCoords(event.pos())
                    if self._useEraser or self._tabletEraser:
                        canvas.erasePoint(self._lastPoint, color, sizeMultiplier, sizeOverride)
                    else:
                        canvas.drawPoint(self._lastPoint, color, sizeMultiplier, sizeOverride)

    def mouseMoveEvent(self, event):
        if (Qt.LeftButton == event.buttons() or Qt.RightButton == event.buttons()) and self._drawing and not self._eyedropperMode:
            sizeOverride = 1 if Qt.RightButton == event.buttons() else None
            canvas = self._sketchCanvas if self._sketchMode else self._maskCanvas
            color = QColor(self._sketchColor if self._sketchMode else Qt.red)
            if self._sketchMode and self._pressureOpacity:
                color.setAlphaF(self._getSketchOpacity())
            sizeMultiplier = self._pen_pressure if self._pressureSize else 1.0
            newLastPoint = self._widgetToImageCoords(event.pos())
            line = QLine(self._lastPoint, newLastPoint)
            self._lastPoint = newLastPoint
            if self._useEraser or self._tabletEraser:
                canvas.eraseLine(line, color, sizeMultiplier, sizeOverride)
            else:
                canvas.drawLine(line, color, sizeMultiplier, sizeOverride)

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
        if (event.button() == Qt.LeftButton or event.button() == Qt.RightButton) and self._drawing:
            self._drawing = False
            self._pen_pressure = 1.0
            self._tabletEraser = False
            canvas = self._sketchCanvas if self._sketchMode else self._maskCanvas
            canvas.endStroke()
            self._maskCanvas.setOpacity(0.6 if canvas == self._maskCanvas else 0.4)
        self.update()

    def resizeEvent(self, event):
        borderSize = self._borderSize()
        self._imageRect = getScaledPlacement(QRect(QPoint(0, 0), self.size()), self._imagePixmap.pixmap().size(),
                borderSize)
        scale = self._imageRect.width() / self._maskCanvas.width()
        transformation = QTransform()
        transformation.scale(scale, scale)
        transformation.translate(float(self._imageRect.x()), float(self._imageRect.y()))
        self.setTransform(transformation)

    def getImageDisplaySize(self):
        return QSize(self._imageRect.width(), self._imageRect.height())

    def _borderSize(self):
        return (min(self.width(), self.height()) // 40) + 1
