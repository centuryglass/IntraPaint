from PyQt5.QtWidgets import (QWidget, QLabel, QSpinBox, QCheckBox, QPushButton, QRadioButton, QButtonGroup,
        QColorDialog, QGridLayout, QSpacerItem)
from PyQt5.QtCore import Qt, QPoint, QRect, QSize, QBuffer, QEvent
from PyQt5.QtGui import QPainter, QPen, QCursor, QPixmap, QBitmap, QIcon
from PIL import Image

from ui.mask_creator import MaskCreator
from ui.util.get_scaled_placement import getScaledPlacement
from ui.config_control_setup import connectedCheckBox
from ui.util.equal_margins import getEqualMargins
import os, sys

class MaskPanel(QWidget):
    def __init__(self, config, maskCanvas, sketchCanvas, editedImage):
        super().__init__()

        def setSketchColor(newColor):
            self.maskCreator.setSketchColor(newColor)
            self.update()
        self.maskCreator = MaskCreator(self, maskCanvas, sketchCanvas, editedImage, setSketchColor)
        self.maskCreator.setMinimumSize(QSize(256, 256))
        self._maskCanvas = maskCanvas
        self._sketchCanvas = sketchCanvas

        self._maskBrushSize = maskCanvas.brushSize()
        self._sketchBrushSize = sketchCanvas.brushSize()
        self._editedImage = editedImage

        self._cursorPixmap = QPixmap('./resources/cursor.png')
        smallCursorPixmap = QPixmap('./resources/minCursor.png')
        self._smallCursor = QCursor(smallCursorPixmap)
        eyedropperIcon = QPixmap('./resources/eyedropper.png')
        self._eyedropperCursor = QCursor(eyedropperIcon, hotX=0, hotY=eyedropperIcon.height())
        self._eyedropperMode = False
        self._lastCursorSize = None
        self._config = config

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
        self.penButton.setIcon(QIcon(QPixmap('./resources/pen.png')))
        self.drawToolGroup.addButton(self.penButton)

        self.eraserButton = QCheckBox(self)
        self.eraserButton.setText("Eraser")
        self.eraserButton.setIcon(QIcon(QPixmap('./resources/eraser.png')))
        self.drawToolGroup.addButton(self.eraserButton)
        self.penButton.toggle()
        def toggleEraser():
            self.maskCreator.setUseEraser(self.eraserButton.isChecked())
        self.eraserButton.toggled.connect(toggleEraser)

        self.clearMaskButton = QPushButton(self)
        self.clearMaskButton.setText("clear")
        self.clearMaskButton.setIcon(QIcon(QPixmap('./resources/clear.png')))
        def clearMask():
            self.maskCreator.clear()
            self.eraserButton.setChecked(False)
        self.clearMaskButton.clicked.connect(clearMask)

        self.fillMaskButton = QPushButton(self)
        self.fillMaskButton.setText("fill")
        self.fillMaskButton.setIcon(QIcon(QPixmap('./resources/fill.png')))
        def fillMask():
            self.maskCreator.fill()
        self.fillMaskButton.clicked.connect(fillMask)

        self.maskModeButton = QRadioButton(self)
        self.sketchModeButton = QRadioButton(self)
        self.maskModeButton.setText("Mask")
        self.maskModeButton.setIcon(QIcon(QPixmap('./resources/mask.png')))
        self.sketchModeButton.setText("Sketch")
        self.sketchModeButton.setIcon(QIcon(QPixmap('./resources/sketch.png')))
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
        self.colorPickerButton.clicked.connect(lambda: setSketchColor(QColorDialog.getColor()))
        self.colorPickerButton.setVisible(False)

        self.keepSketchCheckbox = connectedCheckBox(self, config, 'saveSketchInResult', "Apply sketch", 
                "Set whether parts of the sketch not covered by the mask should appear in generated images")

        self.layout = QGridLayout()
        self.borderSize = 4
        self.brushLabel = QLabel(self, text="Brush size:")
        self.layout.setContentsMargins(getEqualMargins(self.borderSize))
        self.maskCreator.setContentsMargins(getEqualMargins(0))
        self.setLayout(self.layout)
        self._layoutType = ""
        self._setupCorrectLayout()

        self.brushSizeBox.setValue(self._maskBrushSize)

    def _clearControlLayout(self):
        widgets = [ 
            self.maskCreator,
            self.brushLabel,
            self.brushSizeBox,
            self.penButton,
            self.eraserButton,
            self.clearMaskButton,
            self.fillMaskButton,
            self.maskModeButton,
            self.sketchModeButton,
            self.colorPickerButton,
            self.keepSketchCheckbox
        ]
        if hasattr(self, 'pressureSizeCheckbox'):
            widgets.append(self.pressureSizeCheckbox)
            widgets.append(self.pressureOpacityCheckbox)
        for widget in widgets:
            if self.layout.indexOf(widget) != -1:
                self.layout.removeWidget(widget)


    def _setupWideLayout(self):
        self._clearControlLayout()
        row = 0
        self.layout.addWidget(self.penButton, 1, 1, 1, 12)
        self.layout.addWidget(self.eraserButton, 2, 1, 1, 2)
        self.layout.addWidget(self.maskModeButton, 3, 1, 1, 2)
        self.layout.addWidget(self.sketchModeButton, 4, 1, 1, 2)
        row = 5
        if hasattr(self, 'pressureSizeCheckbox'):
            self.layout.addWidget(self.pressureSizeCheckbox, 5, 1, 1, 2)
            self.layout.addWidget(self.pressureOpacityCheckbox, 6, 1, 1, 2)
            row = 7
        self.layout.addWidget(self.brushLabel, row, 1)
        self.layout.addWidget(self.brushSizeBox, row, 2)
        row += 1
        self.layout.addWidget(self.keepSketchCheckbox, row, 1)
        self.layout.addWidget(self.colorPickerButton, row, 2)
        row += 1
        self.layout.addWidget(self.fillMaskButton, row, 1)
        self.layout.addWidget(self.clearMaskButton, row, 2, 1, 2)
        self.layout.addWidget(self.maskCreator, 0, 0, self.layout.rowCount(), 1)
        self.layout.setColumnStretch(0, 255)
        for i in range(self.layout.rowCount()):
            self.layout.setRowStretch(i, 10)
        self.layout.setVerticalSpacing(3 * self.borderSize)
        self.layout.setHorizontalSpacing(self.borderSize)
        self._layoutType = "WIDE"

    def _setupTallLayout(self):
        self._clearControlLayout()
        self.layout.addWidget(self.penButton, 1, 1)
        self.layout.addWidget(self.eraserButton, 2, 1)
        self.layout.addWidget(self.maskModeButton, 1, 2)
        self.layout.addWidget(self.sketchModeButton, 2, 2)
        for i in range(1, 4):
            self.layout.setColumnStretch(i, 10)
        brushSizeRow=3
        if hasattr(self, 'pressureSizeCheckbox'):
            self.layout.addWidget(self.pressureSizeCheckbox, 1, 3)
            self.layout.addWidget(self.pressureOpacityCheckbox, 2, 3)
        else:
            self.layout.setColumnStretch(3, 0)
        self.layout.addWidget(self.brushLabel, 4, 1)
        self.layout.addWidget(self.brushSizeBox, 4, 2, 1, 2)
        self.layout.addWidget(self.keepSketchCheckbox, 5, 1)
        self.layout.addWidget(self.colorPickerButton, 5, 2, 1, 2)
        self.layout.addWidget(self.clearMaskButton, 6, 1)
        self.layout.addWidget(self.fillMaskButton, 6, 2)
        self.layout.setRowStretch(0, 255)
        self.layout.setColumnStretch(0, 0)
        self.layout.addWidget(self.maskCreator, 0, 1, 1, self.layout.columnCount() - 1)
        for i in range(7, self.layout.rowCount()):
            self.layout.setRowStretch(i, 0)
        self.layout.setVerticalSpacing(self.borderSize)
        self.layout.setHorizontalSpacing(self.borderSize)
        self._layoutType = "TALL"

    def _setupCorrectLayout(self):
        minControlWidth = self.penButton.minimumSizeHint().width() + self.maskModeButton.minimumSizeHint().width()
        if hasattr(self, 'pressureSizeCheckbox'):
            minControlWidth = minControlWidth + self.pressureSizeCheckbox.minimumWidth()
        canvasWidgetWidth = self.maskCreator.getImageDisplaySize().width()
        if self._editedImage.hasImage():
            canvasWidgetWidth = max(canvasWidgetWidth, self._editedImage.getSelectionBounds().width())
        else:
            canvasWidgetWidth = max(canvasWidgetWidth, 512)
        if (canvasWidgetWidth + minControlWidth + self.borderSize) < self.width():
            if self._layoutType != "WIDE":
                self._setupWideLayout()
        else:
            if self._layoutType != "TALL":
                self._setupTallLayout()
        self._updateBrushCursor()

    def tabletEvent(self, tabletEvent):
        """Enable tablet controls on first tablet event"""
        if not hasattr(self, 'pressureSizeCheckbox'):
            config = self._config
            self.pressureSizeCheckbox = connectedCheckBox(self, config, 'pressureSize', 'size',
                    'Tablet pen pressure affects line width')
            self.pressureSizeCheckbox.setIcon(QIcon(QPixmap('./resources/pressureSize.png')))
            config.connect(self, 'pressureSize', lambda enabled: self.maskCreator.setPressureSizeMode(enabled))
            self.maskCreator.setPressureSizeMode(config.get('pressureSize'))

            self.pressureOpacityCheckbox = connectedCheckBox(self, config, 'pressureOpacity', 'opacity',
                    'Tablet pen pressure affects color opacity (sketch mode only)')
            config.connect(self, 'pressureOpacity', lambda enabled: self.maskCreator.setPressureOpacityMode(enabled))
            self.pressureOpacityCheckbox.setIcon(QIcon(QPixmap('./resources/pressureOpacity.png')))
            self.maskCreator.setPressureOpacityMode(config.get('pressureOpacity'))
            self._layoutType = ""
            self._setupCorrectLayout()

    def setUseMaskMode(self, useMaskMode):
        if useMaskMode and not self._maskCanvas.enabled():
            raise Exception("called setUseMaskMode(True) when mask mode is disabled")
        if not useMaskMode and not self._sketchCanvas.enabled():
            raise Exception("called setUseMaskMode(False) when sketch mode is disabled")
        if useMaskMode:
            self.maskModeButton.setChecked(True)
        else:
            self.sketchModeButton.setChecked(True)
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
        self._setupCorrectLayout()
        self._updateBrushCursor()

    def eventFilter(self, source, event):
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Control and not self.maskModeButton.isChecked():
                self._eyedropperMode = True
                self.maskCreator.setEyedropperMode(True)
                self.maskCreator.setLineMode(False)
                self.maskCreator.setCursor(self._eyedropperCursor)
            elif event.key() == Qt.Key_Shift:
                self.maskCreator.setLineMode(True)
        elif event.type() == QEvent.KeyRelease:
            if event.key() == Qt.Key_Control and self._eyedropperMode:
                self._eyedropperMode = False
                self.maskCreator.setEyedropperMode(False)
                self._lastCursorSize = None
                self._updateBrushCursor()
            elif event.key() == Qt.Key_Shift:
                self.maskCreator.setLineMode(False)
        return False

    def getBrushSize(self):
        return self._maskBrushSize if self.maskModeButton.isChecked() else self._sketchBrushSize

    def setBrushSize(self, newSize):
        self.brushSizeBox.setValue(newSize)

    def selectPenTool(self):
        self.penButton.setChecked(True)

    def selectEraserTool(self):
        self.eraserButton.setChecked(True)

    def swapDrawTool(self):
        if self.penButton.isChecked():
            self.eraserButton.setChecked(True)
        else:
            self.penButton.setChecked(True)

    def _updateBrushCursor(self):
        brushSize = self.getBrushSize()
        canvasWidth = max(self._editedImage.getSelectionBounds().width(), 1)
        widgetWidth = max(self.maskCreator.getImageDisplaySize().width(), 1)
        scaledSize = max(int(widgetWidth * brushSize / canvasWidth), 9)
        if scaledSize == self._lastCursorSize:
            return
        if scaledSize <= 10:
            self.maskCreator.setCursor(self._smallCursor)
        else:
            newCursor = QCursor(self._cursorPixmap.scaled(QSize(scaledSize, scaledSize)))
            self.maskCreator.setCursor(newCursor)
        self._lastCursorSize = scaledSize
