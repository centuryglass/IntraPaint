"""Options for resizing image layers when scaling the image canvas."""
from enum import Enum

from PySide6.QtWidgets import QApplication

RESIZE_OPTION_ALL = QApplication.translate('config.cache', 'Expand all unlocked layers')
RESIZE_OPTION_FULL_IMAGE = QApplication.translate('config.cache', 'Only expand full-image layers')
RESIZE_OPTION_NONE = QApplication.translate('config.cache', 'Do not expand layers')


class LayerResizeMode(Enum):
    """Options for resizing image layers."""
    RESIZE_ALL = 0
    FULL_IMAGE_LAYERS_ONLY = 1
    RESIZE_NONE = 2

    @classmethod
    def get_from_text(cls, text: str) -> 'LayerResizeMode':
        """Gets the appropriate mode from display text, or raises ValueError if no match is found."""
        if text == RESIZE_OPTION_ALL:
            return LayerResizeMode.RESIZE_ALL
        if text == RESIZE_OPTION_FULL_IMAGE:
            return LayerResizeMode.FULL_IMAGE_LAYERS_ONLY
        if text == RESIZE_OPTION_NONE:
            return LayerResizeMode.RESIZE_NONE
        raise ValueError(f'Unexpected text {text} matches no known resize mode.')
