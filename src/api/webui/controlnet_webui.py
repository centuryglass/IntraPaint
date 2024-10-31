"""Data format definitions for the WebUI API's ControlNet endpoints."""
from typing import TypedDict, NotRequired, Dict, Optional, Literal, Any

from src.api.controlnet_constants import PREPROCESSOR_NONE, CONTROLNET_MODEL_NONE, CONTROLNET_REUSE_IMAGE_CODE, \
    TOOLTIP_CONTROLNET_WEIGHT, TOOLTIP_START_STEP, TOOLTIP_END_STEP, TOOLTIP_CONTROL_MODE, \
    TOOLTIP_RESIZE_MODE, _tr, ControlTypeDef
from src.util.math_utils import clamp
from src.util.parameter import Parameter, TYPE_FLOAT, TYPE_STR


CONTROLNET_SCRIPT_KEY = 'controlNet'

# Settings for the "Resolution" option shared by most preprocessors:
PREPROCESSOR_RES_PARAM_NAME = 'Resolution'
PREPROCESSOR_RES_PARAM_KEY = 'processor_res'
PREPROCESSOR_RES_MIN = 128
PREPROCESSOR_RES_MAX = 2048
PREPROCESSOR_RES_DEFAULT = 512
PREPROCESSOR_RES_STEP = 8


class ControlNetModelResponse(TypedDict):
    """Response format from the WebUI API when loading ControlNet model options."""
    model_list: list[str]


class ControlNetSliderDef(TypedDict):
    """Defines a ControlNet preprocessor's use of the resolution, 'threshold_a' or 'threshold_b' parameters."""
    name: str
    min: float | int
    max: float | int
    default: float | int
    step: float | int


class ModuleDetail(TypedDict):
    """Defines a ControlNet preprocessor's parameters as returned by the module list endpoint."""
    model_free: bool  # Whether the module can be used without a model.
    sliders: list[ControlNetSliderDef]


class ControlNetModuleResponse(TypedDict):
    """Response format when loading ControlNet preprocessor options."""
    module_list: list[str]
    module_details: NotRequired[Dict[str, ModuleDetail]]  # NOTE: not included in Forge.


CONTROL_MODE_OPTIONS = ['Balanced', 'My prompt is more important', 'ControlNet is more important']
RESIZE_MODE_OPTIONS = ['Just Resize', 'Crop and Resize', 'Resize and Fill']


class ControlNetUnitDict(TypedDict):
    """Data format used with the ControlNet script's values within the alwayson_scripts section in WebUI generation
       requests. In the script values section, The ControlNet value parameter is a list holding up to three of these
       objects.  Optional parameters that only affect the UI are omitted."""
    use_preview_as_input: bool
    enabled: bool
    pixel_perfect: NotRequired[bool]
    low_vram: NotRequired[bool]
    module: str  # AKA preprocessor
    model: str
    weight: float
    image: Optional[str]  # base64 image, usually necessary.
    resize_mode: Literal['Just Resize', 'Crop and Resize', 'Resize and Fill']
    guidance_start: float
    guidance_end: float
    control_mode: NotRequired[Literal['Balanced', 'My prompt is more important', 'ControlNet is more important']]

    # preprocessor-specific values:
    processor_res: NotRequired[int]  # Some use this, some don't. Set to -1 or omit if it's not used.
    # Effects of threshold values (if any) vary based on preprocessor.
    threshold_a: NotRequired[float]
    threshold_b: NotRequired[float]


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


def get_common_controlnet_unit_parameters(preprocessor_name: str, include_webui_options: bool) -> list[Parameter]:
    """Returns new Parameter object defining keys, bounds, and default values for the weight, guidance_start, and
       guidance_end ControlNet unit parameters."""
    default_params = [
        Parameter('weight', TYPE_FLOAT, 1.0, TOOLTIP_CONTROLNET_WEIGHT, 0.0, 1.0,
                  0.01),
        Parameter('guidance_start', TYPE_FLOAT, 0.0, TOOLTIP_START_STEP, 0.0, 1.0,
                  0.01),
        Parameter('guidance_end', TYPE_FLOAT, 1.0, TOOLTIP_END_STEP, 0.0, 1.0,
                  0.01)
    ]
    if include_webui_options:
        if preprocessor_name not in PREPROCESSOR_NO_CONTROL_MODE:
            control_mode_param = Parameter('control_mode', TYPE_STR, CONTROL_MODE_OPTIONS[0],
                                           TOOLTIP_CONTROL_MODE)
            control_mode_param.set_valid_options(CONTROL_MODE_OPTIONS)
            default_params.append(control_mode_param)
        resize_mode_param = Parameter('resize_mode', TYPE_STR, RESIZE_MODE_OPTIONS[1], TOOLTIP_RESIZE_MODE)
        resize_mode_param.set_valid_options(RESIZE_MODE_OPTIONS)
        default_params.append(resize_mode_param)
    return default_params


