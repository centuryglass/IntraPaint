from PyQt5.QtWidgets import QWidget, QSpinBox, QLineEdit, QPushButton, QLabel, QGridLayout, QSpacerItem, QFileDialog, QMessageBox
from PyQt5.QtCore import Qt, QPoint, QSize, QRect, QBuffer
import PyQt5.QtGui as QtGui
from PyQt5.QtGui import QPainter, QPen
from PIL import Image
from inpainting.ui.image_viewer import ImageViewer
from inpainting.ui.config_control_setup import connectedTextEdit
import os, sys

class ImagePanel(QWidget):
    """
    Holds the image viewer, provides inputs for selecting an editing area and saving/loading images.
    """

    def __init__(self, config, editedImage, controller):
        super().__init__()

        editedImage.sizeChanged.connect(lambda newSize: self.reloadScaleBounds())
        self._editedImage = editedImage
        self._config = config

        self.imageViewer = ImageViewer(editedImage)
        imageViewer = self.imageViewer

        # wire x/y coordinate boxes to set selection coordinates:
        self.xCoordBox = QSpinBox(self)
        self.yCoordBox = QSpinBox(self)
        self.xCoordBox.setRange(0, 0)
        self.yCoordBox.setRange(0, 0)
        self.xCoordBox.setToolTip("Selected X coordinate")
        self.yCoordBox.setToolTip("Selected Y coordinate")
        def setX(value):
            if editedImage.hasImage():
                lastSelected = editedImage.getSelectionBounds()
                lastSelected.moveLeft(min(value, editedImage.width() - lastSelected.width()))
                editedImage.setSelectionBounds(lastSelected)
        self.xCoordBox.valueChanged.connect(setX)
        def setY(value):
            if editedImage.hasImage():
                lastSelected = editedImage.getSelectionBounds()
                lastSelected.moveTop(min(value, editedImage.height() - lastSelected.height()))
                editedImage.setSelectionBounds(lastSelected)
        self.yCoordBox.valueChanged.connect(setY)

        # Selection size controls:
        self.widthBox = QSpinBox(self)
        self.heightBox = QSpinBox(self)
        minEditSize = config.get('minEditSize')
        maxEditSize = config.get('maxEditSize')
        for sizeControl, typeName, minSize, maxSize in [
                (self.widthBox, "width", minEditSize.width(), maxEditSize.width()),
                (self.heightBox, "height", minEditSize.height(), maxEditSize.height())]:
            sizeControl.setToolTip(f"Selected area {typeName}")
            sizeControl.setRange(minSize, maxSize)
            sizeControl.setSingleStep(minSize)
            sizeControl.setValue(maxSize)

        def setW():
            value = self.widthBox.value()
            if editedImage.hasImage():
                selection = editedImage.getSelectionBounds()
                selection.setWidth(value)
                editedImage.setSelectionBounds(selection)
        self.widthBox.editingFinished.connect(setW)

        def setH():
            value = self.heightBox.value()
            if editedImage.hasImage():
                selection = editedImage.getSelectionBounds()
                selection.setHeight(value)
                editedImage.setSelectionBounds(selection)
        self.heightBox.editingFinished.connect(setH)

        # Update coordinate controls automatically when the selection changes:
        def setCoords(bounds):
            self.xCoordBox.setValue(bounds.left())
            self.yCoordBox.setValue(bounds.top())
            self.widthBox.setValue(bounds.width())
            self.heightBox.setValue(bounds.height())
            if editedImage.hasImage():
                self.xCoordBox.setMaximum(editedImage.width() - bounds.width())
                self.yCoordBox.setMaximum(editedImage.height() - bounds.height())
        editedImage.selectionChanged.connect(setCoords)

        self.fileTextBox = connectedTextEdit(self, config, "lastFilePath") 

        self.layout = QGridLayout()
        self.borderSize = 4
        def makeSpacer():
            return QSpacerItem(self.borderSize, self.borderSize)
        self.layout.addItem(makeSpacer(), 0, 0, 1, 1)
        self.layout.addItem(makeSpacer(), 3, 0, 1, 1)
        self.layout.addItem(makeSpacer(), 0, 0, 1, 1)
        self.layout.addItem(makeSpacer(), 0, 6, 1, 1)
        self.layout.addWidget(self.imageViewer, 1, 1, 1, 14)
        self.layout.addWidget(QLabel(self, text="Image path:"), 2, 3, 1, 1)
        self.layout.addWidget(self.fileTextBox, 2, 4, 1, 1)


        self.layout.addWidget(QLabel(self, text="X:"), 2, 5, 1, 1)
        self.layout.addWidget(self.xCoordBox, 2, 6, 1, 1)
        self.layout.addWidget(QLabel(self, text="Y:"), 2, 7, 1, 1)
        self.layout.addWidget(self.yCoordBox, 2, 8, 1, 1)

        self.layout.addWidget(QLabel(self, text="W:"), 2, 9, 1, 1)
        self.layout.addWidget(self.widthBox, 2, 10, 1, 1)
        self.layout.addWidget(QLabel(self, text="H:"), 2, 11, 1, 1)
        self.layout.addWidget(self.heightBox, 2, 12, 1, 1)

        self.layout.setRowMinimumHeight(1, 250)
        self.layout.setColumnStretch(4, 255)
        self.setLayout(self.layout)

    def reloadScaleBounds(self):
        scaleEnabled = self._config.get('scaleSelectionBeforeInpainting')
        maxEditSize = self._editedImage.getMaxSelectionSize()
        if not self._editedImage.hasImage():
            self.widthBox.setMaximum(maxEditSize.width())
            self.heightBox.setMaximum(maxEditSize.height())
        else:
            imageSize = self._editedImage.size()
            for spinBox, dim, maxEditDim in [
                    (self.widthBox, imageSize.width(), maxEditSize.width()),
                    (self.heightBox, imageSize.height(), maxEditSize.height())]:
                spinBox.setMaximum(maxEditDim)
                spinBox.setSingleStep(8 if scaleEnabled else 64)
                if (spinBox.value() % 64) != 0 and (spinBox.value() > 64):
                    spinBox.setValue(spinBox.value() - (spinBox.value() % 64))
            selectionSize = self._editedImage.getSelectionBounds().size()
            self.xCoordBox.setMaximum(imageSize.width() - selectionSize.width())
            self.yCoordBox.setMaximum(imageSize.height() - selectionSize.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QPen(Qt.black, self.borderSize/2, Qt.SolidLine,
                    Qt.RoundCap, Qt.RoundJoin))
        painter.drawRect(1, 1, self.width() - 2, self.height() - 2)
