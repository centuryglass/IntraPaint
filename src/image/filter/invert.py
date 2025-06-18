"""Define image inversion filter."""
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
TR_ID = 'image.filter.invert'


def _tr(key: str, disambiguation: str = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


INVERT_FILTER_TITLE = _tr('Invert')
INVERT_FILTER_DESCRIPTION = _tr('Invert image colors')


ICON_PATH_INVERT_FILTER = f'{PROJECT_DIR}/resources/icons/filter/invert_icon.svg'


class InvertFilter(ImageFilter):
    """Filter used to invert image colors."""

    def __init__(self, image_stack: ImageStack) -> None:
        super().__init__(image_stack, ICON_PATH_INVERT_FILTER)

    def get_name(self) -> str:
        """Return the modal's title string."""
        return INVERT_FILTER_TITLE

    def get_modal_description(self) -> str:
        """Returns the modal's description string."""
        return INVERT_FILTER_DESCRIPTION

    def get_config_key(self) -> str:
        """Returns the KeyConfig key used to load menu item info and keybindings."""
        return KeyConfig.INVERT_SHORTCUT

    def get_filter(self) -> Callable[..., QImage]:
        """Returns the filter's image variable filtering function."""
        return self.invert

    def is_local(self) -> bool:
        """Indicates whether the filter operates independently on each pixel (True) or takes neighboring pixels
        into account (False)."""
        return True

    @staticmethod
    def invert(image: QImage) -> QImage:
        """Invert image colors."""
        image.invertPixels(QImage.InvertMode.InvertRgb)
        return image

    def get_parameters(self) -> list[Parameter]:
        """Return parameter definitions for the saturation filter."""
        return []