PREPROCESSOR_PRESET_LABELS = {
    'weight':  _tr('Control Weight'),
    'guidance_start': _tr('Starting Control Step'),
    'guidance_end': _tr('Ending Control Step'),
    'control_mode': _tr('Control Mode'),
    'resize_mode': _tr('Resize Mode'),
    'processor_res': _tr('Resolution')
}


def init_controlnet_unit(unit_dict: Optional[dict[str, Any]] = None) -> ControlNetUnitDict:
    """Initialize a ControlNet unit definition from dictionary data that may or may not be present or formatted
       correctly."""
    control_unit = default_controlnet_unit()
    if not isinstance(unit_dict, dict):
        return control_unit
    # I'm invoking all keys explicitly instead of iterating over key/type pairs because the typing module doesn't
    # check things properly when I parameterize TypedDict keys.
    if 'use_preview_as_input' in unit_dict and isinstance(unit_dict['use_preview_as_input'], bool):
        control_unit['use_preview_as_input'] = unit_dict['use_preview_as_input']
    if 'enabled' in unit_dict and isinstance(unit_dict['enabled'], bool):
        control_unit['enabled'] = bool(unit_dict['enabled'])
    if 'pixel_perfect' in unit_dict and isinstance(unit_dict['pixel_perfect'], bool):
        control_unit['pixel_perfect'] = unit_dict['pixel_perfect']
    if 'low_vram' in unit_dict and isinstance(unit_dict['low_vram'], bool):
        control_unit['low_vram'] = unit_dict['low_vram']
    if 'module' in unit_dict and isinstance(unit_dict['module'], str):
        control_unit['module'] = unit_dict['module']
    if 'model' in unit_dict and isinstance(unit_dict['model'], str):
        control_unit['model'] = unit_dict['model']
    if 'weight' in unit_dict and isinstance(unit_dict['weight'], (int, float)):
        control_unit['weight'] = float(unit_dict['weight'])
    if 'image' in unit_dict and isinstance(unit_dict['image'], str):
        control_unit['image'] = unit_dict['image']
    if 'resize_mode' in unit_dict and unit_dict['resize_mode'] in RESIZE_MODE_OPTIONS:
        control_unit['resize_mode'] = unit_dict['resize_mode']  # type: ignore
    if 'guidance_start' in unit_dict and isinstance(unit_dict['guidance_start'], float):
        control_unit['guidance_start'] = float(clamp(unit_dict['guidance_start'], 0.0, 1.0))
    if 'guidance_end' in unit_dict and isinstance(unit_dict['guidance_end'], float):
        control_unit['guidance_end'] = float(clamp(unit_dict['guidance_end'], 0.0, 1.0))
    if 'control_mode' in unit_dict and unit_dict['control_mode'] in CONTROL_MODE_OPTIONS:
        control_unit['control_mode'] = unit_dict['control_mode']  # type: ignore
    if 'processor_res' in unit_dict and isinstance(unit_dict['processor_res'], (int, float)):
        control_unit['processor_res'] = round(unit_dict['processor_res'])
    if 'threshold_a' in unit_dict and isinstance(unit_dict['threshold_a'], (int, float)):
        control_unit['threshold_a'] = float(unit_dict['threshold_a'])
    if 'threshold_b' in unit_dict and isinstance(unit_dict['threshold_b'], (int, float)):
        control_unit['threshold_b'] = float(unit_dict['threshold_b'])
    return control_unit


class ControlTypeResponse(TypedDict):
    """Response format for the /controlnet/control_types endpoint, containing one entry per available control type."""
    control_types: dict[str, ControlTypeDef]


