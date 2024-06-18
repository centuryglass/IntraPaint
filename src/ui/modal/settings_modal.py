"""
Popup modal providing a dynamic settings interface, to be populated by the controller. Currently only used with
stable_diffusion_controller.
"""
import sys
from typing import Any, Dict, List, Optional
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QComboBox, QDoubleSpinBox, \
    QCheckBox, QWidget, QTabWidget, QFormLayout, QLabel, QScrollArea
from PyQt5.QtCore import pyqtSignal, QSize

from src.config.config import Config
from src.config.config_entry import RangeKey
from src.ui.widget.bordered_widget import BorderedWidget
from src.ui.widget.big_int_spinbox import BigIntSpinbox

WIDTH_LABEL = "W:"
HEIGHT_LABEL = "H:"


class SettingsModal(QDialog):
    """Manage remote settings."""

    changes_saved = pyqtSignal(dict)

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setModal(True)

        self._tabs: Dict[str, QWidget] = {}
        self._tab_layouts: Dict[str, QFormLayout] = {}
        self._inputs: Dict[str, QWidget] = {}
        self._changes: Dict[str, Any] = {}

        layout = QVBoxLayout()
        self.setLayout(layout)

        self._tab_widget = QTabWidget(self)
        layout.addWidget(self._tab_widget, stretch=20)

        bottom_panel = BorderedWidget(self)
        bottom_panel_layout = QHBoxLayout()
        bottom_panel.setLayout(bottom_panel_layout)

        cancel_button = QPushButton()
        cancel_button.setText('Cancel')
        cancel_button.clicked.connect(self.hide)
        bottom_panel_layout.addWidget(cancel_button, stretch=1)

        save_button = QPushButton()
        save_button.setText('Save')

        def on_save():
            """Apply changes and close when the save button is clicked."""
            self.changes_saved.emit(self._changes)
            self.hide()

        save_button.clicked.connect(on_save)
        bottom_panel_layout.addWidget(save_button, stretch=1)
        layout.addWidget(bottom_panel, stretch=1)

    def load_from_config(self, config: Config, categories: Optional[List[str]] = None) -> None:
        """Load settings from a Config object, or from a subset of Config object categories."""
        if categories is None:
            categories = config.get_categories()
        for category in categories:
            for key in config.get_category_keys(category):
                if key in self._inputs:
                    continue
                value = config.get(key)
                label = config.get_label(key)
                tooltip = config.get_tooltip(key)
                if isinstance(value, bool):
                    self.add_checkbox_setting(key, category, value, label)
                elif isinstance(value, QSize):
                    self.add_size_setting(key, category, value, label)
                elif isinstance(value, (int, float)):
                    try:
                        min_val = config.get(key, RangeKey.MIN)
                        max_val = config.get(key, RangeKey.MAX)
                        step = config.get(key, RangeKey.STEP)
                    except TypeError:  # No explicit bounds, just use maximums:
                        min_val = BigIntSpinbox.MINIMUM if isinstance(value, int) else sys.float_info.min
                        max_val = BigIntSpinbox.MAXIMUM if isinstance(value, int) else sys.float_info.max
                        step = 1 if isinstance(value, int) else 1.0
                    self.add_spinbox_setting(key, category, value, min_val, max_val, step, label)
                elif isinstance(value, str):
                    try:
                        options = config.get_options(key)
                        self.add_combobox_setting(key, category, value, options, label)
                    except RuntimeError:
                        self.add_text_setting(key, category, value, label)
                else:
                    print(f"skipping key {key} with unsupported type={type(value)}, value={value}")
                    continue
                self.set_tooltip(key, tooltip)

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
            if isinstance(settings[key], QSize):
                widget.width_box.setValue(settings[key].width())
                widget.height_box.setValue(settings[key].height())
            elif isinstance(widget, QLineEdit):
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
            """Update the associated value in the change dict when the combo box changes."""
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
                            step_value: int | float,
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
        step_value: int or float
            Amount the control should increase/decrease by default.
        label_text : str
            Setting display name to show in the UI.
        """
        spinbox = QDoubleSpinBox() if isinstance(initial_value, float) else BigIntSpinbox()
        spinbox.setRange(min_value, max_value)
        spinbox.setSingleStep(step_value)
        spinbox.setValue(initial_value)
        spinbox.valueChanged.connect(lambda new_value: self._add_change(setting_name,
                                                                        int(new_value) if isinstance(initial_value, int)
                                                                        else float(new_value)))
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
        checkbox.stateChanged.connect(lambda is_checked: self._add_change(setting_name, bool(is_checked)))
        self._add_setting(setting_name, panel_name, checkbox, label_text)

    def add_size_setting(self,
                            setting_name: str,
                            panel_name: str,
                            initial_value: QSize,
                            label_text: str):
        """Adds a new size setting.

        Parameters
        ----------
        setting_name : str
            Key string used when tracking the setting.
        panel_name : str
            Setting category that this item should be shown within.
        initial_value : QSize
            Initial value of the setting.
        label_text : str
            Setting display name to show in the UI.
        """
        size_bar = QWidget()
        bar_layout = QHBoxLayout(size_bar)
        bar_layout.addWidget(QLabel(WIDTH_LABEL))
        width_box = BigIntSpinbox(size_bar)
        width_box.setValue(initial_value.width())
        bar_layout.addWidget(width_box)
        bar_layout.addWidget(QLabel(HEIGHT_LABEL))
        height_box = BigIntSpinbox(size_bar)
        height_box.setValue(initial_value.height())
        bar_layout.addWidget(height_box)

        def _update_width(new_width: str) -> None:
            self._add_change(setting_name, QSize(int(new_width), height_box.value()))
        width_box.valueChanged.connect(_update_width)

        def _update_height(new_height: str) -> None:
            self._add_change(setting_name, QSize(width_box.value(), new_height))
        height_box.valueChanged.connect(_update_height)
        setattr(size_bar, 'width_box', width_box)
        setattr(size_bar, 'height_box', height_box)
        self._add_setting(setting_name, panel_name, size_bar, label_text)

    def _add_change(self, setting: str, new_value: Any):
        self._changes[setting] = new_value

    def _add_tab_if_missing(self, tab_name: str):
        if tab_name not in self._tabs:
            tab_body = QWidget()
            tab_layout = QFormLayout(tab_body)
            tab = QScrollArea(self)
            tab.setWidgetResizable(True)
            tab.setWidget(tab_body)
            self._tabs[tab_name] = tab
            self._tab_layouts[tab_name] = tab_layout
            self._tab_widget.addTab(tab, tab_name)

    def _add_setting(self,
                     setting_name: str,
                     panel_name: str,
                     widget: QWidget,
                     label_text: str):
        self._add_tab_if_missing(panel_name)
        self._tab_layouts[panel_name].addRow(label_text, widget)
        self._inputs[setting_name] = widget
