from PyQt5.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QGridLayout, QPushButton
import sys

from inpainting.ui.config_control_setup import *
from inpainting.ui.layout.layout_utils import BorderedWidget
from inpainting.ui.layout.collapsible_box import CollapsibleBox
from inpainting.ui.window.main_window import MainWindow
from inpainting.ui.param_slider import ParamSlider

class StableDiffusionMainWindow(MainWindow):
    def __init__(self, config, editedImage, mask, sketch, controller):
        super().__init__(config, editedImage, mask, sketch, controller)
        # Decrease imageLayout stretch to make room for additional controls:
        self.layout.setStretch(0, 180)

    def _buildControlLayout(self, controller):
        controlPanel = BorderedWidget(self)
        controlLayout = QVBoxLayout()
        controlPanel.setLayout(controlLayout)
        self.layout.addWidget(controlPanel, stretch=20)

        mainControlBox = CollapsibleBox("Controls", controlPanel)
        mainControls = QHBoxLayout();
        mainControlBox.setContentLayout(mainControls)
        controlLayout.addWidget(mainControlBox, stretch=20)

        # Left side: sliders and other wide inputs:
        wideOptions = BorderedWidget()
        mainControls.addWidget(wideOptions, stretch=50)
        wideOptionsLayout = QGridLayout()
        wideOptionsLayout.setVerticalSpacing(max(2, self.height() // 100))
        wideOptions.setLayout(wideOptionsLayout)
        # Font size will be used to limit the height of the prompt boxes:
        textboxHeight = self.font().pixelSize() * 3
        if textboxHeight < 0: #font uses pt, not px
            textboxHeight = self.font().pointSize() * 4

        # First line: prompt, batch size
        wideOptionsLayout.setRowStretch(0, 2)
        wideOptionsLayout.addWidget(QLabel("Prompt:"), 0, 0)
        textPromptBox = connectedTextEdit(controlPanel, self._config, 'prompt', multiLine=True)
        textPromptBox.setMaximumHeight(textboxHeight)
        wideOptionsLayout.addWidget(textPromptBox, 0, 1)
        # batch size:
        wideOptionsLayout.addWidget(QLabel("Batch size:"), 0, 2)
        batchSizeBox = connectedSpinBox(controlPanel, self._config, 'batchSize', maxKey='maxBatchSize')
        batchSizeBox.setRange(1, batchSizeBox.maximum())
        batchSizeBox.setToolTip("Inpainting images generated per batch")
        wideOptionsLayout.addWidget(batchSizeBox, 0, 3)

        # Second line: negative prompt, batch count:
        wideOptionsLayout.setRowStretch(1, 2)
        wideOptionsLayout.addWidget(QLabel('Negative:'), 1, 0)
        negativePromptBox = connectedTextEdit(controlPanel, self._config, 'negativePrompt', multiLine=True)
        negativePromptBox.setMaximumHeight(textboxHeight)
        wideOptionsLayout.addWidget(negativePromptBox, 1, 1)
        # batch count:
        wideOptionsLayout.addWidget(QLabel('Batch count:'), 1, 2)
        batchCountBox = connectedSpinBox(controlPanel, self._config, 'batchCount', maxKey='maxBatchCount')
        batchCountBox.setRange(1, batchCountBox.maximum())
        batchCountBox.setToolTip("Number of inpainting image batches to generate")
        wideOptionsLayout.addWidget(batchCountBox, 1, 3)

        # Misc. sliders:
        wideOptionsLayout.setRowStretch(2, 1)
        sampleStepSlider = ParamSlider(wideOptions, 'Sampling steps:', self._config, 'samplingSteps',
                'minSamplingSteps', 'maxSamplingSteps')
        wideOptionsLayout.addWidget(sampleStepSlider, 2, 0, 1, 4)
        wideOptionsLayout.setRowStretch(3, 1)
        cfgScaleSlider = ParamSlider(wideOptions, 'CFG scale:', self._config, 'cfgScale', 'minCfgScale', 'maxCfgScale',
                'cfgScaleStep')
        wideOptionsLayout.addWidget(cfgScaleSlider, 3, 0, 1, 4)
        wideOptionsLayout.setRowStretch(4, 1)
        denoisingSlider = ParamSlider(wideOptions, 'Denoising strength:', self._config, 'denoisingStrength',
                'minDenoisingStrength', 'maxDenoisingStrength', 'denoisingStrengthStep')
        wideOptionsLayout.addWidget(denoisingSlider, 4, 0, 1, 4)


        # Right side: box of dropdown/checkbox options:
        optionList = BorderedWidget()
        mainControls.addWidget(optionList, stretch=10)
        optionListLayout = QVBoxLayout()
        optionListLayout.setSpacing(max(2, self.height() // 100))
        optionList.setLayout(optionListLayout)
        def addOptionLine(labelText, widget, toolTip=None):
            optionLine = QHBoxLayout()
            optionListLayout.addLayout(optionLine)
            optionLine.addWidget(QLabel(labelText), stretch=1)
            if toolTip is not None:
                widget.setToolTip(toolTip)
            optionLine.addWidget(widget, stretch=2)

        def addComboBoxLine(labelText, configKey, inpaintingOnly, toolTip=None):
            comboBox = connectedComboBox(optionList, self._config, configKey)
            if inpaintingOnly:
                self._config.connect(comboBox, 'editMode', lambda newMode: comboBox.setEnabled(newMode == 'Inpaint'))
            addOptionLine(labelText, comboBox, toolTip)

        addComboBoxLine('Editing mode:', 'editMode', False)
        addComboBoxLine('Mask mode:', 'inpaintMasked', True)
        addComboBoxLine('Masked content:', 'maskedContent', True)
        addComboBoxLine('Sampling method:', 'samplingMethod', False)

        checkboxLine = QHBoxLayout()
        optionListLayout.addLayout(checkboxLine)
        checkboxLine.addWidget(QLabel('Restore faces:'))
        faceCheckBox = connectedCheckBox(optionList, self._config, 'restoreFaces')
        checkboxLine.addWidget(faceCheckBox)
        checkboxLine.addWidget(QLabel('Tiling:'))
        tilingCheckBox = connectedCheckBox(optionList, self._config, 'tiling')
        checkboxLine.addWidget(tilingCheckBox)

        seedInput = connectedSpinBox(optionList, self._config, 'seed')
        seedInput.setRange(-1, 2147483647)
        addOptionLine("Seed:", seedInput, "Controls image generation, use -1 to use a random value each time.")

        lastSeedBox = connectedTextEdit(optionList, self._config, 'lastSeed');
        lastSeedBox.setReadOnly(True)
        addOptionLine("Last Seed", lastSeedBox, "Seed used during the last inpainting action.")

        
        # Put action buttons on the bottom:
        buttonBar = BorderedWidget(controlPanel)
        buttonBarLayout = QHBoxLayout()
        buttonBar.setLayout(buttonBarLayout)
        controlLayout.addWidget(buttonBar, stretch=5)

        # interrogateButton:
        interrogateButton = QPushButton();
        interrogateButton.setText("Interrogate")
        interrogateButton.setToolTip("Attempt to generate a prompt that describes the current selection")
        interrogateButton.clicked.connect(lambda: print('TODO: implement interrogate request in controller'))
        buttonBarLayout.addWidget(interrogateButton, stretch=1)
        interrogateButton.resize(interrogateButton.width(), interrogateButton.height() * 2)
        # Start generation button:
        startButton = QPushButton();
        startButton.setText("Generate")
        startButton.clicked.connect(lambda: controller.startAndManageInpainting())
        buttonBarLayout.addWidget(startButton, stretch=2)
        startButton.resize(startButton.width(), startButton.height() * 2)




