"""Defines a ControlNet preprocessor's name and parameters, for use with a Stable-Diffusion API"""
import json
from copy import deepcopy
from typing import Optional, cast, Any

from src.api.comfyui.comfyui_types import NodeInfoResponse, ParamDef, IntParamDef, BoolParamDef, FloatParamDef, \
    CONTROLNET_PREPROCESSOR_OUTPUT_NAME, StrParamDef
from src.api.comfyui.nodes.controlnet.dynamic_preprocessor_node import DynamicPreprocessorNode
from src.api.webui.controlnet_webui import ControlNetSliderDef, ModuleDetail, ControlNetUnitDict, \
    PREPROCESSOR_RES_PARAM_NAME, PREPROCESSOR_RES_PARAM_KEY, THRESHOLD_A_PARAMETER_NAMES, PREPROCESSOR_RES_MIN, \
    PREPROCESSOR_RES_MAX, PREPROCESSOR_RES_DEFAULT, PREPROCESSOR_RES_STEP, PREPROCESSOR_RES_DEFAULTS, \
    PREPROCESSOR_NO_RESOLUTION, THRESHOLD_B_PARAMETER_NAMES
from src.util.parameter import Parameter, ParamType, TYPE_INT, TYPE_BOOL, TYPE_FLOAT, TYPE_STR


