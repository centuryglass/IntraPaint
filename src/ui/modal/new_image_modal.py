"""Popup modal window used for creating a new image at an arbitrary size."""
from typing import Optional

from PySide6.QtGui import QIcon, QColor, Qt, QPixmap, QPainter
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QPushButton, QApplication, QWidget, QHBoxLayout, QComboBox
from PySide6.QtCore import QSize, QRect, QPoint

from src.config.cache import Cache
from src.ui.input_fields.labeled_spinbox import LabeledSpinbox
from src.ui.widget.color_button import ColorButton
from src.util.visual.image_utils import get_color_icon
from src.util.shared_constants import APP_ICON_PATH, ICON_SIZE

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.modal.new_image_modal'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


CREATE_IMAGE_TITLE = _tr('Create new image')
WIDTH_LABEL = _tr('Width:')
WIDTH_TOOLTIP = _tr('New image width in pixels')
HEIGHT_LABEL = _tr('Height:')
HEIGHT_TOOLTIP = _tr('New image height in pixels')
CREATE_BUTTON_TEXT = _tr('Create')
CANCEL_BUTTON_TEXT = _tr('Cancel')
LABEL_TEXT_BACKGROUND_COLOR = _tr('Background Color:')

BACKGROUND_COLOR_OPTION_TRANSPARENT = _tr('transparent')
BACKGROUND_COLOR_OPTION_WHITE = _tr('white')
BACKGROUND_COLOR_OPTION_BLACK = _tr('black')
BACKGROUND_COLOR_OPTION_CUSTOM = _tr('custom')

BUTTON_TEXT_PICK_CUSTOM_COLOR = _tr('Select background color')

MIN_PX_VALUE = 8
MAX_PX_VALUE = 20000


def _custom_color_icon() -> QPixmap:
    size = QSize(ICON_SIZE, ICON_SIZE)
    pixmap = QPixmap(size)
    painter = QPainter(pixmap)
    rect = QRect(0, 0, pixmap.width() // 3, pixmap.height())
    painter.fillRect(rect, Qt.GlobalColor.red)
    rect.moveLeft(rect.width())
    painter.fillRect(rect, Qt.GlobalColor.green)
    rect.moveLeft(rect.left() + rect.width())
    rect.setWidth(size.width() - rect.left())
    painter.fillRect(rect, Qt.GlobalColor.blue)
    painter.drawRect(QRect(QPoint(), size).adjusted(0, 0, -1, -1))
    painter.end()
    return pixmap


class NewImageModal(QDialog):
    """Popup modal window used for creating a new image at an arbitrary size."""

    def __init__(self, default_width: int, default_height: int) -> None:
        super().__init__()
        self.setWindowIcon(QIcon(APP_ICON_PATH))

        self._create = False
        self._color = Cache().get_color(Cache.NEW_IMAGE_BACKGROUND_COLOR, Qt.GlobalColor.white)
        self.setModal(True)

        self.setWindowTitle(CREATE_IMAGE_TITLE)

        self._width_box = LabeledSpinbox(self, WIDTH_LABEL, WIDTH_TOOLTIP, MIN_PX_VALUE, default_width, MAX_PX_VALUE)
        self._height_box = LabeledSpinbox(self, HEIGHT_LABEL, HEIGHT_TOOLTIP, MIN_PX_VALUE, default_height,
                                          MAX_PX_VALUE)

        self._color_row = QWidget(self)
        self._color_row_layout = QHBoxLayout(self._color_row)
        self._color_row_layout.addWidget(QLabel(LABEL_TEXT_BACKGROUND_COLOR))
        self._color_dropdown = QComboBox()
        self._color_row_layout.addWidget(self._color_dropdown)

        self._color_button = ColorButton(parent=self)
        self._color_button.color = self._color
        self._color_button.setText(BUTTON_TEXT_PICK_CUSTOM_COLOR)
        self._color_button.setVisible(False)

        # Background color options:
        self._color_dropdown.addItem(get_color_icon(Qt.GlobalColor.transparent), BACKGROUND_COLOR_OPTION_TRANSPARENT)
        self._color_dropdown.addItem(get_color_icon(Qt.GlobalColor.white), BACKGROUND_COLOR_OPTION_WHITE)
        self._color_dropdown.addItem(get_color_icon(Qt.GlobalColor.black), BACKGROUND_COLOR_OPTION_BLACK)
        self._color_dropdown.addItem(_custom_color_icon(), BACKGROUND_COLOR_OPTION_CUSTOM)
        self._color_dropdown.currentTextChanged.connect(self._color_dropdown_change_slot)
        self._set_dropdown_to_color(self._color)

        self._button_row = QWidget(self)
        self._button_row_layout = QHBoxLayout(self._button_row)

        self._create_button = QPushButton(self)
        self._create_button.setText(CREATE_BUTTON_TEXT)
        self._create_button.clicked.connect(self._confirm)
        self._button_row_layout.addWidget(self._create_button)

        self._cancel_button = QPushButton(self)
        self._cancel_button.setText(CANCEL_BUTTON_TEXT)
        self._cancel_button.clicked.connect(self._cancel)
        self._button_row_layout.addWidget(self._cancel_button)


        self._layout = QVBoxLayout()
        for widget in [self._width_box, self._height_box, self._color_row, self._color_button, self._button_row]:
            self._layout.addWidget(widget)

        self.setLayout(self._layout)

    def _get_color_from_dropdown(self, dropdown_text: Optional[str] = None) -> QColor:
        if dropdown_text is None:
            dropdown_text = self._color_dropdown.currentText()
        if dropdown_text == BACKGROUND_COLOR_OPTION_TRANSPARENT:
            return QColor(Qt.GlobalColor.transparent)
        if dropdown_text == BACKGROUND_COLOR_OPTION_WHITE:
            return QColor(Qt.GlobalColor.white)
        if dropdown_text == BACKGROUND_COLOR_OPTION_BLACK:
            return QColor(Qt.GlobalColor.black)
        assert dropdown_text == BACKGROUND_COLOR_OPTION_CUSTOM
        return self._color_button.color

    def _set_dropdown_to_color(self, color: QColor) -> None:
        if color == Qt.GlobalColor.transparent:
            self._color_dropdown.setCurrentText(BACKGROUND_COLOR_OPTION_TRANSPARENT)
        elif color == Qt.GlobalColor.white:
            self._color_dropdown.setCurrentText(BACKGROUND_COLOR_OPTION_WHITE)
        elif color == Qt.GlobalColor.black:
            self._color_dropdown.setCurrentText(BACKGROUND_COLOR_OPTION_BLACK)
        else:
            self._color_dropdown.setCurrentText(BACKGROUND_COLOR_OPTION_CUSTOM)

    def _confirm(self) -> None:
        self._create = True
        color = self._get_color_from_dropdown()
        Cache().set(Cache.NEW_IMAGE_BACKGROUND_COLOR, color.name(QColor.NameFormat.HexArgb))
        self._color_button.disconnect_config()
        self.hide()

    def _cancel(self) -> None:
        self._create = False
        self._color_button.disconnect_config()
        self.hide()

    def _color_dropdown_change_slot(self, option_text: str) -> None:
        self._color_button.setVisible(option_text == BACKGROUND_COLOR_OPTION_CUSTOM)

    def show_image_modal(self) -> Optional[QSize]:
        """Shows the modal, then returns the user-entered size when closed."""
        self.exec()
        if self._create:
            return QSize(self._width_box.spinbox.value(), self._height_box.spinbox.value())
        return None
