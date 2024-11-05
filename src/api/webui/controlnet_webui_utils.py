"""Helper functions for processing ControlNet configuration data for use with the WebUI API."""
import logging
from json import JSONDecodeError
from typing import Optional

from src.api.controlnet.control_parameter import ControlParameter
from src.api.controlnet.controlnet_constants import PREPROCESSOR_NONE, CONTROLNET_MODEL_NONE, \
    CONTROLNET_REUSE_IMAGE_CODE
from src.api.controlnet.controlnet_preprocessor import ControlNetPreprocessor
from src.api.controlnet.controlnet_unit import ControlNetUnit
from src.api.webui.controlnet_webui_constants import RESIZE_MODE_PARAM_KEY, RESIZE_MODE_LABEL, RESIZE_MODE_DEFAULT, \
    RESIZE_MODE_OPTIONS, ModuleDetail, PREPROCESSOR_NO_CONTROL_MODE, CONTROL_MODE_PARAM_KEY, CONTROL_MODE_LABEL, \
    CONTROL_MODE_DEFAULT, CONTROL_MODE_OPTIONS, FIRST_GENERIC_PARAMETER_KEY, SECOND_GENERIC_PARAMETER_KEY, \
    PREPROCESSOR_RES_PARAM_NAME, PREPROCESSOR_RES_PARAM_KEY, PREPROCESSOR_NO_RESOLUTION, PREPROCESSOR_RES_DEFAULT, \
    PREPROCESSOR_RES_DEFAULTS, PREPROCESSOR_RES_LABEL, PREPROCESSOR_RES_MIN, PREPROCESSOR_RES_MAX, \
    PREPROCESSOR_RES_STEP, THRESHOLD_A_PARAMETER_NAMES, THRESHOLD_B_PARAMETER_NAMES, PREPROCESSOR_MODEL_FREE, \
    ControlNetUnitDict
from src.config.cache import Cache
from src.util.parameter import TYPE_STR, TYPE_FLOAT, TYPE_INT

logger = logging.getLogger(__name__)


def _resize_mode_parameter() -> ControlParameter:
    """Returns the Resize mode preprocessor parameter, which is always identical, but only used for certain
       preprocessors."""
    return ControlParameter(RESIZE_MODE_PARAM_KEY,
                            RESIZE_MODE_LABEL,
                            TYPE_STR,
                            RESIZE_MODE_DEFAULT,
                            options=RESIZE_MODE_OPTIONS)


