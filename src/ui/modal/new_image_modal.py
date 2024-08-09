"""Popup modal window used for creating a new image at an arbitrary size."""
from typing import Optional

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QPushButton
from PySide6.QtCore import QSize
from src.ui.input_fields.labeled_spinbox import LabeledSpinbox
from src.util.shared_constants import APP_ICON_PATH

CREATE_IMAGE_TITLE = 'Create new image'
WIDTH_LABEL = 'Width:'
WIDTH_TOOLTIP = 'New image width in pixels'
HEIGHT_LABEL = 'Height:'
HEIGHT_TOOLTIP = 'New image height in pixels'
CREATE_BUTTON_TEXT = 'Create'
CANCEL_BUTTON_TEXT = 'Cancel'
MIN_PX_VALUE = 8
MAX_PX_VALUE = 20000


class NewImageModal(QDialog):
    """Popup modal window used for creating a new image at an arbitrary size."""

    def __init__(self, default_width: int, default_height: int) -> None:
        super().__init__()
        self.setWindowIcon(QIcon(APP_ICON_PATH))

        self._create = False
        self.setModal(True)

        self._title = QLabel(self)
        self._title.setText(CREATE_IMAGE_TITLE)

        self._width_box = LabeledSpinbox(self, WIDTH_LABEL, WIDTH_TOOLTIP, MIN_PX_VALUE, default_width, MAX_PX_VALUE)
        self._height_box = LabeledSpinbox(self, HEIGHT_LABEL, HEIGHT_TOOLTIP, MIN_PX_VALUE, default_height,
                                          MAX_PX_VALUE)

        self._create_button = QPushButton(self)
        self._create_button.setText(CREATE_BUTTON_TEXT)
        self._create_button.clicked.connect(self._confirm)

        self._cancel_button = QPushButton(self)
        self._cancel_button.setText(CANCEL_BUTTON_TEXT)
        self._cancel_button.clicked.connect(self._cancel)

        self._layout = QVBoxLayout()
        for widget in [self._title, self._width_box, self._height_box, self._create_button, self._cancel_button]:
            self._layout.addWidget(widget)

        self.setLayout(self._layout)

    def _confirm(self) -> None:
        self._create = True
        self.hide()

    def _cancel(self) -> None:
        self._create = False
        self.hide()

    def show_image_modal(self) -> Optional[QSize]:
        """Shows the modal, then returns the user-entered size when closed."""
        self.exec()
        if self._create:
            return QSize(self._width_box.spinbox.value(), self._height_box.spinbox.value())
        return None
