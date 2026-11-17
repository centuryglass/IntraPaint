"""Data from another program's .ora file that IntraPaint carries through a load and save without interpreting it.

`open_raster` captures these records on load and re-emits them on save; nothing else reads them. Foreign data is
preserved, never parsed or upgraded: unknown attributes, elements and files are written back as they were read.

A layer's record describes the pixels it was loaded with. When the layer's pixels or transform change, `open_raster`
drops the record's attributes, elements and files on save, because other programs may rebuild the layer from them and
discard the edits (MyPaint rebuilds a background layer from `mypaint:background-tile`, ignoring its PNG). An
unrecognized composite op is kept either way.
"""
import copy
import hashlib
from dataclasses import dataclass, field
from typing import Optional
from xml.etree.ElementTree import Element

from PySide6.QtGui import QImage, QTransform


@dataclass(frozen=True)
class OraArchiveFile:
    """One archive member's content, with the zip settings it was stored with."""

    data: bytes
    compress_type: int
    date_time: tuple[int, int, int, int, int, int]


@dataclass
class OraForeignLayerData:
    """What a `<layer>` or `<stack>` element held that IntraPaint doesn't model, stored as `Layer.ora_foreign_data`.

    `Layer.copy` doesn't copy it, so each record has one owner and its `src` path and files are written once.
    """

    src: Optional[str] = None
    """The `<layer>` element's archive path, normalized to '/' separators. None for a stack."""

    source: Optional[OraArchiveFile] = None
    """The `src` file, kept only when it isn't a PNG (MyPaint's SVG layers). Written back in place of a PNG while the
    layer is unedited."""

    attributes: dict[str, str] = field(default_factory=dict)
    """Unrecognized attributes, keyed by ElementTree's `{namespace}name` form, in document order."""

    elements: list[tuple[int, Element]] = field(default_factory=list)
    """Unrecognized child elements with their index among the element's children. Never evaluated."""

    composite_op: Optional[str] = None
    """The `composite-op` value, when IntraPaint doesn't support it and loaded the layer as Normal."""

    files: dict[str, OraArchiveFile] = field(default_factory=dict)
    """Archive files named by a value in `attributes` (MyPaint's strokemaps), keyed by archive path."""

    fingerprint: Optional[bytes] = None
    """Hash of the pixels and transform the layer was loaded with, from `pixel_fingerprint`. None for a stack."""

    def copy_elements(self) -> list[tuple[int, Element]]:
        """Returns deep copies of `elements`, so writing them can't change the stored ones."""
        return [(index, copy.deepcopy(element)) for index, element in self.elements]


@dataclass
class OraForeignDocumentData:
    """What a loaded .ora file held outside its layers that IntraPaint doesn't model, stored as
    `ImageStack.ora_foreign_data`. Loading any image replaces it."""

    image_attributes: dict[str, str] = field(default_factory=dict)
    """Unrecognized `<image>` attributes (Krita's `xres`, MyPaint's `mypaint:*`), keyed as in
    `OraForeignLayerData.attributes`."""

    image_elements: list[tuple[int, Element]] = field(default_factory=list)
    """Unrecognized `<image>` children, with their index among its children."""

    root: OraForeignLayerData = field(default_factory=OraForeignLayerData)
    """The root `<stack>`'s record. The loaded root group's own record is lost when `ImageStack.load_layer_stack` moves
    its children, so it lives here."""

    files: dict[str, OraArchiveFile] = field(default_factory=dict)
    """Archive files that no layer, IntraPaint extension or required ORA entry uses, keyed by archive path."""

    namespaces: dict[str, str] = field(default_factory=dict)
    """Namespace prefixes declared in `stack.xml`, so saved files keep names like `mypaint:` instead of `ns0:`."""


def pixel_fingerprint(image: QImage, transform: QTransform) -> bytes:
    """Returns a hash that changes when the image's pixels or the transform change."""
    digest = hashlib.blake2b(digest_size=16)
    digest.update(f'{image.width()},{image.height()},{image.format()},{image.bytesPerLine()}'.encode())
    if not image.isNull():
        digest.update(image.constBits().tobytes())
    digest.update(','.join(str(value) for value in (
        transform.m11(), transform.m12(), transform.m13(),
        transform.m21(), transform.m22(), transform.m23(),
        transform.m31(), transform.m32(), transform.m33())).encode())
    return digest.digest()
