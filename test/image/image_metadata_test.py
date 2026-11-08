"""Tests for ImageMetadata and A1111Parameters: parsing, detection, EXIF editing and file round-trips."""
import json
import os
import sys
import tempfile
from typing import Any, Optional

from PIL import Image, ExifTags, PngImagePlugin
from PIL.ExifTags import IFD
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication

from src.image.image_metadata import A1111Parameters, ImageMetadata, PARAMETERS_KEY, COMMENT_KEY, \
    decode_user_comment, encode_user_comment, SOURCE_COMFYUI, SOURCE_NOVELAI, SOURCE_INVOKEAI, ComfyUINode
from src.util.visual.image_format_utils import load_image, save_image_with_metadata
from src.util.visual.image_utils import logger as image_utils_logger
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

FORGE_TEXT = ('masterpiece, a cat <lora:cat_style:0.8>\nsitting on a windowsill\n'
              'Negative prompt: lowres, bad anatomy\nworst quality\n'
              'Steps: 28, Sampler: DPM++ 2M, Schedule type: Karras, CFG scale: 7, Seed: 3141592653, Size: 832x1216, '
              'Model hash: 31e35c80fc, Model: sd_xl_base_1.0, Denoising strength: 0.4, Clip skip: 2, '
              'Lora hashes: "cat_style: 0a1b2c3d4e5f, other: 6a7b8c9d0e1f", Hires upscale: 1.5, '
              'Hires upscaler: R-ESRGAN 4x+, ADetailer model: face_yolov8n.pt, Version: f2.0.1v1.10.1')

PARSER_FIXTURES = {
    'forge': FORGE_TEXT,
    'no negative prompt': 'a dog\nSteps: 20, Sampler: Euler a, CFG scale: 7, Seed: 1, Size: 512x512, Model: sd15',
    'unknown trailing key': 'a dog\nNegative prompt: cat\nSteps: 20, Sampler: Euler, CFG scale: 7, Seed: 1, '
                            'Size: 512x512, My extension: "a: b, c"',
    'old IntraPaint spacing': 'p\nNegative prompt: \nSteps: 30, Sampler: Euler a, CFG scale:9.0, Seed: -1, Size: 512x512',
    'empty prompt': 'Negative prompt: cat\nSteps: 20, Sampler: Euler, CFG scale: 7',
    'fields only': 'Steps: 20, Sampler: Euler, CFG scale: 7',
    'trailing newline and comma': 'a dog\nSteps: 20, Sampler: Euler, CFG scale: 7,\n',
    'not generation data': 'OLYMPUS DIGITAL CAMERA',
}