# PREPROCESSOR PARAMETER PRESETS:
# -------------------------------
#  The WebUI API stores all ControlNet preprocessor parameters under the "processor_res", "threshold_a", "threshold_b",
# "control_mode", and "resize_mode" keys. The Automatic1111 WebUI API sends parameter definitions we can use to handle
# differences in how these parameters are used, but the Forge WebUI does not. Instead, follow these steps when
# creating Parameter objects for Forge preprocessors and displaying UI controls:
#
#  For all of these values except the varable threshold_a and threshold_b, parameter names are mapped to translated
# display names in PREPROCESSOR_PRESET_LABELS above. The threshold_* parameters will go untranslated for now.
#
# "processor_res":
#   If the preprocessor name is in the PREPROCESSOR_NO_RESOLUTION set below, omit this parameter. Otherwise, use the
#   PREPROCESSOR_RES_PARAM_NAME, PREPROCESSOR_RES_PARAM_KEY, PREPROCESSOR_RES_MIN, PREPROCESSOR_RES_MAX, and
#   PREPROCESSOR_RES_DEFAULT constants above to define this as a TYPE_INT Parameter. If the preprocessor name has an
#   entry in the PREPROCESSOR_RES_DEFAULTS dict below, that value should replace PREPROCESSOR_RES_DEFAULT.
#
# "control_mode":
#   If the preprocessor name is in the PREPROCESSOR_NO_CONTROL_MODE set below, omit this parameter. Otherwise, add it
#   as a TYPE_STR Parameter with valid options set to the CONTROL_MODE_OPTIONS string list defined above.
#
# "resize_mode":
#   This should be included in any preprocessor that uses "processor_res".  It should also be a TYPE_STR Parameter, with
#   valid options set to the RESIZE_MODE_OPTIONS string list defined above.
#
# "threshold_a", "threshold_b":
#   The name, default, and range values for these parameters are stored under the preprocessor name in the
#   THRESHOLD_A_PARAMETER_NAMES and THRESHOLD_B_PARAMETER_NAMES dicts below.  They're always either TYPE_INT or
#   TYPE_FLOAT, check the type of the 'min', 'max', 'default', or 'step' values to determine which one.  If the
#   preprocessor name isn't present in one of the THRESHOLD_*_PARAMETER_NAMES dicts, then the preprocessor doesn't use
#   that value.
#
#  When parameterizing values, make sure "threshold_a" always comes before "threshold_b", because the order is used to
#  determine which is which.
THRESHOLD_A_PARAMETER_NAMES: dict[str, ControlNetSliderDef] = {
    'reference_only': {
        'name': 'Style Fidelity',
        'min': 0.0,
        'max': 1.0,
        'default': 0.5,
        'step': 0.01
    },
    'canny': {
        'name': 'Low Threshold',
        'min': 0,
        'max': 256,
        'default': 100,
        'step': 1
    },
    'CLIP-G (Revision)': {
        'name': 'Noise Augmentation',
        'min': 0.0,
        'max': 1.0,
        'default': 0.0,
        'step': 0.01
    },
    'CLIP-G (Revision ignore prompt)': {
        'name': 'Noise Augmentation',
        'min': 0.0,
        'max': 1.0,
        'default': 0.0,
        'step': 0.01
    },
    'revision_clipvision': {
        'name': 'Noise Augmentation',
        'min': 0.0,
        'max': 1.0,
        'default': 0.0,
        'step': 0.01
    },
    'revision_ignore_prompt': {
        'name': 'Noise Augmentation',
        'min': 0.0,
        'max': 1.0,
        'default': 0.0,
        'step': 0.01
    },
    'tile_resample': {
        'name': 'Downsampling Rate',
        'min': 1.0,
        'max': 8.0,
        'default': 1.0,
        'step': 0.01
    },
    'tile_colorfix+sharp': {
        'name': 'Variation',
        'min': 3,
        'max': 32,
        'default': 8,
        'step': 1
    },
    'tile_colorfix': {
        'name': 'Variation',
        'min': 3,
        'max': 32,
        'default': 8,
        'step': 1
    },
    'reference_adain+attn': {
        'name': 'Style Fidelity',
        'min': 0.0,
        'max': 1.0,
        'default': 0.5,
        'step': 0.01
    },
    'reference_adain': {
        'name': 'Style Fidelity',
        'min': 0.0,
        'max': 1.0,
        'default': 0.5,
        'step': 0.01
    },
    'recolor_luminance': {
        'name': 'Gamma Correction',
        'min': 0.1,
        'max': 2.0,
        'default': 1.0,
        'step': 0.001
    },
    'recolor_intensity': {
        'name': 'Gamma Correction',
        'min': 0.1,
        'max': 2.0,
        'default': 1.0,
        'step': 0.001
    },
    'mlsd': {
        'name': 'MLSD Value Threshold',
        'min': 0.01,
        'max': 2.0,
        'default': 0.1,
        'step': 0.01
    },
    'threshold': {
        'name': 'Binarization Threshold',
        'min': 0.0,
        'max': 255.0,
        'default': 127.0,
        'step': 0.01
    },
    'softedge_teed': {
        'name': 'Safe Steps',
        'min': 0,
        'max': 10,
        'default': 2,
        'step': 1
    },
    'softedge_anyline': {
        'name': 'Safe Steps',
        'min': 0,
        'max': 10,
        'default': 2,
        'step': 1
    },
    'scribble_xdog': {
        'name': 'XDoG Threshold',
        'min': 1.0,
        'max': 64.0,
        'default': 32.0,
        'step': 0.01
    },
    'normal_midas': {
        'name': 'Normal Backgroud Threshold',
        'min': 0.0,
        'max': 1.0,
        'default': 0.4,
        'step': 0.01
    },
    'normal_dsine': {
        'name': 'Fov',
        'min': 0.0,
        'max': 360.0,
        'default': 60,
        'step': 0.1
    },
    'mediapipe_face': {
        'name': 'Max Faces',
        'min': 1,
        'max': 10,
        'default': 1,
        'step': 1
    },
    'depth_leres++': {
        'name': 'Remove Near %',
        'min': 0.0,
        'max': 100.0,
        'default': 0.0,
        'step': 0.1
    },
    'depth_leres': {
        'name': 'Remove Near %',
        'min': 0.0,
        'max': 100.0,
        'default': 0.0,
        'step': 0.1
    },
    'blur_gaussian': {
        'name': 'Sigma',
        'min': 0.01,
        'max': 64.0,
        'default': 9.0,
        'step': 0.01
    }
}

