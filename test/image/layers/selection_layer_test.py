"""Tests SelectionLayer context pins: crop bounds, undo history, and how image size changes carry them."""
import sys
from unittest.mock import MagicMock

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.image.layers.image_stack import ImageStack
from src.image.layers.image_stack_utils import scale_all_layers
from src.image.layers.layer_resize_mode import LayerResizeMode
from src.undo_stack import UndoStack
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

IMAGE_SIZE = QSize(512, 512)
GENERATION_AREA = QRect(100, 100, 200, 200)
SELECTION_BOUNDS = QRect(150, 150, 20, 20)


class SelectionLayerContextPinTest(IntraPaintTestCase):
    """Tests context pins on the selection layer of an image stack."""

    def setUp(self) -> None:
        super().setUp()
        AppConfig().set(AppConfig.UNDO_MERGE_INTERVAL, 0.0)
        cache = Cache()
        cache.set(Cache.INPAINT_FULL_RES, True)
        cache.set(Cache.INPAINT_FULL_RES_PADDING, 0)
        self.image_stack = ImageStack(IMAGE_SIZE, GENERATION_AREA.size(), QSize(8, 8), QSize(1024, 1024))
        self.image_stack.generation_area = GENERATION_AREA
        self.selection_layer = self.image_stack.selection_layer
        self.pins_changed = MagicMock()
        self.selection_layer.context_pins_changed.connect(self.pins_changed)
        UndoStack().clear()

    def _select(self, bounds: QRect) -> None:
        with self.selection_layer.borrow_image() as mask_image:
            painter = QPainter(mask_image)
            painter.fillRect(bounds, Qt.GlobalColor.black)
            painter.end()

    def test_no_pins_crops_to_selection(self) -> None:
        """Without pins, a square selection inside a square area crops to the selection."""
        self._select(SELECTION_BOUNDS)
        self.assertEqual(self.selection_layer.get_selection_gen_area(), SELECTION_BOUNDS)

    def test_one_sided_pin_stretches_crop(self) -> None:
        """A pin to one side stretches the crop to include it, then the crop grows to the area's aspect ratio."""
        self._select(SELECTION_BOUNDS)
        self.selection_layer.add_context_pin(QPoint(200, 160))
        self.assertEqual(self.selection_layer.get_selection_gen_area(), QRect(QPoint(150, 135), QPoint(200, 185)))
        self.assertEqual(self.selection_layer.get_selection_gen_area(include_context_pins=False), SELECTION_BOUNDS)

    def test_pin_outside_area_clamps_to_area_edge(self) -> None:
        """A pin outside the generation area stretches the crop only as far as the area's edge."""
        self._select(SELECTION_BOUNDS)
        self.selection_layer.add_context_pin(QPoint(50, 160))
        self.assertEqual(self.selection_layer.get_selection_gen_area(), QRect(QPoint(100, 125), QPoint(169, 194)))

    def test_pins_without_selection_give_no_crop(self) -> None:
        """Pins alone don't make a crop: they only count while something is selected."""
        self.selection_layer.add_context_pin(QPoint(120, 120))
        self.selection_layer.add_context_pin(QPoint(250, 250))
        self.assertIsNone(self.selection_layer.get_selection_gen_area())

    def test_pins_count_with_full_res_ignored(self) -> None:
        """With ignore_config, pins stretch the crop even while inpaint full-res is off."""
        Cache().set(Cache.INPAINT_FULL_RES, False)
        self._select(SELECTION_BOUNDS)
        self.selection_layer.add_context_pin(QPoint(200, 160))
        self.assertIsNone(self.selection_layer.get_selection_gen_area())
        self.assertEqual(self.selection_layer.get_selection_gen_area(True), QRect(QPoint(150, 135), QPoint(200, 185)))

    def test_add_remove_clear_undo_redo(self) -> None:
        """Adding, removing and clearing pins are each one undoable step."""
        first = QPoint(10, 10)
        second = QPoint(20, 20)
        undo_stack = UndoStack()
        self.selection_layer.add_context_pin(first)
        self.selection_layer.add_context_pin(second)
        self.assertEqual(self.selection_layer.context_pins, [first, second])
        self.selection_layer.remove_context_pin(first)
        self.assertEqual(self.selection_layer.context_pins, [second])
        self.selection_layer.clear_context_pins()
        self.assertEqual(self.selection_layer.context_pins, [])
        self.assertEqual(undo_stack.undo_count(), 4)

        undo_stack.undo()
        self.assertEqual(self.selection_layer.context_pins, [second])
        undo_stack.undo()
        self.assertEqual(self.selection_layer.context_pins, [first, second])
        undo_stack.undo()
        self.assertEqual(self.selection_layer.context_pins, [first])
        undo_stack.redo()
        undo_stack.redo()
        self.assertEqual(self.selection_layer.context_pins, [second])
        self.pins_changed.assert_called_with([second])

    def test_duplicate_pin_adds_nothing(self) -> None:
        """Adding a pin where one already is changes nothing and records no undo step."""
        self.selection_layer.add_context_pin(QPoint(10, 10))
        self.selection_layer.add_context_pin(QPoint(10, 10))
        self.assertEqual(self.selection_layer.context_pins, [QPoint(10, 10)])
        self.assertEqual(UndoStack().undo_count(), 1)
        self.assertEqual(self.pins_changed.call_count, 1)

    def test_context_pin_near(self) -> None:
        """context_pin_near finds the closest pin within range of a point, measured from pixel centers."""
        self.selection_layer.set_context_pins([QPoint(10, 10), QPoint(14, 10)])
        self.assertEqual(self.selection_layer.context_pin_near(QPoint(11, 10), 3.0), QPoint(10, 10))
        self.assertEqual(self.selection_layer.context_pin_near(QPoint(14, 11), 3.0), QPoint(14, 10))
        self.assertIsNone(self.selection_layer.context_pin_near(QPoint(30, 30), 3.0))

    def test_select_none_keeps_pins(self) -> None:
        """Clearing the selection leaves pins in place."""
        self._select(SELECTION_BOUNDS)
        self.selection_layer.add_context_pin(QPoint(10, 10))
        self.selection_layer.clear()
        self.assertEqual(self.selection_layer.context_pins, [QPoint(10, 10)])

    def test_resize_canvas_moves_and_drops_pins(self) -> None:
        """Resizing the canvas moves pins with the image content and drops the ones left outside, undoably."""
        pins = [QPoint(10, 10), QPoint(100, 100), QPoint(400, 400)]
        self.selection_layer.set_context_pins(pins)
        self.image_stack.resize_canvas(QSize(300, 300), -50, -50, LayerResizeMode.RESIZE_NONE, False)
        self.assertEqual(self.selection_layer.context_pins, [QPoint(50, 50)])
        UndoStack().undo()
        self.assertEqual(self.selection_layer.context_pins, pins)

    def test_scale_moves_pins(self) -> None:
        """Scaling the image scales pin positions, undoably."""
        pins = [QPoint(10, 20), QPoint(511, 511)]
        self.selection_layer.set_context_pins(pins)
        scale_all_layers(self.image_stack, 256, 1024)
        self.assertEqual(self.selection_layer.context_pins, [QPoint(5, 40), QPoint(255, 1022)])
        UndoStack().undo()
        self.assertEqual(self.selection_layer.context_pins, pins)

    def test_load_image_clears_pins(self) -> None:
        """Loading a new image removes pins, and undoing the load restores them."""
        self.selection_layer.set_context_pins([QPoint(10, 10)])
        new_image = QImage(QSize(256, 256), QImage.Format.Format_ARGB32_Premultiplied)
        new_image.fill(Qt.GlobalColor.white)
        self.image_stack.load_image(new_image)
        self.assertEqual(self.selection_layer.context_pins, [])
        UndoStack().undo()
        self.assertEqual(self.selection_layer.context_pins, [QPoint(10, 10)])