class A1111ParametersTest(IntraPaintTestCase):
    """Tests the A1111 / Forge parameter parser and serializer."""

    def test_unchanged_parse_round_trips(self) -> None:
        """Every fixture serializes back to identical text."""
        for name, text in PARSER_FIXTURES.items():
            with self.subTest(fixture=name):
                self.assertEqual(text, A1111Parameters.parse(text).serialize())

    def test_parse_forge_text(self) -> None:
        """Multi-line prompts, the negative prompt and every field parse, with quoted commas unquoted."""
        params = A1111Parameters.parse(FORGE_TEXT)
        self.assertEqual('masterpiece, a cat <lora:cat_style:0.8>\nsitting on a windowsill', params.prompt)
        self.assertEqual('lowres, bad anatomy\nworst quality', params.negative_prompt)
        self.assertTrue(params.has_generation_fields)
        self.assertEqual(['Steps', 'Sampler', 'Schedule type', 'CFG scale', 'Seed', 'Size', 'Model hash', 'Model',
                          'Denoising strength', 'Clip skip', 'Lora hashes', 'Hires upscale', 'Hires upscaler',
                          'ADetailer model', 'Version'], params.keys())
        self.assertEqual('cat_style: 0a1b2c3d4e5f, other: 6a7b8c9d0e1f', params.get('Lora hashes'))
        self.assertEqual('R-ESRGAN 4x+', params.get('Hires upscaler'))
        self.assertIsNone(params.get('Missing'))

    def test_missing_negative_prompt(self) -> None:
        params = A1111Parameters.parse(PARSER_FIXTURES['no negative prompt'])
        self.assertEqual('a dog', params.prompt)
        self.assertIsNone(params.negative_prompt)

    def test_text_without_fields_is_a_prompt(self) -> None:
        params = A1111Parameters.parse('a dog\nwith two lines')
        self.assertFalse(params.has_generation_fields)
        self.assertEqual('a dog\nwith two lines', params.prompt)

    def test_edit_one_field_keeps_the_rest(self) -> None:
        """Changing one field rewrites only that field's text."""
        params = A1111Parameters.parse(FORGE_TEXT)
        params.set('Seed', '42')
        self.assertEqual(FORGE_TEXT.replace('Seed: 3141592653', 'Seed: 42'), params.serialize())

    def test_edit_prompts_keeps_fields(self) -> None:
        params = A1111Parameters.parse(FORGE_TEXT)
        params.prompt = 'a dog'
        params.negative_prompt = 'cat'
        expected_fields = FORGE_TEXT[FORGE_TEXT.index('Steps:'):]
        self.assertEqual(f'a dog\nNegative prompt: cat\n{expected_fields}', params.serialize())

    def test_set_quotes_when_needed(self) -> None:
        """Values with commas, colons or newlines are quoted as JSON, and read back unquoted."""
        params = A1111Parameters.parse(PARSER_FIXTURES['no negative prompt'])
        params.set('Lora hashes', 'a: 1, b: 2')
        params.set('Plain', 'value')
        self.assertTrue(params.serialize().endswith(', Lora hashes: "a: 1, b: 2", Plain: value'))
        reparsed = A1111Parameters.parse(params.serialize())
        self.assertEqual('a: 1, b: 2', reparsed.get('Lora hashes'))
        self.assertEqual('value', reparsed.get('Plain'))

    def test_set_same_value_keeps_text(self) -> None:
        """Setting a field to its current value doesn't respace or requote it."""
        text = PARSER_FIXTURES['old IntraPaint spacing']
        params = A1111Parameters.parse(text)
        params.set('CFG scale', '9.0')
        self.assertEqual(text, params.serialize())

    def test_remove_field(self) -> None:
        params = A1111Parameters.parse(PARSER_FIXTURES['no negative prompt'])
        params.remove('Steps')
        params.remove('Model')
        self.assertEqual('a dog\nSampler: Euler a, CFG scale: 7, Seed: 1, Size: 512x512', params.serialize())

    def test_build_from_empty(self) -> None:
        params = A1111Parameters()
        params.prompt = 'p'
        params.negative_prompt = 'n'
        for key, value in (('Steps', '20'), ('Sampler', 'Euler'), ('CFG scale', '7')):
            params.set(key, value)
        self.assertEqual('p\nNegative prompt: n\nSteps: 20, Sampler: Euler, CFG scale: 7', params.serialize())

    def test_negative_prompt_added_to_fields_only_text(self) -> None:
        params = A1111Parameters.parse(PARSER_FIXTURES['fields only'])
        params.negative_prompt = 'n'
        self.assertEqual('Negative prompt: n\nSteps: 20, Sampler: Euler, CFG scale: 7', params.serialize())


class UserCommentTest(IntraPaintTestCase):
    """Tests decoding and encoding the EXIF UserComment encoding header."""

    def test_decode_encodings(self) -> None:
        text = 'a prompt, ünïcode'
        cases = {
            'utf-16-be': b'UNICODE\0' + text.encode('utf-16-be'),
            'utf-16-le': b'UNICODE\0' + text.encode('utf-16-le'),
        }
        for encoding, raw in cases.items():
            with self.subTest(encoding=encoding):
                self.assertEqual((text, encoding), decode_user_comment(raw))
        self.assertEqual(('ascii text', 'ascii'), decode_user_comment(b'ASCII\0\0\0ascii text\0'))
        self.assertEqual(('plain', None), decode_user_comment(b'\0' * 8 + b'plain'))
        self.assertEqual((None, None), decode_user_comment(42))

    def test_encode_keeps_byte_order(self) -> None:
        for encoding in ('utf-16-be', 'utf-16-le'):
            with self.subTest(encoding=encoding):
                self.assertEqual(('text', encoding), decode_user_comment(encode_user_comment('text', encoding)))
        self.assertTrue(encode_user_comment('text').startswith(b'UNICODE\0\0t'))


def _exif(tags: dict[Optional[int], dict[int, Any]]) -> Image.Exif:
    """Returns EXIF data holding `tags` by IFD, None for IFD0, encoded and read back as a loaded file's would be."""
    exif = Image.Exif()
    for ifd, ifd_tags in tags.items():
        target = exif if ifd is None else exif.get_ifd(ifd)
        for tag, value in ifd_tags.items():
            target[tag] = value
    loaded = Image.Exif()
    loaded.load(exif.tobytes())
    return loaded


