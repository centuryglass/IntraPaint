"""WebUI API custom script data definitions."""
from typing import TypedDict, List, Any, Optional


class ScriptRes(TypedDict):
    """Response containing available image generation scripts."""
    txt2img: List[str]
    img2img: List[str]


class ScriptParamDef(TypedDict):
    """Defines a parameter taken by a custom script."""
    label: str
    value: Any
    minimum: Optional[int | float]
    maximum: Optional[int | float]
    step: Optional[int | float]
    choices: Optional[List[Any]]


class ScriptInfo(TypedDict):
    """Defines the properties of a custom script."""
    name: str
    is_alwayson: bool
    is_img2img: bool
    args: List[ScriptParamDef]

