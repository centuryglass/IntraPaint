"""A color dialog built on the color picker's parts, comparing the new color with the starting one.

The dialog has one arrangement: the header, the ring beside the sliders and saved colors, then the recent colors.
"""
from typing import Optional

from PySide6.QtGui import QColor, QKeyEvent
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QApplication, QDialogButtonBox, QWidget

from src.ui.widget.color_picker.color_comparison import ColorComparison
from src.ui.modal.modal_parent import modal_parent
from src.ui.widget.color_picker.color_picker_parts import ColorPickerParts
from src.util.layout import add_layout


# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.modal.color_dialog'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


COLOR_DIALOG_TITLE = _tr('Select Color')

RING_MIN_SIZE = 260


class _PickerArea(QWidget):
    """Holds the picker's parts, and keeps Escape in a field from closing the dialog."""

    def keyPressEvent(self, event: Optional[QKeyEvent]) -> None:  # pylint: disable=invalid-name
        """Accepts every key that reaches the picker, so the dialog never closes on one."""


class ColorDialog(QDialog):
    """A color dialog built on the color picker's parts, comparing the new color with the starting one."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(modal_parent(parent))
        self.setWindowTitle(COLOR_DIALOG_TITLE)

        self._comparison = ColorComparison()
        self._color_picker = ColorPickerParts(self._comparison, parent=self)
        self._color_picker.color_selected.connect(self._comparison.set_color)
        self._comparison.revert_requested.connect(self._color_picker.set_current_color)
        self._layout = QVBoxLayout(self)
        picker_area = _PickerArea()
        picker_layout = QVBoxLayout(picker_area)
        picker_layout.setContentsMargins(0, 0, 0, 0)
        parts = self._color_picker
        picker_layout.addWidget(parts.header)
        row = QHBoxLayout()
        add_layout(picker_layout, row, 1)
        parts.ring_square.setMinimumSize(RING_MIN_SIZE, RING_MIN_SIZE)
        row.addWidget(parts.ring_square, stretch=1)
        column = QVBoxLayout()
        add_layout(row, column, 1)
        column.addWidget(parts.slider_block)
        column.addWidget(parts.saved_colors_panel, stretch=1)
        picker_layout.addWidget(parts.recent_colors_row)
        self._layout.addWidget(picker_area, stretch=1)

        # noinspection PyTypeChecker
        self._button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        self._button_box.accepted.connect(self.accept)
        self._button_box.rejected.connect(self.reject)
        self._layout.addWidget(self._button_box)

    @property
    def color_picker(self) -> ColorPickerParts:
        """The dialog's color picker."""
        return self._color_picker

    @property
    def comparison(self) -> ColorComparison:
        """The starting and new colors, side by side."""
        return self._comparison

    @property
    def selected_color(self) -> QColor:
        """Accesses the current selected color."""
        return self._color_picker.selected_color()

    @selected_color.setter
    def selected_color(self, new_color: QColor) -> None:
        """Accesses the current selected color."""
        self._color_picker.set_current_color(new_color)

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
        selection = dialog.selected_color if dialog.result() == QDialog.DialogCode.Accepted else None
        dialog.deleteLater()
        return selection
