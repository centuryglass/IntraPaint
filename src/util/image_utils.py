"""Adds general-purpose utility functions for manipulating image data"""
import base64
import io
import logging
from collections.abc import Buffer
from typing import Optional, Dict, Any, Tuple

import cv2
import numpy as np
from PIL import Image, ImageQt, PngImagePlugin, ExifTags, TiffTags, TiffImagePlugin
from PIL.ExifTags import IFD
from PySide6.QtCore import QBuffer, QRect, QSize, Qt, QPoint, QFile, QIODevice, QByteArray
from PySide6.QtGui import QImage, QIcon, QPixmap, QPainter, QColor, QImageReader, QImageWriter
from PySide6.QtWidgets import QStyle, QWidget, QApplication

from src.config.application_config import AppConfig
from src.image.mypaint.numpy_image_utils import AnyNpArray, image_data_as_numpy_8bit, numpy_8bit_to_qimage
from src.util.display_size import max_font_size
from src.util.geometry_utils import is_smaller_size
from src.util.shared_constants import PIL_SCALING_MODES

logger = logging.getLogger(__name__)
DEFAULT_ICON_SIZE = QSize(64, 64)

METADATA_PARAMETER_KEY = 'parameters'
METADATA_COMMENT_KEY = 'comment'
TIFF_DESCRIPTION_TAG = 'ImageDescription'

OPENRASTER_FORMAT = 'ORA'

# QImage can read: ['BMP', 'CUR', 'GIF', 'ICNS', 'ICO', 'JP2', 'JPEG', 'JPG', 'MNG', 'PBM', 'PDF', 'PGM', 'PNG', 'PPM',
#                   'SVG', 'SVGZ', 'TGA', 'TIF', 'TIFF', 'WBMP', 'WEBP', 'XBM', 'XPM']
QIMAGE_READ_FORMATS = {str(qba.data(), encoding='utf-8').upper() for qba in QImageReader.supportedImageFormats()}

# QImage can write: ['BMP', 'CUR', 'ICNS', 'ICO', 'JP2', 'JPEG', 'JPG', 'PBM', 'PGM', 'PNG', 'PPM', 'TIF', 'TIFF',
#                    'WBMP', 'WEBP', 'XBM', 'XPM']
QIMAGE_WRITE_FORMATS = {str(qba.data(), encoding='utf-8').upper() for qba in QImageWriter.supportedImageFormats()}

# PIL can read: ['BLP', 'BMP', 'DIB', 'BUFR', 'CUR', 'PCX', 'DCX', 'DDS', 'PS', 'EPS', 'FIT', 'FITS', 'FLI', 'FLC',
#                'FPX', 'FTC', 'FTU', 'GBR', 'GIF', 'GRIB', 'H5', 'HDF', 'PNG', 'APNG', 'JP2', 'J2K', 'JPC', 'JPF',
#                'JPX', 'J2C', 'ICNS', 'ICO', 'IM', 'IIM', 'JFIF', 'JPE', 'JPG', 'JPEG', 'TIF', 'TIFF', 'MIC', 'MPG',
#                'MPEG', 'MSP', 'PCD', 'PXR', 'PBM', 'PGM', 'PPM', 'PNM', 'PFM', 'PSD', 'QOI', 'BW', 'RGB', 'RGBA',
#                'SGI', 'RAS', 'TGA', 'ICB', 'VDA', 'VST', 'WEBP', 'WMF', 'EMF', 'XBM', 'XPM']
PIL_READ_FORMATS = {ex[1:].upper() for ex, f in Image.registered_extensions().items() if f in Image.OPEN}

# PIL can write: ['BLP', 'BMP', 'DIB', 'BUFR', 'PCX', 'DDS', 'PS', 'EPS', 'GIF', 'GRIB', 'H5', 'HDF', 'PNG', 'APNG',
#                 'JP2', 'J2K', 'JPC', 'JPF', 'JPX', 'J2C', 'ICNS', 'ICO', 'IM', 'JFIF', 'JPE', 'JPG', 'JPEG', 'TIF',
#                 'TIFF', 'MPO', 'MSP', 'PALM', 'PDF', 'PBM', 'PGM', 'PPM', 'PNM', 'PFM', 'BW', 'RGB', 'RGBA', 'SGI',
#                 'TGA', 'ICB', 'VDA', 'VST', 'WEBP', 'WMF', 'EMF', 'XBM']
PIL_WRITE_FORMATS = {ex[1:].upper() for ex, f in Image.registered_extensions().items() if f in Image.SAVE}