def get_all_preprocessors(preprocessor_names: list[str],
                          preprocessor_details: Optional[dict[str, ModuleDetail]] = None
                          ) -> list[ControlNetPreprocessor]:
    """Returns the full set of available preprocessors, loading preprocessor details from API definitions if possible,
       or predefined definitions otherwise."""
    preprocessors: list[ControlNetPreprocessor] = []
    for preprocessor_name in preprocessor_names:
        parameters: list[ControlParameter] = []

        # Start with standard "control mode " parameter:
        if preprocessor_name not in PREPROCESSOR_NO_CONTROL_MODE:
            control_type_param = ControlParameter(CONTROL_MODE_PARAM_KEY,
                                                  CONTROL_MODE_LABEL,
                                                  TYPE_STR,
                                                  CONTROL_MODE_DEFAULT,
                                                  options=CONTROL_MODE_OPTIONS)
            parameters.append(control_type_param)

        # Load preprocessor parameters from API details if possible:
        if preprocessor_details is not None and preprocessor_name in preprocessor_details:
            preprocessor_dict = preprocessor_details[preprocessor_name]
            next_threshold_key: Optional[str] = FIRST_GENERIC_PARAMETER_KEY
            resize_insert_index = len(parameters)

            # Iterate through parameter definitions.  Resolution parameter is identified by name, threshold_a and
            # threshold_b are identified by their order.
            for parameter_definition in preprocessor_dict['sliders']:
                name = parameter_definition['name']
                if name.lower() == PREPROCESSOR_RES_PARAM_NAME:
                    parameters.insert(resize_insert_index, _resize_mode_parameter())
                    res_param = ControlParameter(PREPROCESSOR_RES_PARAM_KEY,
                                                 PREPROCESSOR_RES_LABEL,
                                                 TYPE_INT,
                                                 parameter_definition['default'],
                                                 '',
                                                 parameter_definition['min'],
                                                 parameter_definition['max'],
                                                 parameter_definition['step'])
                    parameters.insert(resize_insert_index + 1, res_param)
                else:
                    if next_threshold_key is None:
                        raise RuntimeError(f'Unexpected extra parameter in "{preprocessor_name}" details')
                    key = next_threshold_key
                    if next_threshold_key == FIRST_GENERIC_PARAMETER_KEY:
                        next_threshold_key = SECOND_GENERIC_PARAMETER_KEY
                    else:
                        next_threshold_key = None
                    parameter = ControlParameter(key, name, TYPE_FLOAT, parameter_definition['default'], '',
                                                 parameter_definition['min'],
                                                 parameter_definition['max'],
                                                 parameter_definition['step'])
                    parameters.append(parameter)

        else:  # No API preprocessor definition, use predefined constants:
            if preprocessor_name not in PREPROCESSOR_NO_RESOLUTION:
                parameters.append(_resize_mode_parameter())
                resolution_default = PREPROCESSOR_RES_DEFAULT if preprocessor_name not in PREPROCESSOR_RES_DEFAULTS \
                    else PREPROCESSOR_RES_DEFAULTS[preprocessor_name]
                parameters.append(ControlParameter(PREPROCESSOR_RES_PARAM_KEY, PREPROCESSOR_RES_LABEL, TYPE_INT,
                                                   resolution_default, '', PREPROCESSOR_RES_MIN,
                                                   PREPROCESSOR_RES_MAX, PREPROCESSOR_RES_STEP))
            for param_key, preset_list in ((FIRST_GENERIC_PARAMETER_KEY, THRESHOLD_A_PARAMETER_NAMES),
                                           (SECOND_GENERIC_PARAMETER_KEY, THRESHOLD_B_PARAMETER_NAMES)):
                if preprocessor_name not in preset_list:
                    break  # "threshold_b" will never be used if "threshold_a" isn't
                threshold_def = preset_list[preprocessor_name]
                type_name = TYPE_FLOAT if isinstance(threshold_def['step'], float) else TYPE_INT
                parameters.append(ControlParameter(param_key, threshold_def['name'], type_name,
                                                   threshold_def['default'], '', threshold_def['min'],
                                                   threshold_def['max'], threshold_def['step']))
        # create preprocessor:
        preprocessor = ControlNetPreprocessor(preprocessor_name, preprocessor_name, parameters)
        if preprocessor_details is not None and preprocessor_name in preprocessor_details:
            preprocessor.model_free = preprocessor_details[preprocessor_name]['model_free']
        else:
            preprocessor.model_free = preprocessor_name not in PREPROCESSOR_MODEL_FREE
        preprocessors.append(preprocessor)
    return preprocessors


def default_controlnet_unit() -> ControlNetUnitDict:
    """Creates a ControlNetUnitDict with default parameters."""
    return {
        'use_preview_as_input': False,
        'enabled': False,
        'pixel_perfect': True,
        'low_vram': False,
        'module': PREPROCESSOR_NONE,
        'model': CONTROLNET_MODEL_NONE,
        'weight': 1.0,
        'image': CONTROLNET_REUSE_IMAGE_CODE,
        'control_mode': CONTROL_MODE_OPTIONS[0],  # type: ignore
        'resize_mode': RESIZE_MODE_OPTIONS[1],  # type: ignore
        'guidance_start': 0.0,
        'guidance_end': 1.0
    }


def load_cached_controlnet_units() -> list[ControlNetUnitDict]:
    """Loads ControlNet units from cache and converts them to the required WebUI API dict format.

    Image key values will still need to be replaced with appropriate base64 image data before this can be used in
    requests.
    """
    cache = Cache()
    control_unit_dicts: list[ControlNetUnitDict] = []

    for control_unit_key in (Cache.CONTROLNET_ARGS_0_WEBUI, Cache.CONTROLNET_ARGS_1_WEBUI,
                             Cache.CONTROLNET_ARGS_2_WEBUI):
        try:
            control_unit = ControlNetUnit.deserialize(cache.get(control_unit_key))
        except (KeyError, ValueError, RuntimeError, JSONDecodeError) as err:
            logger.error(f'skipping invalid controlnet unit "{control_unit_key}": {err}')
            continue
        if not control_unit.enabled:
            continue
        preprocessor = control_unit.preprocessor
        control_dict = default_controlnet_unit()
        control_dict['enabled'] = True
        control_dict['pixel_perfect'] = control_unit.pixel_perfect
        control_dict['low_vram'] = control_unit.low_vram
        control_dict['module'] = preprocessor.name
        control_dict['model'] = control_unit.model.full_model_name
        control_dict['weight'] = float(control_unit.control_strength.value)
        control_dict['image'] = control_unit.image_string
        control_dict['guidance_start'] = float(control_unit.control_start.value)
        control_dict['guidance_end'] = float(control_unit.control_end.value)
        for preprocessor_param in preprocessor.parameters:
            control_dict[preprocessor_param.key] = preprocessor_param.value  # type: ignore
        control_unit_dicts.append(control_dict)
    return control_unit_dicts
