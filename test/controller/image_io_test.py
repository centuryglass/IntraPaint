"""Tests for ImageIO: opening and saving image files, animations and the open file's metadata."""
import base64
import json
import os
import sys
import tempfile
from typing import Optional
from unittest.mock import patch

from PIL import Image
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QWidget

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller.image_io import ImageIO
from src.ui.modal.save_loss_modal import SAVE_ANYWAY, SAVE_ORA, CANCEL
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.util.main_thread import is_main_thread
from src.util.visual.image_format_utils import IMAGE_FORMATS_SUPPORTING_METADATA, IMAGE_READ_FORMATS, \
    IMAGE_WRITE_FORMATS, AnimationSaveOptions, count_image_frames, load_image_frames
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

LAYER_IMAGE = 'test/resources/test_images/layer_move_test.ora'


class ImageIOTestCase(IntraPaintTestCase):
    """Builds an ImageIO over a bare window and image stack, with a three-frame GIF to open."""

    COLORS = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]

    def setUp(self) -> None:
        super().setUp()
        size = QSize(64, 64)
        self.window = QWidget()
        self.image_stack = ImageStack(size, size, size, size)
        self.image_io = ImageIO(self.window, self.image_stack, lambda: None)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.gif_path = os.path.join(self.temp_dir.name, 'anim.gif')
        frames = [Image.new('RGBA', (16, 16), color) for color in self.COLORS]
        frames[0].save(self.gif_path, save_all=True, append_images=frames[1:], duration=[100, 200, 50], loop=0)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()
        super().tearDown()

    def _layer_names_bottom_up(self) -> list[str]:
        return [layer.name for layer in sorted(self.image_stack.top_level_layers, key=lambda layer: layer.z_value)]


class TestImageIO(ImageIOTestCase):
    """Tests saving and loading across formats, and the background write."""

    def test_image_save_and_load(self):
        AppConfig()._reset()
        AppConfig().set(AppConfig.WARN_BEFORE_RGB_SAVE, False)
        AppConfig().set(AppConfig.WARN_BEFORE_LAYERLESS_SAVE, False)
        AppConfig().set(AppConfig.WARN_BEFORE_SAVE_WITHOUT_METADATA, False)
        AppConfig().set(AppConfig.WARN_BEFORE_WRITE_ONLY_SAVE, False)
        AppConfig().set(AppConfig.WARN_BEFORE_COLOR_LOSS, False)
        AppConfig().set(AppConfig.WARN_BEFORE_FIXED_SIZE_SAVE, False)
        self.image_io.load(LAYER_IMAGE)
        self.assertTrue(self.image_stack.has_image)


        sorted_formats = [*IMAGE_WRITE_FORMATS]
        sorted_formats.sort()
        with tempfile.TemporaryDirectory() as save_dir:
            for file_format in sorted_formats:
                self.image_io.load(LAYER_IMAGE)
                save_path = os.path.join(save_dir, f'save_test_{file_format}.{file_format.lower()}')
                test_prompt_str = f'{file_format} R/W test'
                Cache().set(Cache.PROMPT, test_prompt_str)
                self.image_io.update_metadata(show_messagebox=False)
                self.image_io.save_as(save_path)
                self.image_io.wait_for_pending_save()
                self.assertTrue(os.path.isfile(save_path), f'{file_format} save test failed')
                Cache().set(Cache.PROMPT, '')
                if file_format in IMAGE_READ_FORMATS:
                    self.image_io.load(save_path)
                    prompt = Cache().get(Cache.PROMPT)
                    expected_metadata = file_format in IMAGE_FORMATS_SUPPORTING_METADATA
                    if prompt == test_prompt_str:
                        self.assertTrue(expected_metadata,
                                        f'Metadata found but not expected for format {file_format}')
                    else:
                        self.assertFalse(expected_metadata,
                                         f'Metadata expected but not found for format {file_format}')

    def test_save_write_error_reaches_error_dialog_on_main_thread(self):
        """A failed background write shows the error dialog from the GUI thread and leaves the last path alone."""
        self.image_io.load(LAYER_IMAGE)
        self.image_io.update_metadata(show_messagebox=False)
        Cache().set(Cache.LAST_FILE_PATH, '')
        dialog_threads = []
        with tempfile.TemporaryDirectory() as save_dir, \
                patch('src.controller.image_io.request_save_loss_choice', return_value=SAVE_ANYWAY), \
                patch('src.controller.image_io.show_error_dialog',
                      side_effect=lambda *_: dialog_threads.append(is_main_thread())) as error_dialog:
            for extension in ('png', 'ora'):
                self.image_io.save_as(os.path.join(save_dir, 'missing', f'bad.{extension}'))
                self.image_io.wait_for_pending_save()
        self.assertEqual(2, error_dialog.call_count)
        self.assertEqual([True, True], dialog_threads)
        self.assertEqual('', Cache().get(Cache.LAST_FILE_PATH))

    def test_save_ora_in_background_sets_last_path(self):
        """A finished background .ora save records its path once the GUI thread handles the result."""
        self.image_io.load(LAYER_IMAGE)
        self.image_io.update_metadata(show_messagebox=False)
        with tempfile.TemporaryDirectory() as save_dir:
            save_path = os.path.join(save_dir, 'saved.ora')
            self.image_io.save_as(save_path)
            self.image_io.wait_for_pending_save()
            self.assertTrue(os.path.isfile(save_path))
            self.assertEqual(save_path, Cache().get(Cache.LAST_FILE_PATH))

    def test_metadata_json_handles_binary_metadata(self):
        """Binary metadata values such as an ICC profile serialize instead of raising."""
        self.image_io.metadata = {'icc_profile': b'\x00\x00\x01\xe0mntrRGB', 'text': b'plain', 'dpi': (96.0, 96.0)}
        loaded = json.loads(self.image_io.metadata_json())
        self.assertEqual(base64.b64encode(b'\x00\x00\x01\xe0mntrRGB').decode(), loaded['icc_profile'])
        self.assertEqual('plain', loaded['text'])


