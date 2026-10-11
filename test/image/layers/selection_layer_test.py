"""Tests SelectionLayer: context pins, bounds, 1-bit thresholding, select/clear/invert, grow/shrink, outline geometry
and undo of each.

The operation tests pin observable results (the selected pixel mask, pixel values and outline polygons) so a change to
how the layer stores its mask (#26) must reproduce them.
"""
import sys
from typing import Callable, Optional
from unittest.mock import MagicMock

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QRect, QSize, Qt, QRectF
from PySide6.QtGui import QImage, QPainter, QColor, QPainterPath
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.image.layers.image_stack import ImageStack
from src.image.layers.image_stack_utils import scale_all_layers
from src.image.layers.layer_resize_mode import LayerResizeMode
from src.image.layers.selection_layer import SelectionLayer
from src.undo_stack import UndoStack
from src.util.visual.image_utils import image_data_as_numpy_8bit
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

IMAGE_SIZE = QSize(512, 512)
GENERATION_AREA = QRect(100, 100, 200, 200)
SELECTION_BOUNDS = QRect(150, 150, 20, 20)


class SelectionLayerContextPinTest(IntraPaintTestCase):
    """Tests context pins on the selection layer of an image stack."""

    def setUp(self) -> None:
        super().setUp()
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

    def test_selection_bounds_cover_whole_image(self) -> None:
        """get_selection_bounds includes selected pixels outside the generation area, and is None when empty."""
        self.assertIsNone(self.selection_layer.get_selection_bounds())
        self._select(SELECTION_BOUNDS)
        self._select(QRect(400, 20, 10, 10))
        self.assertEqual(self.selection_layer.get_selection_bounds(), QRect(QPoint(150, 20), QPoint(409, 169)))

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


class SelectionLayerContentBoundsTest(IntraPaintTestCase):
    """Tests SelectionLayer.get_content_bounds across the whole image."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(IMAGE_SIZE, GENERATION_AREA.size(), QSize(8, 8), QSize(1024, 1024))
        self.image_stack.generation_area = GENERATION_AREA
        self.selection_layer = self.image_stack.selection_layer

    def _select(self, bounds: QRect, color: Qt.GlobalColor = Qt.GlobalColor.black) -> None:
        with self.selection_layer.borrow_image() as mask_image:
            painter = QPainter(mask_image)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            painter.fillRect(bounds, color)
            painter.end()

    def test_empty_selection(self) -> None:
        """Nothing selected gives an empty rect."""
        self.assertTrue(self.selection_layer.get_content_bounds().isEmpty())

    def test_single_region(self) -> None:
        """One region gives its exact pixel bounds."""
        self._select(SELECTION_BOUNDS)
        self.assertEqual(self.selection_layer.get_content_bounds(), SELECTION_BOUNDS)

    def test_separate_regions_are_united(self) -> None:
        """Two disjoint regions give the rect covering both, including regions outside the generation area."""
        self._select(QRect(10, 10, 20, 20))
        self._select(QRect(400, 450, 20, 20))
        self.assertEqual(self.selection_layer.get_content_bounds(), QRect(QPoint(10, 10), QPoint(419, 469)))

    def test_region_with_hole(self) -> None:
        """A selection with a hole gives the outer bounds, not the hole's."""
        self._select(QRect(100, 100, 100, 100))
        self._select(QRect(130, 130, 40, 40), Qt.GlobalColor.transparent)
        self.assertEqual(self.selection_layer.get_content_bounds(), QRect(100, 100, 100, 100))


SMALL_SIZE = QSize(32, 32)
SMALL_RECT = QRect(QPoint(), SMALL_SIZE)


def selection_mask(layer: SelectionLayer) -> np.ndarray:
    """Returns a (height, width) bool array of selected pixels."""
    return image_data_as_numpy_8bit(layer.image)[:, :, 3] > 0


def rect_mask(*rects: QRect, size: QSize = SMALL_SIZE) -> np.ndarray:
    """Returns a bool mask with every pixel in rects set."""
    mask = np.zeros((size.height(), size.width()), dtype=bool)
    for rect in rects:
        rect = rect.intersected(QRect(QPoint(), size))
        mask[rect.y():rect.y() + rect.height(), rect.x():rect.x() + rect.width()] = True
    return mask


