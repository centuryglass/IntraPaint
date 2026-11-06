"""
The metadata an image file carries, kept per source so a save writes back what a load read.

- `ImageMetadata` holds text entries, EXIF data and read-only format info as separate sources.
- `A1111Parameters` parses and writes the A1111 / Forge `parameters` text without losing fields it doesn't know.
- Read-only views recognize ComfyUI, NovelAI and InvokeAI data and give EXIF tags readable names.

This module imports nothing from `src.config`: `image_format_utils` imports it, and the config classes import
`image_format_utils` through `src.ui.modal.modal_utils`. The mapping from A1111 fields to `Cache` keys lives in
`src/image/metadata_cache_fields.py`.
"""
import copy
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, NamedTuple, Optional

from PIL import Image, ExifTags
from PIL.ExifTags import IFD

logger = logging.getLogger(__name__)

PARAMETERS_KEY = 'parameters'
"""The text entry A1111 / Forge write generation parameters to, and the first place they are looked up."""
COMMENT_KEY = 'comment'
"""The text entry holding a GIF, JPEG or JPEG 2000 comment, the last place generation parameters are looked up."""
XMP_TEXT_KEY = 'XML:com.adobe.xmp'

# Format info keys holding raw blocks that the model shows but doesn't edit or write:
XMP_INFO_KEY = 'xmp'
ICC_PROFILE_INFO_KEY = 'icc_profile'
PHOTOSHOP_INFO_KEY = 'photoshop'
"""PIL's info key for a JPEG's Photoshop resources, a dict from resource id to bytes. One of them holds IPTC data."""
_IPTC_RESOURCE_ID = 0x0404
# An IPTC dataset starts with this tag marker, then its record number, dataset number and a 2-byte length:
_IPTC_TAG_MARKER = 0x1C
_IPTC_HEADER_SIZE = 5
_IPTC_EXTENDED_LENGTH_FLAG = 0x8000
_IPTC_APPLICATION_RECORD = 2
_IPTC_RECORD_VERSION_DATASET = 0
# Readable names for the IPTC application record datasets that photo tools commonly write:
IPTC_DATASET_NAMES = {
    5: 'Object Name', 7: 'Edit Status', 10: 'Urgency', 15: 'Category', 20: 'Supplemental Category',
    25: 'Keywords', 40: 'Special Instructions', 55: 'Date Created', 60: 'Time Created', 62: 'Digital Creation Date',
    63: 'Digital Creation Time', 65: 'Originating Program', 70: 'Program Version', 80: 'By-line',
    85: 'By-line Title', 90: 'City', 92: 'Sub-location', 95: 'Province/State', 100: 'Country Code',
    101: 'Country', 103: 'Original Transmission Reference', 105: 'Headline', 110: 'Credit', 115: 'Source',
    116: 'Copyright Notice', 118: 'Contact', 120: 'Caption/Abstract', 122: 'Writer/Editor'
}
# PIL's info key for encoded EXIF data, which loads into `ImageMetadata.exif`:
_EXIF_INFO_KEY = 'exif'
# Format info keys that `ImageMetadata.remove_all` removes:
_REMOVABLE_INFO_KEYS = (XMP_INFO_KEY, ICC_PROFILE_INFO_KEY, PHOTOSHOP_INFO_KEY, _EXIF_INFO_KEY)
# Keys an .ora metadata attribute may hold that are binary data, not text entries:
_BINARY_INFO_KEYS = frozenset({_EXIF_INFO_KEY, ICC_PROFILE_INFO_KEY, XMP_INFO_KEY})

# EXIF text tags that can be edited. Any other tag can only be viewed or removed:
EDITABLE_EXIF_TEXT_TAGS = frozenset({ExifTags.Base.ImageDescription, ExifTags.Base.Artist, ExifTags.Base.Copyright,
                                     ExifTags.Base.Software, ExifTags.Base.UserComment})
# Tags that point to sub-IFDs, which are listed through those IFDs. The Interop pointer is in the Exif IFD, the others
# in IFD0:
_IFD_POINTER_TAGS = frozenset({IFD.Exif, IFD.GPSInfo, IFD.Interop})
_IFD0_POINTER_TAGS = frozenset({IFD.Exif, IFD.GPSInfo})