# Formats that are programmatically listed as valid, but fail in testing.
INVALID_WRITE_FORMATS = {'MSP', 'JFIF', 'H5', 'HDF', 'PFM', 'APNG'}

# Formats that need to be renamed to work correctly:
RENAMED_FORMATS = {'ICB': 'TGA', 'VST': 'TGA', 'VDA': 'TGA', 'EMF': 'WMF', 'JPE': 'JPEG', 'JPG': 'JPEG', 'PS': 'EPS',
                   'RGB': 'SGI', 'RGBA': 'SGI', 'BW': 'SGI', 'PBM': 'PPM', 'PGM': 'PPM', 'PNM': 'PPM', 'TIF': 'TIFF'}

# Formats that need to be omitted to work correctly:
OMITTED_FORMATS = {'J2K', 'JPC', 'JPF'}

for format_set in PIL_WRITE_FORMATS, QIMAGE_WRITE_FORMATS:
    for invalid_format in INVALID_WRITE_FORMATS:
        if invalid_format in format_set:
            format_set.remove(invalid_format)
    for initial_format, renamed_format in RENAMED_FORMATS.items():
        if initial_format in format_set:
            format_set.add(renamed_format)


IMAGE_FORMATS_SUPPORTING_METADATA = ('ORA', 'PNG', 'JPG', 'JPEG', 'GIF', 'WEBP', 'TIF', 'TIFF', 'JPX', 'JPC', 'JPM',
                                     'J2C', 'JP2')
IMAGE_READ_FORMATS = {OPENRASTER_FORMAT, *PIL_READ_FORMATS, *QIMAGE_READ_FORMATS}
IMAGE_WRITE_FORMATS = {OPENRASTER_FORMAT, *PIL_WRITE_FORMATS, *QIMAGE_WRITE_FORMATS}

IMAGE_FORMATS_SUPPORTING_ALPHA = ('ORA', 'PNG', 'WEBP', 'TIF', 'TIFF', 'TGA', 'ICB', 'JP2', 'JPX', 'ICNS', 'ICO', 'CUR',
                                  'VDA', 'VST')

IMAGE_FORMATS_SUPPORTING_PARTIAL_ALPHA = {'GIF', 'XPM'}

GREYSCALE_IMAGE_FORMATS = {'PBM', 'PGM', 'XBM'}

IMAGE_FORMATS_WITH_FIXED_SIZE = {
    'CUR': QSize(256, 192),
    'ICNS': QSize(256, 256),
    'ICO': QSize(256, 192)
}

# File formats that need explicit conversion before save:
PALETTE_FORMATS = {'BLP', 'PALM', 'XPM'}
RGB_FORMATS = {'JPEG', 'JPG', 'EPS', 'MPO', 'PCX'}
BINARY_FORMATS = {'XBM'}


def create_transparent_image(size: QSize) -> QImage:
    """Returns a new image filled with transparency, set to the requested size."""
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    return image


def image_is_fully_transparent(image: QImage) -> bool:
    """Returns whether all pixels in the image are 100% transparent."""
    if not image.hasAlphaChannel():
        return False
    if image.format() != QImage.Format.Format_ARGB32_Premultiplied:
        image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    np_image = image_data_as_numpy_8bit(image)
    return not (np_image[:, :, 3] > 0).any()


def image_is_fully_opaque(image: QImage) -> bool:
    """Returns whether all pixels in the image are 100% opaque."""
    if not image.hasAlphaChannel():
        return True
    if image.format() != QImage.Format.Format_ARGB32_Premultiplied:
        image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    np_image = image_data_as_numpy_8bit(image)
    return not (np_image[:, :, 3] < 255).any()


def image_has_partial_alpha(image: QImage) -> bool:
    """Returns whether the image contains pixels with any opacity other than 0 or 255"""
    return not image_is_fully_transparent(image) and not image_is_fully_opaque(image)


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
            mode = PIL_SCALING_MODES[AppConfig().get(AppConfig.UPSCALE_MODE)]
        else:
            mode = PIL_SCALING_MODES[AppConfig().get(AppConfig.DOWNSCALE_MODE)]
    image = image.resize((size.width(), size.height()), mode)
    return pil_image_to_qimage(image)


