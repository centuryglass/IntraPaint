from ui.image_utils import qImageToImage
from data_model.base_canvas import BaseCanvas
from PyQt5.QtCore import Qt, QRect, QPoint, QSize
from PyQt5.QtGui import QPixmap, QPainter, QImage, QColor
import numpy as np
import cv2

class MaskCanvas(BaseCanvas):
    def __init__(self, config, image):
        super().__init__(config, image)
        self.setBrushSize(self._config.get('initialMaskBrushSize'))
        self._maskRect = None
        self._outline = None
        config.connect(self, 'inpaintFullRes', lambda b: self._handleChanges())
        config.connect(self, 'inpaintFullResPadding', lambda x: self._handleChanges())
        self.ditherMask = QPixmap(QSize(512, 512))
        ditherStamp = QPixmap(QSize(8, 8))
        painter = QPainter(ditherStamp)
        painter.fillRect(0, 0, 8, 8, Qt.white)
        painter.fillRect(0, 0, 4, 4, Qt.black)
        painter.fillRect(4, 4, 4, 4, Qt.black)
        painter = QPainter(self.ditherMask)
        painter.drawTiledPixmap(0, 0, 512, 512, ditherStamp)
        self.profiler = cProfile.Profile()

    def getInpaintingMask(self):
        image = self.getImage()
        image = image.convert('L').point( lambda p: 255 if p < 1 else 0 )
        return image

    def getOutline(self):
        if self._outline is not None:
            return self._outline
        image = self.getQImage()
        thickness = max(2, image.width() // 200, image.height() // 200)
        thickness = min(thickness, 5)
        buffer = image.bits().asstring(image.byteCount())
        arr = np.frombuffer(buffer, dtype=np.uint8).reshape((image.height(), image.width(), 4))
        gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
        edges= cv2.Canny(gray, 50, 150)
        edges = 255 - cv2.dilate(edges, np.ones((thickness, thickness), np.uint8), iterations=1)
        edges_A = np.zeros((edges.shape[0], edges.shape[1], 4), dtype=np.uint8)
        edges_A[:, :, 3] = 255 - edges
        outline = QImage(edges_A.data, edges_A.shape[1], edges_A.shape[0], edges_A.strides[0], QImage.Format_RGBA8888)
        painter = QPainter(outline)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.drawPixmap(0, 0, self.ditherMask)
        painter.end()
        self._outline = QPixmap.fromImage(outline)
        return self._outline


    def getMaskedArea(self, ignoreConfig = False):
        if (not ignoreConfig) and (not self._config.get('inpaintFullRes')):
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
        width = self.ditherMask.width()
        height = self.ditherMask.height()
        while width < self.width():
            width += self.width()
        while height < self.height():
            height += self.height()
        if width != self.ditherMask.width() or height != self.ditherMask.height():
            newDitherMask = QPixmap(QSize(width, height))
            painter = QPainter(newDitherMask)
            painter.drawTiledPixmap(0, 0, width, height, self.ditherMask)
            self.ditherMask = newDitherMask
        self._maskRect = None
        self._outline = None
        super()._handleChanges()