# UserComment starts with an 8-byte header naming its encoding:
_USER_COMMENT_HEADER_SIZE = 8
_USER_COMMENT_UNICODE = b'UNICODE\0'
_USER_COMMENT_ASCII = b'ASCII\0\0\0'
_USER_COMMENT_JIS = b'JIS\0\0\0\0\0'
_UTF_16_BE = 'utf-16-be'
_UTF_16_LE = 'utf-16-le'

# Sources of structured data that `ImageMetadata.structured_data` recognizes:
SOURCE_COMFYUI = 'ComfyUI'
SOURCE_NOVELAI = 'NovelAI'
SOURCE_INVOKEAI = 'InvokeAI'
_STRUCTURED_TEXT_KEYS = {
    'prompt': SOURCE_COMFYUI,
    'workflow': SOURCE_COMFYUI,
    'Comment': SOURCE_NOVELAI,
    'invokeai_metadata': SOURCE_INVOKEAI
}
COMFYUI_PROMPT_KEY = 'prompt'


def _decode_text(value: Any) -> Optional[str]:
    """Returns a text value as a string, decoding bytes as UTF-8, or Latin-1 if they aren't valid UTF-8."""
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        try:
            return value.decode('utf-8')
        except UnicodeDecodeError:
            return value.decode('latin-1')
    return None