def qimage_from_base64(image_str: str) -> QImage:
    """Returns a QImage from base64-encoded string data."""
    if image_str.startswith(BASE_64_PREFIX):
        image_str = image_str[len(BASE_64_PREFIX):]
    image_data = QByteArray.fromBase64(image_str.encode())
    image = QImage.fromData(image_data, 'PNG')
    if image.isNull():
        raise ValueError('Invalid base64 image string')
    if image.hasAlphaChannel():
        image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    else:
        image = image.convertToFormat(QImage.Format.Format_RGB888)
    return image


def pil_image_from_base64(image_str: str) -> Image.Image:
    """Returns a PIL image object from base64-encoded string data."""
    if image_str.startswith(BASE_64_PREFIX):
        image_str = image_str[len(BASE_64_PREFIX):]
    return Image.open(io.BytesIO(base64.b64decode(image_str)))


BASE_64_PREFIX = 'data:image/png;base64,'


def image_to_base64(image: QImage | Image.Image | str, include_prefix=False) -> str:
    """Convert a PIL image, QImage or image path to a base64 string."""
    if isinstance(image, str):
        file = QFile(image)
        if not file.open(QIODevice.OpenModeFlag.ReadOnly):
            raise IOError(f'Failed to open {image}')
        image_str = QByteArray(file.readAll()).toBase64().data().decode('utf-8')
        file.close()
    elif isinstance(image, QImage):
        image_bytes = QByteArray()
        buffer = QBuffer(image_bytes)
        image.save(buffer, 'PNG')
        image_str = base64.b64encode(image_bytes.data()).decode('utf-8')
    else:
        assert isinstance(image, Image.Image)
        pil_buffer = io.BytesIO()
        image.save(pil_buffer, format='PNG')
        image_str = str(base64.b64encode(pil_buffer.getvalue()), 'utf-8')
    if include_prefix:
        return BASE_64_PREFIX + image_str
    return image_str


def image_content_bounds(image: QImage | np.ndarray, search_bounds: Optional[QRect] = None,
                         alpha_threshold=0.0) -> QRect:
    """Finds the smallest rectangle within an image that contains all non-empty pixels in that image.

    Parameters
    ----------
    image: QImage | ndarray
        A QImage with format ARGB32_Premultiplied, optionally pre-converted to a numpy array.
    search_bounds: QRect, optional
        Image content outside of these bounds will be ignored. If None, entire image bounds will be used.
    alpha_threshold: float, default = 0.0
        Any pixel with an alpha value at or below the alpha_threshold will be considered empty.
    """
    if isinstance(image, QImage):
        image_ptr = image.bits()
        assert image_ptr is not None
        np_image: AnyNpArray = np.ndarray(shape=(image.height(), image.width(), 4), dtype=np.uint8, buffer=image_ptr)
    else:
        np_image = image
    if search_bounds is not None:
        x_min = max(0, search_bounds.x())
        x_max = min(np_image.shape[1], search_bounds.x() + search_bounds.width())
        y_min = max(0, search_bounds.y())
        y_max = min(np_image.shape[0], search_bounds.y() + search_bounds.height())
        if x_max <= x_min or y_max <= y_min:
            return QRect()
        np_image = np_image[y_min:y_max, x_min:x_max:, :]
    else:
        x_min = 0
        y_min = 0
        y_max = np_image.shape[0]
        x_max = np_image.shape[1]
    content_rows = np.any(np_image[:, :, 3] > alpha_threshold, axis=1)
    if not np.any(content_rows):
        return QRect()
    content_columns = np.any(np_image[:, :, 3] > alpha_threshold, axis=0)
    min_content_row = y_min + np.argmax(content_rows)
    max_content_row = y_max - np.argmax(np.flip(content_rows)) - 1
    min_content_column = x_min + np.argmax(content_columns)
    max_content_column = x_max - np.argmax(np.flip(content_columns)) - 1
    if search_bounds is None:
        search_bounds = QRect(0, 0, np_image.shape[1], np_image.shape[0])
    left = int(min_content_column)
    top = int(min_content_row)
    width = max_content_column - min_content_column + 1
    height = max_content_row - min_content_row + 1
    logger.debug(f'image_content_bounds: searched {search_bounds.width()}x{search_bounds.height()} region at '
                 f'({search_bounds.x()},{search_bounds.y()}) in a {np_image.shape[1]}x{np_image.shape[0]} image, found '
                 f'content bounds {width}x{height} at ({left},{top})')
    if width <= 0 or height <= 0:
        return QRect()
    bounds = QRect(left, top, width, height)
    assert search_bounds.contains(bounds)
    return bounds


