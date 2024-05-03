"""
Popup modal providing a dynamic settings interface, to be populated by the controller. Currently only used with
stable_diffusion_controller.
"""
from PyQt5.QtWidgets import *
from PyQt5.QtCore import pyqtSignal
from ui.widget.bordered_widget import BorderedWidget
from ui.widget.collapsible_box import CollapsibleBox
from ui.widget.big_int_spinbox import BigIntSpinbox
from ui.widget.label_wrapper import LabelWrapper


class SettingsModal(QDialog):
    """Manage remote settings."""

    changes_saved = pyqtSignal(dict)

    def __init__(self, parent):
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
        cancel_button.setText("Cancel")
        cancel_button.clicked.connect(lambda: self.hide())
        bottom_panel_layout.addWidget(cancel_button, stretch=1)

        save_button = QPushButton()
        save_button.setText("Save")
        def on_save():
            self.changes_saved.emit(self._changes)
            self.hide()
        save_button.clicked.connect(lambda: on_save())
        bottom_panel_layout.addWidget(save_button, stretch=1)
        layout.addWidget(bottom_panel, stretch=1)

    def show_modal(self):
        self.exec_()

    def set_tooltip(self, setting_name, tooltip):
        if setting_name not in self._inputs:
            raise Exception(f"{setting_name} not defined")
        self._inputs[setting_name].setToolTip(tooltip)
        
    def _add_change(self, setting, new_value):
        self._changes[setting] = new_value

    def _add_panel_if_missing(self, panel_name):
        if panel_name not in self._panels:
            panel = CollapsibleBox(title=panel_name)
            panel_layout = QVBoxLayout()
            panel.set_content_layout(panel_layout)
            self._panels[panel_name] = panel
            self._panel_layouts[panel_name] = panel_layout
            self._panel_layout.addWidget(panel)

    def _add_setting(self, setting_name, panel_name, widget, label_text):
        self._add_panel_if_missing(panel_name)
        self._panel_layouts[panel_name].addWidget(LabelWrapper(widget, label_text))
        self._inputs[setting_name] = widget

    def update_settings(self, settings):
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

    def add_text_setting(self, setting_name, panel_name, initial_value, label_text):
        textbox = QLineEdit()
        textbox.setText(initial_value)
        textbox.textChanged.connect(lambda: self._add_change(setting_name, textbox.text()))
        self._add_setting(setting_name, panel_name, textbox, label_text)

    def add_combobox_setting(self, setting_name, panel_name, initial_value, options, label_text):
        combobox = QComboBox()
        for option in options:
            if isinstance(option, dict):
                combobox.addItem(option['text'])
            else:
                combobox.addItem(option)
        def update_value(selected_index):
            print(f"Set value {selected_index} for {setting_name}")
            self._add_change(setting_name, options[selected_index])
        combobox.setCurrentIndex(options.index(initial_value))
        combobox.currentIndexChanged.connect(update_value)
        self._add_setting(setting_name, panel_name, combobox, label_text)

    def add_spinbox_setting(self, setting_name, panel_name, initial_value, min_value, max_value, label_text):
        spinbox = QDoubleSpinBox() if type(initial_value) is float else BigIntSpinbox()
        spinbox.setRange(min_value, max_value)
        spinbox.setValue(initial_value)
        spinbox.valueChanged.connect(lambda newValue: self._add_change(setting_name, newValue))
        self._add_setting(setting_name, panel_name, spinbox, label_text)

        
    def add_checkbox_setting(self, setting_name, panel_name, initial_value, label_text):
        checkbox = QCheckBox()
        checkbox.setChecked(initial_value)
        checkbox.stateChanged.connect(lambda isChecked: self._add_change(setting_name, bool(isChecked)))
        self._add_setting(setting_name, panel_name, checkbox, label_text)
