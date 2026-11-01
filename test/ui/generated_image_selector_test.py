"""Tests for GeneratedImageSelector: batch snapshots, the manual view carry-over between options, re-opening the
previous generation batch, and how a run's Cancel, Stop and end close or keep the screen."""
import sys
import time
from typing import Optional
from unittest.mock import MagicMock, Mock, patch

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QColor, QImage, QKeyEvent, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication, QMenu

from src.config.cache import Cache
from src.controller.image_generation.generation_session import GenerationSession
from src.controller.image_generation.test_generator import TestGenerator
from src.image.layers.image_stack import ImageStack
from src.ui.generated_image_selector import GeneratedImageSelector, LABEL_TEXT_IMAGE_OPTION, ORIGINAL_CONTENT_LABEL, \
    SCROLL_DEBOUNCE_MS
from src.ui.generated_selector_bars import CANCEL_BUTTON_TEXT, CLOSE_BUTTON_TEXT, USE_OPTION_BUTTON_TEXT, VIEW_GRID, \
    VIEW_SINGLE
from src.ui.window.main_window import MainWindow
from src.undo_stack import UndoStack
from src.util.application_state import AppStateTracker, APP_STATE_EDITING, APP_STATE_SELECTION
from src.util.async_task import AsyncTask
from src.util.shared_constants import EDIT_MODE_IMG2IMG
from test.base_test_case import IntraPaintTestCase
from test.image.layers.image_stack_state import select_rect

app = QApplication.instance() or QApplication(sys.argv)

# pylint: disable=protected-access

IMAGE_SIZE = QSize(64, 64)
# The number of images each test batch delivers: `Cache.BATCH_SIZE` with `Cache.BATCH_COUNT` left at 1.
OPTION_COUNT = 5
# A fake clock reading later than any `time.time()` the selector recorded before the test:
_CLOCK_BASE = time.time() + 3600


def _solid(color: QColor, size: QSize = IMAGE_SIZE) -> QImage:
    """An image filled with one color."""
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color)
    return image


def _option_image(index: int, size: QSize = IMAGE_SIZE) -> QImage:
    """A distinct image standing in for one generated option."""
    return _solid(QColor(index * 40, 128, 255 - index * 40), size)


