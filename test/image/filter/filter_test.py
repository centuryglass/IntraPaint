"""Tests applying each image filter from the Filters menu: through `ImageFilter.get_filter_modal` and its apply button.

The filter brush tests cover the filtering functions themselves, including their known bugs on translucent pixels.
These tests use opaque images, so they check only what the menu path adds: which layers and pixels get filtered, and
that one undo step reverts it.
"""
import sys
from typing import Any
from unittest.mock import patch

import pytest

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QTransform
from PySide6.QtWidgets import QApplication

from src.image.filter.blur import BlurFilter, MODE_BOX
from src.image.filter.brightness_contrast import BrightnessContrastFilter
from src.image.filter.filter import ImageFilter
from src.image.filter.invert import InvertFilter
from src.image.filter.posterize import PosterizeFilter
from src.image.filter.rgb_color_balance import RGBColorBalanceFilter
from src.image.filter.saturation import SaturationFilter
from src.image.filter.sharpen import SharpenFilter
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.undo_stack import UndoStack
from src.util.async_task import AsyncTask
from test.base_test_case import IntraPaintTestCase
from test.image.brush.brush_test_case import brush_test_pattern

app = QApplication.instance() or QApplication(sys.argv)

IMAGE_SIZE = QSize(256, 256)
SELECTED_REGIONS = (QRect(10, 10, 20, 20), QRect(200, 200, 20, 20))
UNSELECTED_POINT = QPoint(100, 100)

STACK_SIZE = QSize(96, 64)
LAYER_SIZE = QSize(48, 32)
SELECTION = QRect(30, 12, 24, 20)
# Inside TRANSFORM's transformed layer bounds, (64, 8)-(96, 56):
TRANSFORMED_SELECTION = QRect(70, 16, 20, 30)
# Rotates a LAYER_SIZE layer 90 degrees clockwise, onto the right edge of the stack:
TRANSFORM = QTransform.fromTranslate(STACK_SIZE.width(), 8).rotate(90)

# Every filter in the Filters menu, with parameter values that change the test pattern. The filters with identity
# defaults get other values; the rest keep their defaults. Contrast stays at 1.0, since the selection tests would hit
# the bug that test_contrast_inside_selection_matches_whole_layer pins.
MENU_FILTERS: tuple[tuple[type[ImageFilter], list[Any]], ...] = (
    (RGBColorBalanceFilter, [2.0, 0.5, 1.0, 1.0]),
    (BrightnessContrastFilter, [1.5, 1.0]),
    (BlurFilter, [MODE_BOX, 3.0]),
    (SharpenFilter, [2.0]),
    (PosterizeFilter, [3]),
    (SaturationFilter, [0.0]),
    (InvertFilter, []),
)


def opaque_pattern(size: QSize) -> QImage:
    """Returns brush_test_pattern with every pixel made opaque, transparent pixels becoming black."""
    return brush_test_pattern(size).convertToFormat(QImage.Format.Format_RGB32).convertToFormat(
        QImage.Format.Format_ARGB32_Premultiplied)


def inverted_pattern(size: QSize) -> QImage:
    """Returns opaque_pattern with its colors inverted, for a second layer that differs from the first."""
    image = opaque_pattern(size)
    image.invertPixels(QImage.InvertMode.InvertRgb)
    return image


def filtered_copy(image_filter: ImageFilter, image: QImage, parameter_values: list[Any]) -> QImage:
    """Returns the filter function's output for a copy of an image, which some filter functions change in place."""
    return image_filter.get_filter()(image.copy(), *parameter_values).convertToFormat(
        QImage.Format.Format_ARGB32_Premultiplied)


def merge_in_rect(original: QImage, filtered: QImage, rect: QRect) -> QImage:
    """Returns a copy of `original` with the pixels inside `rect` taken from `filtered`."""
    merged = original.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(merged)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
    painter.drawImage(rect, filtered, rect)
    painter.end()
    return merged


