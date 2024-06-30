"""Adjust image brightness/contrast."""
from typing import List, Callable
from PIL import ImageEnhance
from PyQt5.QtGui import QImage

from src.config.key_config import KeyConfig
from src.image.filter.filter import ImageFilter
from src.util.image_utils import qimage_to_pil_image, pil_image_to_qimage
from src.util.parameter import Parameter, TYPE_FLOAT

BRIGHTNESS_CONTRAST_FILTER_TITLE = 'Brightness/Contrast'
BRIGHTNESS_CONTRAST_FILTER_DESCRIPTION = 'Adjust image brightness and contrast.'

BRIGHTNESS_LABEL = 'Brightness:'
CONTRAST_LABEL = 'Contrast'


class BrightnessContrastFilter(ImageFilter):
    """Filter used to adjust image brightness and contrast."""

    def get_modal_title(self) -> str:
        """Return the modal's title string."""
        return BRIGHTNESS_CONTRAST_FILTER_TITLE

    def get_modal_description(self) -> str:
        """Returns the modal's description string."""
        return BRIGHTNESS_CONTRAST_FILTER_DESCRIPTION

    def get_config_key(self) -> str:
        """Returns the KeyConfig key used to load menu item info and keybindings."""
        return KeyConfig.BRIGHTNESS_CONTRAST_SHORTCUT

    def get_filter(self) -> Callable[..., QImage]:
        """Returns the filter's image variable filtering function."""
        return self.brightness_contrast_filter

    @staticmethod
    def brightness_contrast_filter(image: QImage, brightness: float, contrast: float) -> QImage:
        """Adjusts image brightness and contrast."""
        pil_image = qimage_to_pil_image(image)
        pil_image = ImageEnhance.Brightness(pil_image).enhance(brightness)
        pil_image = ImageEnhance.Contrast(pil_image).enhance(contrast)
        return pil_image_to_qimage(pil_image)

    def get_parameters(self) -> List[Parameter]:
        """Return parameter definitions for the brightness/contrast filter."""
        return [
            Parameter(BRIGHTNESS_LABEL,
                      TYPE_FLOAT,
                      1.0,
                      '',
                      0.0,
                      50.0,
                      0.5),
            Parameter(CONTRAST_LABEL,
                      TYPE_FLOAT,
                      1.0,
                      '',
                      0.0,
                      50.0,
                      0.5),
        ]
