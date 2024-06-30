"""
Provides simple popup windows for error messages, requesting confirmation, and loading images.
"""
import sys
import traceback
import logging
from typing import Optional

from PyQt5.QtWidgets import QMessageBox, QFileDialog, QWidget, QStyle
from PIL import UnidentifiedImageError

from src.util.image_utils import get_standard_qt_icon

logger = logging.getLogger(__name__)

LOAD_IMAGE_MODE = 'load'
SAVE_IMAGE_MODE = 'save'
LOAD_IMAGE_TITLE = 'Open Image'
LOAD_LAYER_TITLE = 'Open Images as Layers'
SAVE_IMAGE_TITLE = 'Save Image'
LOAD_IMAGE_ERROR_MSG = 'Open failed'
IMAGE_SAVE_FILTER = 'Images and IntraPaint projects (*.png *.inpt)'
IMAGE_LOAD_FILTER = ('Images and IntraPaint projects (*.bmp *.gif *.jpg *.jpeg *.png *.pbm *.pgm *.ppm *.xbm *.xpm'
                     ' *.inpt)')
LAYER_LOAD_FILTER = 'Images (*.bmp *.gif *.jpg *.jpeg *.png *.pbm *.pgm *.ppm *.xbm *.xpm *.inpt)'


def show_error_dialog(parent: Optional[QWidget], title: str, error: str | BaseException) -> None:
    """Opens a message box to show some text to the user."""
    logger.error(f'Error: {error}')
    if isinstance(error, BaseException) and hasattr(error, '__traceback__'):
        traceback.print_exception(type(error), error, error.__traceback__)
    messagebox = QMessageBox(parent)
    messagebox.setWindowTitle(title)
    messagebox.setText(f'{error}')
    messagebox.setWindowIcon(get_standard_qt_icon(QStyle.SP_MessageBoxWarning, parent))
    messagebox.setIcon(QMessageBox.Icon.Critical)
    messagebox.setStandardButtons(QMessageBox.Ok)
    messagebox.exec()


def request_confirmation(parent: QWidget, title: str, message: str) -> bool:
    """Requests confirmation from the user, returns whether that confirmation was granted."""
    confirm_box = QMessageBox(parent)
    confirm_box.setWindowTitle(title)
    confirm_box.setText(message)
    confirm_box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
    confirm_box.setWindowIcon(get_standard_qt_icon(QStyle.SP_MessageBoxQuestion, parent))
    response = confirm_box.exec()
    return bool(response == QMessageBox.Ok)


def open_image_file(parent: QWidget, mode: str = 'load',
                    selected_file: str = '') -> tuple[str, str] | tuple[None, None]:
    """Opens an image file for editing, saving, etc."""
    is_pyinstaller_bundle = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')
    options = str(QFileDialog.Option.DontUseNativeDialog) if is_pyinstaller_bundle else None
    try:
        if mode == LOAD_IMAGE_MODE:
            return QFileDialog.getOpenFileNames(parent, LOAD_IMAGE_TITLE, options, filter=IMAGE_LOAD_FILTER)
        if mode == SAVE_IMAGE_MODE:
            return QFileDialog.getSaveFileName(parent, SAVE_IMAGE_TITLE, selected_file, filter=IMAGE_SAVE_FILTER)
        raise ValueError(f'invalid file access mode {mode}')
    except (ValueError, UnidentifiedImageError) as err:
        show_error_dialog(parent, LOAD_IMAGE_ERROR_MSG, err)
    return None, None


def open_image_layers(parent: QWidget) -> tuple[list[str], str] | tuple[None, None]:
    """Opens multiple image files to import as layers."""
    is_pyinstaller_bundle = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')
    options = str(QFileDialog.Option.DontUseNativeDialog) if is_pyinstaller_bundle else None
    return QFileDialog.getOpenFileNames(parent, LOAD_LAYER_TITLE, options, filter=LAYER_LOAD_FILTER)
