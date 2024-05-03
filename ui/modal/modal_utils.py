"""
Provides simple popup windows for error messages, requesting confirmation, and loading images.
"""
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QMessageBox
from PyQt5.QtCore import QPoint, QRect, QSize, QMargins
import sys, traceback


def show_error_dialog(parent, title, error):
    """Opens a message box to show some text to the user."""
    print(f"Error: {error}")
    if hasattr(error, '__traceback__'):
        traceback.print_exception(type(error), error, error.__traceback__)
    messagebox = QMessageBox(parent)
    messagebox.setWindowTitle(title)
    messagebox.setText(f"{error}")
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
    is_pyinstaller_bundle = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')
    options = QFileDialog.Option.DontUseNativeDialog if is_pyinstaller_bundle else None
    try:
        file, file_selected = (None, None)
        if mode == 'load':
            return QFileDialog.getOpenFileName(parent, 'Open Image', options)
        elif mode == 'save':
            pngFilter = "Images (*.png)"
            return QFileDialog.getSaveFileName(parent, 'Save Image', selected_file, filter=pngFilter)
        else:
            raise Exception(f"invalid file access mode {mode}")
    except Exception as err:
        show_error_dialog(parent, "Open failed", err)
