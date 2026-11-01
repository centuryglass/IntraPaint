"""Builds input widgets for `Parameter` and `Config` values, keeping the model layer free of UI imports.

`src/util/parameter.py` and `src/config/` hold typed values, metadata and change signals. Widget construction and the
two-way binding between a widget and a config value live here.
"""
from typing import Any, Callable, Optional, TypeAlias, cast

from PySide6.QtCore import QSize

from src.config.config import Config
from src.ui.input_fields.big_int_spinbox import BigIntSpinbox
from src.ui.input_fields.check_box import CheckBox
from src.ui.input_fields.combo_box import ComboBox
from src.ui.input_fields.dual_toggle import DualToggle
from src.ui.input_fields.line_edit import LineEdit
from src.ui.input_fields.plain_text_edit import PlainTextEdit
from src.ui.input_fields.pressure_curve_input import PressureCurveInput
from src.ui.input_fields.size_field import SizeField
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox, FloatSliderSpinbox
from src.util.parameter import (Parameter, ParamType, ParamTypeList, TYPE_BOOL, TYPE_FLOAT, TYPE_INT, TYPE_QSIZE,
                                TYPE_STR)
from src.util.shared_constants import INT_MIN, INT_MAX, FLOAT_MIN, FLOAT_MAX
from src.util.signals_blocked import signals_blocked

DynamicFieldWidget: TypeAlias = (BigIntSpinbox | CheckBox | ComboBox | DualToggle | LineEdit | PlainTextEdit |
                                 SizeField | IntSliderSpinbox | FloatSliderSpinbox | PressureCurveInput)


def create_input_widget(param: Parameter,
                        multi_line=False,
                        allow_dual_toggle=True,
                        option_display: Optional[Callable[[ParamType], str]] = None) -> DynamicFieldWidget:
    """Creates a widget that can be used to set a parameter.

    `option_display` maps an option to the text shown for it. The widget's value is always the option itself.
    """
    display = option_display if option_display is not None else str
    if multi_line and param.type_name != TYPE_STR:
        raise ValueError(f'multi_line=True is only valid for text parameters, value {param.name}'
                         f' is {param.type_name}')
    if param.options is not None and len(param.options) > 0:
        if multi_line:
            raise ValueError('multi_line=True is not valid for parameters with fixed option lists')
        assert param.type_name == TYPE_STR, 'Widget support for non-string option lists is not implemented'
        if len(param.options) == 2 and allow_dual_toggle:
            toggle = DualToggle(parent=None, options=cast(list[str], param.options),
                                display_names=[display(option) for option in param.options])
            assert param.default_value is None or isinstance(param.default_value, str)
            toggle.setValue(param.default_value)
            input_field = cast(DynamicFieldWidget, toggle)
        else:
            combo_box = ComboBox()
            for option in param.options:
                combo_box.addItem(display(option), userData=option)
            if param.default_value is not None:
                index = combo_box.findData(param.default_value)
                assert index >= 0
                combo_box.setCurrentIndex(index)
            input_field = cast(DynamicFieldWidget, combo_box)
    elif param.type_name == TYPE_INT:
        if (param.maximum is not None and param.maximum > INT_MAX) or (param.minimum is not None
                                                                       and param.minimum < INT_MIN):
            spin_box = BigIntSpinbox()
        else:
            spin_box = IntSliderSpinbox()
        spin_box.setMinimum(cast(int, param.minimum) if param.minimum is not None else INT_MIN)
        spin_box.setMaximum(cast(int, param.maximum) if param.maximum is not None else INT_MAX)
        if param.single_step is not None:
            spin_box.setSingleStep(int(param.single_step))
        assert param.default_value is None or isinstance(param.default_value, int)
        spin_box.setValue(param.default_value if param.default_value is not None else max(0, spin_box.minimum()))
        if isinstance(spin_box, IntSliderSpinbox) and (param.minimum is None or param.maximum is None):
            spin_box.set_slider_included(False)
        input_field = cast(DynamicFieldWidget, spin_box)
    elif param.type_name == TYPE_FLOAT:
        spin_box = FloatSliderSpinbox()
        spin_box.setMinimum(cast(float, param.minimum) if param.minimum is not None else FLOAT_MIN)
        spin_box.setMaximum(cast(float, param.maximum) if param.maximum is not None else FLOAT_MAX)
        if param.single_step is not None:
            spin_box.setSingleStep(float(param.single_step))
        assert param.default_value is None or isinstance(param.default_value, float)
        spin_box.setValue(param.default_value if param.default_value is not None else max(0.0, spin_box.minimum()))
        if param.minimum is None or param.maximum is None:
            spin_box.set_slider_included(False)
        input_field = cast(DynamicFieldWidget, spin_box)
    elif param.type_name == TYPE_STR:
        text_box: PlainTextEdit | LineEdit = PlainTextEdit() if multi_line else LineEdit()
        if param.default_value is not None:
            assert isinstance(param.default_value, str)
            text_box.setValue(param.default_value)
        input_field = cast(DynamicFieldWidget, text_box)
    elif param.type_name == TYPE_BOOL:
        check_box = CheckBox()
        if param.default_value is not None:
            check_box.setChecked(bool(param.default_value))
        input_field = cast(DynamicFieldWidget, check_box)
    elif param.type_name == TYPE_QSIZE:
        size_field = SizeField()
        if param.minimum is not None:
            assert isinstance(param.minimum, QSize)
            size_field.minimum = param.minimum
        if param.maximum is not None:
            assert isinstance(param.maximum, QSize)
            size_field.maximum = param.maximum
        if param.single_step is not None:
            size_field.set_single_step(int(param.single_step))
        if param.default_value is not None:
            assert isinstance(param.default_value, QSize)
            size_field.setValue(param.default_value)
        input_field = cast(DynamicFieldWidget, size_field)
    else:
        raise RuntimeError(f'create_input_widget not supported for type {param.type_name}')
    if len(param.description) > 0:
        input_field.setToolTip(param.description)
    return input_field


