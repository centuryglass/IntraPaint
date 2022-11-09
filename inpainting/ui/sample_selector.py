from PyQt5.QtWidgets import QWidget, QLabel, QPushButton
from PyQt5.QtCore import Qt, QMargins
import PyQt5.QtGui as QtGui
from PyQt5.QtGui import QPainter, QPen, QColor, QImage, QPixmap
from PyQt5.QtCore import Qt, QPoint, QRect, QBuffer, QSize
from PIL import Image
import math, gc

from inpainting.ui.util.get_scaled_placement import getScaledPlacement
from inpainting.ui.util.equal_margins import getEqualMargins
from inpainting.ui.widget.loading_widget import LoadingWidget
from inpainting.image_utils import imageToQImage

class SampleSelector(QWidget):
    """Shows all inpainting samples as they load, allows the user to select one or discard all of them."""

    def __init__(self, config, editedImage, mask, sketch, closeSelector):
        super().__init__()

        self._config = config
        self._sketch = sketch

        sourceImage = editedImage.getSelectionContent()
        if sketch.hasSketch:
            sketchImage = sketch.getImage().convert('RGBA')
            sourceImage = Image.alpha_composite(sourceImage.convert('RGBA'), sketchImage).convert('RGB')
        maskImage = mask.getImage()

        self._editedImage = editedImage
        self._sourcePixmap = QPixmap.fromImage(imageToQImage(sourceImage))
        self._maskPixmap = QPixmap.fromImage(imageToQImage(maskImage))
        self._sourceImageBounds = QRect(0, 0, 0, 0)
        self._maskImageBounds = QRect(0, 0, 0, 0)
        self._includeOriginal = config.get('addOriginalToSamples')
        self._sourceOptionBounds = None
        self._zoomImageBounds = None
        
        self._batchCount = config.get('batchCount')
        self._batchSize = config.get('batchSize')
        self._imageSize = QSize(sourceImage.width, sourceImage.height)
        self._zoomMode = False
        self._zoomIndex = 0
        self._options = []
        for row in range(self._batchCount):
            columns = []
            for col in range(self._batchSize):
                columns.append({"image": None, "pixmap": None, "bounds": None})
            self._options.append(columns)

        self._instructions = QLabel(self, text="Click a sample to apply it to the source image, or click 'cancel' to"
                + " discard all samples.")
        self._instructions.show()
        if ((self._batchCount * self._batchSize) > 1) or self._includeOriginal:
            self._zoomButton = QPushButton(self)
            self._zoomButton.setText("Zoom in")
            self._zoomButton.clicked.connect(lambda: self.toggleZoom())
            self._zoomButton.show()
        else:
            self._zoomButton = None
        self._cancelButton = QPushButton(self)
        self._cancelButton.setText("Cancel")
        self._cancelButton.clicked.connect(closeSelector)
        self._cancelButton.show()

        self._isLoading = False
        self._loadingWidget = LoadingWidget()
        self._loadingWidget.setParent(self)
        self._loadingWidget.setGeometry(self.frameGeometry())
        self._loadingWidget.hide()
        self.resizeEvent(None)

        def freeMemoryAndClose():
            del self._sourcePixmap
            self._sourcePixmap = None
            del self._maskPixmap
            self._maskPixmap = None
            for row in self._options:
                for option in row:
                    if option["image"] is not None:
                        del option["image"]
                        option["image"] = None
                    if option["pixmap"] is not None:
                        del option["pixmap"]
                        option["pixmap"] = None
            gc.collect()
            closeSelector()
        self._closeSelector = freeMemoryAndClose

    def toggleZoom(self):
        if self._zoomButton is None:
            return
        if self._zoomMode:
            self._zoomButton.setText("Zoom in")
            self._zoomMode = False
        else: 
            self._zoomButton.setText("Zoom out")
            self._zoomMode = True
            self._zoomIndex = 0
        self.resizeEvent(None)
        self.update()

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

    def setLoadingMessage(self, message):
        self._loadingWidget.setMessage(message)

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
                int(statusArea.width() * 0.8),
                statusArea.height()).marginsRemoved(getEqualMargins(4))
        self._instructions.setGeometry(textArea)
        zoomArea = QRect(textArea.width(), statusArea.y(),
            (statusArea.width() - textArea.width()) // 2,
            statusArea.height()).marginsRemoved(getEqualMargins(statusArea.height() // 3))
        if self._zoomButton is not None:
            self._zoomButton.setGeometry(zoomArea)
        cancelArea = QRect(zoomArea.left() + zoomArea.width(), statusArea.y(),
            (statusArea.width() - zoomArea.right()),
            statusArea.height()).marginsRemoved(getEqualMargins(statusArea.height() // 3))
        self._cancelButton.setGeometry(cancelArea)

        
        optionCount = self._batchCount * self._batchSize
        if self._includeOriginal:
            optionCount += 1
        optionArea = QRect(0, statusArea.height(), self.width(), self.height() - statusArea.height())
        if self._zoomMode:
            # Make space on sides for arrows:
            arrowSize = max(self.width() // 70, 8)
            arrowMargin = arrowSize // 2
            optionArea.setLeft(optionArea.left() + arrowSize + (arrowMargin * 2))
            optionArea.setRight(optionArea.right() - arrowSize - (arrowMargin * 2))
            self._zoomImageBounds = getScaledPlacement(optionArea, self._imageSize, 2)

            arrowTop = optionArea.y() + (optionArea.height() // 2) - (arrowSize // 2)
            self._leftArrowBounds = QRect(optionArea.left() - (arrowSize + arrowMargin), arrowTop, arrowSize,
                    arrowSize)
            self._rightArrowBounds = QRect(optionArea.x() + optionArea.width() + arrowMargin, arrowTop, arrowSize,
                    arrowSize)
        else:
            margin = 10
            def getScaleFactorForRowCount(nRows):
                nColumns = math.ceil(optionCount / nRows)
                imgBounds = QRect(0, 0, optionArea.width() // nColumns, optionArea.height() // nRows)
                imgRect = getScaledPlacement(imgBounds, self._imageSize, margin)
                return imgRect.width() / self._imageSize.width()
            nRows = 1
            bestScale = 0
            lastScale = 0
            for i in range(1, optionCount + 1):
                scale = getScaleFactorForRowCount(i)
                lastScale = scale
                if scale > bestScale:
                    bestScale = scale
                    nRows = i
                elif scale < lastScale:
                    break
            nColumns = math.ceil(optionCount / nRows)
            rowSize = optionArea.height() // nRows
            columnSize = optionArea.width() // nColumns
            for idx in range(optionCount):
                batchIdx = idx // self._batchSize
                idxInBatch = idx % self._batchSize
                row = idx // nColumns
                col = idx % nColumns
                x = columnSize * col
                y = optionArea.y() + rowSize * row
                containerRect = QRect(x, y, columnSize, rowSize)
                if idx >= self._batchCount * self._batchSize:
                    self._sourceOptionBounds = getScaledPlacement(containerRect, self._imageSize, 10)
                else:
                    self._options[batchIdx][idxInBatch]["bounds"] = getScaledPlacement(containerRect, self._imageSize, 10)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        if self._sourcePixmap is not None:
            painter.drawPixmap(self._sourceImageBounds, self._sourcePixmap)
        if self._maskPixmap is not None:
            painter.drawPixmap(self._maskImageBounds, self._maskPixmap)
        painter.setPen(QPen(Qt.black, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        def drawImage(option):
            painter.setPen(QPen(Qt.black, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawRect(option['bounds'].marginsAdded(getEqualMargins(2)))
            if ('pixmap' in option) and (option['pixmap'] is not None):
                painter.drawPixmap(option['bounds'], option['pixmap'])
            else:
                painter.fillRect(option['bounds'], Qt.black)
                painter.setPen(QPen(Qt.white, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                painter.drawText(option['bounds'], Qt.AlignCenter, "Waiting for image...")
        if self._zoomMode:
            pixmap = None
            if self._zoomIndex >= self._batchCount * self._batchSize:
                pixmap = self._sourcePixmap
            else:
                idxInBatch = self._zoomIndex % self._batchSize
                batchIdx = self._zoomIndex // self._batchSize
                pixmap = self._options[batchIdx][idxInBatch]['pixmap']
            drawImage({ 'bounds': self._zoomImageBounds, 'pixmap': pixmap })

            # draw arrows:
            def drawArrow(arrowBounds, pts, text):
                painter.setPen(QPen(Qt.black, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                textBounds = QRect(arrowBounds)
                textBounds.moveTop(textBounds.top() - textBounds.height())
                bgBounds = QRect(arrowBounds)
                bgBounds.setTop(textBounds.top())
                # Arrow background:
                painter.fillRect(bgBounds.marginsAdded(getEqualMargins(4)), Qt.white)
                # Arrow:
                painter.drawLine(pts[0], pts[1])
                painter.drawLine(pts[1], pts[2])
                painter.drawLine(pts[0], pts[2])
                # Index labels:
                painter.drawText(textBounds, Qt.AlignCenter, text)
            maxIdx = (self._batchSize * self._batchCount) - (0 if self._includeOriginal else 1)
            prevIdx = maxIdx if (self._zoomIndex == 0) else (self._zoomIndex - 1)
            nextIdx = 0 if (self._zoomIndex >= maxIdx) else (self._zoomIndex + 1)
            leftMid = QPoint(self._leftArrowBounds.left(), self._leftArrowBounds.top()
                    + self._leftArrowBounds.width() // 2)
            rightMid = QPoint(self._rightArrowBounds.left() + self._rightArrowBounds.width(),
                    self._rightArrowBounds.top() + self._rightArrowBounds.width() // 2)
            drawArrow(self._leftArrowBounds,
                    [leftMid, self._leftArrowBounds.topRight(), self._leftArrowBounds.bottomRight()],
                    str(prevIdx + 1))
            drawArrow(self._rightArrowBounds,
                    [rightMid, self._rightArrowBounds.topLeft(), self._rightArrowBounds.bottomLeft()],
                    str(nextIdx + 1))
        else:
            for row in self._options:
                for option in row:
                    drawImage(option)
            if self._sourceOptionBounds is not None:
                option = { 'bounds': self._sourceOptionBounds, 'pixmap': self._sourcePixmap }
                drawImage(option)

    def mousePressEvent(self, event):
        def setImage(option):
            if isinstance(option['image'], Image.Image):
                self._editedImage.setSelectionContent(option['image'])
                self._closeSelector()
                return True
            else:
                print("image still pending")
            return
        if self._zoomMode:
            maxIdx = (self._batchSize * self._batchCount) - (0 if self._includeOriginal else 1)
            # Check for arrow clicks:
            if self._leftArrowBounds.contains(event.pos()):
                self._zoomIndex = maxIdx if (self._zoomIndex == 0) else (self._zoomIndex - 1)
                self.resizeEvent(None)
                self.update()
                return
            elif self._rightArrowBounds.contains(event.pos()):
                self._zoomIndex = 0 if (self._zoomIndex >= maxIdx) else (self._zoomIndex + 1)
                self.resizeEvent(None)
                self.update()
                return
            if self._isLoading:
                return
            if self._zoomImageBounds.contains(event.pos()):
                if self._includeOriginal and self._zoomIndex == maxIdx:
                    # Original chosen, no need to change anything:
                    self._closeSelector()
                else:
                    col = self._zoomIndex % self._batchSize
                    row = self._zoomIndex // self._batchSize
                    option = self._options[row][col]
                    setImage(option)
        else:
            if self._isLoading:
                return
            if self._includeOriginal and self._sourceOptionBounds is not None:
                if self._sourceOptionBounds.contains(event.pos()):
                    # Original chosen: write in sketch content if enabled, otherwise do nothing:
                    if self._config.get('saveSketchInResult') and self._sketch.hasSketch:
                        sourceSelection = self._editedImage.getSelectionContent()
                        sketchImage = self._sketch.getImage().resize((sourceSelection.width, sourceSelection.height),
                                self._config.get('downscaleMode')).convert('RGBA')
                        sourceSelection = Image.alpha_composite(sourceSelection.convert('RGBA'), sketchImage).convert('RGB')
                        self._editedImage.setSelectionContent(sourceSelection)
                        self._sketch.clear()
                    self._closeSelector()
            rowNum = 0
            colNum = 0
            for row in self._options:
                rowNum += 1
                for option in row:
                    colNum += 1
                    if option['bounds'].contains(event.pos()):
                        if self._config.get('saveSketchInResult') and self._sketch.hasSketch:
                            self._sketch.clear()
                        setImage(option)
                        return