from PyQt5.QtWidgets import QWidget, QDialog, QSpinBox, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt5.QtCore import QSize
from inpainting.ui.widget.labeled_spinbox import LabeledSpinbox

class NewImageModal(QDialog):
    def __init__(self, defaultWidth, defaultHeight):
        super().__init__()

        self._create = False
        self.setModal(True)

        self._title = QLabel(self)
        self._title.setText("Create new image")

        minVal = 8
        maxVal = 20000
        self._widthBox = LabeledSpinbox(self, "Width:", "New image width in pixels", minVal, defaultWidth, maxVal)
        self._heightBox = LabeledSpinbox(self, "Height:", "New image height in pixels", minVal, defaultHeight, maxVal)

        self._createButton = QPushButton(self)
        self._createButton.setText("Create new image")
        def onCreate():
            self._create = True
            self.hide()
        self._createButton.clicked.connect(onCreate)

        self._cancelButton = QPushButton(self)
        self._cancelButton.setText("Cancel")
        def onCancel():
            self._create = False
            self.hide()
        self._cancelButton.clicked.connect(onCancel)
        
        self._layout = QVBoxLayout()
        for widget in [self._title, self._widthBox, self._heightBox, self._createButton, self._cancelButton]:
            self._layout.addWidget(widget)

        self.setLayout(self._layout)

    def showImageModal(self):
        self.exec_()
        if self._create:
            return QSize(self._widthBox.spinbox.value(), self._heightBox.spinbox.value())
