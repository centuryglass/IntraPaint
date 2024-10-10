"""Tests the ImageLayer class"""
import os
import sys
import unittest
from unittest.mock import MagicMock

from PySide6.QtCore import QSize, QRect, QPoint
from PySide6.QtGui import QImage, QPainter, QTransform, Qt
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.composite_mode import CompositeMode
from src.image.layers.image_layer import ImageLayer
from src.undo_stack import UndoStack
from src.util.visual.geometry_utils import map_rect_precise
from src.util.visual.image_utils import image_is_fully_transparent, create_transparent_image

IMG_SIZE = QSize(512, 512)
LAYER_NAME = 'test layer'
INIT_IMAGE = 'test/resources/test_images/source.png'
TRANSFORM_TEST_IMAGE = 'test/resources/test_images/render_transform_1.png'
app = QApplication.instance() or QApplication(sys.argv)

def save_temporary(name, expected, actual):
    expected.save(f'expected_{name}.png')
    actual.save(f'actual_{name}.png')

def clear_temporary(name):
    for img_path in (f'expected_{name}.png', f'actual_{name}.png'):
        if os.path.isfile(img_path):
            os.remove(img_path)

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
        self.content_changed_mock.assert_called()
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

    # Render testing, no base image:

    def test_basic_render(self) -> None:
        """Test basic rendering with no complicating factors."""
        init_image = QImage(INIT_IMAGE).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        self.image_layer.image = init_image
        render = self.image_layer.render_to_new_image()
        self.assertEqual(init_image, render)

    def test_bounded_render(self) -> None:
        """Test rendering when image bounds are defined."""
        init_image = QImage(INIT_IMAGE).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        self.image_layer.image = init_image
        bounds = QRect(50, 5, 100, 150)
        expected_image = self.image_layer.image.copy(bounds)
        render = self.image_layer.render_to_new_image(inner_bounds=bounds)
        save_temporary('test_bounded_render', expected_image, render)
        self.assertEqual(expected_image, render)
        clear_temporary('test_bounded_render')

    def test_transformed_render(self) -> None:
        """Test rendering when a transformation is provided."""
        init_image = QImage(INIT_IMAGE).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        self.image_layer.image = init_image
        transform = (QTransform.fromTranslate(5, 10) * QTransform.fromScale(.5, 1)
                     * QTransform().rotate(50))

        source_bounds = QRect(QPoint(), init_image.size())
        final_bounds = map_rect_precise(source_bounds, transform).toAlignedRect()
        painter_transform = transform * QTransform.fromTranslate(-final_bounds.x(), - final_bounds.y())
        assert map_rect_precise(source_bounds, painter_transform).toAlignedRect() == QRect(QPoint(), final_bounds.size())
        transform_image = create_transparent_image(final_bounds.size())
        painter = QPainter(transform_image)
        painter.setTransform(painter_transform)
        painter.drawImage(source_bounds, self.image_layer.image)
        painter.end()

        render = self.image_layer.render_to_new_image(transform=transform)
        save_temporary('test_transformed_render', transform_image, render)
        self.assertEqual(transform_image, render)
        clear_temporary('test_transformed_render')

        # Results should be the same when the transform is applied through the layer instead of the render function
        self.image_layer.transform = transform
        render2 = self.image_layer.render_to_new_image()

        save_temporary('test_transformed_render_owntransform', transform_image, render2)
        self.assertEqual(transform_image, render2)
        clear_temporary('test_transformed_render_owntransform')

    def test_render_with_transform_and_bounds(self) -> None:
        """Test rendering with both transformation and rendering bounds"""

        init_image = QImage(INIT_IMAGE).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        self.image_layer.image = init_image
        transform = (QTransform.fromTranslate(5, 10) * QTransform.fromScale(.5, 1)
                     * QTransform().rotate(50))
        image_bounds = QRect(50, 50, 100, 100)
        source_bounds = QRect(QPoint(), init_image.size())
        final_bounds = map_rect_precise(source_bounds, transform).toAlignedRect().intersected(image_bounds)

        expected_image = create_transparent_image(final_bounds.size())
        painter_transform = transform * QTransform.fromTranslate(-final_bounds.x(), -final_bounds.y())
        painter = QPainter(expected_image)
        painter.setTransform(painter_transform)
        painter.drawImage(source_bounds, self.image_layer.image)
        painter.end()

        render = self.image_layer.render_to_new_image(transform=transform, inner_bounds=image_bounds)
        save_temporary('test_render_with_transform_and_bounds', expected_image, render)
        self.assertEqual(render.size(), image_bounds.size())
        self.assertEqual(expected_image, render)
        clear_temporary('test_render_with_transform_and_bounds')

    def test_render_onto_base(self):
        """"Test rendering onto a pre-existing base"""
        init_image = QImage(INIT_IMAGE).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        self.image_layer.image = init_image
        base_image = QImage(IMG_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
        base_image.fill(Qt.GlobalColor.red)

        expected_image = base_image.copy()
        painter = QPainter(expected_image)
        painter.drawImage(0, 0, init_image)
        painter.end()

        self.image_layer.render(base_image=base_image)
        save_temporary('test_render_onto_base', expected_image, base_image)
        self.assertEqual(expected_image, base_image)
        clear_temporary('test_render_onto_base')

    def test_render_onto_base_with_bounds(self):
        """"Test rendering onto a pre-existing base, with render bounds provided"""
        init_image = QImage(INIT_IMAGE).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        self.image_layer.image = init_image
        base_image = QImage(IMG_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
        base_image.fill(Qt.GlobalColor.red)

        image_bounds = QRect(50, 50, 100, 100)

        expected_image = base_image.copy()
        painter = QPainter(expected_image)
        painter.drawImage(image_bounds, init_image, image_bounds)
        painter.end()

        self.image_layer.render(base_image=base_image, image_bounds=image_bounds)
        save_temporary('test_render_onto_base_with_bounds', expected_image, base_image)
        self.assertEqual(expected_image, base_image)
        clear_temporary('test_render_onto_base_with_bounds')

    def test_render_onto_base_with_transform_and_bounds(self):
        """"Test rendering onto a pre-existing base, with render bounds provided"""
        init_image = QImage(INIT_IMAGE).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        self.image_layer.image = init_image
        base_image = QImage(IMG_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
        base_image.fill(Qt.GlobalColor.red)
        image_bounds = QRect(50, 50, 100, 100)

        # Apply the transformation, then copy into the render bounds
        transform = QTransform.fromTranslate(5, 10) * QTransform.fromScale(2, 1.5)
        source_bounds = QRect(QPoint(), init_image.size())
        final_bounds = map_rect_precise(source_bounds, transform).toAlignedRect().united(source_bounds)

        transform_image = create_transparent_image(final_bounds.size())
        painter = QPainter(transform_image)
        painter.setTransform(transform)
        painter.drawImage(source_bounds, self.image_layer.image)
        painter.end()

        expected_image = base_image.copy()
        painter = QPainter(expected_image)
        painter.drawImage(image_bounds, transform_image, image_bounds)
        painter.end()

        # Confirm that the rendered layer matches:
        self.image_layer.render(base_image=base_image, transform=transform, image_bounds=image_bounds)
        save_temporary('test_render_onto_base_with_transform_and_bounds', expected_image, base_image)
        self.assertEqual(expected_image, base_image)
        clear_temporary('test_render_onto_base_with_transform_and_bounds')

    def test_render_onto_base_with_transform_and_bounds_masked(self):
        """"Test rendering onto a pre-existing base, with render bounds provided, and with a transformation that will
        need to be masked internally to conform to the bounds."""
        init_image = QImage(INIT_IMAGE).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        self.image_layer.image = init_image
        # self.image_layer.composition_mode = CompositeMode.LUMINOSITY
        base_image = QImage(IMG_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
        base_image.fill(Qt.GlobalColor.red)

        image_bounds = QRect(50, 50, 100, 100)

        transform = (QTransform.fromTranslate(5, 10) * QTransform.fromScale(2, 1.5)
                     * QTransform().rotate(50))
        source_bounds = QRect(QPoint(), init_image.size())
        final_bounds = map_rect_precise(source_bounds, transform).toAlignedRect().united(source_bounds)

        transform_image = create_transparent_image(final_bounds.size())
        painter = QPainter(transform_image)
        painter.setTransform(transform)
        painter.drawImage(source_bounds, self.image_layer.image)
        painter.end()

        expected_image = base_image.copy()
        painter = QPainter(expected_image)
        painter.drawImage(image_bounds, transform_image, image_bounds)
        painter.end()

        self.image_layer.render(base_image=base_image, transform=transform, image_bounds=image_bounds)
        save_temporary('test_render_onto_base_with_transform_and_bounds_masked', expected_image, base_image)
        self.assertEqual(expected_image, base_image)
        clear_temporary('test_render_onto_base_with_transform_and_bounds_masked')
