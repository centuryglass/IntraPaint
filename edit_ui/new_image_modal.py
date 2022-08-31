from PyQt5.QtWidgets import QWidget, QDialog, QSpinBox, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt5.QtCore import QSize

class NewImageModal(QDialog):
    def __init__(self):
        super().__init__()

        self._create = False
        self.setModal(True)

        self._title = QLabel(self)
        self._title.setText("Create new image")


        def makeLabeledSpinbox(labelText, toolTip):
            widget = QWidget(self)
            widget.setToolTip(toolTip)
            widget.layout = QHBoxLayout()
            widget.label = QLabel(widget)
            widget.label.setText(labelText)
            widget.spinbox = QSpinBox(widget)
            widget.spinbox.setRange(8, 100000)
            widget.spinbox.setValue(256)
            widget.layout.addWidget(widget.label, 1)
            widget.layout.addWidget(widget.spinbox, 2)
            widget.setLayout(widget.layout)
            return widget

        self._widthBox = makeLabeledSpinbox("Width:", "New image width in pixels")
        self._heightBox = makeLabeledSpinbox("Height:", "New image height in pixels")

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
