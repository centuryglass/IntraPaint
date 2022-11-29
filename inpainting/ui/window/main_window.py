from PyQt5.QtWidgets import *
from PyQt5.QtGui import QPainter, QPen, QIcon
from PyQt5.QtCore import Qt, QObject, QThread, QRect, QPoint, QSize, pyqtSignal
import PyQt5.QtGui as QtGui
from PIL import Image, ImageFilter
import sys, os, glob

from inpainting.ui.modal.modal_utils import showErrorDialog, requestConfirmation
from inpainting.ui.panel.mask_panel import MaskPanel
from inpainting.ui.panel.image_panel import ImagePanel
from inpainting.ui.sample_selector import SampleSelector
from inpainting.ui.config_control_setup import *
from inpainting.ui.widget.draggable_arrow import DraggableArrow
from inpainting.ui.widget.loading_widget import LoadingWidget

class MainWindow(QMainWindow):
    """Main user interface for GLID-3-XL inpainting."""

    def __init__(self, config, editedImage, mask, sketch, controller):
        super().__init__()
        self.setWindowIcon(QtGui.QIcon('resources/icon.png'))
        # Initialize UI/editing data model:
        self._config = config
        self._editedImage = editedImage
        self._mask = mask
        self._sketch = sketch
        self._draggingDivider = False
        self._timelapsePath = None
        self._sampleSelector = None

        # Create components, build layout:
        self.layout = QVBoxLayout()
        self._mainWidget = QWidget(self);
        self._mainWidget.setLayout(self.layout)

        # Image/Mask editing layout:
        imageLayout = QHBoxLayout()
        imagePanel = ImagePanel(self._config, self._editedImage, controller)
        maskPanel = MaskPanel(self._config, self._mask, self._sketch, self._editedImage)
        divider = DraggableArrow()
        def scaleWidgets(pos):
            x = pos.x()
            imgWeight = int(x / self.width() * 300)
            maskWeight = 300 - imgWeight
            self.imageLayout.setStretch(0, imgWeight)
            self.imageLayout.setStretch(2, maskWeight)
            self.update()
        divider.dragged.connect(scaleWidgets)

        imageLayout.addWidget(imagePanel, stretch=255)
        imageLayout.addWidget(divider, stretch=5)
        imageLayout.addWidget(maskPanel, stretch=100)
        self.layout.addLayout(imageLayout, stretch=255)
        self.imageLayout = imageLayout
        self.imagePanel = imagePanel
        self.maskPanel = maskPanel

        # Set up menu:
        self._menu = self.menuBar()

        def addAction(name, shortcut, onTrigger, menu):
            action = QAction(name, self)
            if shortcut is not None:
                action.setShortcut(shortcut)
            action.triggered.connect(onTrigger)
            menu.addAction(action)

        # File:
        fileMenu = self._menu.addMenu("File")
        addAction("New Image", "Ctrl+N", lambda: controller.newImage(), fileMenu)
        addAction("Save", "Ctrl+S", lambda: controller.saveImage(), fileMenu)
        addAction("Load", "Ctrl+O", lambda: controller.loadImage(), fileMenu)
        addAction("Reload", "F5", lambda: controller.reloadImage(), fileMenu)
        def tryQuit():
            if (not self._editedImage.hasImage()) or requestConfirmation(self, "Quit now?", "All unsaved changes will be lost."):
                self.close()
        addAction("Quit", "Ctrl+Q", tryQuit, fileMenu)

        # Image:
        imageMenu = self._menu.addMenu("Image")
        addAction("Resize canvas", None, lambda: controller.resizeCanvas(), imageMenu)
        addAction("Scale image", None, lambda: controller.scaleImage(), imageMenu)
        def updateMetadata():
            self._editedImage.updateMetadata()
            messageBox = QMessageBox(self)
            messageBox.setWindowTitle("Metadata updated")
            messageBox.setText("On save, current image generation paremeters will be stored within the image")
            messageBox.setStandardButtons(QMessageBox.Ok)
            messageBox.exec()
        addAction("Update image metadata", None, updateMetadata, imageMenu)


        # Build config + control layout (varying based on implementation): 
        self._buildControlLayout(controller)
        self.centralWidget = QStackedWidget(self);
        self.centralWidget.addWidget(self._mainWidget)
        self.setCentralWidget(self.centralWidget)
        self.centralWidget.setCurrentWidget(self._mainWidget)

        # Loading widget (for interrogate):
        self._isLoading = False
        self._loadingWidget = LoadingWidget()
        self._loadingWidget.setParent(self)
        self._loadingWidget.setGeometry(self.frameGeometry())
        self._loadingWidget.hide()

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
        self.resizeEvent(None)

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
            del self._sampleSelector
            self._sampleSelector = None

    def loadSamplePreview(self, image, y, x):
        if self._sampleSelector is None:
            print(f"Tried to load sample y={y} x={x} after sampleSelector was closed")
        else:
            self._sampleSelector.loadSampleImage(image, y, x)

    def setIsLoading(self, isLoading, message=None):
        if self._sampleSelector is not None:
            self._sampleSelector.setIsLoading(isLoading, message)
        else:
            if isLoading:
                self._loadingWidget.show()
                if message:
                    self._loadingWidget.setMessage(message)
                else:
                    self._loadingWidget.setMessage("Loading...")
            else:
                self._loadingWidget.hide()
            self._isLoading = isLoading
            self.update()

    def setLoadingMessage(self, message):
        if self._sampleSelector is not None:
            self._sampleSelector.setLoadingMessage(message)

    def resizeEvent(self, event):
        loadingWidgetSize = int(self.height() / 8)
        loadingBounds = QRect(self.width() // 2 - loadingWidgetSize // 2, loadingWidgetSize * 3,
                loadingWidgetSize, loadingWidgetSize)
        self._loadingWidget.setGeometry(loadingBounds)

    def mousePressEvent(self, event):
        if not self._isLoading:
            super().mousePressEvent(event)
