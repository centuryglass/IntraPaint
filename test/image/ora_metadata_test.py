"""Tests that .ora files keep every part of `ImageMetadata`, where `src/image/ora_metadata.py` puts each one."""
import json
import os
import sys
import tempfile
import zipfile
from typing import Optional
from xml.etree.ElementTree import fromstring, tostring

from PIL import ExifTags
from PIL.ExifTags import IFD
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from src.image.image_metadata import ImageMetadata, XMP_TEXT_KEY, COMMENT_KEY
from src.image.layers.image_stack import ImageStack
from src.image.open_raster import (save_ora_image, read_ora_image, MIMETYPE_FILE_NAME, XML_FILE_NAME,
                                   EXTENDED_DATA_XML_FILE_NAME, METADATA_TAG)
from src.image.ora_extensions import DocumentExtension, register_document_extension, METADATA_EXTENSION_NAME
from src.image.ora_metadata import XMP_ARCHIVE_PATH, EXIF_ARCHIVE_PATH, IPTC_ARCHIVE_PATH, decode_dpi
from src.util.visual.image_format_utils import load_image, save_image_with_metadata
from test.base_test_case import IntraPaintTestCase
from test.image.image_metadata_test import photo_metadata, PHOTO_XMP, _exif

app = QApplication.instance() or QApplication(sys.argv)

IMG_SIZE = QSize(16, 16)

# An XMP packet shaped like picrew-downloader's, one of the proposal's example writers: no x:xmpmeta wrapper, and
# namespaces declared on each property. The photoshop:City property is a place field.
BARE_RDF_XMP = ("<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?><rdf:RDF "
                "xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'><rdf:Description rdf:about=''>"
                "<exif:UserComment xmlns:exif='http://ns.adobe.com/exif/1.0/'><rdf:Alt>"
                "<rdf:li xml:lang='x-default' xml:space='preserve'><![CDATA[a café maker]]></rdf:li></rdf:Alt>"
                "</exif:UserComment><photoshop:City xmlns:photoshop='http://ns.adobe.com/photoshop/1.0/'>"
                "Springfield</photoshop:City></rdf:Description></rdf:RDF><?xpacket end='r'?>").encode()


def _archive(path: str) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def _rewrite_archive(path: str, replaced: dict[str, Optional[bytes]]) -> None:
    """Rewrites an archive with some members replaced, added, or removed when their value is None."""
    with zipfile.ZipFile(path) as archive:
        members = [(info, archive.read(info)) for info in archive.infolist()]
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_STORED) as archive:
        for info, data in members:
            if info.filename not in replaced:
                archive.writestr(info, data)
        for name, data in replaced.items():
            if data is not None:
                archive.writestr(name, data)


