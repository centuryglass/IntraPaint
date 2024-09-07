"""Tests the ImageLayer class"""
import os
import sys
import unittest
from unittest.mock import MagicMock

from PySide6.QtCore import QSize, QRect, QPoint
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.composite_mode import CompositeMode
from src.image.layers.image_layer import ImageLayer
from src.undo_stack import UndoStack
from src.util.visual.image_utils import image_is_fully_transparent

IMG_SIZE = QSize(512, 512)
LAYER_NAME = 'test layer'
INIT_IMAGE = 'test/resources/test_images/source.png'
app = QApplication.instance() or QApplication(sys.argv)


class ImageLayerTest(unittest.TestCase):
    """Tests the ImageLayer class"""

    def setUp(self) -> None:
        while os.path.basename(os.getcwd()) not in ('IntraPaint', ''):
            os.chdir('..')
        assert os.path.basename(os.getcwd()) == 'IntraPaint'
        self._app_config = AppConfig('test/resources/app_config_test.json')
        self._key_config = KeyConfig('test/resources/key_config_test.json')
        self._cache = Cache('test/resources/cache_test.json')
        AppConfig()._reset()
        KeyConfig()._reset()
        UndoStack().clear()
        Cache()._reset()
        self.image_layer = ImageLayer(IMG_SIZE, LAYER_NAME)

        self.name_changed_mock = MagicMock()
        self.visibility_changed_mock = MagicMock()
        self.content_changed_mock = MagicMock()
        self.opacity_changed_mock = MagicMock()
        self.size_changed_mock = MagicMock()
        self.composition_changed_mock = MagicMock()
        self.z_value_changed_mock = MagicMock()
        self.lock_changed_mock = MagicMock()
        self.alpha_lock_changed_mock = MagicMock()
        self.image_layer.name_changed.connect(self.name_changed_mock)
        self.image_layer.visibility_changed.connect(self.visibility_changed_mock)
        self.image_layer.content_changed.connect(self.content_changed_mock)
        self.image_layer.opacity_changed.connect(self.opacity_changed_mock)
        self.image_layer.size_changed.connect(self.size_changed_mock)
        self.image_layer.composition_mode_changed.connect(self.composition_changed_mock)
        self.image_layer.z_value_changed.connect(self.z_value_changed_mock)
        self.image_layer.lock_changed.connect(self.lock_changed_mock)
        self.image_layer.alpha_lock_changed.connect(self.alpha_lock_changed_mock)

    def assert_no_signals(self) -> None:
        self.name_changed_mock.assert_not_called()
        self.visibility_changed_mock.assert_not_called()
        self.content_changed_mock.assert_not_called()
        self.opacity_changed_mock.assert_not_called()
        self.size_changed_mock.assert_not_called()
        self.composition_changed_mock.assert_not_called()
        self.z_value_changed_mock.assert_not_called()
        self.lock_changed_mock.assert_not_called()
        self.alpha_lock_changed_mock.assert_not_called()

    def test_init_properties(self) -> None:
        """Check that all initial properties behave as expected."""
        self.assertEqual(self.image_layer.name, LAYER_NAME)
        self.assertEqual(self.image_layer.size, IMG_SIZE)
        self.assertTrue(self.image_layer.visible)
        self.assertEqual(self.image_layer.opacity, 1.0)
        self.assertEqual(self.image_layer.composition_mode, CompositeMode.NORMAL)
        self.assertFalse(self.image_layer.locked)
        self.assertFalse(self.image_layer.alpha_locked)
        self.assertTrue(self.image_layer.transform.isIdentity())
        self.assert_no_signals()

    def test_set_image(self) -> None:
        """Test setting content with a QImage through the image property"""
        new_image = QImage(INIT_IMAGE).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        self.assertNotEqual(new_image, self.image_layer.size)
        init_image = self.image_layer.image
        self.assertNotEqual(new_image, init_image)
        self.assertTrue(image_is_fully_transparent(init_image))
        self.assert_no_signals()
        undo_count = UndoStack().undo_count()

        self.image_layer.image = new_image
        self.content_changed_mock.assert_called_once()
        self.size_changed_mock.assert_called_once()
        self.assertEqual(UndoStack().undo_count(), undo_count + 1)
        final_image = self.image_layer.image
        self.assertNotEqual(final_image, init_image)
        self.assertEqual(final_image, new_image)

    def test_borrow_image(self) -> None:
        """Test setting content with a QImage when using the borrow_image method"""
        new_image = QImage(INIT_IMAGE).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        self.assertNotEqual(new_image, self.image_layer.size)
        init_image = self.image_layer.image
        self.assertNotEqual(new_image, init_image)
        self.assertTrue(image_is_fully_transparent(init_image))
        self.assert_no_signals()
        self.assertEqual(0, UndoStack().undo_count())

        with self.image_layer.borrow_image() as edited_image:
            painter = QPainter(edited_image)
            painter.drawImage(QPoint(), new_image)
            painter.end()

        self.size_changed_mock.assert_not_called()
        self.content_changed_mock.assert_called_once()
        self.assertEqual(1, UndoStack().undo_count())
        expected_image = new_image.copy(QRect(QPoint(), IMG_SIZE))
        final_image = self.image_layer.image
        self.assertNotEqual(final_image, init_image)
        self.assertEqual(expected_image, final_image)