def decode_exif_text(value: Any) -> Any:
    """Returns an EXIF ASCII tag's value with UTF-8 text decoded, and any other value unchanged.

    Many programs write UTF-8 to ASCII tags. PIL decodes them as Latin-1, so "\u00a9" reads as "\u00c2\u00a9", and
    re-decoding as UTF-8 recovers the text. A string that isn't UTF-8 read as Latin-1 is returned unchanged.
    """
    if isinstance(value, bytes):
        return _decode_text(value.rstrip(b'\0'))
    if not isinstance(value, str) or value.isascii():
        return value
    try:
        return value.encode('latin-1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


def decode_user_comment(raw: Any) -> tuple[Optional[str], Optional[str]]:
    """Decodes an EXIF UserComment, returning its text and the Python codec it used.

    The value starts with an 8-byte header naming the encoding, which PIL leaves in the raw bytes. A UNICODE comment is
    UTF-16 in either byte order: A1111 writes big-endian, and the EXIF standard follows the file's byte order. Returns
    `(None, None)` when the value isn't text.
    """
    if isinstance(raw, str):
        return raw.rstrip('\0'), None
    if not isinstance(raw, bytes):
        return None, None
    header = raw[:_USER_COMMENT_HEADER_SIZE]
    body = raw[_USER_COMMENT_HEADER_SIZE:]
    if header == _USER_COMMENT_UNICODE:
        if body.startswith(b'\xfe\xff'):
            encoding, body = _UTF_16_BE, body[2:]
        elif body.startswith(b'\xff\xfe'):
            encoding, body = _UTF_16_LE, body[2:]
        else:
            # Mostly-ASCII UTF-16 text has its zero bytes at even offsets when big-endian, odd ones when little-endian:
            even_zeros = body[0::2].count(0)
            odd_zeros = body[1::2].count(0)
            encoding = _UTF_16_BE if even_zeros >= odd_zeros else _UTF_16_LE
        if len(body) % 2 != 0:
            body = body[:-1]
        return body.decode(encoding, errors='replace').rstrip('\0'), encoding
    if header == _USER_COMMENT_ASCII:
        return body.decode('ascii', errors='replace').rstrip('\0'), 'ascii'
    if header == _USER_COMMENT_JIS:
        return body.decode('shift_jis', errors='replace').rstrip('\0'), 'shift_jis'
    if header == b'\0' * _USER_COMMENT_HEADER_SIZE:
        return _decode_text(body.rstrip(b'\0')), None
    return _decode_text(raw.rstrip(b'\0')), None


def encode_user_comment(text: str, encoding: Optional[str] = None) -> bytes:
    """Encodes text as an EXIF UserComment, as UTF-16 unless `encoding` names the codec of the comment it replaces.

    UTF-16 is big-endian unless `encoding` is little-endian, matching what A1111 writes and reads.
    """
    if encoding == 'ascii' and text.isascii():
        return _USER_COMMENT_ASCII + text.encode('ascii')
    if encoding == _UTF_16_LE:
        return _USER_COMMENT_UNICODE + text.encode(_UTF_16_LE)
    return _USER_COMMENT_UNICODE + text.encode(_UTF_16_BE)


class ExifEntry(NamedTuple):
    """One EXIF tag, with its readable name and decoded value.

    `ifd` is None for the main IFD (IFD0), or the `PIL.ExifTags.IFD` that holds the tag.
    """
    ifd: Optional[int]
    tag: int
    name: str
    value: Any
    editable: bool


class IptcEntry(NamedTuple):
    """One IPTC (IIM) dataset, which the model shows but doesn't edit or write."""
    record: int
    dataset: int
    name: str
    value: str


def parse_iptc(data: bytes) -> list[IptcEntry]:
    """Parses IPTC (IIM) datasets, stopping at the first byte that doesn't start one.

    Application record datasets get readable names. Values decode as UTF-8, or Latin-1 if they aren't valid UTF-8.
    """
    entries: list[IptcEntry] = []
    offset = 0
    while offset + _IPTC_HEADER_SIZE <= len(data) and data[offset] == _IPTC_TAG_MARKER:
        record = data[offset + 1]
        dataset = data[offset + 2]
        length = int.from_bytes(data[offset + 3:offset + 5], 'big')
        offset += _IPTC_HEADER_SIZE
        if length & _IPTC_EXTENDED_LENGTH_FLAG:
            length_size = length & ~_IPTC_EXTENDED_LENGTH_FLAG
            length = int.from_bytes(data[offset:offset + length_size], 'big')
            offset += length_size
        value = data[offset:offset + length]
        offset += length
        name = IPTC_DATASET_NAMES.get(dataset) if record == _IPTC_APPLICATION_RECORD else None
        entries.append(IptcEntry(record, dataset, name or f'{record}:{dataset}', _decode_text(value) or ''))
    return entries


class StructuredData(NamedTuple):
    """A text entry recognized as another program's JSON data, which the model shows but doesn't edit."""
    source: str
    key: str
    data: Any
    text: str
    """`data` as indented JSON."""


class ComfyUINode(NamedTuple):
    """One node of a ComfyUI API-format prompt."""
    node_id: str
    class_type: str
    inputs: dict[str, Any]


class ImageMetadata:
    """The metadata of one image, kept per source: text entries, EXIF data, and read-only format info.

    - `text` holds PNG text chunks, or a GIF / JPEG comment, in file order. PNG saves write every entry. Other formats
      keep only the generation parameters, see `save_image_with_metadata`.
    - `exif` holds EXIF data, including the Exif and GPS sub-IFDs. `Image.Exif.get_ifd` adds an empty IFD for a missing
      one, which a save then writes, so code reading `exif` goes through `exif_entries` or `_read_ifd`.
    - `format_info` holds PIL's other info entries: animation loop counts, DPI, raw XMP and ICC profile data. Nothing
      in it is written back as metadata.
    """

    def __init__(self, text: Optional[dict[str, str]] = None, exif: Optional[Image.Exif] = None,
                 format_info: Optional[dict[str, Any]] = None) -> None:
        self.text: dict[str, str] = {} if text is None else text
        self.exif: Image.Exif = Image.Exif() if exif is None else exif
        self.format_info: dict[str, Any] = {} if format_info is None else format_info

    @classmethod
    def from_pil_image(cls, image: Image.Image) -> 'ImageMetadata':
        """Reads the metadata of an open PIL image. A PNG's text chunks make the image load."""
        text: dict[str, str] = {}
        if image.format == 'PNG':
            for key, value in getattr(image, 'text', {}).items():
                decoded = _decode_text(value)
                if decoded is not None:
                    text[key] = decoded
        format_info: dict[str, Any] = {}
        for key, value in image.info.items():
            if key in text or key == _EXIF_INFO_KEY:
                continue
            if key == COMMENT_KEY:
                comment = _decode_text(value)
                if comment is not None:
                    text[COMMENT_KEY] = comment
                    continue
            format_info[key] = value
        return ImageMetadata(text, image.getexif(), format_info)

    @classmethod
    def from_ora_json(cls, metadata_json: Optional[str], exif_bytes: Optional[bytes] = None) -> 'ImageMetadata':
        """Reads the text entries an .ora file's metadata attribute holds, with optional encoded EXIF data.

        Files written before this model hold the whole PIL info dict, so string values become text entries and
        anything else becomes format info.
        """
        metadata = ImageMetadata()
        if exif_bytes is not None:
            metadata.exif.load(exif_bytes)
        if metadata_json is None or metadata_json == '':
            return metadata
        try:
            entries = json.loads(metadata_json)
        except json.JSONDecodeError as err:
            logger.error(f'Ignoring unreadable .ora metadata: {err}')
            return metadata
        if not isinstance(entries, dict):
            return metadata
        for key, value in entries.items():
            if isinstance(value, str) and key not in _BINARY_INFO_KEYS:
                metadata.text[key] = value
            elif value is not None:
                metadata.format_info[key] = value
        return metadata

    def to_ora_json(self) -> Optional[str]:
        """Returns the text entries as the JSON an .ora metadata attribute holds, or None if there are none."""
        if len(self.text) == 0:
            return None
        return json.dumps(self.text)

    def copy(self) -> 'ImageMetadata':
        """Returns an independent copy, for a save that runs on a worker thread."""
        return copy.deepcopy(self)

    @property
    def is_empty(self) -> bool:
        """Whether there are no text entries, EXIF tags or format info."""
        return len(self.text) == 0 and len(self.exif_entries()) == 0 and len(self.format_info) == 0

    @property
    def has_removable_data(self) -> bool:
        """Whether `remove_all` would remove anything. Format info such as DPI doesn't count."""
        return (len(self.text) > 0 or len(self.exif_entries()) > 0
                or any(self.format_info.get(key) is not None for key in _REMOVABLE_INFO_KEYS))

    def remove_all(self) -> None:
        """Removes every text entry, EXIF tag, and the XMP, IPTC and ICC profile blocks. Other format info is kept."""
        self.text.clear()
        self.exif = Image.Exif()
        for key in _REMOVABLE_INFO_KEYS:
            self.format_info.pop(key, None)

    # Generation parameters:

    def _exif_description(self) -> Optional[str]:
        """Returns the EXIF ImageDescription from IFD0, or else the Exif IFD, where IntraPaint 1.4 also wrote it."""
        description = self.exif.get(ExifTags.Base.ImageDescription)
        if description is None:
            description = self._read_ifd(IFD.Exif).get(ExifTags.Base.ImageDescription)
        decoded = decode_exif_text(description)
        return decoded if isinstance(decoded, str) else None

    def _user_comment(self) -> tuple[Optional[str], Optional[str]]:
        raw = self._read_ifd(IFD.Exif).get(ExifTags.Base.UserComment)
        return (None, None) if raw is None else decode_user_comment(raw)

    @property
    def parameters(self) -> Optional[str]:
        """Returns the generation parameters text, or None if the image has none.

        Looked up in the `parameters` text entry, then EXIF UserComment (A1111's JPEG, WebP and AVIF location), then
        EXIF ImageDescription, then the comment. Empty values are skipped. Text from any source but `parameters`
        counts only if it has an A1111 `Key: value` line, so a camera caption or comment isn't read as a prompt.
        """
        text_parameters = self.text.get(PARAMETERS_KEY)
        if text_parameters is not None and text_parameters != '':
            return text_parameters
        user_comment, _ = self._user_comment()
        for candidate in (user_comment, self._exif_description(), self.text.get(COMMENT_KEY)):
            if candidate is not None and candidate != '' and A1111Parameters.parse(candidate).has_generation_fields:
                return candidate
        return None

    def set_parameters(self, parameters: str) -> None:
        """Replaces the generation parameters text.

        Writes the `parameters` text entry, and every other source that held the previous text, so the lookup in
        `parameters` finds the new text whichever source it reads first.
        """
        previous = self.parameters
        self.text[PARAMETERS_KEY] = parameters
        if previous is None:
            return
        user_comment, encoding = self._user_comment()
        exif_ifd = self._read_ifd(IFD.Exif)
        if user_comment == previous:
            exif_ifd[ExifTags.Base.UserComment] = encode_user_comment(parameters, encoding)
        description = parameters if parameters.isascii() else parameters.encode('utf-8')
        if decode_exif_text(exif_ifd.get(ExifTags.Base.ImageDescription)) == previous:
            exif_ifd[ExifTags.Base.ImageDescription] = description
        if decode_exif_text(self.exif.get(ExifTags.Base.ImageDescription)) == previous:
            self.exif[ExifTags.Base.ImageDescription] = description
        if self.text.get(COMMENT_KEY) == previous:
            self.text[COMMENT_KEY] = parameters

    def a1111_parameters(self) -> Optional['A1111Parameters']:
        """Returns the generation parameters parsed as A1111 / Forge text, or None if the image has none."""
        parameters = self.parameters
        return None if parameters is None else A1111Parameters.parse(parameters)

    # Read-only raw data:

    @property
    def xmp(self) -> Optional[str]:
        """Returns the XMP packet, from a PNG text chunk or PIL's raw block, or None if there is none."""
        if XMP_TEXT_KEY in self.text:
            return self.text[XMP_TEXT_KEY]
        return _decode_text(self.format_info.get(XMP_INFO_KEY))

    def iptc_entries(self) -> list[IptcEntry]:
        """Returns the IPTC application record datasets of a JPEG's Photoshop resources, in file order.

        Envelope records and the record version dataset describe the encoding, not the image, and are left out.
        """
        resources = self.format_info.get(PHOTOSHOP_INFO_KEY)
        if not isinstance(resources, dict):
            return []
        data = resources.get(_IPTC_RESOURCE_ID)
        if not isinstance(data, bytes):
            return []
        return [entry for entry in parse_iptc(data)
                if entry.record == _IPTC_APPLICATION_RECORD and entry.dataset != _IPTC_RECORD_VERSION_DATASET]

    @property
    def has_icc_profile(self) -> bool:
        """Whether the file had an embedded ICC profile. See `src/util/visual/pil_image_utils.py` for its handling."""
        return self.format_info.get(ICC_PROFILE_INFO_KEY) is not None

    def structured_data(self) -> list[StructuredData]:
        """Returns the text entries recognized as ComfyUI, NovelAI or InvokeAI JSON, in text entry order.

        An entry with a recognized key that isn't valid JSON is left out, and stays a plain text entry.
        """
        found: list[StructuredData] = []
        for key, value in self.text.items():
            source = _STRUCTURED_TEXT_KEYS.get(key)
            if source is None:
                continue
            try:
                data = json.loads(value)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, (dict, list)):
                continue
            found.append(StructuredData(source, key, data, json.dumps(data, indent=2, ensure_ascii=False)))
        return found

    def comfyui_nodes(self) -> list[ComfyUINode]:
        """Returns the nodes of a ComfyUI API-format `prompt` entry, or an empty list if there is none."""
        try:
            prompt = json.loads(self.text.get(COMFYUI_PROMPT_KEY, ''))
        except json.JSONDecodeError:
            return []
        if not isinstance(prompt, dict):
            return []
        nodes: list[ComfyUINode] = []
        for node_id, node in prompt.items():
            if isinstance(node, dict) and isinstance(node.get('class_type'), str):
                inputs = node.get('inputs')
                nodes.append(ComfyUINode(str(node_id), node['class_type'], inputs if isinstance(inputs, dict) else {}))
        return nodes

    # EXIF:

    def exif_entries(self) -> list[ExifEntry]:
        """Lists every EXIF tag in IFD0 and the Exif, GPS and Interop IFDs, with readable names.

        UserComment values are decoded. Tags PIL can't name are named by their hex tag id.
        """
        entries: list[ExifEntry] = []
        sources: list[tuple[Optional[int], dict[int, Any]]] = [(None, dict(self.exif))]
        for ifd in (IFD.Exif, IFD.GPSInfo, IFD.Interop):
            sources.append((ifd, self._read_ifd(ifd)))
        for ifd, tags in sources:
            names = ExifTags.GPSTAGS if ifd == IFD.GPSInfo else ExifTags.TAGS
            for tag, value in tags.items():
                if ifd != IFD.GPSInfo and tag in _IFD_POINTER_TAGS:
                    continue
                if ifd != IFD.GPSInfo and tag == ExifTags.Base.UserComment:
                    value, _ = decode_user_comment(value)
                else:
                    value = decode_exif_text(value)
                editable = ifd != IFD.GPSInfo and tag in EDITABLE_EXIF_TEXT_TAGS
                entries.append(ExifEntry(ifd, tag, names.get(tag, f'0x{tag:04X}'), value, editable))
        return entries

    def _read_ifd(self, ifd: int) -> dict[int, Any]:
        """Returns the tags of a sub-IFD, or an empty dict if it is missing, without adding it to `exif`.

        Changes to a returned IFD's tags are saved, but an IFD missing from `exif` is only added by `_set_tag`.
        """
        if ifd == IFD.Interop:
            if IFD.Interop not in self._read_ifd(IFD.Exif):
                return {}  # get_ifd raises KeyError when the Exif IFD has no Interop pointer.
        elif ifd not in self.exif:
            return {}
        return self.exif.get_ifd(ifd)

    def _set_tag(self, ifd: Optional[int], tag: int, value: Any) -> None:
        """Sets an EXIF tag in IFD0 or a sub-IFD, adding the sub-IFD if it is missing."""
        if ifd is None:
            self.exif[tag] = value
            return
        is_new_ifd = len(self._read_ifd(ifd)) == 0
        self.exif.get_ifd(ifd)[tag] = value
        if is_new_ifd:
            # Re-reading the encoded data adds the new IFD's pointer, so `_read_ifd` finds it:
            exif = Image.Exif()
            exif.load(self.exif.tobytes())
            self.exif = exif

    def set_exif_text(self, ifd: Optional[int], tag: int, value: str) -> None:
        """Sets an editable EXIF text tag. Raises ValueError for a tag not in `EDITABLE_EXIF_TEXT_TAGS`.

        Non-ASCII text is stored as UTF-8 bytes, which PIL writes unchanged. PIL replaces non-ASCII characters in a
        string with "?".
        """
        if tag not in EDITABLE_EXIF_TEXT_TAGS or ifd == IFD.GPSInfo:
            raise ValueError(f'EXIF tag 0x{tag:04X} is not an editable text tag')
        current = self.exif.get(tag) if ifd is None else self._read_ifd(ifd).get(tag)
        if tag == ExifTags.Base.UserComment:
            _, encoding = decode_user_comment(current)
            self._set_tag(ifd, tag, encode_user_comment(value, encoding))
        else:
            self._set_tag(ifd, tag, value if value.isascii() else value.encode('utf-8'))

    def remove_exif_tag(self, ifd: Optional[int], tag: int) -> None:
        """Removes one EXIF tag, if present. Removing an IFD pointer tag from IFD0 removes that IFD."""
        if ifd is None and tag in _IFD0_POINTER_TAGS:
            self._remove_ifd(tag)
            return
        tags = self.exif if ifd is None else self._read_ifd(ifd)
        if tag in tags:
            del tags[tag]

    def remove_gps(self) -> None:
        """Removes the GPS IFD, and with it every location tag."""
        self._remove_ifd(IFD.GPSInfo)

    def _remove_ifd(self, ifd: int) -> None:
        """Removes a sub-IFD and its pointer from IFD0.

        `Image.Exif` keeps every IFD that `get_ifd` has read and writes it even after its pointer is deleted, so the
        data is re-read into a fresh `Image.Exif` that hasn't read it, and the pointer deleted there.
        """
        if ifd in self.exif:
            del self.exif[ifd]
        exif = Image.Exif()
        exif.load(self.exif.tobytes())
        if ifd in exif:
            del exif[ifd]
        self.exif = exif


