"""Tests the generation orchestration in `ImageGenerator`: running `generate` as a task, collecting results, and
applying a chosen sample. Backends are replaced by a scripted subclass, and the main window by a mock."""
from typing import Optional, Any
from unittest import mock
from unittest.mock import MagicMock

from PIL import Image
from PySide6.QtCore import QPoint, QRect, QSize, Qt, SignalInstance
from PySide6.QtGui import QImage, QColor, QPainter
from PySide6.QtWidgets import QWidget

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller.image_generation.image_generator import ImageGenerator
from src.controller.image_generation.test_generator import TestGenerator
from src.image.layers.image_stack import ImageStack
from src.ui.modal.settings_modal import SettingsModal
from src.util.application_state import AppStateTracker, APP_STATE_EDITING
from src.util.async_task import AsyncTask
from src.util.shared_constants import EDIT_MODE_INPAINT, EDIT_MODE_TXT2IMG
from test.base_test_case import IntraPaintTestCase

IMAGE_SIZE = QSize(128, 128)
GENERATION_AREA = QRect(32, 32, 64, 64)
SELECTION_BOUNDS = QRect(48, 48, 16, 16)
SOURCE_COLOR = QColor(200, 30, 30)
GENERATED_COLOR = QColor(30, 30, 200)
BATCH_COUNT = 2
BATCH_SIZE = 2


def _solid(size: QSize, color: QColor) -> QImage:
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color)
    return image


class _ScriptedGenerator(TestGenerator):
    """Returns canned images, or raises a canned error, from `generate`."""

    def __init__(self, window, image_stack: ImageStack) -> None:
        super().__init__(window, image_stack)
        self.results: list[QImage] = []
        self.error: Optional[BaseException] = None
        self.generate_calls: list[tuple[QImage, Optional[QImage]]] = []
        self.status_updates: list[dict[str, str]] = []

    def generate(self, status_signal: SignalInstance, source_image: QImage,
                 mask_image: Optional[QImage] = None) -> None:
        self.generate_calls.append((source_image, mask_image))
        if self.error is not None:
            raise self.error
        for update in self.status_updates:
            status_signal.emit(update)  # type: ignore
        for index, image in enumerate(self.results):
            self._generated_images.append(image)
            self._cache_generated_image(image, index)


