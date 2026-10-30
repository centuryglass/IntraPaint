"""Popup modal for applying, renaming and deleting saved panel layouts."""
from typing import Callable, Optional

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget)

from src.ui.modal.layout_name_modal import TITLE_RENAME, prompt_layout_name
from src.ui.modal.modal_utils import request_confirmation
from src.ui.window import saved_layouts
from src.util.shared_constants import APP_ICON_PATH

# The QCoreApplication.translate context for strings in this file
TR_ID = 'ui.modal.manage_layouts_modal'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


TITLE_MANAGE = _tr('Manage panel layouts')
BUTTON_APPLY = _tr('Apply')
BUTTON_RENAME = _tr('Rename')
BUTTON_DELETE = _tr('Delete')
BUTTON_CLOSE = _tr('Close')
TITLE_CONFIRM_DELETE = _tr('Delete layout?')
MESSAGE_CONFIRM_DELETE = _tr('Delete the layout "{layout_name}"?')


class ManageLayoutsModal(QDialog):
    """Lists the saved layouts, with buttons to apply, rename and delete the selected one."""

    def __init__(self, apply_layout: Callable[[str], None], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setWindowTitle(TITLE_MANAGE)
        self.setModal(True)
        self._apply_layout = apply_layout

        layout = QVBoxLayout(self)
        self._list = QListWidget(self)
        layout.addWidget(self._list)
        button_row = QHBoxLayout()
        self._apply_button = QPushButton(BUTTON_APPLY, self)
        self._rename_button = QPushButton(BUTTON_RENAME, self)
        self._delete_button = QPushButton(BUTTON_DELETE, self)
        close_button = QPushButton(BUTTON_CLOSE, self)
        for button in (self._apply_button, self._rename_button, self._delete_button, close_button):
            button_row.addWidget(button)
        layout.addLayout(button_row)

        self._apply_button.clicked.connect(self.apply_selected)
        self._rename_button.clicked.connect(self.rename_selected)
        self._delete_button.clicked.connect(self.delete_selected)
        close_button.clicked.connect(self.accept)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._list.currentRowChanged.connect(self._on_row_changed)
        self.refresh()

    def refresh(self) -> None:
        """Reloads the list from the saved layouts, keeping the selection where it still exists."""
        selected = self.selected_name()
        self._list.clear()
        self._list.addItems(saved_layouts.layout_names())
        names = saved_layouts.layout_names()
        if selected in names:
            self._list.setCurrentRow(names.index(selected))
        elif names:
            self._list.setCurrentRow(0)
        self._update_buttons()

    def selected_name(self) -> Optional[str]:
        """Returns the selected layout's name, if any."""
        item = self._list.currentItem()
        return None if item is None else item.text()

    def _on_item_double_clicked(self, _item: QListWidgetItem) -> None:
        self.apply_selected()

    def _on_row_changed(self, _row: int) -> None:
        self._update_buttons()

    def _update_buttons(self) -> None:
        has_selection = self.selected_name() is not None
        for button in (self._apply_button, self._rename_button, self._delete_button):
            button.setEnabled(has_selection)

    def apply_selected(self) -> None:
        """Applies the selected layout and closes the dialog."""
        name = self.selected_name()
        if name is None:
            return
        self.accept()
        self._apply_layout(name)

    def rename_selected(self) -> None:
        """Asks for a new name for the selected layout, confirming before it replaces another layout."""
        name = self.selected_name()
        if name is None:
            return
        new_name = prompt_layout_name(self, TITLE_RENAME, name, set(saved_layouts.layout_names()),
                                      allowed_existing=name)
        if new_name is not None and new_name != name:
            saved_layouts.rename_layout(name, new_name)
            self.refresh()

    def delete_selected(self) -> None:
        """Deletes the selected layout after one confirmation."""
        name = self.selected_name()
        if name is None:
            return
        if request_confirmation(self, TITLE_CONFIRM_DELETE, MESSAGE_CONFIRM_DELETE.format(layout_name=name),
                                discards_work=True):
            saved_layouts.delete_layout(name)
            self.refresh()
