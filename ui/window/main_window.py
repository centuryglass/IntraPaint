from PyQt5.QtWidgets import *
from PyQt5.QtGui import QPainter, QPen, QIcon
from PyQt5.QtCore import Qt, QObject, QThread, QRect, QPoint, QSize, pyqtSignal
import PyQt5.QtGui as QtGui
from PIL import Image, ImageFilter
import sys, os, glob

from ui.modal.modal_utils import showErrorDialog, requestConfirmation
from ui.panel.mask_panel import MaskPanel
from ui.panel.image_panel import ImagePanel
from ui.sample_selector import SampleSelector
from ui.config_control_setup import *
from ui.widget.draggable_arrow import DraggableArrow
from ui.widget.loading_widget import LoadingWidget
from data_model.filled_canvas import FilledMaskCanvas

class MainWindow(QMainWindow):
    """Main user interface for GLID-3-XL inpainting."""

    def __init__(self, config, editedImage, mask, sketch, controller):
        super().__init__()
        self.setWindowIcon(QtGui.QIcon('resources/icon.png'))
        # Initialize UI/editing data model:
        self._controller = controller
        self._config = config
        self._editedImage = editedImage
        self._mask = mask
        self._sketch = sketch
        self._draggingDivider = False
        self._timelapsePath = None
        self._sampleSelector = None
        self._layoutMode = 'horizontal'

        # Create components, build layout:
        self.layout = QVBoxLayout()
        self._mainWidget = QWidget(self);
        self._mainWidget.setLayout(self.layout)

        # Image/Mask editing layout:
        imagePanel = ImagePanel(self._config, self._editedImage, controller)
        maskPanel = MaskPanel(self._config, self._mask, self._sketch, self._editedImage)
        self.installEventFilter(maskPanel)
        divider = DraggableArrow()
        self._scaleHandler = None
        self.imageLayout = None
        self.imagePanel = imagePanel
        self.maskPanel = maskPanel
        self.divider = divider
        self._setupCorrectLayout()


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
        addAction("Resize canvas", "F2", lambda: controller.resizeCanvas(), imageMenu)
        addAction("Scale image", "F3", lambda: controller.scaleImage(), imageMenu)
        addAction("Generate", "F4", lambda: controller.startAndManageInpainting(), imageMenu)
        def updateMetadata():
            self._editedImage.updateMetadata()
            messageBox = QMessageBox(self)
            messageBox.setWindowTitle("Metadata updated")
            messageBox.setText("On save, current image generation paremeters will be stored within the image")
            messageBox.setStandardButtons(QMessageBox.Ok)
            messageBox.exec()
        addAction("Update image metadata", None, updateMetadata, imageMenu)

        # Tools:
        toolMenu = self._menu.addMenu("Tools")
        addAction("Toggle mask/sketch editing mode", "F6", lambda: maskPanel.setUseMaskMode(not maskPanel.maskModeButton.isChecked()), toolMenu)
        addAction("Toggle pen/eraser tool", "F7", lambda: maskPanel.swapDrawTool(), toolMenu)
        def clearBoth():
            mask.clear()
            sketch.clear()
        addAction("Clear mask and sketch", "F8", clearBoth, toolMenu)
        def brushSizeChange(offset):
            size = maskPanel.getBrushSize()
            maskPanel.setBrushSize(size + offset)
        addAction("Increase brush size", "Ctrl+]", lambda: brushSizeChange(1), toolMenu)
        addAction("Decrease brush size", "Ctrl+[", lambda: brushSizeChange(-1), toolMenu)


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

    def _clearEditingLayout(self):
        if self.imageLayout is not None:
            for widget in [self.imagePanel, self.divider, self.maskPanel]:
                self.imageLayout.removeWidget(widget)
            self.layout.removeItem(self.imageLayout)
            self.imageLayout = None
            if self._scaleHandler is not None:
                self.divider.dragged.disconnect(self._scaleHandler)
                self._scaleHandler = None

    def _setupWideLayout(self):
        if self.imageLayout is not None:
            self._clearEditingLayout()
        imageLayout = QHBoxLayout()
        self.divider.setHorizontalMode()
        self.imageLayout = imageLayout
        def scaleWidgets(pos):
            x = pos.x()
            imgWeight = int(x / self.width() * 300)
            maskWeight = 300 - imgWeight
            self.imageLayout.setStretch(0, imgWeight)
            self.imageLayout.setStretch(2, maskWeight)
            self.update()
        self._scaleHandler = scaleWidgets
        self.divider.dragged.connect(self._scaleHandler)

        imageLayout.addWidget(self.imagePanel, stretch=255)
        imageLayout.addWidget(self.divider, stretch=5)
        imageLayout.addWidget(self.maskPanel, stretch=100)
        self.layout.insertLayout(0, imageLayout, stretch=255)

    def _setupTallLayout(self):
        if self.imageLayout is not None:
            self._clearEditingLayout()
        imageLayout = QVBoxLayout()
        self.imageLayout = imageLayout
        self.divider.setVerticalMode()
        def scaleWidgets(pos):
            y = pos.y()
            imgWeight = int(y / self.height() * 300)
            maskWeight = 300 - imgWeight
            self.imageLayout.setStretch(0, imgWeight)
            self.imageLayout.setStretch(2, maskWeight)
            self.update()
        self._scaleHandler = scaleWidgets
        self.divider.dragged.connect(self._scaleHandler)

        imageLayout.addWidget(self.imagePanel, stretch=255)
        imageLayout.addWidget(self.divider, stretch=5)
        imageLayout.addWidget(self.maskPanel, stretch=100)
        self.layout.insertLayout(0, imageLayout, stretch=255)
        self.imageLayout = imageLayout
        self.update()

    def _setupCorrectLayout(self):
        if self.height() > (self.width() * 1.2):
            if isinstance(self.imageLayout, QHBoxLayout) or self.imageLayout is None:
                self._setupTallLayout()
        elif isinstance(self.imageLayout, QVBoxLayout) or self.imageLayout is None: 
                self._setupWideLayout()

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

    def isSampleSelectorVisible(self):
        return self.centralWidget.currentWidget() is not self._mainWidget

    def setSampleSelectorVisible(self, visible):
        isVisible = self.isSampleSelectorVisible()
        if (visible == isVisible):
            return
        if visible:
            mask = self._mask if (self._config.get('editMode') == 'Inpaint') else FilledMaskCanvas(self._config)
            self._sampleSelector = SampleSelector(
                    self._config,
                    self._editedImage,
                    mask,
                    self._sketch,
                    lambda: self.setSampleSelectorVisible(False),
                    lambda img: self._controller.selectAndApplySample(img))
            self.centralWidget.addWidget(self._sampleSelector)
            self.centralWidget.setCurrentWidget(self._sampleSelector)
            self.installEventFilter(self._sampleSelector)
        else:
            self.removeEventFilter(self._sampleSelector)
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
        self._setupCorrectLayout()
        if hasattr(self, '_loadingWidget'):
            loadingWidgetSize = int(self.height() / 8)
            loadingBounds = QRect(self.width() // 2 - loadingWidgetSize // 2, loadingWidgetSize * 3,
                    loadingWidgetSize, loadingWidgetSize)
            self._loadingWidget.setGeometry(loadingBounds)

    def mousePressEvent(self, event):
        if not self._isLoading:
            super().mousePressEvent(event)
