"""Tests ImageStack merges: merge_layer_down, merge_group, flatten_layer and merge_all_visible, with undo and redo.

A merge that keeps every pixel's inputs the same must leave the composite unchanged, so most expectations here are the
composite from before the merge.
"""
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtGui import QImage, QTransform

from src.image.composite_mode import CompositeMode
from src.image.layers.image_layer import ImageLayer
from src.image.text_rect import TextRect
from src.undo_stack import UndoStack
from src.util.visual.image_utils import image_content_bounds, image_data_as_numpy_8bit, image_data_as_numpy_8bit_readonly
from test.image.layers.image_stack_state import CANVAS_SIZE, ImageStackOpTestCase, noise_image

ERROR_DIALOG = 'src.image.layers.image_stack.show_error_dialog'
CONFIRM = 'src.image.layers.image_stack.request_confirmation'
CONFIRM_RENDER_TEXT = 'src.image.layers.text_layer.request_confirmation'

ISSUE_BASE_OPACITY = ('https://github.com/centuryglass/IntraPaint/issues/211: merge down applies the base layer\'s'
                      ' opacity to the merged top layer')
ISSUE_ALPHA_LOCK = ('https://github.com/centuryglass/IntraPaint/issues/212: merge down onto an alpha-locked layer'
                    ' changes its alpha')

TOP_SIZE = QSize(14, 10)
TOP_OFFSET = QPoint(20, 16)


def _text_data() -> TextRect:
    text_data = TextRect()
    text_data.text = 'text'
    text_data.size = QSize(24, 16)
    return text_data


class MergeTestCase(ImageStackOpTestCase):
    """Adds checks for operations that must not change the composite."""

    def assert_composite_kept(self, operation) -> None:
        """Checks operation with assert_undo_redo, and that it leaves the composite unchanged."""
        before, after = self.assert_undo_redo(operation)
        self.assert_images_equal(after.composite, before.composite, 'composite changed')

    def assert_blocked(self, operation, error_dialog: MagicMock) -> None:
        """Checks that operation shows one error and changes nothing."""
        UndoStack().clear()
        before = self.capture()
        operation()
        error_dialog.assert_called_once()
        self.capture().assert_matches(before, 'blocked merge')
        self.assertEqual(0, UndoStack().undo_count())


