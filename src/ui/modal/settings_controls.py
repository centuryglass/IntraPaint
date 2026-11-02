"""Chooses the control the settings window shows for each config value.

The choice follows the value's type, range, options and `ControlHint`. Every control returned has `value()`,
`setValue()` and a `valueChanged` signal.
"""
from typing import Optional

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QWidget

from src.config.config import Config
from src.config.config_entry import ControlHint
from src.ui.input_fields.check_box import CheckBox
from src.ui.input_fields.line_edit import LineEdit
from src.ui.input_fields.setting_fields import ColorSettingField, DirectorySettingField, KeybindingField, \
    NumberSettingField, OptionSegmentsField, SizeSettingField, SliderSettingField
from src.util.parameter import TYPE_BOOL, TYPE_FLOAT, TYPE_INT, TYPE_QSIZE, TYPE_STR
from src.ui.input_fields.field_factory import create_control_widget

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.modal.settings_controls'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


ASK_LABEL = _tr('Ask')
ALWAYS_LABEL = _tr('Always')
NEVER_LABEL = _tr('Never')
MINIMAL_MOVE_LABEL = _tr('Minimal move')
CENTER_LABEL = _tr('Center')
OFF_LABEL = _tr('Off')

# Options whose stored values are not meant to be read, or whose labels are short enough for segments. The values are
# the options as stored, and are never translated. A key listed here must have exactly these options.
OPTION_LABELS: dict[str, dict[str, str]] = {
    'always_init_metadata_on_save': {'always_ask': ASK_LABEL, 'confirm': ALWAYS_LABEL, 'cancel': NEVER_LABEL},
    'always_update_metadata_on_save': {'always_ask': ASK_LABEL, 'confirm': ALWAYS_LABEL, 'cancel': NEVER_LABEL},
    'generation_area_follow_selection': {'Minimal move': MINIMAL_MOVE_LABEL, 'Center on selection': CENTER_LABEL,
                                         'Off': OFF_LABEL},
}

# Numeric settings with a range at most this wide get a slider:
MAX_SLIDER_SPAN = 2000
KEYBINDING_CATEGORIES = ('Keybindings', 'Menu Shortcuts')


def is_keybinding(config: Config, key: str) -> bool:
    """Returns whether a config value is a key sequence."""
    return config.get_data_type(key) == TYPE_STR and config.get_category(key) in KEYBINDING_CATEGORIES


def _options(config: Config, key: str) -> list:
    """Returns a value's option list, empty if it has none."""
    try:
        return list(config.get_options(key))
    except RuntimeError:
        return []


def create_setting_control(config: Config, key: str) -> QWidget:
    """Returns a standalone control for one config value, set to its current value and not connected to the config.

    Raises
    ------
    RuntimeError
        If the value's type has no control, such as a list.
    """
    data_type = config.get_data_type(key)
    label = config.get_label(key)
    tooltip = config.get_tooltip(key)
    control: QWidget
    if data_type == TYPE_BOOL:
        control = CheckBox()
    elif key in OPTION_LABELS and sorted(_options(config, key)) == sorted(OPTION_LABELS[key]):
        control = OptionSegmentsField(OPTION_LABELS[key])
    elif data_type == TYPE_STR and _options(config, key):
        return create_control_widget(config, key, False)
    elif data_type == TYPE_STR:
        hint = config.get_control_hint(key)
        if hint in (ControlHint.COLOR, ControlHint.COLOR_REQUIRED):
            control = ColorSettingField(allow_theme_default=hint == ControlHint.COLOR)
        elif hint == ControlHint.DIRECTORY:
            control = DirectorySettingField()
        elif is_keybinding(config, key):
            control = KeybindingField()
        else:
            control = LineEdit()
    elif data_type in (TYPE_INT, TYPE_FLOAT):
        minimum, maximum, step = config.get_range(key)
        default_step: int | float = 1 if data_type == TYPE_INT else 0.1
        step = step if step is not None else default_step
        if minimum is not None and maximum is not None and maximum - minimum <= MAX_SLIDER_SPAN \
                and minimum < maximum:
            control = SliderSettingField('', config.get(key), minimum, maximum, step=step)
        else:
            control = NumberSettingField('', config.get(key), minimum, maximum, step)
        control.setAccessibleName(label)
    elif data_type == TYPE_QSIZE:
        minimum_size, maximum_size, _ = config.get_range(key)
        control = SizeSettingField(minimum_size if isinstance(minimum_size, QSize) else None,
                                   maximum_size if isinstance(maximum_size, QSize) else None)
    else:
        raise RuntimeError(f'No settings control for {key} of type {data_type}')
    control.setValue(config.get(key))  # type: ignore[attr-defined]
    control.setToolTip(tooltip)
    return control
