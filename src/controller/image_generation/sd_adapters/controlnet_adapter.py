"""Converts between saved ControlNet settings and the library's `ControlNetUnit`.

`Cache.CONTROLNET_ARGS_*` and `Cache.SD_UPSCALING_CONTROLNET_TILE_SETTINGS` hold JSON in one of two formats:
- The legacy format written by `src.api.controlnet.controlnet_unit.ControlNetUnit.serialize`, with either
  `ControlKeyType`. The key type only renames the strength, start and end parameters, so both read the same way.
- The format `SavedControlNetUnit.to_json` writes, which wraps the library's own `ControlNetUnit` dump.

`SavedControlNetUnit.from_json` reads both formats, and `to_json` writes only the second.

`legacy_preprocessor` and `preprocessor_from_legacy` convert preprocessors for the ControlNet panel, which still uses
`src.api`'s preprocessor type (#39, step 5).
"""
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Optional, cast

from PIL import Image
from PySide6.QtGui import QImage
from sd_backend_client import CONTROLNET_MODEL_NONE, PREPROCESSOR_NONE, ControlNetModel, ControlNetPreprocessor, \
    ControlNetUnit, ParameterDef, PreprocessorParams

from src.api.controlnet import controlnet_preprocessor as legacy
from src.api.controlnet.control_parameter import ControlParameter, ControlParamTypeList
from src.api.controlnet.controlnet_constants import CONTROLNET_REUSE_IMAGE_CODE
from src.config.cache import Cache
from src.controller.image_generation.sd_adapters.image_adapter import qimage_to_pil
from src.util.parameter import get_parameter_type
from src.util.visual.pil_image_utils import PIL_OPEN_FORMATS

logger = logging.getLogger(__name__)

# Keys of the format `SavedControlNetUnit.to_json` writes:
ENABLED_KEY = 'enabled'
IMAGE_KEY = 'image'
UNIT_KEY = 'unit'

# Key found only in the legacy format:
LEGACY_PREPROCESSOR_KEY = 'preprocessor_serialized'


@dataclass
class SavedControlNetUnit:
    """One saved ControlNet unit: the library unit plus the two settings that exist only in IntraPaint's UI.

    Attributes
    ----------
    enabled: bool
        Whether the unit is applied to generation.
    image_string: str
        Where the control image comes from: `CONTROLNET_REUSE_IMAGE_CODE` for the generation area content, a path
        to an image file, or the empty string for no image.
    unit: ControlNetUnit
        All other settings. Its `image` is always unset; `to_request_unit` fills it from `image_string`.
    """
    enabled: bool
    image_string: str
    unit: ControlNetUnit

    def to_json(self) -> str:
        """Serializes the unit, writing the library's `ControlNetUnit` dump."""
        return json.dumps({
            ENABLED_KEY: self.enabled,
            IMAGE_KEY: self.image_string,
            UNIT_KEY: self.unit.model_dump(mode='json', exclude={'image'})
        })

    @staticmethod
    def from_json(data_str: str) -> 'SavedControlNetUnit':
        """Parses a saved unit in either format.

        Raises
        ------
        ValueError
            If the data is not valid JSON in either format, or holds values the library rejects. pydantic's
            `ValidationError` and `JSONDecodeError` are both subclasses.
        """
        data = json.loads(data_str)
        if not isinstance(data, dict):
            raise ValueError(f'Expected a saved ControlNet unit object, found {type(data).__name__}')
        try:
            if LEGACY_PREPROCESSOR_KEY in data:
                return _from_legacy_dict(data)
            unit = ControlNetUnit.model_validate(data[UNIT_KEY])
            return SavedControlNetUnit(bool(data[ENABLED_KEY]), str(data[IMAGE_KEY]), unit)
        except (KeyError, TypeError) as err:
            raise ValueError(f'Invalid saved ControlNet unit: {err!r}') from err


def _from_legacy_dict(data: dict[str, Any]) -> SavedControlNetUnit:
    """Converts a dict in the legacy `ControlNetUnit.serialize` format."""
    model_name = data['model_name']
    model = None if model_name == CONTROLNET_MODEL_NONE else ControlNetModel(model_name)
    unit = ControlNetUnit(preprocessor=_preprocessor_from_legacy_json(data[LEGACY_PREPROCESSOR_KEY]),
                          model=model,
                          control_strength=data['control_strength'],
                          control_start=data['control_start'],
                          control_end=data['control_end'],
                          pixel_perfect=data['pixel_perfect'],
                          low_vram=data['low_vram'])
    return SavedControlNetUnit(bool(data['enabled']), str(data['image']), unit)