class MergeLayerDownTest(MergeTestCase):
    """Tests ImageStack.merge_layer_down."""

    def setUp(self) -> None:
        super().setUp()
        self.top = self.add_layer('top', 1, TOP_SIZE, TOP_OFFSET, min_alpha=60)
        self.base = self.add_layer('base', 2, min_alpha=60)
        self.image_stack.active_layer = self.top

    def test_merge_down(self) -> None:
        """The base layer grows to hold both layers, the top layer is removed, and the base becomes active."""
        self.assert_composite_kept(lambda: self.image_stack.merge_layer_down(self.top))
        self.assertEqual([self.base], self.image_stack.layer_stack.child_layers)
        self.assertIs(self.base, self.image_stack.active_layer)
        self.assertEqual(QRect(QPoint(), CANVAS_SIZE).united(QRect(TOP_OFFSET, TOP_SIZE)),
                         self.base.transformed_bounds)

    def test_merge_down_composite_modes(self) -> None:
        """The top layer's opacity and composite mode apply when merging onto the bottom layer."""
        for mode in CompositeMode:
            with self.subTest(mode=mode.name):
                UndoStack().clear()
                self.setUp()
                self.top.set_composition_mode(mode)
                self.top.set_opacity(0.6)
                self.assert_composite_kept(lambda: self.image_stack.merge_layer_down(self.top))

    @pytest.mark.xfail(strict=True, reason=ISSUE_BASE_OPACITY)
    def test_merge_down_onto_translucent_base(self) -> None:
        """The base layer's opacity applies to the base content only, not to the merged top layer."""
        self.base.set_opacity(0.5)
        self.assert_composite_kept(lambda: self.image_stack.merge_layer_down(self.top))

    def test_merge_down_transformed(self) -> None:
        """A rotated top layer merges onto a translated base in its rendered position."""
        self.top.set_transform(QTransform().rotate(90) * QTransform.fromTranslate(12, 2))
        self.base.set_transform(QTransform.fromTranslate(-3, 4))
        self.assert_composite_kept(lambda: self.image_stack.merge_layer_down(self.top))
        self.assertEqual(QTransform.fromTranslate(-3, 2), self.base.transform)

    @pytest.mark.xfail(strict=True, reason=ISSUE_ALPHA_LOCK)
    def test_merge_down_alpha_locked_base(self) -> None:
        """Merging onto an alpha-locked base keeps the base's alpha channel, inside and outside its old bounds."""
        self.base.image = self.base.image.copy(QRect(0, 0, 24, 20))
        self.base.set_alpha_locked(True)
        base_alpha = image_data_as_numpy_8bit_readonly(self.base.image)[:, :, 3].copy()
        self.assert_undo_redo(lambda: self.image_stack.merge_layer_down(self.top))
        expected_alpha = np.zeros((26, 34), dtype=np.uint8)
        expected_alpha[:20, :24] = base_alpha
        np.testing.assert_array_equal(image_data_as_numpy_8bit_readonly(self.base.image)[:, :, 3], expected_alpha)

    @patch(CONFIRM_RENDER_TEXT, return_value=True)
    def test_merge_text_layer_down(self, _) -> None:
        """A text layer converts to an image before merging, and undo restores the text layer."""
        text_layer = self.image_stack.create_text_layer(_text_data(), self.image_stack.layer_stack, 0)
        self.assert_composite_kept(lambda: self.image_stack.merge_layer_down(text_layer))
        self.assertEqual([], self.image_stack.text_layers)
        UndoStack().undo()
        self.assertIs(text_layer, self.image_stack.layer_stack.child_layers[0])

    @patch(CONFIRM_RENDER_TEXT, return_value=False)
    def test_merge_text_layer_down_cancelled(self, _) -> None:
        """Declining to convert a text layer cancels the merge."""
        text_layer = self.image_stack.create_text_layer(_text_data(), self.image_stack.layer_stack, 0)
        UndoStack().clear()
        before = self.capture()
        self.image_stack.merge_layer_down(text_layer)
        self.capture().assert_matches(before, 'cancelled merge')
        self.assertEqual(0, UndoStack().undo_count())

    @patch(ERROR_DIALOG)
    def test_merge_down_hidden_blocked(self, error_dialog) -> None:
        """Hidden layers can't be merged, whether the hidden layer is the top or the base."""
        for hidden in (self.top, self.base):
            with self.subTest(hidden=hidden.name):
                error_dialog.reset_mock()
                hidden.set_visible(False)
                self.assert_blocked(lambda: self.image_stack.merge_layer_down(self.top), error_dialog)
                hidden.set_visible(True)

    def test_merge_group_down_does_nothing(self) -> None:
        """A group can't be merged down onto the layer below it."""
        group = self.add_group('group')
        self.image_stack.move_layer(group, self.image_stack.layer_stack, 1)
        self.add_layer('child', 3, parent=group)
        UndoStack().clear()
        before = self.capture()
        self.image_stack.merge_layer_down(group)
        self.capture().assert_matches(before, 'merging group down')
        self.assertEqual(0, UndoStack().undo_count())

    @patch(ERROR_DIALOG)
    def test_merge_down_onto_locked_blocked(self, error_dialog) -> None:
        """A locked base layer blocks the merge."""
        self.base.set_locked(True)
        self.assert_blocked(lambda: self.image_stack.merge_layer_down(self.top), error_dialog)

    @patch(ERROR_DIALOG)
    def test_merge_down_onto_group_blocked(self, error_dialog) -> None:
        """A group below blocks the merge."""
        group = self.add_group('group')
        self.image_stack.move_layer(group, self.image_stack.layer_stack, 1)
        self.add_layer('child', 3, parent=group)
        self.assert_blocked(lambda: self.image_stack.merge_layer_down(self.top), error_dialog)

    def test_merge_down_bottom_layer_does_nothing(self) -> None:
        """Merging the bottom layer of a group does nothing."""
        UndoStack().clear()
        before = self.capture()
        self.image_stack.merge_layer_down(self.base)
        self.capture().assert_matches(before, 'merging bottom layer')
        self.assertEqual(0, UndoStack().undo_count())

    def test_merge_down_in_group(self) -> None:
        """Merging inside a group merges onto the layer below within the group."""
        group = self.add_group('group')
        top = self.add_layer('inner top', 3, TOP_SIZE, QPoint(2, 2), group, min_alpha=60)
        inner_base = self.add_layer('inner base', 4, QSize(10, 10), QPoint(6, 8), group, min_alpha=60)
        self.assert_composite_kept(lambda: self.image_stack.merge_layer_down(top))
        self.assertEqual([inner_base], group.child_layers)


