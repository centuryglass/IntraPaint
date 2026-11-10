"""Tests for ImageIO: opening and saving image files, animations and the open file's metadata."""
import os
import sys
import tempfile
from typing import Optional
from unittest.mock import patch

from PIL import Image, PngImagePlugin, ExifTags
from PIL.ExifTags import IFD
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QWidget

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller.image_io import ImageIO, UNTITLED_FILE_NAME, RELOAD_CONFIRMATION_BUTTON
from src.image.image_metadata import ImageMetadata, encode_user_comment
from src.ui.modal.save_loss_modal import SAVE_ANYWAY, SAVE_ORA, CANCEL
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.ui.modal.modal_utils import UNSAVED_SAVE, UNSAVED_DISCARD, UNSAVED_CANCEL
from src.undo_stack import UndoStack
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
        AppConfig().set(AppConfig.WARN_BEFORE_METADATA_LOSS, False)
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

    def test_ora_save_keeps_metadata(self):
        """An .ora save and load keeps the text entries, EXIF, XMP, IPTC and DPI, and leaves out the ICC profile."""
        self.image_io.load(LAYER_IMAGE)
        exif = Image.Exif()
        exif[ExifTags.Base.Artist] = 'Someone'
        iptc = b'\x1c\x02\x19\x00\x03tag'
        self.image_io.metadata = ImageMetadata({'text': 'plain'}, exif, {
            'xmp': b'<x:xmpmeta xmlns:x="adobe:ns:meta/"/>', 'photoshop': {0x0404: iptc},
            'icc_profile': b'\x00\x00\x01\xe0mntrRGB', 'dpi': (96, 96)})
        with tempfile.TemporaryDirectory() as save_dir:
            save_path = os.path.join(save_dir, 'saved.ora')
            self.image_io.save_as(save_path)
            self.image_io.wait_for_pending_save()
            self.image_io.clear_metadata()
            self.image_io.load(save_path)
        metadata = self.image_io.metadata
        self.assertEqual({'text': 'plain'}, metadata.text)
        self.assertEqual('Someone', metadata.exif[ExifTags.Base.Artist])
        self.assertEqual(b'<x:xmpmeta xmlns:x="adobe:ns:meta/"/>', metadata.xmp_packet)
        self.assertEqual(iptc, metadata.iptc_data)
        self.assertEqual((96, 96), metadata.format_info['dpi'])
        self.assertFalse(metadata.has_icc_profile)

A1111_TEXT = ('a red fox\nNegative prompt: blurry\nSteps: 25, Sampler: Euler a, Schedule type: Karras, CFG scale: 6.5, '
              'Seed: 1234, Size: 512x768, Model hash: 6ce0161689, Model: v1-5-pruned, Denoising strength: 0.6, '
              'Lora hashes: "fox: 1a2b, style: 3c4d", Version: f2.0.1')


