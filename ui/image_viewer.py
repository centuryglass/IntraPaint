from PyQt5.QtWidgets import QWidget, QSizePolicy
from PyQt5.QtGui import QPainter, QPen, QImage
from PyQt5.QtCore import Qt, QPoint, QRect, QSize
import PyQt5.QtGui as QtGui
from PIL import Image

from ui.image_utils import qImageToImage, imageToQImage
from ui.util.get_scaled_placement import getScaledPlacement
from ui.util.equal_margins import getEqualMargins

class ImageViewer(QWidget):
    """
    Shows the image being edited, and allows the user to select sections.
    """

    def __init__(self, editedImage):
        super().__init__()
        self._editedImage = editedImage
        self._borderSize = 4
        editedImage.sizeChanged.connect(lambda: self.resizeEvent(None))
        editedImage.selectionChanged.connect(lambda: self.update())
        editedImage.contentChanged.connect(lambda: self.update())
        self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))

    def resizeEvent(self, event):
        print(f"viewerSize: {self.size()}")
        if self._editedImage.hasImage():
            self._imageRect = getScaledPlacement(QRect(QPoint(0, 0), self.size()), self._editedImage.size(), self._borderSize)
        else:
            self._imageRect = getScaledPlacement(QRect(QPoint(0, 0), self.size()), self.size(), self._borderSize)

    def _imageToWidgetCoords(self, point):
        assert isinstance(point, QPoint)
        scale = self._imageRect.width() / self._editedImage.width()
        return QPoint(int(point.x() * scale) + self._imageRect.x(),
                int(point.y() * scale) + self._imageRect.y())

    def _widgetToImageCoords(self, point):
        assert isinstance(point, QPoint)
        scale = self._imageRect.width() / self._editedImage.width()
        return QPoint(int((point.x() - self._imageRect.x()) / scale),
                int((point.y() - self._imageRect.y()) / scale))

    def paintEvent(self, event):
        """Draw the image, selection area, and border."""
        painter = QPainter(self)
        linePen = QPen(Qt.black, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(linePen)
        if self._editedImage.hasImage():
            painter.drawImage(self._imageRect, self._editedImage.getQImage())
            # outline selection:
            selection = self._editedImage.getSelectionBounds()
            selectionTopLeft = self._imageToWidgetCoords(selection.topLeft())
            selectionBottomRight = self._imageToWidgetCoords(selection.topLeft() +
                    + QPoint(selection.width(), selection.height()))
            selectedRect = QRect(selectionTopLeft, selection.size())
            selectedRect.setBottomRight(selectionBottomRight)
            painter.drawRect(selectedRect)
        # draw margin:
        margin = self._borderSize // 2
        linePen.setWidth(self._borderSize)
        painter.drawRect(QRect(QPoint(0, 0), self.size()).marginsRemoved(getEqualMargins(2)))

    def sizeHint(self):
        if self._editedImage.hasImage():
            return self._editedImage.size()
        return QSize(512, 512)

    def mousePressEvent(self, event):
        """Select the area in in the image to be edited."""
        if event.button() == Qt.LeftButton and self._editedImage.hasImage():
            imageCoords = self._widgetToImageCoords(event.pos())
            selection = self._editedImage.getSelectionBounds()
            selection.moveTopLeft(imageCoords)
            self._editedImage.setSelectionBounds(selection)

