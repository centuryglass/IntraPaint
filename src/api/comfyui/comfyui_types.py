"""Typedefs for ComfyUI API data."""
from typing import TypeAlias, Literal, TypedDict, Optional, NotRequired, Any

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

CONTROLNET_PREPROCESSOR_CATEGORY = 'ControlNet Preprocessors'
CONTROLNET_PREPROCESSOR_OUTPUT_NAME = ['IMAGE']
CONTROLNET_PREPROCESSOR_REQUIRED_INPUT = 'image'


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


IntParam: TypeAlias = tuple[Literal['INT'], IntParamDef]
BoolParam: TypeAlias = tuple[Literal['BOOLEAN'], BoolParamDef]
FloatParam: TypeAlias = tuple[Literal['FLOAT'], FloatParamDef]
StrOptionParam: TypeAlias = tuple[list[str]] | tuple[list[str], ParamDef]
CustomTypedParam: TypeAlias = tuple[ComplexInputType] | tuple[ComplexInputType, ParamDef]
InputParam: TypeAlias = IntParam | FloatParam | BoolParam | StrOptionParam \
                        | CustomTypedParam


class InputTypeDef(TypedDict):
    """Defines inputs for a ComfyUI node."""
    required: dict[str, InputParam]
    optional: NotRequired[dict[str, InputParam]]


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


class ImageFileReference(TypedDict):
    """References an uploaded or generated image file."""
    filename: str
    subfolder: str
    type: NotRequired[FileType]  # used when output_dir from filename is None, default = 'output'


class MaskUploadParams(ImageUploadParams):
    """Mask upload body key constants."""
    original_ref: str  # when parsed as JSON, should be ImageFileReference


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
    argv: list[str]


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
    devices: list[DeviceObject]


class NodeInfoResponse(TypedDict):
    """Response defining a ComfyUI node."""
    input: InputTypeDef
    input_order: dict[Literal['required', 'optional'], list[str]]
    output: tuple[NodeReturnType]
    output_is_list: list[bool]  # length should match output
    output_name: list[str]  # Length should match output
    name: str
    display_name: str
    description: str
    python_module: str
    category: str
    output_node: bool
    deprecated: NotRequired[bool]
    experimental: NotRequired[bool]


# QUEUED PROMPT/TASK DATA:

# Entry structure: (task_number, UUID, workflow, optional_extra_data)
QueueEntry: TypeAlias = tuple[int, str, dict[str, dict[str, Any]]] \
                        | tuple[int, str, dict[str, dict[str, Any]], dict[str, Any]]

ACTIVE_QUEUE_KEY = 'queue_running'
PENDING_QUEUE_KEY = 'queue_pending'


class QueueInfoResponse(TypedDict):
    """Response structure used when getting queued task info."""
    queue_running: list[QueueEntry]
    queue_pending: list[QueueEntry]


class QueueAdditionRequest(TypedDict):
    """Body structure to use when adding to the ComfyUI queue."""
    prompt: dict[str, Any]
    number: NotRequired[int]  # Sets priority
    front: NotRequired[bool]  # Pushes this job ahead of others
    client_id: NotRequired[str]  # Optional extra identifier
    extra_data: NotRequired[dict[str, Any]]  # Associate some extra


class ErrorEntry(TypedDict):
    """A single queue error."""
    type: str
    message: str
    details: str
    extra_info: dict[str, str]


class NodeErrorEntry(TypedDict):
    """Defines error data for a single node."""
    errors: list[ErrorEntry]
    dependent_outputs: list[str]  # connected node ids
    class_type: str


class QueueAdditionResponse(TypedDict):
    """Response structure used when a new job is queued."""
    prompt_id: NotRequired[str]  # UUID, omitted on error
    number: NotRequired[int]  # Queue number/priority, omitted on error
    error: NotRequired[str | ErrorEntry]
    node_errors: list[NodeErrorEntry]

    # IntraPaint extensions:
    # These properties won't ever be set by ComfyUI, they're additions that IntraPaint uses to simplify passing data
    # back from ComfyUIWebservice.
    uploaded_images: NotRequired[dict[str, ImageFileReference]]  # Uploaded image references, to reuse across batches.
    uploaded_mask: NotRequired[ImageFileReference]  # Uploaded mask reference, to reuse across batches.
    seed: NotRequired[int]  # Not added by the API, used for tracking last seed values and handling sequential batches.


class QueueDeletionRequest(TypedDict):
    """Request structure used to delete queue items."""
    clear: NotRequired[bool]  # If true, the whole queue is wiped.
    delete: NotRequired[list[str]]  # Set specific queued items to delete.


class PromptStatusMessageData(TypedDict):
    """Extra data bundled with queued task messages."""
    prompt_id: str  # UUID
    timestamp: int
    nodes: NotRequired[list[str]]


PromptStatusMessage: TypeAlias = tuple[str, PromptStatusMessageData]


class PromptExecStatus(TypedDict):
    """Status data associated with a task in the history, directly from ComfyUI/execution.py."""
    status_str: Literal['success', 'error']
    completed: bool
    messages: list[PromptStatusMessage]


class PromptExecOutputs(TypedDict):
    """Returns generated file info for a completed task."""
    images: list[ImageFileReference]
    # TODO: track down format for other possible output types


class PromptHistory(TypedDict):
    """Prompt execution data from the /history endpoint."""
    prompt: QueueEntry
    outputs: dict[str, dict[str, PromptExecOutputs]]  # keys are output node ids
    status: PromptExecStatus


QueueHistoryResponse: TypeAlias = dict[str, PromptHistory]  # key is prompt_id
