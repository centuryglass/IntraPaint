from PyQt5.QtCore import QSize
from PyQt5.QtGui import QPainter
from data_model.base_canvas import BaseCanvas

class TransparencyCanvas(BaseCanvas):
    def __init__(self, config):
        super().__init__(config, None)
        self.setBrushSize(self._config.get('initialSketchBrushSize'))

    def drawPoint(self, point, color, sizeMultiplier = 1.0):
        self._draw(point, color, QPainter.CompositionMode.CompositionMode_Source, sizeMultiplier)

    def drawLine(self, line, color, sizeMultiplier = 1.0):
        self._draw(line, color, QPainter.CompositionMode.CompositionMode_Source, sizeMultiplier)
