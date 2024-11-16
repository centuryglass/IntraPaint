"""Defines a ControlNet preprocessor's name and parameters, for use with a Stable Diffusion API"""
import json
from copy import deepcopy
from typing import Optional, cast, Any, TypedDict

from src.api.controlnet.control_parameter import ControlParameter, ControlParamType
from src.api.webui.controlnet_webui_constants import ControlNetSliderDef
from src.util.parameter import TYPE_INT, TYPE_FLOAT


class ControlNetPreprocessor:
    """Defines a ControlNet preprocessor's name and parameters, for use with a Stable Diffusion API."""

    def __init__(self, name: str, display_name: str, parameters: list[ControlParameter]) -> None:
        """Parameter objects are used similarly to the way they're used in src.image.filter, except that the name value
           holds a key string, and description is the display name."""
        self._name = name
        self._display_name = display_name
        self._description = ''
        self._parameters = parameters
        self._category_name = ''
        self._has_image_input = True
        self._has_mask_input = True
        self._model_free = False

    @property
    def category_name(self) -> str:
        """Access the category name: an extra string that's used for categorizing preprocessor types, provided in
           ComfyUI only."""
        return self._category_name

    @category_name.setter
    def category_name(self, category: str) -> None:
        self._category_name = category

    @property
    def description(self) -> str:
        """Access description text, which is empty by default."""
        return self._description

    @description.setter
    def description(self, description: str) -> None:
        self._description = description

    @property
    def has_image_input(self) -> bool:
        """Accesses whether this preprocessor accepts an image input when converted into a ComfyUI node."""
        return self._has_image_input

    @has_image_input.setter
    def has_image_input(self, image_input: bool) -> None:
        self._has_image_input = image_input

    @property
    def has_mask_input(self) -> bool:
        """Accesses whether this preprocessor accepts a mask input when converted into a ComfyUI node."""
        return self._has_mask_input

    @has_mask_input.setter
    def has_mask_input(self, mask_input: bool) -> None:
        self._has_mask_input = mask_input

    @property
    def model_free(self) -> bool:
        """Accesses whether this preprocessor can be used without a ControlNet model."""
        return self._model_free

    @model_free.setter
    def model_free(self, model_free: bool) -> None:
        self._model_free = model_free

    def __deepcopy__(self, memo: dict[int, Any]) -> 'ControlNetPreprocessor':
        self_copy = ControlNetPreprocessor(self._name, self._display_name, deepcopy(self._parameters, memo))
        self_copy.category_name = self.category_name
        self_copy.description = self.description
        self_copy.has_image_input = self.has_image_input
        self_copy.has_mask_input = self.has_mask_input
        self_copy.model_free = self._model_free
        memo[id(self)] = self_copy
        return self_copy

    def __eq__(self, other: Any) -> bool:
        if (not isinstance(other, ControlNetPreprocessor) or self._name != other.name
                or self.parameter_keys != other.parameter_keys or self._has_image_input != other.has_image_input
                or self._has_mask_input != other.has_mask_input or self.description != other.description
                or self.category_name != other.category_name
                or self.model_free != other.model_free):
            return False
        return self.parameters == other.parameters

    class _SerializedDataFormat(TypedDict):
        name: str
        category_name: Optional[str]
        display_name: str
        description: str
        has_image: bool
        has_mask: bool
        model_free: bool
        parameters_serialized: list[str]

    def serialize(self) -> str:
        """Serialize all preprocessor data as a JSON string."""
        data_dict: ControlNetPreprocessor._SerializedDataFormat = {
            'name': self._name,
            'category_name': self._category_name,
            'display_name': self._display_name,
            'description': self._description,
            'has_image': self._has_image_input,
            'has_mask': self._has_mask_input,
            'model_free': self._model_free,
            'parameters_serialized': [param.serialize() for param in self._parameters]
        }
        return json.dumps(data_dict)

    @staticmethod
    def deserialize(data_str: str) -> 'ControlNetPreprocessor':
        """Parse a ControlNetPreprocessor from serialized JSON data."""
        data_dict = cast(ControlNetPreprocessor._SerializedDataFormat, json.loads(data_str))
        parameters = [ControlParameter.deserialize(param_str) for param_str in data_dict['parameters_serialized']]
        preprocessor = ControlNetPreprocessor(data_dict['name'], data_dict['display_name'], parameters)
        if data_dict['category_name'] is not None:
            preprocessor.category_name = data_dict['category_name']
        preprocessor.has_image_input = data_dict['has_image']
        preprocessor.has_mask_input = data_dict['has_mask']
        preprocessor.model_free = data_dict['model_free']
        preprocessor.description = data_dict['description']
        return preprocessor

    @property
    def name(self) -> str:
        """Returns the preprocessor name"""
        return self._name

    @property
    def parameters(self) -> list[ControlParameter]:
        """Returns the parameter list."""
        return [*self._parameters]

    @property
    def parameter_keys(self) -> list[str]:
        """Returns the list of parameter key strings"""
        return [param.key for param in self._parameters]

    def get_value(self, param_key: str) -> ControlParamType:
        """Gets the value of a parameter, looking it up using its name key."""
        for param in self._parameters:
            if param_key == param.key:
                return param.value
        raise KeyError(f'Parameter "{param_key}" not found in "{self._name}" preprocessor')

    def set_value(self, param_key: str, value: ControlParamType) -> None:
        """Sets the value of a parameter, validating it first.  This will also convert between int and float if
           needed."""
        for param in self._parameters:
            if param_key == param.key:
                param.value = value
                return
        raise KeyError(f'Parameter "{param_key}" not found in "{self._name}" preprocessor')

    @staticmethod
    def _parameter_from_slider_def(slider_def: ControlNetSliderDef, param_key: str) -> ControlParameter:
        param_name = slider_def['name']
        min_val = slider_def['min']
        max_val = slider_def['max']
        default_val = slider_def['default']
        step_val = slider_def['step']
        if any((num % 1) != 0.0 for num in (min_val, max_val, default_val, step_val)):
            parameter_type = TYPE_FLOAT
            min_val = float(min_val)
            max_val = float(max_val)
            default_val = float(default_val)
            step_val = float(step_val)
        else:
            parameter_type = TYPE_INT
            min_val = round(min_val)
            max_val = round(max_val)
            default_val = round(default_val)
            step_val = round(step_val)
        return ControlParameter(param_key, param_name, parameter_type, default_val, '', min_val, max_val,
                                step_val)