def _reload_exif(exif: Image.Exif) -> Image.Exif:
    """Returns `exif` encoded and read back, as a saved and reopened file's would be."""
    loaded = Image.Exif()
    loaded.load(exif.tobytes())
    return loaded


PHOTO_XMP = (b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
             b'<rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/"'
             b' xmlns:ps="http://ns.adobe.com/photoshop/1.0/" xmlns:geo="http://ns.adobe.com/exif/1.0/"'
             b' xmlns:iptc="http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/"'
             b' xmlns:ext="http://iptc.org/std/Iptc4xmpExt/2008-02-29/" ps:Country="USA" ps:Credit="Someone">'
             b'<dc:description>Photographed in Paris</dc:description><ps:City>Springfield</ps:City>'
             b'<geo:GPSLatitude>45,30N</geo:GPSLatitude><iptc:Location/>'
             b'<ext:LocationShown><rdf:Bag><rdf:li rdf:parseType="Resource"><ps:City>Elsewhere</ps:City></rdf:li>'
             b'</rdf:Bag></ext:LocationShown></rdf:Description></rdf:RDF></x:xmpmeta>')
PHOTO_XMP_WITHOUT_LOCATION = (
    b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    b'<rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/"'
    b' xmlns:ps="http://ns.adobe.com/photoshop/1.0/" xmlns:geo="http://ns.adobe.com/exif/1.0/"'
    b' xmlns:iptc="http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/"'
    b' xmlns:ext="http://iptc.org/std/Iptc4xmpExt/2008-02-29/" ps:Credit="Someone">'
    b'<dc:description>Photographed in Paris</dc:description></rdf:Description></rdf:RDF></x:xmpmeta>')


def _iptc_dataset(record: int, dataset: int, value: bytes) -> bytes:
    return bytes([0x1C, record, dataset]) + len(value).to_bytes(2, 'big') + value


def _with_jpeg_segment(jpeg: bytes, marker: int, payload: bytes) -> bytes:
    """Returns JPEG data with an APPn segment inserted after the start-of-image marker."""
    return jpeg[:2] + bytes([0xFF, marker]) + (len(payload) + 2).to_bytes(2, 'big') + payload + jpeg[2:]


def _photoshop_iptc_segment(iptc: bytes) -> bytes:
    """Returns an APP13 payload holding `iptc` as a Photoshop IPTC resource, the way photo tools write it."""
    padded = iptc + (b'\0' if len(iptc) % 2 else b'')
    return b'Photoshop 3.0\0' + b'8BIM' + (0x0404).to_bytes(2, 'big') + b'\0\0' \
        + len(iptc).to_bytes(4, 'big') + padded


def _metadata_with_exif() -> ImageMetadata:
    exif = _exif({None: {ExifTags.Base.Make: 'Camera Co', ExifTags.Base.Artist: 'Someone'},
                  IFD.Exif: {ExifTags.Base.ExposureTime: 0.01},
                  IFD.GPSInfo: {ExifTags.GPS.GPSLatitudeRef: 'N', ExifTags.GPS.GPSLatitude: (45.0, 30.0, 0.0)}})
    return ImageMetadata({PARAMETERS_KEY: 'a prompt\nSteps: 1, Sampler: Euler, CFG scale: 7'}, exif)


