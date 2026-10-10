"""Display text for the library's ControlNet `ParameterDef` values.

WebUI parameter definitions keep their display label in `ParameterDef.description` and carry no tooltip. ComfyUI
definitions use the key as the label and keep the tooltip in `description`. `parameter_label` and
`parameter_tooltip` tell the two apart by key.
"""
from sd_backend_client import CONTROL_MODE_PARAM_KEY, PREPROCESSOR_RES_PARAM_KEY, RESIZE_MODE_PARAM_KEY, ParameterDef

# Keys that only WebUI preprocessors use. WebUI labels its parameters through `ParameterDef.description`.
_WEBUI_KEYS = (CONTROL_MODE_PARAM_KEY, RESIZE_MODE_PARAM_KEY, PREPROCESSOR_RES_PARAM_KEY, 'threshold_a', 'threshold_b')


def parameter_label(param: ParameterDef) -> str:
    """Returns the text that labels a parameter's input widget."""
    if param.key in _WEBUI_KEYS and param.description != '':
        return param.description
    return param.key


def parameter_tooltip(param: ParameterDef) -> str:
    """Returns a parameter's tooltip text, which is empty for WebUI parameters."""
    return '' if param.key in _WEBUI_KEYS else param.description