class FilterSelectionOnlyTest(IntraPaintTestCase):
    """Applies a filter to selected areas of a single white layer."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(IMAGE_SIZE, IMAGE_SIZE, QSize(8, 8), QSize(1024, 1024))
        image = QImage(IMAGE_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.white)
        self.layer = self.image_stack.create_layer(None, image)
        self.image_stack.active_layer = self.layer
        self.filter = InvertFilter(self.image_stack)
        self.filter.selection_only = True
        self.filter.active_layer_only = True

    def _select(self, bounds: QRect) -> None:
        with self.image_stack.selection_layer.borrow_image() as mask_image:
            painter = QPainter(mask_image)
            painter.fillRect(bounds, Qt.GlobalColor.black)
            painter.end()

    def _apply_filter(self) -> None:
        """Runs apply_filter with its background task on the calling thread."""
        with patch.object(AsyncTask, 'start', AsyncTask.run):
            self.filter.apply_filter([])

    def test_filter_changes_every_selected_region(self) -> None:
        """Each region of a multi-region selection is filtered, and unselected pixels are left alone."""
        for region in SELECTED_REGIONS:
            self._select(region)
        self._apply_filter()
        image = self.layer.image
        for region in SELECTED_REGIONS:
            for point in (region.topLeft(), region.bottomRight()):
                self.assertEqual(image.pixelColor(point), QColor(Qt.GlobalColor.black), f'{point} not filtered')
        self.assertEqual(image.pixelColor(UNSELECTED_POINT), QColor(Qt.GlobalColor.white))


class MenuFilterTest(IntraPaintTestCase):
    """Applies each menu filter through its modal, the way the Filters menu does, then undoes it.

    Each test covers every filter in a subTest, with a fresh image stack for each.
    """

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(STACK_SIZE, STACK_SIZE, QSize(8, 8), QSize(1024, 1024))

    def _reset_stack(self) -> None:
        """Replaces the image stack and clears the undo history, for the next filter's subTest."""
        UndoStack().clear()
        self.image_stack = ImageStack(STACK_SIZE, STACK_SIZE, QSize(8, 8), QSize(1024, 1024))

    def _select(self, bounds: QRect) -> None:
        with self.image_stack.selection_layer.borrow_image() as mask_image:
            painter = QPainter(mask_image)
            painter.fillRect(bounds, Qt.GlobalColor.black)
            painter.end()

    def _apply_from_modal(self, image_filter: ImageFilter, parameter_values: list[Any]) -> None:
        """Opens the filter's modal without showing it, enters parameter values, and clicks "Apply".

        The undo history is cleared first, so layer setup can't merge into the filter's undo step. The filter's
        background task runs on the calling thread.
        """
        UndoStack().clear()
        modal = image_filter.get_filter_modal()
        # pylint: disable-next=protected-access
        for field_widget, value in zip(modal._param_inputs, parameter_values, strict=True):
            field_widget.setValue(value)
        with patch.object(AsyncTask, 'start', AsyncTask.run):
            modal._apply_button.click()  # pylint: disable=protected-access
        modal.deleteLater()

    def _assert_one_undo_step(self, expected: dict[ImageLayer, QImage], originals: dict[ImageLayer, QImage]) -> None:
        """Checks each layer's filtered image, then that one undo restores every original and redo restores the
        filtered images."""
        for layer, expected_image in expected.items():
            self.assert_images_equal(layer.image, expected_image, f'{layer.name} after filtering')
        self.assertEqual(UndoStack().undo_count(), 1, 'filter did not add exactly one undo step')
        UndoStack().undo()
        for layer, original in originals.items():
            self.assert_images_equal(layer.image, original, f'{layer.name} after undo')
        UndoStack().redo()
        for layer, expected_image in expected.items():
            self.assert_images_equal(layer.image, expected_image, f'{layer.name} after redo')

    def test_whole_layer(self) -> None:
        """With nothing selected, the filter replaces the whole active layer and leaves other layers alone."""
        for filter_class, parameter_values in MENU_FILTERS:
            with self.subTest(filter=filter_class.__name__):
                self._reset_stack()
                other_layer = self.image_stack.create_layer('other', inverted_pattern(STACK_SIZE))
                original = opaque_pattern(STACK_SIZE)
                layer = self.image_stack.create_layer('filtered', original)
                self.image_stack.active_layer = layer
                image_filter = filter_class(self.image_stack)
                self.assertNotEqual(filtered_copy(image_filter, original, parameter_values), original,
                                    'parameter values leave the test pattern unchanged')

                self._apply_from_modal(image_filter, parameter_values)
                self.assertFalse(image_filter.selection_only)
                self._assert_one_undo_step({layer: filtered_copy(image_filter, original, parameter_values),
                                            other_layer: other_layer.image},
                                           {layer: original, other_layer: other_layer.image})

    def test_inside_selection(self) -> None:
        """With a selection, selected pixels match filtering the whole layer, and the rest are unchanged."""
        for filter_class, parameter_values in MENU_FILTERS:
            with self.subTest(filter=filter_class.__name__):
                self._reset_stack()
                original = opaque_pattern(STACK_SIZE)
                layer = self.image_stack.create_layer('filtered', original)
                self.image_stack.active_layer = layer
                self._select(SELECTION)
                image_filter = filter_class(self.image_stack)

                self._apply_from_modal(image_filter, parameter_values)
                self.assertTrue(image_filter.selection_only)
                expected = merge_in_rect(original, filtered_copy(image_filter, original, parameter_values), SELECTION)
                self._assert_one_undo_step({layer: expected}, {layer: original})

    @pytest.mark.xfail(strict=True, reason='https://github.com/centuryglass/IntraPaint/issues/192')
    def test_contrast_inside_selection_matches_whole_layer(self) -> None:
        """Contrast inside a selection matches contrast on the whole layer.

        PIL's contrast pivots on the mean of the image it is given, and the menu filter passes it the selection's
        bounds.
        """
        original = opaque_pattern(STACK_SIZE)
        layer = self.image_stack.create_layer('filtered', original)
        self.image_stack.active_layer = layer
        self._select(SELECTION)
        image_filter = BrightnessContrastFilter(self.image_stack)
        parameter_values = [1.0, 2.0]

        self._apply_from_modal(image_filter, parameter_values)
        self.assert_images_equal(layer.image, merge_in_rect(
            original, filtered_copy(image_filter, original, parameter_values), SELECTION))

    def test_transformed_layer_inside_selection(self) -> None:
        """On a rotated and offset layer, the filter changes the layer pixels under the selection, mapped through the
        layer's transform."""
        local_selection = TRANSFORM.inverted()[0].mapRect(QRectF(TRANSFORMED_SELECTION)).toAlignedRect()
        for filter_class, parameter_values in MENU_FILTERS:
            with self.subTest(filter=filter_class.__name__):
                self._reset_stack()
                original = opaque_pattern(LAYER_SIZE)
                layer = self.image_stack.create_layer('transformed', original, transform=TRANSFORM)
                self.image_stack.active_layer = layer
                self.assertTrue(layer.transformed_bounds.contains(TRANSFORMED_SELECTION))
                self._select(TRANSFORMED_SELECTION)
                image_filter = filter_class(self.image_stack)

                self._apply_from_modal(image_filter, parameter_values)
                expected = merge_in_rect(original, filtered_copy(image_filter, original, parameter_values),
                                         local_selection)
                self._assert_one_undo_step({layer: expected}, {layer: original})

    def test_layer_group(self) -> None:
        """With a group active, the filter changes every layer in the group, and one undo step reverts them all."""
        for filter_class, parameter_values in MENU_FILTERS:
            with self.subTest(filter=filter_class.__name__):
                self._reset_stack()
                outside_layer = self.image_stack.create_layer('outside', opaque_pattern(STACK_SIZE))
                group = self.image_stack.create_layer_group('group')
                first_original = opaque_pattern(STACK_SIZE)
                second_original = inverted_pattern(STACK_SIZE)
                first_layer = self.image_stack.create_layer('first', first_original, group, 0)
                second_layer = self.image_stack.create_layer('second', second_original, group, 1)
                self.image_stack.active_layer = group
                image_filter = filter_class(self.image_stack)

                self._apply_from_modal(image_filter, parameter_values)
                outside_original = opaque_pattern(STACK_SIZE)
                self._assert_one_undo_step(
                    {first_layer: filtered_copy(image_filter, first_original, parameter_values),
                     second_layer: filtered_copy(image_filter, second_original, parameter_values),
                     outside_layer: outside_original},
                    {first_layer: first_original, second_layer: second_original, outside_layer: outside_original})

    def test_selection_outside_layer_changes_nothing(self) -> None:
        """A selection that doesn't overlap the active layer leaves it unchanged and adds no undo step."""
        for filter_class, parameter_values in MENU_FILTERS:
            with self.subTest(filter=filter_class.__name__):
                self._reset_stack()
                original = opaque_pattern(LAYER_SIZE)
                layer = self.image_stack.create_layer('filtered', original)
                self.image_stack.active_layer = layer
                self._select(QRect(QPoint(LAYER_SIZE.width() + 8, 0), QSize(8, 8)))
                image_filter = filter_class(self.image_stack)

                self._apply_from_modal(image_filter, parameter_values)
                self.assert_images_equal(layer.image, original)
                self.assertEqual(UndoStack().undo_count(), 0)
