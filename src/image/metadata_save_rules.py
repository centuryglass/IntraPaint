"""Which parts of an image's metadata a save to each file format keeps.

`kept_kinds` is the one copy of these rules that the user-facing reports read: the metadata window's save note and the
pre-save loss dialog. `save_image_with_metadata`, `save_animation` and `src/image/ora_metadata.py` do the writing, and
a change to what they write changes `kept_kinds` too.
"""
from enum import Enum
from typing import NamedTuple, Optional

from src.image.image_metadata import ImageMetadata, PARAMETERS_KEY, COMMENT_KEY, XMP_TEXT_KEY
from src.util.visual.image_format_utils import IMAGE_FORMATS_SUPPORTING_METADATA, RENAMED_FORMATS


class MetadataKind(Enum):
    """A category of metadata that saves keep or drop as a unit."""
    PARAMETERS = 'parameters'
    COMMENT = 'comment'
    TEXT_ENTRIES = 'text_entries'
    EXIF = 'exif'
    XMP = 'xmp'
    IPTC = 'iptc'


class MetadataPart(NamedTuple):
    """One kind of metadata an image carries, with the names of its items.

    `details` names the EXIF tags, IPTC datasets or text entry keys, without repeats. It is empty for kinds that have
    no separate items, and can be long.
    """
    kind: MetadataKind
    details: tuple[str, ...]


_PNG_FORMATS = ('PNG', 'APNG')
_COMMENT_ONLY_FORMATS = ('GIF',)
_COMMENT_EXIF_FORMATS = ('JP2', 'JPX', 'J2C', 'JPC', 'JPM')

_PNG_KINDS = frozenset({MetadataKind.PARAMETERS, MetadataKind.COMMENT, MetadataKind.TEXT_ENTRIES, MetadataKind.EXIF,
                        MetadataKind.XMP})
_ORA_KINDS = _PNG_KINDS | {MetadataKind.IPTC}
_JPEG_KINDS = frozenset({MetadataKind.PARAMETERS, MetadataKind.COMMENT, MetadataKind.EXIF, MetadataKind.XMP,
                         MetadataKind.IPTC})
_EXIF_XMP_KINDS = frozenset({MetadataKind.PARAMETERS, MetadataKind.EXIF, MetadataKind.XMP})
# Animation saves write less than still saves, see `save_animation`:
_ANIMATION_KINDS = {'GIF': frozenset({MetadataKind.PARAMETERS}), 'PNG': frozenset({MetadataKind.PARAMETERS}),
                    'WEBP': frozenset({MetadataKind.PARAMETERS, MetadataKind.EXIF})}


def format_name(file_format: str) -> str:
    """Returns the upper-case format name saves use for an extension, so 'jpg' and 'JPEG' are both 'JPEG'."""
    file_format = file_format.upper()
    return RENAMED_FORMATS.get(file_format, file_format)


def format_keeps_metadata(file_format: str) -> bool:
    """Returns whether saving as `file_format` can keep any metadata."""
    return format_name(file_format) in IMAGE_FORMATS_SUPPORTING_METADATA


def metadata_parts(metadata: ImageMetadata) -> list[MetadataPart]:
    """Returns the kinds of metadata `metadata` carries, in a fixed order.

    A comment equal to the generation parameters is the same data, so it is not listed twice.
    """
    parameters = metadata.parameters
    comment = metadata.text.get(COMMENT_KEY, '')
    other_keys = [key for key in metadata.text if key not in (PARAMETERS_KEY, COMMENT_KEY, XMP_TEXT_KEY)]
    exif_names = tuple(dict.fromkeys(entry.name for entry in metadata.exif_entries()))
    iptc_names = tuple(dict.fromkeys(entry.name for entry in metadata.iptc_entries()))
    parts: list[MetadataPart] = []
    if parameters is not None:
        parts.append(MetadataPart(MetadataKind.PARAMETERS, ()))
    if comment not in ('', parameters):
        parts.append(MetadataPart(MetadataKind.COMMENT, ()))
    if len(other_keys) > 0:
        parts.append(MetadataPart(MetadataKind.TEXT_ENTRIES, tuple(other_keys)))
    if len(exif_names) > 0:
        parts.append(MetadataPart(MetadataKind.EXIF, exif_names))
    if metadata.xmp_packet is not None:
        parts.append(MetadataPart(MetadataKind.XMP, ()))
    if len(iptc_names) > 0:
        parts.append(MetadataPart(MetadataKind.IPTC, iptc_names))
    return parts


def kept_kinds(file_format: str, metadata: ImageMetadata, is_animation: bool = False) -> frozenset[MetadataKind]:
    """Returns the kinds of metadata a save as `file_format` writes, when `metadata` is what's saved.

    `is_animation` selects the rules of a multi-frame save. GIF and JPEG 2000 have one comment slot, which holds the
    parameters if `metadata` has any and the comment otherwise.
    """
    name = format_name(file_format)
    if not format_keeps_metadata(name):
        return frozenset()
    if is_animation:
        return _ANIMATION_KINDS.get(name, frozenset())
    parameters_or_comment = MetadataKind.PARAMETERS if metadata.parameters is not None else MetadataKind.COMMENT
    if name in _PNG_FORMATS:
        return _PNG_KINDS
    if name == 'ORA':
        return _ORA_KINDS
    if name in _COMMENT_ONLY_FORMATS:
        return frozenset({parameters_or_comment})
    if name in _COMMENT_EXIF_FORMATS:
        return frozenset({parameters_or_comment, MetadataKind.EXIF})
    if name == 'JPEG':
        return _JPEG_KINDS
    return _EXIF_XMP_KINDS


class MetadataSplit(NamedTuple):
    """What a save keeps and drops of an image's metadata."""
    kept: list[MetadataPart]
    dropped: list[MetadataPart]


def split_metadata(metadata: ImageMetadata, file_format: str, is_animation: bool = False,
                   ignored: Optional[frozenset[MetadataKind]] = None) -> MetadataSplit:
    """Sorts the metadata `metadata` carries into what a save as `file_format` keeps and drops.

    Kinds in `ignored` are left out of both lists.
    """
    kept_set = kept_kinds(file_format, metadata, is_animation)
    split = MetadataSplit([], [])
    for part in metadata_parts(metadata):
        if ignored is not None and part.kind in ignored:
            continue
        (split.kept if part.kind in kept_set else split.dropped).append(part)
    return split
