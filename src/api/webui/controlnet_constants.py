"""WebUI API types and constants associated with ControlNet."""
from typing import TypedDict, List, Optional, Literal, Dict, TypeAlias, NotRequired


class ControlNetModelRes(TypedDict):
    """Response format when loading ControlNet model options."""
    model_list: List[str]


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
    sliders: List[ControlNetSliderDef]


class ControlNetModuleRes(TypedDict):
    """Response format when loading ControlNet preprocessor options."""
    module_list: List[str]
    module_details: NotRequired[Dict[str, ModuleDetail]]  # NOTE: not included in Forge.


class ControlNetModuleResFull(TypedDict):
    """Extended response."""
    module_list: List[str]


class ControlNetScriptValue(TypedDict):
    """Data format used with the ControlNet script's values within the alwayson_scripts section in WebUI generation
       requests. In the script values section, The ControlNet value parameter is a list holding up to three of these
       objects.  Optional parameters that only affect the UI are omitted."""
    use_preview_as_input: bool
    enabled: bool
    module: str  # AKA preprocessor
    model: str
    weight: float
    image: Optional[str]  # base64 image, usually necessary.
    resize_mode: Literal['Just Resize', 'Crop and Resize', 'Resize and Fill']
    guidance_start: float
    guidance_end: float
    control_mode: Literal['Balanced', 'My prompt is more important', 'ControlNet is more important']

    # preprocessor-specific values:
    processor_res: int  # Some use this, some don't. Set to -1 if its not used.
    # Effects of of threshold values (if any) vary based on preprocessor.
    threshold_a: float
    threshold_b: float


class ControlTypeDef(TypedDict):
    """Defines one of the ControlNet Type options returned by the /controlnet/control_types endpoint."""
    module_list: List[str]
    model_list: List[str]
    default_option: str
    default_model: str


# Response format for the /controlnet/control_types endpoint, containing one entry per available control type.
ControlTypeRes: TypeAlias = Dict[str, ControlTypeDef]


# FORGE CONTROLNET CONSTANTS:
# WebUI Forge has a significantly worse ControlNet API that does not provide preprocessor parameters or control type
# options.  To keep feature parity between Forge and A1111, those values are hard-coded here.


class StaticControlTypeDef(ControlTypeDef):
    """Extended from the API definitions to include regex, hopefully catching any renamed or augmented models or
       preprocessors that should be in the list.  Also has the benefit of letting me avoid manually listing all the
       options that match the pattern."""
    preprocessor_pattern: NotRequired[str]
    model_pattern: NotRequired[str]


