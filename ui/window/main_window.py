from PyQt5.QtWidgets import *
from PyQt5.QtGui import QPainter, QPen, QIcon, QPixmap
from PyQt5.QtCore import Qt, QObject, QThread, QRect, QPoint, QSize, pyqtSignal
import PyQt5.QtGui as QtGui
from PIL import Image, ImageFilter
import sys, os, glob, math

from ui.modal.modal_utils import showErrorDialog, requestConfirmation
from ui.modal.settings_modal import SettingsModal
from ui.panel.mask_panel import MaskPanel
from ui.panel.image_panel import ImagePanel
from ui.sample_selector import SampleSelector
from ui.config_control_setup import *
from ui.widget.draggable_arrow import DraggableArrow
from ui.widget.loading_widget import LoadingWidget
from ui.util.contrast_color import contrastColor
from data_model.canvas.filled_canvas import FilledMaskCanvas

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
        self._slidersEnabled = True

        # Create components, build layout:
        self.layout = QVBoxLayout()
        self._mainWidget = QWidget(self);
        self._mainWidget.setLayout(self.layout)
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

        def onImageToggle(imageShowing):
            if imageShowing:
                self.imageLayout.setStretch(0, 255)
                self.imageLayout.setStretch(2, 100)
            else:
                self.imageLayout.setStretch(0, 1)
                self.imageLayout.setStretch(2, 255)
            divider.setHidden(not imageShowing)
            self.update()
        imagePanel.imageToggled().connect(onImageToggle)

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
        def ifNotSelecting(fn):
            if not self.isSampleSelectorVisible():
                fn()
        addAction("New Image", "Ctrl+N", lambda: ifNotSelecting(lambda: controller.newImage()), fileMenu)
        addAction("Save", "Ctrl+S", lambda: controller.saveImage(), fileMenu)
        addAction("Load", "Ctrl+O", lambda: ifNotSelecting(lambda: controller.loadImage()), fileMenu)
        addAction("Reload", "F5", lambda: ifNotSelecting(lambda: controller.reloadImage()), fileMenu)
        def tryQuit():
            if (not self._editedImage.hasImage()) or requestConfirmation(self, "Quit now?", "All unsaved changes will be lost."):
                self.close()
        addAction("Quit", "Ctrl+Q", tryQuit, fileMenu)

        # Edit:
        editMenu = self._menu.addMenu("Edit")
        addAction("Undo", "Ctrl+Z", lambda: ifNotSelecting(lambda: self.maskPanel.undo()), editMenu)
        addAction("Redo", "Ctrl+Shift+Z", lambda: ifNotSelecting(lambda: self.maskPanel.redo()), editMenu)
        addAction("Generate", "F4", lambda: ifNotSelecting(lambda: controller.startAndManageInpainting()), editMenu)


        # Image:
        imageMenu = self._menu.addMenu("Image")
        addAction("Resize canvas", "F2", lambda: ifNotSelecting(lambda: controller.resizeCanvas()), imageMenu)
        addAction("Scale image", "F3", lambda: ifNotSelecting(lambda: controller.scaleImage()), imageMenu)
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
        def sketchModeToggle():
            maskPanel.setSketchMode(not maskPanel.maskModeButton.isChecked())
        addAction("Toggle mask/sketch editing mode", "F6", lambda: ifNotSelecting(sketchModeToggle), toolMenu)
        def maskToolToggle():
            maskPanel.swapDrawTool()
        addAction("Toggle pen/eraser tool", "F7", lambda: ifNotSelecting(maskToolToggle), toolMenu)
        def clearBoth():
            mask.clear()
            sketch.clear()
        addAction("Clear mask and sketch", "F8", lambda: ifNotSelecting(clearBoth), toolMenu)
        def brushSizeChange(offset):
            size = maskPanel.getBrushSize()
            maskPanel.setBrushSize(size + offset)
        addAction("Increase brush size", "Ctrl+]", lambda: ifNotSelecting(lambda: brushSizeChange(1)), toolMenu)
        addAction("Decrease brush size", "Ctrl+[", lambda: ifNotSelecting(lambda: brushSizeChange(-1)), toolMenu)

        try:
            from data_model.canvas.brushlib import Brushlib
            def loadBrush():
                isPyinstallerBundle = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')
                options = QFileDialog.Option.DontUseNativeDialog if isPyinstallerBundle else None
                file, fileSelected = QFileDialog.getOpenFileName(self, 'Open Brush File', options)
                if fileSelected:
                    Brushlib.loadBrush(file)
            addAction("Load MyPaint Brush (.myb)", None, loadBrush, toolMenu)
        except ImportError:
            print("Skipping brush selection init, brushlib not loaded")

        self._settings = SettingsModal(self)
        if (controller.initSettings(self._settings)):
            self._settings.changesSaved.connect(lambda changes: controller.updateSettings(changes))
            def showSettings():
                controller.refreshSettings(self._settings)
                frame = self.frameGeometry()
                frame.setX(frame.x() + (frame.width() // 8))
                frame.setY(frame.y() + (frame.height() // 8))
                frame.setWidth(math.floor(self.width() * 0.75))
                frame.setHeight(math.floor(self.height() * 0.75))
                self._settings.setGeometry(frame)
                self._settings.showModal()
            addAction("Settings", "F9", lambda: ifNotSelecting(showSettings), toolMenu)

        # TODO: the following are specific to the A1111 stable-diffusion api and should move to 
        #       stable_diffusion_main_window.py:
        if hasattr(controller, '_webservice') and 'LCM' in config.getOptions('samplingMethod'):
            try:
                loras = [l['name'] for l in controller._webservice.getLoras()]
                if 'lcm-lora-sdv1-5' in loras:
                    def setLcmMode():
                        loraKey= '<lora:lcm-lora-sdv1-5:1>'
                        prompt = config.get("prompt")
                        if loraKey not in prompt:
                            config.set("prompt", f"{prompt} {loraKey}")
                        config.set('cfgScale', 1.5)
                        config.set('samplingSteps', 8)
                        config.set('samplingMethod', 'LCM')
                        config.set('seed', -1)
                        if config.get('batchSize') < 5:
                            config.set('batchSize', 5)
                        if self._editedImage.hasImage():
                            imageSize = self._editedImage.size()
                            if imageSize.width() < 1200 and imageSize.height() < 1200:
                                config.set('editSize', imageSize)
                            else:
                                size = QSize(min(imageSize.width(), 1024), min(imageSize.height(), 1024))
                                config.set('editSize', size)
                    addAction("LCM Mode", "F10", setLcmMode, toolMenu)
            except:
                print('Failed to check loras for lcm lora')

        # Build config + control layout (varying based on implementation): 
        self._buildControlLayout(controller)

    def shouldUseWideLayout(self):
        return self.height() <= (self.width() * 1.2)

    def _clearEditingLayout(self):
        if self.imageLayout is not None:
            for widget in [self.imagePanel, self.divider, self.maskPanel]:
                self.imageLayout.removeWidget(widget)
            self.layout.removeItem(self.imageLayout)
            self.imageLayout = None
            if self._scaleHandler is not None:
                self.divider.dragged.disconnect(self._scaleHandler)
                self._scaleHandler = None

    def setImageSlidersEnabled(self, slidersEnabled):
        self._slidersEnabled = slidersEnabled
        if not slidersEnabled and self.imagePanel.slidersShowing():
            self.imagePanel.showSliders(False)
        elif slidersEnabled and not self.imagePanel.slidersShowing() and self.shouldUseWideLayout():
            self.imagePanel.showSliders(True)

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
        self.imagePanel.showSliders(True and self._slidersEnabled)
        self.update()

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
        self.imagePanel.showSliders(False)
        self.update()



    def _setupCorrectLayout(self):
        if self.shouldUseWideLayout():
            if isinstance(self.imageLayout, QVBoxLayout) or self.imageLayout is None: 
                self._setupWideLayout()
        elif isinstance(self.imageLayout, QHBoxLayout) or self.imageLayout is None:
                self._setupTallLayout()

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

    def loadSamplePreview(self, image, idx):
        if self._sampleSelector is None:
            print(f"Tried to load sample {idx} after sampleSelector was closed")
        else:
            self._sampleSelector.loadSampleImage(image, idx)

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
