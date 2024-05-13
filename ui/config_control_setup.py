"""
Creates UI input components linked to data_model.config values.
- Initial component values are read from config.
- Changes to the component update the corresponding config value.
- Changes to the config value are applied to the input (if necessary).
"""

from PyQt5.QtWidgets import QSpinBox, QDoubleSpinBox, QLineEdit, QCheckBox, QComboBox, QPlainTextEdit, QHBoxLayout, QLabel
from PyQt5.QtGui import QTextCursor, QFont, QFontMetrics
from ui.widget.big_int_spinbox import BigIntSpinbox


def connected_spinbox(parent, config, key, min_val=None, max_val=None, step_val=None, dict_key=None):
    initial_value = config.get(key, inner_key=dict_key)
    spinbox = QDoubleSpinBox(parent) if type(initial_value) is float else BigIntSpinbox(parent)
    if (initial_value < spinbox.minimum() or initial_value > spinbox.maximum()):
        spinbox.setRange(min(spinbox.minimum(), initial_value), max(spinbox.maximum(), initial_value))
    min_width = spinbox.sizeHint().width()
    spinbox.setValue(initial_value)

    if dict_key is None and step_val is None:
        step = config.get(key, inner_key="step")
        spinbox.setSingleStep(step)
    elif step_val is not None:
        spinbox.setSingleStep(step_val)

    if dict_key is None and min_val is None:
        min_config_val = config.get(key, inner_key="min")
        spinbox.setRange(min_config_val, spinbox.maximum())
    elif min_val is not None:
        spinbox.setRange(min_val, spinbox.maximum())
    
    if dict_key is None and max_val is None:
        max_config_val = config.get(key, inner_key="max")
        spinbox.setRange(spinbox.minimum(), max_config_val)
    elif max_val is not None:
        spinbox.setRange(spinbox.minimum(), max_val)
        spinbox.setRange(min_val, spinbox.maximum())
    def apply_change_to_spinbox(new_value):
        if spinbox.value() != new_value:
            spinbox.setValue(new_value if new_value is not None else 0)
    config.connect(spinbox, key, apply_change_to_spinbox, inner_key=dict_key)
    def apply_change_to_config(newValue):
        num_value = int(newValue) if type(initial_value) is int else float(newValue)
        if config.get(key, inner_key=dict_key) != num_value:
            config.set(key, num_value, inner_key=dict_key)
    spinbox.valueChanged.connect(apply_change_to_config)
    if dict_key is None:
        spinbox.setToolTip(config.get_tooltip(key))

    font = QFont()
    font.setPointSize(config.get("font_point_size"))
    longest_str = str(spinbox.maximum())
    if type(initial_value) is float and "." not in longest_str:
        longest_str += ".00"
    min_size = QFontMetrics(font).boundingRect(longest_str).size()
    min_size.setWidth(min_size.width() + min_width)
    spinbox.setMinimumSize(min_size)
    return spinbox


def connected_textedit(parent, config, key, multi_line=False, inner_key=None):
    textedit = QLineEdit(config.get(key), parent) if not multi_line else QPlainTextEdit(config.get(key), parent)
    if multi_line:
        textedit.textChanged.connect(lambda: config.set(key, textedit.toPlainText(), inner_key=inner_key))
        def setText(newText):
            if newText != textedit.toPlainText():
                textedit.setPlainText(newText if newText is not None else "")
        config.connect(textedit, key, setText, inner_key=inner_key)
    else:
        textedit.textChanged.connect(lambda newContent: config.set(key, newContent, inner_key=inner_key))
        def setText(newText):
            if newText != textedit.text():
                textedit.setText(newText if newText is not None else "")
        config.connect(textedit, key, setText, inner_key=inner_key)
    if inner_key is None:
        textedit.setToolTip(config.get_tooltip(key))
    return textedit


def connected_checkbox(parent, config, key, text=None, inner_key=None):
    checkbox = QCheckBox(parent)
    checkbox.setChecked(bool(config.get(key, inner_key)))
    checkbox.stateChanged.connect(lambda isChecked: config.set(key, bool(isChecked), inner_key=inner_key))
    config.connect(checkbox, key, lambda isChecked: checkbox.setChecked(bool(isChecked)), inner_key=inner_key)
    if text is not None:
        checkbox.setText(text)
    if inner_key is None:
        checkbox.setToolTip(config.get_tooltip(key))
    return checkbox


def connected_combobox(parent, config, key, text=None):
    combobox = QComboBox(parent)
    options = config.get_options(key)
    for option in options:
        combobox.addItem(option)
    default_value = config.get(key)
    combobox.setCurrentIndex(options.index(default_value))
    def updateConfigValue(index):
        value = combobox.itemText(index)
        config.set(key, value)
    combobox.currentIndexChanged.connect(updateConfigValue)
    config.connect(combobox, key, lambda newValue: combobox.setCurrentIndex(options.index(newValue)))
    combobox.setToolTip(config.get_tooltip(key))
    if text is not None:
        label = QLabel(text)
        layout = QHBoxLayout()
        layout.addWidget(label)
        layout.addWidget(combobox)
        return combobox, layout
    else:
        return combobox