class MergeGroupTest(MergeTestCase):
    """Tests ImageStack.merge_group and flatten_layer on groups, checking exact pixels."""

    def setUp(self) -> None:
        super().setUp()
        self.group = self.add_group('group')
        self.child_a = self.add_layer('a', 1, QSize(16, 12), QPoint(2, 3), self.group, min_alpha=60)
        self.child_b = self.add_layer('b', 2, QSize(18, 14), QPoint(10, 8), self.group, min_alpha=60)

    def _assert_merges_to_one_layer(self) -> ImageLayer:
        self.assert_composite_kept(lambda: self.image_stack.merge_group(self.group))
        merged = self.image_stack.layer_stack.child_layers[0]
        assert isinstance(merged, ImageLayer)
        self.assertEqual('group', merged.name)
        return merged

    @staticmethod
    def content_bounds(layer: ImageLayer) -> QRect:
        """Returns the canvas bounds of a layer's non-transparent pixels."""
        return image_content_bounds(layer.image).translated(layer.transformed_bounds.topLeft())

    def test_merge_group(self) -> None:
        """A group of offset translucent layers merges to one layer covering the group's bounds."""
        merged = self._assert_merges_to_one_layer()
        self.assertEqual(self.group.bounds, merged.transformed_bounds)

    def test_merge_group_child_modes(self) -> None:
        """Child opacity and composite modes are applied by the merge."""
        for mode in CompositeMode:
            with self.subTest(mode=mode.name):
                UndoStack().clear()
                self.setUp()
                self.child_a.set_composition_mode(mode)
                self.child_a.set_opacity(0.7)
                self._assert_merges_to_one_layer()

    def test_merge_group_opacity_and_isolate(self) -> None:
        """Group opacity applies to the merged layer's pixels, for isolated and non-isolated groups."""
        for isolate in (False, True):
            with self.subTest(isolate=isolate):
                UndoStack().clear()
                self.setUp()
                self.group.set_isolate(isolate)
                self.group.set_opacity(0.5)
                self._assert_merges_to_one_layer()

    def test_merge_nested_group(self) -> None:
        """Nested groups and their children merge into the outer group's layer."""
        inner = self.add_group('inner', self.group)
        self.add_layer('inner child', 3, QSize(8, 8), QPoint(20, 1), inner, min_alpha=60)
        inner.set_opacity(0.6)
        merged = self._assert_merges_to_one_layer()
        self.assertEqual(QRect(2, 1, 26, 21), merged.transformed_bounds)

    def test_merge_group_with_hidden_child(self) -> None:
        """A hidden child isn't drawn into the merged layer."""
        self.child_b.set_visible(False)
        merged = self._assert_merges_to_one_layer()
        self.assertFalse(self.image_stack.layer_stack.contains_recursive(self.child_b))
        self.assertEqual(self.child_a.transformed_bounds, self.content_bounds(merged))

    def test_merge_group_over_opaque_layer(self) -> None:
        """A group over an opaque layer merges without taking in the layer beneath."""
        base = self.add_layer('base', 3)
        merged = self._assert_merges_to_one_layer()
        self.assertEqual([merged, base], self.image_stack.layer_stack.child_layers)

    def test_merge_layer_stack_does_nothing(self) -> None:
        """merge_group ignores the root layer stack and non-group layers."""
        UndoStack().clear()
        before = self.capture()
        self.image_stack.merge_group(self.image_stack.layer_stack)
        self.image_stack.merge_group(self.child_a)
        self.capture().assert_matches(before, 'ignored merge')
        self.assertEqual(0, UndoStack().undo_count())

    def test_flatten_image_layer(self) -> None:
        """Flattening a translucent, transformed layer over an opaque layer bakes its opacity and transform in."""
        layer = self.add_layer('flattened', 4, QSize(10, 12), min_alpha=60)
        self.image_stack.move_layer(layer, self.image_stack.layer_stack, 0)
        self.add_layer('base', 3)
        layer.set_transform(QTransform().rotate(90) * QTransform.fromTranslate(20, 4))
        layer.set_opacity(0.5)
        self.assert_composite_kept(lambda: self.image_stack.flatten_layer(layer))
        flattened = self.image_stack.layer_stack.child_layers[0]
        assert isinstance(flattened, ImageLayer)
        self.assertTrue(self.image_stack.layer_is_flat(flattened))

    def test_layer_is_flat(self) -> None:
        """Only a group with no children, or an image layer at full opacity in Normal mode with a whole-pixel offset,
        is flat."""
        self.assertTrue(self.image_stack.layer_is_flat(self.child_a))
        self.assertFalse(self.image_stack.layer_is_flat(self.group))
        self.assertTrue(self.image_stack.layer_is_flat(self.add_group('empty')))
        for change, undo in ((lambda: self.child_a.set_opacity(0.5), lambda: self.child_a.set_opacity(1.0)),
                             (lambda: self.child_a.set_composition_mode(CompositeMode.MULTIPLY),
                              lambda: self.child_a.set_composition_mode(CompositeMode.NORMAL)),
                             (lambda: self.child_a.set_transform(QTransform.fromTranslate(2.5, 3)),
                              lambda: self.child_a.set_transform(QTransform.fromTranslate(2, 3))),
                             (lambda: self.child_a.set_transform(QTransform().rotate(90)),
                              lambda: self.child_a.set_transform(QTransform.fromTranslate(2, 3)))):
            change()
            self.assertFalse(self.image_stack.layer_is_flat(self.child_a))
            undo()
            self.assertTrue(self.image_stack.layer_is_flat(self.child_a))

    def test_flatten_layer_in_group(self) -> None:
        """A translucent layer inside a group flattens in place within the group."""
        self.child_b.image = noise_image(self.child_b.size, 5)
        self.child_a.set_opacity(0.5)
        self.assert_composite_kept(lambda: self.image_stack.flatten_layer(self.child_a))
        flattened = self.group.child_layers[0]
        assert isinstance(flattened, ImageLayer)
        self.assertEqual([flattened, self.child_b], self.group.child_layers)
        self.assertTrue(self.image_stack.layer_is_flat(flattened))

    def test_flatten_text_layer(self) -> None:
        """Flattening a text layer replaces it with an image layer, which undo turns back into the text layer."""
        self.group.set_visible(False)
        self.add_layer('base', 3)
        text_layer = self.image_stack.create_text_layer(_text_data(), self.image_stack.layer_stack, 0)
        self.assert_composite_kept(lambda: self.image_stack.flatten_layer(text_layer))
        self.assertEqual([], self.image_stack.text_layers)
        self.assertIsInstance(self.image_stack.layer_stack.child_layers[0], ImageLayer)
        UndoStack().undo()
        self.assertIs(text_layer, self.image_stack.layer_stack.child_layers[0])

    def test_flatten_over_translucent_layer(self) -> None:
        """Flattening a translucent layer over translucent content leaves the composite within 8-bit rounding."""
        self.child_a.set_opacity(0.5)
        before, after = self.assert_undo_redo(lambda: self.image_stack.flatten_layer(self.child_a))
        def pixels(image: QImage) -> np.ndarray:
            return image_data_as_numpy_8bit(image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)).astype(int)

        max_difference = np.abs(pixels(before.composite) - pixels(after.composite)).max()
        self.assertLessEqual(max_difference, 2)

    @patch(ERROR_DIALOG)
    def test_flatten_hidden_layer_blocked(self, error_dialog) -> None:
        """A hidden layer or group can't be flattened, since its rendered content is empty."""
        self.child_a.set_opacity(0.5)
        for hidden in (self.child_a, self.group):
            with self.subTest(hidden=hidden.name):
                error_dialog.reset_mock()
                hidden.set_visible(False)
                self.assert_blocked(lambda: self.image_stack.flatten_layer(hidden), error_dialog)
                hidden.set_visible(True)


