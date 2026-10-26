"""Tests for GenerationSession: current and previous batch ownership, without a selection widget."""
import sys

import tempfile
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.controller.image_generation.generation_session import GenerationSession
from src.image.layers.image_stack import ImageStack
from src.controller.image_generation.apply_option import ApplyResult
from src.util.application_state import AppStateTracker, APP_STATE_EDITING, APP_STATE_SELECTION
from src.util.shared_constants import EDIT_MODE_TXT2IMG
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

IMAGE_SIZE = QSize(64, 64)
LOADING_TEXT = 'Loading'


def _solid(color: QColor) -> QImage:
    image = QImage(IMAGE_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color)
    return image


class GenerationSessionTest(IntraPaintTestCase):
    """Tests batch capture, archiving, and re-opening."""

    def setUp(self) -> None:
        super().setUp()
        Cache().set(Cache.GENERATION_SIZE, IMAGE_SIZE)
        Cache().set(Cache.EDIT_SIZE, IMAGE_SIZE)
        self.image_stack = ImageStack(IMAGE_SIZE, IMAGE_SIZE, QSize(8, 8), IMAGE_SIZE)
        self.image_stack.load_image(_solid(QColor(200, 10, 10)))
        self.session = GenerationSession(self.image_stack)
        self.availability: list[bool] = []
        self.session.previous_options_available.connect(self.availability.append)

    def _begin_with_results(self) -> None:
        batch = self.session.begin(LOADING_TEXT)
        batch.option_images.extend([batch.loading_image, batch.loading_image])
        self.session.add_image(_solid(QColor(0, 255, 0)), 0)

    def test_current_requires_begin(self) -> None:
        """Reading the current batch before any generation raises."""
        with self.assertRaises(RuntimeError):
            _ = self.session.current

    def test_begin_captures_original_content(self) -> None:
        """A new batch starts with the canvas content and accepts results."""
        self.image_stack.flush_render()
        batch = self.session.begin(LOADING_TEXT)
        self.assertEqual(batch.option_images, [self.image_stack.qimage_generation_area_content()])
        self.assertTrue(self.session.accepting_results)
        self.assertFalse(batch.has_results())

    def test_batch_without_results_is_not_archived(self) -> None:
        """Archiving a batch that only holds placeholders stores nothing."""
        self.session.begin(LOADING_TEXT)
        self.assertIsNone(self.session.archive_current())
        self.assertFalse(self.session.can_restore_previous())
        self.assertEqual(self.availability, [])

    def test_archive_drops_placeholders_once(self) -> None:
        """Archiving keeps arrived images, reports their indices, and ignores repeat calls."""
        self._begin_with_results()
        batch = self.session.current
        self.assertEqual(self.session.archive_current(), [0, 1])
        self.assertIs(self.session.previous, batch)
        self.assertEqual(len(batch.option_images), 2)
        self.assertIsNone(self.session.archive_current())
        self.assertEqual(self.availability, [True])

    def test_restore_refreshes_original_and_stops_accepting(self) -> None:
        """A restored batch shows the current canvas as option zero and takes no new results."""
        self._begin_with_results()
        self.session.archive_current()
        self.session.begin(LOADING_TEXT)
        self.image_stack.active_layer.image = _solid(QColor(1, 2, 3))
        self.image_stack.flush_render()
        batch = self.session.restore_previous()
        self.assertEqual(batch.option_images[0], self.image_stack.qimage_generation_area_content())
        self.assertFalse(self.session.accepting_results)
        self.assertFalse(self.session.add_image(_solid(QColor(9, 9, 9)), 0))

    def test_restore_without_batch_raises(self) -> None:
        """Restoring with nothing stored raises."""
        with self.assertRaises(RuntimeError):
            self.session.restore_previous()

    def test_new_document_drops_previous(self) -> None:
        """Loading another document discards the stored batch."""
        self._begin_with_results()
        self.session.archive_current()
        self.image_stack.load_image(_solid(QColor(5, 5, 5)))
        self.assertFalse(self.session.can_restore_previous())
        self.assertEqual(self.availability, [True, False])

    def test_choose_applies_to_active_layer_and_returns_to_editing(self) -> None:
        """Choosing a generated option writes it to the active layer and leaves the selection state."""
        Cache().set(Cache.EDIT_MODE, EDIT_MODE_TXT2IMG)  # inpainting would clip the option by the empty selection
        self._begin_with_results()
        AppStateTracker.set_app_state(APP_STATE_SELECTION)
        outcome = self.session.choose(1, 'Option 1')
        self.image_stack.flush_render()
        assert outcome is not None
        self.assertEqual(outcome.result, ApplyResult.APPLIED)
        self.assertEqual(AppStateTracker.app_state(), APP_STATE_EDITING)
        self.assertEqual(self.image_stack.qimage_generation_area_content().pixelColor(5, 5), QColor(0, 255, 0))

    def test_choose_original_applies_nothing(self) -> None:
        """Choosing option zero leaves the image alone and still returns to editing."""
        self._begin_with_results()
        AppStateTracker.set_app_state(APP_STATE_SELECTION)
        self.assertIsNone(self.session.choose(0, 'Original'))
        self.assertEqual(AppStateTracker.app_state(), APP_STATE_EDITING)

    def test_choose_reports_locked_layer_fallback(self) -> None:
        """A locked target layer sends the option to a new layer and the outcome says why."""
        self._begin_with_results()
        self.image_stack.active_layer.locked = True
        outcome = self.session.choose(1, 'Option 1')
        assert outcome is not None
        self.assertEqual(outcome.result, ApplyResult.BLOCKED_LOCKED)
        self.assertEqual(outcome.layer.name, 'Option 1')

    def test_send_to_new_layer(self) -> None:
        """The option lands on a new layer named for it."""
        self._begin_with_results()
        layer = self.session.send_to_new_layer(1, 'Option 1')
        self.assertEqual(layer.name, 'Option 1')
        self.assertIs(self.image_stack.active_layer, layer)

    def test_save_to_file_writes_option(self) -> None:
        """Saving passes the chosen option's image and the path on to the image writer."""
        Cache().set(Cache.EDIT_MODE, EDIT_MODE_TXT2IMG)
        self._begin_with_results()
        with patch('src.controller.image_generation.generation_session.save_image') as save:
            self.session.save_to_file(1, str(Path(tempfile.gettempdir()) / 'option.png'))
        self.assertEqual(save.call_args.args[0].pixelColor(5, 5), QColor(0, 255, 0))
