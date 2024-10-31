"""Types and constants associated with ControlNet.  All values are either not specific to a single API, or are reused
   because they don't have a useful equivalent in both APIs."""
from typing import TypedDict

from PySide6.QtWidgets import QApplication


PREPROCESSOR_NONE = 'none'
CONTROLNET_MODEL_NONE = 'None'

# When used as the controlnet image path, this signifies that the image should be taken from the image generation area.
# This is only meaninful within IntraPaint, and it must be replaced before sending any actual requests through the API.
CONTROLNET_REUSE_IMAGE_CODE = 'SELECTION'

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'api.controlnet_constants'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


CONTROLNET_TAB = _tr('ControlNet')
CONTROLNET_UNIT_TAB = _tr('ControlNet Unit {unit_number}')
TOOLTIP_CONTROLNET_WEIGHT = _tr('A multiplier that controls how strongly the ControlNet unit will affect image'
                                ' generation.')
TOOLTIP_START_STEP = _tr('The step in the image generation process where the ControlNet unit will be enabled, as a'
                         ' fraction of the total step count.')
TOOLTIP_END_STEP = _tr('The step in the image generation process where the ControlNet unit will be disabled, as a'
                       ' fraction of the total step count.')
TOOLTIP_RESIZE_MODE = _tr('Controls how preprocessor images are adjusted to fit the preprocessor resolution.')
TOOLTIP_CONTROL_MODE = _tr('Secondary control to set how ControlNet and prompt influence are weighted.')

# FORGE/COMFYUI CONTROLNET CONSTANTS:
# The Automatic1111 WebUI provides a useful endpoint for sorting preprocessors and ControlNet models into useful
# categories.  ComfyUI only provides some basic preprocessor categories, and the Forge WebUI doesn't even have that.
# To keep feature parity, these definitions will be used to categorize available preprocessors and models.

class ControlTypeDef(TypedDict):
    """Defines one of the ControlNet Type options returned by the /controlnet/control_types endpoint.

    TODO: I moved this here to resolve some circular import issues, but that's not an ideal fix. The best solution would
          be to completely decouple STATIC_CONTROL_TYPE_DEFS from the WebUI definitions and just handle the difference
          in ControlNetCategoryBuilder.
    """
    module_list: list[str]
    model_list: list[str]
    default_option: str
    default_model: str
class StaticControlTypeDef(ControlTypeDef):
    """Extended from the WebUI API definitions to include regex, hopefully catching any renamed or augmented models or
       preprocessors that should be in the list.  Also has the benefit of letting me avoid manually listing all the
       options that match the pattern."""

