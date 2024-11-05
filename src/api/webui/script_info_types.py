"""WebUI API custom script data definitions."""
from typing import TypedDict, Any, Optional


class ScriptRequestData(TypedDict):
    """Object format to use when invoking a script in a txt2img/img2img request body."""
    args: list[Any]


class ScriptResponseData(TypedDict):
    """Response containing available image generation scripts."""
    txt2img: list[str]
    img2img: list[str]


class ScriptParamDef(TypedDict):
    """Defines a parameter taken by a custom script."""
    label: str
    value: Any
    minimum: Optional[int | float]
    maximum: Optional[int | float]
    step: Optional[int | float]
    choices: Optional[list[Any]]


class ScriptInfo(TypedDict):
    """Defines the properties of a custom script."""
    name: str
    is_alwayson: bool
    is_img2img: bool
    args: list[ScriptParamDef]
