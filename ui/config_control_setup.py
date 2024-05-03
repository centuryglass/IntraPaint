"""
Creates UI input components linked to data_model.config values.
- Initial component values are read from config.
- Changes to the component update the corresponding config value.
- Changes to the config value are applied to the input (if necessary).
"""

from PyQt5.QtWidgets import QSpinBox, QDoubleSpinBox, QLineEdit, QCheckBox, QComboBox, QPlainTextEdit, QHBoxLayout, QLabel
from PyQt5.QtGui import QTextCursor, QFont, QFontMetrics
from ui.widget.big_int_spinbox import BigIntSpinbox


def connected_spinbox(parent, config, key, min_key=None, max_key=None, step_size_key=None, inner_key=None):
    initial_value = config.get(key, inner_key)
    spinbox = QDoubleSpinBox(parent) if type(initial_value) is float else BigIntSpinbox(parent)
    if (initial_value < spinbox.minimum() or initial_value > spinbox.maximum()):
        spinbox.setRange(min(spinbox.minimum(), initial_value), max(spinbox.maximum(), initial_value))
    min_width = spinbox.sizeHint().width()
    spinbox.setValue(initial_value)
    if isinstance(step_size_key, str):
        step = config.get(step_size_key)
        spinbox.setSingleStep(step)
        config.connect(spinbox, step_size_key, lambda newVal: spinbox.setSingleStep(newVal), inner_key)
    elif step_size_key is not None:
        spinbox.setSingleStep(step_size_key)
    def apply_change_to_spinbox(new_value):
        if spinbox.value() != new_value:
            spinbox.setValue(new_value if new_value is not None else 0)
    config.connect(spinbox, key, apply_change_to_spinbox, inner_key=inner_key)
    def apply_change_to_config(newValue):
        num_value = int(newValue) if type(initial_value) is int else float(newValue)
        if config.get(key, inner_key) != num_value:
            config.set(key, num_value, inner_key=inner_key)
    spinbox.valueChanged.connect(apply_change_to_config)

    if max_key is not None:
        min_val = 0 if min_key is None else config.get(min_key) if isinstance(min_key, str) else min_key
        max_val = config.get(max_key) if isinstance(max_key, str) else max_key
        spinbox.setRange(min_val, max_val)
        if isinstance(min_key, str):
            config.connect(spinbox, min_key, lambda newMin: spinbox.setRange(newMin, spinbox.maximum())) 
        if isinstance(max_key, str):
            config.connect(spinbox, max_key, lambda newMax: spinbox.setRange(spinbox.minimum(), newMax))

    font = QFont()
    font.setPointSize(config.get("fontPointSize"))
    longest_str = str(initial_value)
    if max_key is not None:
        longest_str = str(config.get(max_key) if isinstance(max_key, str) else max_key)
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
    return textedit


def connected_checkbox(parent, config, key, text=None, tooltip=None, inner_key=None):
    checkbox = QCheckBox(parent)
    checkbox.setChecked(bool(config.get(key, inner_key)))
    checkbox.stateChanged.connect(lambda isChecked: config.set(key, bool(isChecked), inner_key=inner_key))
    config.connect(checkbox, key, lambda isChecked: checkbox.setChecked(bool(isChecked)), inner_key=inner_key)
    if text is not None:
        checkbox.setText(text)
    if tooltip is not None:
        checkbox.setToolTip(tooltip)
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
    if text is not None:
        label = QLabel(text)
        layout = QHBoxLayout()
        layout.addWidget(label)
        layout.addWidget(combobox)
        return combobox, layout
    else:
        return combobox