def crop_to_content(image: QImage) -> QImage:
    """Return a copy of an image with outer transparent pixels cropped away."""
    if image.isNull():
        return QImage()
    bounds = image_content_bounds(image)
    if bounds.isEmpty():
        return image.copy()
    return image.copy(bounds)


def get_standard_qt_icon(icon_code: QStyle.StandardPixmap, style_source: Optional[QWidget] = None) -> QIcon:
    """Returns one of the standard Qt icons."""
    if style_source is None:
        style = QApplication.style()
    else:
        style = style_source.style()
    assert style is not None
    return style.standardIcon(icon_code)


def get_character_icon(character: str, color: QColor) -> QIcon:
    """Renders a character as an icon."""
    assert len(character) == 1, f'Expected a single character, got {character}'
    font = QApplication.font()
    size = DEFAULT_ICON_SIZE
    pt_size = max_font_size(character, font, size)
    font.setPointSize(pt_size)
    font.setBold(True)
    pixmap = QPixmap(size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setFont(font)
    painter.setPen(color)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.drawText(QRect(QPoint(), DEFAULT_ICON_SIZE), Qt.AlignmentFlag.AlignCenter, character)
    painter.end()
    return QIcon(pixmap)


TRANSPARENCY_PATTERN_BACKGROUND_DIM = 640
TRANSPARENCY_PATTERN_TILE_DIM = 16


def tile_pattern_fill(pixmap: QPixmap,
                      tile_size: int,
                      tile_color_1: QColor | Qt.GlobalColor,
                      tile_color_2: QColor | Qt.GlobalColor) -> None:
    """Draws an alternating tile pattern onto a QPixmap."""
    fill_pixmap_size = tile_size * 2
    fill_pixmap = QPixmap(QSize(fill_pixmap_size, fill_pixmap_size))
    fill_pixmap.fill(tile_color_1)
    painter = QPainter(fill_pixmap)
    for x in range(tile_size, fill_pixmap_size + tile_size, tile_size):
        for y in range(tile_size, fill_pixmap_size + tile_size, tile_size):
            if (x % (tile_size * 2)) == (y % (tile_size * 2)):
                continue
            painter.fillRect(x - tile_size, y - tile_size, tile_size, tile_size, tile_color_2)
    painter.end()
    painter = QPainter(pixmap)
    painter.drawTiledPixmap(0, 0, pixmap.width(), pixmap.height(), fill_pixmap)
    painter.end()


def get_transparency_tile_pixmap(size: Optional[QSize] = None) -> QPixmap:
    """Returns a tiling pixmap used to represent transparency."""
    if size is None:
        size = QSize(TRANSPARENCY_PATTERN_BACKGROUND_DIM, TRANSPARENCY_PATTERN_BACKGROUND_DIM)
    transparency_pixmap = QPixmap(size)
    tile_pattern_fill(transparency_pixmap, TRANSPARENCY_PATTERN_TILE_DIM, Qt.GlobalColor.lightGray,
                      Qt.GlobalColor.darkGray)
    return transparency_pixmap


def _flood_fill_rgb(image: QImage, pos: QPoint, color: QColor, threshold: float) -> QImage:
    np_image = image_data_as_numpy_8bit(image)
    cv2_np_image = np_image[:, :, :3]  # cv2 won't accept 4-channel images.
    if not cv2_np_image.flags['C_CONTIGUOUS']:
        cv2_np_image = np.ascontiguousarray(cv2_np_image)
    seed_point = (pos.x(), pos.y())
    fill_color = (color.blue(), color.green(), color.red())
    height, width, _ = np_image.shape
    mask = np.zeros((height + 2, width + 2), np.uint8)
    flags = cv2.FLOODFILL_MASK_ONLY
    cv2.floodFill(cv2_np_image, mask, seed_point, fill_color,
                  loDiff=(threshold, threshold, threshold, threshold),
                  upDiff=(threshold, threshold, threshold, threshold),
                  flags=flags)
    assert mask is not None
    mask = mask[1:-1, 1:-1]  # Remove the border
    mask_image = np.zeros_like(np_image)
    mask_indices = np.where(mask == 1)
    mask_image[mask_indices[0], mask_indices[1]] = (color.blue(), color.green(), color.red(), 255)
    return numpy_8bit_to_qimage(mask_image)


def flood_fill(image: QImage, pos: QPoint, color: QColor, threshold: float, in_place: bool = False) -> Optional[QImage]:
    """Returns a mask image marking all areas of similar color directly connected to a point in an image.

    Parameters
    ----------
        image: QImage
            Source image, in format Format_ARGB32_Premultiplied.
        pos: QPoint
            Seed point for the fill operation.
        color: QColor
            Color used to draw filled pixels in the final mask image.
        threshold: float
            Maximum color difference to ignore when determining which pixels to fill.
        in_place: bool, default=False
            If True, modify the image in-place and do not return a mask.
    Returns
    -------
        mask: Optional[QImage]
            Mask image marking the area to be filled, returned only if in_place=False. The mask image will be the same
            size as the source image. filled pixels will be set to the color parameter, while unfilled pixels will be
            fully transparent.
    """
    tmp_image = image.copy()
    np_tmp_image = image_data_as_numpy_8bit(tmp_image)
    np_image = image_data_as_numpy_8bit(image)
    mask = QImage(image.size(), QImage.Format.Format_ARGB32_Premultiplied)
    mask.fill(color)
    painter = QPainter(mask)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    np_tmp_image[..., 3] = 255
    for i in range(3):
        if i > 0:
            np_tmp_image[..., i - 1] = np_image[..., i - 1]
        np_tmp_image[..., i] = np_image[..., 3]
        channel_fill_mask = _flood_fill_rgb(tmp_image, pos, color, threshold)
        painter.drawImage(0, 0, channel_fill_mask)
    painter.end()
    if not in_place:
        return mask
    painter = QPainter(image)
    painter.drawImage(0, 0, mask)
    painter.end()
    return None


def _write_data_to_exif_description(exif: Optional[Image.Exif], data: Optional[str]) -> Optional[Image.Exif]:
    """Create exif data storing a parameter string in the image description, or add the string to existing exif."""
    if data is None:
        return exif
    if exif is None:
        exif = Image.Exif()
    exif_tags = exif.get_ifd(IFD.Exif)
    exif[ExifTags.Base.ImageDescription.value] = data
    exif_tags[ExifTags.Base.ImageDescription.value] = data
    return exif


def _save_pil(image: Image.Image, file_path: str, file_format: Optional[str] = None,
              exif: Optional[Image.Exif] = None) -> None:
    """Save a PIL image, optionally with metadata, performing format conversions as necessary."""
    if file_format is None:
        delimiter_index = file_path.rfind('.')
        if delimiter_index < 0:
            raise ValueError(f'Invalid path {file_path} missing extension')
        file_format = file_path[delimiter_index + 1:].upper()
    if file_format in RENAMED_FORMATS:
        file_format = RENAMED_FORMATS[file_format]
    if file_format in PALETTE_FORMATS:
        image = image.convert('P')
        if file_format == 'PALM':
            palette = image.getpalette()
            image.save(file_path, file_format, info={'custom-colormap': palette})
    elif file_format in RGB_FORMATS:
        image = image.convert('RGB')
    elif file_format in BINARY_FORMATS:
        image = image.convert('1')
    if exif is not None:
        if file_format in OMITTED_FORMATS:
            image.save(file_path, exif=exif)
        else:
            image.save(file_path, file_format, exif=exif)
    else:
        if file_format in OMITTED_FORMATS:
            image.save(file_path)
        else:
            image.save(file_path, file_format)


def save_image_with_metadata(image: Image.Image | QImage, file_path: str, metadata: Optional[Dict[str, Any]] = None,
                             exif: Optional[Image.Exif] = None) -> None:
    """
    Save an image to disk, using one of the formats that supports preserving metadata

    image: Image.Image
        PIL image or QImage to save. Must be compatible with the requested file format
    file_path: str
        Path where the file should be saved, including file extension.  File format will be selected based on extension.
        Supported extensions are PNG, GIF,
    metadata: dict
        Metadata key/value pairs. Only .png will preserve the full dict, other formats only save image generation data
        found within metadata['parameters'].
    """
    delimiter_index = file_path.rfind('.')
    if delimiter_index < 0:
        raise ValueError(f'Invalid path {file_path} missing extension')
    file_format = file_path[delimiter_index + 1:].upper()
    if file_format in RENAMED_FORMATS:
        file_format = RENAMED_FORMATS[file_format]

    parameter_text = None
    if metadata is not None:
        if METADATA_PARAMETER_KEY in metadata:  # png
            parameter_text = metadata[METADATA_PARAMETER_KEY]
        elif METADATA_COMMENT_KEY in metadata:  # gif, jpeg2000
            parameter_text = metadata[METADATA_COMMENT_KEY]
    if parameter_text is not None:
        if not isinstance(parameter_text, str):
            assert isinstance(parameter_text, Buffer)
            parameter_text = str(parameter_text, encoding='utf-8')
    if file_format not in IMAGE_FORMATS_SUPPORTING_METADATA:
        raise ValueError(f'Format {file_format} cannot be used to store metadata.')
    if isinstance(image, QImage):
        image = qimage_to_pil_image(image)
    match file_format:
        case 'PNG':
            info = PngImagePlugin.PngInfo()
            if metadata is not None:
                for key in metadata:
                    try:
                        info.add_itxt(key, metadata[key])
                    except AttributeError as png_err:
                        # Encountered some sort of image metadata that PIL knows how to read but not how to write.
                        # I've seen this a few times, mostly with images edited in Krita.
                        # TODO: Look into what data is actually lost here, fix it or confirm that it is definitely
                        #       inconsequential.
                        logger.error(f'failed to preserve "{key}" in metadata: {png_err}')
                assert exif is not None
                image.save(file_path, 'PNG', pnginfo=info, exif=exif)
        case 'GIF':
            image.save(file_path, file_format, comment=parameter_text)
        case  'JP2' | 'JPX' | 'J2C' | 'JPC':
            image.save(file_path, comment=parameter_text, exif=exif)
        case 'JPG' | 'JPEG' | 'TIFF' | 'WEBP':
            assert exif is not None
            assert parameter_text is not None
            _write_data_to_exif_description(exif, parameter_text)
            _save_pil(image, file_path, file_format, exif)
        case _:
            raise ValueError(f'Unhandled format {file_format}')


def save_image(image: Image.Image | QImage, file_path: str, exif: Optional[Image.Exif] = None) -> None:
    """Save an image to disk, using any format supported by PIL or QImage."""
    delimiter_index = file_path.rfind('.')
    if delimiter_index < 0:
        raise ValueError(f'Invalid path {file_path} missing extension')
    file_format = file_path[delimiter_index + 1:].upper()
    if file_format in RENAMED_FORMATS:
        file_format = RENAMED_FORMATS[file_format]

    if isinstance(image, Image.Image):
        if file_format in PIL_WRITE_FORMATS:
            _save_pil(image, file_path, file_format, exif)
        elif file_format in QIMAGE_WRITE_FORMATS:
            image = pil_image_to_qimage(image)
            image.save(file_path)
        else:
            raise ValueError(f'Unsupported image format {file_format}')
    else:
        assert isinstance(image, QImage)
        if file_format in PIL_WRITE_FORMATS:
            _save_pil(qimage_to_pil_image(image), file_path, file_format, exif)
        elif file_format in QIMAGE_WRITE_FORMATS:
            image.save(file_path)
        else:
            raise ValueError(f'Unsupported image format {file_format}')


def load_image(file_path: str) -> Tuple[QImage, Optional[Dict[str, Any]], Optional[Image.Exif]]:
    """Load an image, returning it with associated metadata if possible"""
    delimiter_index = file_path.rfind('.')
    if delimiter_index < 0:
        raise ValueError(f'Invalid path {file_path} missing extension')
    file_format = file_path[delimiter_index + 1:].upper()
    if file_format in IMAGE_FORMATS_SUPPORTING_METADATA or file_format not in QIMAGE_READ_FORMATS:
        assert file_format in PIL_READ_FORMATS
        image = Image.open(file_path)
        exif = image.getexif()
        info = None
        if hasattr(image, 'tag_v2') and file_format in ('TIF', 'TIFF'):
            tags = image.tag_v2
            assert isinstance(tags, TiffImagePlugin.ImageFileDirectory_v2)
            info = {}
            for code, value in tags.items():
                tag_name = TiffTags.TAGS_V2[code].name
                info[tag_name] = value
                if tag_name == TIFF_DESCRIPTION_TAG:
                    info[METADATA_PARAMETER_KEY] = value
        elif hasattr(image, 'info') and image.info is not None:
            info = image.info
            assert isinstance(info, dict)
            if METADATA_COMMENT_KEY in info and METADATA_PARAMETER_KEY not in info:
                info[METADATA_PARAMETER_KEY] = info[METADATA_COMMENT_KEY]
        return pil_image_to_qimage(image), info, exif
    if file_format not in QIMAGE_READ_FORMATS:
        raise ValueError(f'Unsupported image format {file_format}')
    return QImage(file_path), None, None

