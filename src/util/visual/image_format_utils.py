"""Utility functions for saving and loading images across as many file formats as possible."""
from typing import Optional, Any

from PIL import Image, ExifTags, PngImagePlugin, TiffImagePlugin, TiffTags
from PIL.ExifTags import IFD
from PySide6.QtCore import QSize
from PySide6.QtGui import QImageReader, QImageWriter, QImage

from src.util.visual.image_utils import logger
from src.util.visual.pil_image_utils import qimage_to_pil_image, pil_image_to_qimage

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
INVALID_WRITE_FORMATS = {'MSP', 'JFIF', 'H5', 'HDF', 'PFM', 'APNG', 'WBMP'}

# Formats that need to be renamed to work correctly:
RENAMED_FORMATS = {'ICB': 'TGA', 'VST': 'TGA', 'VDA': 'TGA', 'EMF': 'WMF', 'JPE': 'JPEG', 'JPG': 'JPEG', 'PS': 'EPS',
                   'RGB': 'SGI', 'RGBA': 'SGI', 'BW': 'SGI', 'PBM': 'PPM', 'PGM': 'PPM', 'PNM': 'PPM', 'TIF': 'TIFF'}

# Formats that need to be omitted from PIL save parameters to work correctly:
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


def _write_data_to_exif_description(exif: Optional[Image.Exif], data: Optional[str]) -> Optional[Image.Exif]:
    """Create exif data storing a parameter string in the image description, or add the string to existing exif."""
    if exif is None:
        exif = Image.Exif()
    if data is None:
        return exif
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
        file_format = RENAMED_FORMATS.get(file_format)
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


def save_image_with_metadata(image: Image.Image | QImage, file_path: str, metadata: Optional[dict[str, Any]] = None,
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
    if file_format not in IMAGE_FORMATS_SUPPORTING_METADATA:
        raise ValueError(f'Format {file_format} cannot be used to store metadata.')
    parameter_text = ''
    if metadata is not None:
        if METADATA_PARAMETER_KEY in metadata:  # png
            parameter_text = metadata[METADATA_PARAMETER_KEY]
        elif METADATA_COMMENT_KEY in metadata:  # gif, jpeg2000
            parameter_text = metadata[METADATA_COMMENT_KEY]
    if not isinstance(parameter_text, str):
        # noinspection PyTypeChecker
        parameter_text = str(parameter_text, encoding='utf-8') if parameter_text is not None else ''
    if exif is None:
        exif = Image.Exif()
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
                image.save(file_path, 'PNG', pnginfo=info, exif=exif)
            else:
                image.save(file_path, 'PNG', exif=exif)
        case 'GIF':
            image.save(file_path, file_format, comment=parameter_text)
        case  'JP2' | 'JPX' | 'J2C' | 'JPC':
            image.save(file_path, comment=parameter_text, exif=exif)
        case 'JPG' | 'JPEG' | 'TIFF' | 'WEBP':
            if parameter_text != '':
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


def load_image(file_path: str) -> tuple[QImage, Optional[dict[str, Any]], Optional[Image.Exif]]:
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
