from PyQt5.QtCore import QSize
from PyQt5.QtGui import QPainter
from data_model.base_canvas import BaseCanvas
from data_model.transparency_canvas import TransparencyCanvas

class SketchCanvas(BaseCanvas):
    def __init__(self, config, initData):
        super().__init__(config, initData)
        self._transparencyCanvas = TransparencyCanvas(config)
        self.setBrushSize(self._config.get('initialSketchBrushSize'))
        self.shading = False
        self._transparencyCanvas.redrawRequired.connect(lambda: self.redrawRequired.emit())

    def setBrushSize(self, newSize):
        super().setBrushSize(newSize)
        self._transparencyCanvas.setBrushSize(newSize)

    def setImage(self, initData):
        super().setImage(initData)
        self.hasSketch = initData is not None and not isinstance(initData, QSize)

    def drawLine(self, line, color, sizeMultiplier=None, sizeOverride=None):
        if self.shading:
            self._transparencyCanvas.drawLine(line, color, sizeMultiplier, sizeOverride)
        else:
            super().drawLine(line, color, sizeMultiplier, sizeOverride)
        self.hasSketch = True

    def drawPoint(self, point, color, sizeMultiplier=None, sizeOverride=None):
        if self.shading:
            self._transparencyCanvas.drawPoint(point, color, sizeMultiplier, sizeOverride)
        else:
            super().drawPoint(point, color, sizeMultiplier, sizeOverride)
        self.hasSketch = True

    def startShading(self):
        self.shading = True

    def applyShading(self):
        if self.shading:
            painter = QPainter(self.getPixmap())
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.drawPixmap(0, 0, self.width(), self.height(), self._transparencyCanvas.getPixmap())
            self._transparencyCanvas.clear()
            self.shading = False

    def resize(self, size):
        super().resize(size)
        self._transparencyCanvas.resize(size)


    def clear(self):
        super().clear()
        self._transparencyCanvas.clear()
        self.hasSketch = False

    def fill(self, color):
        super().fill(color)
        self.hasSketch = True

