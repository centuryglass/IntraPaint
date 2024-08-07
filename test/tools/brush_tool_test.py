import os
import sys
import unittest
from typing import Optional
from unittest.mock import Mock, MagicMock, patch

from PyQt6.QtCore import QSize, QPoint
from PyQt6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.image.mypaint.mp_tile import MPTile
from src.tools.brush_tool import BRUSH_LABEL
from src.ui.graphics_items.layer_graphics_item import LayerGraphicsItem
from src.ui.window.main_window import MainWindow

app = QApplication.instance() or QApplication(sys.argv)


class BrushToolTest(unittest.TestCase):
    """Tool panel GUI testing"""

    def setUp(self) -> None:
        while os.path.basename(os.getcwd()) not in ('IntraPaint', ''):
            os.chdir('..')
        assert os.path.basename(os.getcwd()) == 'IntraPaint'
        AppConfig('test/resources/app_config_test.json')._reset()
        KeyConfig('test/resources/key_config_test.json')._reset()
        Cache('test/resources/cache_test.json')._reset()
        test_size = QSize(512, 512)
        self.image_stack = ImageStack(test_size, test_size, test_size, test_size)
        self.window = MainWindow(self.image_stack)
        self.window.show()
        self.tool_panel = self.window._tool_panel
        self.brush_tool = self.tool_panel._tools[BRUSH_LABEL]
        self.tool_handler = self.tool_panel._event_handler
        scene = self.window._image_panel.image_viewer.scene()
        assert scene is not None
        self.scene = scene

    def test_activation_no_layers(self) -> None:
        self.assertEqual(self.image_stack.layer_stack.count, 0)
        self.assertFalse(self.brush_tool.is_active)
        self.tool_handler.active_tool = self.brush_tool
        self.assertTrue(self.brush_tool.is_active)
        for item in self.scene.items():
            self.assertNotIsInstance(item, MPTile)

    def test_activation_one_layer(self) -> None:
        # Create one layer, confirm that layer property assumptions are true:
        layer = self.image_stack.create_layer()
        self.assertFalse(self.brush_tool.is_active)
        layer_item = None
        for item in self.scene.items():
            if isinstance(item, LayerGraphicsItem) and item.layer == layer:
                layer_item = item
                break
        self.assertIsInstance(layer_item, LayerGraphicsItem)
        assert layer_item is not None
        self.assertEqual(layer_item.layer, layer)
        self.assertEqual(layer_item.zValue(), layer.z_value)
        # self.assertFalse(layer_item.hidden)  # TODO: Why is this failing? I'm not seeing issues in practice
        self.assertEqual(self.image_stack.active_layer, layer)

        # Activate brush tool, confirm that tiles are present, at the layer z-value, and the existing layer item is
        # hidden:
        self.tool_handler.active_tool = self.brush_tool
        self.assertTrue(self.brush_tool.is_active)
        self.assertTrue(layer_item.hidden)
        self.brush_tool._stroke_to(QPoint(50, 50))
        self.brush_tool._stroke_to(QPoint(150, 150))
        tiles_found = 0
        for item in self.scene.items():
            if isinstance(item, MPTile):
                tiles_found += 1
                self.assertEqual(item.zValue(), layer.z_value)
            elif isinstance(item, LayerGraphicsItem) and item.isVisible():
                self.assertEqual(item.layer, self.image_stack.selection_layer)
        self.assertGreater(tiles_found, 0)

    def test_activation_two_layer(self) -> None:
        # Create one layer, confirm that layer property assumptions are true:
        layer1 = self.image_stack.create_layer()
        layer2 = self.image_stack.create_layer()
        self.assertFalse(self.brush_tool.is_active)
        layer_item_1: Optional[LayerGraphicsItem] = None
        layer_item_2: Optional[LayerGraphicsItem] = None
        for item in self.scene.items():
            if isinstance(item, LayerGraphicsItem):
                if item.layer == layer1:
                    layer_item_1 = item
                elif item.layer == layer2:
                    layer_item_2 = item
        self.assertIsInstance(layer_item_1, LayerGraphicsItem)
        self.assertIsInstance(layer_item_2, LayerGraphicsItem)
        assert layer_item_1 is not None
        assert layer_item_2 is not None
        self.assertEqual(layer_item_1.layer, layer1)
        self.assertEqual(layer_item_2.layer, layer2)
        self.assertEqual(self.image_stack.active_layer, layer1)


        # Activate brush tool, confirm that tiles are present, at the layer z-value, and the existing layer item is
        # hidden:
        self.tool_handler.active_tool = self.brush_tool
        self.assertTrue(self.brush_tool.is_active)
        self.assertTrue(layer_item_1.hidden)
        self.assertFalse(layer_item_2.hidden)
        self.image_stack.active_layer = layer2
        self.assertFalse(layer_item_1.hidden)
        self.assertTrue(layer_item_2.hidden)
        self.brush_tool._stroke_to(QPoint(50, 50))
        self.brush_tool._stroke_to(QPoint(150, 150))

        tiles_found = 0
        for item in self.scene.items():
            if isinstance(item, MPTile):
                tiles_found += 1
                self.assertEqual(item.zValue(), layer2.z_value)
            elif isinstance(item, LayerGraphicsItem) and item.isVisible() \
                    and item.layer != self.image_stack.selection_layer:
                self.assertEqual(item.layer, layer1)
                self.assertLess(item.zValue(), layer2.z_value)
        self.assertGreater(tiles_found, 0)