class TestGenerationMetadata(ImageIOTestCase):
    """Tests applying generation parameters on load, and keeping unknown fields through updates and saves."""

    def setUp(self) -> None:
        super().setUp()
        cache = Cache()
        cache.update_options(Cache.SAMPLING_METHOD, ['Euler a', 'DPM++ 2M'])
        self.addCleanup(cache.restore_default_options, Cache.SAMPLING_METHOD)

    def _write_png(self, parameters: str, name: str = 'generated.png') -> str:
        path = os.path.join(self.temp_dir.name, name)
        info = PngImagePlugin.PngInfo()
        info.add_text('parameters', parameters)
        Image.new('RGB', (16, 16)).save(path, pnginfo=info)
        return path

    def _assert_cache_values(self, prompt: str, negative: str, steps: int, sampler: str, cfg_scale: float,
                             seed: int) -> None:
        cache = Cache()
        self.assertEqual((prompt, negative, steps, sampler, cfg_scale, seed),
                         (cache.get(Cache.PROMPT), cache.get(Cache.NEGATIVE_PROMPT), cache.get(Cache.SAMPLING_STEPS),
                          cache.get(Cache.SAMPLING_METHOD), cache.get(Cache.GUIDANCE_SCALE), cache.get(Cache.SEED)))

    def test_load_applies_six_fields(self) -> None:
        """Loading applies the prompt, negative prompt, steps, sampler, CFG scale and seed, and nothing else."""
        cache = Cache()
        size_before = cache.get(Cache.GENERATION_SIZE)
        denoising_before = cache.get(Cache.DENOISING_STRENGTH)
        self.image_io.load(self._write_png(A1111_TEXT))
        self._assert_cache_values('a red fox', 'blurry', 25, 'Euler a', 6.5, 1234)
        self.assertEqual(size_before, cache.get(Cache.GENERATION_SIZE))
        self.assertEqual(denoising_before, cache.get(Cache.DENOISING_STRENGTH))

    def test_load_without_negative_prompt_clears_it(self) -> None:
        """Parameters with no negative prompt line set the negative prompt to empty text."""
        Cache().set(Cache.NEGATIVE_PROMPT, 'old')
        self.image_io.load(self._write_png('a fox\nSteps: 25, Sampler: Euler a, CFG scale: 7, Seed: 5, Size: 64x64'))
        self._assert_cache_values('a fox', '', 25, 'Euler a', 7.0, 5)

    def test_load_skips_unsupported_sampler(self) -> None:
        """A sampler the generator doesn't offer is left unapplied, and the other fields still apply."""
        Cache().set(Cache.SAMPLING_METHOD, 'DPM++ 2M')
        self.image_io.load(self._write_png(A1111_TEXT.replace('Euler a', 'Unknown sampler')))
        self._assert_cache_values('a red fox', 'blurry', 25, 'DPM++ 2M', 6.5, 1234)

    def test_load_ignores_text_that_is_not_generation_data(self) -> None:
        """A comment with no parameter line leaves the editor settings unchanged."""
        Cache().set(Cache.PROMPT, 'unchanged')
        self.image_io.load(self._write_png('Made with a camera'))
        self.assertEqual('unchanged', Cache().get(Cache.PROMPT))
        self.assertEqual('Made with a camera', self.image_io.metadata.parameters)

    def test_load_user_comment_parameters(self) -> None:
        """JPEG and WebP files keeping A1111 parameters in EXIF UserComment load them."""
        for extension in ('jpg', 'webp'):
            with self.subTest(extension=extension):
                Cache().set(Cache.PROMPT, '')
                path = os.path.join(self.temp_dir.name, f'a1111.{extension}')
                exif = Image.Exif()
                exif.get_ifd(IFD.Exif)[ExifTags.Base.UserComment] = encode_user_comment(A1111_TEXT)
                Image.new('RGB', (16, 16)).save(path, exif=exif)
                self.image_io.load(path)
                self._assert_cache_values('a red fox', 'blurry', 25, 'Euler a', 6.5, 1234)

    def test_update_keeps_unmapped_fields(self) -> None:
        """Update metadata replaces the editor's fields and keeps every other field as written."""
        self.image_io.load(self._write_png(A1111_TEXT))
        cache = Cache()
        cache.set(Cache.PROMPT, 'a blue fox')
        cache.set(Cache.SEED, 99)
        cache.set(Cache.GENERATION_SIZE, QSize(640, 640))
        self.image_io.update_metadata(show_messagebox=False)
        self.assertEqual(A1111_TEXT.replace('a red fox', 'a blue fox').replace('Seed: 1234', 'Seed: 99')
                         .replace('512x768', '640x640'), self.image_io.metadata.parameters)

    def test_update_unchanged_keeps_text(self) -> None:
        """Updating with the values the file already holds leaves the text unchanged, so a save doesn't ask to."""
        self.image_io.load(self._write_png(A1111_TEXT))
        Cache().set(Cache.GENERATION_SIZE, QSize(512, 768))
        self.assertTrue(self.image_io._metadata_is_latest())
        self.image_io.update_metadata(show_messagebox=False)
        self.assertEqual(A1111_TEXT, self.image_io.metadata.parameters)

    def test_update_without_metadata(self) -> None:
        """Update metadata on an image with no parameters writes the editor's fields."""
        cache = Cache()
        cache.set(Cache.PROMPT, 'p')
        cache.set(Cache.NEGATIVE_PROMPT, 'n')
        cache.set(Cache.SAMPLING_STEPS, 20)
        cache.set(Cache.SAMPLING_METHOD, 'Euler a')
        cache.set(Cache.GUIDANCE_SCALE, 7.0)
        cache.set(Cache.SEED, 3)
        cache.set(Cache.GENERATION_SIZE, QSize(512, 512))
        self.image_io.update_metadata(show_messagebox=False)
        self.assertEqual('p\nNegative prompt: n\nSteps: 20, Sampler: Euler a, CFG scale: 7.0, Seed: 3, Size: 512x512',
                         self.image_io.metadata.parameters)

    def test_load_then_save_keeps_unknown_fields(self) -> None:
        """Saving a loaded image, after Update metadata, keeps the A1111 fields IntraPaint doesn't use."""
        AppConfig().set(AppConfig.WARN_BEFORE_LAYERLESS_SAVE, False)
        for extension in ('png', 'jpg', 'webp', 'ora'):
            with self.subTest(extension=extension):
                self.image_io.load(self._write_png(A1111_TEXT))
                self.image_io.update_metadata(show_messagebox=False)
                save_path = os.path.join(self.temp_dir.name, f'saved.{extension}')
                self.image_io.save_as(save_path)
                self.image_io.wait_for_pending_save()
                self.image_io.load(save_path)
                params = self.image_io.metadata.a1111_parameters()
                assert params is not None
                self.assertEqual('fox: 1a2b, style: 3c4d', params.get('Lora hashes'))
                self.assertEqual('6ce0161689', params.get('Model hash'))
                self.assertEqual('f2.0.1', params.get('Version'))


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

    def test_lone_layer_group_warns_about_layers(self) -> None:
        """A root holding only a layer group still lists the layers loss on a flat save."""
        stack = self.image_stack
        group = stack.create_layer_group('group', None, stack.layer_stack.count)
        for layer in [child for child in stack.layer_stack.child_layers if child is not group]:
            stack.layer_stack.remove_layer(layer)
            group.insert_layer(layer, group.count)
        self.assertEqual(1, stack.layer_stack.count)
        _, calls = self._save_png(SAVE_ANYWAY)
        losses, _ = calls[0]
        self.assertIn(AppConfig.WARN_BEFORE_LAYERLESS_SAVE, [loss.config_key for loss in losses])

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