class GeneratedImageSelectorViewTest(IntraPaintTestCase):
    """Tests that manual pan and zoom carry between options while the same batch is showing."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(IMAGE_SIZE, IMAGE_SIZE, QSize(8, 8), IMAGE_SIZE)
        self.selector = GeneratedImageSelector(self.image_stack, GenerationSession(self.image_stack), lambda: None)
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

    def test_new_options_drops_manual_view(self) -> None:
        """A new batch starts without the old manual view."""
        self._manual_zoom(2.0, QPointF(3.0, -2.0))
        self.selector.start_new_options()
        self.selector._zoom_to_option(0, True)
        self.assertAlmostEqual(self._scale_ratio(), 1.0, places=3)
        self.assertEqual(self.selector._view.offset, self.selector._base_option_offset)


class GeneratedImageSelectorBatchTest(IntraPaintTestCase):
    """Tests the batch snapshot, archiving and re-opening."""

    def setUp(self) -> None:
        super().setUp()
        cache = Cache()
        # Option images are stored and compared at the generation area's own size, which keeps the pixel assertions
        # below exact:
        cache.set(Cache.GENERATION_SIZE, IMAGE_SIZE)
        cache.set(Cache.EDIT_SIZE, IMAGE_SIZE)
        self.image_stack = ImageStack(IMAGE_SIZE, IMAGE_SIZE, QSize(8, 8), IMAGE_SIZE)
        self.image_stack.load_image(_solid(QColor(200, 10, 10)))
        self.selector = GeneratedImageSelector(self.image_stack, GenerationSession(self.image_stack), lambda: None)
        self.selector.resize(400, 300)

    def _fill_batch(self) -> None:
        """Replaces every loading placeholder with a distinct image, as a completed run does."""
        for idx in range(len(self.selector._option_items) - 1):
            self.selector.add_image_option(_option_image(idx), idx)

    def _record_availability(self) -> list[bool]:
        """Collects the values `previous_options_available` emits for the rest of the test."""
        emissions: list[bool] = []
        self.selector.previous_options_available.connect(emissions.append)
        return emissions

    def test_new_options_snapshots_content_and_placeholders(self) -> None:
        """A new batch starts from the content on the canvas and reserves a placeholder per expected image."""
        self.image_stack.flush_render()
        current = self.image_stack.qimage_generation_area_content()
        self.selector.start_new_options()
        self.assertEqual(self.selector._session.current.option_images[0], current)
        self.assertEqual(len(self.selector._option_items), OPTION_COUNT + 1)
        self.assertFalse(self.selector._session.current.has_results())

    def test_snapshot_uses_generation_area_mask_crop(self) -> None:
        """The batch's mask is the generation area crop, the size the option images are applied at."""
        self.image_stack.generation_area = QRect(QPoint(0, 0), QSize(32, 32))
        select_rect(self.image_stack, QRect(QPoint(4, 4), QSize(8, 8)))
        self.selector.start_new_options()
        batch = self.selector._session.current
        self.assertEqual(batch.mask_image.size(), QSize(32, 32))
        self.assertNotEqual(batch.mask_image.size(), self.image_stack.selection_layer.image.size())

    def test_snapshot_stores_raw_edit_mode(self) -> None:
        """The batch stores the value `Cache.EDIT_MODE` holds, not a translated label."""
        self.assertEqual(self.selector._session.current.edit_mode, Cache().get(Cache.EDIT_MODE))

    def test_archive_skips_batch_without_results(self) -> None:
        """Archiving a batch of placeholders stores nothing."""
        emissions = self._record_availability()
        self.selector.archive_current_options()
        self.assertIsNone(self.selector._session.previous)
        self.assertFalse(self.selector.can_restore_previous())
        self.assertEqual(emissions, [])

    def test_archive_keeps_completed_batch(self) -> None:
        """Archiving a completed batch stores it, without its placeholders."""
        self._fill_batch()
        batch = self.selector._session.current
        self.selector.archive_current_options()
        self.assertIs(self.selector._session.previous, batch)
        self.assertEqual(len(batch.option_images), OPTION_COUNT + 1)
        self.assertNotIn(batch.loading_image, batch.option_images)

    def test_can_restore_previous_when_batch_no_longer_fits(self) -> None:
        """A stored batch that the image no longer contains cannot be re-opened."""
        self._fill_batch()
        self.selector.archive_current_options()
        self.assertTrue(self.selector.can_restore_previous())
        self.image_stack.size = QSize(16, 16)
        self.assertFalse(self.selector.can_restore_previous())

    def test_load_drops_stored_batch(self) -> None:
        """Loading another image, even at the same size, drops the stored batch."""
        self._fill_batch()
        self.selector.archive_current_options()
        emissions = self._record_availability()
        self.image_stack.load_image(_solid(QColor(0, 0, 255), self.image_stack.size))
        self.assertIsNone(self.selector._session.previous)
        self.assertFalse(self.selector.can_restore_previous())
        self.assertEqual(emissions, [False])

    def test_restore_raises_without_a_stored_batch(self) -> None:
        """Re-opening with nothing stored raises rather than showing an empty screen."""
        with self.assertRaises(RuntimeError):
            self.selector.restore_previous_options()

    def test_restore_starts_on_full_view(self) -> None:
        """Re-opening shows every option unzoomed, whatever zoom state the batch closed with."""
        self._fill_batch()
        self.selector.toggle_zoom(2)
        self.selector._zoom_to_option(2, True)
        self.selector.archive_current_options()

        self.selector.start_new_options()
        self.selector.restore_previous_options()
        self.assertFalse(self.selector._zoomed_in)
        self.assertEqual(self.selector._zoom_index, 0)
        self.assertEqual(self.selector._option_pos_offset, QPointF(0.0, 0.0))
        self.assertEqual(self.selector._option_scale_ratio, 1.0)
        for item in self.selector._option_items:
            self.assertEqual(item.opacity(), 1.0)

    def test_restore_reuses_option_items(self) -> None:
        """Re-opening reuses the stored items for generated options, and only builds a new one for the first slot."""
        self._fill_batch()
        stored_items = list(self.selector._option_items)
        self.selector.archive_current_options()
        self.selector.start_new_options()

        self.selector.restore_previous_options()
        self.assertIsNot(self.selector._option_items[0], stored_items[0])
        self.assertEqual(self.selector._option_items[1:], stored_items[1:])

    def test_partial_batch_restores_without_placeholders(self) -> None:
        """A batch closed before every image arrived re-opens with only the delivered images, under their labels."""
        self.selector.add_image_option(_option_image(0), 0)
        self.selector.add_image_option(_option_image(2), 2)
        self.selector.toggle_zoom(OPTION_COUNT)  # A placeholder, dropped on archive.
        self.selector.archive_current_options()

        self.selector.restore_previous_options()
        self.assertEqual([item.text for item in self.selector._option_items],
                         [ORIGINAL_CONTENT_LABEL, LABEL_TEXT_IMAGE_OPTION.format(index=1),
                          LABEL_TEXT_IMAGE_OPTION.format(index=3)])
        self.assertEqual(self.selector._session.current.option_images[1:], [_option_image(0), _option_image(2)])

    def test_restore_shows_current_content_in_first_slot(self) -> None:
        """The first option of a re-opened batch is what is on the canvas now, not the batch's original."""
        self._fill_batch()
        self.selector.archive_current_options()
        self.image_stack.create_layer(layer_name='new content', image_data=_solid(QColor(0, 200, 0)))
        self.image_stack.flush_render()
        current = self.image_stack.qimage_generation_area_content()

        self.selector.restore_previous_options()
        self.assertEqual(self.selector._session.current.option_images[0], current)
        self.assertEqual(self.selector._option_items[0].full_image, current)

    def test_restore_is_repeatable(self) -> None:
        """Closing a re-opened batch keeps it stored, so re-opening works again."""
        self._fill_batch()
        self.selector.archive_current_options()
        for _ in range(2):
            self.selector.restore_previous_options()
            self.selector.archive_current_options()
        self.assertTrue(self.selector.can_restore_previous())

    def test_restore_uses_batch_selection_not_current_selection(self) -> None:
        """Changing the selection after a batch was archived does not reach into the re-opened batch."""
        select_rect(self.image_stack, QRect(QPoint(0, 0), QSize(16, 16)))
        self.selector.start_new_options()
        self._fill_batch()
        saved_change_bounds = self.selector._session.current.change_bounds
        self.selector.archive_current_options()

        select_rect(self.image_stack, QRect(QPoint(48, 48), QSize(16, 16)))
        self.selector.restore_previous_options()
        self.assertEqual(self.selector._change_bounds, saved_change_bounds)

    def _switch_live_mode_to_img2img(self) -> None:
        """Moves the app's current mode away from the batch's inpaint mode."""
        cache = Cache()
        cache.set(Cache.EDIT_MODE, EDIT_MODE_IMG2IMG)

    def test_rebuild_uses_batch_edit_mode_not_live_cache(self) -> None:
        """Re-opening an inpaint batch keeps its selection controls after the mode was switched away from."""
        select_rect(self.image_stack, QRect(QPoint(0, 0), QSize(16, 16)))
        # The batch captured in setUp saw no selection; re-capture so this one carries the mask and change bounds:
        self.selector.start_new_options()
        self._fill_batch()
        self.selector.archive_current_options()
        self._switch_live_mode_to_img2img()

        self.selector.start_new_options()
        self.assertFalse(self.selector._selection_outline_checkbox.isEnabled())

        self.selector.restore_previous_options()
        self.assertTrue(self.selector._selection_outline_checkbox.isEnabled())
        self.assertEqual(len(self.selector._selections), len(self.selector._option_items))

    def test_apply_uses_batch_edit_mode_and_mask(self) -> None:
        """Applying a re-opened inpaint batch masks with its own mask, even when the app is no longer inpainting."""
        select_rect(self.image_stack, QRect(QPoint(0, 0), QSize(16, 16)))
        # The batch captured in setUp saw no selection; re-capture so this one carries the mask:
        self.selector.start_new_options()
        self._fill_batch()
        batch = self.selector._session.current
        self.selector.archive_current_options()
        self._switch_live_mode_to_img2img()
        self.selector.restore_previous_options()
        self.assertIs(self.selector._session.current, batch)

        applied = Mock()
        with patch.object(self.image_stack, 'set_generation_area_content', applied):
            self.selector._session.apply(1, self.image_stack.active_layer, 'Option 1')
        image = applied.call_args.args[0]
        self.assertEqual(image.pixelColor(4, 4).alpha(), 255)
        self.assertEqual(image.pixelColor(40, 40).alpha(), 0)

    def test_apply_clips_with_batch_paste_mask(self) -> None:
        """An inpaint batch started with a paste mask applies options through it, not through the hard selection."""
        select_rect(self.image_stack, QRect(QPoint(0, 0), QSize(16, 16)))
        self.selector.start_new_options(_solid(QColor(0, 0, 0, 128)))
        self._fill_batch()
        select_rect(self.image_stack, QRect(QPoint(48, 48), QSize(16, 16)))

        applied = Mock()
        with patch.object(self.image_stack, 'set_generation_area_content', applied):
            self.selector._session.apply(1, self.image_stack.active_layer, 'Option 1')
        image = applied.call_args.args[0]
        self.assertEqual(image.pixelColor(4, 4).alpha(), 128)
        self.assertEqual(image.pixelColor(40, 40).alpha(), 128)

    def test_availability_signal_reports_each_change(self) -> None:
        """The signal reports when a batch becomes restorable, and again when it stops fitting the image."""
        emissions = self._record_availability()
        self._fill_batch()
        self.selector.archive_current_options()
        self.selector.restore_previous_options()
        self.image_stack.size = QSize(16, 16)
        self.image_stack.size = QSize(64, 64)
        self.assertEqual(emissions, [True, False, True])

    def test_size_change_reports_lost_batch(self) -> None:
        """Shrinking the image past the stored batch's area reports it unavailable."""
        self._fill_batch()
        self.selector.archive_current_options()
        emissions = self._record_availability()
        self.image_stack.size = QSize(16, 16)
        self.assertEqual(emissions, [False])


