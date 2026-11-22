"""Reads an image file's metadata, and writes edited metadata back to the file without changing its pixels.

- PNG and APNG chunks, JPEG segments, WebP chunks, GIF extension blocks and .ora archive members are rewritten in
  place. The image data is copied byte for byte, so every frame and the color profile are kept.
- TIFF and JPEG 2000 files are re-encoded from their decoded pixels, which is lossless. Every TIFF page is kept.
- A JPEG-compressed TIFF loses quality when it is re-encoded, and some formats hold no metadata at all.
  `metadata_write_method` reports both, so the caller can ask before writing.

Each write keeps the parts of the metadata that an editor save to the same format keeps (`kept_kinds` in
`src/image/metadata_save_rules.py`), so the metadata window's save note describes these writes too. The color profile
is never removed, since the pixels a file holds depend on it.

This module imports nothing that loads the image model or libmypaint, so the standalone metadata mode can use it.
"""
import copy
import os
import shutil
import struct
import zipfile
import zlib
from enum import Enum
from typing import Any

from PIL import Image, ImageSequence, UnidentifiedImageError
from PySide6.QtGui import QImage

from src.image.image_metadata import ImageMetadata, COMMENT_KEY, ICC_PROFILE_INFO_KEY, DPI_INFO_KEY
from src.image.metadata_save_rules import format_name, format_keeps_metadata
from src.image.ora_extensions import MERGED_IMAGE_FILE_NAME
from src.image.ora_metadata import read_ora_file_metadata, write_ora_file_metadata
from src.util.file_replace import replacing_file
from src.util.visual.image_format_utils import png_text_chunks, iptc_app13_segment, write_data_to_exif_description, \
    save_image_with_metadata, save_image, load_image_frames, save_animation, AnimationSaveOptions, \
    ANIMATION_WRITE_FORMATS, OPENRASTER_FORMAT, JPEG_XMP_MAX_SIZE, ImageFrame
from src.util.visual.image_utils import read_qimage
from src.util.visual.pil_image_utils import PIL_OPEN_FORMATS


class MetadataWriteMethod(Enum):
    """How `write_file_metadata` writes a file's metadata."""
    IN_PLACE = 'in_place'
    """Rewrites the metadata blocks, and copies the image data unchanged."""
    REENCODE = 'reencode'
    """Re-encodes the decoded pixels losslessly."""
    LOSSY_REENCODE = 'lossy_reencode'
    """Re-encodes the pixels at the highest quality, which still loses some. Needs `allow_lossy`."""
    UNSUPPORTED = 'unsupported'
    """The format can't hold metadata, or this module can't write it."""


_IN_PLACE_FORMATS = frozenset({OPENRASTER_FORMAT, 'PNG', 'JPEG', 'WEBP', 'GIF'})
_JPEG_2000_FORMATS = frozenset({'JP2', 'JPX', 'J2C', 'JPC'})
# Upper-case format names `write_file_metadata` can write, see `format_name`:
METADATA_WRITE_FORMATS = _IN_PLACE_FORMATS | _JPEG_2000_FORMATS | {'TIFF'}
_TIFF_JPEG_COMPRESSIONS = frozenset({'jpeg', 'tiff_jpeg'})
# Display time for frames without their own, when a Save as re-encodes an animation:
_DEFAULT_FRAME_DURATION_MS = 100


def file_format(file_path: str) -> str:
    """Returns the upper-case format name saves use for a file's extension."""
    return format_name(os.path.splitext(file_path)[1].lstrip('.'))


def format_writes_metadata(file_path: str) -> bool:
    """Returns whether `write_file_metadata` can write a file with this extension, perhaps only with `allow_lossy`.

    Reads only the extension, so it is cheap enough to check on every refresh.
    """
    name = file_format(file_path)
    return name in METADATA_WRITE_FORMATS