class ControlNetPreprocessor:
    """Defines a ControlNet preprocessor's name and parameters, for use with a Stable-Diffusion API."""

    def __init__(self, name: str, display_name: str, parameters: list[Parameter]) -> None:
        """Parameter objects are used similarly to the way they're used in src.image.filter, except that the name value
           holds a key string, and description is the display name."""
        self._name = name
        self._display_name = display_name
        self._parameters = parameters
        self._category_name = ''
        self._values: list[ParamType] = []
        self._has_image_input = True
        self._has_mask_input = True
        for parameter in self._parameters:
            self._values.append(parameter.default_value)

    @property
    def category_name(self) -> str:
        """Access the category name: an extra string that's used for categorizing preprocessor types, provided in
           ComfyUI only."""
        return self._category_name

    @property
    def has_image_input(self) -> bool:
        """Accesses whether this preprocessor accepts an image input when converted into a ComfyUI node."""
        return self._has_image_input

    @has_image_input.setter
    def has_image_input(self, image_input: bool) -> None:
        self._has_image_input = image_input

    @property
    def has_mask_input(self) -> bool:
        """Accesses whether this preprocessor accepts a mask input when converted into a ComfyUI node."""
        return self._has_mask_input

    @has_mask_input.setter
    def has_mask_input(self, mask_input: bool) -> None:
        self._has_mask_input = mask_input

    @category_name.setter
    def category_name(self, category: str) -> None:
        self._category_name = category

    def __deepcopy__(self, memo: dict[int, Any]) -> 'ControlNetPreprocessor':
        self_copy = ControlNetPreprocessor(self._name, self._display_name, deepcopy(self._parameters, memo))
        memo[id(self)] = self_copy
        return self_copy

    def __eq__(self, other: Any) -> bool:
        if (not isinstance(other, ControlNetPreprocessor) or self._name != other.name
                or self.parameter_keys != other.parameter_keys):
            return False
        for i, parameter in enumerate(self._parameters):
            if self._values[i] != other.get_value(parameter.name):
                return False
        return True

    @property
    def name(self) -> str:
        """Returns the preprocessor name"""
        return self._name

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
        """Sets the value of a parameter, validating it first.  This will also convert between int and float if
           needed."""
        for i, param in enumerate(self._parameters):
            if param_key == param.name:
                if param.type_name == TYPE_FLOAT and isinstance(value, int):
                    value = float(value)
                elif param.type_name == TYPE_INT and isinstance(value, float):
                    value = round(value)
                param.validate(value, raise_on_failure=True)
                self._values[i] = value
                return
        raise KeyError(f'Parameter "{param_key}" not found in "{self._name}" preprocessor')

    def get_parameter_webui_key(self, parameter: Parameter) -> str:
        """Gets a preprocessor parameter's WebUI key, or raise ValueError if the parameter doesn't share a name with
           one of the preprocessor parameters."""
        threshold_a_encountered = False
        for own_param in self._parameters:
            if own_param.name != parameter.name:
                if own_param.name != PREPROCESSOR_RES_PARAM_NAME:
                    threshold_a_encountered = True
                continue
            if parameter.name.lower() == PREPROCESSOR_RES_PARAM_NAME.lower():
                return PREPROCESSOR_RES_PARAM_KEY
            return 'threshold_b' if threshold_a_encountered else 'threshold_a'
        raise ValueError(f'Parameter "{parameter.name}" not found in preprocessor "{self._name}"')

    def load_values_from_webui_data(self, controlnet_unit: ControlNetUnitDict) -> None:
        """Sets values from WebUI ControlNet unit data."""
        if controlnet_unit['module'] != self._name:
            raise ValueError(f'Tried to init proprocessor "{self._name}" using values for preprocessor'
                             f' "{controlnet_unit["module"]}"')
        for param in self._parameters:
            parameter_key = self.get_parameter_webui_key(param)
            self.set_value(param.name, controlnet_unit[parameter_key])  # type: ignore

    def update_webui_data(self, controlnet_unit: ControlNetUnitDict) -> None:
        """Writes preprocessor-specific parameters to a WebUI request's ControlNet script dict."""
        controlnet_unit['module'] = self._name
        for i, param in enumerate(self._parameters):
            value = self._values[i]
            param_key = self.get_parameter_webui_key(param)
            controlnet_unit[param_key] = value  # type: ignore

    def create_comfyui_node(self) -> DynamicPreprocessorNode:
        """Initializes a ComfyUI node from the preprocessor definition and values."""
        value_dict: dict[str, ParamType] = {}
        for i, param in enumerate(self._parameters):
            value_dict[param.name] = self._values[i]
        return DynamicPreprocessorNode(self._name, value_dict, self.has_image_input, self.has_mask_input)

    @staticmethod
    def from_comfyui_node_def(node_info: NodeInfoResponse) -> 'ControlNetPreprocessor':
        """Create a ControlNetPreprocessor from a ComfyUI API definition."""
        if 'output_name' in node_info and node_info['output_name'] != CONTROLNET_PREPROCESSOR_OUTPUT_NAME:
            raise ValueError('Not a vaild ControlNetPreprocessor node: unexpected output format'
                             f' {node_info["output_name"]}')
        name = node_info['name']
        if 'display_name' in node_info:
            display_name = node_info['display_name']
        else:
            display_name = name
        parameter_list: list[Parameter] = []
        image_input = False
        mask_input = False
        for input_category in ('required', 'optional'):
            if input_category not in node_info['input_order'] or input_category not in node_info['input']:
                continue
            if input_category == 'required':  # TypedDict doesn't like direct indexing with input_category
                inputs = node_info['input_order']['required']
                input_dict = node_info['input']['required']
            else:
                inputs = node_info['input_order']['optional']
                input_dict = node_info['input']['optional']
            for input_name in inputs:
                if input_name == DynamicPreprocessorNode.IMAGE:
                    image_input = True
                    continue
                if input_name == DynamicPreprocessorNode.MASK:
                    mask_input = True
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
                    default_value = round(int_param_def['default'])
                    min_val = round(int_param_def['min'])
                    max_val = round(int_param_def['max'])
                    if 'step' in int_param_def:
                        step_val = round(int_param_def['step'])
                elif input_type_or_list == 'BOOLEAN':
                    parameter_type = TYPE_BOOL
                    assert input_param_def is not None
                    bool_param_def = cast(BoolParamDef, input_param_def)
                    default_value = bool_param_def['default']
                elif input_type_or_list == 'FLOAT':
                    parameter_type = TYPE_FLOAT
                    assert input_param_def is not None
                    float_param_def = cast(FloatParamDef, input_param_def)
                    default_value = float(float_param_def['default'])
                    min_val = float(float_param_def['min'])
                    max_val = float(float_param_def['max'])
                    if 'step' in float_param_def:
                        step_val = float(float_param_def['step'])
                elif input_type_or_list == 'STRING':
                    parameter_type = TYPE_STR
                    string_param_def = cast(StrParamDef, input_param_def)
                    default_value = string_param_def['default']
                elif isinstance(input_type_or_list, list):
                    parameter_type = TYPE_STR
                    options = input_type_or_list
                    default_value = options[0]
                else:
                    raise ValueError(f'"{name}" preprocessor node: unexpected input {input_tuple}')
                parameter = Parameter(param_name, parameter_type, default_value, param_description, min_val, max_val,
                                      step_val)
                if options is not None:
                    parameter.set_valid_options(cast(list[ParamType], options))
                parameter_list.append(parameter)
        preprocessor = ControlNetPreprocessor(name, display_name, parameter_list)
        if 'category' in node_info:
            preprocessor.category_name = node_info['category']
        preprocessor.has_image_input = image_input
        preprocessor.has_mask_input = mask_input
        return preprocessor

    @staticmethod
    def _parameter_from_slider_def(slider_def: ControlNetSliderDef) -> Parameter:
        param_name = slider_def['name']
        min_val = slider_def['min']
        max_val = slider_def['max']
        default_val = slider_def['default']
        step_val = slider_def['step']
        if any((num % 1) != 0.0 for num in (min_val, max_val, default_val, step_val)):
            parameter_type = TYPE_FLOAT
            min_val = float(min_val)
            max_val = float(max_val)
            default_val = float(default_val)
            step_val = float(step_val)
        else:
            parameter_type = TYPE_INT
            min_val = round(min_val)
            max_val = round(max_val)
            default_val = round(default_val)
            step_val = round(step_val)
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
            resolution_parameter = Parameter(PREPROCESSOR_RES_PARAM_NAME, TYPE_INT, default_value, '',
                                             PREPROCESSOR_RES_MIN, PREPROCESSOR_RES_MAX, PREPROCESSOR_RES_STEP)
            parameters.append(resolution_parameter)
        if module_name in THRESHOLD_A_PARAMETER_NAMES:
            slider_def_a = THRESHOLD_A_PARAMETER_NAMES[module_name]
            parameters.append(ControlNetPreprocessor._parameter_from_slider_def(slider_def_a))
        if module_name in THRESHOLD_B_PARAMETER_NAMES:
            slider_def_b = THRESHOLD_B_PARAMETER_NAMES[module_name]
            parameters.append(ControlNetPreprocessor._parameter_from_slider_def(slider_def_b))
        return ControlNetPreprocessor(module_name, module_name, parameters)
