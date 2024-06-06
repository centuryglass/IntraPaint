"""
Provides simple popup windows for error messages, requesting confirmation, and loading images.
"""
import sys
import traceback
import logging
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QWidget
from PIL import UnidentifiedImageError

logger = logging.getLogger(__name__)

LOAD_IMAGE_MODE = 'load'
SAVE_IMAGE_MODE = 'save'
LOAD_IMAGE_TITLE = 'Open Image'
SAVE_IMAGE_TITLE = 'Save Image'
LOAD_IMAGE_ERROR_MSG = 'Open failed'
PNG_IMAGE_FILTER = 'Images (*.png *.inpt)'


def show_error_dialog(parent: QWidget, title: str, error: str | BaseException) -> None:
    """Opens a message box to show some text to the user."""
    logger.error(f'Error: {error}')
    if isinstance(error, BaseException) and hasattr(error, '__traceback__'):
        traceback.print_exception(type(error), error, error.__traceback__)
    messagebox = QMessageBox(parent)
    messagebox.setWindowTitle(title)
    messagebox.setText(f'{error}')
    messagebox.setStandardButtons(QMessageBox.Ok)
    messagebox.exec()


def request_confirmation(parent: QWidget, title: str, message: str) -> bool:
    """Requests confirmation from the user, returns whether that confirmation was granted."""
    confirm_box = QMessageBox(parent)
    confirm_box.setWindowTitle(title)
    confirm_box.setText(message)
    confirm_box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
    response = confirm_box.exec()
    return bool(response == QMessageBox.Ok)


def open_image_file(parent: QWidget, mode: str = 'load',
                    selected_file: str = '') -> tuple[str, str] | tuple[None, None]:
    """Opens an image file for editing, saving, etc."""
    is_pyinstaller_bundle = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')
    options = QFileDialog.Option.DontUseNativeDialog if is_pyinstaller_bundle else None
    try:
        if mode == LOAD_IMAGE_MODE:
            return QFileDialog.getOpenFileName(parent, LOAD_IMAGE_TITLE, options)
        if mode == SAVE_IMAGE_MODE:
            png_filter = PNG_IMAGE_FILTER
            return QFileDialog.getSaveFileName(parent, SAVE_IMAGE_TITLE, selected_file, filter=png_filter)
        raise ValueError(f'invalid file access mode {mode}')
    except (ValueError, UnidentifiedImageError) as err:
        show_error_dialog(parent, LOAD_IMAGE_ERROR_MSG, err)
    return None, None
