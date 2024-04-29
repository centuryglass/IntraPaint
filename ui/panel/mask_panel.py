from PyQt5.QtWidgets import (QWidget, QLabel, QSpinBox, QCheckBox, QPushButton, QRadioButton,
        QColorDialog, QGridLayout, QSpacerItem)
from PyQt5.QtCore import Qt, QPoint, QRect, QSize, QBuffer, QEvent
from PyQt5.QtGui import QPainter, QPen, QCursor, QPixmap, QBitmap, QIcon
from PIL import Image

from ui.mask_creator import MaskCreator
from ui.util.get_scaled_placement import getScaledPlacement
from ui.config_control_setup import connectedCheckBox
from ui.util.equal_margins import getEqualMargins
from ui.util.contrast_color import contrastColor
from ui.widget.dual_toggle import DualToggle
from ui.widget.param_slider import ParamSlider
import os, sys

class DRAW_MODES:
    MASK = "Mask"
    SKETCH = "Sketch"
    def isValid(option):
        return option == DRAW_MODES.MASK or option == DRAW_MODES.SKETCH or option is None

class TOOL_MODES:
    PEN = "Pen"
    ERASER = "Eraser"
    def isValid(option):
        return option == TOOL_MODES.PEN or option == TOOL_MODES.ERASER or option is None