THRESHOLD_B_PARAMETER_NAMES: dict[str, ControlNetSliderDef] = {
    'canny': {
        'name': 'High Threshold',
        'min': 0,
        'max': 256,
        'default': 200,
        'step': 1
    },
    'tile_colorfix+sharp': {
        'name': 'Sharpness',
        'min': 0.0,
        'max': 2.0,
        'default': 1.0,
        'step': 0.01
    },
    'mlsd': {
        'name': 'MLSD Distance Threshold',
        'min': 0.01,
        'max': 20.0,
        'default': 0.1,
        'step': 0.01
    },
    'normal_dsine': {
        'name': 'Iterations',
        'min': 1,
        'max': 20,
        'default': 5,
        'step': 1
    },
    'mediapipe_face': {
        'name': 'Min Face Confidence',
        'min': 0.01,
        'max': 1.0,
        'default': 0.5,
        'step': 0.01
    },
    'depth_leres++': {
        'name': 'Remove Background %',
        'min': 0.0,
        'max': 100.0,
        'default': 0.0,
        'step': 0.1
    },
    'depth_leres': {
        'name': 'Remove Background %',
        'min': 0.0,
        'max': 100.0,
        'default': 0.0,
        'step': 0.1
    }
}

# Defines the set of preprocessors that have alternate default resolutions.
PREPROCESSOR_RES_DEFAULTS: dict[str, int] = {
    'depth_marigold': 768
}

# Defines the set of preprocessors that explicitly exclude resolution.
PREPROCESSOR_NO_RESOLUTION: set[str] = {
    'inpaint_only',
    'invert (from white bg & black line)',
    'shuffle',
    'ip-adapter_pulid',
    'inpaint_only+lama',
    'inpaint_global_harmonious',
    'facexlib'
}

# Defines the set of preprocessors that don't have the control_mode option.
PREPROCESSOR_NO_CONTROL_MODE: set[str] = {
    'ip-adapter-auto',
    'revision_clipvision',
    'ip-adapter_clip_h',
    't2ia_style_clipvision',
    'revision_ignore_prompt',
    'ip-adapter_face_id_plus',
    'ip-adapter_face_id',
    'ip-adapter_clip_sdxl_plus_vith',
    'ip-adapter_clip_g',

}

# Defines preprocessors that don't need a corresponding model.
PREPROCESSOR_MODEL_FREE: set[str] = {
    'revision_clipvision',
    'revision_ignore_prompt',
    'reference_only',
    'reference_adain+attn',
    'reference_adain'
}