STATIC_CONTROL_TYPE_DEFS: dict[str, StaticControlTypeDef] = {
    'All': {
        'module_list': [PREPROCESSOR_NONE],
        'model_list': [CONTROLNET_MODEL_NONE],
        'default_option': PREPROCESSOR_NONE,
        'default_model': CONTROLNET_MODEL_NONE,
        'preprocessor_pattern': r'.*',
        'model_pattern': r'.*'
    },
    'Canny': {
        'module_list': [PREPROCESSOR_NONE, 'canny', 'invert (from white bg & black line)'],
        'model_list': [CONTROLNET_MODEL_NONE],
        'default_option': 'canny',
        'default_model': 'control_v11p_sd15_canny [d14c016b]',
        'preprocessor_pattern': r'(?i).canny',
        'model_pattern': r'(?i)canny',
    },
    'Depth': {
        'module_list': [PREPROCESSOR_NONE],
        'model_list': [CONTROLNET_MODEL_NONE],
        'default_option': 'depth_marigold',
        'default_model': 'control_v11f1p_sd15_depth [cfd03158]',
        'preprocessor_pattern': r'(?i)depth',
        'model_pattern': r'(?i)depth',
    },
    'IP-Adapter': {
        'module_list': [PREPROCESSOR_NONE],
        'model_list': [CONTROLNET_MODEL_NONE],
        'default_option': 'InsightFace+CLIP-H (IPAdapter)',
        'default_model': 'ip-adapter-plus-face_sd15 [71693645]',
        'preprocessor_pattern': r'(?i)IPAdapter',
        'model_pattern': r'(?i)ip-adapter',
    },
    'Inpaint': {
        'module_list': [PREPROCESSOR_NONE],
        'model_list': [CONTROLNET_MODEL_NONE],
        'default_option': 'inpaint_only+lama',
        'default_model': 'control_v11p_sd15_inpaint [ebff9138]',
        'preprocessor_pattern': r'(?i)inpaint',
        'model_pattern': r'(?i)inpaint',
    },
    'Instant-ID': {
        'module_list': [PREPROCESSOR_NONE, 'InsightFace (InstantID)'],
        'model_list': [CONTROLNET_MODEL_NONE, 'diffusion_pytorch_model.safetensors'],
        'default_option': 'InsightFace (InstantID)',
        'default_model': PREPROCESSOR_NONE,
        'preprocessor_pattern': r'(?i).*instant_id.*',
        'model_pattern': r'(?i).*instant_?id.*',
    },
    'InstructP2P': {
        'module_list': [PREPROCESSOR_NONE],
        'model_list': [CONTROLNET_MODEL_NONE, 'control_v11e_sd15_ip2p [c4bb465c]'],
        'default_option': PREPROCESSOR_NONE,
        'default_model': 'control_v11e_sd15_ip2p [c4bb465c]'
    },
    'NormalMap': {
        'module_list': [PREPROCESSOR_NONE, 'normalbae'],
        'model_list': [CONTROLNET_MODEL_NONE],
        'default_option': 'normalbae',
        'default_model': 'control_v11p_sd15_normalbae [316696f1]',
        'preprocessor_pattern': r'(?i)normal',
        'model_pattern': r'(?i)normal',
    },
    'Lineart': {
        'module_list': [PREPROCESSOR_NONE, 'lineart_standard (from white bg & black line)',
                        'invert (from white bg & black line)'],
        'model_list': [CONTROLNET_MODEL_NONE, 'control_v11p_sd15_lineart [43d4be0d]'],
        'default_option': 'lineart_standard (from white bg & black line)',
        'default_model': 'control_v11p_sd15_lineart [43d4be0d]',
        'preprocessor_pattern': r'(?i)line',
        'model_pattern': r'(?i).*lineart.*',
    },
    'MLSD': {
        'module_list': [PREPROCESSOR_NONE, 'mlsd', 'invert (from white bg & black line)'],
        'model_list': [CONTROLNET_MODEL_NONE, 'control_v11p_sd15_mlsd [aca30ff0]'],
        'default_option': 'mlsd',
        'default_model': 'control_v11p_sd15_mlsd [aca30ff0]',
        'preprocessor_pattern': r'(?i).*mlsd.*',
        'model_pattern': r'(?i).*mlsd.*',
    },
    'OpenPose': {
        'module_list': [PREPROCESSOR_NONE, 'openpose'],
        'model_list': [CONTROLNET_MODEL_NONE, 'control_v11p_sd15_openpose [cab727d4]'],
        'default_option': 'openpose_full',
        'default_model': 'ccontrol_v11p_sd15_openpose [cab727d4]',
        'preprocessor_pattern': r'(?i).*(?:openpose_densepose).*',
        'model_pattern': r'(?i).*openpose.*',
    },
    'PhotoMaker': {
        'module_list': [PREPROCESSOR_NONE, 'ClipVision (Photomaker)'],
        'model_list': [CONTROLNET_MODEL_NONE, 'photomaker-v1.bin'],
        'default_option': 'ClipVision (Photomaker)',
        'default_model': 'photomaker-v1.bin',
    },
    'Recolor': {
        'module_list': [PREPROCESSOR_NONE, 'recolor_luminance', 'recolor_intensity'],
        'model_list': [CONTROLNET_MODEL_NONE, 't2iadapter_color-fp16 [743b5c62]'],
        'default_option': 'recolor_luminance',
        'default_model': 't2iadapter_color-fp16 [743b5c62]',
        'preprocessor_pattern': r'(?i).*recolor.*',
        'model_pattern': r'(?i).*color.*',
    },
    # NOTE: Reference and revision are special cases, they use only a pre-processor and no model.
    'Reference': {
        'module_list': [PREPROCESSOR_NONE, 'reference_only', 'reference_adain+attn', 'reference_adain'],
        'model_list': [CONTROLNET_MODEL_NONE],
        'default_option': 'reference_only',
        'default_model': CONTROLNET_MODEL_NONE
    },
    'Revision': {
        'module_list': [PREPROCESSOR_NONE, 'CLIP-G (Revision)', 'CLIP-G (Revision ignore prompt)'],
        'model_list': [CONTROLNET_MODEL_NONE],
        'default_option': 'CLIP-G (Revision)',
        'default_model': CONTROLNET_MODEL_NONE
    },
    'Scribble': {
        'module_list': [PREPROCESSOR_NONE, 'invert (from white bg & black line)', 'scribble_pidinet'],
        'model_list': [CONTROLNET_MODEL_NONE],
        'default_option': 'scribble_pidinet',
        'default_model': 'control_v11p_sd15_scribble [d4ba51ff]',
        'preprocessor_pattern': r'(?i).*scribble.*',
        'model_pattern': r'(?i).*scribble.*',
    },
    'Segmentation': {
        'module_list': [PREPROCESSOR_NONE, 'seg_ofade20k', 'mobile_sam'],
        'model_list': ['control_v11p_sd15_seg [e1f51eb9]'],
        'default_option': 'seg_ofade20k',
        'default_model': 'control_v11p_sd15_seg [e1f51eb9]',
        'preprocessor_pattern': r'(?i).*seg_.*',
        'model_pattern': r'(?i).*_seg.*',
    },
    'Shuffle': {
        'module_list': [PREPROCESSOR_NONE, 'shuffle'],
        'model_list': ['control_v11e_sd15_shuffle [526bfdae]'],
        'default_option': 'shuffle',
        'default_model': 'control_v11e_sd15_shuffle [526bfdae]',
        'model_pattern': r'(?i).*shuffle.*',
    },
    'SoftEdge': {
        'module_list': [PREPROCESSOR_NONE, 'softedge_pidinet'],
        'model_list': ['control_v11e_sd15_shuffle [526bfdae]'],
        'default_option': 'softedge_pidinet',
        'default_model': 'control_v11p_sd15_softedge [a8575a2a]',
        'preprocessor_pattern': r'(?i).*softedge.*',
        'model_pattern': r'(?i).*softedge.*',
    },
    'T2I-Adapter': {
        'module_list': [PREPROCESSOR_NONE, 't2ia_style_clipvision'],
        'model_list': ['t2iadapter_canny-fp16 [f2e7f7cd]'],
        'default_option': 't2ia_style_clipvision',
        'default_model': 't2iadapter_canny-fp16 [f2e7f7cd]',
        'preprocessor_pattern': r'(?i).*t2ia_.*',
        'model_pattern': r'(?i).*t2iadapter.*',
    },
    'Tile': {
        'module_list': [PREPROCESSOR_NONE, 'tile_resample', 'tile_colorfix+sharp', 'tile_colorfix'],
        'model_list': [CONTROLNET_MODEL_NONE, 'control_v11f1e_sd15_tile [a371b31b]'],
        'default_option': 'tile_resample',
        'default_model': 'control_v11f1e_sd15_tile [a371b31b]',
        'preprocessor_pattern': r'(?i).*tile_.*',
        'model_pattern': r'(?i).*tile.*',
    },
}

#

# Defines preprocessor module uses of the 'threshold_a' parameter:
