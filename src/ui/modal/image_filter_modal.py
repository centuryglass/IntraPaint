"""Popup modal window that applies an arbitrary image filtering action."""
from typing import List, Callable, Optional, TypeAlias, Any

from PyQt5.QtCore import QSize
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QDialog, QFormLayout, QLabel, QWidget, QCheckBox, QHBoxLayout, QPushButton

from src.ui.widget.image_widget import ImageWidget
from src.util.parameter import Parameter

SELECTED_ONLY_LABEL = 'Change selected areas only'
ACTIVE_ONLY_LABEL = 'Change active layer only'
MIN_PREVIEW_SIZE = 450
CANCEL_BUTTON_TEXT = 'Cancel'
APPLY_BUTTON_TEXT = 'Apply'

# parameters: filter_param_values: list, filter_selection_only: bool, filter_active_layer_only: bool
FilterFunction: TypeAlias = Callable[[List[Any], bool, bool], Optional[QImage]]


class ImageFilterModal(QDialog):
    """Popup modal window that applies an arbitrary image filtering action."""

    def __init__(self,
                 title: str,
                 description: str,
                 parameters: List[Parameter],
                 generate_preview: FilterFunction,
                 apply_filter: FilterFunction,
                 filter_selection_only_default: bool = True,
                 filter_active_layer_only_default: bool = True) -> None:
        super().__init__()
        self.setModal(True)
        self._preview = ImageWidget(None, self)
        self._preview.setMinimumSize(QSize(MIN_PREVIEW_SIZE, MIN_PREVIEW_SIZE))
        self._layout = QFormLayout(self)
        self._param_inputs: List[QWidget] = []
        self._generate_preview = generate_preview
        self._apply_filter = apply_filter

        self.setWindowTitle(title)
        self._layout.addWidget(QLabel(description))
        for param in parameters:
            field_widget = param.get_input_widget()
            self._param_inputs.append(field_widget)
            self._layout.addRow(param.name, field_widget)
            field_widget.valueChanged.connect(self._update_preview)

        self._selected_only_checkbox = QCheckBox()
        self._layout.addRow(self._selected_only_checkbox)
        self._selected_only_checkbox.setText(SELECTED_ONLY_LABEL)
        self._selected_only_checkbox.setChecked(filter_selection_only_default)
        self._selected_only_checkbox.stateChanged.connect(self._update_preview)

        self._active_only_checkbox = QCheckBox()
        self._layout.addRow(self._active_only_checkbox)
        self._active_only_checkbox.setText(ACTIVE_ONLY_LABEL)
        self._active_only_checkbox.setChecked(filter_active_layer_only_default)
        self._active_only_checkbox.stateChanged.connect(self._update_preview)

        self._layout.addRow(self._preview)
        self._button_row = QWidget()
        button_layout = QHBoxLayout(self._button_row)
        self._cancel_button = QPushButton()
        self._cancel_button.setText(CANCEL_BUTTON_TEXT)
        self._cancel_button.clicked.connect(lambda: self.close())
        button_layout.addWidget(self._cancel_button)
        self._apply_button = QPushButton()
        self._apply_button.setText(APPLY_BUTTON_TEXT)
        self._apply_button.clicked.connect(self._apply_change)
        button_layout.addWidget(self._apply_button)
        self._layout.addWidget(self._button_row)
        self._update_preview()

    def _update_preview(self, _=None) -> None:
        param_values = [widget.value() for widget in self._param_inputs]
        filter_selection_only = self._selected_only_checkbox.isChecked()
        filter_active_layer_only = self._active_only_checkbox.isChecked()
        self._preview.image = self._generate_preview(param_values, filter_selection_only, filter_active_layer_only)

    def _apply_change(self) -> None:
        param_values = [widget.value() for widget in self._param_inputs]
        filter_selection_only = self._selected_only_checkbox.isChecked()
        filter_active_layer_only = self._active_only_checkbox.isChecked()
        self._apply_filter(param_values, filter_selection_only, filter_active_layer_only)
        self.close()
