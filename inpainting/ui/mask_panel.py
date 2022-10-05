from PyQt5.QtWidgets import (QWidget,
        QLabel,
        QSpinBox,
        QCheckBox,
        QPushButton,
        QRadioButton,
        QButtonGroup,
        QColorDialog,
        QGridLayout,
        QSpacerItem)
from PyQt5.QtCore import Qt, QPoint, QRect, QBuffer
import PyQt5.QtGui as QtGui
from PyQt5.QtGui import QPainter, QPen
from PyQt5.QtCore import Qt
from PIL import Image
from inpainting.ui.mask_creator import MaskCreator

class MaskPanel(QWidget):
    def __init__(self, config, maskCanvas, sketchCanvas, editedImage):
        super().__init__()

        self.maskCreator = MaskCreator(maskCanvas, sketchCanvas, editedImage)
        self._maskCanvas = maskCanvas
        self._sketchCanvas = sketchCanvas

        self._maskBrushSize = maskCanvas.brushSize()
        self._sketchBrushSize = sketchCanvas.brushSize()
        self._editedImage = editedImage

        self.brushSizeBox = QSpinBox(self)
        self.brushSizeBox.setToolTip("Brush size")
        self.brushSizeBox.setRange(1, 200)
        self.brushSizeBox.setValue(self._maskBrushSize)
        def setBrush(newSize):
            if self.maskModeButton.isChecked():
                self._maskBrushSize = newSize
                maskCanvas.setBrushSize(newSize)
            else:
                self._sketchBrushSize = newSize
                sketchCanvas.setBrushSize(newSize)
        self.brushSizeBox.valueChanged.connect(setBrush)

        self.drawToolGroup = QButtonGroup()
        self.penButton = QRadioButton(self)
        self.penButton.setText("Pen")
        self.drawToolGroup.addButton(self.penButton)
        self.eraserButton = QCheckBox(self)
        self.eraserButton.setText("Eraser")
        self.drawToolGroup.addButton(self.eraserButton)
        self.penButton.toggle()
        def toggleEraser():
            self.maskCreator.setUseEraser(self.eraserButton.isChecked())
        self.eraserButton.toggled.connect(toggleEraser)

        self.clearMaskButton = QPushButton(self)
        self.clearMaskButton.setText("clear")
        def clearMask():
            self.maskCreator.clear()
            self.eraserButton.setChecked(False)
        self.clearMaskButton.clicked.connect(clearMask)

        self.fillMaskButton = QPushButton(self)
        self.fillMaskButton.setText("fill")
        def fillMask():
            self.maskCreator.fill()
        self.fillMaskButton.clicked.connect(fillMask)

        self.maskModeButton = QRadioButton(self)
        self.sketchModeButton = QRadioButton(self)
        self.maskModeButton.setText("Draw mask")
        self.sketchModeButton.setText("Draw sketch")
        self.maskModeButton.setToolTip("Draw over the area to be inpainted")
        self.sketchModeButton.setToolTip("Add simple details to help guide inpainting")
        self.maskModeButton.toggle()
        self.maskModeButton.toggled.connect(lambda isChecked: self.setUseMaskMode(isChecked))

        # Enable/disable controls as appropriate when sketch or mask mode are enabled or disabled:
        def handleSketchModeEnabledChange(isEnabled):
            self.sketchModeButton.setEnabled(isEnabled)
            if not isEnabled and self._maskCanvas.enabled() and not self.maskModeButton.isChecked():
                self.maskModeButton.toggle()
            elif isEnabled and not self._maskCanvas.enabled() and not self.sketchModeButton.isChecked():
                self.sketchModeButton.toggle()
            self.setEnabled(isEnabled or self._maskCanvas.enabled())
        sketchCanvas.onEnabledChange.connect(handleSketchModeEnabledChange)

        def handleMaskModeEnabledChange(isEnabled):
            self.maskModeButton.setEnabled(isEnabled)
            if not isEnabled and self._sketchCanvas.enabled() and not self.maskModeButton.isChecked() :
                self.sketchModeButton.toggle()
            elif isEnabled and not self.maskModeButton.isChecked():
                self.maskModeButton.toggle()
            self.setEnabled(isEnabled or self._sketchCanvas.enabled())
        maskCanvas.onEnabledChange.connect(handleMaskModeEnabledChange)

        self.colorPickerButton = QPushButton(self)
        self.colorPickerButton.setText("Select sketch color")
        def getColor():
            color = QColorDialog.getColor()
            self.maskCreator.setSketchColor(color)
            self.update()
        self.colorPickerButton.clicked.connect(getColor)
        self.colorPickerButton.setVisible(False)

        self.keepSketchCheckbox = QCheckBox(self)
        self.keepSketchCheckbox.setText("Apply sketch")
        self.keepSketchCheckbox.setToolTip("Set whether parts of the sketch not covered by the mask should appear in generated images")
        self.keepSketchCheckbox.setChecked(config.get('saveSketchInResult'))
        self.keepSketchCheckbox.toggled.connect(lambda isChecked: config.set('saveSketchInResult', isChecked))

        self.layout = QGridLayout()
        self.borderSize = 4
        def makeSpacer():
            return QSpacerItem(self.borderSize, self.borderSize)
        self.layout.addItem(makeSpacer(), 0, 0, 1, 1)
        self.layout.addItem(makeSpacer(), 3, 0, 1, 1)
        self.layout.addItem(makeSpacer(), 0, 0, 1, 1)
        self.layout.addItem(makeSpacer(), 0, 6, 1, 1)
        self.layout.addWidget(self.maskCreator, 1, 1)
        self.layout.addWidget(QLabel(self, text="Brush size:"), 2, 0)
        self.layout.addWidget(self.brushSizeBox, 2, 1)
        self.layout.addWidget(self.penButton, 3, 0)
        self.layout.addWidget(self.eraserButton, 3, 1)
        self.layout.addWidget(self.clearMaskButton, 4, 0)
        self.layout.addWidget(self.fillMaskButton, 4, 1)
        self.layout.addWidget(self.maskModeButton, 5, 0)
        self.layout.addWidget(self.sketchModeButton, 5, 1)
        self.layout.addWidget(self.colorPickerButton, 6, 0)
        self.layout.addWidget(self.keepSketchCheckbox, 6, 1)
        self.layout.setRowMinimumHeight(1, 250)
        self.setLayout(self.layout)

    def setUseMaskMode(self, useMaskMode):
        if useMaskMode and not self._maskCanvas.enabled():
            raise Exception("called setUseMaskMode(True) when mask mode is disabled")
        if not useMaskMode and not self._sketchCanvas.enabled():
            raise Exception("called setUseMaskMode(False) when sketch mode is disabled")
        if self.maskModeButton.isChecked() != useMaskMode:
            self.maskModeButton.toggle()
        self.maskCreator.setSketchMode(not useMaskMode)
        self.colorPickerButton.setVisible(not useMaskMode)
        self.brushSizeBox.setValue(self._maskBrushSize if useMaskMode else self._sketchBrushSize)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(Qt.black, self.borderSize//2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawRect(1, 1, self.width() - 2, self.height() - 2)
        if not self.colorPickerButton.isHidden():
            painter.setPen(QPen(self.maskCreator.getSketchColor(), self.borderSize//2, Qt.SolidLine, Qt.RoundCap,
                        Qt.RoundJoin))
            painter.drawRect(self.colorPickerButton.geometry())


    def resizeEvent(self, event):
        # Force MaskCreator aspect ratio to match edit sizes, while leaving room for controls:
        selectionSize = self._editedImage.getSelectionBounds().size()
        creatorWidth = self.maskCreator.width()
        creatorHeight = creatorWidth
        if selectionSize.width() > 0:
            creatorHeight = creatorWidth * selectionSize.height() // selectionSize.width()
        maxHeight = self.brushSizeBox.y() - self.borderSize
        if creatorHeight > maxHeight:
            creatorHeight = maxHeight
            if self._maskCanvas.size().height() > 0:
                creatorWidth = creatorHeight * selectionSize.width() // selectionSize.height()
        if creatorHeight != self.maskCreator.height() or creatorWidth != self.maskCreator.width():
            x = (self.width() - self.borderSize - creatorWidth) // 2
            y = self.borderSize + (maxHeight - creatorHeight) // 2
            self.maskCreator.setGeometry(x, y, creatorWidth, creatorHeight)
