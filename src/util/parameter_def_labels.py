"""Display text for the library's ControlNet `ParameterDef` values.

`ParameterDef.display_name` is the label, empty when the backend provides none (ComfyUI), and `ParameterDef.description`
is the tooltip, empty when the backend provides none (WebUI).
"""
from sd_backend_client import ParameterDef


def parameter_label(param: ParameterDef) -> str:
    """Returns the text that labels a parameter's input widget, falling back to the parameter key."""
    return param.display_name if param.display_name != '' else param.key


def parameter_tooltip(param: ParameterDef) -> str:
    """Returns a parameter's tooltip text, which is empty when the backend provides none."""
    return param.description
