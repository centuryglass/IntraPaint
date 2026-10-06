"""Tests .ora saving and loading, including layer names that are awkward as file names and text layers."""
import ntpath
import os
import sys
import tempfile
import zipfile
from typing import Optional
from unittest.mock import patch
from xml.etree.ElementTree import fromstring, tostring

from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QTransform
from PySide6.QtWidgets import QApplication

from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.image.layers.text_layer import TextLayer
from src.image.layers.transform_layer import TransformLayer
from src.image.open_raster import (save_ora_image, read_ora_image, DATA_DIRECTORY_NAME, THUMBNAIL_DIRECTORY_NAME,
                                   XML_FILE_NAME, EXTENDED_DATA_XML_FILE_NAME, LAYER_TAG_SRC, TRANSFORM_SRC_TAG,
                                   TEXT_DATA_TAG)
from src.image.text_rect import TextRect
from test.base_test_case import IntraPaintTestCase

IMG_SIZE = QSize(16, 16)
GEN_AREA_SIZE = QSize(8, 8)
MIN_GEN_AREA = QSize(8, 8)
MAX_GEN_AREA = QSize(32, 32)

METADATA = 'test metadata'

AWKWARD_NAMES = [
    '',
    ' ',
    'with space',
    'a/b',
    '/leading/slash',
    'trailing/',
    'a\\b',
    'C:\\temp\\layer',
    '..',
    '../escape',
    '..\\escape',
    '.',
    '.hidden',
    'name.png',
    'caf\u00e9 \u5c42 \U0001f600',
    'quote"and<angle>&amp;',
    'a' * 200,
]

# The same name for every layer in one stack, including a layer nested in a group:
DUPLICATE_NAME = 'same'

_real_join = os.path.join


def _windows_archive_join(first: str, *rest: str) -> str:
    """Joins like Windows when building a path that starts at an archive directory, and like the host otherwise.

    Real filesystem paths start at the temporary directory, so they still resolve.
    """
    if first in (DATA_DIRECTORY_NAME, THUMBNAIL_DIRECTORY_NAME):
        return ntpath.join(first, *rest)
    return _real_join(first, *rest)


app = QApplication.instance() or QApplication(sys.argv)


def _solid_image(color: QColor) -> QImage:
    image = QImage(IMG_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color)
    return image


def _layer_color(index: int) -> QColor:
    """Returns a distinct opaque color for each layer index."""
    return QColor(index * 20 % 256, 255 - index * 10 % 256, index * 7 % 256)