class GeneratedImageSelectorWindowTest(IntraPaintTestCase):
    """Tests the re-open flow through MainWindow, which is what decides which batch a showing displays."""

    def setUp(self) -> None:
        super().setUp()
        cache = Cache()
        cache.set(Cache.GENERATION_SIZE, IMAGE_SIZE)
        cache.set(Cache.EDIT_SIZE, IMAGE_SIZE)
        self.image_stack = ImageStack(IMAGE_SIZE, IMAGE_SIZE, QSize(8, 8), IMAGE_SIZE)
        self.image_stack.load_image(_solid(QColor(200, 10, 10)))
        self.window = MainWindow(self.image_stack)
        self.selector: GeneratedImageSelector = self.window._ensure_image_selector()

    def _run_completed_generation(self) -> None:
        """Shows the selector for a generation and delivers every expected image."""
        self.window.show_generated_options()
        for idx in range(len(self.selector._option_items) - 1):
            self.window.load_sample_preview(_option_image(idx), idx)

    def test_reopen_shows_stored_images_not_placeholders(self) -> None:
        """Re-opening shows the stored batch instead of a new batch of loading placeholders."""
        select_rect(self.image_stack, QRect(QPoint(0, 0), QSize(16, 16)))
        self._run_completed_generation()
        stored = self.selector._session.current
        self.window.set_image_selector_visible(False)

        self.assertTrue(self.window.can_restore_previous_options())
        self.window.restore_previous_image_selection_options()
        self.assertTrue(self.window.is_image_selector_visible())
        self.assertIs(self.window._image_selector, self.selector)
        self.assertIs(self.selector._session.current, stored)
        self.assertEqual(len(self.selector._option_items), OPTION_COUNT + 1)
        for idx in range(1, len(self.selector._option_items)):
            self.assertEqual(self.selector._option_items[idx].full_image, _option_image(idx - 1))

    def test_show_generated_options_starts_a_new_batch(self) -> None:
        """Showing the screen for a new generation captures the canvas now, and does not re-show the old batch."""
        self._run_completed_generation()
        self.window.set_image_selector_visible(False)
        self.image_stack.create_layer(layer_name='new content', image_data=_solid(QColor(0, 200, 0)))
        self.image_stack.flush_render()
        current = self.image_stack.qimage_generation_area_content()

        self.window.show_generated_options()
        self.assertEqual(self.selector._session.current.option_images[0], current)
        self.assertIn(self.selector._session.current.loading_image, self.selector._session.current.option_images)

    def test_cancel_keeps_the_batch_reopenable(self) -> None:
        """Closing with the Cancel button keeps the batch, and the tooltip no longer claims it is discarded."""
        self._run_completed_generation()
        self.selector._button_bar.close_button.click()
        self.assertFalse(self.window.is_image_selector_visible())
        self.assertTrue(self.window.can_restore_previous_options())

    def test_escape_keeps_the_batch_reopenable(self) -> None:
        """Closing with Escape keeps the batch too."""
        self._run_completed_generation()
        self.selector._close_and_archive()
        self.assertTrue(self.window.can_restore_previous_options())

    def test_selecting_an_option_keeps_the_batch_reopenable(self) -> None:
        """Applying an option stores the batch, and re-opening shows the canvas it was applied to in the first slot."""
        select_rect(self.image_stack, QRect(QPoint(0, 0), QSize(16, 16)))
        self._run_completed_generation()
        self.selector._select_option_and_close(3)
        self.assertFalse(self.window.is_image_selector_visible())
        self.image_stack.flush_render()

        self.window.restore_previous_image_selection_options()
        self.assertFalse(self.selector._zoomed_in)
        canvas = self.image_stack.qimage_generation_area_content()
        self.assertEqual(self.selector._option_items[0].full_image, canvas)
        # Option index 3 holds the image built for `_option_image(2)`, and its pixels reached the canvas inside the
        # selection:
        self.assertEqual(canvas.pixelColor(4, 4), _option_image(2).pixelColor(4, 4))
        self.assertNotEqual(canvas.pixelColor(40, 40), _option_image(2).pixelColor(40, 40))

    def test_selector_close_from_the_generator_keeps_the_batch(self) -> None:
        """A hide the selector didn't ask for, such as a failed generation, still keeps what was on show."""
        self._run_completed_generation()
        self.window.set_image_selector_visible(False)
        self.assertTrue(self.window.can_restore_previous_options())

    def test_reopen_selection_screen_uses_the_selection_app_state(self) -> None:
        """A re-opened screen is a selection screen, so editing actions follow it."""
        self._run_completed_generation()
        self.window.set_image_selector_visible(False)
        self.assertEqual(AppStateTracker.app_state(), APP_STATE_EDITING)
        self.window.restore_previous_image_selection_options()
        self.assertEqual(AppStateTracker.app_state(), APP_STATE_SELECTION)

    def test_window_relists_availability_once_per_change(self) -> None:
        """MainWindow relays re-open availability, including the visibility it adds to the condition."""
        emissions: list[bool] = []
        self.window.previous_options_available.connect(emissions.append)
        self._run_completed_generation()
        self.window.set_image_selector_visible(False)
        self.window.restore_previous_image_selection_options()
        self.window.set_image_selector_visible(False)
        self.assertEqual(emissions, [True, False, True])

    def _deliver_only(self, count: int) -> None:
        """Runs a generation that delivers fewer images than the batch expects."""
        self.window.show_generated_options()
        for idx in range(count):
            self.window.load_sample_preview(_option_image(idx), idx)

    def test_late_preview_after_close_is_dropped(self) -> None:
        """A result that arrives after the screen closed is ignored instead of raising in the delivery timer."""
        self._deliver_only(2)
        self.window.set_image_selector_visible(False)
        stored_images = list(self.selector._session.current.option_images)
        self.window.load_sample_preview(_option_image(4), 4)
        self.assertEqual(self.selector._session.current.option_images, stored_images)

    def test_late_preview_cannot_reach_a_reopened_batch(self) -> None:
        """A late result from an older run has no slot in a re-opened batch, and is ignored rather than raising."""
        self._deliver_only(2)
        self.window.set_image_selector_visible(False)
        self.window.restore_previous_image_selection_options()
        stored_images = list(self.selector._session.current.option_images)
        # The re-opened batch is on screen and shorter than the run's placeholder row:
        self.assertTrue(self.window.is_image_selector_visible())
        self.window.load_sample_preview(_option_image(4), 4)
        self.assertEqual(self.selector._session.current.option_images, stored_images)
        self.assertEqual(len(self.selector._option_items), len(stored_images))