class TestSaveLossWarning(ImageIOTestCase):
    """Tests the dialog shown before a save that loses data."""

    def setUp(self) -> None:
        super().setUp()
        AppConfig()._reset()
        self.image_io.load(LAYER_IMAGE)
        Cache().set(Cache.LAST_FILE_PATH, '')

    def _save_png(self, choice: str) -> tuple[str, list]:
        """Saves to a .png with the dialog answering `choice`, returning the path and the dialog's loss lists."""
        calls: list = []

        def _answer(_parent, losses, offer_ora):
            calls.append((losses, offer_ora))
            return choice

        path = os.path.join(self.temp_dir.name, 'out.png')
        with patch('src.controller.image_io.request_save_loss_choice', side_effect=_answer):
            self.image_io.save_as(path)
            self.image_io.wait_for_pending_save()
        return path, calls

    def test_cancel_writes_nothing(self) -> None:
        """Canceling the dialog writes no file and leaves the last saved path alone."""
        path, calls = self._save_png(CANCEL)
        self.assertEqual(1, len(calls))
        self.assertFalse(os.path.exists(path))
        self.assertEqual('', Cache().get(Cache.LAST_FILE_PATH))

    def test_save_anyway_flattens(self) -> None:
        """Save anyway writes the flat file, after the dialog listed the layers loss."""
        path, calls = self._save_png(SAVE_ANYWAY)
        self.assertTrue(os.path.isfile(path))
        losses, offer_ora = calls[0]
        self.assertTrue(offer_ora)
        self.assertIn(AppConfig.WARN_BEFORE_LAYERLESS_SAVE, [loss.config_key for loss in losses])
        self.assertEqual(path, Cache().get(Cache.LAST_FILE_PATH))

    def test_save_as_ora_writes_ora(self) -> None:
        """Save as .ora writes an .ora beside the chosen path, and no flat file."""
        path, _ = self._save_png(SAVE_ORA)
        self.assertFalse(os.path.exists(path))
        ora_path = os.path.join(self.temp_dir.name, 'out.ora')
        self.assertTrue(os.path.isfile(ora_path))
        self.assertEqual(ora_path, Cache().get(Cache.LAST_FILE_PATH))

    def test_disabled_warning_is_not_listed(self) -> None:
        """A loss whose warning is disabled is left out of the dialog's list."""
        AppConfig().set(AppConfig.WARN_BEFORE_LAYERLESS_SAVE, False)
        _, calls = self._save_png(SAVE_ANYWAY)
        keys = [loss.config_key for loss in calls[0][0]]
        self.assertNotIn(AppConfig.WARN_BEFORE_LAYERLESS_SAVE, keys)

    def test_ora_save_has_no_dialog(self) -> None:
        """.ora saves lose nothing, so they never ask."""
        with patch('src.controller.image_io.request_save_loss_choice') as dialog:
            self.image_io.save_as(os.path.join(self.temp_dir.name, 'out.ora'))
            self.image_io.wait_for_pending_save()
        dialog.assert_not_called()


