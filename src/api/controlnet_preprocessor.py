"""Defines a ControlNet preprocessor's name and parameters, for use with a Stable-Diffusion API"""
from typing import Optional, cast

from PySide6.QtWidgets import QLabel

from src.api.comfyui.comfyui_types import NodeInfoResponse, ParamDef, IntParamDef, BoolParamDef, FloatParamDef, \
    CONTROLNET_PREPROCESSOR_OUTPUT_NAME
from src.api.comfyui.nodes.controlnet.dynamic_preprocessor_node import DynamicPreprocessorNode
from src.api.webui.controlnet_constants import ControlNetUnitDict, RESOLUTION_PARAMETER_NAME, ModuleDetail, \
    PREPROCESSOR_RES_DEFAULTS, PREPROCESSOR_NO_RESOLUTION, PREPROCESSOR_RES_DEFAULT, PREPROCESSOR_RES_MIN, \
    PREPROCESSOR_RES_MAX, PREPROCESSOR_RES_STEP, ControlNetSliderDef, THRESHOLD_A_PARAMETER_NAMES, \
    THRESHOLD_B_PARAMETER_NAMES
from src.util.parameter import Parameter, ParamType, DynamicFieldWidget, TYPE_INT, TYPE_BOOL, TYPE_FLOAT, TYPE_STR


