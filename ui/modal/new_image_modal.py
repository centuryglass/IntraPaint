"""Popup modal window used for creating a new image at an arbitrary size."""
from typing import Optional
from PyQt5.QtWidgets import QDialog, QLabel, QVBoxLayout, QPushButton
from PyQt5.QtCore import QSize
from ui.widget.labeled_spinbox import LabeledSpinbox

class NewImageModal(QDialog):
    """Popup modal window used for creating a new image at an arbitrary size."""

    def __init__(self, default_width: int, default_height: int):
        super().__init__()

        self._create = False
        self.setModal(True)

        self._title = QLabel(self)
        self._title.setText('Create new image')

        min_val = 8
        max_val = 20000
        self._widthbox = LabeledSpinbox(self, 'Width:', 'New image width in pixels', min_val, default_width, max_val)
        self._heightbox = LabeledSpinbox(self, 'Height:', 'New image height in pixels', min_val, default_height,
                max_val)

        self._create_button = QPushButton(self)
        self._create_button.setText('Create new image')
        def on_create():
            self._create = True
            self.hide()
        self._create_button.clicked.connect(on_create)

        self._cancel_button = QPushButton(self)
        self._cancel_button.setText('Cancel')
        def on_cancel():
            self._create = False
            self.hide()
        self._cancel_button.clicked.connect(on_cancel)

        self._layout = QVBoxLayout()
        for widget in [self._title, self._widthbox, self._heightbox, self._create_button, self._cancel_button]:
            self._layout.addWidget(widget)

        self.setLayout(self._layout)

    def show_image_modal(self) -> Optional[QSize]:
        """Shows the modal, then returns the user-entered size when closed."""
        self.exec_()
        if self._create:
            return QSize(self._widthbox.spinbox.value(), self._heightbox.spinbox.value())
        return None