class ImageGeneratorTest(IntraPaintTestCase):
    """Covers task management, result handling and sample application."""

    def setUp(self) -> None:
        super().setUp()
        self.window = MagicMock()
        self.image_stack = ImageStack(IMAGE_SIZE, GENERATION_AREA.size(), QSize(8, 8), QSize(10240, 10240))
        self.image_stack.create_layer('source', _solid(IMAGE_SIZE, SOURCE_COLOR))
        self.image_stack.generation_area = GENERATION_AREA
        with self.image_stack.selection_layer.borrow_image() as mask_image:
            assert isinstance(mask_image, QImage)
            painter = QPainter(mask_image)
            painter.fillRect(SELECTION_BOUNDS, Qt.GlobalColor.black)
            painter.end()
        cache = Cache()
        cache.set(Cache.GENERATION_SIZE, GENERATION_AREA.size())
        cache.set(Cache.BATCH_COUNT, BATCH_COUNT)
        cache.set(Cache.BATCH_SIZE, BATCH_SIZE)
        cache.set(Cache.EDIT_MODE, EDIT_MODE_TXT2IMG)
        self.generator = _ScriptedGenerator(self.window, self.image_stack)
        # Results reach the window through a main-thread timer, which these tests bypass:
        self.generator._cache_generated_image = MagicMock()  # type: ignore # pylint: disable=protected-access

        start_patch = mock.patch.object(AsyncTask, 'start', AsyncTask.run)
        start_patch.start()
        self.addCleanup(start_patch.stop)
        error_patch = mock.patch('src.controller.image_generation.image_generator.show_error_dialog')
        self.show_error_dialog = error_patch.start()
        self.addCleanup(error_patch.stop)

    def _generated_images(self, count: int = BATCH_COUNT * BATCH_SIZE) -> list[QImage]:
        return [_solid(GENERATION_AREA.size(), GENERATED_COLOR) for _ in range(count)]

    def _loaded_previews(self) -> dict[int, QImage]:
        return {call.args[1]: call.args[0] for call in self.window.load_sample_preview.call_args_list}

    def test_generate_runs_with_generation_inputs(self) -> None:
        """The task passes the generation area content to `generate`, with no mask outside of inpainting."""
        self.generator.start_and_manage_image_generation()
        self.assertEqual(len(self.generator.generate_calls), 1)
        image, mask = self.generator.generate_calls[0]
        self.assertEqual(image.size(), GENERATION_AREA.size())
        self.assertEqual(image.pixelColor(10, 10), SOURCE_COLOR)
        self.assertIsNone(mask)
        self.window.show_generated_options.assert_called_once()

    def test_finished_task_resets_state_and_loads_previews(self) -> None:
        """After the task finishes, loading ends, a new request is accepted, and each image reaches the window."""
        images = self._generated_images()
        self.generator.results = images
        self.generator.start_and_manage_image_generation()
        self.window.set_is_loading.assert_called_with(False)
        self.assertEqual(self.generator._generating, False)  # pylint: disable=protected-access
        previews = self._loaded_previews()
        self.assertEqual(sorted(previews), list(range(BATCH_COUNT * BATCH_SIZE)))
        self.assertEqual(previews[0].pixelColor(5, 5), GENERATED_COLOR)

        self.generator.generate_calls.clear()
        self.generator.start_and_manage_image_generation()
        self.assertEqual(len(self.generator.generate_calls), 1)

    def test_images_beyond_expected_count_and_null_images_are_skipped(self) -> None:
        """Previews load only for non-null images within BATCH_COUNT * BATCH_SIZE."""
        images = self._generated_images(BATCH_COUNT * BATCH_SIZE + 2)
        images[1] = QImage()
        self.generator.results = images
        self.generator.start_and_manage_image_generation()
        self.assertEqual(sorted(self._loaded_previews()), [0, 2, 3])

    def test_duplicate_request_is_ignored_while_generating(self) -> None:
        """A request that arrives mid-generation does not start a second task."""
        self.generator._generating = True  # pylint: disable=protected-access
        self.generator.start_and_manage_image_generation()
        self.assertEqual(self.generator.generate_calls, [])
        self.window.show_generated_options.assert_not_called()

    def test_generate_error_closes_selector_and_shows_dialog(self) -> None:
        """Errors from `generate`, expected or not, close the selector, end loading and show an error dialog."""
        for error in (ValueError('bad input'), IOError('no server'), KeyError('surprise')):
            with self.subTest(error=type(error).__name__):
                self.window.reset_mock()
                self.show_error_dialog.reset_mock()
                self.generator.error = error
                self.generator.start_and_manage_image_generation()
                self.window.set_image_selector_visible.assert_called_with(False)
                self.window.set_is_loading.assert_called_with(False)
                self.show_error_dialog.assert_called_once()
                self.assertIs(self.show_error_dialog.call_args.args[2], error)
                self.assertEqual(self.generator._generating, False)  # pylint: disable=protected-access
                self.window.load_sample_preview.assert_not_called()

    def test_inpaint_passes_mask_and_restores_unmasked_pixels(self) -> None:
        """In inpainting mode `generate` gets the mask, and the original image is restored outside it."""
        Cache().set(Cache.EDIT_MODE, EDIT_MODE_INPAINT)
        self.generator.results = self._generated_images()
        self.generator.start_and_manage_image_generation()
        _, mask = self.generator.generate_calls[0]
        self.assertIsNotNone(mask)
        assert mask is not None
        self.assertEqual(mask.size(), GENERATION_AREA.size())
        preview = self._loaded_previews()[0]
        self.assertEqual(preview.pixelColor(2, 2), SOURCE_COLOR)
        center = SELECTION_BOUNDS.center() - GENERATION_AREA.topLeft()
        self.assertEqual(preview.pixelColor(center), GENERATED_COLOR)

    def test_inpaint_previews_and_selector_use_paste_mask(self) -> None:
        """Previews blend into the source through `get_paste_mask`, and the selector gets the same mask to apply."""
        Cache().set(Cache.EDIT_MODE, EDIT_MODE_INPAINT)
        paste_mask = _solid(GENERATION_AREA.size(), QColor(0, 0, 0, 0))
        self.generator.get_paste_mask = MagicMock(return_value=paste_mask)  # type: ignore
        self.generator.results = self._generated_images()
        self.generator.start_and_manage_image_generation()
        self.window.show_generated_options.assert_called_once_with(paste_mask)
        center = SELECTION_BOUNDS.center() - GENERATION_AREA.topLeft()
        # An empty paste mask keeps every source pixel, even inside the selection:
        self.assertEqual(self._loaded_previews()[0].pixelColor(center), SOURCE_COLOR)

    def test_status_update_sets_seeds_and_progress(self) -> None:
        """Seed, subseed and progress entries update the cache and the loading message."""
        self.generator.status_updates = [{'seed': '1234', 'subseed': '56', 'progress': 'step 3'}]
        self.generator.start_and_manage_image_generation()
        self.assertEqual(Cache().get(Cache.LAST_SEED), '1234')
        self.assertEqual(Cache().get(Cache.WEBUI_LAST_SUBSEED), '56')
        self.window.set_loading_message.assert_called_once_with('step 3')

    def test_status_update_ignores_missing_keys(self) -> None:
        """An update without progress leaves the loading message alone."""
        self.generator._apply_status_update({'seed': '7'})  # pylint: disable=protected-access
        self.assertEqual(Cache().get(Cache.LAST_SEED), '7')
        self.window.set_loading_message.assert_not_called()

    def test_cache_generated_image_keeps_order_and_replaces(self) -> None:
        """Images are stored at their index, padding skipped slots with null images, and replaced on repeat."""
        generator = TestGenerator(self.window, self.image_stack)
        first, second, replacement = (_solid(QSize(4, 4), QColor(color))
                                      for color in (Qt.GlobalColor.red, Qt.GlobalColor.green, Qt.GlobalColor.blue))
        with mock.patch('src.controller.image_generation.image_generator.QTimer.singleShot') as single_shot:
            generator._cache_generated_image(first, 0)  # pylint: disable=protected-access
            generator._cache_generated_image(second, 2)  # pylint: disable=protected-access
            stored = generator._generated_images  # pylint: disable=protected-access
            self.assertEqual(len(stored), 3)
            self.assertTrue(stored[1].isNull())
            generator._cache_generated_image(replacement, 0)  # pylint: disable=protected-access
            self.assertEqual(len(stored), 3)
            self.assertEqual(stored[0].pixelColor(0, 0), QColor(Qt.GlobalColor.blue))
            self.assertEqual(single_shot.call_count, 3)

    def test_load_generated_image_skips_null(self) -> None:
        """Only non-null cached images are sent to the window's sample preview."""
        generator = TestGenerator(self.window, self.image_stack)
        generator._generated_images = [QImage(), _solid(QSize(4, 4), QColor(Qt.GlobalColor.red))]  # pylint: disable=protected-access
        generator._load_generated_image_for_selection(0)  # pylint: disable=protected-access
        self.window.load_sample_preview.assert_not_called()
        generator._load_generated_image_for_selection(1)  # pylint: disable=protected-access
        self.window.load_sample_preview.assert_called_once()

    def test_default_upscale_resizes_all_layers(self) -> None:
        """The base class upscales by scaling every layer, and reports that it did."""
        new_size = QSize(256, 256)
        self.assertTrue(self.generator.upscale(new_size))
        self.assertEqual(self.image_stack.size, new_size)
