"""Define image sharpening functions."""
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
TR_ID = 'image.filter.sharpen'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


SHARPEN_FILTER_TITLE = _tr('Sharpen')
SHARPEN_FILTER_DESCRIPTION = _tr('Sharpen the image')

FACTOR_LABEL = _tr('Factor')
FACTOR_DESCRIPTION = _tr('Sharpness factor (1.0: no change)')

ICON_PATH_SHARPEN_FILTER = f'{PROJECT_DIR}/resources/icons/filter/sharpen.png'


class SharpenFilter(ImageFilter):
    """Filter used to sharpen image details."""

    def __init__(self, image_stack: ImageStack) -> None:
        super().__init__(image_stack, ICON_PATH_SHARPEN_FILTER)

    def get_name(self) -> str:
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

    def radius(self, parameter_values: list[Any]) -> float:
        """Given a set of valid parameters, estimate how far each pixel's influence extends in the final image."""
        # This might be larger than necessary, but it's probably not worth finding the exact value to cut a few extra
        # pixel lines out of the change bounds.
        return 5.0

    @staticmethod
    def sharpen(image: QImage, factor: float) -> QImage:
        """Sharpens an image."""
        pil_image = qimage_to_pil_image(image)
        enhancer = ImageEnhance.Sharpness(pil_image)
        return pil_image_to_qimage(enhancer.enhance(factor))

    def get_parameters(self) -> list[Parameter]:
        """Return parameter definitions for the sharpen filter."""
        return [
            Parameter(FACTOR_LABEL, TYPE_FLOAT, 2.0, FACTOR_DESCRIPTION)
        ]
