"""Tests the standalone metadata window's Save, Save as and close prompts, and the editor window's "Save to file"."""
import os
import sys
import tempfile
from typing import Callable
from unittest.mock import patch, MagicMock

import numpy as np
from PIL import Image, ImageSequence, PngImagePlugin
from PySide6.QtWidgets import QApplication

from src.image.metadata_file import read_file_metadata
from src.util.visual.image_format_utils import IMAGE_WRITE_FORMATS
from src.ui.modal.modal_utils import UNSAVED_CANCEL, UNSAVED_DISCARD, UNSAVED_SAVE
from src.ui.window.metadata_window import MetadataWindow, EditorFileHooks
from src.ui.window.standalone_metadata_window import StandaloneMetadataWindow
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

_WINDOW_MODULE = 'src.ui.window.standalone_metadata_window'
_BASE_MODULE = 'src.ui.window.metadata_window'
PARAMETERS = 'a cat\nSteps: 20, Sampler: Euler a, CFG scale: 7'


def _noise() -> Image.Image:
    return Image.fromarray(np.random.default_rng(0).integers(0, 256, (8, 8, 3), dtype=np.uint8), 'RGB')


def _returns(value: object) -> Callable[..., object]:
    """Returns a stand-in for a dialog function that returns `value`.

    A plain function, since a mock would keep the window in its recorded calls, inside the mock's own reference cycles.
    """
    return lambda *_args, **_kwargs: value


def _fails(*_args, **_kwargs) -> None:
    raise AssertionError('Unexpected dialog')


def _pixels(path: str) -> list[bytes]:
    with Image.open(path) as image:
        return [frame.convert('RGBA').tobytes() for frame in ImageSequence.Iterator(image)]


class _FileTestCase(IntraPaintTestCase):
    """Creates a PNG with generation parameters in a temporary directory."""

    def setUp(self) -> None:
        super().setUp()
        self._temp_dir = tempfile.TemporaryDirectory()
        self.dir = self._temp_dir.name
        self.path = os.path.join(self.dir, 'image.png')
        info = PngImagePlugin.PngInfo()
        info.add_itxt('parameters', PARAMETERS)
        _noise().save(self.path, pnginfo=info)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()
        super().tearDown()


class StandaloneMetadataWindowTest(_FileTestCase):
    """Tests saving edits into the file, saving copies, and the prompts around them."""

    def setUp(self) -> None:
        super().setUp()
        self.window = StandaloneMetadataWindow(self.path)

    def test_save_writes_the_file(self) -> None:
        """Save writes the edits into the file and keeps its pixels. The window then shows the saved metadata."""
        pixels = _pixels(self.path)
        self.window._prompt_box.setValue('a dog')
        self.assertTrue(self.window.is_modified)
        self.assertEqual('Save', self.window._footer.confirm_button.text())
        self.window._footer.confirm_button.click()
        self.assertFalse(self.window.is_modified)
        self.assertEqual(PARAMETERS.replace('a cat', 'a dog'), read_file_metadata(self.path).parameters)
        self.assertEqual(pixels, _pixels(self.path))
        self.assertIn('image.png', self.window.windowTitle())

    def test_editor_buttons_hidden(self) -> None:
        self.assertTrue(self.window._apply_all_button.isHidden())
        self.assertTrue(self.window._update_all_button.isHidden())

    def test_save_as_switches_to_the_copy(self) -> None:
        """Save as writes a copy in the chosen format, leaves the original unchanged, and then edits the copy."""
        copy_path = os.path.join(self.dir, 'copy.webp')
        self.window._prompt_box.setValue('a dog')
        with patch(f'{_WINDOW_MODULE}.open_image_file', new=_returns(copy_path)):
            self.assertTrue(self.window.save_as())
        self.assertEqual(PARAMETERS, read_file_metadata(self.path).parameters)
        self.assertEqual(PARAMETERS.replace('a cat', 'a dog'), read_file_metadata(copy_path).parameters)
        self.assertEqual(copy_path, self.window.file_path)
        self.assertIn('copy.webp', self.window.windowTitle())
        self.assertFalse(self.window.is_modified)

    def test_save_as_offers_only_metadata_formats(self) -> None:
        """Save as lists only formats `write_file_metadata` can write."""
        offered: list[object] = []

        def _record(_parent: object, _mode: str, _suggested: str, formats: object = None) -> None:
            offered.append(formats)

        with patch(f'{_WINDOW_MODULE}.open_image_file', new=_record):
            self.assertFalse(self.window.save_as())
        self.assertEqual(1, len(offered))
        self.assertEqual({'ORA', 'PNG', 'APNG', 'JPG', 'JPEG', 'JPE', 'WEBP', 'GIF', 'TIF', 'TIFF', 'JP2', 'JPX', 'J2C',
                          'JPC'} & IMAGE_WRITE_FORMATS, set(offered[0]))

    def test_save_as_cancelled(self) -> None:
        with patch(f'{_WINDOW_MODULE}.open_image_file', new=_returns(None)):
            self.assertFalse(self.window.save_as())
        self.assertEqual(self.path, self.window.file_path)

    def test_unsupported_format_offers_a_png_copy(self) -> None:
        """A format that holds no metadata offers a PNG copy, and is left unchanged."""
        bmp_path = os.path.join(self.dir, 'image.bmp')
        _noise().save(bmp_path)
        with open(bmp_path, 'rb') as file:
            original = file.read()
        window = StandaloneMetadataWindow(bmp_path)
        window._metadata.set_parameters(PARAMETERS)
        window._edited()
        png_path = os.path.join(self.dir, 'converted.png')
        suggested_paths: list[str] = []

        def _choose_file(_parent: object, _mode: str, suggested_path: str, _formats: object = None) -> str:
            suggested_paths.append(suggested_path)
            return png_path

        with patch(f'{_WINDOW_MODULE}.request_confirmation', new=_returns(True)), \
                patch(f'{_WINDOW_MODULE}.open_image_file', new=_choose_file):
            self.assertTrue(window.save())
        self.assertEqual([os.path.join(self.dir, 'image.png')], suggested_paths)
        self.assertEqual(PARAMETERS, read_file_metadata(png_path).parameters)
        with open(bmp_path, 'rb') as file:
            self.assertEqual(original, file.read())

    def test_lossy_format_asks_first(self) -> None:
        """A JPEG-compressed TIFF is only written after the user picks the re-encode."""
        tiff_path = os.path.join(self.dir, 'lossy.tiff')
        _noise().save(tiff_path, compression='jpeg')
        window = StandaloneMetadataWindow(tiff_path)
        window._metadata.set_parameters(PARAMETERS)
        window._edited()
        with patch(f'{_BASE_MODULE}.request_choice', new=_returns(None)):
            self.assertFalse(window.save())
        self.assertIsNone(read_file_metadata(tiff_path).parameters)
        with patch(f'{_BASE_MODULE}.request_choice', new=_returns(0)):
            self.assertTrue(window.save())
        self.assertEqual(PARAMETERS, read_file_metadata(tiff_path).parameters)

    def test_close_asks_about_unsaved_edits(self) -> None:
        """Closing with unsaved edits asks first: Cancel keeps the window open, Save writes the file, Discard drops the
        edits."""
        self.window.show()
        self.window._prompt_box.setValue('a dog')
        with patch(f'{_WINDOW_MODULE}.request_unsaved_changes_choice', new=_returns(UNSAVED_CANCEL)):
            self.window.reject()
        self.assertTrue(self.window.isVisible())
        self.assertTrue(self.window.is_modified)
        with patch(f'{_WINDOW_MODULE}.request_unsaved_changes_choice', new=_returns(UNSAVED_SAVE)):
            self.window.close()
        self.assertFalse(self.window.isVisible())
        self.assertEqual(PARAMETERS.replace('a cat', 'a dog'), read_file_metadata(self.path).parameters)
        self.window.show()
        self.window._prompt_box.setValue('a bird')
        with patch(f'{_WINDOW_MODULE}.request_unsaved_changes_choice', new=_returns(UNSAVED_DISCARD)):
            self.window.close()
        self.assertFalse(self.window.isVisible())
        self.assertFalse(self.window.is_modified)
        self.assertEqual(PARAMETERS.replace('a cat', 'a dog'), read_file_metadata(self.path).parameters)

    def test_close_without_edits_does_not_ask(self) -> None:
        self.window.show()
        with patch(f'{_WINDOW_MODULE}.request_unsaved_changes_choice', new=_fails):
            self.window.reject()
        self.assertFalse(self.window.isVisible())