class TestMetadataLossWarning(ImageIOTestCase):
    """Tests the pre-save entry that lists EXIF, XMP, IPTC and comment data a format can't keep."""

    IPTC = b'\x1c\x02\x19\x00\x03tag' + b'\x1c\x02\x78\x00\x02hi'  # Keywords, Caption/Abstract

    def setUp(self) -> None:
        super().setUp()
        AppConfig()._reset()
        AppConfig().set(AppConfig.WARN_BEFORE_LAYERLESS_SAVE, False)
        self.image_io.load(LAYER_IMAGE)
        self.image_io.metadata = ImageMetadata({'comment': 'a note', 'Author': 'me'},
                                               format_info={'photoshop': {0x0404: self.IPTC}, 'xmp': b'<x/>'})

    def _losses_for(self, extension: str) -> list:
        calls: list = []

        def _answer(_parent, losses, offer_ora):
            calls.append(losses)
            return SAVE_ANYWAY

        with patch('src.controller.image_io.request_save_loss_choice', side_effect=_answer):
            self.image_io.save_as(os.path.join(self.temp_dir.name, f'out.{extension}'))
            self.image_io.wait_for_pending_save()
        self.assertEqual(1, len(calls))
        return [loss for loss in calls[0] if loss.config_key == AppConfig.WARN_BEFORE_METADATA_LOSS]

    def test_png_warns_about_iptc(self) -> None:
        """A PNG save names the IPTC datasets it drops, and nothing it keeps."""
        losses = self._losses_for('png')
        self.assertEqual(1, len(losses))
        self.assertIn('IPTC', losses[0].message)
        self.assertNotIn('XMP', losses[0].message)
        self.assertNotIn('comment', losses[0].message)
        self.assertIn('Keywords', losses[0].details)
        self.assertIn('Caption/Abstract', losses[0].details)

    def test_tiff_warns_about_comment_text_and_iptc(self) -> None:
        """A format that keeps only EXIF and XMP also drops comments and text entries."""
        losses = self._losses_for('tiff')
        self.assertEqual(1, len(losses))
        for dropped in ('comment', 'text entries', 'IPTC'):
            self.assertIn(dropped, losses[0].message)
        self.assertIn('Author', losses[0].details)

    def test_jpeg_keeps_iptc_without_warning(self) -> None:
        """JPEG keeps IPTC, XMP and the comment, and only drops the text entries."""
        losses = self._losses_for('jpg')
        self.assertEqual(1, len(losses))
        self.assertNotIn('IPTC', losses[0].message)
        self.assertIn('text entries', losses[0].message)

    def test_nothing_dropped_has_no_entry(self) -> None:
        """No entry is listed when the format keeps everything the image carries."""
        self.image_io.metadata = ImageMetadata(format_info={'photoshop': {0x0404: self.IPTC}})
        self.assertEqual([], self._losses_for('jpg'))

    def test_removed_metadata_is_not_reported(self) -> None:
        """Metadata removed before the save isn't listed as lost."""
        self.image_io.metadata.remove_all()
        self.assertEqual([], self._losses_for('png'))

    def test_disabled_key_has_no_entry(self) -> None:
        """The entry is left out once its warning is turned off."""
        AppConfig().set(AppConfig.WARN_BEFORE_METADATA_LOSS, False)
        self.assertEqual([], self._losses_for('png'))