class GeneratedImageSelectorGenerationTest(IntraPaintTestCase):
    """Drives a real generator against a real MainWindow.

    The generator tests hand the window a mock, so a call the window doesn't implement fails only here.
    """

    def setUp(self) -> None:
        super().setUp()
        cache = Cache()
        cache.set(Cache.GENERATION_SIZE, IMAGE_SIZE)
        cache.set(Cache.EDIT_SIZE, IMAGE_SIZE)
        cache.set(Cache.BATCH_COUNT, 1)
        cache.set(Cache.BATCH_SIZE, OPTION_COUNT)
        self.image_stack = ImageStack(IMAGE_SIZE, IMAGE_SIZE, QSize(8, 8), IMAGE_SIZE)
        self.image_stack.load_image(_solid(QColor(10, 20, 30)))
        self.window = MainWindow(self.image_stack)
        self.generator = TestGenerator(self.window, self.image_stack)
        # Results reach the window through a main-thread timer, which these tests bypass:
        self.generator._cache_generated_image = self.window.generation_session.store_result  # type: ignore
        start_patch = patch.object(AsyncTask, 'start', AsyncTask.run)
        start_patch.start()
        self.addCleanup(start_patch.stop)

    def _generate(self) -> GeneratedImageSelector:
        """Runs one generation to completion and returns the selection screen it produced."""
        select_rect(self.image_stack, QRect(QPoint(0, 0), QSize(16, 16)))
        self.generator.start_and_manage_image_generation()
        selector = self.window._image_selector
        self.assertIsInstance(selector, GeneratedImageSelector)
        return selector

    def test_a_real_generation_fills_the_selection_screen(self) -> None:
        """A completed run leaves real images on screen and no placeholders."""
        selector = self._generate()
        self.assertTrue(self.window.is_image_selector_visible())
        self.assertEqual(len(selector._option_items), OPTION_COUNT + 1)
        self.assertNotIn(selector._session.current.loading_image, selector._session.current.option_images)

    def test_a_failed_generation_closes_the_selection_screen_and_shows_the_error(self) -> None:
        """An error from the backend hides the selection screen, ends loading and opens the error dialog."""
        error = ValueError('bad input')
        self.generator.generate = MagicMock(side_effect=error)  # type: ignore
        with patch('src.ui.window.main_window.show_error_dialog') as show_error_dialog:
            select_rect(self.image_stack, QRect(QPoint(0, 0), QSize(16, 16)))
            self.generator.start_and_manage_image_generation()
        self.assertFalse(self.window.is_image_selector_visible())
        self.assertFalse(self.window._is_loading)
        show_error_dialog.assert_called_once()
        self.assertIs(show_error_dialog.call_args.args[2], error)

    def test_reopening_after_a_real_generation_shows_the_generated_images(self) -> None:
        """The headline regression: closing and re-opening shows the run's images, not a fresh placeholder batch."""
        selector = self._generate()
        generated = list(selector._session.current.option_images)
        batch = selector._session.current
        self.window.set_image_selector_visible(False)

        self.window.restore_previous_image_selection_options()
        self.assertIs(selector._session.current, batch)
        self.assertNotIn(selector._session.current.loading_image, selector._session.current.option_images)
        self.assertEqual(len(selector._option_items), len(generated))
        for idx in range(1, len(generated)):
            self.assertEqual(selector._option_items[idx].full_image, generated[idx])

    def test_applying_from_a_reopened_batch_is_undoable(self) -> None:
        """Applying an option of a re-opened batch is an ordinary undoable edit."""
        self._generate()
        self.window.set_image_selector_visible(False)
        self.image_stack.flush_render()
        before = self.image_stack.qimage()

        self.window.restore_previous_image_selection_options()
        self.window._image_selector._select_option_and_close(2)
        self.image_stack.flush_render()
        self.assertNotEqual(self.image_stack.qimage(), before)

        UndoStack().undo()
        self.image_stack.flush_render()
        self.assertEqual(self.image_stack.qimage(), before)