CONTROL_TYPE_DEFS: Dict[str, StaticControlTypeDef] = {
    'All': {
        'module_list': ['none'],
        'model_list': ['None'],
        'default_option': 'none',
        'default_model': 'None',
        'preprocessor_pattern': r'.*',
        'model_pattern': r'.*'
    },
    'Canny': {
        'module_list': ['none', 'canny', 'invert (from white bg & black line)'],
        'model_list': ['None'],
        'default_option': 'canny',
        'default_model': 'control_v11p_sd15_canny [d14c016b]',
        'model_pattern': r'(?i).*canny.*',
    },
    'Depth': {
        'module_list': ['none'],
        'model_list': ['None'],
        'default_option': 'depth_marigold',
        'default_model': 'control_v11f1p_sd15_depth [cfd03158]',
        'preprocessor_pattern': r'(?i).*depth.*',
        'model_pattern': r'(?i).*depth.*',
    },
    'IP-Adapter': {
        'module_list': ['none'],
        'model_list': ['None'],
        'default_option': 'InsightFace+CLIP-H (IPAdapter)',
        'default_model': 'ip-adapter-plus-face_sd15 [71693645]',
        'preprocessor_pattern': r'(?i).*IPAdapter.*',
        'model_pattern': r'(?i).*ip-adapter.*',
    },
    'Inpaint': {
        'module_list': ['none'],
        'model_list': ['None'],
        'default_option': 'inpaint_only+lama',
        'default_model': 'control_v11p_sd15_inpaint [ebff9138]',
        'preprocessor_pattern': r'(?i).*inpaint.*',
        'model_pattern': r'(?i).*inpaint.*',
    },
    'Instant-ID': {
        'module_list': ['none', 'InsightFace (InstantID)'],
        'model_list': ['None', 'diffusion_pytorch_model.safetensors'],
        'default_option': 'InsightFace (InstantID)',
        'default_model': 'none',
        'preprocessor_pattern': r'(?i).*instant_id.*',
        'model_pattern': r'(?i).*instant_?id.*',
    },
    'InstructP2P': {
        'module_list': ['none'],
        'model_list': ['None', 'control_v11e_sd15_ip2p [c4bb465c]'],
        'default_option': 'none',
        'default_model': 'control_v11e_sd15_ip2p [c4bb465c]'
    },
    'NormalMap': {
        'module_list': ['none', 'normalbae'],
        'model_list': ['None'],
        'default_option': 'normalbae',
        'default_model': 'control_v11p_sd15_normalbae [316696f1]',
        'model_pattern': r'(?i).*normal.*',
    },
    'Lineart': {
        'module_list': ['none', 'lineart_standard (from white bg & black line)', 'invert (from white bg & black line)'],
        'model_list': ['None', 'control_v11p_sd15_lineart [43d4be0d]'],
        'default_option': 'lineart_standard (from white bg & black line)',
        'default_model': 'control_v11p_sd15_lineart [43d4be0d]',
        'preprocessor_pattern': r'(?i).*lineart.*',
        'model_pattern': r'(?i).*lineart.*',
    },
    'MLSD': {
        'module_list': ['none', 'mlsd', 'invert (from white bg & black line)'],
        'model_list': ['None', 'control_v11p_sd15_mlsd [aca30ff0]'],
        'default_option': 'mlsd',
        'default_model': 'control_v11p_sd15_mlsd [aca30ff0]',
        'preprocessor_pattern': r'(?i).*mlsd.*',
        'model_pattern': r'(?i).*mlsd.*',
    },
    'OpenPose': {
        'module_list': ['none', 'openpose'],
        'model_list': ['None', 'control_v11p_sd15_openpose [cab727d4]'],
        'default_option': 'openpose_full',
        'default_model': 'ccontrol_v11p_sd15_openpose [cab727d4]',
        'preprocessor_pattern': r'(?i).*(?:openpose_densepose).*',
        'model_pattern': r'(?i).*openpose.*',
    },
    'PhotoMaker': {
        'module_list': ['none', 'ClipVision (Photomaker)'],
        'model_list': ['None', 'photomaker-v1.bin'],
        'default_option': 'ClipVision (Photomaker)',
        'default_model': 'photomaker-v1.bin',
    },
    'Recolor': {
        'module_list': ['none', 'recolor_luminance', 'recolor_intensity'],
        'model_list': ['None', 't2iadapter_color-fp16 [743b5c62]'],
        'default_option': 'recolor_luminance',
        'default_model': 't2iadapter_color-fp16 [743b5c62]',
        'preprocessor_pattern': r'(?i).*recolor.*',
        'model_pattern': r'(?i).*color.*',
    },
    # NOTE: Reference and revision are special cases, they use only a pre-processor and no model.
    'Reference': {
        'module_list': ['none', 'reference_only', 'reference_adain+attn', 'reference_adain'],
        'model_list': ['None'],
        'default_option': 'reference_only',
        'default_model': 'None'
    },
    'Revision': {
        'module_list': ['none', 'CLIP-G (Revision)', 'CLIP-G (Revision ignore prompt)'],
        'model_list': ['None'],
        'default_option': 'CLIP-G (Revision)',
        'default_model': 'None'
    },
    'Scribble': {
        'module_list': ['none', 'invert (from white bg & black line)', 'scribble_pidinet'],
        'model_list': ['None'],
        'default_option': 'scribble_pidinet',
        'default_model': 'control_v11p_sd15_scribble [d4ba51ff]',
        'preprocessor_pattern': r'(?i).*scribble.*',
        'model_pattern': r'(?i).*scribble.*',
    },
    'Segmentation': {
        'module_list': ['none', 'seg_ofade20k', 'mobile_sam'],
        'model_list': ['control_v11p_sd15_seg [e1f51eb9]'],
        'default_option': 'seg_ofade20k',
        'default_model': 'control_v11p_sd15_seg [e1f51eb9]',
        'preprocessor_pattern': r'(?i).*seg_.*',
        'model_pattern': r'(?i).*_seg.*',
    },
    'Shuffle': {
        'module_list': ['none', 'shuffle'],
        'model_list': ['control_v11e_sd15_shuffle [526bfdae]'],
        'default_option': 'shuffle',
        'default_model': 'control_v11e_sd15_shuffle [526bfdae]',
        'model_pattern': r'(?i).*shuffle.*',
    },
    'SoftEdge': {
        'module_list': ['none', 'softedge_pidinet'],
        'model_list': ['control_v11e_sd15_shuffle [526bfdae]'],
        'default_option': 'softedge_pidinet',
        'default_model': 'control_v11p_sd15_softedge [a8575a2a]',
        'preprocessor_pattern': r'(?i).*softedge.*',
        'model_pattern': r'(?i).*softedge.*',
    },
    'T2I-Adapter': {
        'module_list': ['none', 't2ia_style_clipvision'],
        'model_list': ['t2iadapter_canny-fp16 [f2e7f7cd]'],
        'default_option': 't2ia_style_clipvision',
        'default_model': 't2iadapter_canny-fp16 [f2e7f7cd]',
        'preprocessor_pattern': r'(?i).*t2ia_.*',
        'model_pattern': r'(?i).*t2iadapter.*',
    },
    'Tile': {
        'module_list': ['none', 'tile_resample', 'tile_colorfix+sharp', 'tile_colorfix'],
        'model_list': ['None', 'control_v11f1e_sd15_tile [a371b31b]'],
        'default_option': 'tile_resample',
        'default_model': 'control_v11f1e_sd15_tile [a371b31b]',
        'preprocessor_pattern': r'(?i).*tile_.*',
        'model_pattern': r'(?i).*tile.*',
    },
}


# Defines preprocessor module uses of the 'threshold_a' parameter:
THRESHOLD_A_PARAMETER_NAMES: Dict[str, ControlNetSliderDef] = {
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

# Defines preprocessor module uses of the 'threshold_a' parameter:
THRESHOLD_B_PARAMETER_NAMES: Dict[str, ControlNetSliderDef] = {
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

PREPROCESSOR_RES_MIN = 128
PREPROCESSOR_RES_MAX = 2048
PREPROCESSOR_RES_DEFAULT = 512
PREPROCESSOR_RES_STEP = 8

# Defines the set of preprocessors that have alternate default resolutions.
PREPROCESSOR_RES_DEFAULTS: Dict[str, int] = {
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


## Defines preprocessors that don't need a corresponding model.
PREPROCESSOR_MODEL_FREE: set[str] = {
    'revision_clipvision',
    'revision_ignore_prompt',
    'reference_only',
    'reference_adain+attn',
    'reference_adain'
}