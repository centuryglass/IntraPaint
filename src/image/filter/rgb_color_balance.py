"""Adjust RGB color levels."""
from typing import Callable, List

import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage

from src.config.key_config import KeyConfig
from src.image.filter.filter import ImageFilter
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.image_utils import image_data_as_numpy_8bit
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
        final_image = image.copy()
        np_image = image_data_as_numpy_8bit(final_image)
        channels = reversed(range(4))
        factors = (alpha, red, green, blue)

        for color_channel, factor in zip(channels, factors):
            adjusted_channel = np_image[:, :, color_channel].astype(np.float32)
            adjusted_channel *= factor
            np.clip(adjusted_channel, 0, 255, out=adjusted_channel)
            np_image[:, :, color_channel] = adjusted_channel
        return final_image

    def get_parameters(self) -> List[Parameter]:
        """Returns definitions for the non-image parameters passed to the filtering function."""
        return [
            Parameter(RED_LABEL, TYPE_FLOAT, 1.0, '', 0.0, MAX_VALUE, 1.0),
            Parameter(GREEN_LABEL, TYPE_FLOAT, 1.0, '', 0.0, MAX_VALUE, 1.0),
            Parameter(BLUE_LABEL, TYPE_FLOAT, 1.0, '', 0.0, MAX_VALUE, 1.0),
            Parameter(ALPHA_LABEL, TYPE_FLOAT, 1.0, '', 0.0, MAX_VALUE, 1.0),
        ]