def metadata_write_method(file_path: str) -> MetadataWriteMethod:
    """Returns how `write_file_metadata` would write an existing file's metadata."""
    name = file_format(file_path)
    if name in _IN_PLACE_FORMATS:
        return MetadataWriteMethod.IN_PLACE
    if name in _JPEG_2000_FORMATS:
        return MetadataWriteMethod.REENCODE
    if name == 'TIFF':
        with Image.open(file_path, formats=('TIFF',)) as image:
            compression = image.info.get('compression')
        return MetadataWriteMethod.LOSSY_REENCODE if compression in _TIFF_JPEG_COMPRESSIONS \
            else MetadataWriteMethod.REENCODE
    return MetadataWriteMethod.UNSUPPORTED


def read_file_metadata(file_path: str) -> ImageMetadata:
    """Reads a file's metadata without loading an image stack. Formats Pillow can't open have none."""
    if file_format(file_path) == OPENRASTER_FORMAT:
        return read_ora_file_metadata(file_path)
    try:
        with Image.open(file_path, formats=PIL_OPEN_FORMATS) as image:
            return ImageMetadata.from_pil_image(image)
    except UnidentifiedImageError:
        if read_qimage(file_path).isNull():
            raise
        return ImageMetadata()


def write_file_metadata(file_path: str, metadata: ImageMetadata, allow_lossy: bool = False) -> None:
    """Replaces an existing file's metadata, keeping its pixels.

    Raises ValueError if `metadata_write_method` is UNSUPPORTED, or LOSSY_REENCODE without `allow_lossy`, or if the file
    doesn't match its extension's format. The file is replaced through a temporary file, so a failed write leaves it
    unchanged.
    """
    method = metadata_write_method(file_path)
    if method == MetadataWriteMethod.UNSUPPORTED:
        raise ValueError(f'IntraPaint can\'t write metadata to {file_format(file_path)} files.')
    if method == MetadataWriteMethod.LOSSY_REENCODE and not allow_lossy:
        raise ValueError(f'Writing metadata to {file_path} would re-encode it with some loss of quality.')
    name = file_format(file_path)
    if name == OPENRASTER_FORMAT:
        write_ora_file_metadata(file_path, metadata)
        return
    with replacing_file(file_path) as temp_path:
        if method == MetadataWriteMethod.IN_PLACE:
            with open(file_path, 'rb') as file:
                data = file.read()
            match name:
                case 'PNG':
                    data = png_with_metadata(data, metadata)
                case 'JPEG':
                    data = jpeg_with_metadata(data, metadata)
                case 'WEBP':
                    data = webp_with_metadata(data, metadata)
                case _:
                    assert name == 'GIF'
                    data = gif_with_metadata(data, metadata)
            with open(temp_path, 'wb') as file:
                file.write(data)
        else:
            _reencode_with_metadata(file_path, temp_path, metadata, method == MetadataWriteMethod.LOSSY_REENCODE)


def save_metadata_copy(source_path: str, target_path: str, metadata: ImageMetadata,
                       allow_lossy: bool = False) -> None:
    """Saves a copy of an image file at `target_path` with `metadata`, in the format the target's extension names.

    - A copy in the source's own format is a file copy followed by `write_file_metadata`, so it keeps the pixels as
      that does. `allow_lossy` is passed on.
    - A copy in another format is re-encoded from the decoded pixels, as an editor save would write them. An
      animation keeps its frames if the target format can hold them, and keeps only the first frame otherwise.
    - The copy of an .ora file in another format is its merged image. Other formats can't be saved as .ora, since
      that needs the editor's layers.

    Raises ValueError for a copy that can't be written.
    """
    if os.path.abspath(source_path) == os.path.abspath(target_path):
        write_file_metadata(target_path, metadata, allow_lossy)
        return
    source_format = file_format(source_path)
    target_format = file_format(target_path)
    if source_format == target_format and metadata_write_method(source_path) != MetadataWriteMethod.UNSUPPORTED:
        with replacing_file(target_path) as temp_path:
            shutil.copyfile(source_path, temp_path)
            write_file_metadata(temp_path, metadata, allow_lossy)
        return
    if target_format == OPENRASTER_FORMAT:
        raise ValueError('Only an .ora file can be saved as .ora without opening it in the editor.')
    if source_format == OPENRASTER_FORMAT:
        frames = [_ora_merged_frame(source_path)]
        loop_count = 0
    else:
        frames = load_image_frames(source_path)
        loop_count = int(metadata.format_info.get('loop', 0))
    with replacing_file(target_path) as temp_path:
        if len(frames) > 1 and target_format in ANIMATION_WRITE_FORMATS:
            save_animation(frames, temp_path, AnimationSaveOptions(_DEFAULT_FRAME_DURATION_MS, loop_count), metadata)
        elif format_keeps_metadata(target_format):
            save_image_with_metadata(frames[0].image, temp_path, metadata)
        else:
            save_image(frames[0].image, temp_path, metadata.exif)


