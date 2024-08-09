"""Define image sharpening functions."""
from typing import List, Callable

from PIL import ImageEnhance
from PySide6.QtGui import QImage

from src.config.key_config import KeyConfig
from src.image.filter.filter import ImageFilter
from src.util.image_utils import qimage_to_pil_image, pil_image_to_qimage
from src.util.parameter import Parameter, TYPE_FLOAT

SHARPEN_FILTER_TITLE = 'Sharpen'
SHARPEN_FILTER_DESCRIPTION = 'Sharpen the image'

FACTOR_LABEL = 'Factor'
FACTOR_DESCRIPTION = 'Sharpness factor (1.0: no change)'


class SharpenFilter(ImageFilter):
    """Filter used to sharpen image details."""

    def get_modal_title(self) -> str:
        """Return the modal's title string."""
        return SHARPEN_FILTER_TITLE

    def get_modal_description(self) -> str:
        """Returns the modal's description string."""
        return SHARPEN_FILTER_DESCRIPTION

    def get_config_key(self) -> str:
        """Returns the KeyConfig key used to load menu item info and keybindings."""
        return KeyConfig.SHARPEN_SHORTCUT

    def get_filter(self) -> Callable[..., QImage]:
        """Returns the filter's image variable filtering function."""
        return self.sharpen

    def is_local(self) -> bool:
        """Indicates whether the filter operates independently on each pixel (True) or takes neighboring pixels
        into account (False)."""
        return False

    @staticmethod
    def sharpen(image: QImage, factor: float) -> QImage:
        """Sharpens an image."""
        pil_image = qimage_to_pil_image(image)
        enhancer = ImageEnhance.Sharpness(pil_image)
        return pil_image_to_qimage(enhancer.enhance(factor))

    def get_parameters(self) -> List[Parameter]:
        """Return parameter definitions for the sharpen filter."""
        return [
            Parameter(FACTOR_LABEL, TYPE_FLOAT, 2.0, FACTOR_DESCRIPTION)
        ]
