from PyQt5.QtWidgets import (QWidget, QLabel, QSpinBox, QCheckBox, QPushButton, QRadioButton, QButtonGroup,
        QColorDialog, QGridLayout, QSpacerItem)
from PyQt5.QtCore import Qt, QPoint, QRect, QSize, QBuffer
from PyQt5.QtGui import QPainter, QPen, QCursor, QPixmap, QBitmap
from PyQt5.QtCore import Qt
from PIL import Image

from inpainting.ui.mask_creator import MaskCreator
from inpainting.ui.util.get_scaled_placement import getScaledPlacement

class MaskPanel(QWidget):
    def __init__(self, config, maskCanvas, sketchCanvas, editedImage):
        super().__init__()

        self.maskCreator = MaskCreator(self, maskCanvas, sketchCanvas, editedImage)
        self._maskCanvas = maskCanvas
        self._sketchCanvas = sketchCanvas

        self._maskBrushSize = maskCanvas.brushSize()
        self._sketchBrushSize = sketchCanvas.brushSize()
        self._editedImage = editedImage

        self._cursorPixmap = QPixmap('./resources/cursor.png')
        smallCursorPixmap = QPixmap('./resources/minCursor.png')
        self._smallCursor = QCursor(smallCursorPixmap)
        self._lastCursorSize = None

        self.brushSizeBox = QSpinBox(self)
        self.brushSizeBox.setToolTip("Brush size")
        self.brushSizeBox.setRange(1, 200)
        def updateBrushSize(newSize):
            if self.maskModeButton.isChecked():
                self._maskBrushSize = newSize
                maskCanvas.setBrushSize(newSize)
            else:
                self._sketchBrushSize = newSize
                sketchCanvas.setBrushSize(newSize)
            self._updateBrushCursor()
        self.brushSizeBox.valueChanged.connect(updateBrushSize)
        editedImage.selectionChanged.connect(lambda: self.resizeEvent(None))

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
            self.resizeEvent(None)
        sketchCanvas.onEnabledChange.connect(handleSketchModeEnabledChange)

        def handleMaskModeEnabledChange(isEnabled):
            self.maskModeButton.setEnabled(isEnabled)
            if not isEnabled and self._sketchCanvas.enabled() and not self.maskModeButton.isChecked() :
                self.sketchModeButton.toggle()
            elif isEnabled and not self.maskModeButton.isChecked():
                self.maskModeButton.toggle()
            self.setEnabled(isEnabled or self._sketchCanvas.enabled())
            self.resizeEvent(None)
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
        self.layout.addItem(QSpacerItem(self.borderSize, self.borderSize), 0, 0)
        self.layout.addWidget(QLabel(self, text="Brush size:"), 1, 0)
        self.layout.addWidget(self.brushSizeBox, 1, 1)
        self.layout.addWidget(self.penButton, 2, 0)
        self.layout.addWidget(self.eraserButton, 2, 1)
        self.layout.addWidget(self.clearMaskButton, 3, 0)
        self.layout.addWidget(self.fillMaskButton, 3, 1)
        self.layout.addWidget(self.maskModeButton, 4, 0)
        self.layout.addWidget(self.sketchModeButton, 4, 1)
        self.layout.addWidget(self.colorPickerButton, 5, 0)
        self.layout.addWidget(self.keepSketchCheckbox, 5, 1)
        self.layout.setRowStretch(0, 255)
        self.setLayout(self.layout)

        self.brushSizeBox.setValue(self._maskBrushSize)

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
        self.resizeEvent(None)
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
        componentBounds = QRect(0, 0, self.width(), self.height())
        componentBounds.setBottom(self.brushSizeBox.y())
        maskCreatorBounds = getScaledPlacement(componentBounds, selectionSize, 4)
        self.maskCreator.setGeometry(maskCreatorBounds)
        self._updateBrushCursor()

    def _updateBrushCursor(self):
        brushSize = self._maskBrushSize if self.maskModeButton.isChecked() else self._sketchBrushSize
        canvasWidth = max(self._editedImage.getSelectionBounds().width(), 1)
        widgetWidth = max(self.maskCreator.width(), 1)
        scaledSize = max(int(widgetWidth * brushSize / canvasWidth), 9)
        if scaledSize == self._lastCursorSize:
            return
        if scaledSize <= 10:
            self.maskCreator.setCursor(self._smallCursor)
        else:
            newCursor = QCursor(self._cursorPixmap.scaled(QSize(scaledSize, scaledSize)))
            self.maskCreator.setCursor(newCursor)
        self._lastCursorSize = scaledSize