def _preprocessor_from_legacy_json(data_str: str) -> Optional[PreprocessorParams]:
    """Converts a legacy `ControlNetPreprocessor.serialize` string, returning None for the "None" preprocessor.

    Each parameter's `ParameterDef.description` takes its legacy `description`, or its `name` when that is empty. That
    matches the library: ComfyUI parameters keep their tooltip in `description`, and WebUI parameters keep their label
    in `name`.
    """
    data = json.loads(data_str)
    name = data['name']
    if name.lower() == PREPROCESSOR_NONE.lower():
        return None
    parameters: list[ParameterDef] = []
    parameter_values: dict[str, Any] = {}
    for param_str in data['parameters_serialized']:
        param_data = json.loads(param_str)
        param_def = json.loads(param_data['parameter'])
        key = param_data['key']
        value = param_data['value']
        parameters.append(ParameterDef(key=key,
                                       default_value=param_def.get('default_value', value),
                                       description=param_def.get('description') or param_def['name'],
                                       option_list=param_def.get('options'),
                                       min_val=param_def.get('minimum'),
                                       max_val=param_def.get('maximum'),
                                       step_val=param_def.get('step')))
        parameter_values[key] = value
    typedef = ControlNetPreprocessor(name=name,
                                     category_name=data.get('category_name') or '',
                                     description=data.get('description') or data.get('display_name') or '',
                                     has_image_input=data['has_image'],
                                     has_mask_input=data['has_mask'],
                                     model_free=data['model_free'],
                                     parameters=parameters)
    return PreprocessorParams(typedef=typedef, parameter_values=parameter_values)


def preprocessor_from_legacy(preprocessor: legacy.ControlNetPreprocessor) -> Optional[PreprocessorParams]:
    """Converts a `src.api` preprocessor and its parameter values, returning None for the "None" preprocessor.

    Raises
    ------
    ValueError
        If a parameter value is one the library rejects.
    """
    return _preprocessor_from_legacy_json(preprocessor.serialize())


def legacy_preprocessor(preprocessor: ControlNetPreprocessor) -> legacy.ControlNetPreprocessor:
    """Converts a ComfyUI preprocessor from the library into a `src.api` preprocessor set to its default values.

    The library keeps a ComfyUI node's display name as the first line of `description`, and each parameter's tooltip
    in its `description`. Each parameter's display name is its key, as `src.api` named ComfyUI parameters.

    Raises
    ------
    TypeError
        If a parameter's options don't all share its default value's type.
    ValueError
        If a parameter's options are outside its limits.
    """
    display_name, _, description = preprocessor.description.partition('\n')
    # ControlParameter raises TypeError for an option list whose types differ from the default's:
    parameters = [ControlParameter(param.key, param.key, get_parameter_type(param.default_value), param.default_value,
                                   param.description, param.min_val, param.max_val, param.step_val,
                                   cast(Optional[ControlParamTypeList], param.option_list))
                  for param in preprocessor.parameters]
    converted = legacy.ControlNetPreprocessor(preprocessor.name, display_name or preprocessor.name, parameters)
    converted.description = description
    converted.category_name = preprocessor.category_name
    converted.has_image_input = preprocessor.has_image_input
    converted.has_mask_input = preprocessor.has_mask_input
    converted.model_free = preprocessor.model_free
    return converted


def to_request_unit(saved: SavedControlNetUnit, source_image: Optional[QImage],
                    source_is_init_image: bool) -> Optional[ControlNetUnit]:
    """Returns the library unit to send for a saved unit, or None if the unit is disabled or unusable.

    A unit is unusable when it has neither a model nor a preprocessor, when it has no model and its preprocessor needs
    one, or when its image file can't be loaded.

    Parameters
    ----------
    saved: SavedControlNetUnit
        The saved unit.
    source_image: Optional[QImage]
        Generation area content, used for `CONTROLNET_REUSE_IMAGE_CODE` when it isn't already the init image.
    source_is_init_image: bool
        Whether the request already sends `source_image` as its init image. `CONTROLNET_REUSE_IMAGE_CODE` then leaves
        the unit's image unset, so both backends reuse the init image and, when inpainting, its mask. Inpainting
        preprocessors fail server-side without that mask.
    """
    if not saved.enabled:
        return None
    unit = saved.unit
    if unit.model is None and (unit.preprocessor is None or not unit.preprocessor.typedef.model_free):
        logger.info('Skipping ControlNet unit: no model is set, and its preprocessor needs one.')
        return None
    image: Optional[Image.Image] = None
    if saved.image_string == CONTROLNET_REUSE_IMAGE_CODE:
        if not source_is_init_image and source_image is not None:
            image = qimage_to_pil(source_image)
    elif saved.image_string != '':
        if not os.path.isfile(saved.image_string):
            logger.error(f'Skipping ControlNet unit: image file "{saved.image_string}" not found')
            return None
        try:
            with Image.open(saved.image_string, formats=PIL_OPEN_FORMATS) as file_image:
                image = file_image.convert('RGBA')
        except (OSError, ValueError) as err:
            logger.error(f'Skipping ControlNet unit: loading image "{saved.image_string}" failed: {err}')
            return None
    request_unit = unit.model_copy(deep=True)
    request_unit.image = image
    return request_unit


def load_request_units(cache_keys: list[str], source_image: Optional[QImage],
                       source_is_init_image: bool) -> list[ControlNetUnit]:
    """Returns the library units to send for the saved units under a list of cache keys, skipping unusable units.

    An empty cached value, the default for a unit the user never configured, is skipped without logging an error. See
    `to_request_unit` for the parameters.
    """
    cache = Cache()
    units: list[ControlNetUnit] = []
    for cache_key in cache_keys:
        saved_json = cache.get(cache_key)
        if saved_json == '':
            continue
        try:
            saved = SavedControlNetUnit.from_json(saved_json)
        except (KeyError, ValueError) as err:
            logger.error(f'Skipping invalid ControlNet unit "{cache_key}": {err}')
            continue
        request_unit = to_request_unit(saved, source_image, source_is_init_image)
        if request_unit is not None:
            units.append(request_unit)
    return units
