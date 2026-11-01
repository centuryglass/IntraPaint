"""Reads and writes the saved soft inpainting settings, whose controls come from the connected backend.

The backend publishes its settings as `ParameterDef` lists (six for the WebUI script, one for ComfyUI's Differential
Diffusion), which `Cache.SOFT_INPAINTING_PARAMETERS` holds as JSON. `Cache.SOFT_INPAINTING_VALUES` holds a JSON object
of the values the user changed, by `ParameterDef.key`. Keys the backend doesn't list are ignored, and unset keys use the
backend's default.
"""
import json
import logging
from typing import Any

from sd_backend_client import ParameterDef

from src.config.cache import Cache

logger = logging.getLogger(__name__)

# Mask blur (pixels at generation resolution) below which the soft band is too narrow to show the effect:
SOFT_INPAINTING_MIN_USEFUL_MASK_BLUR = 12


def load_parameter_defs() -> list[ParameterDef]:
    """Returns the connected backend's soft inpainting settings, skipping any cached entry that no longer parses."""
    parameters: list[ParameterDef] = []
    for serialized in Cache().get(Cache.SOFT_INPAINTING_PARAMETERS):
        try:
            parameters.append(ParameterDef.model_validate_json(serialized))
        except ValueError as err:
            logger.error(f'Ignoring invalid cached soft inpainting parameter: {err}')
    return parameters


def save_parameter_defs(parameters: list[ParameterDef]) -> None:
    """Caches the connected backend's soft inpainting settings."""
    Cache().set(Cache.SOFT_INPAINTING_PARAMETERS, [parameter.model_dump_json() for parameter in parameters])


def load_values() -> dict[str, Any]:
    """Returns the saved setting values by parameter key, or an empty dict if the saved data is invalid."""
    try:
        values = json.loads(Cache().get(Cache.SOFT_INPAINTING_VALUES))
    except json.JSONDecodeError:
        return {}
    return values if isinstance(values, dict) else {}


def save_value(key: str, value: Any) -> None:
    """Saves one setting's value."""
    values = load_values()
    values[key] = value
    Cache().set(Cache.SOFT_INPAINTING_VALUES, json.dumps(values))


def request_values(parameters: list[ParameterDef]) -> dict[str, Any]:
    """Returns the saved values that are valid for `parameters`, for `DiffusionParams.soft_inpainting_params`.

    A saved value the library would reject, such as one saved for another backend's parameter of the same key, is
    left out so the backend's default applies.
    """
    saved = load_values()
    values: dict[str, Any] = {}
    for parameter in parameters:
        if parameter.key not in saved:
            continue
        value = saved[parameter.key]
        default = parameter.default_value
        if isinstance(default, bool) or isinstance(value, bool):
            valid = isinstance(default, bool) and isinstance(value, bool)
        elif isinstance(default, (int, float)):
            valid = isinstance(value, (int, float)) \
                and (parameter.min_val is None or value >= parameter.min_val) \
                and (parameter.max_val is None or value <= parameter.max_val)
        else:
            valid = isinstance(value, type(default))
        if not valid:
            continue
        values[parameter.key] = value
    return values
