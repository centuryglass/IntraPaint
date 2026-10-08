"""Tests image_stack_utils.crop_layer_to_selection on layer groups whose children cross the selection's edge.

Cropping a group crops each image layer inside it, at any depth, to the bounds of the selection within that layer.
Layers left with no selected content are deleted, and the whole crop is one undo step.
"""
import unittest
from unittest.mock import patch

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QPainter, QTransform

from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack_utils import crop_layer_to_selection
from src.image.layers.text_layer import TextLayer
from src.image.text_rect import TextRect
from test.image.layers.image_stack_state import CANVAS_SIZE, ImageStackOpTestCase, masked_to_rect, select_rect

ERROR_DIALOG = 'src.image.layers.image_stack_utils.show_error_dialog'
WARNING_DIALOG = 'src.image.layers.image_stack_utils.show_warning_dialog'
CONFIRM_RENDER_TEXT = 'src.image.layers.text_layer.request_confirmation'

SELECTION = QRect(10, 4, 16, 14)


@patch(WARNING_DIALOG)
@patch(ERROR_DIALOG)
class CropGroupToSelectionTest(ImageStackOpTestCase):
    """Crops a group holding layers inside, outside and across the selection, and a nested group."""

    def setUp(self) -> None:
        super().setUp()
        self.backdrop = self.add_layer('backdrop', 1, min_alpha=120)
        self.group = self.add_group('group')
        self.crossing = self.add_layer('crossing', 2, QSize(14, 10), QPoint(6, 6), self.group, min_alpha=80)
        self.inside = self.add_layer('inside', 3, QSize(4, 4), QPoint(12, 8), self.group, min_alpha=80)
        self.outside = self.add_layer('outside', 4, QSize(4, 4), QPoint(0, 19), self.group, min_alpha=80)
        self.nested = self.add_group('nested', self.group)
        self.rotated = self.add_layer('rotated', 5, QSize(12, 20), parent=self.nested, min_alpha=80)
        self.rotated.set_transform(QTransform().rotate(90) * QTransform.fromTranslate(26, 2))
        self.nested_crossing = self.add_layer('nested crossing', 6, QSize(10, 10), QPoint(20, 12), self.nested,
                                              min_alpha=80)
        self.assertEqual(QRect(6, 2, 20, 12), self.rotated.transformed_bounds)
        select_rect(self.image_stack, SELECTION)

    def _assert_cropped(self, layer: ImageLayer, original_image, local_rect: QRect, canvas_rect: QRect) -> None:
        self.assertEqual(canvas_rect, layer.transformed_bounds, layer.name)
        self.assert_images_equal(layer.image, original_image.copy(local_rect), layer.name)

    def test_crop_group(self, error_dialog, warning_dialog) -> None:
        """Each child is cut to the selection, a child outside it is deleted, and the selected composite is kept."""
        images = {layer: layer.image for layer in (self.backdrop, self.crossing, self.inside, self.rotated,
                                                   self.nested_crossing)}
        before, after = self.assert_undo_redo(lambda: crop_layer_to_selection(self.image_stack, self.group))
        error_dialog.assert_not_called()
        warning_dialog.assert_called_once()

        self._assert_cropped(self.crossing, images[self.crossing], QRect(4, 0, 10, 10), QRect(10, 6, 10, 10))
        self._assert_cropped(self.rotated, images[self.rotated], QRect(2, 0, 10, 16), QRect(10, 4, 16, 10))
        self.assertEqual((0.0, 1.0, -1.0, 0.0), (self.rotated.transform.m11(), self.rotated.transform.m12(),
                                                 self.rotated.transform.m21(), self.rotated.transform.m22()))
        self._assert_cropped(self.nested_crossing, images[self.nested_crossing], QRect(0, 0, 6, 6),
                             QRect(20, 12, 6, 6))
        self._assert_cropped(self.inside, images[self.inside], QRect(0, 0, 4, 4), QRect(12, 8, 4, 4))
        self._assert_cropped(self.backdrop, images[self.backdrop], self.backdrop.bounds, self.backdrop.bounds)

        self.assertFalse(self.image_stack.layer_stack.contains_recursive(self.outside))
        self.assertEqual([self.crossing, self.inside, self.nested], self.group.child_layers)
        self.assertEqual([self.rotated, self.nested_crossing], self.nested.child_layers)

        self.assert_images_equal(masked_to_rect(after.composite, SELECTION),
                                 masked_to_rect(before.composite, SELECTION))
        # Left of the selection, only the backdrop is left:
        left_of_selection = QRect(0, 0, SELECTION.x(), CANVAS_SIZE.height())
        self.assert_images_equal(masked_to_rect(after.composite, left_of_selection),
                                 masked_to_rect(images[self.backdrop], left_of_selection))

    def test_crop_nested_group(self, error_dialog, warning_dialog) -> None:
        """Cropping a nested group leaves its parent's other children alone."""
        crossing_image = self.crossing.image
        self.assert_undo_redo(lambda: crop_layer_to_selection(self.image_stack, self.nested))
        error_dialog.assert_not_called()
        warning_dialog.assert_not_called()
        self.assertEqual(QRect(10, 4, 16, 10), self.rotated.transformed_bounds)
        self.assertEqual(QRect(20, 12, 6, 6), self.nested_crossing.transformed_bounds)
        self._assert_cropped(self.crossing, crossing_image, self.crossing.bounds, QRect(6, 6, 14, 10))
        self.assertTrue(self.image_stack.layer_stack.contains_recursive(self.outside))

    def test_crop_layer_stack(self, error_dialog, _) -> None:
        """Cropping the layer stack itself crops layers both inside and outside the group."""
        self.assert_undo_redo(lambda: crop_layer_to_selection(self.image_stack, self.image_stack.layer_stack))
        error_dialog.assert_not_called()
        self.assertEqual(SELECTION, self.backdrop.transformed_bounds)
        self.assertEqual(QRect(10, 6, 10, 10), self.crossing.transformed_bounds)
        self.assertFalse(self.image_stack.layer_stack.contains_recursive(self.outside))

    def test_selection_with_two_regions(self, error_dialog, _) -> None:
        """A layer under two separate selected regions is cropped to the bounds of both."""
        select_rect(self.image_stack, QRect(8, 7, 3, 2))
        with self.image_stack.selection_layer.borrow_image() as mask:
            assert mask is not None
            painter = QPainter(mask)
            painter.fillRect(QRect(16, 12, 2, 2).translated(-self.image_stack.selection_layer.position),
                             Qt.GlobalColor.red)
            painter.end()
        crossing_image = self.crossing.image
        self.assert_undo_redo(lambda: crop_layer_to_selection(self.image_stack, self.group))
        error_dialog.assert_not_called()
        self._assert_cropped(self.crossing, crossing_image, QRect(2, 1, 10, 7), QRect(8, 7, 10, 7))
        self.assertFalse(self.image_stack.layer_stack.contains_recursive(self.nested_crossing))
        self.assertFalse(self.image_stack.layer_stack.contains_recursive(self.outside))

    def test_selection_missing_every_child(self, error_dialog, _) -> None:
        """A selection that misses every child deletes them all, leaving the groups empty."""
        select_rect(self.image_stack, QRect(0, 0, 4, 4))
        self.assert_undo_redo(lambda: crop_layer_to_selection(self.image_stack, self.group))
        error_dialog.assert_not_called()
        self.assertEqual([self.nested], self.group.child_layers)
        self.assertEqual([], self.nested.child_layers)
        self.assertTrue(self.image_stack.layer_stack.contains_recursive(self.backdrop))

    def test_selection_containing_every_child(self, error_dialog, warning_dialog) -> None:
        """When every child is inside the selection, nothing changes and an error explains why."""
        select_rect(self.image_stack, QRect(QPoint(), CANVAS_SIZE))
        before = self.capture()
        crop_layer_to_selection(self.image_stack, self.group)
        error_dialog.assert_called_once()
        warning_dialog.assert_not_called()
        self.capture().assert_matches(before, 'uncropped')

    @patch(CONFIRM_RENDER_TEXT, return_value=True)
    def test_text_layer_in_group(self, _, error_dialog, __) -> None:
        """A text layer crossing the selection inside the group is converted to an image layer and cropped."""
        text_data = TextRect()
        text_data.text = 'text'
        text_data.size = QSize(24, 16)
        text_layer = self.image_stack.create_text_layer(text_data, self.nested, 0)
        self.assert_undo_redo(lambda: crop_layer_to_selection(self.image_stack, self.group))
        error_dialog.assert_not_called()
        self.assertFalse(self.image_stack.layer_stack.contains_recursive(text_layer))
        converted = self.nested.child_layers[0]
        self.assertNotIsInstance(converted, TextLayer)
        self.assertIsInstance(converted, ImageLayer)
        self.assertEqual(QRect(10, 4, 14, 12), converted.transformed_bounds)


if __name__ == '__main__':
    unittest.main()