class ControlNetPreprocessor:
    """Defines a ControlNet preprocessor's name and parameters, for use with a Stable-Diffusion API."""

    def __init__(self, name: str, display_name: str, parameters: list[Parameter]) -> None:
        """Parameter objects are used similarly to the way they're used in src.image.filter, except that the name value
           holds a key string, and description is the display name."""
        self._name = name
        self._display_name = display_name
        self._parameters = parameters
        self._values: list[ParamType] = []
        for parameter in self._parameters:
            self._values.append(parameter.default_value)

    @property
    def parameters(self) -> list[Parameter]:
        """Returns the parameter list."""
        return [*self._parameters]

    @property
    def parameter_keys(self) -> list[str]:
        """Returns the list of parameter key strings"""
        return [param.name for param in self._parameters]

    def get_value(self, param_key: str) -> ParamType:
        """Gets the value of a parameter, looking it up using its name key."""
        for i, param in enumerate(self._parameters):
            if param_key == param.name:
                return self._values[i]
        raise KeyError(f'Parameter "{param_key}" not found in "{self._name}" preprocessor')

    def set_value(self, param_key: str, value: ParamType) -> None:
        """Sets the value of a parameter, validating it first."""
        for i, param in enumerate(self._parameters):
            if param_key == param.name:
                param.validate(value, raise_on_failure=True)
                self._values[i] = value
                return
        raise KeyError(f'Parameter "{param_key}" not found in "{self._name}" preprocessor')

    def get_control_widget(self, param_key: str,
                           include_label: bool = True) -> tuple[DynamicFieldWidget, Optional[QLabel]]:
        """Gets a widget that directly updates one of the parameter values in this object.

        NOTE: If anything else changes the value, that change will not be reflected back to the widget.  That means its
              best to use either get_control_widget or set_value, but not both.
        """
        for i, param in enumerate(self._parameters):
            if param_key == param.name:
                control = param.get_input_widget()
                label = QLabel(param.description) if include_label else None

                def _update_value(new_value: ParamType, key=param_key) -> None:
                    self.set_value(key, new_value)
                control.valueChanged.connect(_update_value)
                return control, label
        raise KeyError(f'Parameter "{param_key}" not found in "{self._name}" preprocessor')

    def write_to_webui_data(self, controlnet_unit: ControlNetUnitDict) -> None:
        """Writes preprocessor-specific parameters to a WebUI request's ControlNet script dict."""
        controlnet_unit['module'] = self._name
        next_param_key = 'threshold_a'
        for i, param in enumerate(self._parameters):
            value = self._values[i]
            if param.name == RESOLUTION_PARAMETER_NAME:
                assert isinstance(value, int)
                controlnet_unit['processor_res'] = value
            else:
                assert isinstance(value, (int, float))
                if next_param_key == 'threshold_a':
                    controlnet_unit['threshold_a'] = float(value)
                    next_param_key = 'threshold_b'
                elif next_param_key == 'threshold_b':
                    controlnet_unit['threshold_a'] = float(value)
                    next_param_key = 'INVALID'
                else:
                    raise RuntimeError('Expected no more than two threshold values plus optional resolution, found'
                                       f'unexpected "{param.name}" value.')

    def create_comfyui_node(self) -> DynamicPreprocessorNode:
        """Initializes a ComfyUI node from the preprocessor definition and values."""
        value_dict: dict[str, ParamType] = {}
        for i, param in enumerate(self._parameters):
            value_dict[param.name] = self._values[i]
        return DynamicPreprocessorNode(self._name, value_dict)

    @staticmethod
    def from_comfyui_node_def(node_info: NodeInfoResponse) -> 'ControlNetPreprocessor':
        """Create a ControlNetPreprocessor from a ComfyUI API definition."""
        if node_info['output_name'] != CONTROLNET_PREPROCESSOR_OUTPUT_NAME:
            raise ValueError('Not a vaild ControlNetPreprocessor node: unexpected output format'
                             f' {node_info["output_name"]}')
        name = node_info['name']
        if 'display_name' in node_info:
            display_name = node_info['display_name']
        else:
            display_name = name
        parameter_list: list[Parameter] = []
        for input_category in ('required', 'optional'):
            if input_category not in node_info['input_order'] or input_category not in node_info['input']:
                continue
            if input_category == 'required':  # TypedDict doesn't like direct indexing with input_category
                inputs = node_info['input_order']['required']
                input_dict = node_info['input']['required']
                if DynamicPreprocessorNode.IMAGE not in input_dict:
                    raise ValueError('Not a vaild ControlNetPreprocessor node: missing required image input')
            else:
                inputs = node_info['input_order']['optional']
                input_dict = node_info['input']['optional']
            for input_name in inputs:
                if input_name == DynamicPreprocessorNode.IMAGE:
                    continue
                input_tuple = input_dict[input_name]
                input_type_or_list = input_tuple[0]
                input_param_def = None if len(input_tuple) < 2 else cast(ParamDef, input_tuple[1])

                # Find Parameter init values:
                param_name = input_name
                if input_param_def is not None and 'tooltip' in input_param_def:
                    param_description = input_param_def['tooltip']
                else:
                    param_description = ''
                default_value: Optional[int | float | str]
                min_val: Optional[int | float] = None
                max_val: Optional[int | float] = None
                step_val: Optional[int | float] = None
                options: Optional[list[str]] = None

                if input_type_or_list == 'INT':
                    parameter_type = TYPE_INT
                    assert input_param_def is not None
                    int_param_def = cast(IntParamDef, input_param_def)
                    default_value = int_param_def['default']
                    min_val = int_param_def['min']
                    max_val = int_param_def['max']
                    step_val = int_param_def['step']
                elif input_type_or_list == 'BOOLEAN':
                    parameter_type = TYPE_BOOL
                    assert input_param_def is not None
                    bool_param_def = cast(BoolParamDef, input_param_def)
                    default_value = bool_param_def['default']
                elif input_type_or_list == 'FLOAT':
                    parameter_type = TYPE_FLOAT
                    assert input_param_def is not None
                    float_param_def = cast(FloatParamDef, input_param_def)
                    default_value = float_param_def['default']
                    min_val = float_param_def['min']
                    max_val = float_param_def['max']
                    step_val = float_param_def['step']
                elif isinstance(input_type_or_list, list):
                    parameter_type = TYPE_STR
                    options = input_type_or_list
                    default_value = options[0]
                else:
                    raise RuntimeError(f'"{name}" preprocessor node: unexpected input {input_tuple}')
                parameter = Parameter(param_name, parameter_type, default_value, param_description, min_val, max_val,
                                      step_val)
                if options is not None:
                    parameter.set_valid_options(cast(list[ParamType], options))
                parameter_list.append(parameter)
        return ControlNetPreprocessor(name, display_name, parameter_list)

    @staticmethod
    def _parameter_from_slider_def(slider_def: ControlNetSliderDef) -> Parameter:
        param_name = slider_def['name']
        min_val = slider_def['min']
        max_val = slider_def['max']
        default_val = slider_def['default']
        step_val = slider_def['step']
        if any((num % 1) != 0.0 for num in (min_val, max_val, default_val, step_val)):
            parameter_type = TYPE_FLOAT
            min_val = round(min_val)
            max_val = round(max_val)
            default_val = round(default_val)
            step_val = round(step_val)
        else:
            parameter_type = TYPE_INT
            min_val = int(min_val)
            max_val = int(max_val)
            default_val = int(default_val)
            step_val = int(step_val)
        return Parameter(param_name, parameter_type, default_val, '', min_val, max_val, step_val)

    @staticmethod
    def from_webui_module_details(module_name: str, module_details: ModuleDetail) -> 'ControlNetPreprocessor':
        """Create a ControlNetPreprocessor from a WebUI API definition."""
        parameters = []
        for slider_def in module_details['sliders']:
            parameters.append(ControlNetPreprocessor._parameter_from_slider_def(slider_def))
        return ControlNetPreprocessor(module_name, module_name, parameters)

    @staticmethod
    def from_webui_predefined(module_name: str) -> 'ControlNetPreprocessor':
        """Create a ControlNetPreprocessor from a predefined Forge/WebUI preprocessor definition, if possible."""
        parameters = []
        if module_name not in PREPROCESSOR_NO_RESOLUTION:
            if module_name in PREPROCESSOR_RES_DEFAULTS:
                default_value = PREPROCESSOR_RES_DEFAULTS[module_name]
            else:
                default_value = PREPROCESSOR_RES_DEFAULT
            resolution_parameter = Parameter(RESOLUTION_PARAMETER_NAME, TYPE_INT, default_value, '',
                                             PREPROCESSOR_RES_MIN, PREPROCESSOR_RES_MAX, PREPROCESSOR_RES_STEP)
            parameters.append(resolution_parameter)
        if module_name in THRESHOLD_A_PARAMETER_NAMES:
            slider_def_a = THRESHOLD_A_PARAMETER_NAMES[module_name]
            parameters.append(ControlNetPreprocessor._parameter_from_slider_def(slider_def_a))
        if module_name in THRESHOLD_B_PARAMETER_NAMES:
            slider_def_b = THRESHOLD_B_PARAMETER_NAMES[module_name]
            parameters.append(ControlNetPreprocessor._parameter_from_slider_def(slider_def_b))
        return ControlNetPreprocessor(module_name, module_name, parameters)

