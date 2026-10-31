"""Popup modal for naming a saved panel layout."""
from typing import Optional

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QLineEdit, QVBoxLayout, QWidget

from src.ui.modal.dialog_footer import DialogFooter
from src.ui.modal.modal_utils import request_confirmation
from src.util.shared_constants import APP_ICON_PATH

# The QCoreApplication.translate context for strings in this file
TR_ID = 'ui.modal.layout_name_modal'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


TITLE_SAVE = _tr('Save panel layout')
TITLE_RENAME = _tr('Rename panel layout')
LABEL_NAME = _tr('Layout name:')
BUTTON_SAVE = _tr('Save layout')
ERROR_EMPTY_NAME = _tr('Enter a name for the layout.')
TITLE_CONFIRM_OVERWRITE = _tr('Replace layout?')
MESSAGE_CONFIRM_OVERWRITE = _tr('A layout named "{layout_name}" already exists. Replace it?')


class LayoutNameModal(QDialog):
    """Asks for a layout name. `name` holds the trimmed result once the dialog is accepted."""

    def __init__(self, title: str, default_name: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setWindowTitle(title)
        self.setModal(True)
        self.name: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(LABEL_NAME, self))
        self._name_input = QLineEdit(default_name, self)
        self._name_input.selectAll()
        layout.addWidget(self._name_input)
        self._status = QLabel(self)
        layout.addWidget(self._status)

        footer = DialogFooter(BUTTON_SAVE, self)
        footer.accepted.connect(self._accept_name)
        footer.rejected.connect(self.reject)
        layout.addWidget(footer)
        self._name_input.returnPressed.connect(self._accept_name)

    def _accept_name(self) -> None:
        """Accepts the entered name, or shows why it is rejected."""
        name = self._name_input.text().strip()
        if name == '':
            self._status.setText(ERROR_EMPTY_NAME)
            return
        self.name = name
        self.accept()


def confirm_overwrite(parent: Optional[QWidget], name: str) -> bool:
    """Asks whether to replace the existing layout with this name."""
    return request_confirmation(parent, TITLE_CONFIRM_OVERWRITE,
                                MESSAGE_CONFIRM_OVERWRITE.format(layout_name=name), discards_work=True)


def prompt_layout_name(parent: Optional[QWidget], title: str, default_name: str, existing_names: set[str],
                       allowed_existing: Optional[str] = None) -> Optional[str]:
    """Asks for a layout name until the user cancels or the name is free or confirmed for replacement.

    `allowed_existing` is a name that can be kept without confirmation, such as the name being renamed.
    Returns the trimmed name, or None if the user cancelled.
    """
    default = default_name
    while True:
        modal = LayoutNameModal(title, default, parent)
        if modal.exec() != QDialog.DialogCode.Accepted or modal.name is None:
            return None
        name = modal.name
        if name == allowed_existing or name not in existing_names or confirm_overwrite(parent, name):
            return name
        default = name
