"""Utility functions for saving and loading images across as many file formats as possible."""
from typing import Optional, Any, NamedTuple

from PIL import Image, ExifTags, PngImagePlugin, TiffImagePlugin, TiffTags, UnidentifiedImageError
from PIL.ExifTags import IFD
from PySide6.QtCore import QSize
from PySide6.QtGui import QImageReader, QImageWriter, QImage

from src.util.visual.image_utils import logger, EXCLUDED_QIMAGE_FORMATS, read_qimage
from src.util.visual.pil_image_utils import qimage_to_pil_image, pil_image_to_qimage, EXCLUDED_PIL_FORMATS, \
    PIL_OPEN_FORMATS

METADATA_PARAMETER_KEY = 'parameters'
METADATA_COMMENT_KEY = 'comment'
TIFF_DESCRIPTION_TAG = 'ImageDescription'

OPENRASTER_FORMAT = 'ORA'

# Formats Qt's image plugins can read or write, minus EXCLUDED_QIMAGE_FORMATS. Qt also picks a plugin from a file's
# contents when reading, so files go through read_qimage.
QIMAGE_READ_FORMATS = {str(qba.data(), encoding='utf-8').upper() for qba in QImageReader.supportedImageFormats()} \
    - EXCLUDED_QIMAGE_FORMATS
QIMAGE_WRITE_FORMATS = {str(qba.data(), encoding='utf-8').upper() for qba in QImageWriter.supportedImageFormats()} \
    - EXCLUDED_QIMAGE_FORMATS

# File extensions of the Pillow formats IntraPaint uses, see pil_image_utils.EXCLUDED_PIL_FORMATS.
PIL_READ_FORMATS = {ex[1:].upper() for ex, f in Image.registered_extensions().items()
                    if f in Image.OPEN and f not in EXCLUDED_PIL_FORMATS}

PIL_WRITE_FORMATS = {ex[1:].upper() for ex, f in Image.registered_extensions().items()
                     if f in Image.SAVE and f not in EXCLUDED_PIL_FORMATS}

# Formats that are programmatically listed as valid, but fail in testing.
INVALID_WRITE_FORMATS = {'MSP', 'JFIF', 'PFM', 'WBMP', 'AVIFS', 'WMF', 'EMF'}

# Formats that need to be renamed to work correctly:
RENAMED_FORMATS = {'ICB': 'TGA', 'VST': 'TGA', 'VDA': 'TGA', 'EMF': 'WMF', 'JPE': 'JPEG', 'JPG': 'JPEG',
                   'RGB': 'SGI', 'RGBA': 'SGI', 'BW': 'SGI', 'PBM': 'PPM', 'PGM': 'PPM', 'PNM': 'PPM', 'TIF': 'TIFF',
                   'APNG': 'PNG'}

# Formats saved with no Pillow format name. Pillow names these JPEG2000, and picks the container from the extension.
OMITTED_FORMATS = {'JP2', 'J2K', 'JPC', 'JPF', 'JPX', 'J2C'}


for format_set in PIL_WRITE_FORMATS, QIMAGE_WRITE_FORMATS:
    for invalid_format in INVALID_WRITE_FORMATS:
        if invalid_format in format_set:
            format_set.remove(invalid_format)
    for initial_format, renamed_format in RENAMED_FORMATS.items():
        if initial_format in format_set:
            format_set.add(renamed_format)


IMAGE_FORMATS_SUPPORTING_METADATA = ('ORA', 'PNG', 'APNG', 'JPG', 'JPEG', 'GIF', 'WEBP', 'TIF', 'TIFF', 'JPX', 'JPC',
                                     'JPM', 'JPE', 'J2C', 'JP2')
IMAGE_READ_FORMATS = {OPENRASTER_FORMAT, *PIL_READ_FORMATS, *QIMAGE_READ_FORMATS}
IMAGE_WRITE_FORMATS = {OPENRASTER_FORMAT, *PIL_WRITE_FORMATS, *QIMAGE_WRITE_FORMATS}

IMAGE_FORMATS_SUPPORTING_ALPHA = ('ORA', 'PNG', 'APNG', 'AVIF', 'WEBP', 'TIF', 'TIFF', 'TGA', 'ICB', 'JP2', 'JPX',
                                  'ICNS', 'ICO', 'CUR', 'VDA', 'VST')

IMAGE_FORMATS_SUPPORTING_PARTIAL_ALPHA = {'GIF', 'XPM'}

GREYSCALE_IMAGE_FORMATS = {'PBM', 'PGM', 'XBM'}

IMAGE_FORMATS_WITH_FIXED_SIZE = {
    'CUR': QSize(256, 192),
    'ICNS': QSize(256, 256),
    'ICO': QSize(256, 192)
}

# Pillow formats whose files open as one layer per frame. Other multi-frame formats load only their first frame, so a
# camera's MPO stereo pair opens as one photo.
ANIMATION_READ_FORMATS = {'GIF', 'PNG', 'WEBP', 'AVIF', 'TIFF'}

