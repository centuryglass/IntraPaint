"""Tests the fill tool through synthetic mouse input."""
from unittest.mock import patch

import numpy as np
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QTransform

from src.config.cache import Cache
from src.controller import color_controller
from src.image.layers.image_layer import ImageLayer
from src.tools.fill_tool import FillTool
from src.ui.input_fields.fill_style_combo_box import BRUSH_PATTERN_DENSE_4
from src.undo_stack import UndoStack
from src.util.visual.image_utils import image_data_as_numpy_8bit_readonly
from test.tools.eyedropper_tool_test import solid_image
from test.tools.tool_test_case import ToolTestCase

FILL_COLOR = QColor(0, 0, 255)

# The test pattern's three regions, side by side. NEAR_COLOR is a few LAB units from BASE_COLOR, FAR_COLOR far from both:
BASE_COLOR = QColor(100, 100, 100)
NEAR_COLOR = QColor(104, 104, 104)
FAR_COLOR = QColor(0, 0, 0)
BASE_RECT = QRect(0, 0, 8, 16)
NEAR_RECT = QRect(8, 0, 4, 16)
FAR_RECT = QRect(12, 0, 4, 16)
SEED_POINT = QPoint(2, 3)

# Threshold that joins NEAR_COLOR to BASE_COLOR without reaching FAR_COLOR:
NEAR_THRESHOLD = 20.0


def region_pattern(size: QSize) -> QImage:
    """Returns an image with BASE_RECT, NEAR_RECT and FAR_RECT filled with their colors."""
    image = solid_image(size, QColor(Qt.GlobalColor.transparent))
    painter = QPainter(image)
    painter.fillRect(BASE_RECT, BASE_COLOR)
    painter.fillRect(NEAR_RECT, NEAR_COLOR)
    painter.fillRect(FAR_RECT, FAR_COLOR)
    painter.end()
    return image


def region_mask(size: QSize, *rects: QRect) -> np.ndarray:
    """Returns a (height, width) boolean array that is true inside any of the rectangles."""
    mask = np.zeros((size.height(), size.width()), dtype=bool)
    for rect in rects:
        mask[rect.top():rect.bottom() + 1, rect.left():rect.right() + 1] = True
    return mask


