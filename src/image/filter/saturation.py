"""Define image saturation changes."""
from typing import Callable, Any

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
TR_ID = 'image.filter.saturation'


def _tr(key: str, disambiguation: str = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


SATURATION_FILTER_TITLE = _tr('Saturation')
SATURATION_FILTER_DESCRIPTION = _tr('Adjust image color saturation')

FACTOR_LABEL = _tr('Saturation')
FACTOR_DESCRIPTION = _tr('Saturation multiplier')

ICON_PATH_SHARPEN_FILTER = f'{PROJECT_DIR}/resources/icons/filter/saturation.png'


class SaturationFilter(ImageFilter):
    """Filter used to sharpen image details."""

    def __init__(self, image_stack: ImageStack) -> None:
        super().__init__(image_stack, ICON_PATH_SHARPEN_FILTER)

    def get_name(self) -> str:
        """Return the modal's title string."""
        return SATURATION_FILTER_TITLE

    def get_modal_description(self) -> str:
        """Returns the modal's description string."""
        return SATURATION_FILTER_DESCRIPTION

    def get_config_key(self) -> str:
        """Returns the KeyConfig key used to load menu item info and keybindings."""
        return KeyConfig.SATURATION_SHORTCUT

    def get_filter(self) -> Callable[..., QImage]:
        """Returns the filter's image variable filtering function."""
        return self.saturation

    def is_local(self) -> bool:
        """Indicates whether the filter operates independently on each pixel (True) or takes neighboring pixels
        into account (False)."""
        return True

    @staticmethod
    def saturation(image: QImage, factor: float) -> QImage:
        """Sharpens an image."""
        pil_image = qimage_to_pil_image(image)
        enhancer = ImageEnhance.Color(pil_image)
        return pil_image_to_qimage(enhancer.enhance(factor))

    def get_parameters(self) -> list[Parameter]:
        """Return parameter definitions for the saturation filter."""
        return [
            Parameter(FACTOR_LABEL, TYPE_FLOAT, 1.0, FACTOR_DESCRIPTION, 0.0, 5.0, 0.1)
        ]
