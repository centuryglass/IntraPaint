from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QPoint, QRect, QBuffer
import PyQt5.QtGui as QtGui
from PyQt5.QtGui import QPainter, QPen
from PyQt5.QtCore import Qt
from PIL import Image
from edit_ui.mask_creator import MaskCreator

class MaskPanel(QWidget):
    def __init__(self, pilImage, getSelection, selectionChangeSignal):
        super().__init__()
        assert pilImage is None or isinstance(pilImage, Image.Image)
        assert callable(getSelection)
        assert hasattr(selectionChangeSignal, 'connect') and callable(selectionChangeSignal.connect)

        self.maskCreator = MaskCreator(pilImage)

        maskCreator = self.maskCreator
        def applySelection(pt, size):
            if size is not None:
                maskCreator.setSelectionSize(size)
            selection = getSelection()
            if selection is not None:
                maskCreator.loadImage(selection)
            maskCreator.update()
        selectionChangeSignal.connect(applySelection)

        self._maskBrushSize = maskCreator.getBrushSize()
        self._sketchBrushSize = 5

        self.brushSizeBox = QSpinBox(self)
        self.brushSizeBox.setToolTip("Brush size")
        self.brushSizeBox.setRange(1, 200)
        self.brushSizeBox.setValue(maskCreator.getBrushSize())
        def setBrush(newSize):
            if self.maskModeButton.isChecked():
                self._maskBrushSize = newSize
            else:
                self._sketchBrushSize = newSize
            maskCreator.setBrushSize(newSize)
        self.brushSizeBox.valueChanged.connect(setBrush)

        self.eraserCheckbox = QCheckBox(self)
        self.eraserCheckbox.setText("Use eraser")
        self.eraserCheckbox.setChecked(False)
        def toggleEraser():
            self.maskCreator.setUseEraser(self.eraserCheckbox.isChecked())
        self.eraserCheckbox.stateChanged.connect(toggleEraser)

        self.clearMaskButton = QPushButton(self)
        self.clearMaskButton.setText("clear")
        def clearMask():
            self.maskCreator.clear()
            self.eraserCheckbox.setChecked(False)
        self.clearMaskButton.clicked.connect(clearMask)

        self.maskModeButton = QRadioButton(self)
        self.sketchModeButton = QRadioButton(self)
        self.maskModeButton.setText("Draw mask")
        self.sketchModeButton.setText("Draw sketch")
        self.maskModeButton.setToolTip("Draw over the area to be inpainted")
        self.sketchModeButton.setToolTip("Add simple details to help guide inpainting")
        self.maskModeButton.setChecked(True)
        def setMaskMode(maskMode):
            self.maskCreator.setSketchMode(not maskMode)
            self.colorPickerButton.setVisible(not maskMode)
            self.brushSizeBox.setValue(self._maskBrushSize if maskMode else self._sketchBrushSize)
            self.update()
        self.maskModeButton.toggled.connect(setMaskMode)

        self.colorPickerButton = QPushButton(self)
        self.colorPickerButton.setText("Select sketch color")
        def getColor():
            color = QColorDialog.getColor()
            self.maskCreator.setSketchColor(color)
            self.update()
        self.colorPickerButton.clicked.connect(getColor)
        self.colorPickerButton.setVisible(False)

        self.keepSketchCheckbox = QCheckBox(self)
        self.keepSketchCheckbox.setText("Save in results")
        self.keepSketchCheckbox.setToolTip("Set whether parts of the sketch not covered by the mask should appear in generated images")

        

        self.layout = QGridLayout()
        self.borderSize = 4
        def makeSpacer():
            return QSpacerItem(self.borderSize, self.borderSize)
        self.layout.addItem(makeSpacer(), 0, 0, 1, 1)
        self.layout.addItem(makeSpacer(), 3, 0, 1, 1)
        self.layout.addItem(makeSpacer(), 0, 0, 1, 1)
        self.layout.addItem(makeSpacer(), 0, 6, 1, 1)
        self.layout.addWidget(self.maskCreator, 1, 1, 1, 6)
        self.layout.addWidget(QLabel(self, text="Brush size:"), 2, 1, 1, 1)
        self.layout.addWidget(self.brushSizeBox, 2, 2, 1, 1)
        self.layout.addWidget(self.clearMaskButton, 2, 3, 1, 2)
        self.layout.addWidget(self.maskModeButton, 3, 1, 1, 1)
        self.layout.addWidget(self.keepSketchCheckbox, 3, 2, 1, 1)
        self.layout.addWidget(self.eraserCheckbox, 3, 3, 1, 1)
        self.layout.addWidget(self.sketchModeButton, 4, 1, 1, 1)
        self.layout.addWidget(self.colorPickerButton, 4, 2, 1, 1)
        self.layout.setRowMinimumHeight(1, 250)
        self.setLayout(self.layout)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(Qt.black, self.borderSize//2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawRect(1, 1, self.width() - 2, self.height() - 2)
        if not self.colorPickerButton.isHidden():
            painter.setPen(QPen(self.maskCreator.getSketchColor(), self.borderSize//2, Qt.SolidLine, Qt.RoundCap,
                        Qt.RoundJoin))
            painter.drawRect(self.colorPickerButton.geometry())

    def loadImage(self, im):
        self.maskCreator.loadImage(im)

    def getMask(self):
        return self.maskCreator.getMask()

    def resizeEvent(self, event):
        # Force MaskCreator aspect ratio to match edit sizes, while leaving room for controls:
        creatorWidth = self.maskCreator.width()
        creatorHeight = creatorWidth
        if self.maskCreator.selectionWidth() > 0:
            creatorHeight = creatorWidth * self.maskCreator.selectionHeight() // self.maskCreator.selectionWidth()
        maxHeight = self.clearMaskButton.y() - self.borderSize
        if creatorHeight > maxHeight:
            creatorHeight = maxHeight
            if self.maskCreator.selectionHeight() > 0:
                creatorWidth = creatorHeight * self.maskCreator.selectionWidth() // self.maskCreator.selectionHeight()
        if creatorHeight != self.maskCreator.height() or creatorWidth != self.maskCreator.width():
            x = (self.width() - self.borderSize - creatorWidth) // 2
            y = self.borderSize + (maxHeight - creatorHeight) // 2
            self.maskCreator.setGeometry(x, y, creatorWidth, creatorHeight)
