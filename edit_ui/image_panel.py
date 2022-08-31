from PyQt5.QtWidgets import QWidget, QSpinBox, QLineEdit, QPushButton, QLabel, QGridLayout, QSpacerItem, QFileDialog, QMessageBox
from PyQt5.QtCore import Qt, QPoint, QSize, QRect, QBuffer
import PyQt5.QtGui as QtGui
from PyQt5.QtGui import QPainter, QPen
from PIL import Image
from edit_ui.image_viewer import ImageViewer
from edit_ui.new_image_modal import NewImageModal
from edit_ui.ui_utils import showErrorDialog
import os, sys

class ImagePanel(QWidget):
    """
    Shows the image being edited, along with associated UI elements.
    ...
    Attributes
    ----------
        imageViewer : ImageViewer
            Main image editing widget
        xCoordBox : QSpinBox
            Connected to the selected inpaiting area's x-coordinate.
        yCoordBox : QSpinBox
            Connected to the selected inpaiting area's y-coordinate.
        fileTextBox : QLineEdit
            Gets/sets the edited image's file path.
        fileSelectButton : QPushButton
            Opens a file selection dialog to load a new image.
        imagReloadButton : QPushButton
            (Re)loads the image from the path in the fileTextBox.
    """

    def __init__(self, pilImage=None, selectionSize=QSize(256, 256), scaleEnabled = True):
        """
        Parameters
        ----------
        pilImage : Image, optional
            An initial pillow Image object to load.
        selectionSize : QSize, default QSize(256, 256)
            Size in pixels of selected image sections used for inpainting.
            Dimensions should be positive multiples of 64, no greater than 256.
        """
        super().__init__()
        assert pilImage is None or isinstance(pilImage, Image.Image)
        assert isinstance(selectionSize, QSize)
        self._scaleEnabled = scaleEnabled

        self.imageViewer = ImageViewer(pilImage, selectionSize)
        imageViewer = self.imageViewer

        # wire x/y coordinate boxes to set selection coordinates:
        self.xCoordBox = QSpinBox(self)
        self.yCoordBox = QSpinBox(self)
        self.xCoordBox.setToolTip("Selected X coordinate")
        self.yCoordBox.setToolTip("Selected Y coordinate")
        def setX(value):
            lastSelected = imageViewer.getSelection()
            if lastSelected:
                selection = QPoint(value, lastSelected.y())
                imageViewer.setSelection(selection)
        self.xCoordBox.valueChanged.connect(setX)
        def setY(value):
            lastSelected = imageViewer.getSelection()
            if lastSelected:
                selection = QPoint(lastSelected.x(), value)
                imageViewer.setSelection(selection)
        self.yCoordBox.valueChanged.connect(setY)

        # Selection size controls:
        self.widthBox = QSpinBox(self)
        self.heightBox = QSpinBox(self)
        for sizeControl, typeName in [(self.widthBox, "width"), (self.heightBox, "height")]:
            sizeControl.setToolTip(f"Selected area {typeName}")
            sizeControl.setRange(64, 256)
            sizeControl.setSingleStep(64)
            sizeControl.setValue(256)
        def setW(value):
            size = QSize(value, imageViewer.selectionHeight())
            imageSize = self.imageViewer.imageSize()
            if imageSize:
                self.xCoordBox.setMaximum(imageSize.width() - value)
            imageViewer.setSelection(size=size)
        self.widthBox.valueChanged.connect(setW)
        def setH(value):
            size = QSize(imageViewer.selectionWidth(), value)
            imageSize = self.imageViewer.imageSize()
            if imageSize:
                self.yCoordBox.setMaximum(imageSize.height() - value)
            imageViewer.setSelection(size=size)
        self.heightBox.valueChanged.connect(setH)

        # Update coordinate controls automatically when the selection changes:
        def setCoords(pt, size):
            self.xCoordBox.setValue(pt.x())
            self.yCoordBox.setValue(pt.y())
            self.widthBox.setValue(size.width())
            self.heightBox.setValue(size.height())
        self.imageViewer.onSelection.connect(setCoords)

        self.fileTextBox = QLineEdit("", self)

        isPyinstallerBundle = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

        # Set image path, load image viewer when a file is selected:
        self.fileSelectButton = QPushButton(self)
        self.fileSelectButton.setText("Select Image")
        def openImageFile():
            try:
                file, fileSelected = (None, None)
                if isPyinstallerBundle:
                    file, fileSelected = QFileDialog.getOpenFileName(self, 'Open Image',
                        options=QFileDialog.Option.DontUseNativeDialog)
                else:
                    file, fileSelected = QFileDialog.getOpenFileName(self, 'Open Image')
                if file and fileSelected:
                    self.loadImage(file)
            except Exception as err:
                showErrorDialog(self, "Open failed", err)
        self.fileSelectButton.clicked.connect(openImageFile)

        self.newImageButton = QPushButton(self)
        self.newImageButton.setText("New Image")
        def newImage():
            imageModal = NewImageModal()
            imageSize = imageModal.showImageModal()
            if imageSize:
                if self.imageViewer.hasImage():
                    confirmBox = QMessageBox(self)
                    confirmBox.setWindowTitle("Create new image?")
                    confirmBox.setWindowTitle("Create new image?")
                    confirmBox.setText("This will discard all unsaved changes.")
                    confirmBox.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
                    response = confirmBox.exec()
                    if response == QMessageBox.Cancel:
                        return
                newImage = Image.new('RGB', (imageSize.width(), imageSize.height()), color = 'white')
                self.loadImage(newImage)
        self.newImageButton.clicked.connect(newImage)

        self.imgReloadButton = QPushButton(self)
        self.imgReloadButton.setText("Reload image")
        def reloadImage():
            if self.fileTextBox.text() == "":
                showErrorDialog(self, "Reload failed", f"Enter an image path or click 'Open Image' first.")
                return
            if not os.path.isfile(self.fileTextBox.text()):
                showErrorDialog(self, "Reload failed", f"Image path '{self.fileTextBox.text()}' is not a valid file.")
                return
            if self.imageViewer.hasImage():
                confirmBox = QMessageBox(self)
                confirmBox.setWindowTitle("Reload image?")
                confirmBox.setWindowTitle("Reload image?")
                confirmBox.setText("This will overwrite all unsaved changes.")
                confirmBox.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
                response = confirmBox.exec()
                if response == QMessageBox.Cancel:
                    return
            self.loadImage(self.fileTextBox.text())

        self.imgReloadButton.clicked.connect(reloadImage)

        self.saveButton = QPushButton(self)
        self.saveButton.setText("Save Image")
        def saveImage():
            if not self.imageViewer.hasImage():
                showErrorDialog(self, "Save failed", "Open an image first before trying to save.")
                return
            pngFilter = "Images (*.png)"
            file, fileSelected = (None, None)
            if isPyinstallerBundle:
                file, fileSelected = QFileDialog.getSaveFileName(self, 'Save Image',
                    filter=pngFilter,
                    options=QFileDialog.Option.DontUseNativeDialog)
            else:
                file, fileSelected = QFileDialog.getSaveFileName(self, 'Save Image', filter=pngFilter)
            try:
                if file and fileSelected:
                    self.saveImage(file)
            except Exception as err:
                showErrorDialog(self, "Save failed", str(err))
                print(f"Saving image failed: {err}")
        self.saveButton.clicked.connect(saveImage)

        self.layout = QGridLayout()
        self.borderSize = 4
        def makeSpacer():
            return QSpacerItem(self.borderSize, self.borderSize)
        self.layout.addItem(makeSpacer(), 0, 0, 1, 1)
        self.layout.addItem(makeSpacer(), 3, 0, 1, 1)
        self.layout.addItem(makeSpacer(), 0, 0, 1, 1)
        self.layout.addItem(makeSpacer(), 0, 6, 1, 1)
        self.layout.addWidget(self.imageViewer, 1, 1, 1, 14)
        self.layout.addWidget(self.fileSelectButton, 2, 1, 1, 1)
        self.layout.addWidget(self.newImageButton, 2, 2, 1, 1)
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

        self.layout.addWidget(self.imgReloadButton, 2, 13, 1, 1)
        self.layout.addWidget(self.saveButton, 2, 14, 1, 1)

        self.layout.setRowMinimumHeight(1, 250)
        self.layout.setColumnStretch(4, 255)
        self.setLayout(self.layout)

    def saveImage(self, filePath):
        image = self.imageViewer.getImage()
        image.save(filePath, "PNG")

    def loadImage(self, image):
        try:
            self.imageViewer.setImage(image)
            if isinstance(image, str): # image is a file path:
                self.fileTextBox.setText(image)
            imageSize = self.imageViewer.imageSize()
            if imageSize:
                if imageSize.width() < 64 or imageSize.height() < 64:
                    raise Exception(f"image width and height should be no smaller than 64px, got {imageSize}")
                self.xCoordBox.setRange(0, max(
                            imageSize.width() - self.imageViewer.selectionWidth(), 0))
                self.yCoordBox.setRange(0, max(
                            imageSize.height() - self.imageViewer.selectionHeight(), 0))
                self.reloadScaleBounds()
        except Exception as err:
            print(f"Failed to load image from '{image}': {err}")
            showErrorDialog(self, "Loading image failed", err)


    def setScaleEnabled(self, scaleEnabled):
        if scaleEnabled != self._scaleEnabled:
            self._scaleEnabled = scaleEnabled
            self.reloadScaleBounds()

    def reloadScaleBounds(self):
        imageSize = self.imageViewer.imageSize()
        if imageSize is None:
            imageSize = QSize(0, 0)
        for spinBox, dim in [(self.widthBox, imageSize.width()), (self.heightBox, imageSize.height())]:
            if self._scaleEnabled and dim != 0:
                spinBox.setMaximum(dim)
                spinBox.setSingleStep(8)
            else:
                spinBox.setSingleStep(64)
                if imageSize:
                    spinBox.setMaximum(min(256, dim - (dim % 64)))
                else:
                    spinBox.setMaximum(256)
                if (spinBox.value() % 64) != 0:
                    spinBox.setValue(spinBox.value() - (spinBox.value() % 64))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QPen(Qt.black, self.borderSize/2, Qt.SolidLine,
                    Qt.RoundCap, Qt.RoundJoin))
        painter.drawRect(1, 1, self.width() - 2, self.height() - 2)
