from PyQt5.QtWidgets import QMessageBox, QFileDialog, QMessageBox
from PyQt5.QtCore import QPoint, QRect, QSize, QMargins
import sys, traceback


def showErrorDialog(parent, title, error):
    """Opens a message box to show some text to the user."""
    print(f"Error: {error}")
    if hasattr(error, '__traceback__'):
        traceback.print_exception(type(error), error, error.__traceback__)
    messageBox = QMessageBox(parent)
    messageBox.setWindowTitle(title)
    messageBox.setText(f"{error}")
    messageBox.setStandardButtons(QMessageBox.Ok)
    messageBox.exec()

def requestConfirmation(parent, title, message):
    """Requests confirmation from the user, returns whether that confirmation was granted."""
    confirmBox = QMessageBox(parent)
    confirmBox.setWindowTitle(title)
    confirmBox.setText(message)
    confirmBox.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
    response = confirmBox.exec()
    return bool(response == QMessageBox.Ok)

def openImageFile(parent, mode='load', selectedFile=''):
    isPyinstallerBundle = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')
    options = QFileDialog.Option.DontUseNativeDialog if isPyinstallerBundle else None
    try:
        file, fileSelected = (None, None)
        if mode == 'load':
            return QFileDialog.getOpenFileName(parent, 'Open Image', options)
        elif mode == 'save':
            pngFilter = "Images (*.png)"
            return QFileDialog.getSaveFileName(parent, 'Save Image', selectedFile, filter=pngFilter)
        else:
            raise Exception(f"invalid file access mode {mode}")
    except Exception as err:
        showErrorDialog(parent, "Open failed", err)