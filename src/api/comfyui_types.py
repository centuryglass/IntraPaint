"""Typedefs for ComfyUI API data."""
from typing import TypeAlias, Literal, TypedDict, Optional, List, Tuple, NotRequired, Dict

# Misc. types used within multiple request/response objects:
FileType: TypeAlias = Literal['input', 'temp', 'output']

# I/O parameter definitions:
ComplexTypes: TypeAlias = Literal[
    'CLIP',
    'CONDITIONING',
    'IMAGE',
]

ComplexInputType: TypeAlias = Literal[
                                  'CLIP',
                                  'CLIP_VISION',
                                  'CLIP_VISION_OUTPUT',
                                  'CONDITIONING',
                                  'CONTROL_NET',
                                  'GLIGEN',
                                  'LATENT',
                                  'MASK',
                                  'MODEL',
                                  'STYLE_MODEL',
                                  'VAE'
                              ] | ComplexTypes

NodeReturnType: TypeAlias = Literal[
                                'AUDIO',
                                'LATENT',
                                'LATENT_OPERATION',
                            ] | ComplexTypes

DisplayType: TypeAlias = Literal['color', 'number', 'slider']


class ParamDef(TypedDict):
    """Input value parameters accepted across all tyeps."""
    tooltip: NotRequired[str]


class IntParamDef(ParamDef):
    """Defines int parameter ranges, step size, and default value."""
    default: int
    min: int
    max: int
    step: int
    display: NotRequired[DisplayType]


class FloatParamDef(ParamDef):
    """Defines float parameter ranges, step size, and default value."""
    default: float
    min: float
    max: float
    step: float
    round: NotRequired[float]


class StrParamDef(ParamDef):
    """Defines string parameter requirements."""
    default: NotRequired[str]
    multiline: bool
    dynamicPrompts: bool


class BoolParamDef(ParamDef):
    """Defines a default boolean parameter value."""
    default: bool


IntParam: TypeAlias = Tuple[Literal['INT'], IntParamDef]
BoolParam: TypeAlias = Tuple[Literal['BOOLEAN'], BoolParamDef]
FloatParam: TypeAlias = Tuple[Literal['FLOAT'], FloatParamDef]
StrOptionParam: TypeAlias = Tuple[List[str]] | Tuple[List[str], ParamDef]
CustomTypedParam: TypeAlias = Tuple[ComplexInputType] | Tuple[ComplexInputType, ParamDef]
InputParam: TypeAlias = IntParam | FloatParam | BoolParam | StrOptionParam \
                        | CustomTypedParam


class InputTypeDef(TypedDict):
    """Defines inputs for a ComfyUI node."""
    required: Dict[str, InputParam]
    optional: NotRequired[Dict[str, InputParam]]


# API request/parameter/response types, by endpoint:

IMAGE_UPLOAD_FILE_NAME = 'image'


class ImageUploadParams(TypedDict):
    """Image upload body."""
    type: NotRequired[FileType]
    subfolder: NotRequired[str]
    overwrite: NotRequired[str]  # 'true' or '1' to overwrite


class ImageUploadResponse(TypedDict):
    """Image upload response body."""
    name: str
    subfolder: str
    type: FileType


class MaskRefObject(TypedDict):
    """Reference object used to specify which image is affected by a mask:"""
    filename: str
    subfolder: str
    type: NotRequired[FileType]  # used when output_dir from filename is None, default = 'output'


class MaskUploadParams(ImageUploadParams):
    """Mask upload body key constants."""
    original_ref: str  # when parsed as JSON, should be ComfyMaskRefObject


class ViewUrlParams(TypedDict):
    """URL parameters used with the VIEW_IMAGE endpoint."""
    filename: Optional[str]
    type: Optional[FileType]  # default = 'output'
    subfolder: Optional[str]
    channel: Optional[Literal['rgb', 'rgba']]  # default = 'rgba'
    preview: Optional[str]  # should be '{format};{quality}',  default = 'webp;90', format can also be 'jpeg'


class SystemObject(TypedDict):
    """System data object used in SYSTEM_STATS responses."""
    os: str
    ram_total: int
    ram_free: int
    comfyui_version: str
    python_version: str
    pytorch_version: str
    embedded_python: bool
    argv: List[str]


class DeviceObject(TypedDict):
    """Torch device object used in SYSTEM_STATS responses."""
    name: str
    type: str
    index: int
    vram_total: int
    vram_free: int
    torch_vram_total: int
    torch_vram_free: int


class SystemStatResponse(TypedDict):
    """Response body format for the SYSTEM_STATS endpoint."""
    system: SystemObject
    devices: List[DeviceObject]


class NodeInfoResponse(TypedDict):
    """Response defining a ComfyUI node."""
    input: InputTypeDef
    input_order: Dict[Literal['required', 'optional'], List[str]]
    output: Tuple[NodeReturnType]
    output_is_list: List[bool]  # length should match output
    output_name: List[str]  # Length should match output
    name: str
    display_name: str
    description: str
    python_module: str
    category: str
    output_node: bool
    deprecated: NotRequired[bool]
    experimental: NotRequired[bool]
