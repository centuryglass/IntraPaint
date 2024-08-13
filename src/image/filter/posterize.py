"""Simplify images by reducing color count."""
from typing import List, Callable

from PIL import ImageOps
from PyQt5.QtWidgets import QApplication
from PySide6.QtCore import QRect
from PySide6.QtGui import QImage, QPainter

from src.config.key_config import KeyConfig
from src.image.filter.filter import ImageFilter
from src.util.image_utils import qimage_to_pil_image, pil_image_to_qimage
from src.util.parameter import Parameter, TYPE_INT

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'image.filter.posterize'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


POSTERIZE_FILTER_TITLE = _tr('Posterize')
POSTERIZE_FILTER_DESCRIPTION = _tr('Reduce color range by reducing image color bit count.')
PARAM_LABEL = _tr('Bit Count:')
PARAM_TEXT = _tr('Image color bits to preserve (1-8)')


class PosterizeFilter(ImageFilter):
    """Filter used to reduce image color range."""

    def get_modal_title(self) -> str:
        """Return the modal's title string."""
        return POSTERIZE_FILTER_TITLE

    def get_modal_description(self) -> str:
        """Returns the modal's description string."""
        return POSTERIZE_FILTER_DESCRIPTION

    def get_config_key(self) -> str:
        """Returns the KeyConfig key used to load menu item info and keybindings."""
        return KeyConfig.POSTERIZE_SHORTCUT

    def get_filter(self) -> Callable[..., QImage]:
        """Returns the filter's image variable filtering function."""
        return self.posterize

    @staticmethod
    def posterize(image: QImage, bits: int) -> QImage:
        """Reduce color depth within an image.

        Parameters
        ----------
        image: QImage | Image.Image
            Source image to adjust.
        bits: int
            The color channel bit count to keep. must be 1-8 inclusive.
        """
        assert 0 < bits <= 8, f'Invalid bit count {bits}'
        pil_image = qimage_to_pil_image(image).convert('RGB')
        posterized = ImageOps.posterize(pil_image, bits)
        filtered_image = pil_image_to_qimage(posterized).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        # Preserve transparency:
        painter = QPainter(filtered_image)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.drawImage(QRect(0, 0, image.width(), image.height()), image)
        painter.end()
        return filtered_image

    def get_parameters(self) -> List[Parameter]:
        """Return parameter definitions for the posterize filter."""
        return [Parameter(PARAM_LABEL, TYPE_INT, 3, PARAM_TEXT, 1, 8, 1)]