class MergeAllVisibleTest(MergeTestCase):
    """Tests ImageStack.merge_all_visible beyond test_merge_all_visible in image_stack_test.py."""

    def setUp(self) -> None:
        super().setUp()
        self.top = self.add_layer('top', 1, TOP_SIZE, TOP_OFFSET, min_alpha=60)
        self.hidden = self.add_layer('hidden', 2, QSize(6, 6), QPoint(-4, -4))
        self.hidden.set_visible(False)
        self.group = self.add_group('group')
        self.child = self.add_layer('child', 3, QSize(16, 12), QPoint(-2, 3), self.group, min_alpha=60)
        self.child.set_composition_mode(CompositeMode.MULTIPLY)
        self.child_base = self.add_layer('child base', 4, QSize(12, 12), QPoint(4, 2), self.group, min_alpha=60)
        self.group.set_opacity(0.6)
        self.bottom = self.add_layer('bottom', 5, min_alpha=60)

    def test_merge_all_visible_with_group(self) -> None:
        """Visible layers and groups merge into one layer below the hidden layer, matching the old composite."""
        self.assert_composite_kept(self.image_stack.merge_all_visible)
        merged = self.image_stack.active_layer
        self.assertEqual([self.hidden, merged], self.image_stack.layer_stack.child_layers)
        assert isinstance(merged, ImageLayer)
        self.assertEqual(QRect(QPoint(-2, 0), QSize(36, 26)),
                         image_content_bounds(merged.image).translated(merged.transformed_bounds.topLeft()))

    @patch(CONFIRM, return_value=True)
    def test_merge_all_visible_drops_hidden_child(self, confirm) -> None:
        """A hidden layer inside a merged group is deleted once the user confirms."""
        self.child_base.set_visible(False)
        self.assert_composite_kept(self.image_stack.merge_all_visible)
        confirm.assert_called_once()
        self.assertFalse(self.image_stack.layer_stack.contains_recursive(self.child_base))

    @patch(CONFIRM, return_value=False)
    def test_merge_all_visible_hidden_child_cancelled(self, _) -> None:
        """Declining to delete a hidden child cancels the merge."""
        self.child_base.set_visible(False)
        UndoStack().clear()
        before = self.capture()
        self.image_stack.merge_all_visible()
        self.capture().assert_matches(before, 'cancelled merge')
        self.assertEqual(0, UndoStack().undo_count())

    @patch(ERROR_DIALOG)
    def test_merge_all_visible_locked_blocked(self, error_dialog) -> None:
        """A locked layer inside a visible group blocks the merge."""
        self.child.set_locked(True)
        self.assert_blocked(self.image_stack.merge_all_visible, error_dialog)

    @patch(CONFIRM_RENDER_TEXT, return_value=True)
    def test_merge_all_visible_with_text_layer(self, _) -> None:
        """A visible text layer is rendered into the merged layer."""
        text_layer = self.image_stack.create_text_layer(_text_data(), self.image_stack.layer_stack, 0)
        self.assert_composite_kept(self.image_stack.merge_all_visible)
        self.assertEqual([], self.image_stack.text_layers)
        UndoStack().undo()
        self.assertIs(text_layer, self.image_stack.layer_stack.child_layers[0])


if __name__ == '__main__':
    unittest.main()
