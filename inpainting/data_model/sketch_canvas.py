from PyQt5.QtCore import QSize
from inpainting.data_model.base_canvas import BaseCanvas

class SketchCanvas(BaseCanvas):
    def __init__(self, config, initData):
        super().__init__(config, initData)
        self.setBrushSize(self._config.get('initialSketchBrushSize'))

    def setImage(self, initData):
        super().setImage(initData)
        self.hasSketch = initData is not None and not isinstance(initData, QSize)

    def drawLine(self, line, color):
        super().drawLine(line, color)
        self.hasSketch = True

    def clear(self):
        if self.hasSketch:
            super().clear()
            self.hasSketch = False

    def fill(self, color):
        super().fill(color)
        self.hasSketch = True