# Formats that can save more than one frame. Pillow has no APNG save format, so APNG files are PNG saved with
# `save_all`, see RENAMED_FORMATS.
ANIMATION_WRITE_FORMATS = {'GIF', 'WEBP', 'AVIF', 'APNG'}

# Formats where an animation save is the only way to keep more than one layer, so they never offer a flattened save.
ANIMATION_ONLY_FORMATS = {'APNG'}

# File formats that need explicit conversion before save:
PALETTE_FORMATS = {'BLP', 'PALM', 'XPM'}
RGB_FORMATS = {'JPEG', 'JPG', 'MPO', 'PCX'}
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
    # Apply replacement format if present, keep unchanged otherwise:
    file_format = RENAMED_FORMATS.get(file_format, file_format)
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
    # Apply replacement format if present, keep unchanged otherwise:
    file_format = RENAMED_FORMATS.get(file_format, file_format)

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
        if file_format not in PIL_READ_FORMATS:
            raise UnidentifiedImageError(f'Unsupported image format {file_format}')
        image = Image.open(file_path, formats=PIL_OPEN_FORMATS)
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
    return read_qimage(file_path), None, None


class ImageFrame(NamedTuple):
    """One frame of a multi-frame image file, with its display time in milliseconds if the file sets one."""
    image: QImage
    duration_ms: Optional[int]


def _frame_count(image: Image.Image) -> int:
    """Returns how many of an open Pillow image's frames load as layers."""
    if image.format not in ANIMATION_READ_FORMATS:
        return 1
    return int(getattr(image, 'n_frames', 1))


def count_image_frames(file_path: str) -> int:
    """Returns how many layers load_image_frames would load from a file, or 1 if Pillow can't open it."""
    try:
        with Image.open(file_path, formats=PIL_OPEN_FORMATS) as image:
            return _frame_count(image)
    except OSError:  # Includes UnidentifiedImageError, for files only Qt can read.
        return 1


def load_image_frames(file_path: str) -> list[ImageFrame]:
    """Loads every frame of an animation or multi-page image, in order. Other images load as a single frame.

    Pillow composites GIF and APNG frames onto the previous ones, so each frame is a complete image. Use load_image for
    metadata, and for formats only Qt can read.
    """
    frames: list[ImageFrame] = []
    with Image.open(file_path, formats=PIL_OPEN_FORMATS) as image:
        for frame_index in range(_frame_count(image)):
            image.seek(frame_index)
            image.load()  # WebP and AVIF set a frame's duration only once it loads.
            duration = image.info.get('duration')
            frames.append(ImageFrame(pil_image_to_qimage(image), None if duration is None else round(duration)))
    return frames


class AnimationSaveOptions(NamedTuple):
    """How to write an animation: the display time for frames without their own, and the loop count (0 is forever)."""
    default_duration_ms: int
    loop_count: int


def save_animation(frames: list[ImageFrame], file_path: str, options: AnimationSaveOptions,
                   metadata: Optional[dict[str, Any]] = None, exif: Optional[Image.Exif] = None) -> None:
    """Saves frames as an animated GIF, WebP, APNG or AVIF, chosen by the file extension.

    Frames without a duration use `options.default_duration_ms`. Image generation data in `metadata` goes with the
    first frame, as the GIF comment, a PNG text chunk or WebP EXIF. AVIF animations save none.
    """
    if len(frames) == 0:
        raise ValueError('Cannot save an animation with no frames.')
    delimiter_index = file_path.rfind('.')
    if delimiter_index < 0:
        raise ValueError(f'Invalid path {file_path} missing extension')
    extension = file_path[delimiter_index + 1:].upper()
    if extension not in ANIMATION_WRITE_FORMATS:
        raise ValueError(f'Format {extension} cannot be used to save animations.')
    file_format = RENAMED_FORMATS.get(extension, extension)
    durations = [options.default_duration_ms if frame.duration_ms is None else frame.duration_ms for frame in frames]
    parameter_text = ''
    if metadata is not None:
        parameter_text = metadata.get(METADATA_PARAMETER_KEY, metadata.get(METADATA_COMMENT_KEY, ''))
        if isinstance(parameter_text, bytes):
            parameter_text = parameter_text.decode('utf-8')
        elif not isinstance(parameter_text, str):
            parameter_text = ''
    save_args: dict[str, Any] = {'save_all': True, 'duration': durations, 'loop': options.loop_count}
    match file_format:
        case 'GIF':
            # Without disposal=2, transparent pixels show the previous frames through them.
            save_args['disposal'] = 2
            save_args['duration'] = [round(duration / 10) * 10 for duration in durations]
            if parameter_text != '':
                save_args['comment'] = parameter_text
        case 'PNG':
            if parameter_text != '':
                png_info = PngImagePlugin.PngInfo()
                png_info.add_itxt(METADATA_PARAMETER_KEY, parameter_text)
                save_args['pnginfo'] = png_info
        case 'WEBP':
            if parameter_text != '' or exif is not None:
                save_args['exif'] = _write_data_to_exif_description(exif, parameter_text)
    pil_frames = [qimage_to_pil_image(frame.image) for frame in frames]
    pil_frames[0].save(file_path, file_format, append_images=pil_frames[1:], **save_args)
