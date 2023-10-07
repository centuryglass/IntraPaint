from PyQt5.QtWidgets import QWidget, QDialog, QSpinBox, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt5.QtCore import QSize
from ui.config_control_setup import connectedComboBox, connectedCheckBox, connectedSpinBox
from ui.widget.labeled_spinbox import LabeledSpinbox

class ImageScaleModal(QDialog):
    def __init__(self, defaultWidth, defaultHeight, config):
        super().__init__()

        self._create = False
        self.setModal(True)
        self._layout = QVBoxLayout()

        self._title = QLabel(self)
        self._title.setText("Scale image")
        self._layout.addWidget(self._title)

        minVal = 8
        maxVal = 20000
        self._widthBox = LabeledSpinbox(self, "Width:", "New image width in pixels", minVal, defaultWidth, maxVal)
        self._layout.addWidget(self._widthBox)
        self._heightBox = LabeledSpinbox(self, "Height:", "New image height in pixels", minVal, defaultHeight, maxVal)
        self._layout.addWidget(self._heightBox)
        self._xMultBox = LabeledSpinbox(self, "Width scale:", "New image width (as multiplier)", 0.0, 1.0, 999.0)
        self._layout.addWidget(self._xMultBox)
        self._yMultBox = LabeledSpinbox(self, "Height scale:", "New image height (as multiplier)", 0.0, 1.0, 999.0)
        self._layout.addWidget(self._yMultBox)
        self._upscaleMethodBox, self._upscaleLayout = connectedComboBox(self, config, 'upscaleMethod', text='Upscale Method:')
        self._layout.addLayout(self._upscaleLayout)

        # Synchronize scale boxes with pixel size boxes
        def setScaleOnPxChange(pixelSize, baseValue, scaleBox):
            scale = round(int(pixelSize) / baseValue, 2)
            print(f"{pixelSize} / {baseValue} = {scale}")
            if scaleBox.spinbox.value() != scale:
                scaleBox.spinbox.setValue(scale)

        def setPxOnScaleChange(scale, baseValue, pxBox):
            pixelSize = int(baseValue * float(scale))
            print(f"{baseValue} * {scale} = {pixelSize}")
            if pxBox.spinbox.value() != pixelSize:
                pxBox.spinbox.setValue(pixelSize)

        self._widthBox.spinbox.valueChanged.connect(lambda px: setScaleOnPxChange(px, defaultWidth, self._xMultBox))
        self._xMultBox.spinbox.valueChanged.connect(lambda px: setPxOnScaleChange(px, defaultWidth, self._widthBox))
        self._heightBox.spinbox.valueChanged.connect(lambda px: setScaleOnPxChange(px, defaultHeight, self._yMultBox))
        self._yMultBox.spinbox.valueChanged.connect(lambda px: setPxOnScaleChange(px, defaultHeight, self._heightBox))

        # Add controlnet upscale option:
        if config.get('controlnetVersion') > 0:
            self._controlnetCheckbox = connectedCheckBox(self, config, 'controlnetUpscaling', text='Use ControlNet Tiles')
            self._controlnetRateBox = connectedSpinBox(
                    self,
                    config,
                    'controlnetDownsampleRate',
                    'controlnetDownsampleMin',
                    'controlnetDownsampleMax',
                    'controlnetDownsampleSteps')
            self._controlnetRateBox.setEnabled(config.get('controlnetUpscaling'))
            self._controlnetCheckbox.stateChanged.connect(lambda enabled: self._controlnetRateBox.setEnabled(enabled))
            self._layout.addWidget(self._controlnetCheckbox)
            self._layout.addWidget(self._controlnetRateBox)

        self._createButton = QPushButton(self)
        self._createButton.setText("Scale image")
        self._layout.addWidget(self._createButton)
        def onCreate():
            config.disconnect(self._upscaleMethodBox, 'upscaleMethod')
            self._create = True
            self.hide()
        self._createButton.clicked.connect(onCreate)

        self._cancelButton = QPushButton(self)
        self._cancelButton.setText("Cancel")
        def onCancel():
            config.disconnect(self._upscaleMethodBox, 'upscaleMethod')
            self._create = False
            self.hide()
        self._cancelButton.clicked.connect(onCancel)
        self._layout.addWidget(self._cancelButton)
        
        self.setLayout(self._layout)

    def showImageModal(self):
        self.exec_()
        if self._create:
            return QSize(self._widthBox.spinbox.value(), self._heightBox.spinbox.value())
