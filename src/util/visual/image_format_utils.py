"""Utility functions for saving and loading images across as many file formats as possible."""
import copy
from typing import Optional, Any, NamedTuple

from PIL import Image, ExifTags, PngImagePlugin, UnidentifiedImageError
from PIL.ExifTags import IFD
from PySide6.QtCore import QSize
from PySide6.QtGui import QImageReader, QImageWriter, QImage

from src.image.image_metadata import ImageMetadata, PARAMETERS_KEY, COMMENT_KEY, XMP_TEXT_KEY, IPTC_RESOURCE_ID
from src.util.visual.image_utils import logger, EXCLUDED_QIMAGE_FORMATS, read_qimage
from src.util.visual.pil_image_utils import qimage_to_pil_image, pil_image_to_qimage, EXCLUDED_PIL_FORMATS, \
    PIL_OPEN_FORMATS, convert_to_srgb

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
    """Stores a parameter string as the IFD0 ImageDescription, creating EXIF data if there is none.

    - Non-ASCII text is stored as UTF-8 bytes, which PIL writes unchanged. PIL writes a string's non-ASCII characters
      as "?". `decode_exif_text` reads the bytes back.
    - Removes an ImageDescription from the Exif IFD, where IntraPaint 1.4 and earlier also wrote it.
      `ImageMetadata._exif_description` reads that copy too, so a stale one would shadow the new text.
    """
    if exif is None:
        exif = Image.Exif()
    if data is None:
        return exif
    exif[ExifTags.Base.ImageDescription.value] = data if data.isascii() else data.encode('utf-8')
    if IFD.Exif in exif:
        exif.get_ifd(IFD.Exif).pop(ExifTags.Base.ImageDescription.value, None)
    return exif


def _save_pil(image: Image.Image, file_path: str, file_format: Optional[str] = None,
              exif: Optional[Image.Exif] = None, save_args: Optional[dict[str, Any]] = None) -> None:
    """Save a PIL image, optionally with metadata, performing format conversions as necessary.

    `save_args` are extra keyword arguments for `Image.save`, such as `xmp` or `comment`.
    """
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
    arguments = {} if save_args is None else dict(save_args)
    if exif is not None:
        arguments['exif'] = exif
    if file_format in OMITTED_FORMATS:
        image.save(file_path, **arguments)
    else:
        image.save(file_path, file_format, **arguments)


# A JPEG segment holds at most this many bytes after its marker, counting its 2-byte length field:
_JPEG_SEGMENT_MAX_SIZE = 0xFFFF
_JPEG_APP13_MARKER = b'\xff\xed'
_PHOTOSHOP_HEADER = b'Photoshop 3.0\0'
_PHOTOSHOP_RESOURCE_SIGNATURE = b'8BIM'
# Pillow's JPEG writer rejects an XMP packet longer than this, which is a segment minus its length field and header:
_JPEG_XMP_MAX_SIZE = 65504
# The XMP tag of a TIFF's first IFD:
_TIFF_XMP_TAG = 700


def _iptc_app13_segment(iptc: bytes) -> Optional[bytes]:
    """Returns a JPEG APP13 segment holding IPTC datasets as a Photoshop resource, or None if it would be too long.

    The resource has an empty name, and its data is padded to an even length, as Photoshop's format requires.
    """
    resource = _PHOTOSHOP_RESOURCE_SIGNATURE + IPTC_RESOURCE_ID.to_bytes(2, 'big') + b'\0\0' \
        + len(iptc).to_bytes(4, 'big') + iptc + (b'\0' if len(iptc) % 2 else b'')
    payload = _PHOTOSHOP_HEADER + resource
    if 2 + len(payload) > _JPEG_SEGMENT_MAX_SIZE:
        return None
    return _JPEG_APP13_MARKER + (2 + len(payload)).to_bytes(2, 'big') + payload


def _jpeg_save_args(metadata: ImageMetadata) -> dict[str, Any]:
    """Returns the `Image.save` arguments that write a JPEG's comment, XMP packet and IPTC data."""
    args: dict[str, Any] = {}
    comment = metadata.text.get(COMMENT_KEY, '')
    if comment != '':
        args['comment'] = comment
    xmp = metadata.xmp_packet
    if xmp is not None:
        if len(xmp) > _JPEG_XMP_MAX_SIZE:
            logger.warning('XMP data is too long for a JPEG and was not saved')
        else:
            args['xmp'] = xmp
    iptc = metadata.iptc_data
    if iptc is not None and len(iptc) > 0:
        segment = _iptc_app13_segment(iptc)
        if segment is None:
            logger.warning('IPTC data is too long for a JPEG and was not saved')
        else:
            args['extra'] = segment
    return args


