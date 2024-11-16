"""Sorts ControlNet models and preprocessors into categories, automatically filtering out unavailable options."""
import re
from copy import deepcopy
from typing import Optional, cast

from src.api.controlnet.controlnet_constants import STATIC_CONTROL_TYPE_DEFS, \
    PREPROCESSOR_NONE, CONTROLNET_MODEL_NONE, StaticControlTypeDef
from src.api.webui.controlnet_webui_constants import ControlTypeDef, ControlTypeResponse, PREPROCESSOR_MODEL_FREE


class ControlNetCategoryBuilder:
    """Sorts ControlNet models and preprocessors into categories, automatically filtering out unavailable options."""

    def __init__(self, preprocessor_names: list[str], model_names: list[str],
                 preprocessor_comfyui_categories: Optional[dict[str, str]] = None,
                 control_type_defs: Optional[ControlTypeResponse] = None):
        self._preprocessors: list[str] = preprocessor_names
        self._models: list[str] = model_names
        self._control_types: dict[str, ControlTypeDef] = {}
        if PREPROCESSOR_NONE not in self._preprocessors and PREPROCESSOR_NONE.lower() not in self._preprocessors:
            self._preprocessors.append(PREPROCESSOR_NONE)
        if CONTROLNET_MODEL_NONE not in self._models and CONTROLNET_MODEL_NONE.lower() not in self._models:
            self._models.append(CONTROLNET_MODEL_NONE)

        # Apply definitions if available:
        api_type_dict = None if control_type_defs is None else control_type_defs['control_types']
        type_dict: dict[str, ControlTypeDef] | dict[str, StaticControlTypeDef] | None
        for type_dict in (api_type_dict, STATIC_CONTROL_TYPE_DEFS):
            if type_dict is None:
                continue
            for type_name, type_def in type_dict.items():
                if type_name not in self._control_types:
                    self._control_types[type_name] = {
                        'module_list': [PREPROCESSOR_NONE],
                        'model_list': [CONTROLNET_MODEL_NONE],
                        'default_option': PREPROCESSOR_NONE,
                        'default_model': CONTROLNET_MODEL_NONE
                    }
                saved_type_def = self._control_types[type_name]
                for preprocessor in type_def['module_list']:
                    if preprocessor in self._preprocessors and preprocessor not in saved_type_def['module_list']:
                        saved_type_def['module_list'].append(preprocessor)
                for model in type_def['model_list']:
                    if model in self._models and model not in saved_type_def['model_list']:
                        saved_type_def['model_list'].append(model)
                if saved_type_def['default_option'] == PREPROCESSOR_NONE:
                    if type_def['default_option'] != PREPROCESSOR_NONE \
                            and type_def['default_option'] in self._preprocessors:
                        saved_type_def['default_option'] = type_def['default_option']
                if saved_type_def['default_model'] == CONTROLNET_MODEL_NONE \
                        and type_def['default_model'] != CONTROLNET_MODEL_NONE \
                        and type_def['default_model'] in self._models:
                    saved_type_def['default_model'] = type_def['default_model']
                # Check for preprocessor/model regex patterns from the static definitions:
                static_type_def = cast(StaticControlTypeDef, type_def)
                if 'preprocessor_pattern' in static_type_def:
                    preprocessor_pattern = re.compile(static_type_def['preprocessor_pattern'])
                    for preprocessor in self._preprocessors:
                        if preprocessor in saved_type_def['module_list']:
                            continue
                        if preprocessor_comfyui_categories is not None \
                                and preprocessor in preprocessor_comfyui_categories:
                            category = preprocessor_comfyui_categories[preprocessor]
                        else:
                            category = ''
                        if preprocessor_pattern.search(preprocessor) is not None \
                                or preprocessor_pattern.search(category) is not None:
                            saved_type_def['module_list'].append(preprocessor)
                if 'model_pattern' in static_type_def:
                    model_pattern = re.compile(static_type_def['model_pattern'])
                    for model in self._models:
                        if model not in saved_type_def['model_list'] and \
                                model_pattern.search(model) is not None:
                            saved_type_def['model_list'].append(model)

    def get_control_types(self) -> dict[str, ControlTypeDef]:
        """Returns all control types that have at least one preprocessor that's not 'none', and either at least one
           model that's not 'None' or are model-free ControlNet types."""
        non_empty_types: dict[str, ControlTypeDef] = {}
        for name, type_def in self._control_types.items():
            if len(type_def['module_list']) > 1 and (len(type_def['model_list']) > 1
                                                     or name in PREPROCESSOR_MODEL_FREE):
                non_empty_types[name] = deepcopy(type_def)
        return non_empty_types