class TestUnsavedChanges(ImageIOTestCase):
    """Tests which saves make the document clean, and the prompt before discarding unsaved changes."""

    CHOICE = 'src.controller.image_io.request_unsaved_changes_choice'

    def setUp(self) -> None:
        super().setUp()
        patcher = patch('src.controller.image_io.request_save_loss_choice', return_value=SAVE_ANYWAY)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _load_single_layer(self) -> None:
        self.image_stack.load_image(QImage(QSize(16, 16), QImage.Format.Format_ARGB32_Premultiplied))
        Cache().set(Cache.LAST_FILE_PATH, '')

    def _save(self, file_name: str) -> str:
        save_path = os.path.join(self.temp_dir.name, file_name)
        self.image_io.save_as(save_path)
        self.image_io.wait_for_pending_save()
        self.assertTrue(os.path.isfile(save_path))
        return save_path

    def test_load_is_clean_and_edit_is_modified(self) -> None:
        """Opening a file makes the document clean, and an edit makes it modified."""
        self.image_io.load(LAYER_IMAGE)
        self.assertTrue(UndoStack().is_clean())
        self.image_stack.create_layer('edit')
        self.assertFalse(UndoStack().is_clean())
        UndoStack().undo()
        self.assertTrue(UndoStack().is_clean())

    def test_ora_save_is_clean(self) -> None:
        """Saving layers to .ora makes the document clean."""
        self.image_io.load(LAYER_IMAGE)
        self.image_stack.create_layer('edit')
        self._save('saved.ora')
        self.assertTrue(UndoStack().is_clean())

    def test_flat_save_of_one_layer_is_clean(self) -> None:
        """A flat save that loses no layers makes the document clean."""
        self._load_single_layer()
        UndoStack().commit_action(lambda: None, lambda: None, 'test.edit')
        self.assertFalse(UndoStack().is_clean())
        self._save('saved.png')
        self.assertTrue(UndoStack().is_clean())

    def test_flat_save_of_layers_is_modified(self) -> None:
        """A flat save that flattens layers leaves no state clean, even the one it saved from."""
        self.image_io.load(LAYER_IMAGE)
        self.assertGreater(self.image_stack.layer_stack.count, 1)
        self._save('flat.png')
        self.assertFalse(UndoStack().is_clean())
        self.image_stack.create_layer('edit')
        UndoStack().undo()
        self.assertFalse(UndoStack().is_clean())

    def test_failed_save_keeps_modified(self) -> None:
        """A save whose write fails leaves the document modified."""
        self._load_single_layer()
        self.image_stack.create_layer('edit')
        with patch('src.controller.image_io.show_error_dialog'):
            self.image_io.save_as(os.path.join(self.temp_dir.name, 'missing', 'bad.png'))
            self.image_io.wait_for_pending_save()
        self.assertFalse(UndoStack().is_clean())

    def test_prompt_skipped_when_clean(self) -> None:
        """confirm_unsaved_changes proceeds without asking when nothing changed."""
        self.image_io.load(LAYER_IMAGE)
        with patch(self.CHOICE) as choice:
            self.assertTrue(self.image_io.confirm_unsaved_changes('Quit without saving'))
        choice.assert_not_called()

    def test_prompt_discard_and_cancel(self) -> None:
        """Discard lets the action proceed, Cancel stops it, and neither saves."""
        self.image_io.load(LAYER_IMAGE)
        self.image_stack.create_layer('edit')
        for choice_value, expected in ((UNSAVED_DISCARD, True), (UNSAVED_CANCEL, False)):
            with patch(self.CHOICE, return_value=choice_value) as choice, \
                    patch.object(self.image_io, 'save') as save:
                self.assertEqual(self.image_io.confirm_unsaved_changes('Quit without saving'), expected)
            choice.assert_called_once_with(self.window, 'layer_move_test.ora', 'Quit without saving')
            save.assert_not_called()
        self.assertFalse(UndoStack().is_clean())

    def test_prompt_save_proceeds_after_save(self) -> None:
        """Save writes the file, then lets the action proceed."""
        self._load_single_layer()
        self.image_stack.create_layer('edit')
        save_path = os.path.join(self.temp_dir.name, 'chosen.ora')
        with patch(self.CHOICE, return_value=UNSAVED_SAVE) as choice, \
                patch('src.controller.image_io.open_image_file', return_value=save_path):
            self.assertTrue(self.image_io.confirm_unsaved_changes('Quit without saving'))
        self.assertEqual(choice.call_args.args[1], UNTITLED_FILE_NAME)
        self.assertTrue(os.path.isfile(save_path))
        self.assertTrue(UndoStack().is_clean())

    def test_prompt_save_cancelled_or_failed_stops_action(self) -> None:
        """Cancelling the save dialog, or a failed write, stops the action."""
        self._load_single_layer()
        self.image_stack.create_layer('edit')
        bad_path = os.path.join(self.temp_dir.name, 'missing', 'bad.ora')
        for selected_path in (None, bad_path):
            with patch(self.CHOICE, return_value=UNSAVED_SAVE), \
                    patch('src.controller.image_io.open_image_file', return_value=selected_path), \
                    patch('src.controller.image_io.show_error_dialog'):
                self.assertFalse(self.image_io.confirm_unsaved_changes('Quit without saving'))
        self.assertFalse(UndoStack().is_clean())

    def test_reload_prompts_only_when_modified(self) -> None:
        """Reloading an unchanged file doesn't ask, and reloading an edited one does."""
        self.image_io.load(LAYER_IMAGE)
        layer_count = self.image_stack.layer_stack.count
        with patch(self.CHOICE, return_value=UNSAVED_CANCEL) as choice:
            self.image_io.reload()
            choice.assert_not_called()
            self.image_stack.create_layer('edit')
            self.image_io.reload()
            choice.assert_called_once_with(self.window, 'layer_move_test.ora', RELOAD_CONFIRMATION_BUTTON)
        self.assertEqual(self.image_stack.layer_stack.count, layer_count + 1)


class TestOpenAnimation(ImageIOTestCase):
    """Tests opening animated images as one layer per frame."""

    def test_open_animation(self) -> None:
        """Opening an animated GIF loads one layer per frame and keeps the loop count in the metadata."""
        self.image_io.load(self.gif_path)
        self.assertEqual(self._layer_names_bottom_up(), ['Frame 1 (100ms)', 'Frame 2 (200ms)', 'Frame 3 (50ms)'])
        self.assertEqual(self.image_stack.size, QSize(16, 16))
        self.assertEqual(self.image_io.metadata.format_info.get('loop'), 0)

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

    def test_animation_save_without_metadata_writes_no_exif(self) -> None:
        """A WebP animation saved from an image with no metadata reloads with no EXIF tags."""
        self.image_io.load(self.gif_path)
        path = os.path.join(self.temp_dir.name, 'plain.webp')
        with patch(self.SAVE_MODAL, return_value=(True, AnimationSaveOptions(75, 0))), \
                patch('src.controller.image_io.open_image_file', return_value=path):
            self.image_io.save_as()
            self.image_io.wait_for_pending_save()
        self.image_io.load(path)
        self.assertEqual([], self.image_io.metadata.exif_entries())

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