def create_control_widget(config: Config, key: str, connect_to_config: bool = True,
                          multi_line=False) -> DynamicFieldWidget:
    """Returns a widget that adjusts a config value. Unless connect_to_config is false, changes propagate to the
    config, and later config changes (including option list changes) propagate back to the widget."""
    entry = config.get_entry(key)
    control_widget = create_input_widget(entry, multi_line, False, config.get_option_display)
    control_widget.setValue(entry.get_value())
    if isinstance(control_widget, CheckBox):
        control_widget.setText(entry.name)
    if not connect_to_config:
        return control_widget

    def _update_config(new_value: Any) -> None:
        config.set(key, new_value)

    assert hasattr(control_widget, 'valueChanged')
    control_widget.valueChanged.connect(_update_config)

    def _update_control(new_value: Any) -> None:
        if control_widget.value() != new_value:
            if isinstance(control_widget, ComboBox):
                current_options = config.get_options(key)
                widget_options = [control_widget.itemData(i) for i in range(control_widget.count())]
                if widget_options != current_options:
                    with signals_blocked(control_widget):
                        while control_widget.count() > 0:
                            control_widget.removeItem(0)
                        for new_option in current_options:
                            control_widget.addItem(config.get_option_display(new_option), userData=new_option)
            control_widget.setValue(new_value)

    config.connect(control_widget, key, _update_control)

    if isinstance(control_widget, ComboBox):
        combobox = control_widget

        def _update_options(new_options: ParamTypeList) -> None:
            last_selected = combobox.currentData()
            with signals_blocked(combobox):
                while combobox.count() > 0:
                    combobox.removeItem(0)
                for option in new_options:
                    combobox.addItem(config.get_option_display(option), userData=option)
                new_index = combobox.findData(last_selected)
                if new_index >= 0:
                    combobox.setCurrentIndex(new_index)

        config.connect_to_option_changes(combobox, key, _update_options)
    return control_widget
