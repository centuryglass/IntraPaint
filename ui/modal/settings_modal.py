"""
Popup modal providing a dynamic settings interface, to be populated by the controller. Currently only used with
stable_diffusion_controller.
"""
from typing import Any
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QComboBox, QDoubleSpinBox, \
         QCheckBox, QWidget
from PyQt5.QtCore import pyqtSignal
from ui.widget.bordered_widget import BorderedWidget
from ui.widget.collapsible_box import CollapsibleBox
from ui.widget.big_int_spinbox import BigIntSpinbox
from ui.widget.label_wrapper import LabelWrapper


class SettingsModal(QDialog):
    """Manage remote settings."""

    changes_saved = pyqtSignal(dict)

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setModal(True)

        self._panels = {}
        self._panel_layouts = {}
        self._inputs = {}
        self._changes = {}
        self._panel_layout = QVBoxLayout()

        layout = QVBoxLayout()
        self.setLayout(layout)

        panel_widget = BorderedWidget(self)
        panel_widget.setLayout(self._panel_layout)
        layout.addWidget(panel_widget, stretch=20)

        bottom_panel = BorderedWidget(self)
        bottom_panel_layout = QHBoxLayout()
        bottom_panel.setLayout(bottom_panel_layout)
        bottom_panel_layout.addSpacing(300)

        cancel_button = QPushButton()
        cancel_button.setText('Cancel')
        cancel_button.clicked.connect(self.hide)
        bottom_panel_layout.addWidget(cancel_button, stretch=1)

        save_button = QPushButton()
        save_button.setText('Save')
        def on_save():
            self.changes_saved.emit(self._changes)
            self.hide()
        save_button.clicked.connect(on_save)
        bottom_panel_layout.addWidget(save_button, stretch=1)
        layout.addWidget(bottom_panel, stretch=1)


    def show_modal(self):
        """Shows the settings modal."""
        self.exec_()


    def set_tooltip(self, setting_name: str, tooltip: str):
        """Sets tooltip text for a setting.

        Parameters
        ----------
        setting_name : str
            Name of the setting being explained.
        tooltip : str
            Text explaining the updated setting, to be shown when the mouse hovers over the setting's control widget.
        """
        if setting_name not in self._inputs:
            raise ValueError(f'{setting_name} not defined')
        self._inputs[setting_name].setToolTip(tooltip)


    def update_settings(self, settings: dict):
        """Sets all setting control widgets to match current settings values.

        Parameters
        ----------
        settings : dict
            Current state of all settings.
        """
        for key in settings:
            if key not in self._inputs:
                continue
            widget = self._inputs[key]
            if isinstance(widget, QLineEdit):
                widget.setText(settings[key])
            elif isinstance(widget, QComboBox):
                widget.setCurrentIndex(widget.findText(settings[key]))
            elif isinstance(widget, QDoubleSpinBox):
                widget.setValue(float(settings[key]))
            elif isinstance(widget, BigIntSpinbox):
                widget.setValue(int(settings[key]))
            elif isinstance(widget, QCheckBox):
                widget.setChecked(settings[key])
            if key in self._changes:
                del self._changes[key]


    def add_text_setting(self,
            setting_name: str,
            panel_name: str,
            initial_value: Any,
            label_text: str):
        """Adds a new setting that accepts an arbitrary text value.

        Parameters
        ----------
        setting_name : str
            Key string used when tracking the setting.
        panel_name : str
            Setting category that this item should be shown within.
        initial_value : str
            Initial value of the text setting.
        label_text : str
            Setting display name to show in the UI.
        """
        textbox = QLineEdit()
        textbox.setText(initial_value)
        textbox.textChanged.connect(lambda: self._add_change(setting_name, textbox.text()))
        self._add_setting(setting_name, panel_name, textbox, label_text)


    def add_combobox_setting(self,
            setting_name: str,
            panel_name: str,
            initial_value: str,
            options: list[str],
            label_text: str):
        """Adds a new setting that accepts one of several pre-determined options.

        Parameters
        ----------
        setting_name : str
            Key string used when tracking the setting.
        panel_name : str
            Setting category that this item should be shown within.
        initial_value : str
            Initial value of the setting, must be one of the values within the options parameter.
        options : list of str
            All options to be listed in the combobox.
        label_text : str
            Setting display name to show in the UI.
        """
        combobox = QComboBox()
        if initial_value is not None and initial_value not in options:
            options.append(initial_value)
        for option in options:
            if isinstance(option, dict):
                combobox.addItem(option['text'])
            else:
                combobox.addItem(option)
        def update_value(selected_index):
            self._add_change(setting_name, options[selected_index])
        combobox.setCurrentIndex(options.index(initial_value))
        combobox.currentIndexChanged.connect(update_value)
        self._add_setting(setting_name, panel_name, combobox, label_text)


    def add_spinbox_setting(self,
            setting_name: str,
            panel_name: str,
            initial_value: int | float,
            min_value: int | float,
            max_value: int | float,
            label_text: str):
        """Adds a new numeric setting.

        Parameters
        ----------
        setting_name : str
            Key string used when tracking the setting.
        panel_name : str
            Setting category that this item should be shown within.
        initial_value : int or float
            Initial value of the text setting.
        min_value : int or float
            Smallest valid value accepted.
        max_value : int or float
            Largest valid value accepted.
        label_text : str
            Setting display name to show in the UI.
        """
        spinbox = QDoubleSpinBox() if isinstance(initial_value, float) else BigIntSpinbox()
        spinbox.setRange(min_value, max_value)
        spinbox.setValue(initial_value)
        spinbox.valueChanged.connect(lambda newValue: self._add_change(setting_name, newValue))
        self._add_setting(setting_name, panel_name, spinbox, label_text)


    def add_checkbox_setting(self,
            setting_name: str,
            panel_name: str,
            initial_value: bool,
            label_text: str):
        """Adds a new checkbox setting.

        Parameters
        ----------
        setting_name : str
            Key string used when tracking the setting.
        panel_name : str
            Setting category that this item should be shown within.
        initial_value : bool
            Initial value of the setting.
        label_text : str
            Setting display name to show in the UI.
        """
        checkbox = QCheckBox()
        checkbox.setChecked(initial_value)
        checkbox.stateChanged.connect(lambda isChecked: self._add_change(setting_name, bool(isChecked)))
        self._add_setting(setting_name, panel_name, checkbox, label_text)


    def _add_change(self, setting: str, new_value: Any):
        self._changes[setting] = new_value


    def _add_panel_if_missing(self, panel_name: str):
        if panel_name not in self._panels:
            panel = CollapsibleBox(title=panel_name)
            panel_layout = QVBoxLayout()
            panel.set_content_layout(panel_layout)
            self._panels[panel_name] = panel
            self._panel_layouts[panel_name] = panel_layout
            self._panel_layout.addWidget(panel)


    def _add_setting(self,
            setting_name: str,
            panel_name: str,
            widget: QWidget,
            label_text: str):
        self._add_panel_if_missing(panel_name)
        self._panel_layouts[panel_name].addWidget(LabelWrapper(widget, label_text))
        self._inputs[setting_name] = widget