class ImageMetadataTest(IntraPaintTestCase):
    """Tests parameter lookup, recognized data, EXIF views and edits, and .ora JSON."""

    def test_parameters_lookup_order(self) -> None:
        """Parameters come from the text entry, then UserComment, then ImageDescription, then the comment."""
        fields = '\nSteps: 20, Sampler: Euler a, Seed: 5'
        metadata = ImageMetadata({COMMENT_KEY: 'from comment' + fields})
        self.assertEqual('from comment' + fields, metadata.parameters)
        metadata.set_exif_text(None, ExifTags.Base.ImageDescription, 'from description' + fields)
        self.assertEqual('from description' + fields, metadata.parameters)
        metadata.set_exif_text(IFD.Exif, ExifTags.Base.UserComment, 'from user comment' + fields)
        self.assertEqual('from user comment' + fields, metadata.parameters)
        metadata.text[PARAMETERS_KEY] = 'from text'
        self.assertEqual('from text', metadata.parameters)
        self.assertIsNone(ImageMetadata().parameters)

    def test_captions_are_not_parameters(self) -> None:
        """A description, UserComment or comment without an A1111 field line isn't read as generation parameters."""
        metadata = ImageMetadata({COMMENT_KEY: 'a comment'})
        metadata.set_exif_text(None, ExifTags.Base.ImageDescription, 'OLYMPUS DIGITAL CAMERA')
        metadata.set_exif_text(IFD.Exif, ExifTags.Base.UserComment, 'a user comment')
        self.assertIsNone(metadata.parameters)
        self.assertIsNone(metadata.a1111_parameters())

    def test_set_parameters_updates_every_source(self) -> None:
        """Setting the parameters rewrites each source that held the old text, keeping UserComment's encoding."""
        old = 'old\nSteps: 20, Sampler: Euler a, Seed: 5'
        metadata = ImageMetadata(exif=_exif({None: {ExifTags.Base.ImageDescription: old},
                                             IFD.Exif: {ExifTags.Base.UserComment: encode_user_comment(old,
                                                                                                       'utf-16-le')}}))
        metadata.set_parameters('new')
        self.assertEqual('new', metadata.text[PARAMETERS_KEY])
        self.assertEqual('new', metadata.exif[ExifTags.Base.ImageDescription])
        self.assertEqual(('new', 'utf-16-le'),
                         decode_user_comment(metadata.exif.get_ifd(IFD.Exif)[ExifTags.Base.UserComment]))

    def test_utf8_exif_text(self) -> None:
        """UTF-8 in an ASCII EXIF tag reads as UTF-8, and non-ASCII edits survive an EXIF round trip."""
        metadata = ImageMetadata()
        metadata.exif[ExifTags.Base.Copyright] = '\u00a9 me'.encode('utf-8').decode('latin-1')  # As PIL reads it.
        entry = next(entry for entry in metadata.exif_entries() if entry.tag == ExifTags.Base.Copyright)
        self.assertEqual('\u00a9 me', entry.value)
        metadata.set_exif_text(None, ExifTags.Base.Artist, 'Ren\u00e9')
        reloaded = ImageMetadata(exif=_reload_exif(metadata.exif))
        entry = next(entry for entry in reloaded.exif_entries() if entry.tag == ExifTags.Base.Artist)
        self.assertEqual('Ren\u00e9', entry.value)

    def test_iptc_entries(self) -> None:
        """IPTC datasets in a Photoshop resource block are named, and Remove all removes them."""
        iptc = _iptc_dataset(2, 90, 'Springfield'.encode()) + _iptc_dataset(2, 120, 'caf\u00e9'.encode())
        metadata = ImageMetadata(format_info={'photoshop': {0x0404: iptc}})
        self.assertEqual([('City', 'Springfield'), ('Caption/Abstract', 'caf\u00e9')],
                         [(entry.name, entry.value) for entry in metadata.iptc_entries()])
        self.assertTrue(metadata.has_removable_data)
        metadata.remove_all()
        self.assertEqual([], metadata.iptc_entries())
        self.assertFalse(metadata.has_removable_data)

    def test_has_removable_data_ignores_format_info(self) -> None:
        """DPI and other format info aren't removable metadata."""
        self.assertFalse(ImageMetadata(format_info={'dpi': (72, 72)}).has_removable_data)
        self.assertTrue(ImageMetadata({'a': 'b'}).has_removable_data)

    def test_set_parameters_leaves_unrelated_sources(self) -> None:
        metadata = ImageMetadata({PARAMETERS_KEY: 'old'})
        metadata.exif[ExifTags.Base.ImageDescription] = 'a camera description'
        metadata.set_parameters('new')
        self.assertEqual('a camera description', metadata.exif[ExifTags.Base.ImageDescription])

    def test_structured_data_detection(self) -> None:
        """ComfyUI, NovelAI and InvokeAI JSON is recognized. Other entries, and invalid JSON, stay plain text."""
        comfy_prompt = {'3': {'class_type': 'KSampler', 'inputs': {'seed': 5, 'model': ['4', 0]}},
                        '4': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': 'sd15.safetensors'}}}
        metadata = ImageMetadata({
            'prompt': json.dumps(comfy_prompt),
            'workflow': json.dumps({'nodes': []}),
            'Comment': json.dumps({'prompt': 'a cat', 'steps': 28}),
            'invokeai_metadata': json.dumps({'positive_prompt': 'a cat'}),
            'Software': 'NovelAI',
            'parameters': 'not json',
        })
        found = [(entry.source, entry.key) for entry in metadata.structured_data()]
        self.assertEqual([(SOURCE_COMFYUI, 'prompt'), (SOURCE_COMFYUI, 'workflow'), (SOURCE_NOVELAI, 'Comment'),
                          (SOURCE_INVOKEAI, 'invokeai_metadata')], found)
        self.assertEqual(json.dumps({'prompt': 'a cat', 'steps': 28}, indent=2), metadata.structured_data()[2].text)
        self.assertEqual([ComfyUINode('3', 'KSampler', {'seed': 5, 'model': ['4', 0]}),
                          ComfyUINode('4', 'CheckpointLoaderSimple', {'ckpt_name': 'sd15.safetensors'})],
                         metadata.comfyui_nodes())
        self.assertEqual([], ImageMetadata({'Comment': 'just a comment'}).structured_data())

    def test_exif_entries_have_names(self) -> None:
        entries = {(entry.ifd, entry.name): entry for entry in _metadata_with_exif().exif_entries()}
        self.assertEqual('Camera Co', entries[(None, 'Make')].value)
        self.assertFalse(entries[(None, 'Make')].editable)
        self.assertTrue(entries[(None, 'Artist')].editable)
        self.assertIn((IFD.Exif, 'ExposureTime'), entries)
        self.assertIn((IFD.GPSInfo, 'GPSLatitude'), entries)
        self.assertNotIn((None, 'ExifOffset'), entries)

    def test_exif_text_edit(self) -> None:
        metadata = _metadata_with_exif()
        metadata.set_exif_text(None, ExifTags.Base.Copyright, 'CC0')
        metadata.set_exif_text(IFD.Exif, ExifTags.Base.UserComment, 'a comment')
        self.assertEqual('CC0', metadata.exif[ExifTags.Base.Copyright])
        self.assertEqual(('a comment', 'utf-16-be'),
                         decode_user_comment(metadata.exif.get_ifd(IFD.Exif)[ExifTags.Base.UserComment]))
        with self.assertRaises(ValueError):
            metadata.set_exif_text(None, ExifTags.Base.Make, 'not editable')
        metadata.remove_exif_tag(None, ExifTags.Base.Make)
        self.assertNotIn(ExifTags.Base.Make, metadata.exif)

    def test_ora_json_round_trip(self) -> None:
        metadata = ImageMetadata({PARAMETERS_KEY: 'p', 'Software': 'IntraPaint'}, format_info={'dpi': (72, 72)})
        restored = ImageMetadata.from_ora_json(metadata.to_ora_json(), metadata.exif.tobytes())
        self.assertEqual(metadata.text, restored.text)
        self.assertIsNone(ImageMetadata().to_ora_json())

    def test_ora_json_from_info_dict(self) -> None:
        """An .ora file holding a whole PIL info dict keeps its text, and binary or non-text values as format info."""
        restored = ImageMetadata.from_ora_json(json.dumps({PARAMETERS_KEY: 'p', 'dpi': [72, 72], 'icc_profile': 'AAA=',
                                                           'loop': 0}))
        self.assertEqual({PARAMETERS_KEY: 'p'}, restored.text)
        self.assertEqual({'dpi': [72, 72], 'icc_profile': 'AAA=', 'loop': 0}, restored.format_info)
        self.assertTrue(restored.has_icc_profile)
        self.assertTrue(ImageMetadata.from_ora_json('not json').is_empty)


class MetadataFileTest(IntraPaintTestCase):
    """Tests saving and loading metadata through image files."""

    PARAMETERS = 'a cat\nSteps: 20, Sampler: Euler, CFG scale: 7, Lora hashes: "a: 1, b: 2"'

    def setUp(self) -> None:
        super().setUp()
        self._temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp_dir.cleanup)
        self.image = QImage(16, 16, QImage.Format.Format_ARGB32_Premultiplied)
        self.image.fill(QColor(255, 0, 0))

    def _path(self, name: str) -> str:
        return os.path.join(self._temp_dir.name, name)

    def test_png_keeps_every_chunk(self) -> None:
        text = {PARAMETERS_KEY: self.PARAMETERS, 'prompt': '{"1": {}}', 'workflow': '{}', 'XML:com.adobe.xmp': '<x/>'}
        metadata = _metadata_with_exif()
        metadata.text = dict(text)
        save_image_with_metadata(self.image, self._path('saved.png'), metadata)
        _, loaded = load_image(self._path('saved.png'))
        self.assertEqual(text, loaded.text)
        self.assertEqual('<x/>', loaded.xmp)
        self.assertEqual('Someone', loaded.exif[ExifTags.Base.Artist])

    def test_jpeg_with_iptc_xmp_and_gps(self) -> None:
        """A JPEG carrying IPTC, XMP and EXIF GPS, as photo tools write them, loads all three."""
        exif = _exif({None: {ExifTags.Base.ImageDescription: 'A caption'},
                      IFD.GPSInfo: {ExifTags.GPS.GPSLatitudeRef: 'N', ExifTags.GPS.GPSLatitude: (45.0, 30.0, 0.0)}})
        xmp = b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><Iptc4xmpCore:Location>Market</Iptc4xmpCore:Location></x:xmpmeta>'
        path = self._path('photo.jpg')
        Image.new('RGB', (8, 8)).save(path, exif=exif, xmp=xmp)
        with open(path, 'rb') as file:
            data = file.read()
        iptc = _iptc_dataset(2, 90, b'Springfield') + _iptc_dataset(2, 101, b'USA')
        with open(path, 'wb') as file:
            file.write(_with_jpeg_segment(data, 0xED, _photoshop_iptc_segment(iptc)))
        _, loaded = load_image(path)
        self.assertEqual([('City', 'Springfield'), ('Country', 'USA')],
                         [(entry.name, entry.value) for entry in loaded.iptc_entries()])
        self.assertIn('Market', loaded.xmp or '')
        self.assertIn(IFD.GPSInfo, [entry.ifd for entry in loaded.exif_entries()])
        self.assertIsNone(loaded.parameters)

    def test_gif_keeps_a_plain_comment(self) -> None:
        """A comment that isn't generation data is still saved as the GIF comment."""
        save_image_with_metadata(self.image, self._path('comment.gif'), ImageMetadata({COMMENT_KEY: 'a note'}))
        _, loaded = load_image(self._path('comment.gif'))
        self.assertEqual({COMMENT_KEY: 'a note'}, loaded.text)
        self.assertIsNone(loaded.parameters)

    def test_formats_keep_parameters_and_exif(self) -> None:
        """JPEG, WebP, TIFF and GIF keep the parameters, and every one but GIF keeps the EXIF data."""
        for extension in ('jpg', 'webp', 'tiff', 'gif'):
            with self.subTest(extension=extension):
                path = self._path(f'saved.{extension}')
                metadata = _metadata_with_exif()
                metadata.set_parameters(self.PARAMETERS)
                save_image_with_metadata(self.image, path, metadata)
                _, loaded = load_image(path)
                self.assertEqual(self.PARAMETERS, loaded.parameters)
                if extension != 'gif':
                    self.assertEqual('Someone', loaded.exif[ExifTags.Base.Artist])

    def test_viewing_adds_no_empty_ifds(self) -> None:
        """Listing and looking up EXIF data of an image without sub-IFDs doesn't add empty ones to the saved file."""
        metadata = ImageMetadata({PARAMETERS_KEY: 'p'}, _exif({None: {ExifTags.Base.Artist: 'Someone'}}))
        self.assertEqual(1, len(metadata.exif_entries()))
        self.assertEqual('p', metadata.parameters)
        save_image_with_metadata(self.image, self._path('plain.png'), metadata)
        _, loaded = load_image(self._path('plain.png'))
        self.assertEqual([ExifTags.Base.Artist], list(loaded.exif))

    def test_save_leaves_caller_exif_unchanged(self) -> None:
        metadata = _metadata_with_exif()
        save_image_with_metadata(self.image, self._path('saved.jpg'), metadata)
        self.assertNotIn(ExifTags.Base.ImageDescription, metadata.exif)

    def test_parameters_written_to_ifd0_description_only(self) -> None:
        """JPEG, WebP and TIFF saves write the parameters to the IFD0 ImageDescription, and drop a stale Exif IFD copy."""
        for extension in ('jpg', 'webp', 'tiff'):
            with self.subTest(extension=extension):
                metadata = ImageMetadata({PARAMETERS_KEY: self.PARAMETERS},
                                         _exif({IFD.Exif: {ExifTags.Base.ImageDescription: 'stale',
                                                           ExifTags.Base.ExposureTime: 0.01}}))
                path = self._path(f'description.{extension}')
                save_image_with_metadata(self.image, path, metadata)
                _, loaded = load_image(path)
                self.assertEqual(self.PARAMETERS, loaded.exif[ExifTags.Base.ImageDescription])
                self.assertNotIn(ExifTags.Base.ImageDescription, loaded.exif.get_ifd(IFD.Exif))
                self.assertEqual(self.PARAMETERS, loaded.parameters)

    def test_non_ascii_parameters_survive_exif_saves(self) -> None:
        """JPEG, WebP and TIFF saves keep non-ASCII characters in the parameters."""
        parameters = 'caf\u00e9, \u2605\nSteps: 20, Sampler: Euler a, Seed: 1'
        for extension in ('jpg', 'webp', 'tiff'):
            with self.subTest(extension=extension):
                path = self._path(f'unicode.{extension}')
                save_image_with_metadata(self.image, path, ImageMetadata({PARAMETERS_KEY: parameters}))
                _, loaded = load_image(path)
                self.assertEqual(parameters, loaded.parameters)

    def test_user_comment_parameters_load(self) -> None:
        """JPEG and WebP files with A1111's UserComment parameters load them."""
        for extension in ('jpg', 'webp'):
            with self.subTest(extension=extension):
                path = self._path(f'a1111.{extension}')
                exif = Image.Exif()
                exif.get_ifd(IFD.Exif)[ExifTags.Base.UserComment] = encode_user_comment(self.PARAMETERS)
                Image.new('RGB', (16, 16)).save(path, exif=exif)
                _, loaded = load_image(path)
                self.assertEqual(self.PARAMETERS, loaded.parameters)

    def test_jpeg_comment_and_png_info_load(self) -> None:
        """A JPEG comment loads as a text entry, and PNG format info stays out of the text entries."""
        Image.new('RGB', (16, 16)).save(self._path('comment.jpg'), comment=b'a comment')
        _, loaded = load_image(self._path('comment.jpg'))
        self.assertEqual({COMMENT_KEY: 'a comment'}, loaded.text)
        info = PngImagePlugin.PngInfo()
        info.add_text(PARAMETERS_KEY, 'p')
        Image.new('RGB', (16, 16)).save(self._path('dpi.png'), pnginfo=info, dpi=(72, 72))
        _, loaded = load_image(self._path('dpi.png'))
        self.assertEqual({PARAMETERS_KEY: 'p'}, loaded.text)
        self.assertIn('dpi', loaded.format_info)

    def _photo_metadata(self) -> ImageMetadata:
        """Returns the metadata of a JPEG with a comment, XMP, IPTC and GPS tags, as a photo tool writes them."""
        iptc = _iptc_dataset(1, 90, b'\x1b%G') + _iptc_dataset(2, 0, b'\x00\x04') \
            + _iptc_dataset(2, 25, b'market') + _iptc_dataset(2, 90, b'Springfield') \
            + _iptc_dataset(2, 116, 'caf\u00e9'.encode())
        return ImageMetadata({COMMENT_KEY: 'a camera note'},
                             _exif({IFD.GPSInfo: {ExifTags.GPS.GPSLatitudeRef: 'N'}}),
                             {'xmp': PHOTO_XMP, 'photoshop': {0x0404: iptc, 0x0409: b'thumbnail'}})

    def test_jpeg_keeps_comment_xmp_and_iptc(self) -> None:
        """A JPEG save writes the comment, the XMP packet and the IPTC datasets unchanged, with nothing else added."""
        source = self._photo_metadata()
        path = self._path('photo.jpg')
        save_image_with_metadata(self.image, path, source)
        _, loaded = load_image(path)
        self.assertEqual({COMMENT_KEY: 'a camera note'}, loaded.text)
        self.assertEqual(PHOTO_XMP, loaded.xmp_packet)
        self.assertEqual(source.iptc_data, loaded.iptc_data)
        self.assertEqual(source.iptc_entries(), loaded.iptc_entries())
        self.assertEqual({0x0404}, set(loaded.format_info['photoshop']))
        self.assertIn(IFD.GPSInfo, [entry.ifd for entry in loaded.exif_entries()])

    def test_xmp_survives_every_format_that_holds_it(self) -> None:
        """JPEG, WebP, TIFF and PNG saves write the XMP packet, and IPTC is written only to JPEG."""
        for extension in ('jpg', 'webp', 'tiff', 'png'):
            with self.subTest(extension=extension):
                path = self._path(f'photo.{extension}')
                save_image_with_metadata(self.image, path, self._photo_metadata())
                _, loaded = load_image(path)
                self.assertEqual(PHOTO_XMP.decode(), loaded.xmp)
                self.assertEqual(extension == 'jpg', loaded.iptc_data is not None)

    def test_xmp_from_a_png_chunk_is_written_to_jpeg(self) -> None:
        """An XMP packet read from a PNG text chunk is saved to a JPEG as XMP."""
        path = self._path('from_png.jpg')
        save_image_with_metadata(self.image, path, ImageMetadata({'XML:com.adobe.xmp': PHOTO_XMP.decode()}))
        _, loaded = load_image(path)
        self.assertEqual(PHOTO_XMP.decode(), loaded.xmp)
        self.assertEqual({}, loaded.text)

    def test_oversized_iptc_is_skipped(self) -> None:
        """IPTC data too long for one JPEG segment is left out, and the rest of the metadata is still saved."""
        iptc = _iptc_dataset(2, 120, b'x' * 30000) * 3
        path = self._path('large.jpg')
        with self.assertLogs(image_utils_logger, 'WARNING'):
            save_image_with_metadata(self.image, path, ImageMetadata({COMMENT_KEY: 'kept'},
                                                                    format_info={'photoshop': {0x0404: iptc}}))
        _, loaded = load_image(path)
        self.assertEqual({COMMENT_KEY: 'kept'}, loaded.text)
        self.assertIsNone(loaded.iptc_data)

    def test_remove_location(self) -> None:
        """Remove location clears GPS tags and IPTC and XMP place fields, keeping the rest byte for byte."""
        metadata = self._photo_metadata()
        self.assertTrue(metadata.has_location_data)
        metadata.remove_location()
        self.assertFalse(metadata.has_location_data)
        self.assertEqual([('Keywords', 'market'), ('Copyright Notice', 'caf\u00e9')],
                         [(entry.name, entry.value) for entry in metadata.iptc_entries()])
        self.assertEqual(_iptc_dataset(1, 90, b'\x1b%G') + _iptc_dataset(2, 0, b'\x00\x04')
                         + _iptc_dataset(2, 25, b'market') + _iptc_dataset(2, 116, 'caf\u00e9'.encode()),
                         metadata.iptc_data)
        self.assertNotIn(IFD.GPSInfo, [entry.ifd for entry in metadata.exif_entries()])
        self.assertEqual(PHOTO_XMP_WITHOUT_LOCATION, metadata.xmp_packet)
        self.assertEqual({COMMENT_KEY: 'a camera note'}, metadata.text)

    def test_remove_location_from_a_png_xmp_chunk(self) -> None:
        """An XMP packet kept as a text entry loses its place fields too."""
        metadata = ImageMetadata({'XML:com.adobe.xmp': PHOTO_XMP.decode()})
        self.assertTrue(metadata.has_location_data)
        metadata.remove_location()
        self.assertEqual(PHOTO_XMP_WITHOUT_LOCATION.decode(), metadata.text['XML:com.adobe.xmp'])
        self.assertFalse(metadata.has_location_data)

    def test_no_location_data(self) -> None:
        """Metadata with no place fields reports none, and Remove location leaves it unchanged."""
        metadata = ImageMetadata({COMMENT_KEY: 'Paris'}, format_info={
            'xmp': b'<x:xmpmeta xmlns:x="adobe:ns:meta/"/>', 'photoshop': {0x0404: _iptc_dataset(2, 25, b'Paris')}})
        self.assertFalse(metadata.has_location_data)
        before = metadata.copy()
        metadata.remove_location()
        self.assertEqual(before.format_info, metadata.format_info)
        self.assertEqual(before.text, metadata.text)

    def test_remove_all(self) -> None:
        """Remove all clears text, EXIF, XMP and ICC data and keeps other format info."""
        metadata = ImageMetadata({"a": "b"}, format_info={"xmp": b"x", "icc_profile": b"p", "dpi": (72, 72)})
        metadata.set_exif_text(None, ExifTags.Base.Artist, "me")
        metadata.remove_all()
        self.assertEqual({}, metadata.text)
        self.assertEqual([], metadata.exif_entries())
        self.assertEqual({"dpi": (72, 72)}, metadata.format_info)

    def test_remove_gps_leaves_no_gps_ifd(self) -> None:
        metadata = _metadata_with_exif()
        self.assertIn(IFD.GPSInfo, {entry.ifd for entry in metadata.exif_entries()})  # Reads the GPS IFD first.
        metadata.remove_gps()
        self.assertNotIn(IFD.GPSInfo, {entry.ifd for entry in metadata.exif_entries()})
        save_image_with_metadata(self.image, self._path('no_gps.jpg'), metadata)
        _, loaded = load_image(self._path('no_gps.jpg'))
        self.assertNotIn(IFD.GPSInfo, loaded.exif)
        self.assertEqual('Someone', loaded.exif[ExifTags.Base.Artist])
        self.assertEqual(0.01, loaded.exif.get_ifd(IFD.Exif)[ExifTags.Base.ExposureTime])