class _RunScreenTestCase(IntraPaintTestCase):
    """Base for tests that run a generation in a `MainWindow` with a fake backend action.

    The action runs synchronously in place of the background task.
    """

    BATCH = 4

    def setUp(self) -> None:
        super().setUp()
        cache = Cache()
        cache.set(Cache.GENERATION_SIZE, IMAGE_SIZE)
        cache.set(Cache.EDIT_SIZE, IMAGE_SIZE)
        cache.set(Cache.BATCH_COUNT, 1)
        cache.set(Cache.BATCH_SIZE, self.BATCH)
        self.image_stack = ImageStack(IMAGE_SIZE, IMAGE_SIZE, QSize(8, 8), IMAGE_SIZE)
        self.image_stack.load_image(_solid(QColor(10, 20, 30)))
        self.window = MainWindow(self.image_stack)
        self.session = self.window.generation_session
        self.cancel_requests: list[bool] = []
        self.window.cancel_generation.connect(lambda: self.cancel_requests.append(True))
        start_patch = patch.object(AsyncTask, 'start', AsyncTask.run)
        start_patch.start()
        self.addCleanup(start_patch.stop)

    @property
    def selector(self) -> GeneratedImageSelector:
        """The selection screen the run opened."""
        selector = self.window._image_selector
        assert selector is not None
        return selector

    def _deliver(self, idx: int) -> None:
        """Delivers one result the way a backend does, minus the main-thread timer hop."""
        self.session.store_result(_option_image(idx), idx)
        self.session.deliver_result(idx)

    def _run(self, action) -> None:
        select_rect(self.image_stack, QRect(QPoint(0, 0), QSize(16, 16)))
        image = self.image_stack.qimage_generation_area_content()
        self.session.generate(lambda _status, _image, _mask: action(), image, None, None)

