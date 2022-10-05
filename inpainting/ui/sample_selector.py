from PyQt5.QtWidgets import QWidget, QLabel, QPushButton
from PyQt5.QtCore import Qt, QMargins
import PyQt5.QtGui as QtGui
from PyQt5.QtGui import QPainter, QPen, QColor, QImage, QPixmap
from PyQt5.QtCore import Qt, QPoint, QRect, QBuffer, QSize
from inpainting.ui.loading_widget import LoadingWidget
from inpainting.ui.layout_utils import getScaledPlacement, QEqualMargins
from inpainting.image_utils import imageToQImage
from PIL import Image

class SampleSelector(QWidget):
    """Shows all inpainting samples as they load, allows the user to select one or discard all of them."""

    def __init__(self, config, editedImage, mask, sketch, closeSelector):
        super().__init__()

        sourceImage = editedImage.getSelectionContent()
        if sketch.hasSketch:
            sketchImage = sketch.getImage().convert('RGBA')
            sourceImage = Image.alpha_composite(sourceImage.convert('RGBA'), sketchImage).convert('RGB')
        maskImage = mask.getImage()

        self._editedImage = editedImage
        self._closeSelector = closeSelector
        self._sourcePixmap = QPixmap.fromImage(imageToQImage(sourceImage))
        self._maskPixmap = QPixmap.fromImage(imageToQImage(maskImage))
        self._sourceImageBounds = QRect(0, 0, 0, 0)
        self._maskImageBounds = QRect(0, 0, 0, 0)
        
        self._nRows = config.get('batchCount')
        self._nColumns = config.get('batchSize')
        self._imageSize = QSize(sourceImage.width, sourceImage.height)
        self._options = []
        for row in range(self._nRows):
            columns = []
            for col in range(self._nColumns):
                columns.append({"image": None, "pixmap": None, "bounds": None})
            self._options.append(columns)

        self._instructions = QLabel(self, text="Click a sample to apply it to the source image, or click 'cancel' to discard all samples.")
        self._cancelButton = QPushButton(self)
        self._cancelButton.setText("cancel")
        self._cancelButton.clicked.connect(closeSelector)
        self._instructions.show()
        self._cancelButton.show()

        self._isLoading = False
        self._loadingWidget = LoadingWidget()
        self._loadingWidget.setParent(self)
        self._loadingWidget.setGeometry(self.frameGeometry())
        self._loadingWidget.hide()
        self.resizeEvent(None)

    def setIsLoading(self, isLoading, message=None):
        """Show or hide the loading indicator"""
        if isLoading:
            self._loadingWidget.show()
            if message:
                self._loadingWidget.setMessage(message)
            else:
                self._loadingWidget.setMessage("Loading images")
        else:
            self._loadingWidget.hide()
        self._isLoading = isLoading
        self.update()

    def loadSampleImage(self, imageSample, idx, batch):
        """
        Loads an inpainting sample image into the appropriate SampleWidget.
        Parameters:
        -----------
        imageSample : Image
            Newly generated inpainting image sample.
        idx : int
            Index of the image sample within its batch.
        batch : int
            Batch index of the image sample.
        """
        pixmap = QPixmap.fromImage(imageToQImage(imageSample))
        assert pixmap is not None
        self._options[batch][idx]["pixmap"] = pixmap
        self._options[batch][idx]["image"] = imageSample
        self.update()

    def resizeEvent(self, event):
        statusArea = QRect(0, 0, self.width(), self.height() // 8)
        self._sourceImageBounds = getScaledPlacement(statusArea, self._imageSize, 5)
        self._sourceImageBounds.moveLeft(statusArea.x() + 10)
        self._maskImageBounds = QRect(self._sourceImageBounds.x() + self._sourceImageBounds.width() + 5,
                self._sourceImageBounds.y(),
                self._sourceImageBounds.width(),
                self._sourceImageBounds.height())

        loadingWidgetSize = int(statusArea.height() * 1.2)
        loadingBounds = QRect(self.width() // 2 - loadingWidgetSize // 2, 0,
                loadingWidgetSize, loadingWidgetSize)
        self._loadingWidget.setGeometry(loadingBounds)

        textArea = QRect(self._maskImageBounds.x() + self._maskImageBounds.width() + 10,
                statusArea.y(),
                int(statusArea.width() * 0.9),
                statusArea.height()).marginsRemoved(QEqualMargins(4))
        self._instructions.setGeometry(textArea)
        cancelArea = QRect(textArea.width(), statusArea.y(),
            statusArea.width() - textArea.width(),
            statusArea.height()).marginsRemoved(QEqualMargins(statusArea.height() // 3))
        self._cancelButton.setGeometry(cancelArea)
        
        optionArea = QRect(0, statusArea.height(), self.width(), self.height() - statusArea.height())
        rowSize = optionArea.height() // self._nRows
        columnSize = optionArea.width() // self._nColumns
        for row in range(self._nRows):
            y = optionArea.y() + rowSize * row
            for col in range(self._nColumns):
                x = columnSize * col
                containerRect = QRect(x, y, columnSize, rowSize)
                self._options[row][col]["bounds"] = getScaledPlacement(containerRect,
                    self._imageSize, 10)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.drawPixmap(self._sourceImageBounds, self._sourcePixmap)
        painter.drawPixmap(self._maskImageBounds, self._maskPixmap)
        painter.setPen(QPen(Qt.black, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        for row in self._options:
            for option in row:
                painter.setPen(QPen(Qt.black, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                painter.drawRect(option['bounds'].marginsAdded(QEqualMargins(2)))
                if ('pixmap' in option) and (option['pixmap'] is not None):
                    painter.drawPixmap(option['bounds'], option['pixmap'])
                else:
                    painter.fillRect(option['bounds'], Qt.black)
                    painter.setPen(QPen(Qt.white, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                    painter.drawText(option['bounds'], Qt.AlignCenter, "Waiting for image...")

    def mousePressEvent(self, event):
        if self._isLoading:
            return
        rowNum = 0
        colNum = 0
        for row in self._options:
            rowNum += 1
            for option in row:
                colNum += 1
                if option['bounds'].contains(event.pos()):
                    if isinstance(option['image'], Image.Image):
                        print(f"selected {rowNum},{colNum}")
                        self._editedImage.setSelectionContent(option['image'])
                        self._closeSelector()
                        return
                    else:
                        print(f"{rowNum},{colNum} still pending")
                        return
