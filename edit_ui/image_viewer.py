from PyQt5 import QtWidgets
from PyQt5.QtGui import QPainter, QPen, QImage
from PyQt5.QtCore import Qt, QPoint, QRect, QSize, pyqtSignal
import PyQt5.QtGui as QtGui
from PIL import Image
from edit_ui.ui_utils import getScaledPlacement, qImageToImage, imageToQImage, QEqualMargins

class ImageViewer(QtWidgets.QWidget):
    """
    QWidget that shows the image being edited, and allows the user to select sections.
    ...
    Attributes:
    -----------
    onSelection : pyqtSignal(QPoint)
        Signal that fires whenever the selection changes coordinates, or whenever the image portion under the
        selection changes.
    """
    onSelection = pyqtSignal(QPoint, QSize)

    def __init__( self,
            pilImage=None,
            selectionSize = QSize(256, 256)):
        """
        Parameters:
        -----------
        pilImage : Image, optional
            An initial pillow Image object to load.
        selectionSize : QSize, default QSize(256, 256)
            Size in pixels of selected image sections used for inpainting.
        """
        super().__init__()
        assert pilImage is None or isinstance(pilImage, Image.Image)
        assert isinstance(selectionSize, QSize)

        self._selectionSize = selectionSize
        self._borderSize = 4
        self._selected = QPoint(0, 0)
        if pilImage is not None:
            self.setImage(pilImage)

    def selectionWidth(self):
        """Returns the width of the selected image area."""
        return self._selectionSize.width()
    
    def selectionHeight(self):
        """Returns the height of the selected image area."""
        return self._selectionSize.height()

    def selectionSize(self):
        """Returns the size of the selected image area."""
        return self._selectionSize

    def hasImage(self):
        """Checks if an image has been loaded for editing."""
        return hasattr(self, '_qimage')

    def getImage(self):
        """Returns the image currently being edited as a PIL Image object"""
        if not self.hasImage():
            return None
        return qImageToImage(self._qimage)

    def setImage(self, image):
        """Loads a new image to be edited from a file path, QImage, or PIL image."""
        if isinstance(image, str):
            try:
                self._qimage = QImage(image)
                self._qimage.convertTo(QImage.Format_RGB888)
            except Exception as err:
                print(f"image load error: {err}")
                self._qimage = None
            if self._qimage is None:
                print("ImageViewer.setImage: invalid image!")
                return
        elif isinstance(image, QImage):
            self._qimage = image
        elif isinstance(image, Image.Image):
            self._qimage = imageToQImage(image)
        else:
            print("ImageViewer.setImage: image was not a string, QImage, or PIL Image")
            return
        self._pixmap = QtGui.QPixmap.fromImage(self._qimage)
        self.resizeEvent(None)
        if not hasattr(self, '_selected'):
            self._selected = QPoint(0, 0)
        self.onSelection.emit(self._selected, self._selectionSize)
        self.update()

    def getSelection(self):
        """Gets the QPoint coordinates of the area selected for inpainting."""
        if hasattr(self, '_selected'):
            return self._selected

    def setSelection(self, pt=None, size=None):
        """Sets the QPoint coordinates and/or QSize dimensions of the area selected for inpainting."""
        assert pt is None or isinstance(pt, QPoint)
        assert size is None or isinstance(size, QSize)
        assert pt is not None or size is not None

        if not hasattr(self, '_selected') or not hasattr(self, '_qimage'):
            return
        # Unless selection size exceeds image size, ensure the selection is
        # entirely within the image:
        initial_size = self._selectionSize
        initial_coords = self._selected
        if size:
            self._selectionSize = size
            if not pt:
                pt = initial_coords
        if pt:
            if pt.x() >= (self._qimage.width() - self.selectionWidth()):
                pt.setX(self._qimage.width() - self.selectionWidth())
            if pt.x() < 0:
                pt.setX(0)
            if pt.y() >= (self._qimage.height() - self.selectionHeight()):
                pt.setY(self._qimage.height() - self.selectionHeight())
            if pt.y() < 0:
                pt.setY(0)
            self._selected = pt
        if (size and size != initial_size) or (pt and pt != initial_coords):
            self.onSelection.emit(self._selected, self._selectionSize)
            self.update()

    def insertIntoSelection(self, inserted_image):
        """Pastes a pillow image object onto the image at the selected coordinates."""
        assert isinstance(inserted_image, Image.Image)
        if hasattr(self, '_selected') and hasattr(self, '_qimage'):
            pilImage = qImageToImage(self._qimage)
            pilImage.paste(inserted_image, (self._selected.x(), self._selected.y()))
            self.setImage(pilImage)

    def getSelectedSection(self):
        """Gets a copy of the image, cropped to the current selection area."""
        if hasattr(self, '_selected') and hasattr(self, '_qimage'):
            cropped_image = self._qimage.copy(self._selected.x(),
                    self._selected.y(),
                    self.selectionWidth(),
                    self.selectionHeight())
            return qImageToImage(cropped_image)
        else:
            print(f"selected: {self._selected}, no qimage")
    
    def imageSize(self):
        """Returns the size of the current edited image."""
        if hasattr(self, '_qimage'):
            return self._qimage.size()

    def _imageToWidgetCoords(self, point):
        assert isinstance(point, QPoint)
        scale = self._imageRect.width() / self._qimage.width()
        return QPoint(int(point.x() * scale) + self._imageRect.x(),
                int(point.y() * scale) + self._imageRect.y())

    def _widgetToImageCoords(self, point):
        assert isinstance(point, QPoint)
        scale = self._imageRect.width() / self._qimage.width()
        return QPoint(int((point.x() - self._imageRect.x()) / scale),
                int((point.y() - self._imageRect.y()) / scale))

    def paintEvent(self, event):
        """Draw the image, selection area, and border."""
        if not hasattr(self, '_qimage'):
            return
        painter = QPainter(self)
        painter.drawPixmap(self._imageRect, self._pixmap)

        painter.setPen(QPen(Qt.black, self._borderSize, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        margin = self._borderSize // 2
        painter.drawRect(QRect(QPoint(0, 0), self.size()).marginsRemoved(QEqualMargins(2)))
        if hasattr(self, '_selected'):
            painter.setPen(QPen(Qt.black, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            selectionTopLeft = self._imageToWidgetCoords(self._selected)
            selectionBottomRight = self._imageToWidgetCoords(self._selected 
                    + QPoint(self.selectionWidth(), self.selectionHeight()))
            selectedRect = QRect(selectionTopLeft, self._selectionSize)
            selectedRect.setBottomRight(selectionBottomRight)
            painter.drawRect(selectedRect)

    def mousePressEvent(self, event):
        """Select the arean in the image to be edited."""
        if event.button() == Qt.LeftButton and hasattr(self, '_qimage'):
            imageCoords = self._widgetToImageCoords(event.pos())
            self.setSelection(imageCoords)
            self.update()

    def resizeEvent(self, event):
        if not hasattr(self, '_qimage') or not isinstance(self._qimage, QImage):
            return
        self._imageRect = getScaledPlacement(QRect(QPoint(0, 0), self.size()), self._qimage.size(), self._borderSize)
        self._pixmap = QtGui.QPixmap.fromImage(self._qimage)
        self._pixmap = self._pixmap.scaled(self._imageRect.size())