class GeneratedImageSelectorRunTest(_RunScreenTestCase):
    """Tests how a run's Cancel, Stop and end close or keep the selection screen.

    The action plays the user's part by clicking the screen's buttons partway through.
    """

    def test_cancel_before_first_result_closes_and_stops(self) -> None:
        """With nothing ready the only exit is Cancel, which stops the backend and returns to the editor."""
        def _action() -> None:
            self.assertTrue(self.window.is_image_selector_visible())
            self.assertEqual(self.selector._button_bar.close_button.text(), CANCEL_BUTTON_TEXT)
            self.assertFalse(self.selector._button_bar.stop_button.isVisibleTo(self.selector))
            self.selector._button_bar.close_button.click()
        self._run(_action)
        self.assertFalse(self.window.is_image_selector_visible())
        self.assertEqual(self.cancel_requests, [True])
        self.assertFalse(self.window.can_restore_previous_options())

    def test_stop_after_two_of_four_keeps_two(self) -> None:
        """Stop ends the run, keeps the two options that arrived, and drops the placeholders for the rest."""
        def _action() -> None:
            self._deliver(0)
            self._deliver(1)
            self.assertEqual(self.selector._button_bar.close_button.text(), CLOSE_BUTTON_TEXT)
            self.assertTrue(self.selector._button_bar.stop_button.isVisibleTo(self.selector))
            self.selector._button_bar.stop_button.click()
        self._run(_action)
        self.assertEqual(self.cancel_requests, [True])
        self.assertTrue(self.window.is_image_selector_visible())
        self.assertEqual(len(self.selector._option_items), 3)
        self.assertNotIn(self.session.current.loading_image, self.session.current.option_images)
        self.assertFalse(self.selector._button_bar.stop_button.isVisibleTo(self.selector))
        self.assertEqual(self.selector._button_bar.close_button.text(), CLOSE_BUTTON_TEXT)

    def test_stop_with_no_results_closes_and_reports(self) -> None:
        """A stopped run that produced nothing closes the screen and says why on the canvas."""
        self._run(self.session.stop)
        self.assertFalse(self.window.is_image_selector_visible())
        self.assertIsNotNone(self.window._toast_message)

    def test_empty_run_closes_and_reports(self) -> None:
        """A run that ends without images closes the screen and says why on the canvas."""
        self._run(lambda: None)
        self.assertFalse(self.window.is_image_selector_visible())
        self.assertIsNotNone(self.window._toast_message)

    def test_failure_with_zero_results_closes(self) -> None:
        """A failure before any image arrived closes the screen, and the error dialog reports it."""
        def _raises() -> None:
            raise ValueError('bad input')
        with patch('src.ui.window.main_window.show_error_dialog') as show_error_dialog:
            self._run(_raises)
        show_error_dialog.assert_called_once()
        # The recorded exception's traceback holds the task's frames:
        show_error_dialog.reset_mock()
        self.assertFalse(self.window.is_image_selector_visible())

    def test_failure_after_results_keeps_them(self) -> None:
        """A failure after some images arrived reports the error and keeps those options on screen."""
        def _partial() -> None:
            self._deliver(0)
            raise ValueError('bad input')
        with patch('src.ui.window.main_window.show_error_dialog') as show_error_dialog:
            self._run(_partial)
        # The recorded exception's traceback holds the task's frames:
        show_error_dialog.reset_mock()
        self.assertTrue(self.window.is_image_selector_visible())
        self.assertEqual(len(self.selector._option_items), 2)

    def test_use_button_applies_the_focused_option(self) -> None:
        """The primary button names the focused option and applies it."""
        def _action() -> None:
            for idx in range(self.BATCH):
                self._deliver(idx)
        self._run(_action)
        self.selector._zoom_to_option(3, True)
        self.assertEqual(self.selector._button_bar.use_button.text(), USE_OPTION_BUTTON_TEXT.format(index=3))
        self.selector._button_bar.use_button.click()
        self.assertFalse(self.window.is_image_selector_visible())
        self.image_stack.flush_render()
        canvas = self.image_stack.qimage_generation_area_content()
        self.assertEqual(canvas.pixelColor(4, 4), _option_image(2).pixelColor(4, 4))

    def test_view_modes_and_compare_keep_focus(self) -> None:
        """Switching between grid and single views, and holding the compare modifier, leave the focus in place."""
        def _action() -> None:
            for idx in range(self.BATCH):
                self._deliver(idx)
        self._run(_action)
        selector = self.selector
        selector.toggle_zoom(2)
        selector.toggle_zoom()
        self.assertFalse(selector._zoomed_in)
        self.assertEqual(selector._zoom_index, 2)

        selector._view_mode_changed(VIEW_SINGLE)
        self.assertTrue(selector._zoomed_in)
        self.assertEqual(selector._zoom_index, 2)

        selector.eventFilter(selector._view, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Alt,
                                                       Qt.KeyboardModifier.AltModifier))
        self.assertTrue(selector._comparing)
        self.assertTrue(selector._compare_item.isVisible())
        self.assertEqual(selector._zoom_index, 2)
        selector.eventFilter(selector._view, QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Alt,
                                                       Qt.KeyboardModifier.NoModifier))
        self.assertFalse(selector._comparing)
        self.assertFalse(selector._compare_item.isVisible())

        selector._view_mode_changed(VIEW_GRID)
        self.assertFalse(selector._zoomed_in)
        self.assertEqual(selector._zoom_index, 2)

    def test_compare_needs_single_view(self) -> None:
        """Holding the compare modifier in the grid view shows nothing in place of an option."""
        def _action() -> None:
            self._deliver(0)
        self._run(_action)
        self.selector._zoom_index = 1
        self.selector.eventFilter(self.selector._view, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Alt,
                                                                 Qt.KeyboardModifier.AltModifier))
        self.assertFalse(self.selector._comparing)