class MaskPanel(QWidget):
    def __init__(self, config, maskCanvas, sketchCanvas, editedImage):
        super().__init__()

        self._cursorPixmap = QPixmap('./resources/cursor.png')
        smallCursorPixmap = QPixmap('./resources/minCursor.png')
        self._smallCursor = QCursor(smallCursorPixmap)
        eyedropperIcon = QPixmap('./resources/eyedropper.png')
        self._eyedropperCursor = QCursor(eyedropperIcon, hotX=0, hotY=eyedropperIcon.height())
        self._eyedropperMode = False
        self._lastCursorSize = None
        self._config = config
        self._drawMode = None

        def setSketchColor(newColor):
            self.maskCreator.setSketchColor(newColor)
            if hasattr(self, 'colorPickerButton'):
                icon = QPixmap(QSize(64, 64))
                icon.fill(newColor)
                self.colorPickerButton.setIcon(QIcon(icon))
            self.update()
        self.maskCreator = MaskCreator(self, maskCanvas, sketchCanvas, editedImage, config, setSketchColor)
        self.maskCreator.setMinimumSize(QSize(256, 256))
        self._maskCanvas = maskCanvas
        self._sketchCanvas = sketchCanvas

        self._maskBrushSize = maskCanvas.brushSize()
        self._sketchBrushSize = sketchCanvas.brushSize()
        self._editedImage = editedImage


        self.brushSizeSlider = ParamSlider(self, "Brush size", config, "maskBrushSize", "minBrushSize", "maxBrushSize")
        def updateBrushSize(mode, newSize):
            if mode == DRAW_MODES.MASK:
                self._maskBrushSize = newSize
                maskCanvas.setBrushSize(newSize)
            else:
                self._sketchBrushSize = newSize
                sketchCanvas.setBrushSize(newSize)
            self._updateBrushCursor()

        config.connect(self, "maskBrushSize", lambda s: updateBrushSize(DRAW_MODES.MASK, s))
        config.connect(self, "sketchBrushSize", lambda s: updateBrushSize(DRAW_MODES.SKETCH, s))
        editedImage.selectionChanged.connect(lambda: self.resizeEvent(None))

        self.toolToggle = DualToggle(self, TOOL_MODES.PEN, TOOL_MODES.ERASER, config)
        self.toolToggle.setIcons('./resources/pen.png', 'resources/eraser.png')
        self.toolToggle.setSelected(TOOL_MODES.PEN)
        def setDrawingTool(selection):
            self.maskCreator.setUseEraser(selection == TOOL_MODES.ERASER)
        self.toolToggle.valueChanged.connect(setDrawingTool)

        self.clearMaskButton = QPushButton(self)
        self.clearMaskButton.setText("clear")
        self.clearMaskButton.setIcon(QIcon(QPixmap('./resources/clear.png')))
        def clearMask():
            self.maskCreator.clear()
            self.toolToggle.setSelected(TOOL_MODES.PEN)
        self.clearMaskButton.clicked.connect(clearMask)

        self.fillMaskButton = QPushButton(self)
        self.fillMaskButton.setText("fill")
        self.fillMaskButton.setIcon(QIcon(QPixmap('./resources/fill.png')))
        def fillMask():
            self.maskCreator.fill()
        self.fillMaskButton.clicked.connect(fillMask)

        self.maskSketchToggle = DualToggle(self, DRAW_MODES.MASK, DRAW_MODES.SKETCH, config)
        self.maskSketchToggle.setIcons('./resources/mask.png', 'resources/sketch.png')
        self.maskSketchToggle.setToolTips("Draw over the area to be inpainted", "Add details to help guide inpainting")
        self.maskSketchToggle.valueChanged.connect(lambda selection: self.setDrawMode(selection))


        self.colorPickerButton = QPushButton(self)
        self.colorPickerButton.setText("Color")
        self.colorPickerButton.setToolTip("Select sketch brush color")
        self.colorPickerButton.clicked.connect(lambda: setSketchColor(QColorDialog.getColor()))
        setSketchColor(self.maskCreator.getSketchColor())
        self.colorPickerButton.setVisible(False)

        try:
            from data_model.canvas.brushlib import Brushlib
            from ui.widget.brush_picker import BrushPicker
            self.brushPickerButton = QPushButton(self)
            self._brushPicker = None
            self.brushPickerButton.setText("Brush")
            self.brushPickerButton.setToolTip("Select sketch brush type")
            self.brushPickerButton.setIcon(QIcon(QPixmap('./resources/brush.png')))
            def openBrushPicker():
                if self._brushPicker is None:
                    self._brushPicker = BrushPicker()
                self._brushPicker.show()
                self._brushPicker.raise_()
            self.openBrushPicker = openBrushPicker
            self.brushPickerButton.clicked.connect(openBrushPicker)
            self.brushPickerButton.setVisible(False)
        except ImportError as err:
            print(f"Skipping brush selection init, brushlib loading failed: {err}")



        self.layout = QGridLayout()
        self.borderSize = 2
        self.maskCreator.setContentsMargins(getEqualMargins(0))
        self.setLayout(self.layout)
        self._layoutType = ""
        self._setupCorrectLayout()

        # Enable/disable controls as appropriate when sketch or mask mode are enabled or disabled:
        def handleSketchModeEnabledChange(isEnabled):
            self.maskSketchToggle.setEnabled(isEnabled and self._maskCanvas.enabled())
            if not isEnabled and self._maskCanvas.enabled():
                self.setDrawMode(DRAW_MODES.MASK)
            elif isEnabled and not self._maskCanvas.enabled():
                self.setDrawMode(DRAW_MODES.SKETCH)
            elif not isEnabled:
                self.setDrawMode(DRAW_MODES.SKETCH if isEnabled else None)
            self.setEnabled(isEnabled or self._maskCanvas.enabled())
            self.resizeEvent(None)
        sketchCanvas.enabledStateChanged.connect(handleSketchModeEnabledChange)
        handleSketchModeEnabledChange(self._sketchCanvas.enabled())

        def handleMaskModeEnabledChange(isEnabled):
            self.maskSketchToggle.setEnabled(isEnabled and self._sketchCanvas.enabled())
            if not isEnabled and self._sketchCanvas.enabled():
                self.setDrawMode(DRAW_MODES.SKETCH)
            elif isEnabled and not self._sketchCanvas.enabled():
                self.setDrawMode(DRAW_MODES.MASK)
            else:
                self.setDrawMode(DRAW_MODES.MASK if isEnabled else None)

            self.setEnabled(isEnabled or self._maskCanvas.enabled())
            self.resizeEvent(None)
        maskCanvas.enabledStateChanged.connect(handleMaskModeEnabledChange)
        handleMaskModeEnabledChange(self._maskCanvas.enabled())


    def _clearControlLayout(self):
        widgets = [ 
            self.maskCreator,
            self.brushSizeSlider,
            self.toolToggle,
            self.clearMaskButton,
            self.fillMaskButton,
            self.maskSketchToggle,
            self.colorPickerButton
        ]
        if hasattr(self, 'pressureSizeCheckbox'):
            widgets.append(self.pressureSizeCheckbox)
            widgets.append(self.pressureOpacityCheckbox)
        if hasattr(self, 'brushPickerButton'):
            widgets.append(self.brushPickerButton)
        for widget in widgets:
            if self.layout.indexOf(widget) != -1:
                self.layout.removeWidget(widget)
        for i in range(self.layout.rowCount()):
            self.layout.setRowStretch(i, 10)
        for i in range(self.layout.columnCount()):
            self.layout.setColumnStretch(i, 10)


    def _setupVerticalLayout(self):
        self._clearControlLayout()
        self.toolToggle.setOrientation(Qt.Orientation.Vertical)
        self.maskSketchToggle.setOrientation(Qt.Orientation.Vertical)
        self.brushSizeSlider.setOrientation(Qt.Orientation.Vertical)
        borderSize = self.brushSizeSlider.sizeHint().width() // 3
        self.layout.addWidget(self.colorPickerButton, 0, 1, 1, 2)
        if hasattr(self, 'brushPickerButton'):
            self.layout.addWidget(self.brushPickerButton, 1, 1, 1, 2)
        else:
            self.layout.setRowStretch(1, 0)
        if not self.colorPickerButton.isVisible():
            self.layout.setRowStretch(0, 0)
            self.layout.setRowStretch(1, 0)

        self.layout.addWidget(self.maskSketchToggle, 2, 1, 2, 1)
        self.layout.addWidget(self.toolToggle, 4, 1, 2, 1)
        self.layout.addWidget(self.brushSizeSlider, 2, 2, 4, 1)
        if hasattr(self, 'pressureSizeCheckbox'):
            self.layout.addWidget(self.pressureSizeCheckbox, 6, 1, 1, 2)
            if self.pressureOpacityCheckbox.isVisible():
                self.layout.addWidget(self.pressureOpacityCheckbox, 7, 1, 1, 2)
            else:
                self.layout.setRowStretch(7, 0)
        else:
            self.layout.setRowStretch(6, 0)
            self.layout.setRowStretch(7, 0)
        self.layout.addWidget(self.fillMaskButton, 8, 1, 1, 2)
        self.layout.addWidget(self.clearMaskButton, 9, 1, 1, 2)
        self.layout.addWidget(self.maskCreator, 0, 0, self.layout.rowCount(), 1)
        self.layout.setColumnStretch(0, 255)

        borderSize = self.brushSizeSlider.sizeHint().width() // 3
        self.layout.setVerticalSpacing(borderSize)
        self.layout.setHorizontalSpacing(borderSize)
        self.layout.setContentsMargins(getEqualMargins(borderSize))
        self._layoutType = Qt.Orientation.Vertical

    def _setupHorizontalLayout(self):
        self._clearControlLayout()
        self.toolToggle.setOrientation(Qt.Orientation.Horizontal)
        self.maskSketchToggle.setOrientation(Qt.Orientation.Horizontal)
        self.brushSizeSlider.setOrientation(Qt.Orientation.Horizontal)
        self.layout.addWidget(self.toolToggle, 1, 2)
        self.layout.addWidget(self.maskSketchToggle, 1, 3)
        if hasattr(self, 'brushPickerButton'):
            self.layout.addWidget(self.colorPickerButton, 2, 2)
            self.layout.addWidget(self.brushPickerButton, 2, 3)
        else:
            self.layout.addWidget(self.colorPickerButton, 2, 2, 1, 2)
        if not self.colorPickerButton.isVisible():
            self.layout.setRowStretch(2, 0)
        if hasattr(self, 'pressureSizeCheckbox'):
            if self.pressureOpacityCheckbox.isVisible():
                self.layout.addWidget(self.pressureSizeCheckbox, 3, 2)
                self.layout.addWidget(self.pressureOpacityCheckbox, 3, 3)
            else:
                self.layout.addWidget(self.pressureSizeCheckbox, 3, 2, 1, 2)
        else:
            self.layout.setRowStretch(3, 0)
        self.layout.addWidget(self.brushSizeSlider, 4, 2, 1, 2)
        self.layout.addWidget(self.clearMaskButton, 5, 2)
        self.layout.addWidget(self.fillMaskButton, 5, 3)
        self.layout.setRowStretch(0, 255)
        self.layout.setColumnStretch(0, 0)
        self.layout.setColumnStretch(1, 1)
        self.layout.setColumnStretch(4, 1)
        self.layout.addWidget(self.maskCreator, 0, 1, 1, self.layout.columnCount() - 1)
        for i in range(7, self.layout.rowCount()):
            self.layout.setRowStretch(i, 0)
        for i in range(6, self.layout.columnCount()):
            self.layout.setColumnStretch(i, 0)

        borderSize = self.brushSizeSlider.sizeHint().height() // 3
        self.layout.setVerticalSpacing(borderSize)
        self.layout.setHorizontalSpacing(borderSize)
        self.layout.setContentsMargins(getEqualMargins(self.borderSize))
        self._layoutType = Qt.Orientation.Horizontal

    def _setupCorrectLayout(self):
        widgetAspectRatio = self.width() / self.height()
        editSize = self._config.get("editSize")
        editAspectRatio = editSize.width() / editSize.height()
        if widgetAspectRatio > editAspectRatio:
            if self._layoutType != Qt.Orientation.Vertical:
                self._setupVerticalLayout()
        else:
            if self._layoutType != Qt.Orientation.Horizontal:
                self._setupHorizontalLayout()
        self.update()
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
            self._layoutType = None
            self._setupCorrectLayout()

    def setDrawMode(self, mode):
        if mode == self._drawMode:
            return
        if not DRAW_MODES.isValid(mode):
            raise Exception(f"tried to set invalid drawing mode {mode}")
        if mode == DRAW_MODES.MASK and not self._maskCanvas.enabled():
            raise Exception("called setDrawMode(MASK) when mask mode is disabled")
        if mode == DRAW_MODES.SKETCH and not self._sketchCanvas.enabled():
            raise Exception("called setDrawMode(SKETCH) when sketch mode is disabled")
        self._drawMode = mode
        self.maskSketchToggle.setSelected(mode)
        self.maskCreator.setSketchMode(mode == DRAW_MODES.SKETCH)
        self.colorPickerButton.setVisible(mode == DRAW_MODES.SKETCH)
        if hasattr(self, 'brushPickerButton'):
            self.brushPickerButton.setVisible(mode == DRAW_MODES.SKETCH)
            if hasattr(self, 'pressureOpacityCheckbox'):
                self.pressureSizeCheckbox.setVisible(mode == DRAW_MODES.MASK)
                self.pressureOpacityCheckbox.setVisible(False)
        self.brushSizeSlider.connectKey("maskBrushSize" if mode == DRAW_MODES.MASK else "sketchBrushSize",
                "minBrushSize", "maxBrushSize", None)
        self._layoutType = None
        self.resizeEvent(None)
        self.update()

    def toggleDrawMode(self):
        if self._drawMode is not None:
            self.setDrawMode(DRAW_MODES.MASK if self._drawMode == DRAW_MODES.SKETCH else DRAW_MODES.SKETCH)

    def getBrushSize(self):
        return self._config.get("maskBrushSize" if self._drawMode == DRAW_MODES.MASK else "sketchBrushSize")

    def setBrushSize(self, size):
        self._config.set("maskBrushSize" if self._drawMode == DRAW_MODES.MASK else "sketchBrushSize", size)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(contrastColor(self), self.borderSize//2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
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
            if event.key() == Qt.Key_Control and not self._drawMode == DRAW_MODES.MASK:
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

    def selectPenTool(self):
        self.toolToggle.setSelected(TOOL_MODES.PEN)

    def selectEraserTool(self):
        self.toolToggle.setSelected(TOOL_MODES.ERASER)

    def swapDrawTool(self):
        self.toolToggle.toggle()

    def undo(self):
        self.maskCreator.undo()

    def redo(self):
        self.maskCreator.redo()

    def _updateBrushCursor(self):
        if not hasattr(self, 'maskCreator'):
            return
        brushSize = self._config.get("maskBrushSize" if self._drawMode == DRAW_MODES.MASK else "sketchBrushSize")
        scale = max(self.maskCreator.getImageDisplaySize().width(), 1) / max(self._maskCanvas.width(), 1)
        scaledSize = max(int(brushSize * scale), 9)
        if scaledSize == self._lastCursorSize:
            return
        if scaledSize <= 10:
            self.maskCreator.setCursor(self._smallCursor)
        else:
            newCursor = QCursor(self._cursorPixmap.scaled(QSize(scaledSize, scaledSize)))
            self.maskCreator.setCursor(newCursor)
        self._lastCursorSize = scaledSize
