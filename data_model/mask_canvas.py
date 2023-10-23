from ui.image_utils import qImageToImage
from data_model.base_canvas import BaseCanvas
from PyQt5.QtCore import QRect, QPoint

class MaskCanvas(BaseCanvas):
    def __init__(self, config, image):
        super().__init__(config, image)
        self.setBrushSize(self._config.get('initialMaskBrushSize'))
        self._maskRect = None
        config.connect(self, 'inpaintFullRes', lambda b: self._handleChanges())
        config.connect(self, 'inpaintFullResPadding', lambda x: self._handleChanges())

    def getInpaintingMask(self):
        image = self.getImage()
        image = image.convert('L').point( lambda p: 255 if p < 1 else 0 )
        return image

    def getMaskedArea(self):
        if not self._config.get('inpaintFullRes'):
            return
        if self._maskRect is not None:
            return self._maskRect
        radius = self._config.get('inpaintFullResPadding')
        image = self.getQImage()
        top = image.height() - 1
        bottom = 0
        left = image.width() - 1
        right = 0
        for y in range(0, image.height()):
            row = image.constScanLine(y).asarray(image.bytesPerLine())
            for x in range(3, image.bytesPerLine(), 4):
                if row[x] > 0:
                    top = min(y, top)
                    bottom = max(y, bottom)
                    left = min(x//4, left)
                    right = max(x//4, right)
        if top > bottom:
            return # mask was empty
        top = max(0, top - radius)
        bottom = min(image.height() - 1, bottom + radius)
        left = max(0, left - radius)
        right = min(image.width() - 1, right + radius)
        height = bottom - top
        width = right - left
        if width > height:
            difference = width - height
            dTop = min(top, difference // 2)
            dBottom = min((image.height() - 1) - bottom, difference - dTop)
            top -= dTop
            bottom += dBottom
        elif height > width:
            difference = height - width
            dLeft = min(left, difference // 2)
            dRight = min((image.width() - 1) - right, difference - dLeft)
            left -= dLeft
            right += dRight
        self._maskRect = QRect(QPoint(left, top), QPoint(right, bottom))
        return self._maskRect

    def _handleChanges(self):
        self._maskRect = None
        super()._handleChanges()

