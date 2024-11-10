"""Represents everything needed to define a ControlNet layer, including a preprocessor module and/or a ControlNet model
 (usually both, but not always), and all associated settings.  Values can be serialized and deserialized in both WebUI
 and ComfyUI formats."""
import json
from enum import Enum
from typing import TypedDict, cast

from PySide6.QtWidgets import QApplication

import src.api.webui.controlnet_webui_constants as webui_constants
from src.api.comfyui.nodes.controlnet.apply_controlnet_node import CONTROLNET_COMFTUI_CONTROL_WEIGHT_KEY, \
    CONTROLNET_COMFYUI_START_STEP_KEY, CONTROLNET_COMFYUI_END_STEP_KEY
from src.api.controlnet.control_parameter import ControlParameter
from src.api.controlnet.controlnet_constants import PREPROCESSOR_NONE, CONTROLNET_MODEL_NONE, \
    CONTROLNET_REUSE_IMAGE_CODE
from src.api.controlnet.controlnet_model import ControlNetModel
from src.api.controlnet.controlnet_preprocessor import ControlNetPreprocessor
from src.util.parameter import TYPE_FLOAT

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'api.controlnet.controlnet_unit'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


LABEL_TEXT_CONTROL_STRENGTH = _tr('Strength')
TOOLTIP_CONTROL_STRENGTH = _tr('Controls how powerful the ControlNet unit\'s influence is on image generation')

LABEL_TEXT_CONTROL_START = _tr('Starting control step')
TOOLTIP_CONTROL_START = _tr('Step where the ControlNet unit is first activated, as a fraction of the total step count.')

LABEL_TEXT_CONTROL_END = _tr('Ending control step')
TOOLTIP_CONTROL_END = _tr('Step where the ControlNet unit is deactivated, as a fraction of the total step count.')


class KeyType(Enum):
    """Sets the key format used for ControlNet model parameters (start, end, weight/strength)"""
    WEBUI = 0
    COMFYUI = 1