class GeneratedImageSelectorInputTest(_RunScreenTestCase):
    """Tests the keyboard, wheel and mouse handling in `eventFilter`, and the option context menu."""

    def setUp(self) -> None:
        super().setUp()

        def _action() -> None:
            for idx in range(self.BATCH):
                self._deliver(idx)
        self._run(_action)
        self.selector.resize(400, 300)

    def _key(self, key: Qt.Key, text: str = '', event_type: QEvent.Type = QEvent.Type.KeyPress) -> bool:
        event = QKeyEvent(event_type, key, Qt.KeyboardModifier.NoModifier, text)
        return bool(self.selector.eventFilter(self.selector._view, event))

    def _wheel(self, dx: int, source=None) -> bool:
        event = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(dx, 0), Qt.MouseButton.NoButton,
                            Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
        return bool(self.selector.eventFilter(source or self.selector._view, event))

    def _mouse(self, event_type: QEvent.Type, pos: QPoint, button: Qt.MouseButton = Qt.MouseButton.LeftButton) -> bool:
        event = QMouseEvent(event_type, QPointF(pos), QPointF(pos), button, button, Qt.KeyboardModifier.NoModifier)
        return bool(self.selector.eventFilter(self.selector._view, event))

    def _option_center(self, idx: int) -> QPoint:
        """The view position at the center of an option."""
        return self.selector._view.scene_point_to_widget(self.selector._option_items[idx].bounds.center())

    def test_number_keys_focus_that_option(self) -> None:
        """A digit key focuses the matching option and is consumed; out-of-range digits and other keys are not."""
        self.assertTrue(self._key(Qt.Key.Key_3, '3'))
        self.assertEqual(self.selector._zoom_index, 3)
        self.assertFalse(self._key(Qt.Key.Key_9, '9'))
        self.assertEqual(self.selector._zoom_index, 3)
        self.assertFalse(self._key(Qt.Key.Key_A, 'a'))
        self.assertEqual(self.selector._zoom_index, 3)

    def _wheel_at(self, clock: Mock, ms: float, dx: int) -> bool:
        """Sends a wheel event with the selector's clock reading `ms` milliseconds."""
        clock.return_value = _CLOCK_BASE + ms / 1000
        return self._wheel(dx)

    def test_wheel_steps_through_options(self) -> None:
        """Horizontal wheel motion steps forward or back and is consumed; vertical-only motion is not."""
        self.selector._zoom_to_option(1, True)
        with patch('src.ui.generated_image_selector.time.time') as clock:
            self.assertTrue(self._wheel_at(clock, 1000, 120))
            self.assertEqual(self.selector._zoom_index, 2)
            self.assertTrue(self._wheel_at(clock, 2000, -120))
            self.assertEqual(self.selector._zoom_index, 1)
            self.assertFalse(self._wheel_at(clock, 3000, 0))
            self.assertEqual(self.selector._zoom_index, 1)

    def test_wheel_steps_are_debounced(self) -> None:
        """Wheel events closer together than SCROLL_DEBOUNCE_MS are consumed without stepping again."""
        self.selector._zoom_to_option(1, True)
        with patch('src.ui.generated_image_selector.time.time') as clock:
            self._wheel_at(clock, 1000, 120)
            self.assertTrue(self._wheel_at(clock, 1000 + SCROLL_DEBOUNCE_MS - 1, 120))
            self.assertEqual(self.selector._zoom_index, 2)
            self.assertTrue(self._wheel_at(clock, 1000 + SCROLL_DEBOUNCE_MS + 1, 120))
            self.assertEqual(self.selector._zoom_index, 3)

    def test_wheel_from_another_source_does_not_step_again(self) -> None:
        """A wheel event bubbling up from the view is ignored, so it doesn't step twice."""
        self.selector._zoom_to_option(1, True)
        with patch('src.ui.generated_image_selector.time.time') as clock:
            clock.return_value = _CLOCK_BASE + 1.0
            self.assertFalse(self._wheel(120, source=self.window))
        self.assertEqual(self.selector._zoom_index, 1)

    def test_escape_leaves_single_view_before_closing(self) -> None:
        """Escape returns from the single view to the grid first, and closes the screen from the grid."""
        self.selector.toggle_zoom(2)
        self.assertTrue(self.selector._zoomed_in)
        self.assertTrue(self._key(Qt.Key.Key_Escape))
        self.assertFalse(self.selector._zoomed_in)
        self.assertTrue(self.window.is_image_selector_visible())
        self.assertTrue(self._key(Qt.Key.Key_Escape))
        self.assertFalse(self.window.is_image_selector_visible())

    def test_enter_applies_the_focused_option(self) -> None:
        """Enter applies the focused option and closes the screen."""
        self.selector._zoom_to_option(2, True)
        self.assertTrue(self._key(Qt.Key.Key_Return))
        self.assertFalse(self.window.is_image_selector_visible())
        self.image_stack.flush_render()
        canvas = self.image_stack.qimage_generation_area_content()
        self.assertEqual(canvas.pixelColor(4, 4), _option_image(1).pixelColor(4, 4))

    def test_enter_ignores_an_unfinished_option(self) -> None:
        """Enter on a loading placeholder does nothing."""
        self.session.current.option_images[2] = self.session.current.loading_image
        self.selector._zoom_index = 2
        self.assertTrue(self._key(Qt.Key.Key_Return))
        self.assertTrue(self.window.is_image_selector_visible())

    def test_modifier_release_and_focus_loss_end_comparing(self) -> None:
        """Releasing the compare modifier, or losing focus, stops comparing."""
        self.selector.toggle_zoom(2)
        for end_comparing in (lambda: self._key(Qt.Key.Key_Alt, event_type=QEvent.Type.KeyRelease),
                              lambda: self.selector.eventFilter(self.selector._view, QEvent(QEvent.Type.FocusOut))):
            self.selector.eventFilter(self.selector._view, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Alt,
                                                                     Qt.KeyboardModifier.AltModifier))
            self.assertTrue(self.selector._comparing)
            end_comparing()
            self.assertFalse(self.selector._comparing)

    def test_left_click_applies_the_option_under_the_cursor(self) -> None:
        """A left click on a finished option applies it and closes the screen."""
        self.assertEqual(self.selector._option_at(self._option_center(3)), 3)
        self._mouse(QEvent.Type.MouseButtonPress, self._option_center(3))
        self.assertFalse(self.window.is_image_selector_visible())
        self.image_stack.flush_render()
        canvas = self.image_stack.qimage_generation_area_content()
        self.assertEqual(canvas.pixelColor(4, 4), _option_image(2).pixelColor(4, 4))

    def test_click_on_a_placeholder_does_nothing(self) -> None:
        """Clicking an option that is still loading leaves the screen open."""
        self.session.current.option_images[3] = self.session.current.loading_image
        self._mouse(QEvent.Type.MouseButtonPress, self._option_center(3))
        self.assertTrue(self.window.is_image_selector_visible())

    def test_middle_click_and_empty_space_do_nothing(self) -> None:
        """Other buttons, and clicks outside every option, don't apply anything."""
        self._mouse(QEvent.Type.MouseButtonPress, self._option_center(1), Qt.MouseButton.MiddleButton)
        self.assertTrue(self.window.is_image_selector_visible())
        self.assertIsNone(self.selector._option_at(QPoint(-500, -500)))
        self._mouse(QEvent.Type.MouseButtonPress, QPoint(-500, -500))
        self.assertTrue(self.window.is_image_selector_visible())

    def test_hover_follows_the_cursor(self) -> None:
        """Moving over an option sets the hover index, and leaving the view clears it."""
        self._mouse(QEvent.Type.MouseMove, self._option_center(2), Qt.MouseButton.NoButton)
        self.assertEqual(self.selector._hover_index, 2)
        self.selector.eventFilter(self.selector._view, QEvent(QEvent.Type.Leave))
        self.assertIsNone(self.selector._hover_index)

    def test_right_click_opens_the_context_menu(self) -> None:
        """A right click on a finished option opens its context menu without applying it."""
        with patch.object(self.selector, '_show_context_menu') as show_menu:
            self._mouse(QEvent.Type.MouseButtonPress, self._option_center(2), Qt.MouseButton.RightButton)
        show_menu.assert_called_once()
        self.assertEqual(show_menu.call_args.args[0], 2)
        self.assertTrue(self.window.is_image_selector_visible())

    def _open_menu(self, idx: int, trigger: Optional[int] = None) -> int:
        """Opens an option's context menu with `exec` replaced, optionally triggering one action while it is open.

        Returns the number of actions the menu offered.
        """
        captured: dict = {}

        class _RecordingMenu(QMenu):
            def exec(self, *_args) -> None:  # type: ignore[override]
                captured['title'] = self.title()
                actions = self.actions()
                captured['count'] = len(actions)
                if trigger is not None:
                    actions[trigger].trigger()
        with patch('src.ui.generated_image_selector.QMenu', _RecordingMenu):
            self.selector._show_context_menu(idx, QPoint(5, 5))
        self.assertEqual(captured['title'], ORIGINAL_CONTENT_LABEL if idx == 0
                         else LABEL_TEXT_IMAGE_OPTION.format(index=idx))
        return captured['count']

    def test_context_menu_lists_three_actions(self) -> None:
        """The menu offers select, save and send to a new layer."""
        self.assertEqual(self._open_menu(1), 3)
        self.assertEqual(self._open_menu(0), 3)

    def test_context_menu_select_applies_the_option(self) -> None:
        """The menu's select action applies its option and closes the screen."""
        self._open_menu(4, trigger=0)
        self.assertFalse(self.window.is_image_selector_visible())
        self.image_stack.flush_render()
        canvas = self.image_stack.qimage_generation_area_content()
        self.assertEqual(canvas.pixelColor(4, 4), _option_image(3).pixelColor(4, 4))

    def test_context_menu_save_asks_for_a_path(self) -> None:
        """The menu's save action saves its option to the chosen path."""
        with patch('src.ui.generated_image_selector.open_image_file', return_value='/tmp/out.png'), \
                patch.object(self.session, 'save_to_file') as save:
            self._open_menu(2, trigger=1)
        save.assert_called_once_with(2, '/tmp/out.png')

    def test_context_menu_send_to_new_layer_keeps_the_screen_open(self) -> None:
        """Sending an option to a new layer adds a layer and keeps the selector open."""
        layer_count = len(self.image_stack.layers)
        self._open_menu(2, trigger=2)
        self.assertEqual(len(self.image_stack.layers), layer_count + 1)
        self.assertTrue(self.window.is_image_selector_visible())
        self.assertIsNotNone(self.selector._toast_message)

    def test_save_to_file_saves_the_option(self) -> None:
        """Saving writes the option to the chosen path, and cancelling the dialog writes nothing."""
        with patch('src.ui.generated_image_selector.open_image_file', return_value='/tmp/out.png'), \
                patch.object(self.session, 'save_to_file') as save:
            self.selector._save_to_file(2)
        save.assert_called_once_with(2, '/tmp/out.png')
        with patch('src.ui.generated_image_selector.open_image_file', return_value=None), \
                patch.object(self.session, 'save_to_file') as save:
            self.selector._save_to_file(2)
        save.assert_not_called()
        self.assertIsNotNone(self.selector._toast_message)

    def test_save_and_send_ignore_a_placeholder(self) -> None:
        """An option that hasn't arrived can't be saved or sent to a layer."""
        self.session.current.option_images[2] = self.session.current.loading_image
        layer_count = len(self.image_stack.layers)
        with patch('src.ui.generated_image_selector.open_image_file') as open_file:
            self.selector._save_to_file(2)
        open_file.assert_not_called()
        self.selector._send_to_new_layer(2)
        self.assertEqual(len(self.image_stack.layers), layer_count)
