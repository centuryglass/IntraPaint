"""Tests the ImageStack module"""
import sys
from unittest.mock import MagicMock

from typing import cast

from PySide6.QtCore import QSize, QRect, QPoint, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer_group import LayerGroup
from src.image.layers.selection_layer import SelectionLayer
from src.image.layers.transform_layer import TransformLayer
from src.image.open_raster import read_ora_image
from src.undo_stack import UndoStack
from src.util.visual.image_utils import create_transparent_image
from test.base_test_case import IntraPaintTestCase

IMG_SIZE = QSize(512, 512)
GEN_AREA_SIZE = QSize(300, 300)
MIN_GEN_AREA = QSize(8, 8)
MAX_GEN_AREA = QSize(999, 999)

INIT_IMAGE = 'test/resources/test_images/source.png'
LAYER_MOVE_TEST_IMAGE = 'test/resources/test_images/layer_move_test.ora'
LAYER_MOVE_TEST_PNG = 'test/resources/test_images/layer_move_test.png'
SELECTION_PNG = 'test/resources/test_images/selected_test.png'
SELECTION_CLEARED_PNG = 'test/resources/test_images/selected_clear_test.png'
app = QApplication.instance() or QApplication(sys.argv)


class ImageStackTest(IntraPaintTestCase):
    """Tests the ImageStack module"""

    def setUp(self) -> None:
        super().setUp()
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
        self.assertEqual(self.image_stack.active_layer, self.image_stack.layer_stack)
        self.assertEqual(self.image_stack.active_layer_id, self.image_stack.layer_stack.id)
        self.assertEqual(self.image_stack.top_level_layers, [])
        layer_list = self.image_stack.layers
        self.assertEqual(len(layer_list), 1)
        # Layer stack should be only layer, name should sync with last file
        layer_stack = layer_list[0]
        self.assertIsInstance(layer_stack, LayerGroup)
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
        # image should be transparent:
        self.assertEqual(self.image_stack.qimage(), create_transparent_image(IMG_SIZE))
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
        image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        self.assertEqual(self.image_stack.qimage(), image)
        layer = self.image_stack.active_layer
        from src.image.layers.image_layer import ImageLayer
        self.assertIsInstance(layer, ImageLayer)
        assert layer is not None
        self.assertEqual(layer.image, image)

    def test_layer_create(self) -> None:
        """Test creating new layers and layer groups"""

        # Create layer from image:
        image = QImage(INIT_IMAGE)
        layer_0 = self.image_stack.create_layer(None, image)
        image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        self.layer_added_mock.assert_called_once()
        self.content_changed_mock.assert_called_once()
        self.active_layer_changed_mock.assert_called_with(layer_0)
        self.assertEqual(self.image_stack.active_layer_id, layer_0.id)
        self.assertEqual(self.image_stack.active_layer, layer_0)
        self.assertEqual(1, self.image_stack.count)
        # size wasn't updated, so image will be cropped to initial size:
        self.assertEqual(self.image_stack.qimage(), image.copy(QRect(QPoint(), IMG_SIZE)))
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
        self.image_stack.move_layer_by_offset(1)
        self.assertEqual(-1, layer_1.z_value)
        self.assertEqual(-2, layer_group.z_value)
        self.assertEqual(-3, inner_group.z_value)
        self.assertEqual(-4, layer_0.z_value)
        self.assertEqual(self.image_stack._layer_stack, layer_0.layer_parent)

        # Move up to top:
        self.image_stack.move_layer_by_offset(-1)
        self.assertEqual(-4, layer_0.z_value)
        self.assertEqual(layer_group, layer_0.layer_parent)

        self.image_stack.move_layer_by_offset(-1)
        self.assertEqual(-4, layer_0.z_value)
        self.assertEqual(inner_group, layer_0.layer_parent)

        self.image_stack.move_layer_by_offset(-1)
        self.assertEqual(-3, layer_0.z_value)
        self.assertEqual(layer_group, layer_0.layer_parent)

        self.image_stack.move_layer_by_offset(-1)
        self.assertEqual(-2, layer_0.z_value)
        self.assertEqual(self.image_stack._layer_stack, layer_0.layer_parent)

        self.image_stack.move_layer_by_offset(-1)
        self.assertEqual(-1, layer_0.z_value)

        # No change moving up from top:
        self.image_stack.move_layer_by_offset(-1)
        self.assertEqual(-1, layer_0.z_value)
        self.assertEqual(-2, layer_1.z_value)
        self.assertEqual(-3, layer_group.z_value)
        self.assertEqual(-4, inner_group.z_value)

        # Move back to bottom:
        self.image_stack.move_layer_by_offset(1)
        self.assertEqual(-2, layer_0.z_value)

        self.image_stack.move_layer_by_offset(1)
        self.assertEqual(-3, layer_0.z_value)
        self.assertEqual(layer_group, layer_0.layer_parent)

        self.image_stack.move_layer_by_offset(1)
        self.assertEqual(-4, layer_0.z_value)
        self.assertEqual(inner_group, layer_0.layer_parent)

        self.image_stack.move_layer_by_offset(1)
        self.assertEqual(-4, layer_0.z_value)
        self.assertEqual(layer_group, layer_0.layer_parent)

        self.image_stack.move_layer_by_offset(1)
        self.assertEqual(-4, layer_0.z_value)
        self.assertEqual(self.image_stack._layer_stack, layer_0.layer_parent)

    def test_transform_rendering(self) -> None:
        """Confirm that image rendering properly supports complex transformed nested layer groups."""
        read_ora_image(self.image_stack, LAYER_MOVE_TEST_IMAGE)
        group_count = 0
        image_count = 0
        for layer in self.image_stack.layers:
            # Confirm that all the layers have transformations:
            if isinstance(layer, TransformLayer):
                self.assertFalse(layer.transform.isIdentity())
                image_count += 1
            elif isinstance(layer, LayerGroup):
                group_count += 1
        self.assertEqual(3, group_count)
        self.assertEqual(8, image_count)
        output_image = self.image_stack.qimage()
        self.assertEqual(output_image.size(), self.image_stack.size)
        self.assert_image_matches_golden(output_image, LAYER_MOVE_TEST_PNG)

    def test_copy_paste_selected(self) -> None:
        """Confirm that copying selected layer content properly supports complex transformed nested layer groups."""
        read_ora_image(self.image_stack, LAYER_MOVE_TEST_IMAGE)
        selection_bounds = QRect(50, self.image_stack.height // 6 * 4, self.image_stack.width - 80, 160)
        with self.image_stack.selection_layer.borrow_image() as mask_image:
            painter = QPainter(mask_image)
            painter.fillRect(selection_bounds, Qt.GlobalColor.black)
            painter.end()
        self.image_stack.active_layer = self.image_stack.layer_stack
        self.image_stack.copy_selected()
        self.image_stack.paste()
        pasted_layer = self.image_stack.active_layer
        self.assertEqual(pasted_layer.name, 'Paste layer')
        self.assert_image_matches_golden(pasted_layer.image, SELECTION_PNG)

    def test_clear_selected(self) -> None:
        """Confirm that clearing selected layer content properly supports complex transformed nested layer groups."""
        read_ora_image(self.image_stack, LAYER_MOVE_TEST_IMAGE)
        selection_bounds = QRect(50, self.image_stack.height // 6 * 4, self.image_stack.width - 80, 160)
        with self.image_stack.selection_layer.borrow_image() as mask_image:
            painter = QPainter(mask_image)
            painter.fillRect(selection_bounds, Qt.GlobalColor.black)
            painter.end()
        self.image_stack.active_layer = self.image_stack.layer_stack
        self.image_stack.clear_selected()
        self.assert_image_matches_golden(self.image_stack.qimage(crop_to_image=False), SELECTION_CLEARED_PNG)

    def test_borrow_layer_image(self) -> None:
        """Confirm that setting layer images within the stack still works correctly"""
        read_ora_image(self.image_stack, LAYER_MOVE_TEST_IMAGE)
        new_content = QImage(QSize(512, 512), QImage.Format.Format_ARGB32_Premultiplied)
        new_content.fill(Qt.GlobalColor.red)

        first_image_layer = self.image_stack.image_layers[0]
        self.image_stack.active_layer = first_image_layer
        layer_image = first_image_layer.image
        layer_size = first_image_layer.size
        self.assertNotEqual(layer_image, new_content)
        self.assertEqual(1, UndoStack().undo_count())
        UndoStack().clear()
        self.assertEqual(0, UndoStack().undo_count())

        self.assertTrue(first_image_layer.visible)
        self.assertFalse(first_image_layer.locked)
        self.assertFalse(first_image_layer.alpha_locked)
        self.assertFalse(layer_size.isEmpty())

        with first_image_layer.borrow_image() as edited_image:
            painter = QPainter(edited_image)
            painter.drawImage(QPoint(), new_content)
            painter.end()

        expected_image = layer_image.copy()
        painter = QPainter(expected_image)
        painter.fillRect(QRect(QPoint(), new_content.size()), Qt.GlobalColor.red)
        painter.end()
        final_image = first_image_layer.image
        self.assertNotEqual(final_image, layer_image)
        self.assertEqual(expected_image, final_image)
        self.assertEqual(1, UndoStack().undo_count())

    def test_merge_group(self) -> None:
        """Merge group should replace a layer group with a single image layer."""
        group = self.image_stack.create_layer_group('group')
        top = self.image_stack.create_layer('top', layer_parent=group)
        bottom = self.image_stack.create_layer('bottom', layer_parent=group)
        with top.borrow_image() as image:
            painter = QPainter(image)
            painter.fillRect(QRect(10, 10, 40, 40), Qt.GlobalColor.red)
            painter.end()
        with bottom.borrow_image() as image:
            painter = QPainter(image)
            painter.fillRect(QRect(20, 20, 40, 40), Qt.GlobalColor.blue)
            painter.end()

        before = self.image_stack.qimage(crop_to_image=False)
        self.image_stack.active_layer = group
        UndoStack().clear()
        self.image_stack.merge_group()
        active = self.image_stack.active_layer
        self.assertIsInstance(active, ImageLayer)
        self.assertEqual(active.name, 'group')
        self.assertEqual(1, self.image_stack.count)
        self.assertEqual(before, self.image_stack.qimage(crop_to_image=False))

        UndoStack().undo()
        self.assertEqual(1, self.image_stack.count)
        self.assertIsInstance(self.image_stack.layer_stack.child_layers[0], LayerGroup)
        self.assertEqual(2, cast(LayerGroup, self.image_stack.layer_stack.child_layers[0]).count)

    def test_merge_all_visible(self) -> None:
        """Merge all visible should combine visible layers and preserve hidden ones."""
        hidden = self.image_stack.create_layer('hidden')
        visible_a = self.image_stack.create_layer('a')
        visible_b = self.image_stack.create_layer('b')
        hidden.set_visible(False)
        with visible_a.borrow_image() as image:
            painter = QPainter(image)
            painter.fillRect(QRect(0, 0, 50, 50), Qt.GlobalColor.red)
            painter.end()
        with visible_b.borrow_image() as image:
            painter = QPainter(image)
            painter.fillRect(QRect(25, 25, 50, 50), Qt.GlobalColor.green)
            painter.end()
        with hidden.borrow_image() as image:
            painter = QPainter(image)
            painter.fillRect(QRect(100, 100, 30, 30), Qt.GlobalColor.blue)
            painter.end()

        before_visible = self.image_stack.qimage(crop_to_image=False)
        UndoStack().clear()
        self.image_stack.merge_all_visible()
        self.assertEqual(2, self.image_stack.count)
        layers = self.image_stack.layer_stack.child_layers
        self.assertIsInstance(layers[0], ImageLayer)
        self.assertEqual(layers[0].name, 'Merged')
        self.assertFalse(layers[1].visible)
        self.assertEqual(layers[1].name, 'hidden')
        self.assertEqual(before_visible, self.image_stack.qimage(crop_to_image=False))

        UndoStack().undo()
        self.assertEqual(3, self.image_stack.count)
        restored_names = [layer.name for layer in self.image_stack.layer_stack.child_layers]
        self.assertEqual(['a', 'b', 'hidden'], restored_names)

