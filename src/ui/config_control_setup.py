"""
Creates UI input components linked to data_model.config values.
- Initial component values are read from config.
- Changes to the component update the corresponding config value.
- Changes to the config value are applied to the input (if necessary).
"""
from typing import Optional
from PyQt5.QtWidgets import QDoubleSpinBox, QLineEdit, QCheckBox, QComboBox, QPlainTextEdit, QHBoxLayout, QLabel, \
    QWidget
from PyQt5.QtGui import QFont, QFontMetrics

from src.config.config_entry import RangeKey
from src.ui.widget.big_int_spinbox import BigIntSpinbox
from src.config.application_config import AppConfig


def connected_spinbox(parent: Optional[QWidget],
                      config: AppConfig,
                      key: str,
                      min_val: Optional[int | float] = None,
                      max_val: Optional[int | float] = None,
                      step_val: Optional[int | float] = None,
                      dict_key: Optional[str] = None) -> QDoubleSpinBox | BigIntSpinbox:
    """Creates a spinbox widget connected to a numeric config property.

    Properties can be either integer or floating point, but the type needs to be consistent with the config value's
    fixed type.

    Parameters
    ----------
    parent : QWidget or None
        Optional parent widget.
    config : AppConfig
        Shared application configuration object.
    key : str
        Numeric config value to connect to the spinbox.
    min_val : int or float or None
        Minimum spinbox value. If not provided and dict_key is None, use the minimum from config.
    max_val : int or float or None
        Maximum spinbox value. If not provided and dict_key is None, use the maximum from config.
    step_val : int or float or None
        Value for a single spinbox step. If not provided and dict_key is None, use the step value from config.
    dict_key : str or None
        If not None, the spinbox will be connected to the inner property of a dict config value.
    """
    initial_value = config.get(key, inner_key=dict_key)
    spinbox = QDoubleSpinBox(parent) if isinstance(initial_value, float) else BigIntSpinbox(parent)
    if initial_value < spinbox.minimum() or initial_value > spinbox.maximum():
        spinbox.setRange(min(spinbox.minimum(), initial_value), max(spinbox.maximum(), initial_value))
    min_width = spinbox.sizeHint().width()
    spinbox.setValue(initial_value)

    if dict_key is None and step_val is None:
        step = config.get(key, inner_key=RangeKey.STEP)
        spinbox.setSingleStep(step)
    elif step_val is not None:
        spinbox.setSingleStep(step_val)

    if dict_key is None and min_val is None:
        min_config_val = config.get(key, inner_key=RangeKey.MIN)
        spinbox.setRange(min_config_val, spinbox.maximum())
    elif min_val is not None:
        spinbox.setRange(min_val, spinbox.maximum())

    if dict_key is None and max_val is None:
        max_config_val = config.get(key, inner_key=RangeKey.MAX)
        spinbox.setRange(spinbox.minimum(), max_config_val)
    elif max_val is not None:
        spinbox.setRange(spinbox.minimum(), max_val)
        spinbox.setRange(min_val, spinbox.maximum())

    def apply_change_to_spinbox(new_value: int) -> None:
        """Update the spinbox when the config value changes."""
        if spinbox.value() != new_value:
            spinbox.setValue(new_value if new_value is not None else 0)

    config.connect(spinbox, key, apply_change_to_spinbox, inner_key=dict_key)

    def apply_change_to_config(new_value: int) -> None:
        """Update the config value when the spinbox changes."""
        num_value = int(new_value) if isinstance(initial_value, int) else float(new_value)
        if config.get(key, inner_key=dict_key) != num_value:
            config.set(key, num_value, inner_key=dict_key)

    spinbox.valueChanged.connect(apply_change_to_config)
    if dict_key is None:
        spinbox.setToolTip(config.get_tooltip(key))

    font = QFont()
    font.setPointSize(config.get(AppConfig.FONT_POINT_SIZE))
    longest_str = str(spinbox.maximum())
    if isinstance(initial_value, float) and '.' not in longest_str:
        longest_str += '.00'
    min_size = QFontMetrics(font).boundingRect(longest_str).size()
    min_size.setWidth(min_size.width() + min_width)
    spinbox.setMinimumSize(min_size)
    return spinbox


