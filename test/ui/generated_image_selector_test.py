"""Tests for GeneratedImageSelector: manual pan and zoom carry-over between options, and saving and restoring the
previous generation batch."""
import sys

from PySide6.QtCore import QPoint, QPointF, QRect, QSize
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.image.layers.image_stack import ImageStack
from src.ui.generated_image_selector import GeneratedImageSelector, _OptionData, LABEL_TEXT_IMAGE_OPTION, \
    ORIGINAL_CONTENT_LABEL
from src.util.shared_constants import EDIT_MODE_IMG2IMG
from test.base_test_case import IntraPaintTestCase
from test.image.layers.image_stack_state import select_rect

app = QApplication.instance() or QApplication(sys.argv)

# pylint: disable=protected-access


class GeneratedImageSelectorTest(IntraPaintTestCase):
    """Tests view carry-over when stepping between options, and previous-batch save and restore."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(QSize(64, 64), QSize(64, 64), QSize(8, 8), QSize(64, 64))
        self.selector = GeneratedImageSelector(self.image_stack, lambda: None)
        self.selector.resize(400, 300)
        self.selector._zoom_to_option(0, True)

    def _manual_zoom(self, scale_ratio: float, offset: QPointF) -> None:
        """Applies a manual zoom and pan the way the view's own input handling does."""
        view = self.selector._view
        view.offset = view.offset + offset
        view.scale_without_fixed_scene_point(view.scene_scale * scale_ratio)

    def _scale_ratio(self) -> float:
        return self.selector._view.scene_scale / self.selector._base_option_scale

    def test_step_keeps_zoom_ratio_and_pan(self) -> None:
        """Stepping to the next option keeps the manual zoom ratio and pan."""
        self._manual_zoom(2.0, QPointF(3.0, -2.0))
        self.selector._zoom_to_option(1, True)
        self.assertAlmostEqual(self._scale_ratio(), 2.0, places=3)
        self.assertEqual(self.selector._view.offset - self.selector._base_option_offset, QPointF(3.0, -2.0))

    def test_zoom_ratio_survives_base_scale_change(self) -> None:
        """A change in the fitted scale keeps the chosen zoom ratio, not the scale difference."""
        self._manual_zoom(2.0, QPointF(0.0, 0.0))
        self.selector.resize(800, 600)
        self.selector._zoom_to_option(1, True)
        self.assertAlmostEqual(self._scale_ratio(), 2.0, places=3)

    def test_zoom_to_changes_drops_manual_view(self) -> None:
        """Toggling 'zoom to changes' returns to the fitted view."""
        self._manual_zoom(2.0, QPointF(3.0, -2.0))
        self.selector.zoom_to_changes(not self.selector._zoom_to_changes)
        self.assertAlmostEqual(self._scale_ratio(), 1.0, places=3)
        self.assertEqual(self.selector._view.offset, self.selector._base_option_offset)

    def test_reset_drops_manual_view(self) -> None:
        """A new batch starts without the old manual view."""
        self._manual_zoom(2.0, QPointF(3.0, -2.0))
        self.selector.reset()
        self.selector._zoom_to_option(0, True)
        self.assertAlmostEqual(self._scale_ratio(), 1.0, places=3)
        self.assertEqual(self.selector._view.offset, self.selector._base_option_offset)

    def _complete_batch(self) -> None:
        """Replaces every loading placeholder with a distinct image, as after a completed generation run."""
        generation_size = self.image_stack.generation_area.size()
        for idx in range(len(self.selector._option_items) - 1):
            image = QImage(generation_size, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(QColor(idx * 40, 128, 255 - idx * 40))
            self.selector.add_image_option(image, idx)

    def test_can_restore_previous_without_saved_options(self) -> None:
        """can_restore_previous returns False when no previous options were saved."""
        self.assertFalse(self.selector.can_restore_previous())
        # A reset that only produces placeholder images doesn't create saved options either:
        self.selector.reset()
        self.assertFalse(self.selector.can_restore_previous())

    def test_reset_skips_incomplete_batch(self) -> None:
        """reset() does not save a batch that still contains loading placeholders."""
        self.selector.reset()
        self.assertIsNone(self.selector._prev_options)

    def test_reset_skips_source_image_only_batch(self) -> None:
        """reset() does not save a batch holding only the source image."""
        self.selector._prev_options = None
        self.selector._option_data = _OptionData(self.image_stack)
        self.selector.reset()
        self.assertIsNone(self.selector._prev_options)

    def test_reset_saves_completed_batch(self) -> None:
        """reset() saves the current options as previous when the batch holds real generated images."""
        self._complete_batch()
        saved = self.selector._option_data
        self.selector.reset()
        self.assertIs(self.selector._prev_options, saved)

    def test_can_restore_previous_when_batch_fits_image(self) -> None:
        """can_restore_previous returns True when saved options exist and still fit within the image bounds."""
        self._complete_batch()
        self.selector.reset()
        self.assertTrue(self.selector.can_restore_previous())

    def test_can_restore_previous_when_batch_no_longer_fits(self) -> None:
        """can_restore_previous returns False when the image no longer contains the saved generation area."""
        self._complete_batch()
        self.selector.reset()
        self.image_stack.size = QSize(32, 32)
        self.assertFalse(self.selector.can_restore_previous())

    def test_restore_previous_choices_raises_without_saved_options(self) -> None:
        """restore_previous_choices raises RuntimeError when there is nothing restorable."""
        with self.assertRaises(RuntimeError):
            self.selector.restore_previous_choices()
        # Saved options that no longer fit the image can't be restored either:
        self._complete_batch()
        self.selector.reset()
        self.image_stack.size = QSize(32, 32)
        with self.assertRaises(RuntimeError):
            self.selector.restore_previous_choices()

    def test_restore_previous_choices_restores_saved_options(self) -> None:
        """restore_previous_choices restores the saved images and the batch's own generation context."""
        # The selection active when the batch was made becomes part of its snapshot; changing the selection
        # afterwards must not leak into the restored batch:
        select_rect(self.image_stack, QRect(QPoint(0, 0), QSize(16, 16)))
        self.selector.reset()
        self._complete_batch()
        saved_images = list(self.selector._option_data.option_images)
        saved_change_bounds = QRect(self.selector._option_data.change_bounds)
        self.selector.reset()
        select_rect(self.image_stack, QRect(QPoint(48, 48), QSize(16, 16)))
        self.selector.restore_previous_choices()

        self.assertEqual(self.selector._option_data.option_images, saved_images)
        self.assertEqual(self.selector._change_bounds, saved_change_bounds)
        self.assertNotEqual(self.selector._change_bounds, _OptionData(self.image_stack).change_bounds)
        # Restored batches don't get loading placeholders:
        self.assertNotIn(self.selector._option_data.loading_image, self.selector._option_data.option_images)
        self.assertEqual(len(self.selector._option_items), len(saved_images))
        self.assertEqual(self.selector._option_items[0].text, ORIGINAL_CONTENT_LABEL)
        for idx in range(1, len(saved_images)):
            self.assertEqual(self.selector._option_items[idx].text, LABEL_TEXT_IMAGE_OPTION.format(index=idx))
        # Every restored option gets its selection outline in inpaint mode:
        self.assertEqual(len(self.selector._selections), len(saved_images))

    def test_can_restore_previous_after_restoring(self) -> None:
        """can_restore_previous returns False once the saved options have been restored."""
        self._complete_batch()
        self.selector.reset()
        self.selector.restore_previous_choices()
        self.assertFalse(self.selector.can_restore_previous())

    def test_init_applies_saved_change_bounds(self) -> None:
        """_init_option_data keeps the snapshot's change bounds for zoom-to-changes in inpaint mode."""
        select_rect(self.image_stack, QRect(QPoint(0, 0), QSize(16, 16)))
        self.selector.reset()
        self.assertEqual(self.selector._change_bounds, self.selector._option_data.change_bounds)
        self.assertTrue(self.selector._change_zoom_checkbox.isVisibleTo(self.selector))

    def test_init_hides_selection_controls_outside_inpaint_mode(self) -> None:
        """Outside inpaint mode the selection controls are hidden and change bounds are cleared."""
        select_rect(self.image_stack, QRect(QPoint(0, 0), QSize(16, 16)))
        Cache().restore_default_options(Cache.EDIT_MODE)
        Cache().set(Cache.EDIT_MODE, EDIT_MODE_IMG2IMG)
        self.selector.reset()
        self.assertIsNone(self.selector._change_bounds)
        self.assertFalse(self.selector._selection_outline_checkbox.isVisibleTo(self.selector))
        self.assertFalse(self.selector._change_zoom_checkbox.isVisibleTo(self.selector))
