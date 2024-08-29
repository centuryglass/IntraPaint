import os
import sys
import unittest
from typing import Optional

from PySide6.QtCore import QSize, QPoint, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.image.mypaint.mypaint_scene_tile import MyPaintSceneTile
from src.tools.brush_tool import BrushTool
from src.ui.graphics_items.layer_graphics_item import LayerGraphicsItem
from src.ui.window.main_window import MainWindow
from src.undo_stack import UndoStack

app = QApplication.instance() or QApplication(sys.argv)


BRUSH_STROKE_IMAGE_PATH = 'test/resources/test_images/brush_test.png'
BRUSH_PATH = 'resources/brushes/classic/bulk.myb'


class BrushToolTest(unittest.TestCase):
    """Tool panel GUI testing"""

    def setUp(self) -> None:
        while os.path.basename(os.getcwd()) not in ('IntraPaint', ''):
            os.chdir('..')
        assert os.path.basename(os.getcwd()) == 'IntraPaint'
        AppConfig('test/resources/app_config_test.json')._reset()
        KeyConfig('test/resources/key_config_test.json')._reset()
        Cache('test/resources/cache_test.json')._reset()
        UndoStack().clear()
        test_size = QSize(512, 512)
        self.image_stack = ImageStack(test_size, test_size, test_size, test_size)
        self.window = MainWindow(self.image_stack)
        self.window.show()
        self.tool_panel = self.window._tool_panel
        self.brush_tool = self.tool_panel._tool_controller.find_tool_by_class(BrushTool)
        assert self.brush_tool is not None
        self.tool_handler = self.tool_panel._tool_controller
        self.canvas = self.brush_tool._canvas
        self.surface = self.canvas._mp_surface
        self.tiles = self.surface._tiles
        self.pending_tiles = self.surface._pending_changed_tiles

    def test_activation_no_layers(self) -> None:
        assert self.brush_tool is not None
        self.assertEqual(self.image_stack.layer_stack.count, 0)
        self.assertFalse(self.brush_tool.is_active)
        self.tool_handler.active_tool = self.brush_tool
        self.assertTrue(self.brush_tool.is_active)
        self.assertIsNotNone(self.canvas)
        self.assertIsNotNone(self.surface)
        self.assertEqual(len(self.tiles), 0)
        self.assertEqual(len(self.pending_tiles), 0)

    def test_activation_one_layer(self) -> None:
        # Create one layer, confirm that layer property assumptions are true:
        assert self.brush_tool is not None
        layer = self.image_stack.create_layer()
        self.image_stack.active_layer = layer
        self.assertFalse(self.brush_tool.is_active)

        # Activate brush tool, confirm that using the brush tool applies changes as expected:
        initial_image = layer.image

        self.tool_handler.active_tool = self.brush_tool
        self.assertTrue(self.brush_tool.is_active)
        self.assertFalse(layer.locked)
        self.assertFalse(layer.alpha_locked)
        self.assertFalse(layer.bounds.isEmpty())

        class _Event:
            def buttons(self):
                return Qt.MouseButton.LeftButton
        event = _Event()

        self.assertEqual(self.image_stack.active_layer, layer)
        self.assertEqual(self.brush_tool._layer, layer)
        self.assertEqual(self.canvas._layer, layer)
        self.assertEqual(self.surface._layer, layer)
        self.assertEqual(self.surface.brush.color.alpha(), 255)
        self.assertGreater(self.brush_tool.brush_size, 1)
        self.brush_tool.brush_size = 50
        self.surface.brush.load_file(BRUSH_PATH)

        UndoStack().clear()
        self.assertEqual(0, UndoStack().undo_count())

        self.brush_tool.mouse_click(event, QPoint(50, 50))
        for xy in range(50, 150, 5):
            self.brush_tool.mouse_move(event, QPoint(xy, xy))
            if xy == 100:
                self.assertGreater(len(self.pending_tiles), 0)
                for tile in self.pending_tiles:
                    self.assertTrue(not tile.bounds.isEmpty())
                    self.assertIn(tile, self.tiles.values())
        self.brush_tool.mouse_release(event, QPoint(150, 150))
        self.assertEqual(len(self.pending_tiles), 0)
        self.assertGreater(len(self.tiles), 0)
        self.assertEqual(1, UndoStack().undo_count())

        final_image = layer.image
        self.assertNotEqual(initial_image, final_image)
        expected_image = QImage(BRUSH_STROKE_IMAGE_PATH).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        self.assertEqual(expected_image, final_image)

    def test_activation_two_layer(self) -> None:
        # Create one layer, confirm that layer property assumptions are true:
        assert self.brush_tool is not None
        layer1 = self.image_stack.create_layer()
        layer2 = self.image_stack.create_layer()
        group = self.image_stack.create_layer_group('group')

        # Activate brush tool, confirm that it connects whenever an image layer is active, but not when a group is
        self.tool_handler.active_tool = self.brush_tool
        self.assertTrue(self.brush_tool.is_active)

        self.image_stack.active_layer = self.image_stack.layer_stack
        self.assertIsNone(self.brush_tool._layer)

        self.image_stack.active_layer = layer1
        self.assertEqual(layer1, self.brush_tool._layer)
        self.image_stack.active_layer = group
        self.assertIsNone(self.brush_tool._layer)
        self.image_stack.active_layer = layer2
        self.assertEqual(layer2, self.brush_tool._layer)