class OpenRasterTest(IntraPaintTestCase):
    """Tests .ora saving and loading, including layer names that are awkward as file names."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(IMG_SIZE, GEN_AREA_SIZE, MIN_GEN_AREA, MAX_GEN_AREA)
        self.loaded_stack = ImageStack(IMG_SIZE, GEN_AREA_SIZE, MIN_GEN_AREA, MAX_GEN_AREA)

    def _add_image_layer(self, name: str, parent: Optional[LayerGroup] = None) -> ImageLayer:
        color = _layer_color(len(self.image_stack.image_layers))
        return self.image_stack.create_layer(name, _solid_image(color), layer_parent=parent,
                                             layer_index=parent.count if parent is not None else
                                             self.image_stack.layer_stack.count)

    def _round_trip(self) -> Optional[str]:
        """Saves the image stack to a temporary .ora file and loads it into self.loaded_stack."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ora_path = os.path.join(temp_dir, 'round_trip.ora')
            save_ora_image(self.image_stack, ora_path, METADATA)
            self.assertTrue(os.path.isfile(ora_path))
            self.assertEqual([], [name for name in os.listdir(temp_dir) if name != 'round_trip.ora'],
                             'saving left extra files beside the .ora file')
            return read_ora_image(self.loaded_stack, ora_path)

    def _assert_layers_match(self, expected: Layer, actual: Layer) -> None:
        """Asserts that two layers and everything nested in them have the same names, types and pixels."""
        self.assertEqual(type(expected), type(actual))
        self.assertEqual(expected.name, actual.name)
        if isinstance(expected, LayerGroup):
            assert isinstance(actual, LayerGroup)
            self.assertEqual(expected.count, actual.count, f'child count of group "{expected.name}"')
            for expected_child, actual_child in zip(expected.child_layers, actual.child_layers):
                self._assert_layers_match(expected_child, actual_child)
        else:
            assert isinstance(expected, TransformLayer) and isinstance(actual, TransformLayer)
            self.assert_images_equal(actual.image, expected.image, f'pixels of layer "{expected.name}"')
            self.assertEqual(expected.transform, actual.transform, f'transform of layer "{expected.name}"')
            self.assertEqual(expected.opacity, actual.opacity, f'opacity of layer "{expected.name}"')
            self.assertEqual(expected.visible, actual.visible, f'visibility of layer "{expected.name}"')
            if isinstance(expected, TextLayer):
                assert isinstance(actual, TextLayer)
                # TextRect equality compares QFont identity, so compare serialized data instead:
                self.assertEqual(expected.text_rect.serialize(), actual.text_rect.serialize(),
                                 f'text data of layer "{expected.name}"')

    def _assert_round_trip_matches(self) -> None:
        metadata = self._round_trip()
        self.assertEqual(METADATA, metadata)
        self.assertEqual(self.image_stack.size, self.loaded_stack.size)
        self.assertEqual(len(self.image_stack.layers), len(self.loaded_stack.layers))
        self._assert_layers_match(self.image_stack.layer_stack, self.loaded_stack.layer_stack)

    def test_awkward_names_individually(self) -> None:
        """Each awkward layer name survives a round trip, as a top-level layer and inside a group."""
        for name in AWKWARD_NAMES:
            with self.subTest(name=name, nested=False):
                self.setUp()
                self._add_image_layer(name)
                self._assert_round_trip_matches()
            with self.subTest(name=name, nested=True):
                self.setUp()
                group = self.image_stack.create_layer_group(name)
                self._add_image_layer(name, group)
                self._assert_round_trip_matches()

    def test_awkward_names_together(self) -> None:
        """All awkward layer names survive a round trip in one stack, in order, with their own pixels."""
        group = self.image_stack.create_layer_group('group')
        for name in AWKWARD_NAMES:
            self._add_image_layer(name)
            self._add_image_layer(name, group)
        self.assertEqual(len(AWKWARD_NAMES) * 2, len(self.image_stack.image_layers))
        self._assert_round_trip_matches()
        loaded_names = [layer.name for layer in self.loaded_stack.image_layers]
        self.assertEqual([layer.name for layer in self.image_stack.image_layers], loaded_names)

    def test_duplicate_names(self) -> None:
        """Layers sharing a name, in the main stack and in groups, keep separate pixel content."""
        first_group = self.image_stack.create_layer_group(DUPLICATE_NAME)
        second_group = self.image_stack.create_layer_group(DUPLICATE_NAME)
        for parent in (None, first_group, second_group):
            self._add_image_layer(DUPLICATE_NAME, parent)
            self._add_image_layer(DUPLICATE_NAME, parent)
        self._assert_round_trip_matches()
        loaded_colors = {layer.image.pixelColor(0, 0).rgb() for layer in self.loaded_stack.image_layers}
        self.assertEqual(len(self.image_stack.image_layers), len(loaded_colors))

    def test_empty_names_only(self) -> None:
        """A stack where every layer and group is unnamed round-trips."""
        group = self.image_stack.create_layer_group('')
        nested_group = self.image_stack.create_layer_group('', group)
        for parent in (None, group, nested_group):
            self._add_image_layer('', parent)
            self._add_image_layer('', parent)
        self._assert_round_trip_matches()

    def test_awkward_names_stay_inside_archive_data_directory(self) -> None:
        """Layer image files are archived under data/, one path component deep, whatever the layer names are."""
        for name in AWKWARD_NAMES:
            layer = self._add_image_layer(name)
            layer.transform = QTransform.fromScale(0.5, 0.5)
        with tempfile.TemporaryDirectory() as temp_dir:
            ora_path = os.path.join(temp_dir, 'archive.ora')
            save_ora_image(self.image_stack, ora_path, METADATA)
            with zipfile.ZipFile(ora_path) as zip_file:
                image_files = [entry for entry in zip_file.namelist() if entry.startswith(f'{DATA_DIRECTORY_NAME}/')]
                self.assertEqual(2 * len(AWKWARD_NAMES), len(image_files))
                self.assertEqual(len(image_files), len(set(image_files)))
                for entry in image_files:
                    self.assertEqual(2, len(entry.split('/')), entry)
                    self.assertNotIn('..', entry.split('/'))
                    self.assertFalse(entry.endswith('/'), entry)
                for entry in zip_file.namelist():
                    self.assertFalse(entry.startswith('/') or '..' in entry.split('/'), entry)

    def test_transformed_layers_with_awkward_names(self) -> None:
        """Layers with a transform save an untransformed copy under a safe name, and load with the transform."""
        for i, name in enumerate(AWKWARD_NAMES):
            layer = self._add_image_layer(name)
            layer.transform = QTransform.fromScale(0.5, 0.5) * QTransform.fromTranslate(i % 4, 2)
        self._assert_round_trip_matches()
        for expected, actual in zip(self.image_stack.image_layers, self.loaded_stack.image_layers):
            self.assertEqual(expected.transform, actual.transform, f'transform of layer "{expected.name}"')

    def test_layer_transforms_round_trip(self) -> None:
        """Image layer transforms load with every matrix element intact, including flips, rotation, fractional
        offsets and shear."""
        transforms = {
            'flip horizontal': QTransform(-1.0, 0.0, 0.0, 1.0, 100.0, 0.0),
            'flip vertical': QTransform(1.0, 0.0, 0.0, -1.0, 0.0, 50.0),
            'rotate': QTransform.fromTranslate(-50.0, -25.0) * QTransform().rotate(33.3)
            * QTransform.fromTranslate(80.0, 40.0),
            'fractional offset': QTransform.fromTranslate(10.125, -3.7),
            'flip, scale and rotate': QTransform.fromScale(-0.4, 1.7) * QTransform().rotate(250.0)
            * QTransform.fromTranslate(64.5, 200.25),
            'shear': QTransform(1.0, 0.3, 0.0, 1.0, 50.0, 50.0),
        }
        for name, transform in transforms.items():
            self._add_image_layer(name).transform = transform
        self._assert_round_trip_matches()
        loaded = {layer.name: layer.transform for layer in self.loaded_stack.image_layers}
        self.assertEqual(transforms, loaded)

    def test_archive_paths_use_forward_slashes(self) -> None:
        """Every src in stack.xml and the extended XML is a '/'-separated entry in the archive."""
        for i, name in enumerate(AWKWARD_NAMES):
            layer = self._add_image_layer(name)
            if i % 2 == 0:
                layer.transform = QTransform.fromScale(0.5, 0.5)
        group = self.image_stack.create_layer_group('group')
        self._add_image_layer('nested', group)
        with tempfile.TemporaryDirectory() as temp_dir:
            ora_path = os.path.join(temp_dir, 'src_paths.ora')
            # Simulates Windows path joining for archive-relative paths:
            with patch('os.path.join', side_effect=_windows_archive_join):
                save_ora_image(self.image_stack, ora_path, METADATA)
            with zipfile.ZipFile(ora_path) as zip_file:
                entries = set(zip_file.namelist())
                stack_xml = fromstring(zip_file.read(XML_FILE_NAME))
                extended_xml = fromstring(zip_file.read(EXTENDED_DATA_XML_FILE_NAME))
        layer_sources = [element.get(LAYER_TAG_SRC) for element in stack_xml.iter('layer')]
        self.assertEqual(len(self.image_stack.image_layers), len(layer_sources))
        transform_sources = [element.get(TRANSFORM_SRC_TAG) for element in extended_xml.iter('layer')
                             if element.get(TRANSFORM_SRC_TAG) is not None]
        self.assertEqual(len(AWKWARD_NAMES) // 2 + len(AWKWARD_NAMES) % 2, len(transform_sources))
        extended_sources = [element.get(LAYER_TAG_SRC) for element in extended_xml.iter('layer')]
        for source in [*layer_sources, *transform_sources, *extended_sources]:
            self.assertIsNotNone(source)
            self.assertNotIn('\\', str(source))
            self.assertIn(source, entries)
        self.assertIn(f'{THUMBNAIL_DIRECTORY_NAME}/thumbnail.png', entries)
        self.assertFalse([entry for entry in entries if '\\' in entry])

    def test_load_backslash_src_paths(self) -> None:
        """Files saved on Windows by earlier versions, with '\\' in src attributes, still load."""
        layer = self._add_image_layer('legacy')
        layer.transform = QTransform.fromScale(0.5, 0.5)
        with tempfile.TemporaryDirectory() as temp_dir:
            ora_path = os.path.join(temp_dir, 'legacy.ora')
            legacy_path = os.path.join(temp_dir, 'legacy_windows.ora')
            save_ora_image(self.image_stack, ora_path, METADATA)
            with zipfile.ZipFile(ora_path) as source, zipfile.ZipFile(legacy_path, 'w') as legacy:
                for entry in source.namelist():
                    content = source.read(entry)
                    if entry in (XML_FILE_NAME, EXTENDED_DATA_XML_FILE_NAME):
                        content = content.replace(f'{DATA_DIRECTORY_NAME}/'.encode(),
                                                  f'{DATA_DIRECTORY_NAME}\\'.encode())
                        self.assertIn(b'\\', content)
                    legacy.writestr(entry, content)
            read_ora_image(self.loaded_stack, legacy_path)
        self._assert_layers_match(self.image_stack.layer_stack, self.loaded_stack.layer_stack)
        self.assertEqual(layer.transform, self.loaded_stack.image_layers[0].transform)

    def _add_text_layer(self, text: str, parent: Optional[LayerGroup] = None) -> TextLayer:
        text_rect = TextRect()
        text_rect.text = text
        text_rect.size = QSize(12, 10)
        text_rect.text_color = QColor(Qt.GlobalColor.red)
        text_rect.background_color = QColor(0, 0, 255, 128)
        text_rect.fill_background = True
        text_rect.text_alignment = Qt.AlignmentFlag.AlignRight
        return self.image_stack.create_text_layer(text_rect, parent,
                                                  parent.count if parent is not None else
                                                  self.image_stack.layer_stack.count)

    def _save_with_edited_extended_data(self, edit_text_data) -> None:
        """Saves the image stack, rewrites each text-data value with edit_text_data, and loads the result.

        edit_text_data takes the saved value and returns the replacement, or None to remove it.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            ora_path = os.path.join(temp_dir, 'text.ora')
            edited_path = os.path.join(temp_dir, 'edited.ora')
            save_ora_image(self.image_stack, ora_path, METADATA)
            with zipfile.ZipFile(ora_path) as source, zipfile.ZipFile(edited_path, 'w') as edited:
                for entry in source.namelist():
                    content = source.read(entry)
                    if entry == EXTENDED_DATA_XML_FILE_NAME:
                        extended_xml = fromstring(content)
                        for element in extended_xml.iter('layer'):
                            text_data = element.get(TEXT_DATA_TAG)
                            if text_data is None:
                                continue
                            new_data = edit_text_data(text_data)
                            if new_data is None:
                                del element.attrib[TEXT_DATA_TAG]
                            else:
                                element.set(TEXT_DATA_TAG, new_data)
                        content = tostring(extended_xml)
                    edited.writestr(entry, content)
            read_ora_image(self.loaded_stack, edited_path)

    def _assert_loaded_as_rendered_images(self) -> None:
        """Asserts that each saved text layer loaded as an image layer showing the rendered text."""
        self.assertEqual([], self.loaded_stack.text_layers)
        self.assertEqual(len(self.image_stack.layers), len(self.loaded_stack.layers))
        for expected, actual in zip(self.image_stack.layers, self.loaded_stack.layers):
            if isinstance(expected, TextLayer):
                assert isinstance(actual, ImageLayer)
                self.assertEqual(expected.name, actual.name)
                self.assertEqual(expected.transform, actual.transform)
                self.assert_images_equal(actual.image, expected.image, f'pixels of layer "{expected.name}"')

    def test_text_layers_round_trip(self) -> None:
        """Text layers load as editable text layers with their text data, transform and layer attributes."""
        self._add_image_layer('background')
        self._add_text_layer('top level')
        group = self.image_stack.create_layer_group('group')
        nested = self._add_text_layer('nested', group)
        nested.offset = QPointF(3, 4)
        nested.set_opacity(0.5)
        hidden = self._add_text_layer('hidden')
        hidden.set_visible(False)
        rotated = self._add_text_layer('rotated')
        rotated.transform = QTransform.fromTranslate(5, 2).rotate(30)
        self._assert_round_trip_matches()
        self.assertEqual(4, len(self.loaded_stack.text_layers))

    def test_text_layer_archive_has_rendered_image(self) -> None:
        """A text layer's stack.xml entry points at its rendered pixels, so other editors can show it."""
        layer = self._add_text_layer('rendered')
        layer.offset = QPointF(2, 3)
        with tempfile.TemporaryDirectory() as temp_dir:
            ora_path = os.path.join(temp_dir, 'rendered.ora')
            save_ora_image(self.image_stack, ora_path, METADATA)
            with zipfile.ZipFile(ora_path) as zip_file:
                stack_xml = fromstring(zip_file.read(XML_FILE_NAME))
                layer_elements = list(stack_xml.iter('layer'))
                self.assertEqual(1, len(layer_elements))
                self.assertEqual('2', layer_elements[0].get('x'))
                self.assertEqual('3', layer_elements[0].get('y'))
                saved_image = QImage.fromData(zip_file.read(str(layer_elements[0].get(LAYER_TAG_SRC))))
        self.assert_images_equal(saved_image, layer.image, 'rendered text layer image')

    def test_text_layer_without_text_data_loads_as_image(self) -> None:
        """A text layer saved without text data, as earlier versions did, loads as an image of the rendered text."""
        self._add_text_layer('plain')
        rotated = self._add_text_layer('rotated')
        rotated.transform = QTransform.fromScale(2, 1)
        self._save_with_edited_extended_data(lambda _: None)
        self._assert_loaded_as_rendered_images()

    def test_invalid_text_data_loads_as_image(self) -> None:
        """Text data that can't be parsed falls back to an image of the rendered text."""
        for label, edit in (('not json', lambda _: '{not json'),
                            ('not an object', lambda _: '[]'),
                            ('missing key', lambda data: data.replace('"font"', '"unknown"'))):
            with self.subTest(label):
                self.setUp()
                self._add_text_layer(label)
                self._save_with_edited_extended_data(edit)
                self._assert_loaded_as_rendered_images()

    def test_unsupported_layer_type_is_not_flattened(self) -> None:
        """Saving a layer type the .ora writer doesn't know fails instead of saving it as plain pixels."""

        class _OtherLayer(TransformLayer):
            def get_qimage(self) -> QImage:
                return _solid_image(QColor(Qt.GlobalColor.green))

        self.image_stack.layer_stack.insert_layer(_OtherLayer('other'), 0)
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(TypeError):
                save_ora_image(self.image_stack, os.path.join(temp_dir, 'unsupported.ora'), METADATA)