class OraMetadataTest(IntraPaintTestCase):
    """Tests where .ora saves put each part of the metadata, and that loads read them all back."""

    def setUp(self) -> None:
        super().setUp()
        self._temp_dir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.image_stack = ImageStack(IMG_SIZE, IMG_SIZE, IMG_SIZE, IMG_SIZE)
        image = QImage(IMG_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor(20, 120, 220))
        self.image_stack.load_image(image)
        self.loaded_stack = ImageStack(IMG_SIZE, IMG_SIZE, IMG_SIZE, IMG_SIZE)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()
        super().tearDown()

    def _path(self, name: str) -> str:
        return os.path.join(self._temp_dir.name, name)

    def _save(self, metadata: Optional[ImageMetadata], name: str = 'saved.ora') -> str:
        path = self._path(name)
        save_ora_image(self.image_stack, path, metadata)
        return path

    def _assert_metadata_matches(self, expected: ImageMetadata, actual: ImageMetadata) -> None:
        self.assertEqual(expected.text, actual.text)
        self.assertEqual(expected.exif_entries(), actual.exif_entries())
        self.assertEqual(expected.xmp_packet, actual.xmp_packet)
        self.assertEqual(expected.iptc_data, actual.iptc_data)

    def test_round_trip_keeps_every_part(self) -> None:
        """Text entries, EXIF tags in every IFD, the XMP packet, IPTC envelope and application datasets, and the DPI
        all load back from an .ora file."""
        source = photo_metadata()
        source.exif = _exif({None: {ExifTags.Base.Make: 'Camera Co'}, IFD.Exif: {ExifTags.Base.ExposureTime: 0.01},
                             IFD.GPSInfo: {ExifTags.GPS.GPSLatitudeRef: 'N'}})
        self.assertEqual({None, IFD.Exif, IFD.GPSInfo}, {entry.ifd for entry in source.exif_entries()})
        source.format_info['dpi'] = (300, 300)
        loaded = read_ora_image(self.loaded_stack, self._save(source))
        self._assert_metadata_matches(source, loaded)
        self.assertEqual((300, 300), loaded.format_info['dpi'])
        self.assertEqual(['market', 'Springfield', 'café'], [entry.value for entry in loaded.iptc_entries()])

    def test_archive_layout(self) -> None:
        """The XMP packet is `META-INF/metadata.xml` byte for byte, with no root `meta.xml` hiding it from exiftool,
        and the extension element names the EXIF and IPTC files."""
        source = photo_metadata()
        source.format_info['dpi'] = (72.4, 96)
        path = self._save(source)
        files = _archive(path)
        with zipfile.ZipFile(path) as archive:
            self.assertEqual(MIMETYPE_FILE_NAME, archive.namelist()[0])
            self.assertEqual(zipfile.ZIP_STORED, archive.getinfo(XMP_ARCHIVE_PATH).compress_type)
        self.assertEqual(PHOTO_XMP, files[XMP_ARCHIVE_PATH])
        self.assertNotIn('meta.xml', files)
        self.assertEqual(source.iptc_data, files[IPTC_ARCHIVE_PATH])
        self.assertIn(EXIF_ARCHIVE_PATH, files)
        extended_root = fromstring(files[EXTENDED_DATA_XML_FILE_NAME])
        self.assertEqual({COMMENT_KEY: 'a camera note'}, json.loads(extended_root.get(METADATA_TAG, '')))
        payloads = [element.text for element in extended_root if element.get('name') == METADATA_EXTENSION_NAME]
        self.assertEqual([{'exif': EXIF_ARCHIVE_PATH, 'iptc': IPTC_ARCHIVE_PATH}],
                         [json.loads(payload or '') for payload in payloads])
        image_root = fromstring(files[XML_FILE_NAME])
        self.assertEqual(('72', '96'), (image_root.get('xres'), image_root.get('yres')))

    def test_no_metadata_writes_no_metadata_files(self) -> None:
        """Without metadata, or after Remove all, a save writes no metadata files, element or resolution."""
        removed = photo_metadata()
        removed.remove_all()
        for name, metadata in (('none.ora', None), ('empty.ora', ImageMetadata()), ('removed.ora', removed)):
            with self.subTest(name=name):
                files = _archive(self._save(metadata, name))
                self.assertEqual(set(), {XMP_ARCHIVE_PATH, EXIF_ARCHIVE_PATH, IPTC_ARCHIVE_PATH} & set(files))
                extended_root = fromstring(files[EXTENDED_DATA_XML_FILE_NAME])
                self.assertIsNone(extended_root.get(METADATA_TAG))
                self.assertEqual([], [element for element in extended_root if element.tag == 'extension'])
                self.assertIsNone(fromstring(files[XML_FILE_NAME]).get('xres'))
                self.assertTrue(read_ora_image(self.loaded_stack, self._path(name)).is_empty)

    def test_reads_another_programs_xmp_packet(self) -> None:
        """A packet another program wrote to `META-INF/metadata.xml` loads as the XMP packet, its place fields can be
        found, and a save writes it back once and unchanged."""
        path = self._save(None, 'other.ora')
        _rewrite_archive(path, {XMP_ARCHIVE_PATH: BARE_RDF_XMP})
        loaded = read_ora_image(self.loaded_stack, path)
        self.assertEqual(BARE_RDF_XMP, loaded.xmp_packet)
        self.assertTrue(loaded.has_location_data)
        resaved = self._save(loaded, 'resaved.ora')
        with zipfile.ZipFile(resaved) as archive:
            self.assertEqual(1, archive.namelist().count(XMP_ARCHIVE_PATH))
            self.assertEqual(BARE_RDF_XMP, archive.read(XMP_ARCHIVE_PATH))
        loaded.remove_location()
        self.assertFalse(read_ora_image(self.loaded_stack, self._save(loaded, 'no_location.ora')).has_location_data)

    def test_xmp_text_entry_from_older_files(self) -> None:
        """An XMP text entry in the JSON of a file with no `META-INF/metadata.xml` still loads, and when both exist
        the packet file's content wins."""
        path = self._save(ImageMetadata({XMP_TEXT_KEY: '<old/>'}))
        _rewrite_archive(path, {XMP_ARCHIVE_PATH: None})
        self.assertEqual(b'<old/>', read_ora_image(self.loaded_stack, path).xmp_packet)
        _rewrite_archive(path, {XMP_ARCHIVE_PATH: b'<new/>'})
        loaded = read_ora_image(self.loaded_stack, path)
        self.assertEqual({XMP_TEXT_KEY: '<new/>'}, loaded.text)

    def test_damaged_metadata_files_are_skipped(self) -> None:
        """Unreadable EXIF data, a missing file, an unsafe path or an unreadable payload leaves out only that part."""
        source = photo_metadata()
        path = self._save(source)
        _rewrite_archive(path, {EXIF_ARCHIVE_PATH: b'not exif'})
        loaded = read_ora_image(self.loaded_stack, path)
        self.assertEqual([], loaded.exif_entries())
        self.assertEqual(source.iptc_data, loaded.iptc_data)
        _rewrite_archive(path, {IPTC_ARCHIVE_PATH: None})
        self.assertIsNone(read_ora_image(self.loaded_stack, path).iptc_data)

        original_extended = _archive(path)[EXTENDED_DATA_XML_FILE_NAME]
        for payload in ('not json', json.dumps(['a list']), json.dumps({'iptc': '../outside.bin', 'exif': 7})):
            with self.subTest(payload=payload):
                extended_root = fromstring(original_extended)
                for element in extended_root:
                    if element.get('name') == METADATA_EXTENSION_NAME:
                        element.text = payload
                _rewrite_archive(path, {EXTENDED_DATA_XML_FILE_NAME: tostring(extended_root)})
                loaded = read_ora_image(self.loaded_stack, path)
                self.assertEqual(source.text, loaded.text)
                self.assertEqual(PHOTO_XMP, loaded.xmp_packet)
                self.assertEqual([], loaded.exif_entries())
                self.assertIsNone(loaded.iptc_data)

    def test_decode_dpi(self) -> None:
        """`xres` and `yres` load as DPI, one standing in for the other when it's missing or invalid."""
        self.assertEqual((300, 150), decode_dpi('300', '150'))
        self.assertEqual((72.5, 72.5), decode_dpi('72.5', None))
        self.assertEqual((96, 96), decode_dpi('nan', '96'))
        self.assertIsNone(decode_dpi('0', '-1'))
        self.assertIsNone(decode_dpi(None, None))

    def test_metadata_extension_name_is_reserved(self) -> None:
        """No document extension can take the name the metadata files are stored under."""
        with self.assertRaises(ValueError):
            register_document_extension(DocumentExtension(METADATA_EXTENSION_NAME, lambda _stack, _context: None,
                                                          lambda _stack, _payload, _context: None))

    def test_jpeg_through_ora_matches_direct_jpeg_save(self) -> None:
        """A JPEG with a comment, XMP, IPTC and GPS tags, saved as .ora, reopened and saved as JPEG, keeps the same
        metadata as a JPEG saved directly from the original."""
        photo_path = self._path('photo.jpg')
        save_image_with_metadata(self.image_stack.qimage(True), photo_path, photo_metadata())
        photo_image, photo = load_image(photo_path)
        direct_path = self._path('direct.jpg')
        save_image_with_metadata(photo_image, direct_path, photo)

        self.image_stack.load_image(photo_image)
        reopened = read_ora_image(self.loaded_stack, self._save(photo))
        through_ora_path = self._path('through_ora.jpg')
        save_image_with_metadata(self.loaded_stack.qimage(True), through_ora_path, reopened)

        _, direct = load_image(direct_path)
        _, through_ora = load_image(through_ora_path)
        self._assert_metadata_matches(direct, through_ora)
        self.assertEqual(direct.iptc_entries(), through_ora.iptc_entries())
        self.assertIn(IFD.GPSInfo, [entry.ifd for entry in through_ora.exif_entries()])
        self.assertEqual({COMMENT_KEY: 'a camera note'}, through_ora.text)
