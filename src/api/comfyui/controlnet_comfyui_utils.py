"""Helper functions for processing ControlNet configuration data for use with the ComfyUI API."""
import logging
from typing import cast, Optional

from src.api.comfyui.comfyui_types import (NodeInfoResponse, CONTROLNET_PREPROCESSOR_CATEGORY, IntParamDef,
                                           BoolParamDef, FloatParamDef, StrParamDef, ParamDef)
from src.api.comfyui.nodes.controlnet.dynamic_preprocessor_node import DynamicPreprocessorNode
from src.api.controlnet.control_parameter import ControlParameter
from src.api.controlnet.controlnet_constants import PREPROCESSOR_NONE
from src.api.controlnet.controlnet_preprocessor import ControlNetPreprocessor
from src.util.parameter import TYPE_INT, TYPE_BOOL, TYPE_FLOAT, TYPE_STR

# If a preprocessor name ends in "Preprocessor", we can leave that part out of the display name.
PREPROCESSOR_SUFFIX = 'Preprocessor'


logger = logging.getLogger(__name__)

# These nodes are categorized under ControlNet preprocessors, and appear to have valid inputs and outputs, but
# shouldn't actually be used for various reasons:
INVALID_PREPROCESSOR_NODES = {
    # Selects between preprocessors, presumably for advanced routing purposes that IntraPaint doesn't support:
    'ControlNetPreprocessorSelector',
    # Seems to apply every possible preprocessor, presumably so you can see what all of them would generate:
    'ExecuteAllControlNetPreprocessors',
    # Looks like it's meant for extracting a size, not transforming an image:
    'ImageGenResolutionFromImage',
    # image output is OPTICAL_FLOW type, which we aren't able to handle:
    'Unimatch_OptFlowPreprocessor'
}


def get_all_preprocessors(node_data: dict[str, NodeInfoResponse]) -> list[ControlNetPreprocessor]:
    """Parses available node data to find the complete list of usable ControlNet preprocessiors."""
    none_preprocessor_found = False
    preprocessors: list[ControlNetPreprocessor] = []
    for node_info in node_data.values():
        category = node_info['category']
        if CONTROLNET_PREPROCESSOR_CATEGORY not in category:
            continue
        key = node_info['name']
        if key in INVALID_PREPROCESSOR_NODES:
            continue

        # read all parameters:
        parameter_list: list[ControlParameter] = []
        input_lists = node_info['input_order']
        input_dicts = node_info['input']
        has_image_input = False
        has_mask_input = False

        invalid_input_found = False
        for input_category in ('required', 'optional'):
            if invalid_input_found:
                break
            if input_category not in input_lists or input_category not in input_dicts:
                continue
            inputs = input_lists[input_category]  # type: ignore
            input_dict = input_dicts[input_category]  # type: ignore

            for input_name in inputs:
                if input_name == DynamicPreprocessorNode.IMAGE:
                    has_image_input = True
                    continue
                if input_name == DynamicPreprocessorNode.MASK:
                    has_mask_input = True
                    continue
                input_tuple = input_dict[input_name]
                input_type_or_list = input_tuple[0]
                input_param_def = None if len(input_tuple) < 2 else cast(ParamDef, input_tuple[1])

                # Find Parameter init values:
                param_key = input_name
                if input_param_def is not None and 'tooltip' in input_param_def:
                    param_description = input_param_def['tooltip']
                else:
                    param_description = ''
                default_value: Optional[int | float | str]
                min_val: Optional[int | float] = None
                max_val: Optional[int | float] = None
                step_val: Optional[int | float] = None
                options: Optional[list[str]] = None
                multiline: Optional[bool] = None

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
                    if 'multiline' in string_param_def:
                        multiline = string_param_def['multiline']
                elif isinstance(input_type_or_list, list):
                    parameter_type = TYPE_STR
                    options = input_type_or_list
                    default_value = options[0]
                elif input_category == 'optional':
                    logger.error(f'"{key}" preprocessor: not sure how to handle optional input'
                                 f' {input_name}={input_tuple}, ignoring it.')
                    continue
                else:
                    logger.error(f'Skipping "{key}" preprocessor node: not sure how to handle input'
                                 f' {input_name}={input_tuple}')
                    invalid_input_found = True
                    break
                parameter = ControlParameter(param_key, param_key, parameter_type, default_value, param_description,
                                             min_val, max_val, step_val, options)
                if multiline is not None:
                    parameter.set_multiline(multiline)
                parameter_list.append(parameter)
        if invalid_input_found:
            continue
        if 'display_name' in node_info:
            display_name = node_info['display_name']
        else:
            display_name = key
        if display_name.endswith(PREPROCESSOR_SUFFIX):
            display_name = display_name[:-len(PREPROCESSOR_SUFFIX)]
        preprocessor = ControlNetPreprocessor(key, display_name, parameter_list)
        preprocessor.description = node_info['description']
        preprocessor.category_name = category
        preprocessor.has_image_input = has_image_input
        preprocessor.has_mask_input = has_mask_input
        preprocessors.append(preprocessor)
        if key == PREPROCESSOR_NONE:
            none_preprocessor_found = True
    if not none_preprocessor_found:
        preprocessors.append(ControlNetPreprocessor(PREPROCESSOR_NONE, PREPROCESSOR_NONE, []))
    return preprocessors
