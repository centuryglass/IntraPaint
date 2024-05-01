from PyQt5.QtWidgets import (QWidget, QSpinBox, QLineEdit, QPushButton, QLabel, QGridLayout, QSpacerItem,
        QFileDialog, QMessageBox, QVBoxLayout, QHBoxLayout, QSlider, QSizePolicy)
from PyQt5.QtCore import Qt, QPoint, QSize, QRect, QBuffer, pyqtSignal
from PyQt5.QtGui import QPainter, QPen
from PIL import Image
import os, sys

from ui.image_viewer import ImageViewer
from ui.config_control_setup import connectedTextEdit
from ui.util.contrast_color import contrastColor
from ui.widget.param_slider import ParamSlider
from ui.widget.collapsible_box import CollapsibleBox
from ui.widget.dual_toggle import DualToggle

class ImagePanel(QWidget):
    """
    Holds the image viewer, provides inputs for selecting an editing area and saving/loading images.
    """
    imageToggled = pyqtSignal(bool)


    def __init__(self, config, editedImage, controller):
        super().__init__()

        editedImage.sizeChanged.connect(lambda newSize: self.reloadScaleBounds())
        self._editedImage = editedImage
        self._config = config
        self._showSliders = None
        self._sliderCount = 0
        self._minimized = False
        self.borderSize = 4

        self._layout = QHBoxLayout()
        self.setLayout(self._layout)

        self.imageBox = CollapsibleBox("Full Image",
                parent=self,
                scrolling=False,
                orientation=Qt.Orientation.Horizontal)
        self.imageBox.toggled().connect(lambda t: self.imageToggled.emit(t))
        self.imageBox.setExpandedSizePolicy(QSizePolicy.Ignored)
        self.imageBoxLayout = QVBoxLayout()
        self.imageBox.setContentLayout(self.imageBoxLayout)
        self._layout.addWidget(self.imageBox, stretch=255)


        self.imageViewer = ImageViewer(editedImage)
        imageViewer = self.imageViewer
        self.imageBoxLayout.addWidget(self.imageViewer, stretch=255)

        controlBarLayout = QHBoxLayout()
        self.imageBoxLayout.addLayout(controlBarLayout)

        controlBarLayout.addWidget(QLabel(self, text="Image Path:"))
        self.fileTextBox = connectedTextEdit(self, config, "lastFilePath") 
        controlBarLayout.addWidget(self.fileTextBox, stretch=255)

        # wire x/y coordinate boxes to set selection coordinates:
        controlBarLayout.addWidget(QLabel(self, text="X:"))
        self.xCoordBox = QSpinBox(self)
        controlBarLayout.addWidget(self.xCoordBox)
        self.xCoordBox.setRange(0, 0)
        self.xCoordBox.setToolTip("Selected X coordinate")
        def setX(value):
            if editedImage.hasImage():
                lastSelected = editedImage.getSelectionBounds()
                lastSelected.moveLeft(min(value, editedImage.width() - lastSelected.width()))
                editedImage.setSelectionBounds(lastSelected)
        self.xCoordBox.valueChanged.connect(setX)

        controlBarLayout.addWidget(QLabel(self, text="Y:"))
        self.yCoordBox = QSpinBox(self)
        controlBarLayout.addWidget(self.yCoordBox)
        self.yCoordBox.setRange(0, 0)
        self.yCoordBox.setToolTip("Selected Y coordinate")
        def setY(value):
            if editedImage.hasImage():
                lastSelected = editedImage.getSelectionBounds()
                lastSelected.moveTop(min(value, editedImage.height() - lastSelected.height()))
                editedImage.setSelectionBounds(lastSelected)
        self.yCoordBox.valueChanged.connect(setY)

        # Selection size controls:
        controlBarLayout.addWidget(QLabel(self, text="W:"))
        self.widthBox = QSpinBox(self)
        controlBarLayout.addWidget(self.widthBox)

        controlBarLayout.addWidget(QLabel(self, text="H:"))
        self.heightBox = QSpinBox(self)
        controlBarLayout.addWidget(self.heightBox)

        editSize = config.get('editSize')
        minEditSize = config.get('minEditSize')
        maxEditSize = config.get('maxEditSize')
        for sizeControl, typeName, minSize, maxSize, size in [
                (self.widthBox, "width", minEditSize.width(), maxEditSize.width(), editSize.width()),
                (self.heightBox, "height", minEditSize.height(), maxEditSize.height(), editSize.height())]:
            sizeControl.setToolTip(f"Selected area {typeName}")
            sizeControl.setRange(minSize, maxSize)
            sizeControl.setSingleStep(minSize)
            sizeControl.setValue(size)

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
        self.setLayout(self._layout)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        self.showSliders(False)

    def setOrientation(self, orientation):
        if self.imageBox is not None:
            self._layout.removeWidget(self.imageBox)
            self.imageBox.setParent(None)
            self.imageBox = None
        self.imageBox = CollapsibleBox("Full Image",
                parent=self,
                scrolling=False,
                orientation=orientation)
        self.imageBox.toggled().connect(lambda t: self.imageToggled.emit(t))
        self.imageBox.setContentLayout(self.imageBoxLayout)
        self._layout.insertWidget(self._sliderCount, self.imageBox)

    def addSlider(self, slider):
        assert(isinstance(slider, ParamSlider) or isinstance(slider, QSlider))
        self._layout.insertWidget(self._sliderCount, slider, stretch=1)
        self._sliderCount += 1
        self.showSliders(self._showSliders)

    def slidersShowing(self):
        return self._showSliders

    def showSliders(self, showSliders):
        self._showSliders = showSliders
        if showSliders:
            for i in range(self._sliderCount):
                self._layout.setStretch(i, 1)
            for slider in (self._layout.itemAt(i).widget() for i in range(self._sliderCount)):
                slider.setVisible(True)
                slider.setEnabled(True)
                slider.setMaximumWidth(slider.sizeHint().width())
        else:
            for i in range(self._sliderCount):
                self._layout.setStretch(i, 0)
            for slider in (self._layout.itemAt(i).widget() for i in range(self._sliderCount)):
                slider.setEnabled(False)
                slider.setVisible(False)
                slider.setMaximumWidth(0)
        self.imageBox.showButtonBar(True)

    def reloadScaleBounds(self):
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
            selectionSize = self._editedImage.getSelectionBounds().size()
            self.xCoordBox.setMaximum(imageSize.width() - selectionSize.width())
            self.yCoordBox.setMaximum(imageSize.height() - selectionSize.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QPen(contrastColor(self), self.borderSize/2, Qt.SolidLine,
                    Qt.RoundCap, Qt.RoundJoin))
        painter.drawRect(1, 1, self.width() - 2, self.height() - 2)
