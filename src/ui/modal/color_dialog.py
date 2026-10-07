"""A color dialog built on TabbedColorPicker, comparing the new color with the starting one."""
from typing import Optional

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog, QVBoxLayout, QApplication, QDialogButtonBox

from src.ui.widget.color_picker.color_comparison import ColorComparison
from src.ui.widget.color_picker.tabbed_color_picker import TabbedColorPicker, ColorPickerLayout


# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.modal.color_dialog'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


COLOR_DIALOG_TITLE = _tr('Select Color')


class ColorDialog(QDialog):
    """A color dialog built on TabbedColorPicker, comparing the new color with the starting one."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(COLOR_DIALOG_TITLE)

        self._comparison = ColorComparison()
        self._colorPicker = TabbedColorPicker(self._comparison, ColorPickerLayout.DIALOG)
        self._colorPicker.color_selected.connect(self._comparison.set_color)
        self._comparison.revert_requested.connect(self._colorPicker.set_current_color)
        self._layout = QVBoxLayout(self)
        self._layout.addWidget(self._colorPicker)

        # noinspection PyTypeChecker
        self._button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        self._button_box.accepted.connect(self.accept)
        self._button_box.rejected.connect(self.reject)
        self._layout.addWidget(self._button_box)

    @property
    def color_picker(self) -> TabbedColorPicker:
        """The dialog's color picker."""
        return self._colorPicker

    @property
    def comparison(self) -> ColorComparison:
        """The starting and new colors, side by side."""
        return self._comparison

    @property
    def selected_color(self) -> QColor:
        """Accesses the current selected color."""
        return self._colorPicker.selected_color()

    @selected_color.setter
    def selected_color(self, new_color: QColor) -> None:
        """Accesses the current selected color."""
        self._colorPicker.set_current_color(new_color)

    @staticmethod
    def show_color_dialog(initial_color: QColor) -> Optional[QColor]:
        """
        Opens a color dialog, and returns the selected color.

        Parameters
        ----------
            initial_color: QColor
                The color that should be shown as selected in the new dialog
        Return
        ------
            selected_color: Optional[QColor]
                The color the user selected, or None if the user did not click the "Ok" button to close the dialog.
        """
        dialog = ColorDialog()
        dialog.selected_color = initial_color
        dialog.comparison.set_original(initial_color)
        dialog.comparison.set_color(initial_color)
        dialog.exec()
        if dialog.result() == QDialog.DialogCode.Accepted:
            return dialog.selected_color
        return None
