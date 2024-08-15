"""
Provides simple popup windows for error messages, requesting confirmation, and loading images.
"""
import logging
import os
import sys
import traceback
from typing import Optional, Set

from PIL import UnidentifiedImageError
from PySide6.QtWidgets import QMessageBox, QFileDialog, QWidget, QStyle, QApplication

from src.config.application_config import AppConfig
from src.ui.input_fields.check_box import CheckBox
from src.util.image_utils import get_standard_qt_icon, IMAGE_WRITE_FORMATS, IMAGE_READ_FORMATS, OPENRASTER_FORMAT

logger = logging.getLogger(__name__)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.modal.modal_utils'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


LOAD_IMAGE_TITLE = _tr('Open Image')
LOAD_LAYER_TITLE = _tr('Open Images as Layers')
SAVE_IMAGE_TITLE = _tr('Save Image')
LOAD_IMAGE_ERROR_MSG = _tr('Open failed')

IMAGE_FORMATS_DESCRIPTION = _tr('Images and IntraPaint projects')
LAYER_FORMATS_DESCRIPTION = _tr('Images')

DO_NOT_WARN_AGAIN_CHECKBOX_MESSAGE = _tr('Don\'t show this again')


def _extension_set_to_filter_string(str_set: Set[str]) -> str:
    format_list = [f'*.{file_format.lower()}' for file_format in str_set]
    format_list.sort()
    return f'({' '.join(format_list)})'


SAVE_FILE_FORMATS = _extension_set_to_filter_string(IMAGE_WRITE_FORMATS)
LOAD_FILE_FORMATS = _extension_set_to_filter_string(IMAGE_READ_FORMATS)
LOAD_LAYER_FORMATS = _extension_set_to_filter_string({file_format for file_format in IMAGE_READ_FORMATS
                                                      if file_format != OPENRASTER_FORMAT})

IMAGE_SAVE_FILTER = f'{IMAGE_FORMATS_DESCRIPTION} {SAVE_FILE_FORMATS}'
IMAGE_LOAD_FILTER = f'{IMAGE_FORMATS_DESCRIPTION} {LOAD_FILE_FORMATS}'
LAYER_LOAD_FILTER = f'{LAYER_FORMATS_DESCRIPTION} {LOAD_LAYER_FORMATS}'

LOAD_IMAGE_MODE = 'load'
SAVE_IMAGE_MODE = 'save'


def show_error_dialog(parent: Optional[QWidget], title: str, error: str | BaseException) -> None:
    """Opens a message box to show some text to the user."""
    logger.error(f'Error: {error}')
    if isinstance(error, BaseException) and hasattr(error, '__traceback__'):
        traceback.print_exception(type(error), error, error.__traceback__)
    messagebox = QMessageBox(parent)
    messagebox.setWindowTitle(title)
    messagebox.setText(f'{error}')
    messagebox.setWindowIcon(get_standard_qt_icon(QStyle.StandardPixmap.SP_MessageBoxWarning, parent))
    messagebox.setIcon(QMessageBox.Icon.Critical)
    messagebox.setStandardButtons(QMessageBox.StandardButton.Ok)
    messagebox.exec()


def show_warning_dialog(parent: Optional[QWidget], title: str, message: str,
                        reminder_config_key: Optional[str]) -> None:
    """Show a warning dialog, optionally with a 'don't show again' checkbox"""
    if reminder_config_key is not None and not AppConfig().get(reminder_config_key):
        return  # Warning already disabled
    messagebox = QMessageBox(parent)
    messagebox.setWindowTitle(title)
    messagebox.setText(message)
    messagebox.setWindowIcon(get_standard_qt_icon(QStyle.StandardPixmap.SP_MessageBoxWarning, parent))
    messagebox.setIcon(QMessageBox.Icon.Critical)
    if reminder_config_key is not None:
        checkbox = CheckBox()
        checkbox.setText(DO_NOT_WARN_AGAIN_CHECKBOX_MESSAGE)
        checkbox.valueChanged.connect(lambda is_checked: AppConfig().set(reminder_config_key, not is_checked))
        messagebox.setCheckBox(checkbox)
    messagebox.setStandardButtons(QMessageBox.StandardButton.Ok)
    messagebox.exec()


def request_confirmation(parent: QWidget, title: str, message: str) -> bool:
    """Requests confirmation from the user, returns whether that confirmation was granted."""
    confirm_box = QMessageBox(parent)
    confirm_box.setWindowTitle(title)
    confirm_box.setText(message)
    confirm_box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
    confirm_box.setWindowIcon(get_standard_qt_icon(QStyle.StandardPixmap.SP_MessageBoxQuestion, parent))
    response = confirm_box.exec()
    return bool(response == QMessageBox.StandardButton.Ok)


def open_image_file(parent: QWidget, mode: str = 'load',
                    selected_file: str = '') -> Optional[str]:
    """Opens an image file for editing, saving, etc."""
    is_pyinstaller_bundle = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')
    file_filter = IMAGE_LOAD_FILTER if mode == LOAD_IMAGE_MODE else IMAGE_SAVE_FILTER
    file_dialog = QFileDialog(parent, filter=file_filter)
    if os.path.isfile(selected_file):
        file_dialog.selectFile(selected_file)
    if mode == LOAD_IMAGE_MODE:
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        file_dialog.setViewMode(QFileDialog.ViewMode.Detail)
    else:
        assert mode == SAVE_IMAGE_MODE
        file_dialog.setFileMode(QFileDialog.FileMode.AnyFile)
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
    if is_pyinstaller_bundle:
        file_dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    try:
        if file_dialog.exec():
            return file_dialog.selectedFiles()[0]
        return None
    except (ValueError, UnidentifiedImageError) as err:
        show_error_dialog(parent, LOAD_IMAGE_ERROR_MSG, err)
    return None


def open_image_layers(parent: QWidget) -> tuple[list[str], str] | tuple[None, None]:
    """Opens multiple image files to import as layers."""
    is_pyinstaller_bundle = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')
    options = str(QFileDialog.Option.DontUseNativeDialog) if is_pyinstaller_bundle else None
    return QFileDialog.getOpenFileNames(parent, LOAD_LAYER_TITLE, options, filter=LAYER_LOAD_FILTER)
