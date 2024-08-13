"""Define image blurring functions."""
from typing import List, Callable
from PIL import ImageFilter as PilImageFilter
from PyQt5.QtWidgets import QApplication
from PySide6.QtGui import QImage

from src.config.key_config import KeyConfig
from src.image.filter.filter import ImageFilter
from src.util.image_utils import qimage_to_pil_image, pil_image_to_qimage
from src.util.parameter import Parameter, TYPE_FLOAT, TYPE_STR

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'image.filter.blur'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


MODE_SIMPLE = _tr('Simple')
MODE_BOX = _tr('Box')
MODE_GAUSSIAN = _tr('Gaussian')

BLUR_FILTER_TITLE = _tr('Blur')
BLUR_FILTER_DESCRIPTION = _tr('Blur the image')

MODE_LABEL = _tr('Blurring mode')
MODE_DESCRIPTION = _tr('Image blurring algorithm')

RADIUS_LABEL = _tr('Radius')
RADIUS_DESCRIPTION = _tr('Pixel blur radius (no effect in simple mode).')


class BlurFilter(ImageFilter):
    """Filter used to blur image content."""

    def get_modal_title(self) -> str:
        """Return the modal's title string."""
        return BLUR_FILTER_TITLE

    def get_modal_description(self) -> str:
        """Returns the modal's description string."""
        return BLUR_FILTER_DESCRIPTION

    def get_config_key(self) -> str:
        """Returns the KeyConfig key used to load menu item info and keybindings."""
        return KeyConfig.BLUR_SHORTCUT

    def get_filter(self) -> Callable[..., QImage]:
        """Returns the filter's image variable filtering function."""
        return self.blur

    def is_local(self) -> bool:
        """Indicates whether the filter operates independently on each pixel (True) or takes neighboring pixels
        into account (False)."""
        return False

    @staticmethod
    def blur(image: QImage, mode: str, radius: float) -> QImage:
        """Blurs an image."""
        pil_image = qimage_to_pil_image(image)
        if mode == MODE_SIMPLE:
            image_filter = PilImageFilter.BLUR
        elif mode == MODE_BOX:
            image_filter = PilImageFilter.BoxBlur(radius)
        elif mode == MODE_GAUSSIAN:
            image_filter = PilImageFilter.GaussianBlur(radius)
        else:
            raise ValueError(f'Invalid blur mode {mode}')
        return pil_image_to_qimage(pil_image.filter(image_filter))

    def get_parameters(self) -> List[Parameter]:
        """Return parameter definitions for the blur filter."""
        mode_parameter = Parameter(MODE_LABEL, TYPE_STR, MODE_BOX, MODE_DESCRIPTION)
        mode_parameter.set_valid_options([MODE_BOX, MODE_GAUSSIAN, MODE_SIMPLE])
        return [
            mode_parameter,
            Parameter(RADIUS_LABEL,
                      TYPE_FLOAT,
                      3.0,
                      RADIUS_DESCRIPTION,
                      0.0)
        ]