@dataclass
class _ParameterField:
    """One `Key: value` field of an A1111 parameter line, with the exact text around it.

    The field's text is `before + key + ':' + spacing + raw`. `before` holds the comma and space separating it from
    the previous field, `raw` the value as written, quoted or not.
    """
    key: str
    raw: str
    before: str
    spacing: str

    @property
    def value(self) -> str:
        """The value with any quoting removed."""
        if len(self.raw) >= 2 and self.raw.startswith('"') and self.raw.endswith('"'):
            try:
                unquoted = json.loads(self.raw)
                if isinstance(unquoted, str):
                    return unquoted
            except json.JSONDecodeError:
                pass
        return self.raw.strip()


def quote_parameter_value(value: str) -> str:
    """Quotes a parameter value the way A1111 does: as a JSON string if it holds a comma, colon or newline."""
    if ',' not in value and '\n' not in value and ':' not in value:
        return value
    return json.dumps(value, ensure_ascii=False)


# A1111's `Key: value` pattern, with the whitespace around the key captured so the line can be rebuilt exactly:
_PARAMETER_FIELD_PATTERN = re.compile(r'\s*(\w[\w \-/]+):(\s*)("(?:\\.|[^\\"])+"|[^,]*)(?:,|$)')
# A1111 reads the last line as parameters only when it holds at least this many fields:
_MIN_PARAMETER_LINE_FIELDS = 3
_NEGATIVE_PROMPT_PATTERN = re.compile(r'(^|\n)Negative prompt:( ?)')


