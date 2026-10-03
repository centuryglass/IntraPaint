"""Tests .ora saving and loading, including layer names that are awkward as file names."""
import os
import sys
import tempfile
import zipfile
from typing import Optional

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage, QTransform
from PySide6.QtWidgets import QApplication

from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.image.open_raster import save_ora_image, read_ora_image, DATA_DIRECTORY_NAME
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
            assert isinstance(expected, ImageLayer) and isinstance(actual, ImageLayer)
            self.assert_images_equal(actual.image, expected.image, f'pixels of layer "{expected.name}"')

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