class SaveToFileTest(_FileTestCase):
    """Tests the editor window's "Save to file" button."""

    def setUp(self) -> None:
        super().setUp()
        self.file_path = self.path
        self.unsaved_edits = False
        self.wait_for_save = MagicMock()
        self.window = MetadataWindow(read_file_metadata(self.path), lambda: self.file_path,
                                     file_hooks=EditorFileHooks(lambda: self.unsaved_edits, self.wait_for_save))
        self.applied = []
        self.window.metadata_applied.connect(self.applied.append)

    def test_writes_and_applies(self) -> None:
        """Save to file waits for image saves, writes the file, and applies the edits."""
        assert self.window._save_to_file_button is not None
        self.assertTrue(self.window._save_to_file_button.isEnabled())
        self.window._prompt_box.setValue('a dog')
        self.window._save_to_file_button.click()
        self.wait_for_save.assert_called_once()
        self.assertEqual(PARAMETERS.replace('a cat', 'a dog'), read_file_metadata(self.path).parameters)
        self.assertEqual(1, len(self.applied))
        self.assertFalse(self.window.is_modified)
        self.assertEqual('Saved the metadata to "image.png".', self.window._status_label.text())

    def test_says_when_image_edits_are_unsaved(self) -> None:
        self.unsaved_edits = True
        self.window.save_to_file()
        self.assertIn('unsaved edits to the image', self.window._status_label.text())

    def test_disabled_without_a_writable_file(self) -> None:
        """Save to file is disabled for an image that was never saved, and for a format it can't write."""
        assert self.window._save_to_file_button is not None
        self.file_path = ''
        self.window.refresh()
        self.assertFalse(self.window._save_to_file_button.isEnabled())
        self.file_path = os.path.join(self.dir, 'image.bmp')
        _noise().save(self.file_path)
        self.window.refresh()
        self.assertFalse(self.window._save_to_file_button.isEnabled())
        self.assertIn('BMP', self.window._save_to_file_button.toolTip())

    def test_failure_is_shown(self) -> None:
        """A failed write shows an error and applies nothing."""
        with open(self.path, 'wb') as file:
            file.write(b'not a png')
        self.window._prompt_box.setValue('a dog')
        errors: list[object] = []
        with patch(f'{_BASE_MODULE}.show_error_dialog', new=lambda _parent, _title, error: errors.append(error)):
            self.assertFalse(self.window.save_to_file())
        self.assertEqual(1, len(errors))
        self.assertEqual([], self.applied)
        self.assertTrue(self.window.is_modified)

    def test_no_button_without_hooks(self) -> None:
        window = MetadataWindow(read_file_metadata(self.path), lambda: self.path)
        self.assertIsNone(window._save_to_file_button)