def _ora_merged_frame(file_path: str) -> ImageFrame:
    """Returns an .ora file's merged image as a single frame."""
    with zipfile.ZipFile(file_path) as archive:
        image = QImage.fromData(archive.read(MERGED_IMAGE_FILE_NAME))
    if image.isNull():
        raise ValueError(f'{file_path} has no readable merged image.')
    return ImageFrame(image, None)


def _exif_for_save(metadata: ImageMetadata) -> Image.Exif:
    """Returns a copy of the EXIF data with the generation parameters as its ImageDescription, as JPEG, TIFF and WebP
    saves write it."""
    exif = copy.deepcopy(metadata.exif)
    parameters = metadata.parameters
    if parameters:
        write_data_to_exif_description(exif, parameters)
    return exif


def _has_exif(exif: Image.Exif) -> bool:
    return len(ImageMetadata(exif=exif).exif_entries()) > 0


def _reencode_with_metadata(file_path: str, temp_path: str, metadata: ImageMetadata, lossy: bool) -> None:
    """Re-encodes a TIFF or JPEG 2000 file with new metadata, keeping every TIFF page.

    The pixels are written as the file holds them, with no conversion to sRGB, so a TIFF keeps its color profile.
    """
    with Image.open(file_path, formats=PIL_OPEN_FORMATS) as image:
        frames = [frame.copy() for frame in ImageSequence.Iterator(image)]
        info = dict(image.info)
    save_args: dict[str, Any] = {}
    if file_format(file_path) == 'TIFF':
        if info.get(ICC_PROFILE_INFO_KEY) is not None:
            save_args['icc_profile'] = info[ICC_PROFILE_INFO_KEY]
        compression = info.get('compression')
        if compression not in (None, 'raw'):
            save_args['compression'] = compression
        if DPI_INFO_KEY in info:
            save_args[DPI_INFO_KEY] = info[DPI_INFO_KEY]
        if lossy:
            save_args['quality'] = 100
        if len(frames) > 1:
            save_args['save_all'] = True
            save_args['append_images'] = frames[1:]
    save_image_with_metadata(frames[0], temp_path, metadata, save_args)


# PNG:

_PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
_PNG_METADATA_CHUNKS = frozenset({b'tEXt', b'zTXt', b'iTXt', b'eXIf'})
_EXIF_HEADER = b'Exif\x00\x00'


def _png_chunk(chunk_type: bytes, chunk_data: bytes) -> bytes:
    return struct.pack('>I', len(chunk_data)) + chunk_type + chunk_data \
        + struct.pack('>I', zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF)


