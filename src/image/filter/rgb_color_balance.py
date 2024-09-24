"""Adjust RGB color levels."""
from typing import Callable, List

import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage

from src.config.key_config import KeyConfig
from src.image.filter.filter import ImageFilter
from src.image.layers.image_stack import ImageStack
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.image_utils import image_data_as_numpy_8bit, create_transparent_image
from src.util.parameter import Parameter, TYPE_FLOAT

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'image.filter.rgb_color_balance'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


COLOR_BALANCE_TITLE = _tr('RGBA Color Balance')
COLOR_BALANCE_DESCRIPTION = _tr('Adjust color balance')

RED_LABEL = _tr('Red')
GREEN_LABEL = _tr('Green')
BLUE_LABEL = _tr('Blue')
ALPHA_LABEL = _tr('Alpha')
MAX_VALUE = 8.0
RGBA_ICON_PATH = f'{PROJECT_DIR}/resources/icons/filter/rgba_icon.svg'


class RGBColorBalanceFilter(ImageFilter):
    """Filter used to adjust  RGB color levels."""

    def __init__(self, image_stack: ImageStack) -> None:
        super().__init__(image_stack, RGBA_ICON_PATH)

    def get_name(self) -> str:
        """Return the modal's title string."""
        return COLOR_BALANCE_TITLE

    def get_modal_description(self) -> str:
        """Returns the modal's description string."""
        return COLOR_BALANCE_DESCRIPTION

    def get_config_key(self) -> str:
        """Returns the KeyConfig key used to load menu item info and keybindings."""
        return KeyConfig.COLOR_BALANCE_SHORTCUT

    def get_filter(self) -> Callable[..., QImage]:
        """Returns the filter's image variable filtering function."""
        return self.color_balance

    @staticmethod
    def color_balance(image: QImage, red: float, green: float, blue: float, alpha: float) -> QImage:
        """Add, multiply, subtract, or divide image colors by individual RGB component."""
        if alpha == 0:
            return create_transparent_image(image.size())
        color_channel_multipliers = (blue, green, red)
        final_image = image.copy()
        np_image = image_data_as_numpy_8bit(final_image)
        float_alpha = np_image[:, :, 3] / 255.0
        alpha_zero = np_image[:, :, 3] == 0

        for color_channel, factor in enumerate(color_channel_multipliers):
            np_image[~alpha_zero, color_channel] = np.clip(np_image[~alpha_zero, color_channel]
                                                           / float_alpha[~alpha_zero] * alpha * factor,
                                                           0, 255)
        np_image[~alpha_zero, 3] = np.clip(np_image[~alpha_zero, 3] * alpha, 0, 255)
        return final_image

    def get_parameters(self) -> List[Parameter]:
        """Returns definitions for the non-image parameters passed to the filtering function."""
        return [
            Parameter(RED_LABEL, TYPE_FLOAT, 1.0, '', 0.0, MAX_VALUE, 1.0),
            Parameter(GREEN_LABEL, TYPE_FLOAT, 1.0, '', 0.0, MAX_VALUE, 1.0),
            Parameter(BLUE_LABEL, TYPE_FLOAT, 1.0, '', 0.0, MAX_VALUE, 1.0),
            Parameter(ALPHA_LABEL, TYPE_FLOAT, 1.0, '', 0.0, MAX_VALUE, 1.0),
        ]
