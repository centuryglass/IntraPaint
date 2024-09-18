"""Adjust image brightness/contrast."""
from typing import List, Callable
from PIL import ImageEnhance
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage

from src.config.key_config import KeyConfig
from src.image.filter.filter import ImageFilter
from src.image.layers.image_stack import ImageStack
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.pil_image_utils import pil_image_to_qimage, qimage_to_pil_image
from src.util.parameter import Parameter, TYPE_FLOAT

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'image.filter.brightness_contrast'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


BRIGHTNESS_CONTRAST_FILTER_TITLE = _tr('Brightness/Contrast')
BRIGHTNESS_CONTRAST_FILTER_DESCRIPTION = _tr('Adjust image brightness and contrast.')

BRIGHTNESS_LABEL = _tr('Brightness:')
CONTRAST_LABEL = _tr('Contrast')

BRIGHTNESS_CONTRAST_ICON_PATH =  f'{PROJECT_DIR}/resources/icons/filter/brightness_contrast_icon.svg'


class BrightnessContrastFilter(ImageFilter):
    """Filter used to adjust image brightness and contrast."""

    def __init__(self, image_stack: ImageStack) -> None:
        super().__init__(image_stack, BRIGHTNESS_CONTRAST_ICON_PATH)

    def get_name(self) -> str:
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