class A1111Parameters:
    """A1111 / Forge generation parameters: a prompt, an optional `Negative prompt:` line, and a `Key: value` line.

    Parsing keeps the exact text of every part. `serialize` rewrites only what was changed, so an unchanged parse
    returns the text it was given, and an edit leaves every other field's text as it was.
    """

    def __init__(self) -> None:
        self.prompt = ''
        self.negative_prompt: Optional[str] = None
        """The negative prompt, or None if the text has no `Negative prompt:` line."""
        self._fields: list[_ParameterField] = []
        # Separators found by `parse`, reused while the parts around them are present:
        self._negative_prefix = ''
        self._negative_spacing = ' '
        self._fields_prefix = ''
        self._fields_tail = ''  # Text after the last field's value, such as a trailing comma.
        self._trailing = ''

    @classmethod
    def parse(cls, text: str) -> 'A1111Parameters':
        """Parses parameter text. Text that isn't in A1111's format parses as a prompt with no fields."""
        params = A1111Parameters()
        content = text.rstrip()
        params._trailing = text[len(content):]
        last_newline = content.rfind('\n')
        last_line = content[last_newline + 1:]
        matches = list(_PARAMETER_FIELD_PATTERN.finditer(last_line))
        if len(matches) >= _MIN_PARAMETER_LINE_FIELDS:
            body = content[:max(last_newline, 0)]
            params._fields_prefix = '\n' if last_newline >= 0 else ''
            value_end = 0
            for match in matches:
                params._fields.append(_ParameterField(match.group(1), match.group(3),
                                                      last_line[value_end:match.start(1)], match.group(2)))
                value_end = match.end(3)
            params._fields_tail = last_line[value_end:]
        else:
            body = content
        negative_match = _NEGATIVE_PROMPT_PATTERN.search(body)
        if negative_match is None:
            params.prompt = body
        else:
            params.prompt = body[:negative_match.start()]
            params._negative_prefix = negative_match.group(1)
            params._negative_spacing = negative_match.group(2)
            params.negative_prompt = body[negative_match.end():]
        return params

    @property
    def has_generation_fields(self) -> bool:
        """Whether the text has a `Key: value` parameter line, which marks it as generation data."""
        return len(self._fields) > 0

    def keys(self) -> list[str]:
        """Returns the field names in order, excluding the prompt and negative prompt."""
        return [field.key for field in self._fields]

    def items(self) -> list[tuple[str, str]]:
        """Returns the fields in order as `(name, value)` pairs with quoting removed."""
        return [(field.key, field.value) for field in self._fields]

    def _find(self, key: str) -> Optional[_ParameterField]:
        """Returns the last field named `key`, the one A1111 uses when a name repeats."""
        for field in reversed(self._fields):
            if field.key == key:
                return field
        return None

    def get(self, key: str) -> Optional[str]:
        """Returns a field's value with quoting removed, or None if the field is missing."""
        field = self._find(key)
        return None if field is None else field.value

    def set(self, key: str, value: str) -> None:
        """Sets a field's value, quoting it if needed, or appends the field if it is missing.

        Setting a field to the value it already has leaves its text unchanged.
        """
        field = self._find(key)
        if field is None:
            self._fields.append(_ParameterField(key, quote_parameter_value(value),
                                                '' if len(self._fields) == 0 else ', ', ' '))
        elif field.value != value:
            field.raw = quote_parameter_value(value)
            if field.spacing == '':
                field.spacing = ' '

    def remove(self, key: str) -> None:
        """Removes every field named `key`. The next field takes over a removed first field's leading text."""
        for index in range(len(self._fields) - 1, -1, -1):
            if self._fields[index].key == key:
                removed = self._fields.pop(index)
                if index == 0 and len(self._fields) > 0:
                    self._fields[0].before = removed.before
        if len(self._fields) == 0:
            self._fields_tail = ''

    def serialize(self) -> str:
        """Returns the parameters as A1111 text."""
        text = self.prompt
        if self.negative_prompt is not None:
            text += ('\n' if text != '' else self._negative_prefix) + 'Negative prompt:' + self._negative_spacing \
                    + self.negative_prompt
        if len(self._fields) > 0:
            text += '\n' if text != '' else self._fields_prefix
            text += ''.join(f'{field.before}{field.key}:{field.spacing}{field.raw}' for field in self._fields)
            text += self._fields_tail
        return text + self._trailing

    def __str__(self) -> str:
        return self.serialize()