class FillToolTest(ToolTestCase):
    """Fill tool testing"""

    IMAGE_SIZE = QSize(16, 16)

    def setUp(self) -> None:
        super().setUp()
        # Keep separate fills in separate undo entries:
        cache = Cache()
        cache.set(Cache.FILL_THRESHOLD, 0.0)
        cache.set(Cache.SAMPLE_MERGED, False)
        cache.set(Cache.PAINT_SELECTION_ONLY, False)
        cache.set(Cache.FILL_TOOL_BRUSH_PATTERN, '')
        color_controller.set_foreground(FILL_COLOR, commit=False)
        self.layer = self.image_stack.create_layer(image_data=region_pattern(self.IMAGE_SIZE))
        self.image_stack.active_layer = self.layer
        self.fill_tool = FillTool(self.image_stack)
        self.tool_controller.add_tool(self.fill_tool)
        self.activate_tool(self.fill_tool)
        UndoStack().clear()

    def tearDown(self) -> None:
        self.assert_valid_premultiplied(self.layer.image)
        super().tearDown()

    def assert_valid_premultiplied(self, image: QImage) -> None:
        """Asserts that no color channel in a premultiplied image exceeds its pixel's alpha."""
        self.assertEqual(image.format(), QImage.Format.Format_ARGB32_Premultiplied)
        pixels = image_data_as_numpy_8bit_readonly(image)
        self.assertTrue(np.all(pixels[:, :, :3] <= pixels[:, :, 3:4]), 'invalid premultiplied pixels')

    def assert_filled_exactly(self, layer: ImageLayer, initial_image: QImage, filled: np.ndarray,
                              color: QColor = FILL_COLOR) -> None:
        """Asserts that the pixels marked in `filled` hold `color` and every other pixel is unchanged."""
        actual = image_data_as_numpy_8bit_readonly(layer.image)
        initial = image_data_as_numpy_8bit_readonly(initial_image)
        premultiplied = solid_image(QSize(1, 1), color)
        expected_pixel = image_data_as_numpy_8bit_readonly(premultiplied)[0, 0]
        self.assertTrue(np.all(actual[filled] == expected_pixel),
                        f'filled pixels {np.unique(actual[filled].reshape(-1, 4), axis=0)} != {expected_pixel}')
        self.assertTrue(np.array_equal(actual[~filled], initial[~filled]), 'pixels outside the fill changed')

    def test_threshold_zero_fills_exact_match_only(self) -> None:
        """At threshold 0, a click fills only the connected region of the exact clicked color."""
        initial_image = self.layer.image
        self.mouse_drag([SEED_POINT])
        self.assert_filled_exactly(self.layer, initial_image, region_mask(self.IMAGE_SIZE, BASE_RECT))

    def test_threshold_includes_similar_colors(self) -> None:
        """A higher threshold also fills connected similar colors, but not distant ones."""
        Cache().set(Cache.FILL_THRESHOLD, NEAR_THRESHOLD)
        initial_image = self.layer.image
        self.mouse_drag([SEED_POINT])
        self.assert_filled_exactly(self.layer, initial_image, region_mask(self.IMAGE_SIZE, BASE_RECT, NEAR_RECT))

    def test_fill_is_contiguous(self) -> None:
        """Pixels of the clicked color that aren't connected to the clicked point stay unfilled."""
        image = self.layer.image
        island = QRect(13, 5, 2, 2)
        painter = QPainter(image)
        painter.fillRect(island, BASE_COLOR)
        painter.end()
        self.layer.image = image
        UndoStack().clear()
        self.mouse_drag([SEED_POINT])
        self.assert_filled_exactly(self.layer, image, region_mask(self.IMAGE_SIZE, BASE_RECT))

    def test_fill_uses_current_foreground(self) -> None:
        """A foreground change after the tool was created sets the fill color."""
        new_color = QColor(250, 120, 10)
        color_controller.set_foreground(new_color)
        initial_image = self.layer.image
        self.mouse_drag([SEED_POINT])
        self.assert_filled_exactly(self.layer, initial_image, region_mask(self.IMAGE_SIZE, BASE_RECT), new_color)

    def test_each_fill_is_one_undo_step(self) -> None:
        """Each fill adds one undo entry, and undoing them in turn restores each earlier image."""
        initial_image = self.layer.image
        self.mouse_drag([SEED_POINT])
        self.assertEqual(UndoStack().undo_count(), 1)
        after_first = self.layer.image
        self.mouse_drag([FAR_RECT.center()])
        self.assertEqual(UndoStack().undo_count(), 2)
        UndoStack().undo()
        self.assert_images_equal(self.layer.image, after_first)
        UndoStack().undo()
        self.assert_images_equal(self.layer.image, initial_image)
        UndoStack().redo()
        self.assert_images_equal(self.layer.image, after_first)

    def test_right_click_does_not_fill(self) -> None:
        """Only the left button fills."""
        initial_image = self.layer.image
        self.mouse_drag([SEED_POINT], Qt.MouseButton.RightButton)
        self.assert_images_equal(self.layer.image, initial_image)
        self.assertEqual(UndoStack().undo_count(), 0)

    def test_translucent_region_is_replaced(self) -> None:
        """Filling partly transparent pixels replaces them with the fill color instead of compositing over them."""
        self.layer.image = solid_image(self.IMAGE_SIZE, QColor(255, 0, 0, 128))
        UndoStack().clear()
        initial_image = self.layer.image
        self.mouse_drag([SEED_POINT])
        self.assert_filled_exactly(self.layer, initial_image, region_mask(self.IMAGE_SIZE, QRect(QPoint(), self.IMAGE_SIZE)))

    def test_translucent_fill_color_is_premultiplied(self) -> None:
        """A translucent fill color is written premultiplied, replacing the opaque pixels under it."""
        fill_color = QColor(255, 128, 0, 128)
        color_controller.set_foreground(fill_color)
        initial_image = self.layer.image
        self.mouse_drag([SEED_POINT])
        self.assert_filled_exactly(self.layer, initial_image, region_mask(self.IMAGE_SIZE, BASE_RECT), fill_color)
        self.assert_valid_premultiplied(self.layer.image)

    def test_transparent_region_fills(self) -> None:
        """Fully transparent pixels form one region that fills like any other color."""
        self.layer.image = solid_image(self.IMAGE_SIZE, QColor(Qt.GlobalColor.transparent))
        UndoStack().clear()
        initial_image = self.layer.image
        self.mouse_drag([SEED_POINT])
        self.assert_filled_exactly(self.layer, initial_image, region_mask(self.IMAGE_SIZE, QRect(QPoint(), self.IMAGE_SIZE)))

    def test_sample_merged_off_uses_active_layer_only(self) -> None:
        """With SAMPLE_MERGED off, the fill region comes from the active layer alone."""
        top = self.image_stack.create_layer(image_data=solid_image(self.IMAGE_SIZE, QColor(Qt.GlobalColor.transparent)))
        self.image_stack.active_layer = top
        lower_image = self.layer.image
        UndoStack().clear()
        initial_image = top.image
        self.mouse_drag([SEED_POINT])
        self.assert_filled_exactly(top, initial_image, region_mask(self.IMAGE_SIZE, QRect(QPoint(), self.IMAGE_SIZE)))
        self.assert_images_equal(self.layer.image, lower_image)
        self.assert_valid_premultiplied(top.image)

    def test_sample_merged_on_uses_visible_layers(self) -> None:
        """With SAMPLE_MERGED on, the fill region comes from the merged image but is painted on the active layer."""
        Cache().set(Cache.SAMPLE_MERGED, True)
        top = self.image_stack.create_layer(image_data=solid_image(self.IMAGE_SIZE, QColor(Qt.GlobalColor.transparent)))
        self.image_stack.active_layer = top
        self.image_stack.flush_render()
        lower_image = self.layer.image
        UndoStack().clear()
        initial_image = top.image
        self.mouse_drag([SEED_POINT])
        self.assert_filled_exactly(top, initial_image, region_mask(self.IMAGE_SIZE, BASE_RECT))
        self.assert_images_equal(self.layer.image, lower_image)
        self.assertEqual(UndoStack().undo_count(), 1)

    def test_sample_merged_with_transformed_active_layer(self) -> None:
        """Sample-merged regions map into a transformed active layer's own coordinates."""
        Cache().set(Cache.SAMPLE_MERGED, True)
        top = self.image_stack.create_layer(image_data=solid_image(QSize(8, 8), QColor(Qt.GlobalColor.transparent)))
        top.transform = QTransform.fromTranslate(4, 0)
        self.image_stack.active_layer = top
        self.image_stack.flush_render()
        UndoStack().clear()
        initial_image = top.image
        # Image x 4-7 is BASE_RECT and image x 8-11 is NEAR_RECT, so layer x 0-3 is the region:
        self.mouse_drag([QPoint(5, 2)])
        self.assert_filled_exactly(top, initial_image, region_mask(QSize(8, 8), QRect(0, 0, 4, 8)))
        self.assert_valid_premultiplied(top.image)

    def test_translated_layer_fills_at_mapped_point(self) -> None:
        """A click on a translated layer fills the region under the clicked image point, in layer coordinates."""
        self.layer.transform = QTransform.fromTranslate(4, 0)
        self.image_stack.flush_render()
        UndoStack().clear()
        initial_image = self.layer.image
        # Image point (14, 3) is layer point (10, 3), inside NEAR_RECT:
        self.mouse_drag([QPoint(14, 3)])
        self.assert_filled_exactly(self.layer, initial_image, region_mask(self.IMAGE_SIZE, NEAR_RECT))

    def test_scaled_layer_fills_at_mapped_point(self) -> None:
        """A click on a scaled layer fills the region under the clicked image point, in layer coordinates."""
        self.layer.transform = QTransform.fromScale(0.5, 0.5)
        self.image_stack.flush_render()
        UndoStack().clear()
        initial_image = self.layer.image
        # Image point (6, 3) is layer point (12, 6), inside FAR_RECT:
        self.mouse_drag([QPoint(6, 3)])
        self.assert_filled_exactly(self.layer, initial_image, region_mask(self.IMAGE_SIZE, FAR_RECT))

    def test_click_outside_layer_does_nothing(self) -> None:
        """A click on an image point outside the active layer's bounds changes nothing."""
        self.layer.transform = QTransform.fromTranslate(8, 0)
        self.image_stack.flush_render()
        UndoStack().clear()
        initial_image = self.layer.image
        self.mouse_drag([QPoint(3, 3)])
        self.assert_images_equal(self.layer.image, initial_image)
        self.assertEqual(UndoStack().undo_count(), 0)

    def _select(self, rect: QRect) -> None:
        selection_layer = self.image_stack.selection_layer
        image = selection_layer.image
        painter = QPainter(image)
        painter.fillRect(rect, QColor(255, 0, 0))
        painter.end()
        selection_layer.image = image
        UndoStack().clear()

    def test_paint_selection_only_limits_fill_to_selection(self) -> None:
        """With PAINT_SELECTION_ONLY on, the fill covers only the selected part of the region."""
        Cache().set(Cache.PAINT_SELECTION_ONLY, True)
        selected = QRect(4, 4, 8, 8)
        self._select(selected)
        initial_image = self.layer.image
        self.mouse_drag([QPoint(5, 5)])
        filled = region_mask(self.IMAGE_SIZE, BASE_RECT) & region_mask(self.IMAGE_SIZE, selected)
        self.assert_filled_exactly(self.layer, initial_image, filled)

    def test_paint_selection_only_region_starts_outside_selection(self) -> None:
        """With PAINT_SELECTION_ONLY on, a click outside the selection still fills the selected part of its region."""
        Cache().set(Cache.PAINT_SELECTION_ONLY, True)
        selected = QRect(4, 4, 8, 8)
        self._select(selected)
        initial_image = self.layer.image
        self.mouse_drag([QPoint(1, 1)])
        filled = region_mask(self.IMAGE_SIZE, BASE_RECT) & region_mask(self.IMAGE_SIZE, selected)
        self.assert_filled_exactly(self.layer, initial_image, filled)

    def test_selection_ignored_when_paint_selection_only_off(self) -> None:
        """With PAINT_SELECTION_ONLY off, a selection doesn't limit the fill."""
        self._select(QRect(4, 4, 8, 8))
        initial_image = self.layer.image
        self.mouse_drag([QPoint(5, 5)])
        self.assert_filled_exactly(self.layer, initial_image, region_mask(self.IMAGE_SIZE, BASE_RECT))

    def test_selection_mask_follows_transformed_layer(self) -> None:
        """The selection limit is mapped into a translated layer's coordinates."""
        Cache().set(Cache.PAINT_SELECTION_ONLY, True)
        self.layer.transform = QTransform.fromTranslate(2, 0)
        self.image_stack.flush_render()
        selected = QRect(4, 4, 8, 8)
        self._select(selected)
        initial_image = self.layer.image
        self.mouse_drag([QPoint(5, 5)])
        filled = region_mask(self.IMAGE_SIZE, BASE_RECT) & region_mask(self.IMAGE_SIZE, selected.translated(-2, 0))
        self.assert_filled_exactly(self.layer, initial_image, filled)

    def test_empty_selection_with_paint_selection_only_refuses_fill(self) -> None:
        """With PAINT_SELECTION_ONLY on and nothing selected, a click shows an error and changes nothing."""
        Cache().set(Cache.PAINT_SELECTION_ONLY, True)
        initial_image = self.layer.image
        with patch('src.tools.base_tool.show_error_dialog') as mock_error:
            self.mouse_drag([SEED_POINT])
        mock_error.assert_called_once()
        self.assert_images_equal(self.layer.image, initial_image)
        self.assertEqual(UndoStack().undo_count(), 0)

    def test_pattern_fills_part_of_region(self) -> None:
        """A brush pattern fills a strict, non-empty subset of the region and nothing outside it."""
        Cache().set(Cache.FILL_TOOL_BRUSH_PATTERN, BRUSH_PATTERN_DENSE_4)
        initial_image = self.layer.image
        self.mouse_drag([SEED_POINT])
        actual = image_data_as_numpy_8bit_readonly(self.layer.image)
        initial = image_data_as_numpy_8bit_readonly(initial_image)
        changed = np.any(actual != initial, axis=2)
        region = region_mask(self.IMAGE_SIZE, BASE_RECT)
        self.assertTrue(np.any(changed))
        self.assertFalse(np.array_equal(changed, region))
        self.assertFalse(np.any(changed & ~region))

    def test_locked_layer_refuses_fill(self) -> None:
        """A click on a locked layer shows an error and changes nothing."""
        self.layer.locked = True
        UndoStack().clear()
        initial_image = self.layer.image
        with patch('src.tools.base_tool.show_error_dialog') as mock_error:
            self.mouse_drag([SEED_POINT])
        mock_error.assert_called_once()
        self.assert_images_equal(self.layer.image, initial_image)
        self.assertEqual(UndoStack().undo_count(), 0)
        self.layer.locked = False

    def test_hidden_layer_refuses_fill(self) -> None:
        """A click on a hidden layer shows an error and changes nothing."""
        self.layer.visible = False
        initial_image = self.layer.image
        with patch('src.tools.base_tool.show_error_dialog') as mock_error:
            self.mouse_drag([SEED_POINT])
        mock_error.assert_called_once()
        self.assert_images_equal(self.layer.image, initial_image)
