"""Utility functions for manipulating PIL images."""
import base64
import io
from typing import Optional

from PIL import Image, ImageChops, ImageQt
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from src.config.application_config import AppConfig
from src.util.shared_constants import PIL_SCALING_MODES
from src.util.visual.geometry_utils import is_smaller_size
from src.util.visual.image_utils import BASE_64_PREFIX

# Pillow formats IntraPaint never opens or saves.
# - EPS covers .eps and .ps files, which Pillow reads by running them as programs in the external Ghostscript
#   interpreter. Crafted files have repeatedly escaped its sandbox to run commands.
# - BUFR, GRIB, HDF5 and MPEG files are ones Pillow can identify but not decode or encode.
# - WMF covers .wmf and .emf files. Pillow draws them only on Windows, where Image.core has drawwmf, and saves them
#   nowhere.
Image.init()
EXCLUDED_PIL_FORMATS = {'EPS', 'BUFR', 'GRIB', 'HDF5', 'MPEG'}
if not hasattr(Image.core, 'drawwmf'):
    EXCLUDED_PIL_FORMATS.add('WMF')

# Image.open() picks a decoder from the file's contents, not its name, so it always gets this list. Otherwise an EPS
# file renamed to .png would still reach Ghostscript.
PIL_OPEN_FORMATS = tuple(pil_format for pil_format in Image.OPEN if pil_format not in EXCLUDED_PIL_FORMATS)


def pil_image_to_qimage(pil_image: Image.Image) -> QImage:
    """Convert a PIL Image to a Qt6 QImage."""
    if not isinstance(pil_image, Image.Image):
        raise TypeError('Invalid PIL Image parameter.')
    if pil_image.mode not in ('RGBA', 'RGB'):
        pil_image = pil_image.convert('RGBA')
    if pil_image.mode == 'RGB':
        image = QImage(pil_image.tobytes('raw', 'RGB'),
                       pil_image.width,
                       pil_image.height,
                       pil_image.width * 3,
                       QImage.Format.Format_RGB888)
    else:  # RGBA
        assert pil_image.mode == 'RGBA', f'Unexpected PIL image mode {pil_image.mode}'
        image = QImage(pil_image.tobytes('raw', 'RGBA'),
                       pil_image.width,
                       pil_image.height,
                       pil_image.width * 4,
                       QImage.Format.Format_RGBA8888)
        image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    return image


def qimage_to_pil_image(qimage: QImage) -> Image.Image:
    """Convert a Qt6 QImage to a PIL image, in PNG format."""
    if not isinstance(qimage, QImage):
        raise TypeError('Invalid QImage parameter.')
    return ImageQt.fromqimage(qimage)


def qimage_to_premultiplied_pil_image(qimage: QImage) -> Image.Image:
    """Convert a QImage to a PIL image in 'RGBA' mode whose color channels are premultiplied by alpha.

    Filters that mix neighboring pixels (blur, sharpen) use this so fully transparent pixels contribute no color.
    The result is not straight RGBA: pass it back through `premultiplied_pil_image_to_qimage`, never to code that
    expects straight alpha. `qimage_to_pil_image` is the straight-alpha conversion."""
    if not isinstance(qimage, QImage):
        raise TypeError('Invalid QImage parameter.')
    converted = qimage.convertToFormat(QImage.Format.Format_RGBA8888_Premultiplied)
    # frombuffer reads bytesPerLine() as the stride, so padded rows are handled.
    return Image.frombuffer('RGBA', (converted.width(), converted.height()), bytes(converted.constBits()),
                            'raw', 'RGBA', converted.bytesPerLine(), 1)


def premultiplied_pil_image_to_qimage(pil_image: Image.Image) -> QImage:
    """Convert a PIL image holding premultiplied 'RGBA' data (see `qimage_to_premultiplied_pil_image`) to an
    ARGB32_Premultiplied QImage. Color values that exceed alpha, which filters can produce, are clamped to alpha."""
    if pil_image.mode != 'RGBA':
        raise ValueError(f'Expected premultiplied RGBA data, found mode {pil_image.mode}')
    red, green, blue, alpha = pil_image.split()
    pil_image = Image.merge('RGBA', (ImageChops.darker(red, alpha), ImageChops.darker(green, alpha),
                                     ImageChops.darker(blue, alpha), alpha))
    image = QImage(pil_image.tobytes('raw', 'RGBA'),
                   pil_image.width,
                   pil_image.height,
                   pil_image.width * 4,
                   QImage.Format.Format_RGBA8888_Premultiplied)
    return image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)


def pil_qsize(image: Image.Image) -> QSize:
    """Return PIL image size as QSize for easier comparison."""
    return QSize(image.width, image.height)


def pil_image_scaling(image: QImage | Image.Image, size: QSize, mode: Optional[Image.Resampling] = None) -> QImage:
    """Resize an image using a PIL scaling algorithm, returning a QImage.  If no specific scaling mode is provided,
       the appropriate scaling mode defined in AppConfig will be used."""
    image_size = image.size() if isinstance(image, QImage) else pil_qsize(image)
    if image_size == size:
        return image if isinstance(image, QImage) else pil_image_to_qimage(image)
    if isinstance(image, QImage):
        image = qimage_to_pil_image(image)
    if mode is None:
        if is_smaller_size(image_size, size):
            mode = PIL_SCALING_MODES[AppConfig().get(AppConfig.PIL_UPSCALE_MODE)]
        else:
            mode = PIL_SCALING_MODES[AppConfig().get(AppConfig.PIL_DOWNSCALE_MODE)]
    image = image.resize((size.width(), size.height()), mode)
    return pil_image_to_qimage(image)


def pil_image_from_base64(image_str: str) -> Image.Image:
    """Returns a PIL image object from base64-encoded string data."""
    if image_str.startswith(BASE_64_PREFIX):
        image_str = image_str[len(BASE_64_PREFIX):]
    return Image.open(io.BytesIO(base64.b64decode(image_str)), formats=PIL_OPEN_FORMATS)