class TestOpenAnimation(ImageIOTestCase):
    """Tests opening animated images as one layer per frame."""

    def test_open_animation(self) -> None:
        """Opening an animated GIF loads one layer per frame and keeps the loop count in the metadata."""
        self.image_io.load(self.gif_path)
        self.assertEqual(self._layer_names_bottom_up(), ['Frame 1 (100ms)', 'Frame 2 (200ms)', 'Frame 3 (50ms)'])
        self.assertEqual(self.image_stack.size, QSize(16, 16))
        assert self.image_io.metadata is not None
        self.assertEqual(self.image_io.metadata.get('loop'), 0)

    @patch('src.controller.image_io.request_confirmation', return_value=False)
    @patch('src.controller.image_io.LARGE_ANIMATION_BYTES', 16)
    def test_open_large_animation_first_frame_only(self, mock_confirm) -> None:
        """Declining to open every frame of a large animation opens only its first frame."""
        self.image_io.load(self.gif_path)
        mock_confirm.assert_called_once()
        self.assertEqual(len(self.image_stack.top_level_layers), 1)
        first_frame = self.image_stack.top_level_layers[0]
        assert isinstance(first_frame, ImageLayer)
        self.assertEqual(first_frame.image.pixelColor(8, 8), QColor(255, 0, 0))

    @patch('src.controller.image_io.open_image_layers')
    def test_open_animation_as_layers(self, mock_open_layers) -> None:
        """Opening an animated GIF as layers adds one layer per frame, named after the file."""
        self.image_stack.load_image(QImage(QSize(16, 16), QImage.Format.Format_ARGB32_Premultiplied))
        mock_open_layers.return_value = ([self.gif_path], 'filter')
        self.image_io.load_layers()
        self.assertEqual(self._layer_names_bottom_up()[1:],
                         ['anim.gif: Frame 1 (100ms)', 'anim.gif: Frame 2 (200ms)', 'anim.gif: Frame 3 (50ms)'])


class TestSaveAnimation(ImageIOTestCase):
    """Tests saving one layer per frame as an animated image."""

    SAVE_MODAL = 'src.controller.image_io.AnimationSaveModal.show_animation_save_modal'

    def setUp(self) -> None:
        super().setUp()
        # Decline the metadata prompt and hide the data loss warnings, which would block offscreen:
        for target, return_value in (('request_confirmation', False), ('show_warning_dialog', None)):
            patcher = patch(f'src.controller.image_io.{target}', return_value=return_value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _saved_frame_durations(self, file_path: str) -> list[Optional[int]]:
        return [frame.duration_ms for frame in load_image_frames(file_path)]

    def test_save_animation_round_trip(self) -> None:
        """Save As with the modal's animation options writes every layer as a frame, and reopening restores them."""
        self.image_io.load(self.gif_path)
        for extension in ('gif', 'webp', 'apng'):
            with self.subTest(extension=extension), patch(
                    self.SAVE_MODAL, return_value=(True, AnimationSaveOptions(75, 0))) as mock_modal:
                path = os.path.join(self.temp_dir.name, f'saved.{extension}')
                with patch('src.controller.image_io.open_image_file', return_value=path):
                    self.image_io.save_as()
                    self.image_io.wait_for_pending_save()
                mock_modal.assert_called_once()
                self.assertEqual(self._saved_frame_durations(path), [100, 200, 50])
                self.image_io.load(path)
                self.assertEqual(self._layer_names_bottom_up(),
                                 ['Frame 1 (100ms)', 'Frame 2 (200ms)', 'Frame 3 (50ms)'])

    def test_save_flattened(self) -> None:
        """Choosing a flattened save in the modal writes a single frame."""
        self.image_io.load(self.gif_path)
        path = os.path.join(self.temp_dir.name, 'flat.webp')
        with patch(self.SAVE_MODAL, return_value=(True, None)), \
                patch('src.controller.image_io.request_save_loss_choice', return_value=SAVE_ANYWAY), \
                patch('src.controller.image_io.open_image_file', return_value=path):
            self.image_io.save_as()
            self.image_io.wait_for_pending_save()
        self.assertEqual(count_image_frames(path), 1)

    def test_cancel_saves_nothing(self) -> None:
        """Canceling the animation modal writes no file."""
        self.image_io.load(self.gif_path)
        path = os.path.join(self.temp_dir.name, 'canceled.gif')
        with patch(self.SAVE_MODAL, return_value=(False, None)), \
                patch('src.controller.image_io.open_image_file', return_value=path):
            self.image_io.save_as()
        self.assertFalse(os.path.exists(path))

    def test_plain_save_reuses_options(self) -> None:
        """Saving to a known path doesn't show the modal, and uses the options remembered from the opened file."""
        self.image_io.load(self.gif_path)
        path = os.path.join(self.temp_dir.name, 'plain.gif')
        with patch(self.SAVE_MODAL) as mock_modal:
            self.image_io.save_as(path)
            self.image_io.wait_for_pending_save()
        mock_modal.assert_not_called()
        self.assertEqual(self._saved_frame_durations(path), [100, 200, 50])
        with Image.open(path) as saved:
            self.assertEqual(saved.info.get('loop'), 0)
