from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPainter, QPixmap
from PyQt5.QtWidgets import QGraphicsPixmapItem
from data_model.canvas.pixmap_canvas import PixmapCanvas

class SketchCanvas(PixmapCanvas):
    def __init__(self, config, initData):
        super().__init__(config, initData)
        self.setBrushSize(self._config.get('initialSketchBrushSize'))
        self.shading = False
        self._shadingPixmap = QGraphicsPixmapItem()
        self._setEmptyShadingPixmap()

    def addToScene(self, scene):
        super().addToScene(scene)
        self._shadingPixmap.setZValue(self.zValue())
        scene.addItem(self._shadingPixmap)

    def setImage(self, initData):
        super().setImage(initData)
        self.hasSketch = initData is not None and not isinstance(initData, QSize)

    def startStroke(self):
        super().startStroke()
        if self._config.get("pressureOpacity"):
            self.shading = True

    def endStroke(self):
        super().endStroke()
        self._applyShading()

    def drawLine(self, line, color, sizeMultiplier=None, sizeOverride=None):
        self.hasSketch = True
        if self.shading:
            pixmap = QPixmap(self.size())
            pixmap.swap(self._shadingPixmap.pixmap())
            self._baseDraw(pixmap, line, color, QPainter.CompositionMode.CompositionMode_Source,
                    sizeMultiplier, sizeOverride)
            self._shadingPixmap.setPixmap(pixmap)
        else:
            super().drawLine(line, color, sizeMultiplier, sizeOverride)

    def drawPoint(self, point, color, sizeMultiplier=None, sizeOverride=None):
        if self.shading:
            pixmap = QPixmap(self.size())
            pixmap.swap(self._shadingPixmap.pixmap())
            self._baseDraw(pixmap, point, color, QPainter.CompositionMode.CompositionMode_Source,
                    sizeMultiplier, sizeOverride)
            self._shadingPixmap.setPixmap(pixmap)
        else:
            super().drawPoint(point, color, sizeMultiplier, sizeOverride)
        self.hasSketch = True


    def startShading(self):
        self.shading = True

    def _setEmptyShadingPixmap(self):
            blankPixmap = QPixmap(self.size())
            blankPixmap.fill(Qt.transparent)
            self._shadingPixmap.setPixmap(blankPixmap)

    def _applyShading(self):
        if self.shading:
            pixmap = QPixmap(self.size())
            pixmap.swap(self.pixmap())
            painter = QPainter(pixmap)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.drawPixmap(0, 0, self.width(), self.height(), self._shadingPixmap.pixmap())
            painter.end()
            self.setPixmap(pixmap)
            self._setEmptyShadingPixmap()
            self.shading = False

    def getImage(self):
        self._applyShading()
        return super().getImage()

    def resize(self, size):
        super().resize(size)
        self._shadingPixmap.setPixmap(self._shadingPixmap.pixmap().scaled(size))

    def clear(self):
        super().clear()
        self._setEmptyShadingPixmap()
        self.hasSketch = False

    def fill(self, color):
        super().fill(color)
        self.hasSketch = True

    def setVisible(self, visible):
        super().setVisible(visible)
        self._shadingPixmap.setVisible(visible)

    def setOpacity(self, opacity):
        super().setOpacity(opacity)
        self._shadingPixmap.setOpacity(opacity)