class ControlNetUnit:
    """Represents everything needed to define a ControlNet layer, including a preprocessor module and/or a ControlNet
       model (usually both, but not always), and all associated settings. Values can be serialized and deserialized in
       both WebUI and ComfyUI formats."""

    def __init__(self, key_type: KeyType) -> None:
        self._enabled = False
        self._image = CONTROLNET_REUSE_IMAGE_CODE
        self._pixel_perfect = True
        self._low_vram = False
        self._preprocessor = ControlNetPreprocessor(PREPROCESSOR_NONE, PREPROCESSOR_NONE, [])
        self._model = ControlNetModel(CONTROLNET_MODEL_NONE)
        self._control_strength = ControlParameter(
            webui_constants.CONTROL_WEIGHT_KEY if key_type == KeyType.WEBUI
            else CONTROLNET_COMFTUI_CONTROL_WEIGHT_KEY,
            LABEL_TEXT_CONTROL_STRENGTH,
            TYPE_FLOAT, 1.0, TOOLTIP_CONTROL_STRENGTH, 0.0,
            1.0, 0.01)
        self._control_start = ControlParameter(webui_constants.START_STEP_KEY if key_type == KeyType.WEBUI
                                               else CONTROLNET_COMFYUI_START_STEP_KEY, LABEL_TEXT_CONTROL_START,
                                               TYPE_FLOAT, 0.0, TOOLTIP_CONTROL_START, 0.0, 1.0,
                                               0.01)
        self._control_end = ControlParameter(webui_constants.END_STEP_KEY if key_type == KeyType.WEBUI
                                             else CONTROLNET_COMFYUI_END_STEP_KEY, LABEL_TEXT_CONTROL_END,
                                             TYPE_FLOAT, 1.0, TOOLTIP_CONTROL_END, 0.0, 1.0,
                                             0.01)
        self._key_type = key_type

    @property
    def enabled(self) -> bool:
        """Accesses whether this CntrolNetUnit is enabled and should be used."""
        return self._enabled

    @enabled.setter
    def enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    @property
    def image_string(self) -> str:
        """Accesses the control image string.  This should be either the empty string (for ControlNet with no image),
           the CONTROLNET_REUSE_IMAGE_CODE constant from src.api.controlnet.controlnet_constants (to use image
           generation area content), or the path to a valid image file."""
        return self._image

    @image_string.setter
    def image_string(self, image_string: str) -> None:
        self._image = image_string

    @property
    def preprocessor(self) -> ControlNetPreprocessor:
        """Directly accesses the preprocessor used to prepare image data for the ControlNet model."""
        return self._preprocessor

    @preprocessor.setter
    def preprocessor(self, preprocessor: ControlNetPreprocessor):
        self._preprocessor = preprocessor

    @property
    def model(self) -> ControlNetModel:
        """Accesses the model selected to adjust diffusion conditioning."""
        return self._model

    @model.setter
    def model(self, model: ControlNetModel) -> None:
        self._model = model

    @property
    def control_strength(self) -> ControlParameter:
        """Returns the control strength parameter object."""
        return self._control_strength

    @property
    def control_start(self) -> ControlParameter:
        """Returns the control starting step parameter object."""
        return self._control_start

    @property
    def control_end(self) -> ControlParameter:
        """Returns the control end step parameter object."""
        return self._control_end

    @property
    def pixel_perfect(self) -> bool:
        """Accesses the WebUI-specific "pixel perfect" option, which automatically ensures cropping and resizing is
           optimized for the selected preprocessor."""
        return self._pixel_perfect

    @pixel_perfect.setter
    def pixel_perfect(self, pixel_perfect: bool) -> None:
        self._pixel_perfect = pixel_perfect

    @property
    def low_vram(self) -> bool:
        """Accesses the WebUI-specific "low VRAM" option, which automatically swaps out ControlNet and Stable Diffusion
           models in VRAM to decrease memory use at the cost of increased generation time."""
        return self._low_vram

    @low_vram.setter
    def low_vram(self, low_vram: bool) -> None:
        self._low_vram = low_vram

    class _SerializedDataFormat(TypedDict):
        enabled: bool
        image: str
        model_name: str
        preprocessor_serialized: str
        control_strength: float
        control_start: float
        control_end: float
        key_type: int
        pixel_perfect: bool
        low_vram: bool

    def serialize(self) -> str:
        """Serialize all data to text."""
        data_dict: ControlNetUnit._SerializedDataFormat = {
            'enabled': self._enabled,
            'image': self._image,
            'model_name': self._model.full_model_name,
            'preprocessor_serialized': self._preprocessor.serialize(),
            'control_strength': cast(float, self._control_strength.value),
            'control_start': cast(float, self.control_start.value),
            'control_end': cast(float, self.control_end.value),
            'key_type': self._key_type.value,
            'pixel_perfect': self._pixel_perfect,
            'low_vram': self._low_vram
        }
        return json.dumps(data_dict)

    @staticmethod
    def deserialize(data_str: str) -> 'ControlNetUnit':
        """Loads a ControlNetUnit from serialized data."""
        data_dict = cast(ControlNetUnit._SerializedDataFormat, json.loads(data_str))
        key_type = KeyType(data_dict['key_type'])
        control_unit = ControlNetUnit(key_type)
        control_unit.enabled = data_dict['enabled']
        control_unit.image_string = data_dict['image']
        control_unit.model = ControlNetModel(data_dict['model_name'])
        control_unit.preprocessor = ControlNetPreprocessor.deserialize(data_dict['preprocessor_serialized'])
        control_unit.control_strength.value = data_dict['control_strength']
        control_unit.control_start.value = data_dict['control_start']
        control_unit.control_end.value = data_dict['control_end']
        control_unit.pixel_perfect = data_dict['pixel_perfect']
        control_unit.low_vram = data_dict['low_vram']
        return control_unit
