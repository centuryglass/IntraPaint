"""
Popup modal providing a dynamic settings interface, to be populated by the controller. Currently only used with
stable_diffusion_controller.
"""
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import pyqtSignal, QSize
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QWidget, QTabWidget, QFormLayout, \
    QScrollArea

from src.config.config import Config
from src.ui.input_fields.big_int_spinbox import BigIntSpinbox
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox
from src.ui.input_fields.check_box import CheckBox
from src.ui.input_fields.combo_box import ComboBox
from src.ui.input_fields.dual_toggle import DualToggle
from src.ui.input_fields.line_edit import LineEdit
from src.ui.input_fields.plain_text_edit import PlainTextEdit
from src.ui.input_fields.size_field import SizeField
from src.ui.widget.bordered_widget import BorderedWidget
from src.util.parameter import DynamicFieldWidget


class SettingsModal(QDialog):
    """Manage remote settings."""

    changes_saved = pyqtSignal(dict)

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setModal(True)

        self._tabs: Dict[str, QWidget] = {}
        self._tab_layouts: Dict[str, QFormLayout] = {}
        self._inputs: Dict[str, DynamicFieldWidget] = {}
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
                label = config.get_label(key)
                try:
                    control_widget = config.get_control_widget(key, False)
                except RuntimeError:
                    continue
                assert hasattr(control_widget, 'valueChanged')
                if isinstance(control_widget, CheckBox):
                    control_widget.setText('')  # External labels look better than checkbox labels in this layout.

                def _add_change(new_value: Any, name=key):
                    self._add_change(name, new_value)
                control_widget.valueChanged.connect(_add_change)
                self._add_setting(key, category, control_widget, label)\


    def remove_category(self, config: Config, category: str) -> None:
        """Remove a category from the modal"""
        if category not in self._tabs:
            return
        for key in config.get_category_keys(category):
            if key in self._inputs:
                del self._inputs[key]
            if key in self._changes:
                del self._changes[key]
        assert category in self._tab_layouts
        layout = self._tab_layouts[category]
        del self._tab_layouts[category]
        while layout.count() > 0:
            item = layout.takeAt(0)
            assert item is not None
            widget = item.widget()
            assert widget is not None
            widget.setParent(None)
            widget.deleteLater()
        layout.deleteLater()
        tab = self._tabs[category]
        index = self._tab_widget.indexOf(tab)
        self._tab_widget.removeTab(index)
        del self._tabs[category]
        tab.deleteLater()

    def show_modal(self):
        """Shows the settings modal."""
        self.exec()

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
            assert hasattr(widget, 'setValue')
            new_value = settings[key]
            if isinstance(widget, SizeField):
                assert isinstance(new_value, QSize)
                widget.setValue(new_value)
            else:
                assert not isinstance(new_value, QSize)
                if isinstance(widget, (LineEdit, PlainTextEdit, DualToggle, ComboBox)):
                    widget.setValue(str(new_value))
                else:
                    if new_value is None:
                        new_value = 0
                    assert isinstance(new_value, (int, float, bool))
                    if isinstance(widget, (BigIntSpinbox, IntSliderSpinbox)):
                        widget.setValue(int(new_value))
                    elif isinstance(widget, CheckBox):
                        widget.setValue(bool(new_value))
                    else:
                        widget.setValue(float(new_value))
            if key in self._changes:
                del self._changes[key]

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
                     widget: DynamicFieldWidget,
                     label_text: str):
        self._add_tab_if_missing(panel_name)
        self._tab_layouts[panel_name].addRow(label_text, widget)
        self._inputs[setting_name] = widget
