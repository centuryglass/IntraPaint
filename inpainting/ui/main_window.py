from PyQt5.QtWidgets import *
from PyQt5.QtGui import QPainter, QPen
from PyQt5.QtCore import Qt, QObject, QThread, QRect, QPoint, QSize, pyqtSignal
from inpainting.ui.mask_panel import MaskPanel
from inpainting.ui.image_panel import ImagePanel
from inpainting.ui.sample_selector import SampleSelector
from inpainting.ui.config_control_setup import *
from inpainting.ui.modal_utils import showErrorDialog
import PyQt5.QtGui as QtGui
from PIL import Image, ImageFilter
import sys, os, glob

class MainWindow(QMainWindow):
    """Main user interface for GLID-3-XL inpainting."""

    def __init__(self, config, editedImage, mask, sketch, controller):
        super().__init__()
        # Initialize UI/editing data model:
        self._config = config
        self._editedImage = editedImage
        self._mask = mask
        self._sketch = sketch
        self._draggingDivider = False
        self._timelapsePath = None

        # Create components, build layout:
        self.layout = QVBoxLayout()
        self._mainWidget = QWidget(self);
        self._mainWidget.setLayout(self.layout)

        # Image/Mask editing layout:
        imageLayout = QHBoxLayout()
        imagePanel = ImagePanel(self._config, self._editedImage)
        maskPanel = MaskPanel(self._config, self._mask, self._sketch, self._editedImage)
        imageLayout.addWidget(imagePanel, stretch=255)
        imageLayout.addSpacing(30)
        imageLayout.addWidget(maskPanel, stretch=100)
        self.layout.addLayout(imageLayout, stretch=255)
        self.imageLayout = imageLayout
        self.imagePanel = imagePanel
        self.maskPanel = maskPanel

        # Build config + control layout (varying based on implementation): 
        self._buildControlLayout(controller)
        self.centralWidget = QStackedWidget(self);
        self.centralWidget.addWidget(self._mainWidget)
        self.setCentralWidget(self.centralWidget)
        self.centralWidget.setCurrentWidget(self._mainWidget)

    def _createScaleModeSelector(self, parent, configKey): 
        scaleModeList = QComboBox(parent)
        filterTypes = [
            ('Bilinear', Image.BILINEAR),
            ('Nearest', Image.NEAREST),
            ('Hamming', Image.HAMMING),
            ('Bicubic', Image.BICUBIC),
            ('Lanczos', Image.LANCZOS),
            ('Box', Image.BOX)
        ]
        for name, imageFilter in filterTypes:
            scaleModeList.addItem(name, imageFilter)
        scaleModeList.setCurrentIndex(scaleModeList.findData(self._config.get(configKey)))
        def setScaleMode(modeIndex):
            mode = scaleModeList.itemData(modeIndex)
            if mode:
                self._config.set(configKey, mode)
        scaleModeList.currentIndexChanged.connect(setScaleMode)
        self._config.connect(parent, 'scaleSelectionBeforeInpainting',
                lambda useScaling: scaleModeList.setEnabled(useScaling))
        return scaleModeList

    def _buildControlLayout(self, controller):
        inpaintPanel = QWidget(self)
        textPromptBox = connectedTextEdit(inpaintPanel, self._config, 'prompt')
        negativePromptBox = connectedTextEdit(inpaintPanel, self._config, 'negativePrompt')

        batchSizeBox = connectedSpinBox(inpaintPanel, self._config, 'batchSize', maxKey='maxBatchSize')
        batchSizeBox.setRange(1, batchSizeBox.maximum())
        batchSizeBox.setToolTip("Inpainting images generated per batch")

        batchCountBox = connectedSpinBox(inpaintPanel, self._config, 'batchCount', maxKey='maxBatchCount')
        batchCountBox.setRange(1, batchCountBox.maximum())
        batchCountBox.setToolTip("Number of inpainting image batches to generate")

        inpaintButton = QPushButton();
        inpaintButton.setText("Start inpainting")
        inpaintButton.clicked.connect(lambda: controller.startAndManageInpainting())

        moreOptionsBar = QHBoxLayout()
        guidanceScaleBox = connectedSpinBox(inpaintPanel, self._config, 'guidanceScale', maxKey='maxGuidanceScale',
                stepSizeKey='guidanceScaleStep')
        guidanceScaleBox.setValue(self._config.get('guidanceScale'))
        guidanceScaleBox.setRange(1.0, self._config.get('maxGuidanceScale'))
        guidanceScaleBox.setToolTip("Scales how strongly the prompt and negative are considered. Higher values are "
                + "usually more precise, but have less variation.")

        skipStepsBox = connectedSpinBox(inpaintPanel, self._config, 'skipSteps', maxKey='maxSkipSteps')
        skipStepsBox.setToolTip("Sets how many diffusion steps to skip. Higher values generate faster and produce "
                + "simpler images.")

        enableScaleCheckbox = connectedCheckBox(inpaintPanel, self._config, 'scaleSelectionBeforeInpainting')
        enableScaleCheckbox.setText("Scale edited areas")
        enableScaleCheckbox.setToolTip("Enabling scaling allows for larger sample areas and better results at small "
                + "scales, but increases the time required to generate images for small areas.")
        def updateScale():
            if self._editedImage.hasImage():
                self.imagePanel.reloadScaleBounds()
        enableScaleCheckbox.stateChanged.connect(updateScale)

        upscaleModeLabel = QLabel(inpaintPanel)
        upscaleModeLabel.setText("Upscaling mode:")
        upscaleModeList = self._createScaleModeSelector(inpaintPanel, 'upscaleMode')
        upscaleModeList.setToolTip("Image scaling mode used when increasing image scale");
        downscaleModeLabel = QLabel(inpaintPanel)
        downscaleModeLabel.setText("Downscaling mode:")
        downscaleModeList = self._createScaleModeSelector(inpaintPanel, 'downscaleMode')
        downscaleModeList.setToolTip("Image scaling mode used when decreasing image scale");
        
        moreOptionsBar.addWidget(QLabel(inpaintPanel, text="Guidance scale:"), stretch=0)
        moreOptionsBar.addWidget(guidanceScaleBox, stretch=20)
        moreOptionsBar.addWidget(QLabel(inpaintPanel, text="Skip timesteps:"), stretch=0)
        moreOptionsBar.addWidget(skipStepsBox, stretch=20)
        moreOptionsBar.addWidget(enableScaleCheckbox, stretch=10)
        moreOptionsBar.addWidget(upscaleModeLabel, stretch=0)
        moreOptionsBar.addWidget(upscaleModeList, stretch=10)
        moreOptionsBar.addWidget(downscaleModeLabel, stretch=0)
        moreOptionsBar.addWidget(downscaleModeList, stretch=10)

        zoomButton = QPushButton(); 
        zoomButton.setText("Zoom")
        zoomButton.setToolTip("Save frame, zoom out 15%, set mask to new blank area")
        zoomButton.clicked.connect(lambda: controller.zoomOut())
        moreOptionsBar.addWidget(zoomButton, stretch=5)

        # Build layout with labels:
        layout = QGridLayout()
        layout.addWidget(QLabel(inpaintPanel, text="Prompt:"), 1, 1, 1, 1)
        layout.addWidget(textPromptBox, 1, 2, 1, 1)
        layout.addWidget(QLabel(inpaintPanel, text="Negative:"), 2, 1, 1, 1)
        layout.addWidget(negativePromptBox, 2, 2, 1, 1)
        layout.addWidget(QLabel(inpaintPanel, text="Batch size:"), 1, 3, 1, 1)
        layout.addWidget(batchSizeBox, 1, 4, 1, 1)
        layout.addWidget(QLabel(inpaintPanel, text="Batch count:"), 2, 3, 1, 1)
        layout.addWidget(batchCountBox, 2, 4, 1, 1)
        layout.addWidget(inpaintButton, 2, 5, 1, 1)
        layout.setColumnStretch(2, 255) # Maximize prompt input

        layout.addLayout(moreOptionsBar, 3, 1, 1, 4)
        inpaintPanel.setLayout(layout)
        self.layout.addWidget(inpaintPanel, stretch=20)

    def setSampleSelectorVisible(self, visible):
        isVisible = (self.centralWidget.currentWidget() is not self._mainWidget)
        if (visible == isVisible):
            return
        if visible:
            self._sampleSelector = SampleSelector(
                    self._config,
                    self._editedImage,
                    self._mask,
                    self._sketch,
                    lambda: self.setSampleSelectorVisible(False))
            self.centralWidget.addWidget(self._sampleSelector)
            self.centralWidget.setCurrentWidget(self._sampleSelector)
        else:
            self.centralWidget.setCurrentWidget(self._mainWidget)
            self.centralWidget.removeWidget(self._sampleSelector)
            self._sampleSelector = None

    def loadSamplePreview(self, image, y, x):
        if self._sampleSelector is None:
            print(f"Tried to load sample y={y} x={x} after sampleSelector was closed")
        else:
            self._sampleSelector.loadSampleImage(image, y, x)

    def setIsLoading(self, isLoading, message=None):
        if self._sampleSelector is not None:
            self._sampleSelector.setIsLoading(isLoading, message)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.centralWidget.currentWidget() is self._mainWidget:
            painter = QPainter(self)
            color = Qt.green if self._draggingDivider else Qt.black
            size = 4 if self._draggingDivider else 2
            painter.setPen(QPen(color, size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            dividerBox = self._dividerCoords()
            yMid = dividerBox.y() + (dividerBox.height() // 2)
            midLeft = QPoint(dividerBox.x(), yMid)
            midRight = QPoint(dividerBox.right(), yMid)
            arrowWidth = dividerBox.width() // 4
            # Draw arrows:
            painter.drawLine(midLeft, midRight)
            painter.drawLine(midLeft, dividerBox.topLeft() + QPoint(arrowWidth, 0))
            painter.drawLine(midLeft, dividerBox.bottomLeft() + QPoint(arrowWidth, 0))
            painter.drawLine(midRight, dividerBox.topRight() - QPoint(arrowWidth, 0))
            painter.drawLine(midRight, dividerBox.bottomRight() - QPoint(arrowWidth, 0))

    def _dividerCoords(self):
        imageRight = self.imagePanel.x() + self.imagePanel.width()
        maskLeft = self.maskPanel.x()
        width = (maskLeft - imageRight) // 2
        height = width // 2
        x = imageRight + (width // 2)
        y = self.imagePanel.y() + (self.imagePanel.height() // 2) - (height // 2)
        return QRect(x, y, width, height)

    def mousePressEvent(self, event):
        if self.centralWidget.currentWidget() is self._mainWidget and self._dividerCoords().contains(event.pos()):
            self._draggingDivider = True
            self.update()

    def mouseMoveEvent(self, event):
        if event.buttons() and self._draggingDivider:
            x = event.pos().x()
            imgWeight = int(x / self.width() * 300)
            maskWeight = 300 - imgWeight
            self.imageLayout.setStretch(0, imgWeight)
            self.imageLayout.setStretch(2, maskWeight)
            self.update()

    def mouseReleaseEvent(self, event):
        if self._draggingDivider:
            self._draggingDivider = False
            self.update()
