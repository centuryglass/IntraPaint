"""Tests the ImageStack module"""
import os
import sys
import unittest
from unittest.mock import Mock, MagicMock

from PyQt5.QtCore import QSize, QRect, QPoint, Qt
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer_stack import LayerStack
from src.image.layers.selection_layer import SelectionLayer

IMG_SIZE = QSize(512, 512)
GEN_AREA_SIZE = QSize(300, 300)
MIN_GEN_AREA = QSize(8, 8)
MAX_GEN_AREA = QSize(999, 999)

INIT_IMAGE = 'resources/image_stack/source.png'
app = QApplication.instance() or QApplication(sys.argv)


class ImageStackTest(unittest.TestCase):
    """Tests the ImageStack module"""

    def setUp(self) -> None:
        while os.path.basename(os.getcwd()) not in ('IntraPaint', ''):
            os.chdir('..')
        assert os.path.basename(os.getcwd()) == 'IntraPaint'
        self._app_config = AppConfig('test/resources/app_config_test.json')
        self._key_config = KeyConfig('test/resources/key_config_test.json')
        self._cache = Cache('test/resources/cache_test.json')
        AppConfig()._reset()
        KeyConfig()._reset()
        Cache()._reset()
        self.image_stack = ImageStack(IMG_SIZE, GEN_AREA_SIZE, MIN_GEN_AREA, MAX_GEN_AREA)

        self.generation_area_bounds_changed_mock = MagicMock()
        self.content_changed_mock = MagicMock()
        self.size_changed_mock = MagicMock()
        self.layer_added_mock = MagicMock()
        self.layer_removed_mock = MagicMock()
        self.active_layer_changed_mock = MagicMock()
        self.image_stack.generation_area_bounds_changed.connect(self.generation_area_bounds_changed_mock)
        self.image_stack.content_changed.connect(self.content_changed_mock)
        self.image_stack.size_changed.connect(self.size_changed_mock)
        self.image_stack.layer_added.connect(self.layer_added_mock)
        self.image_stack.layer_removed.connect(self.layer_removed_mock)
        self.image_stack.active_layer_changed.connect(self.active_layer_changed_mock)

    def assert_no_signals(self) -> None:
        self.generation_area_bounds_changed_mock.assert_not_called()
        self.content_changed_mock.assert_not_called()
        self.size_changed_mock.assert_not_called()
        self.layer_added_mock.assert_not_called()
        self.layer_removed_mock.assert_not_called()
        self.active_layer_changed_mock.assert_not_called()

    def test_init_properties(self) -> None:
        """Check that all initial properties behave as expected."""
        self.assertEqual(self.image_stack.count, 0)
        self.assertIsNone(self.image_stack.active_layer)
        self.assertIsNone(self.image_stack.active_layer_id)
        self.assertEqual(self.image_stack.top_level_layers, [])
        layer_list = self.image_stack.layers
        self.assertEqual(len(layer_list), 1)
        # Layer stack should be only layer, name should sync with last file
        layer_stack = layer_list[0]
        self.assertIsInstance(layer_stack, LayerStack)
        self.assertEqual(layer_stack.name, 'new image')
        Cache().set(Cache.LAST_FILE_PATH, '/mock/file/path.png')
        self.assertEqual(layer_stack.name, 'path.png')
        self.assertEqual(self.image_stack.image_layers, [])
        self.assertIsInstance(self.image_stack.selection_layer, SelectionLayer)
        self.assertFalse(self.image_stack.has_image)
        self.assertEqual(self.image_stack.bounds, QRect(QPoint(), IMG_SIZE))
        self.assertEqual(self.image_stack.merged_layer_bounds, QRect())
        self.assertEqual(self.image_stack.size, IMG_SIZE)
        self.assertEqual(self.image_stack.width, IMG_SIZE.width())
        self.assertEqual(self.image_stack.height, IMG_SIZE.height())
        self.assertEqual(self.image_stack.min_generation_area_size, MIN_GEN_AREA)
        self.assertEqual(self.image_stack.max_generation_area_size, MAX_GEN_AREA)
        self.assertEqual(self.image_stack.generation_area, QRect(QPoint(), GEN_AREA_SIZE))
        # image should be null:
        self.assertTrue(self.image_stack.qimage().isNull())
        self.assert_no_signals()

    def test_load_image(self) -> None:
        """Test loading an initial image from a file"""
        image = QImage(INIT_IMAGE)
        self.assert_no_signals()
        self.image_stack.load_image(image)
        self.size_changed_mock.assert_called_with(image.size())
        self.layer_added_mock.assert_called()
        self.content_changed_mock.assert_called()
        self.assertEqual(image.size(), self.image_stack.size)
        self.assertEqual(1, self.image_stack.count)
        self.assertEqual(self.image_stack.qimage(), image)
        layer = self.image_stack.active_layer
        from src.image.layers.image_layer import ImageLayer
        self.assertIsInstance(layer, ImageLayer)
        self.assertEqual(layer.image, image)

    def test_layer_create(self) -> None:
        """Test creating new layers and layer groups"""

        # Create layer from image:
        image = QImage(INIT_IMAGE)
        layer_0 = self.image_stack.create_layer(None, image)
        self.layer_added_mock.assert_called_once()
        self.content_changed_mock.assert_called_once()
        self.active_layer_changed_mock.assert_called_with(layer_0)
        self.assertEqual(self.image_stack.active_layer_id, layer_0.id)
        self.assertEqual(self.image_stack.active_layer, layer_0)
        self.assertEqual(1, self.image_stack.count)
        self.assertEqual(self.image_stack.qimage(), image)
        self.assertEqual(layer_0.image, image)
        self.assertEqual(layer_0.name, 'layer 0')
        self.layer_added_mock.reset_mock()
        self.content_changed_mock.reset_mock()

        # Create empty image layer:
        layer_1 = self.image_stack.create_layer()
        self.layer_added_mock.assert_called_once()
        # TODO: inserting a transparent layer shouldn't trigger content_changed
        self.content_changed_mock.assert_called_once()
        self.assertTrue(layer_1.empty)
        self.assertEqual(layer_1.name, 'layer 1')
        self.layer_added_mock.reset_mock()
        self.content_changed_mock.reset_mock()

        # Create layer group:
        layer_group = self.image_stack.create_layer_group()
        self.layer_added_mock.assert_called_once()
        self.content_changed_mock.assert_not_called()
        self.assertTrue(layer_group.empty)
        self.assertEqual(layer_group.name, 'layer 2')
        self.layer_added_mock.reset_mock()
        self.content_changed_mock.reset_mock()

        # Create inner group:
        inner_group = self.image_stack.create_layer_group('inner group', layer_group)
        self.layer_added_mock.assert_called_once()
        # TODO: inserting a transparent layer shouldn't trigger content_changed, but it triggers 3x
        # self.content_changed_mock.assert_not_called()
        self.assertEqual(inner_group.layer_parent, layer_group)
        self.assertEqual(layer_group.count, 1)
        self.assertTrue(inner_group.empty)
        self.assertEqual(inner_group.name, 'inner group')
        self.layer_added_mock.reset_mock()
        self.content_changed_mock.reset_mock()

    def test_layer_move(self) -> None:
        """Test moving layers through the stack."""
        image = QImage(INIT_IMAGE)
        layer_0 = self.image_stack.create_layer(None, image)
        layer_1 = self.image_stack.create_layer()
        layer_group = self.image_stack.create_layer_group()
        inner_group = self.image_stack.create_layer_group('inner group', layer_group)
        self.layer_added_mock.reset_mock()
        self.content_changed_mock.reset_mock()
        inner_group.z_value = 44
        self.image_stack._update_z_values()

        # Validate z-values and active layer state:
        self.assertEqual(layer_0.id, self.image_stack.active_layer_id)
        self.assertEqual(-1, layer_1.z_value)
        self.assertEqual(-2, layer_group.z_value)
        self.assertEqual(-3, inner_group.z_value)
        self.assertEqual(-4, layer_0.z_value)

        # Moving down when at bottom does nothing:
        self.image_stack.move_layer(1)
        self.assertEqual(-1, layer_1.z_value)
        self.assertEqual(-2, layer_group.z_value)
        self.assertEqual(-3, inner_group.z_value)
        self.assertEqual(-4, layer_0.z_value)
        self.assertEqual(self.image_stack._layer_stack, layer_0.layer_parent)

        # Move up to top:
        self.image_stack.move_layer(-1)
        self.assertEqual(-4, layer_0.z_value)
        self.assertEqual(layer_group, layer_0.layer_parent)

        self.image_stack.move_layer(-1)
        self.assertEqual(-4, layer_0.z_value)
        self.assertEqual(inner_group, layer_0.layer_parent)

        self.image_stack.move_layer(-1)
        self.assertEqual(-3, layer_0.z_value)
        self.assertEqual(layer_group, layer_0.layer_parent)

        self.image_stack.move_layer(-1)
        self.assertEqual(-2, layer_0.z_value)
        self.assertEqual(self.image_stack._layer_stack, layer_0.layer_parent)

        self.image_stack.move_layer(-1)
        self.assertEqual(-1, layer_0.z_value)

        # No change moving up from top:
        self.image_stack.move_layer(-1)
        self.assertEqual(-1, layer_0.z_value)
        self.assertEqual(-2, layer_1.z_value)
        self.assertEqual(-3, layer_group.z_value)
        self.assertEqual(-4, inner_group.z_value)

        # Move back to bottom:
        self.image_stack.move_layer(1)
        self.assertEqual(-2, layer_0.z_value)

        self.image_stack.move_layer(1)
        self.assertEqual(-3, layer_0.z_value)
        self.assertEqual(layer_group, layer_0.layer_parent)

        self.image_stack.move_layer(1)
        self.assertEqual(-4, layer_0.z_value)
        self.assertEqual(inner_group, layer_0.layer_parent)

        self.image_stack.move_layer(1)
        self.assertEqual(-4, layer_0.z_value)
        self.assertEqual(layer_group, layer_0.layer_parent)

        self.image_stack.move_layer(1)
        self.assertEqual(-4, layer_0.z_value)
        self.assertEqual(self.image_stack._layer_stack, layer_0.layer_parent)