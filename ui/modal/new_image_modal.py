"""
Popup modal window used for creating a new image at an arbitrary size.
"""
from PyQt5.QtWidgets import QWidget, QDialog, QSpinBox, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt5.QtCore import QSize
from ui.widget.labeled_spinbox import LabeledSpinbox

class NewImageModal(QDialog):
    def __init__(self, default_width, default_height):
        super().__init__()

        self._create = False
        self.setModal(True)

        self._title = QLabel(self)
        self._title.setText("Create new image")

        min_val = 8
        max_val = 20000
        self._widthbox = LabeledSpinbox(self, "Width:", "New image width in pixels", min_val, default_width, max_val)
        self._heightbox = LabeledSpinbox(self, "Height:", "New image height in pixels", min_val, default_height, max_val)

        self._create_button = QPushButton(self)
        self._create_button.setText("Create new image")
        def onCreate():
            self._create = True
            self.hide()
        self._create_button.clicked.connect(onCreate)

        self._cancel_button = QPushButton(self)
        self._cancel_button.setText("Cancel")
        def onCancel():
            self._create = False
            self.hide()
        self._cancel_button.clicked.connect(onCancel)
        
        self._layout = QVBoxLayout()
        for widget in [self._title, self._widthbox, self._heightbox, self._create_button, self._cancel_button]:
            self._layout.addWidget(widget)

        self.setLayout(self._layout)

    def show_image_modal(self):
        self.exec_()
        if self._create:
            return QSize(self._widthbox.spinbox.value(), self._heightbox.spinbox.value())