def save_image_with_metadata(image: Image.Image | QImage, file_path: str,
                             metadata: Optional[ImageMetadata] = None) -> None:
    """
    Save an image to disk, using one of the formats that supports preserving metadata

    image: Image.Image
        PIL image or QImage to save. Must be compatible with the requested file format
    file_path: str
        Path where the file should be saved, including file extension. File format will be selected based on extension,
        and must be in IMAGE_FORMATS_SUPPORTING_METADATA.
    metadata: ImageMetadata, optional
        Metadata to write, which isn't changed. PNG keeps every text entry, the EXIF data and the XMP packet. GIF keeps
        only the generation parameters, or the comment if there are none, as its comment. JPEG 2000 keeps the same
        comment, plus EXIF data. JPEG, TIFF and WebP keep EXIF data, with the parameters as its ImageDescription, and
        the XMP packet. JPEG also keeps its comment and IPTC data, which no other format has a place for.
        `kept_kinds` in `src/image/metadata_save_rules.py` states these rules for the metadata window's note and the pre-save
        warning, so a change here changes it too.
    """
    delimiter_index = file_path.rfind('.')
    if delimiter_index < 0:
        raise ValueError(f'Invalid path {file_path} missing extension')
    file_format = file_path[delimiter_index + 1:].upper()
    # Apply replacement format if present, keep unchanged otherwise:
    file_format = RENAMED_FORMATS.get(file_format, file_format)
    if file_format not in IMAGE_FORMATS_SUPPORTING_METADATA:
        raise ValueError(f'Format {file_format} cannot be used to store metadata.')
    if metadata is None:
        metadata = ImageMetadata()
    parameter_text = metadata.parameters or ''
    # A comment that isn't generation data is kept where the parameters would go:
    comment_text = parameter_text or metadata.text.get(COMMENT_KEY, '')
    # The parameters are added to a copy, so the caller's EXIF data is unchanged:
    exif = copy.deepcopy(metadata.exif)
    if isinstance(image, QImage):
        image = qimage_to_pil_image(image)
    match file_format:
        case 'PNG':
            image.save(file_path, 'PNG', pnginfo=_png_text_chunks(metadata), exif=exif)
        case 'GIF':
            image.save(file_path, file_format, comment=comment_text)
        case  'JP2' | 'JPX' | 'J2C' | 'JPC':
            image.save(file_path, comment=comment_text, exif=exif)
        case 'JPG' | 'JPEG' | 'TIFF' | 'WEBP':
            if parameter_text != '':
                _write_data_to_exif_description(exif, parameter_text)
            save_args: dict[str, Any] = {}
            if file_format in ('JPG', 'JPEG'):
                save_args = _jpeg_save_args(metadata)
            elif file_format == 'WEBP':
                if metadata.xmp_packet is not None:
                    save_args['xmp'] = metadata.xmp_packet
            elif metadata.xmp_packet is not None:  # Pillow's TIFF writer takes the XMP packet as a tag.
                exif[_TIFF_XMP_TAG] = metadata.xmp_packet
            _save_pil(image, file_path, file_format, exif, save_args)
        case _:
            raise ValueError(f'Unhandled format {file_format}')


def _png_text_chunks(metadata: ImageMetadata) -> PngImagePlugin.PngInfo:
    """Returns every text entry as a PNG text chunk.

    Adds a `parameters` chunk if the parameters came from EXIF, and an XMP chunk if the packet came from another format.
    """
    info = PngImagePlugin.PngInfo()
    for key, value in metadata.text.items():
        try:
            info.add_itxt(key, value)
        except UnicodeEncodeError as png_err:  # PNG keywords must be Latin-1.
            logger.error(f'failed to preserve "{key}" in metadata: {png_err}')
    parameters = metadata.parameters
    if parameters is not None and PARAMETERS_KEY not in metadata.text:
        info.add_itxt(PARAMETERS_KEY, parameters)
    xmp = metadata.xmp
    if xmp is not None and XMP_TEXT_KEY not in metadata.text:
        info.add_itxt(XMP_TEXT_KEY, xmp)
    return info


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


def load_image(file_path: str) -> tuple[QImage, ImageMetadata]:
    """Load an image, returning it with its metadata. Formats only Qt can read return empty metadata."""
    delimiter_index = file_path.rfind('.')
    if delimiter_index < 0:
        raise ValueError(f'Invalid path {file_path} missing extension')
    file_format = file_path[delimiter_index + 1:].upper()
    if file_format in IMAGE_FORMATS_SUPPORTING_METADATA or file_format not in QIMAGE_READ_FORMATS:
        if file_format not in PIL_READ_FORMATS:
            raise UnidentifiedImageError(f'Unsupported image format {file_format}')
        image = Image.open(file_path, formats=PIL_OPEN_FORMATS)
        metadata = ImageMetadata.from_pil_image(image)
        return pil_image_to_qimage(convert_to_srgb(image)), metadata
    if file_format not in QIMAGE_READ_FORMATS:
        raise ValueError(f'Unsupported image format {file_format}')
    return read_qimage(file_path), ImageMetadata()


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
            frame_image = pil_image_to_qimage(convert_to_srgb(image))
            frames.append(ImageFrame(frame_image, None if duration is None else round(duration)))
    return frames


class AnimationSaveOptions(NamedTuple):
    """How to write an animation: the display time for frames without their own, and the loop count (0 is forever)."""
    default_duration_ms: int
    loop_count: int


def save_animation(frames: list[ImageFrame], file_path: str, options: AnimationSaveOptions,
                   metadata: Optional[ImageMetadata] = None) -> None:
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
    parameter_text = '' if metadata is None else (metadata.parameters or '')
    exif = None if metadata is None else copy.deepcopy(metadata.exif)
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
                png_info.add_itxt(PARAMETERS_KEY, parameter_text)
                save_args['pnginfo'] = png_info
        case 'WEBP':
            # An empty description would reload as an EXIF tag the image never had:
            if parameter_text != '' or (exif is not None and len(exif) > 0):
                save_args['exif'] = _write_data_to_exif_description(exif, parameter_text or None)
    pil_frames = [qimage_to_pil_image(frame.image) for frame in frames]
    pil_frames[0].save(file_path, file_format, append_images=pil_frames[1:], **save_args)
