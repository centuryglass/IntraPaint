from ui.image_utils import qImageToImage
from data_model.canvas.pixmap_canvas import PixmapCanvas
from PyQt5.QtCore import Qt, QRect, QPoint, QSize
from PyQt5.QtGui import QPixmap, QPainter, QImage, QColor, QPen
from PyQt5.QtWidgets import QGraphicsPixmapItem
from ui.util.contrast_color import contrastColor
import numpy as np
import cv2

class MaskCanvas(PixmapCanvas):
    def __init__(self, config, image):
        super().__init__(config, image)
        config.connect(self, 'maskBrushSize', lambda size: self.setBrushSize(size))
        self.setBrushSize(config.get('maskBrushSize'))
        self._outline = None
        self._drawing = False
        self._bounding_box = None
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

        self._outline = QGraphicsPixmapItem()
        self._setEmptyOutline()
        self.setOpacity(0.5)

    def addToScene(self, scene):
        super().addToScene(scene)
        self._outline.setZValue(self.zValue())
        scene.addItem(self._outline)
    
    def _setEmptyOutline(self):
            blankPixmap = QPixmap(self.size())
            blankPixmap.fill(Qt.transparent)
            self._outline.setPixmap(blankPixmap)
            self._bounding_box = None

    def getInpaintingMask(self):
        image = self.getImage()
        image = image.convert('L').point( lambda p: 255 if p < 1 else 0 )
        return image

    def startStroke(self):
        super().startStroke()
        self._setEmptyOutline()

    def endStroke(self):
        super().endStroke()
        self._drawOutline()

    def setImage(self, image):
        super().setImage(image)
        self._drawOutline()
        self.update()

    def _drawOutline(self):
        if not hasattr(self, '_drawing') or self._drawing:
            return
        image = self.getQImage()

        # find edges:
        buffer = image.bits().asstring(image.byteCount())
        arr = np.frombuffer(buffer, dtype=np.uint8).reshape((image.height(), image.width(), 4))
        gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
        edges= cv2.Canny(gray, 50, 150)

        # find bounds:
        nonzero_rows = np.any(arr[:, :, 3] > 0, axis=1)
        nonzero_cols = np.any(arr[:, :, 3] > 0, axis=0)
        top = np.argmax(nonzero_rows)
        bottom = image.height() - 1 - np.argmax(np.flip(nonzero_rows))
        left = np.argmax(nonzero_cols)
        right = image.width() - 1 - np.argmax(np.flip(nonzero_cols))
        if left > right:
            self._bounding_box = None
        else:
            self._bounding_box = QRect(left, top, right - left, bottom - top)

        # expand edges to draw a thicker outline:
        thickness = max(2, image.width() // 200, image.height() // 200)
        thickness = min(thickness, 4)
        edges = 255 - cv2.dilate(edges, np.ones((thickness, thickness), np.uint8), iterations=1)
        edges_A = np.zeros((edges.shape[0], edges.shape[1], 4), dtype=np.uint8)
        edges_A[:, :, 3] = 255 - edges
        outline = QImage(edges_A.data, edges_A.shape[1], edges_A.shape[0], edges_A.strides[0], QImage.Format_RGBA8888)
        painter = QPainter(outline)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.drawPixmap(0, 0, self.ditherMask)

        if self._config.get('inpaintFullRes'):
            maskedArea = self.getMaskedArea()
            if maskedArea is not None:
                painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
                color = contrastColor(self.scene().views()[0])
                pen = QPen(color, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                painter.setPen(pen)
                painter.drawRect(maskedArea)
        painter.end()
        self._outline.setPixmap(QPixmap.fromImage(outline))


    def getMaskedArea(self, ignoreConfig = False):
        if ((not ignoreConfig) and (not self._config.get('inpaintFullRes'))) or self._bounding_box is None:
            return
        padding = self._config.get('inpaintFullResPadding')
        top = self._bounding_box.top()
        bottom = self._bounding_box.bottom()
        left = self._bounding_box.left()
        right = self._bounding_box.right()
        if top >= bottom:
            return # mask was empty

        # Add padding:
        top = max(0, top - padding)
        bottom = min(self.height() - 1, bottom + padding)
        left = max(0, left - padding)
        right = min(self.width() - 1, right + padding)
        height = bottom - top
        width = right - left

        # Expand to match image section's aspect ratio:
        imageRatio = self.size().width() / self.size().height()
        boundsRatio = width / height

        if imageRatio > boundsRatio:
            targetWidth = int(imageRatio * height)
            widthToAdd = targetWidth - width
            assert(widthToAdd >= 0)
            dLeft = min(left, widthToAdd // 2)
            widthToAdd -= dLeft
            dRight = min(self.width() - 1 - right, widthToAdd)
            widthToAdd -= dRight
            if widthToAdd > 0:
                dLeft = min(left, dLeft + widthToAdd)
            left -= dLeft
            right += dRight
        else:
            targetHeight = width // imageRatio
            heightToAdd = targetHeight - height
            assert(heightToAdd >= 0)
            dTop = min(top, heightToAdd // 2)
            heightToAdd -= dTop
            dBottom = min(self.height() - 1 - bottom, heightToAdd)
            heightToAdd -= dBottom
            if heightToAdd > 0:
                dTop = min(top, dTop + heightToAdd)
            top -= dTop
            bottom += dBottom
        maskRect = QRect(QPoint(int(left), int(top)), QPoint(int(right), int(bottom)))
        return maskRect

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
        self._drawOutline()
        super()._handleChanges()

    def resize(self, size):
        super().resize(size)
        self._outline.setPixmap(self._outline.pixmap().scaled(size))

    def clear(self):
        super().clear()
        self._setEmptyOutline()

    def setVisible(self, visible):
        super().setVisible(visible)
        self._outline.setVisible(visible)

    def setOpacity(self, opacity):
        super().setOpacity(opacity)
        self._outline.setOpacity(opacity)