def outline_mask(layer: SelectionLayer) -> np.ndarray:
    """Rasterizes the outline polygons with the odd-even rule, giving the pixels the outline encloses.

    Outline vertices lie on pixel edges, so an outline that traces the selection exactly rasterizes to the selection.
    """
    image = QImage(layer.size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    path = QPainterPath()
    path.setFillRule(Qt.FillRule.OddEvenFill)
    for polygon in layer.outline:
        path.addPolygon(polygon)
    painter = QPainter(image)
    painter.fillPath(path, Qt.GlobalColor.black)
    painter.end()
    return image_data_as_numpy_8bit(image)[:, :, 3] > 0


class SelectionLayerOperationTestCase(IntraPaintTestCase):
    """Shared setup for selection operation tests: a 32x32 image stack whose generation area covers the image."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(SMALL_SIZE, SMALL_SIZE, QSize(8, 8), QSize(64, 64))
        self.selection_layer = self.image_stack.selection_layer
        UndoStack().clear()

    def _paint(self, rect: QRect, color: QColor | Qt.GlobalColor = Qt.GlobalColor.black,
               mode: QPainter.CompositionMode = QPainter.CompositionMode.CompositionMode_Source,
               bounded: bool = True) -> None:
        """Fills rect in the selection layer through borrow_image, passing rect as the change bounds if bounded."""
        with self.selection_layer.borrow_image(rect if bounded else None) as image:
            assert image is not None
            painter = QPainter(image)
            painter.setCompositionMode(mode)
            painter.fillRect(rect, color)
            painter.end()

    def assert_mask_equal(self, actual: np.ndarray, expected: np.ndarray, msg: str = '') -> None:
        """Asserts two bool masks match, naming a few differing (y, x) pixels if they don't."""
        if not np.array_equal(actual, expected):
            diff = np.argwhere(actual != expected)
            self.fail(f'{msg} {len(diff)} pixels differ, first (y, x): {diff[:8].tolist()}')

    def assert_selection(self, expected: np.ndarray, msg: str = '') -> None:
        """Asserts the selected pixels, the pixels the outline encloses, and get_selection_bounds all match expected."""
        self.assert_mask_equal(selection_mask(self.selection_layer), expected, f'{msg} selection:')
        self.assert_mask_equal(outline_mask(self.selection_layer), expected, f'{msg} outline:')
        bounds = self.selection_layer.get_selection_bounds()
        if not expected.any():
            self.assertIsNone(bounds, msg)
            self.assertEqual(self.selection_layer.outline, [], msg)
            return
        rows = np.flatnonzero(expected.any(axis=1))
        cols = np.flatnonzero(expected.any(axis=0))
        expected_bounds = QRect(QPoint(int(cols[0]), int(rows[0])), QPoint(int(cols[-1]), int(rows[-1])))
        self.assertEqual(bounds, expected_bounds, msg)
        outline_bounds = QRectF()
        for polygon in self.selection_layer.outline:
            outline_bounds = outline_bounds.united(polygon.boundingRect())
        self.assertEqual(outline_bounds, QRectF(expected_bounds), msg)


class SelectionLayerThresholdTest(SelectionLayerOperationTestCase):
    """Tests that every write leaves the layer 1-bit: any alpha above zero is selected in the selection color."""

    @staticmethod
    def _alpha_gradient(size: QSize = SMALL_SIZE) -> QImage:
        """Returns an image whose alpha is 8 * column with varied colors, so only column 0 is transparent."""
        pixels = np.zeros((size.height(), size.width(), 4), dtype=np.uint8)
        for x in range(size.width()):
            alpha = 8 * x
            pixels[:, x] = (alpha // 2, alpha // 3, alpha, alpha)  # premultiplied BGRA
        return QImage(pixels.data, size.width(), size.height(), QImage.Format.Format_ARGB32_Premultiplied).copy()

    def _assert_thresholded(self, expected: np.ndarray) -> None:
        pixels = image_data_as_numpy_8bit(self.selection_layer.image)
        color = QColor(AppConfig().get(AppConfig.SELECTION_COLOR))
        self.assertTrue(np.all(pixels[expected] == (color.blue(), color.green(), color.red(), 255)))
        self.assertTrue(np.all(pixels[~expected] == 0))
        self.assert_selection(expected)

    def test_set_image_thresholds(self) -> None:
        """set_image selects every pixel with alpha above zero, in the opaque selection color."""
        self.selection_layer.set_image(self._alpha_gradient())
        self._assert_thresholded(rect_mask(QRect(1, 0, 31, 32)))

    def test_image_property_thresholds(self) -> None:
        """Assigning layer.image thresholds the same way."""
        self.selection_layer.image = self._alpha_gradient()
        self._assert_thresholded(rect_mask(QRect(1, 0, 31, 32)))

    def test_borrow_image_thresholds(self) -> None:
        """Content drawn through borrow_image with alpha 1 becomes fully selected."""
        self._paint(QRect(4, 6, 5, 3), QColor(0, 0, 255, 1))
        self._assert_thresholded(rect_mask(QRect(4, 6, 5, 3)))

    def test_borrow_image_thresholds_whole_layer(self) -> None:
        """borrow_image with no change bounds thresholds the whole layer."""
        self._paint(QRect(4, 6, 5, 3), QColor(0, 255, 0, 1), bounded=False)
        self._assert_thresholded(rect_mask(QRect(4, 6, 5, 3)))

    def test_inserted_image_thresholds(self) -> None:
        """An image pasted in with insert_image_content is thresholded inside its bounds."""
        self.selection_layer.insert_image_content(self._alpha_gradient(QSize(8, 8)), QRect(10, 10, 8, 8))
        self._assert_thresholded(rect_mask(QRect(11, 10, 7, 8)))

    def test_select_layer_content(self) -> None:
        """ImageStack.select_layer_content selects every pixel of the layer with alpha above zero."""
        layer_image = QImage(SMALL_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
        layer_image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(layer_image)
        painter.fillRect(QRect(3, 3, 6, 6), QColor(255, 255, 255, 1))
        painter.fillRect(QRect(20, 2, 4, 10), Qt.GlobalColor.blue)
        painter.end()
        layer = self.image_stack.create_layer('content', layer_image)
        self.image_stack.select_layer_content(layer)
        self._assert_thresholded(rect_mask(QRect(3, 3, 6, 6), QRect(20, 2, 4, 10)))


class SelectionLayerBooleanTest(SelectionLayerOperationTestCase):
    """Tests select all, clear, invert, and adding or subtracting regions."""

    def test_select_all(self) -> None:
        """select_all selects every pixel, outlined by one polygon around the image."""
        self._paint(QRect(4, 4, 4, 4))
        self.selection_layer.select_all()
        self.assert_selection(rect_mask(SMALL_RECT))
        self.assertEqual(len(self.selection_layer.outline), 1)
        self.assertTrue(self.selection_layer.generation_area_fully_selected())

    def test_clear(self) -> None:
        """clear leaves nothing selected and no outline."""
        self.selection_layer.select_all()
        self.selection_layer.clear()
        self.assert_selection(rect_mask())
        self.assertTrue(self.selection_layer.generation_area_is_empty())

    def test_invert(self) -> None:
        """invert_selection selects exactly the unselected pixels, and inverting twice restores the selection."""
        self._paint(QRect(4, 4, 10, 6))
        self._paint(QRect(20, 20, 3, 3))
        original = selection_mask(self.selection_layer)
        self.selection_layer.invert_selection()
        self.assert_selection(~original)
        self.selection_layer.invert_selection()
        self.assert_selection(original)

    def test_invert_empty_and_full(self) -> None:
        """Inverting nothing selects everything, and inverting everything selects nothing."""
        self.selection_layer.invert_selection()
        self.assert_selection(rect_mask(SMALL_RECT))
        self.selection_layer.invert_selection()
        self.assert_selection(rect_mask())

    def test_add_region(self) -> None:
        """Painting over the selection adds to it, merging overlapping regions into one outline."""
        self._paint(QRect(4, 4, 10, 10), mode=QPainter.CompositionMode.CompositionMode_SourceOver)
        self._paint(QRect(8, 8, 10, 10), mode=QPainter.CompositionMode.CompositionMode_SourceOver)
        self.assert_selection(rect_mask(QRect(4, 4, 10, 10), QRect(8, 8, 10, 10)))
        self.assertEqual(len(self.selection_layer.outline), 1)

    def test_subtract_region(self) -> None:
        """Erasing part of the selection removes those pixels."""
        self._paint(QRect(4, 4, 20, 20))
        self._paint(QRect(10, 0, 4, 32), Qt.GlobalColor.transparent)
        self.assert_selection(rect_mask(QRect(4, 4, 6, 20), QRect(14, 4, 10, 20)))


class SelectionLayerGrowShrinkTest(SelectionLayerOperationTestCase):
    """Tests grow_or_shrink_selection, which grows or shrinks with a square kernel."""

    REGION = QRect(10, 10, 8, 8)

    def _grown(self, num_pixels: int) -> np.ndarray:
        self.selection_layer.clear(False)
        self._paint(self.REGION)
        self.selection_layer.grow_or_shrink_selection(num_pixels)
        return selection_mask(self.selection_layer)

    def test_grow_and_shrink_by_one(self) -> None:
        """Growing or shrinking by one moves every edge of a rectangle by one pixel."""
        self._grown(1)
        self.assert_selection(rect_mask(self.REGION.adjusted(-1, -1, 1, 1)))
        self._grown(-1)
        self.assert_selection(rect_mask(self.REGION.adjusted(1, 1, -1, -1)))

    def test_grow_and_shrink_by_several(self) -> None:
        """Growing or shrinking by n moves every edge of a rectangle by n pixels."""
        for num_pixels in (2, 3, -2, -3):
            expected = rect_mask(self.REGION.adjusted(-num_pixels, -num_pixels, num_pixels, num_pixels))
            self.assert_mask_equal(self._grown(num_pixels), expected, f'n={num_pixels}')

    def test_zero_changes_nothing(self) -> None:
        """A radius of zero leaves the selection as it was."""
        self._grown(0)
        self.assert_selection(rect_mask(self.REGION))

    def test_grow_single_pixel_is_square(self) -> None:
        """Growing one pixel by one selects the 3x3 square around it, corners included."""
        self._paint(QRect(5, 5, 1, 1))
        self.selection_layer.grow_or_shrink_selection(1)
        self.assert_selection(rect_mask(QRect(4, 4, 3, 3)))

    def test_shrink_to_empty(self) -> None:
        """Shrinking a region by half its width removes it."""
        self._grown(-4)
        self.assert_selection(rect_mask())
        self.assertTrue(self.selection_layer.generation_area_is_empty())

    def test_grow_past_image_edge(self) -> None:
        """Growth past the image edge is clipped, and the layer keeps the image size."""
        self._paint(QRect(0, 28, 4, 4))
        self.selection_layer.grow_or_shrink_selection(1)
        self.assert_selection(rect_mask(QRect(0, 27, 5, 5)))
        self.assertEqual(self.selection_layer.size, SMALL_SIZE)

    def test_shrink_treats_outside_as_selected(self) -> None:
        """Shrinking doesn't pull the selection away from the image edge: pixels outside the image count as selected."""
        self.selection_layer.select_all()
        self.selection_layer.grow_or_shrink_selection(-1)
        self.assert_selection(rect_mask(SMALL_RECT))


class SelectionLayerOutlineTest(SelectionLayerOperationTestCase):
    """Tests outline polygons: they trace the edges of selected pixels, one polygon per boundary."""

    def _outline_bounds(self) -> list[QRect]:
        return sorted((polygon.boundingRect().toAlignedRect() for polygon in self.selection_layer.outline),
                      key=lambda rect: (rect.x(), rect.y(), rect.width(), rect.height()))

    def test_single_pixel(self) -> None:
        """One selected pixel gets one polygon around that pixel's edges."""
        self._paint(QRect(20, 20, 1, 1))
        self.assert_selection(rect_mask(QRect(20, 20, 1, 1)))
        self.assertEqual(self._outline_bounds(), [QRect(20, 20, 1, 1)])

    def test_disjoint_regions(self) -> None:
        """Separate regions get separate polygons."""
        self.selection_layer.set_image(self._image_with(QRect(2, 2, 5, 5), QRect(20, 4, 3, 8)))
        self.assert_selection(rect_mask(QRect(2, 2, 5, 5), QRect(20, 4, 3, 8)))
        self.assertEqual(self._outline_bounds(), [QRect(2, 2, 5, 5), QRect(20, 4, 3, 8)])

    def test_hole(self) -> None:
        """A region with a hole gets an outer polygon and a polygon around the hole."""
        self._paint(QRect(2, 2, 10, 10), bounded=False)
        self._paint(QRect(5, 5, 3, 3), Qt.GlobalColor.transparent, bounded=False)
        self.assert_selection(rect_mask(QRect(2, 2, 10, 10)) & ~rect_mask(QRect(5, 5, 3, 3)))
        self.assertEqual(self._outline_bounds(), [QRect(2, 2, 10, 10), QRect(5, 5, 3, 3)])

    def test_region_touching_edges(self) -> None:
        """A region along the image edges is outlined along those edges."""
        self._paint(QRect(28, 0, 4, 32))
        self.assert_selection(rect_mask(QRect(28, 0, 4, 32)))
        self.assertEqual(self._outline_bounds(), [QRect(28, 0, 4, 32)])

    def test_diagonal_pixels(self) -> None:
        """Pixels touching only at corners are still outlined exactly."""
        self.selection_layer.set_image(self._image_with(QRect(4, 4, 1, 1), QRect(5, 5, 1, 1), QRect(6, 4, 1, 1)))
        self.assert_selection(rect_mask(QRect(4, 4, 1, 1), QRect(5, 5, 1, 1), QRect(6, 4, 1, 1)))

    def test_bounded_edit_far_from_other_regions(self) -> None:
        """A bounded edit leaves the outlines of regions far from it alone."""
        self._paint(QRect(1, 1, 3, 3))
        self._paint(QRect(25, 25, 3, 3))
        self.assert_selection(rect_mask(QRect(1, 1, 3, 3), QRect(25, 25, 3, 3)))
        self.assertEqual(len(self.selection_layer.outline), 2)

    def test_bounded_edit_near_region_clipped_by_margin(self) -> None:
        """A bounded edit near a region that extends past the re-traced margin keeps that region's outline whole."""
        self._paint(QRect(0, 20, 30, 3))
        self._paint(QRect(12, 12, 2, 2))
        self.assertEqual(self._outline_bounds(), [QRect(0, 20, 30, 3), QRect(12, 12, 2, 2)])

    def test_bounded_edit_near_region_duplicates_it(self) -> None:
        """A bounded edit near a region doesn't add a second polygon for that region."""
        self._paint(QRect(2, 2, 4, 4))
        self._paint(QRect(12, 12, 2, 2))
        self.assertEqual(self._outline_bounds(), [QRect(2, 2, 4, 4), QRect(12, 12, 2, 2)])

    def test_bounded_edit_near_region_spanning_another(self) -> None:
        """A region inside the bounds of a nearby region, but far from the edit, keeps one whole polygon."""
        corner = (QRect(10, 2, 20, 1), QRect(29, 2, 1, 28))
        self.selection_layer.set_image(self._image_with(*corner, QRect(20, 20, 3, 3)))
        self._paint(QRect(2, 2, 1, 1))
        self.assertEqual(self._outline_bounds(), [QRect(2, 2, 1, 1), QRect(10, 2, 20, 28), QRect(20, 20, 3, 3)])

    def test_bounded_edits_match_full_trace(self) -> None:
        """Outlines built up from bounded edits match tracing the final selection from scratch."""
        self._paint(QRect(0, 20, 30, 3))
        self._paint(QRect(3, 3, 5, 5))
        self._paint(QRect(12, 12, 2, 2))
        self._paint(QRect(6, 6, 8, 2))
        self._paint(QRect(4, 4, 2, 2), Qt.GlobalColor.transparent)
        self._paint(QRect(13, 10, 1, 12))
        incremental = self._outline_bounds()
        self.selection_layer.set_image(self.selection_layer.image)
        self.assertEqual(incremental, self._outline_bounds())

    @staticmethod
    def _image_with(*rects: QRect) -> QImage:
        image = QImage(SMALL_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        for rect in rects:
            painter.fillRect(rect, Qt.GlobalColor.black)
        painter.end()
        return image


class SelectionLayerUndoTest(SelectionLayerOperationTestCase):
    """Tests that each selection operation is one undo step that undo and redo restore exactly."""

    INITIAL = QRect(6, 6, 10, 10)

    def _assert_undo_redo(self, operation: Callable[[], None], expected_after: Optional[np.ndarray] = None) -> None:
        self._paint(self.INITIAL, bounded=False)
        UndoStack().clear()
        before = selection_mask(self.selection_layer)
        operation()
        after = selection_mask(self.selection_layer)
        if expected_after is not None:
            self.assert_mask_equal(after, expected_after, 'after operation:')
        self.assertFalse(np.array_equal(before, after), 'operation changed nothing')
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assert_selection(before, 'after undo:')
        UndoStack().redo()
        self.assert_selection(after, 'after redo:')

    def test_select_all(self) -> None:
        """select_all undoes to the previous selection."""
        self._assert_undo_redo(self.selection_layer.select_all, rect_mask(SMALL_RECT))

    def test_clear(self) -> None:
        """clear undoes to the previous selection."""
        self._assert_undo_redo(self.selection_layer.clear, rect_mask())

    def test_invert(self) -> None:
        """invert_selection undoes to the previous selection."""
        self._assert_undo_redo(self.selection_layer.invert_selection, ~rect_mask(self.INITIAL))

    def test_grow(self) -> None:
        """Growing undoes to the previous selection."""
        self._assert_undo_redo(lambda: self.selection_layer.grow_or_shrink_selection(1),
                               rect_mask(self.INITIAL.adjusted(-1, -1, 1, 1)))

    def test_shrink(self) -> None:
        """Shrinking undoes to the previous selection."""
        self._assert_undo_redo(lambda: self.selection_layer.grow_or_shrink_selection(-1),
                               rect_mask(self.INITIAL.adjusted(1, 1, -1, -1)))

    def test_add_region(self) -> None:
        """A bounded borrow_image edit undoes to the previous selection."""
        self._assert_undo_redo(lambda: self._paint(QRect(12, 12, 10, 10)),
                               rect_mask(self.INITIAL, QRect(12, 12, 10, 10)))

    def test_subtract_region(self) -> None:
        """A bounded erase undoes to the previous selection."""
        self._assert_undo_redo(lambda: self._paint(QRect(8, 8, 4, 4), Qt.GlobalColor.transparent),
                               rect_mask(self.INITIAL) & ~rect_mask(QRect(8, 8, 4, 4)))

    def test_insert_image_content(self) -> None:
        """A pasted image undoes to the previous selection."""
        pasted = QImage(QSize(4, 4), QImage.Format.Format_ARGB32_Premultiplied)
        pasted.fill(QColor(0, 0, 0, 1))
        self._assert_undo_redo(lambda: self.selection_layer.insert_image_content(pasted, QRect(27, 27, 4, 4)),
                               rect_mask(self.INITIAL, QRect(27, 27, 4, 4)))

    def test_undo_edit_near_region(self) -> None:
        """Undoing a bounded edit that doesn't touch a nearby region keeps that region's outline exact."""
        self._assert_undo_redo(lambda: self._paint(QRect(20, 20, 4, 4)), rect_mask(self.INITIAL, QRect(20, 20, 4, 4)))

    def test_select_layer_content(self) -> None:
        """ImageStack.select_layer_content undoes to the previous selection."""
        layer_image = QImage(SMALL_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
        layer_image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(layer_image)
        painter.fillRect(QRect(1, 1, 3, 3), Qt.GlobalColor.red)
        painter.end()
        layer = self.image_stack.create_layer('content', layer_image)
        self._assert_undo_redo(lambda: self.image_stack.select_layer_content(layer), rect_mask(QRect(1, 1, 3, 3)))


class SelectionLayerStorageTest(SelectionLayerOperationTestCase):
    """Tests the Alpha8 mask storage behind the layer's ARGB32 facade."""

    def test_mask_is_stored_as_alpha8(self) -> None:
        """The stored mask has one byte per pixel, while the images the layer hands out are ARGB32_Premultiplied."""
        self._paint(QRect(4, 4, 8, 8))
        self.assertEqual(self.selection_layer._image.format(), QImage.Format.Format_Alpha8)
        self.assertEqual(self.selection_layer.image.format(), QImage.Format.Format_ARGB32_Premultiplied)
        self.assertEqual(self.selection_layer.mask_image.format(), QImage.Format.Format_ARGB32_Premultiplied)

    def test_images_use_selection_color_at_full_alpha(self) -> None:
        """Selected pixels read back as the opaque selection color, and the rest as transparent black."""
        AppConfig().set(AppConfig.SELECTION_COLOR, '#5500ff00')
        self._paint(QRect(4, 4, 8, 8), QColor(0, 0, 0, 3))
        image = self.selection_layer.image
        self.assertEqual(image.pixelColor(5, 5), QColor(0, 255, 0, 255))
        self.assertEqual(image.pixel(0, 0), 0)

    def test_no_pixmap_is_built_for_the_layer_item(self) -> None:
        """The selection layer's graphics item holds no pixmap."""
        from src.ui.graphics_items.layer_graphics_item import LayerGraphicsItem
        item = LayerGraphicsItem(self.selection_layer)
        self._paint(QRect(4, 4, 8, 8))
        self.assertTrue(item.pixmap().isNull())
        item.disconnect_layer()

    def test_operations_keep_selected_count(self) -> None:
        """Select-all, invert, grow, shrink and clear leave the running count matching the mask."""
        def assert_count() -> None:
            self.assertEqual(self.selection_layer._selected_count, int(selection_mask(self.selection_layer).sum()))
            self.assertEqual(self.selection_layer.is_empty(), self.selection_layer._selected_count == 0)

        self._paint(QRect(4, 4, 8, 8))
        assert_count()
        self.selection_layer.grow_or_shrink_selection(2)
        assert_count()
        self.selection_layer.grow_or_shrink_selection(-1)
        assert_count()
        self.selection_layer.invert_selection()
        assert_count()
        self._paint(QRect(0, 0, 3, 3), Qt.GlobalColor.transparent)
        assert_count()
        self.selection_layer.select_all()
        assert_count()
        self.assertTrue(self.selection_layer.generation_area_fully_selected())
        self.selection_layer.clear()
        assert_count()
        self.assertTrue(self.selection_layer.is_empty())

    def test_invert_twice_is_identity(self) -> None:
        """Inverting twice restores the selection."""
        self._paint(QRect(4, 4, 8, 8))
        self._paint(QRect(20, 3, 5, 9))
        before = selection_mask(self.selection_layer)
        self.selection_layer.invert_selection()
        self.assert_mask_equal(selection_mask(self.selection_layer), ~before)
        self.selection_layer.invert_selection()
        self.assert_selection(before)

    def test_grow_then_shrink_contains_original(self) -> None:
        """Shrinking a grown selection covers everything that was selected originally."""
        self._paint(QRect(4, 4, 8, 8))
        self._paint(QRect(14, 14, 3, 3))
        before = selection_mask(self.selection_layer)
        self.selection_layer.grow_or_shrink_selection(2)
        self.selection_layer.grow_or_shrink_selection(-2)
        self.assertTrue(np.all(selection_mask(self.selection_layer)[before]))

    def test_is_empty_within_bounds(self) -> None:
        """is_empty with bounds checks only that area."""
        self._paint(QRect(4, 4, 8, 8))
        self.assertFalse(self.selection_layer.is_empty(QRect(0, 0, 6, 6)))
        self.assertTrue(self.selection_layer.is_empty(QRect(16, 16, 8, 8)))


class SelectionLayerTimingTest(IntraPaintTestCase):
    """Guards against edit costs that grow with the canvas, with thresholds loose enough not to flake."""

    CANVAS_SIZE = QSize(4000, 4000)

    def test_small_edit_and_select_all_on_large_canvas(self) -> None:
        """A small brush edit and select-all each finish well within a second on a 4000x4000 canvas."""
        import time
        image_stack = ImageStack(self.CANVAS_SIZE, QSize(512, 512), QSize(8, 8), QSize(8000, 8000))
        selection_layer = image_stack.selection_layer
        start = time.monotonic()
        for i in range(5):
            bounds = QRect(100 + i * 40, 100, 30, 30)
            with selection_layer.borrow_image(bounds) as image:
                assert image is not None
                painter = QPainter(image)
                painter.fillRect(bounds, Qt.GlobalColor.black)
                painter.end()
        self.assertLess(time.monotonic() - start, 1.0)
        start = time.monotonic()
        selection_layer.select_all()
        self.assertLess(time.monotonic() - start, 2.0)
        self.assertTrue(selection_layer.generation_area_fully_selected())
