"""Stores an image's `ImageMetadata` in an .ora archive and reads it back, so a save keeps every part a load read.

- The XMP packet goes to `META-INF/metadata.xml` unchanged, following the OpenRaster XMP metadata proposal
  (https://www.openraster.org/proposals/xmp-metadata.html). exiftool reads it there only when the archive has no root
  `meta.xml`, so `open_raster` never writes one. A packet read from there replaces an XMP text entry's value.
- Text entries stay in the JSON of `extended_data.xml`'s `metadata` attribute, which older IntraPaint versions read.
- EXIF and IPTC data go to files under `data/extensions/metadata/`, named by the JSON payload of the
  `<extension name="metadata">` element. XMP can't hold all of either (maker notes, envelope datasets).
- DPI goes to the `<image>` element's `xres` and `yres` attributes.

The ICC profile and encoder details in `ImageMetadata.format_info` aren't stored. Pixels are converted to sRGB on load,
so the profile no longer describes them, and no save writes the rest.
"""
import json
import logging
import math
import posixpath
from typing import Any, Optional

from PIL import Image

from src.image.image_metadata import ImageMetadata, DPI_INFO_KEY
from src.image.ora_extensions import EXTENSION_DIRECTORY, METADATA_EXTENSION_NAME, OraReadContext

logger = logging.getLogger(__name__)

XMP_ARCHIVE_PATH = 'META-INF/metadata.xml'
EXIF_ARCHIVE_PATH = posixpath.join(EXTENSION_DIRECTORY, METADATA_EXTENSION_NAME, 'exif.bin')
"""EXIF data as `Image.Exif.tobytes` writes it: an `Exif` header and a TIFF structure."""
IPTC_ARCHIVE_PATH = posixpath.join(EXTENSION_DIRECTORY, METADATA_EXTENSION_NAME, 'iptc.bin')
"""The raw IPTC (IIM) datasets of a Photoshop IPTC resource."""
# Keys of the metadata extension payload, each naming the archive path of one part:
PAYLOAD_EXIF = 'exif'
PAYLOAD_IPTC = 'iptc'


def _binary_parts(metadata: ImageMetadata) -> dict[str, tuple[str, bytes]]:
    """Returns the EXIF and IPTC data to store, keyed by payload key, with the archive path of each."""
    parts: dict[str, tuple[str, bytes]] = {}
    if len(metadata.exif_entries()) > 0:
        parts[PAYLOAD_EXIF] = (EXIF_ARCHIVE_PATH, metadata.exif.tobytes())
    iptc = metadata.iptc_data
    if iptc is not None and len(iptc) > 0:
        parts[PAYLOAD_IPTC] = (IPTC_ARCHIVE_PATH, iptc)
    return parts


def metadata_archive_files(metadata: ImageMetadata) -> dict[str, bytes]:
    """Returns the archive files holding the XMP packet, EXIF data and IPTC datasets, keyed by archive path."""
    files = dict(_binary_parts(metadata).values())
    packet = metadata.xmp_packet
    if packet is not None:
        files[XMP_ARCHIVE_PATH] = packet
    return files


def metadata_extension_payload(metadata: ImageMetadata) -> Optional[str]:
    """Returns the metadata extension element's payload naming the EXIF and IPTC files, or None if there are none."""
    parts = _binary_parts(metadata)
    if len(parts) == 0:
        return None
    return json.dumps({key: path for key, (path, _) in parts.items()})


def _resolution(value: Any) -> Optional[int]:
    """Returns a DPI value rounded to the whole number `xres` and `yres` hold, or None if it isn't positive."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    rounded = round(value)
    return rounded if rounded > 0 else None


def encode_dpi(metadata: ImageMetadata) -> Optional[tuple[int, int]]:
    """Returns the `xres` and `yres` values for the metadata's DPI, or None if it has no usable DPI."""
    dpi = metadata.format_info.get(DPI_INFO_KEY)
    if not isinstance(dpi, (tuple, list)) or len(dpi) != 2:
        return None
    x_res, y_res = (_resolution(value) for value in dpi)
    if x_res is None or y_res is None:
        return None
    return x_res, y_res


def _parse_resolution(value: Optional[str]) -> Optional[int | float]:
    if value is None:
        return None
    try:
        resolution = float(value)
    except ValueError:
        logger.warning(f'Ignoring invalid .ora resolution "{value}"')
        return None
    if not math.isfinite(resolution) or resolution <= 0:
        logger.warning(f'Ignoring invalid .ora resolution "{value}"')
        return None
    return int(resolution) if resolution.is_integer() else resolution


def decode_dpi(x_res: Optional[str], y_res: Optional[str]) -> Optional[tuple[int | float, int | float]]:
    """Returns the DPI that `xres` and `yres` hold, using one for both if the other is missing or invalid."""
    x_value = _parse_resolution(x_res)
    y_value = _parse_resolution(y_res)
    if x_value is None and y_value is None:
        return None
    if x_value is None:
        x_value = y_value
    if y_value is None:
        y_value = x_value
    assert x_value is not None and y_value is not None
    return x_value, y_value


def load_exif(metadata: ImageMetadata, data: bytes) -> None:
    """Loads encoded EXIF data into `metadata`, logging and skipping data that can't be read."""
    try:
        metadata.exif.load(data)
        metadata.exif_entries()
    except (SyntaxError, ValueError, TypeError, OSError) as err:
        logger.error(f'Ignoring unreadable .ora EXIF data: {err}')
        metadata.exif = Image.Exif()


def read_metadata(metadata_json: Optional[str], extension_payload: Optional[str],
                  dpi: Optional[tuple[int | float, int | float]], read_context: OraReadContext) -> ImageMetadata:
    """Builds the metadata of a loaded .ora file from its text entry JSON, metadata payload, DPI and archive files.

    Missing or unreadable parts are left out, so a damaged file still loads.
    """
    metadata = ImageMetadata.from_ora_json(metadata_json)
    if dpi is not None:
        metadata.format_info[DPI_INFO_KEY] = dpi
    packet = read_context.read_file(XMP_ARCHIVE_PATH)
    if packet is not None:
        metadata.set_xmp_packet(packet)
    if extension_payload is None:
        return metadata
    try:
        paths = json.loads(extension_payload)
    except json.JSONDecodeError as err:
        logger.error(f'Ignoring unreadable .ora metadata payload: {err}')
        return metadata
    if not isinstance(paths, dict):
        return metadata
    for key, path in paths.items():
        data = read_context.read_file(path) if isinstance(path, str) else None
        if data is None:
            logger.warning(f'.ora metadata file for "{key}" is missing: {path}')
        elif key == PAYLOAD_EXIF:
            load_exif(metadata, data)
        elif key == PAYLOAD_IPTC:
            metadata.set_iptc_data(data)
    return metadata
