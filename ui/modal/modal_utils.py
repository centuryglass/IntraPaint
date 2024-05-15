"""
Provides simple popup windows for error messages, requesting confirmation, and loading images.
"""
import sys
import traceback
from PyQt5.QtWidgets import QMessageBox, QFileDialog
from PIL import UnidentifiedImageError


def show_error_dialog(parent, title, error):
    """Opens a message box to show some text to the user."""
    print(f'Error: {error}')
    if hasattr(error, '__traceback__'):
        traceback.print_exception(type(error), error, error.__traceback__)
    messagebox = QMessageBox(parent)
    messagebox.setWindowTitle(title)
    messagebox.setText(f'{error}')
    messagebox.setStandardButtons(QMessageBox.Ok)
    messagebox.exec()

def request_confirmation(parent, title, message):
    """Requests confirmation from the user, returns whether that confirmation was granted."""
    confirmbox = QMessageBox(parent)
    confirmbox.setWindowTitle(title)
    confirmbox.setText(message)
    confirmbox.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
    response = confirmbox.exec()
    return bool(response == QMessageBox.Ok)

def open_image_file(parent, mode='load', selected_file=''):
    """Opens an image file for editing, saving, etc."""
    is_pyinstaller_bundle = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')
    options = QFileDialog.Option.DontUseNativeDialog if is_pyinstaller_bundle else None
    try:
        if mode == 'load':
            return QFileDialog.getOpenFileName(parent, 'Open Image', options)
        if mode == 'save':
            png_filter = 'Images (*.png)'
            return QFileDialog.getSaveFileName(parent, 'Save Image', selected_file, filter=png_filter)
        raise ValueError(f'invalid file access mode {mode}')
    except (ValueError, UnidentifiedImageError) as err:
        show_error_dialog(parent, 'Open failed', err)
    return (None, None)