def connected_textedit(parent: Optional[QWidget],
                       config: AppConfig,
                       key: str,
                       multi_line: bool = False,
                       inner_key: Optional[str] = None) -> QLineEdit | QPlainTextEdit:
    """Creates a textedit widget connected to a string config property.

    Parameters
    ----------
    parent : QWidget or None
        Optional parent widget.
    config : data_model.config.Config
        Shared application configuration object.
    key : str
        String config value to connect to the textedit.
    multi_line : bool
        Whether the textedit should be multi-line.
    inner_key : str or none
        If not None, the textedit will be connected to the inner property of a dict config value.
    """
    textedit = QLineEdit(config.get(key), parent) if not multi_line else QPlainTextEdit(config.get(key), parent)
    if multi_line:
        textedit.textChanged.connect(lambda: config.set(key, textedit.toPlainText(), inner_key=inner_key))

        def set_text(new_text):
            """Copy config value changes to the text box."""
            if new_text != textedit.toPlainText():
                textedit.setPlainText(new_text if new_text is not None else '')

        config.connect(textedit, key, set_text, inner_key=inner_key)
    else:
        textedit.textChanged.connect(lambda new_content: config.set(key, new_content, inner_key=inner_key))

        def set_text(new_text):
            """Copy config value changes to the text box."""
            if new_text != textedit.text():
                textedit.setText(new_text if new_text is not None else '')

        config.connect(textedit, key, set_text, inner_key=inner_key)
    if inner_key is None:
        textedit.setToolTip(config.get_tooltip(key))
    return textedit


def connected_checkbox(parent: Optional[QWidget],
                       config: AppConfig,
                       key: str,
                       text: Optional[str] = None,
                       inner_key: Optional[str] = None) -> QCheckBox:
    """Creates a checkbox widget connected to a boolean config property.

    Parameters
    ----------
    parent : QWidget or None
        Optional parent widget.
    config : AppConfig
        Shared application configuration object.
    key : str
        Boolean config value to connect to the checkbox.
    text : str or None
        Optional label text
    inner_key : str or none
        If not None, the checkbox will be connected to the inner property of a dict config value.
    """
    checkbox = QCheckBox(parent)
    checkbox.setChecked(bool(config.get(key, inner_key)))
    checkbox.stateChanged.connect(lambda is_checked: config.set(key, bool(is_checked), inner_key=inner_key))
    config.connect(checkbox, key, lambda is_checked: checkbox.setChecked(bool(is_checked)), inner_key=inner_key)
    if text is not None:
        checkbox.setText(text)
    if inner_key is None:
        checkbox.setToolTip(config.get_tooltip(key))
    return checkbox


def connected_combobox(parent: Optional[QWidget],
                       config: AppConfig,
                       key: str,
                       text: Optional[str] = None) -> QComboBox | tuple[QComboBox, QHBoxLayout]:
    """Creates a combobox widget connected to a config property with a pre-defined  option list.

    Parameters
    ----------
    parent : QWidget or None
        Optional parent widget.
    config : AppConfig
        Shared application configuration object.
    key : str
        Config value to connect to the combobox.
    text : str or None
        Optional label text
    """
    combobox = QComboBox(parent)
    options = config.get_options(key)
    for option in options:
        combobox.addItem(option)
    default_value = config.get(key)
    combobox.setCurrentIndex(options.index(default_value))

    def apply_change_to_config(index):
        """Copy combo box changes to config."""
        value = combobox.itemText(index)
        config.set(key, value)

    combobox.currentIndexChanged.connect(apply_change_to_config)
    config.connect(combobox, key, lambda new_value: combobox.setCurrentIndex(options.index(new_value)))
    combobox.setToolTip(config.get_tooltip(key))
    if text is not None:
        label = QLabel(text)
        layout = QHBoxLayout()
        layout.addWidget(label)
        layout.addWidget(combobox)
        return combobox, layout
    return combobox