def png_with_metadata(data: bytes, metadata: ImageMetadata) -> bytes:
    """Returns PNG or APNG file data with its text and EXIF chunks replaced, and every other chunk unchanged.

    The new chunks follow IHDR. They hold every text entry, the EXIF data and the XMP packet, as a PNG save writes them.
    """
    if not data.startswith(_PNG_SIGNATURE):
        raise ValueError('Not a PNG file.')
    chunks: list[bytes] = []
    offset = len(_PNG_SIGNATURE)
    while offset < len(data):
        if offset + 8 > len(data):
            raise ValueError('Truncated PNG chunk.')
        length = struct.unpack('>I', data[offset:offset + 4])[0]
        chunk_type = data[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(data):
            raise ValueError('Truncated PNG chunk.')
        if chunk_type not in _PNG_METADATA_CHUNKS:
            chunks.append(data[offset:end])
        offset = end
        if chunk_type == b'IEND':
            break
    if len(chunks) == 0 or chunks[0][4:8] != b'IHDR':
        raise ValueError('PNG file does not start with IHDR.')
    new_chunks = [_png_chunk(chunk_type, chunk_data) for chunk_type, chunk_data, _ in png_text_chunks(metadata).chunks]
    if _has_exif(metadata.exif):
        exif_data = metadata.exif.tobytes()
        new_chunks.append(_png_chunk(b'eXIf', exif_data.removeprefix(_EXIF_HEADER)))
    return _PNG_SIGNATURE + chunks[0] + b''.join(new_chunks) + b''.join(chunks[1:])


# JPEG:

_JPEG_SOI = b'\xff\xd8'
_JPEG_SOS = 0xDA
_JPEG_EOI = 0xD9
_JPEG_APP0 = 0xE0
_JPEG_APP1 = 0xE1
_JPEG_APP13 = 0xED
_JPEG_COM = 0xFE
_JPEG_TEM = 0x01
_JPEG_RST_MARKERS = range(0xD0, 0xD8)
_JPEG_SEGMENT_MAX_DATA = 0xFFFF - 2
_XMP_APP1_HEADER = b'http://ns.adobe.com/xap/1.0/\x00'
_PHOTOSHOP_APP13_HEADER = b'Photoshop 3.0\x00'


def _jpeg_segment(marker: int, payload: bytes, description: str) -> bytes:
    if len(payload) > _JPEG_SEGMENT_MAX_DATA:
        raise ValueError(f'The {description} is too long for a JPEG file.')
    return bytes([0xFF, marker]) + struct.pack('>H', len(payload) + 2) + payload


def _is_replaced_jpeg_segment(marker: int, payload: bytes) -> bool:
    """Returns whether a segment holds a part of the metadata that `jpeg_with_metadata` rewrites."""
    if marker == _JPEG_APP1:
        return payload.startswith(_EXIF_HEADER) or payload.startswith(_XMP_APP1_HEADER)
    if marker == _JPEG_APP13:
        return payload.startswith(_PHOTOSHOP_APP13_HEADER)
    return marker == _JPEG_COM


def jpeg_with_metadata(data: bytes, metadata: ImageMetadata) -> bytes:
    """Returns JPEG file data with its EXIF, XMP, Photoshop and comment segments replaced, and its image data unchanged.

    The new segments follow any JFIF segments. Of the Photoshop resources, only the IPTC data is written, as a JPEG save
    writes it. Raises ValueError if a part is too long for a JPEG segment.
    """
    if not data.startswith(_JPEG_SOI):
        raise ValueError('Not a JPEG file.')
    leading: list[bytes] = []
    kept: list[bytes] = []
    offset = len(_JPEG_SOI)
    while True:
        if offset + 2 > len(data) or data[offset] != 0xFF:
            raise ValueError('Damaged JPEG segment.')
        while data[offset + 1] == 0xFF:  # Fill bytes before a marker
            offset += 1
        marker = data[offset + 1]
        if marker in (_JPEG_SOS, _JPEG_EOI):
            break
        if marker == _JPEG_TEM or marker in _JPEG_RST_MARKERS:
            kept.append(data[offset:offset + 2])
            offset += 2
            continue
        length = struct.unpack('>H', data[offset + 2:offset + 4])[0]
        end = offset + 2 + length
        if length < 2 or end > len(data):
            raise ValueError('Damaged JPEG segment.')
        payload = data[offset + 4:end]
        if marker == _JPEG_APP0 and len(kept) == 0:
            leading.append(data[offset:end])
        elif not _is_replaced_jpeg_segment(marker, payload):
            kept.append(data[offset:end])
        offset = end
    new_segments: list[bytes] = []
    exif = _exif_for_save(metadata)
    if _has_exif(exif):
        new_segments.append(_jpeg_segment(_JPEG_APP1, exif.tobytes(), 'EXIF data'))
    xmp = metadata.xmp_packet
    if xmp is not None:
        if len(xmp) > JPEG_XMP_MAX_SIZE:
            raise ValueError('The XMP data is too long for a JPEG file.')
        new_segments.append(_jpeg_segment(_JPEG_APP1, _XMP_APP1_HEADER + xmp, 'XMP data'))
    iptc = metadata.iptc_data
    if iptc is not None and len(iptc) > 0:
        segment = iptc_app13_segment(iptc)
        if segment is None:
            raise ValueError('The IPTC data is too long for a JPEG file.')
        new_segments.append(segment)
    comment = metadata.text.get(COMMENT_KEY, '')
    if comment != '':
        new_segments.append(_jpeg_segment(_JPEG_COM, comment.encode('utf-8'), 'comment'))
    return _JPEG_SOI + b''.join(leading) + b''.join(new_segments) + b''.join(kept) + data[offset:]


# WebP:

_RIFF_HEADER_SIZE = 12
_VP8X_ALPHA = 0x10
_VP8X_EXIF = 0x08
_VP8X_XMP = 0x04
_VP8L_SIGNATURE = 0x2F


def _riff_chunk(fourcc: bytes, payload: bytes) -> bytes:
    return fourcc + struct.pack('<I', len(payload)) + payload + (b'\x00' if len(payload) % 2 else b'')


def _webp_canvas(fourcc: bytes, payload: bytes) -> tuple[int, int, bool]:
    """Returns the width, height and whether alpha is used, from a simple WebP file's VP8 or VP8L chunk."""
    if fourcc == b'VP8L' and len(payload) >= 5 and payload[0] == _VP8L_SIGNATURE:
        bits = int.from_bytes(payload[1:5], 'little')
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1, bool((bits >> 28) & 1)
    if fourcc == b'VP8 ' and len(payload) >= 10 and payload[3:6] == b'\x9d\x01\x2a':
        width = int.from_bytes(payload[6:8], 'little') & 0x3FFF
        height = int.from_bytes(payload[8:10], 'little') & 0x3FFF
        return width, height, False
    raise ValueError('Damaged WebP image data.')


def webp_with_metadata(data: bytes, metadata: ImageMetadata) -> bytes:
    """Returns WebP file data with its EXIF and XMP chunks replaced, and every other chunk unchanged.

    The new chunks go last. A simple WebP file gains the VP8X header chunk that metadata needs, built from its image
    chunk's size and alpha flag.
    """
    if len(data) < _RIFF_HEADER_SIZE or data[0:4] != b'RIFF' or data[8:12] != b'WEBP':
        raise ValueError('Not a WebP file.')
    chunks: list[tuple[bytes, bytes]] = []
    offset = _RIFF_HEADER_SIZE
    while offset + 8 <= len(data):
        fourcc = data[offset:offset + 4]
        size = struct.unpack('<I', data[offset + 4:offset + 8])[0]
        if offset + 8 + size > len(data):
            raise ValueError('Truncated WebP chunk.')
        if fourcc not in (b'EXIF', b'XMP '):
            chunks.append((fourcc, data[offset + 8:offset + 8 + size]))
        offset += 8 + size + (size % 2)
    if len(chunks) == 0:
        raise ValueError('WebP file has no image data.')
    new_chunks: list[tuple[bytes, bytes]] = []
    flags = 0
    exif = _exif_for_save(metadata)
    if _has_exif(exif):
        new_chunks.append((b'EXIF', exif.tobytes().removeprefix(_EXIF_HEADER)))
        flags |= _VP8X_EXIF
    xmp = metadata.xmp_packet
    if xmp is not None:
        new_chunks.append((b'XMP ', xmp))
        flags |= _VP8X_XMP
    if chunks[0][0] == b'VP8X':
        header = bytearray(chunks[0][1])
        header[0] = (header[0] & ~(_VP8X_EXIF | _VP8X_XMP)) | flags
        chunks[0] = (b'VP8X', bytes(header))
    elif flags != 0:
        width, height, has_alpha = _webp_canvas(*chunks[0])
        if has_alpha:
            flags |= _VP8X_ALPHA
        header = bytes([flags, 0, 0, 0]) + (width - 1).to_bytes(3, 'little') + (height - 1).to_bytes(3, 'little')
        chunks.insert(0, (b'VP8X', header))
    body = b'WEBP' + b''.join(_riff_chunk(fourcc, payload) for fourcc, payload in chunks + new_chunks)
    return b'RIFF' + struct.pack('<I', len(body)) + body


# GIF:

_GIF_EXTENSION = 0x21
_GIF_IMAGE = 0x2C
_GIF_TRAILER = 0x3B
_GIF_COMMENT_LABEL = 0xFE
_GIF_APPLICATION_LABEL = 0xFF
_GIF_SUB_BLOCK_MAX = 255


def _skip_gif_sub_blocks(data: bytes, offset: int) -> int:
    """Returns the offset just past a chain of data sub-blocks and its terminator."""
    while True:
        if offset >= len(data):
            raise ValueError('Truncated GIF data.')
        size = data[offset]
        offset += 1 + size
        if size == 0:
            return offset


def _gif_color_table_size(flags: int) -> int:
    return 3 * (2 ** ((flags & 0x07) + 1)) if flags & 0x80 else 0


def gif_with_metadata(data: bytes, metadata: ImageMetadata) -> bytes:
    """Returns GIF file data with its comment extensions replaced, and every frame unchanged.

    A GIF holds the generation parameters, or the comment if there are none, as one comment. It goes after any
    application extensions, such as the animation loop count, and before the first frame.
    """
    if data[:6] not in (b'GIF87a', b'GIF89a') or len(data) < 13:
        raise ValueError('Not a GIF file.')
    offset = 13 + _gif_color_table_size(data[10])
    header = bytearray(data[:offset])
    blocks: list[tuple[int, int, bytes]] = []  # (introducer, extension label or 0, block bytes)
    while True:
        if offset >= len(data):
            raise ValueError('Truncated GIF data.')
        introducer = data[offset]
        if introducer == _GIF_TRAILER:
            break
        if introducer == _GIF_EXTENSION:
            label = data[offset + 1]
            end = _skip_gif_sub_blocks(data, offset + 2)
        elif introducer == _GIF_IMAGE:
            label = 0
            end = _skip_gif_sub_blocks(data, offset + 11 + _gif_color_table_size(data[offset + 9]))
        else:
            raise ValueError('Damaged GIF block.')
        if not (introducer == _GIF_EXTENSION and label == _GIF_COMMENT_LABEL):
            blocks.append((introducer, label, data[offset:end]))
        offset = end
    comment = metadata.parameters or metadata.text.get(COMMENT_KEY, '')
    comment_block = b''
    if comment != '':
        comment_bytes = comment.encode('utf-8')
        comment_block = bytes([_GIF_EXTENSION, _GIF_COMMENT_LABEL])
        for start in range(0, len(comment_bytes), _GIF_SUB_BLOCK_MAX):
            sub_block = comment_bytes[start:start + _GIF_SUB_BLOCK_MAX]
            comment_block += bytes([len(sub_block)]) + sub_block
        comment_block += b'\x00'
        header[:6] = b'GIF89a'  # GIF87a has no extension blocks.
    insert_index = 0
    while insert_index < len(blocks) and blocks[insert_index][:2] == (_GIF_EXTENSION, _GIF_APPLICATION_LABEL):
        insert_index += 1
    block_data = [block for _, _, block in blocks]
    block_data.insert(insert_index, comment_block)
    return bytes(header) + b''.join(block_data) + data[offset:]
