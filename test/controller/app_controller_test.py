import gc
import os
import sys
import tempfile
import weakref
from contextlib import contextmanager
from typing import Iterator
from unittest.mock import patch, MagicMock

from PIL import Image
from PySide6.QtCore import QEvent, QSize, QTimer
from PySide6.QtGui import QAction, QColor, QImage
from PySide6.QtWidgets import QApplication, QStyleFactory, QWidget

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.controller.app_controller import AppController
from src.controller.image_generation.test_generator import TestGenerator
from src.image.layers.image_layer import ImageLayer
from src.ui.modal.settings_modal import SettingsModal
from src.ui.window.main_window import MainWindow
from src.util.application_state import AppStateTracker, APP_STATE_EDITING, APP_STATE_LOADING
from src.util.arg_parser import build_arg_parser
from src.util.visual.image_format_utils import IMAGE_FORMATS_SUPPORTING_METADATA, IMAGE_READ_FORMATS, \
    IMAGE_WRITE_FORMATS
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

LAYER_IMAGE = 'test/resources/test_images/layer_move_test.ora'


class _GcStateRecorder(QWidget):
    """Records whether cyclic garbage collection was enabled each time the widget receives a style change."""

    def __init__(self) -> None:
        super().__init__()
        self.gc_enabled_states: list[bool] = []

    def event(self, event: QEvent) -> bool:
        """Records the garbage collector state on style changes."""
        if event.type() == QEvent.Type.StyleChange:
            self.gc_enabled_states.append(gc.isenabled())
        return super().event(event)


class _WidgetCycle:
    """Holds a Python-owned widget in a reference cycle, so only cyclic garbage collection can free it."""

    def __init__(self) -> None:
        self.widget = QWidget()
        self.cycle = self


@contextmanager
def _collection_frees_garbage() -> Iterator[None]:
    """Turns off gc.DEBUG_SAVEALL (see test/qt_cycles.py), so a collection in the block frees the cycles it finds."""
    debug_flags = gc.get_debug()
    gc.set_debug(debug_flags & ~gc.DEBUG_SAVEALL)
    try:
        yield
    finally:
        gc.set_debug(debug_flags)


def _unreachable_widget_cycle() -> weakref.ref:
    """Creates an unreachable _WidgetCycle and returns a weak reference to it."""
    return weakref.ref(_WidgetCycle())


class TestAppController(IntraPaintTestCase):

    def setUp(self):
        super().setUp()
        self.mock_screen = MagicMock()
        args = ['--window_size', '800x600', '--mode', 'mock']
        self.args = build_arg_parser(include_edit_params=False).parse_args(args)
        self.args.mode = 'mock'
        self.args.server_url = ''
        self.args.fast_ngrok_connection = False
        self.controller = AppController(self.args)

    def test_init(self):
        self.assertIsInstance(self.controller, AppController)
        self.assertIsInstance(self.controller._window, MainWindow)
        self.assertIsInstance(self.controller._settings_modal, SettingsModal)
        self.assertIsInstance(self.controller._generator, TestGenerator)
        self.assertIsNone(self.controller._layer_panel)
        self.assertIsNone(self.controller._metadata)

    @patch('src.controller.app_controller.SettingsModal')
    def test_init_settings(self, MockSettingsModal):
        settings_modal = MockSettingsModal.return_value
        self.controller.init_settings(settings_modal)
        settings_modal.load_from_config.assert_called()
        MockSettingsModal.reset_mock()  # Its recorded calls hold the custom control the controller added.

    @patch('src.controller.app_controller.SettingsModal')
    def test_refresh_settings(self, MockSettingsModal):
        settings_modal = MockSettingsModal.return_value
        self.controller.refresh_settings(settings_modal)
        self.assertTrue(settings_modal.update_settings.called)

    @patch('src.controller.app_controller.show_warning_dialog')
    def test_update_settings(self, mock_warning_dialog):
        AppConfig().set('max_undo', 10)
        KeyConfig().set('zoom_in', 'PgUp')

        # Define changed settings
        changed_settings = {
            'max_undo': 50,  # should be applied to app_config
            'zoom_in': 'Home',  # should be applied to key_config
            'key5': 'value5'  # should be ignored
        }
        self.assertNotEqual(changed_settings['max_undo'], AppConfig().get('max_undo'))
        self.assertNotEqual(changed_settings['zoom_in'], KeyConfig().get('zoom_in'))

        self.controller.update_settings(changed_settings)

        mock_warning_dialog.assert_called_once()  # The new undo limit applies after a restart.
        self.assertEqual(changed_settings['max_undo'], AppConfig().get('max_undo'))
        self.assertEqual(changed_settings['zoom_in'], KeyConfig().get('zoom_in'))
        KeyConfig().set('zoom_in', 'PgUp')

    @patch('src.ui.theme.qdarktheme')
    @patch('src.ui.theme.qt_material')
    def test_fix_styles_qdarktheme(self, MockQtMaterial, MockQDarkTheme):
        AppConfig()._reset()
        initial_theme = AppConfig().get('theme')
        initial_font_size = AppConfig().get('font_point_size')
        AppConfig().add_option('theme', 'qdarktheme_dark')
        AppConfig().set('theme', 'qdarktheme_dark')
        AppConfig().set('font_point_size', QApplication.instance().font().pointSize() + 10)
        self.assertNotEqual(AppConfig().get('font_point_size'), QApplication.instance().font().pointSize())
        try:
            self.controller = AppController(self.args)
            self.assertTrue(MockQDarkTheme.setup_theme.called)
            self.assertFalse(MockQtMaterial.apply_stylesheet.called)
            self.assertEqual(AppConfig().get('font_point_size'), QApplication.instance().font().pointSize())
        finally:
            # The controller applies config changes to the application, so this restores its theme and font.
            AppConfig().set('theme', initial_theme)
            AppConfig().set('font_point_size', initial_font_size)

    @patch('src.ui.theme.qdarktheme')
    @patch('src.ui.theme.qt_material')
    def test_fix_styles_qt_material(self, MockQtMaterial, MockQDarkTheme):
        AppConfig()._reset()
        initial_theme = AppConfig().get('theme')
        initial_font_size = AppConfig().get('font_point_size')
        AppConfig().add_option('theme', 'qt_material_dark')
        AppConfig().set('theme', 'qt_material_dark')
        AppConfig().set('font_point_size', QApplication.instance().font().pointSize() + 10)
        self.assertNotEqual(AppConfig().get('font_point_size'), QApplication.instance().font().pointSize())
        try:
            self.controller = AppController(self.args)
            self.assertFalse(MockQDarkTheme.setup_theme.called)
            self.assertTrue(MockQtMaterial.apply_stylesheet.called)
            self.assertEqual(AppConfig().get('font_point_size'), QApplication.instance().font().pointSize())
        finally:
            # The controller applies config changes to the application, so this restores its theme and font.
            AppConfig().set('theme', initial_theme)
            AppConfig().set('font_point_size', initial_font_size)

    def test_style_change_pauses_garbage_collection(self):
        """QApplication.setStyle runs after a collection, with collection paused (see gc_paused)."""
        initial_style = AppConfig().get(AppConfig.STYLE)
        new_style = next(key for key in QStyleFactory.keys() if key.lower() != initial_style.lower())
        recorder = _GcStateRecorder()
        garbage = _unreachable_widget_cycle()
        try:
            with _collection_frees_garbage():
                AppConfig().set(AppConfig.STYLE, new_style, add_missing_options=True)
        finally:
            AppConfig().set(AppConfig.STYLE, initial_style)
        self.assertIsNone(garbage())
        self.assertNotEqual(recorder.gc_enabled_states, [])
        self.assertNotIn(True, recorder.gc_enabled_states)
        self.assertTrue(gc.isenabled())

    @patch('src.ui.theme.qdarktheme')
    def test_theme_change_pauses_garbage_collection(self, mock_qdarktheme):
        """Theme stylesheets are applied after a collection, with collection paused (see gc_paused)."""
        mock_qdarktheme.setup_theme.side_effect = lambda *_args: app.setStyleSheet('QWidget { margin: 1px; }')
        initial_theme = AppConfig().get(AppConfig.THEME)
        recorder = _GcStateRecorder()
        garbage = _unreachable_widget_cycle()
        try:
            with _collection_frees_garbage():
                AppConfig().set(AppConfig.THEME, 'qdarktheme_dark', add_missing_options=True)
            gc_enabled_states = list(recorder.gc_enabled_states)
        finally:
            AppConfig().set(AppConfig.THEME, initial_theme)
        mock_qdarktheme.setup_theme.assert_called_once()
        self.assertIsNone(garbage())
        self.assertNotEqual(gc_enabled_states, [])
        self.assertNotIn(True, gc_enabled_states)
        self.assertTrue(gc.isenabled())

    # TODO: Fix issues with MenuBuilder mocking that are breaking this test case.
    def test_start_app(self):
        self.controller = AppController(self.args)
        timer = QTimer()
        timer.setInterval(1000)
        timer.setSingleShot(True)

        def _on_timeout():
            window = self.controller.menu_window
            self.assertIsInstance(window, MainWindow)
            self.assertTrue(window.isVisible())
            self.controller.quit(skip_confirmation=True)
        timer.timeout.connect(_on_timeout)
        timer.start()
        self.controller.start_app()
        self.assertFalse(self.controller.menu_window.isVisible())

    @patch('src.ui.window.main_window.QApplication.exit')
    @patch('src.controller.app_controller.request_confirmation', return_value=True)
    def test_quit_confirmed_asks_once(self, mock_confirm, mock_exit):
        self.controller.quit()
        mock_confirm.assert_called_once()
        mock_exit.assert_called_once()

    @patch('src.ui.window.main_window.QApplication.exit')
    @patch('src.controller.app_controller.request_confirmation', return_value=False)
    def test_quit_cancelled_keeps_window_open(self, mock_confirm, mock_exit):
        self.controller._window.show()
        self.controller.quit()
        mock_confirm.assert_called_once()
        mock_exit.assert_not_called()
        self.assertTrue(self.controller._window.isVisible())

    @patch('src.ui.window.main_window.QApplication.exit')
    @patch('src.controller.app_controller.request_confirmation', return_value=True)
    def test_quit_skip_confirmation_does_not_ask(self, mock_confirm, mock_exit):
        self.controller.quit(skip_confirmation=True)
        mock_confirm.assert_not_called()
        mock_exit.assert_called_once()

    @patch('src.ui.window.main_window.QApplication.exit')
    @patch('src.controller.app_controller.request_confirmation', return_value=True)
    def test_window_close_confirmed_asks_once(self, mock_confirm, mock_exit):
        self.controller._window.close()
        mock_confirm.assert_called_once()
        mock_exit.assert_called_once()

    @patch('src.ui.window.main_window.QApplication.exit')
    @patch('src.controller.app_controller.request_confirmation', return_value=False)
    def test_window_close_cancelled_keeps_window_open(self, mock_confirm, mock_exit):
        self.controller._window.show()
        self.assertFalse(self.controller._window.close())
        mock_confirm.assert_called_once()
        mock_exit.assert_not_called()
        self.assertTrue(self.controller._window.isVisible())

    def test_image_save_and_load(self):
        AppConfig()._reset()
        AppConfig().set(AppConfig.WARN_BEFORE_RGB_SAVE, False)
        AppConfig().set(AppConfig.WARN_BEFORE_LAYERLESS_SAVE, False)
        AppConfig().set(AppConfig.WARN_BEFORE_SAVE_WITHOUT_METADATA, False)
        AppConfig().set(AppConfig.WARN_BEFORE_WRITE_ONLY_SAVE, False)
        AppConfig().set(AppConfig.WARN_BEFORE_COLOR_LOSS, False)
        AppConfig().set(AppConfig.WARN_BEFORE_FIXED_SIZE_SAVE, False)
        self.controller.load_image(LAYER_IMAGE)
        self.assertTrue(self.controller._image_stack.has_image)


        sorted_formats = [*IMAGE_WRITE_FORMATS]
        sorted_formats.sort()
        with tempfile.TemporaryDirectory() as save_dir:
            for file_format in sorted_formats:
                self.controller.load_image(LAYER_IMAGE)
                save_path = os.path.join(save_dir, f'save_test_{file_format}.{file_format.lower()}')
                test_prompt_str = f'{file_format} R/W test'
                Cache().set(Cache.PROMPT, test_prompt_str)
                self.controller.update_metadata(show_messagebox=False)
                self.controller.save_image_as(save_path)
                self.assertTrue(os.path.isfile(save_path), f'{file_format} save test failed')
                Cache().set(Cache.PROMPT, '')
                if file_format in IMAGE_READ_FORMATS:
                    self.controller.load_image(save_path)
                    prompt = Cache().get(Cache.PROMPT)
                    expected_metadata = file_format in IMAGE_FORMATS_SUPPORTING_METADATA
                    if prompt == test_prompt_str:
                        self.assertTrue(expected_metadata,
                                        f'Metadata found but not expected for format {file_format}')
                    else:
                        self.assertFalse(expected_metadata,
                                         f'Metadata expected but not found for format {file_format}')


class TestOpenAnimation(IntraPaintTestCase):
    """Tests opening animated images as one layer per frame."""

    COLORS = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]

    def setUp(self) -> None:
        super().setUp()
        args = build_arg_parser(include_edit_params=False).parse_args(['--window_size', '800x600', '--mode', 'mock'])
        args.mode = 'mock'
        args.server_url = ''
        args.fast_ngrok_connection = False
        self.controller = AppController(args)
        self.image_stack = self.controller._image_stack
        self.temp_dir = tempfile.TemporaryDirectory()
        self.gif_path = os.path.join(self.temp_dir.name, 'anim.gif')
        frames = [Image.new('RGBA', (16, 16), color) for color in self.COLORS]
        frames[0].save(self.gif_path, save_all=True, append_images=frames[1:], duration=[100, 200, 50], loop=0)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()
        super().tearDown()

    def _layer_names_bottom_up(self) -> list[str]:
        return [layer.name for layer in sorted(self.image_stack.top_level_layers, key=lambda layer: layer.z_value)]

    def test_open_animation(self) -> None:
        """Opening an animated GIF loads one layer per frame and keeps the loop count in the metadata."""
        self.controller.load_image(self.gif_path)
        self.assertEqual(self._layer_names_bottom_up(), ['Frame 1 (100ms)', 'Frame 2 (200ms)', 'Frame 3 (50ms)'])
        self.assertEqual(self.image_stack.size, QSize(16, 16))
        assert self.controller._metadata is not None
        self.assertEqual(self.controller._metadata.get('loop'), 0)

    @patch('src.controller.app_controller.request_confirmation', return_value=False)
    @patch('src.controller.app_controller.LARGE_ANIMATION_BYTES', 16)
    def test_open_large_animation_first_frame_only(self, mock_confirm) -> None:
        """Declining to open every frame of a large animation opens only its first frame."""
        self.controller.load_image(self.gif_path)
        mock_confirm.assert_called_once()
        self.assertEqual(len(self.image_stack.top_level_layers), 1)
        first_frame = self.image_stack.top_level_layers[0]
        assert isinstance(first_frame, ImageLayer)
        self.assertEqual(first_frame.image.pixelColor(8, 8), QColor(255, 0, 0))

    @patch('src.controller.app_controller.open_image_layers')
    def test_open_animation_as_layers(self, mock_open_layers) -> None:
        """Opening an animated GIF as layers adds one layer per frame, named after the file."""
        self.image_stack.load_image(QImage(QSize(16, 16), QImage.Format.Format_ARGB32_Premultiplied))
        mock_open_layers.return_value = ([self.gif_path], 'filter')
        self.controller.load_image_layers()
        self.assertEqual(self._layer_names_bottom_up()[1:],
                         ['anim.gif: Frame 1 (100ms)', 'anim.gif: Frame 2 (200ms)', 'anim.gif: Frame 3 (50ms)'])


class TestRestorePreviousChoicesAction(IntraPaintTestCase):
    """Tests that the "Reopen last generated options" action tracks whether a batch can be re-opened."""

    IMAGE_SIZE = QSize(64, 64)

    def setUp(self) -> None:
        super().setUp()
        args = build_arg_parser(include_edit_params=False).parse_args(['--window_size', '800x600', '--mode', 'mock'])
        args.mode = 'mock'
        args.server_url = ''
        args.fast_ngrok_connection = False
        self.controller = AppController(args)
        self.window = self.controller._window
        self.image_stack = self.controller._image_stack
        self.image_stack.load_image(self._image(QColor(10, 20, 30)))
        AppStateTracker.set_app_state(APP_STATE_EDITING)

    def _image(self, color: QColor) -> QImage:
        image = QImage(self.IMAGE_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(color)
        return image

    def _action(self) -> QAction:
        action = self.controller.get_action_for_method(self.controller.restore_previous_image_choices)
        self.assertIsNotNone(action)
        return action

    def _complete_a_generation(self) -> None:
        """Shows the selection screen for a generation and delivers every expected image."""
        self.window.show_generated_options()
        selector = self.window._image_selector
        for idx in range(len(selector._option_items) - 1):
            self.window.load_sample_preview(self._image(QColor(idx * 40, 128, 255 - idx * 40)), idx)

    def test_disabled_without_a_stored_batch(self) -> None:
        """Nothing is stored yet, so the action is disabled."""
        self.assertFalse(self._action().isEnabled())

    def test_disabled_while_the_selection_screen_is_showing(self) -> None:
        """There is nothing to re-open while the options are already on screen."""
        self._complete_a_generation()
        self.assertFalse(self._action().isEnabled())

    def test_enabled_once_a_batch_is_stored(self) -> None:
        """Closing the screen after a completed generation makes the action available."""
        self._complete_a_generation()
        self.window.set_image_selector_visible(False)
        self.assertTrue(self._action().isEnabled())

    def test_disabled_again_for_a_new_generation(self) -> None:
        """Starting a new generation takes the old batch off the menu until the new one completes."""
        self._complete_a_generation()
        self.window.set_image_selector_visible(False)
        self.window.show_generated_options()
        self.assertFalse(self._action().isEnabled())

    def test_disabled_when_the_image_no_longer_fits_the_batch(self) -> None:
        """Shrinking the image past the stored batch's generation area takes the action away again."""
        self._complete_a_generation()
        self.window.set_image_selector_visible(False)
        self.assertTrue(self._action().isEnabled())
        self.image_stack.size = QSize(8, 8)
        self.assertFalse(self._action().isEnabled())

    def test_disabled_after_opening_a_same_size_image(self) -> None:
        """Opening another image of the same size takes the previous image's batch off the menu."""
        self._complete_a_generation()
        self.window.set_image_selector_visible(False)
        self.assertTrue(self._action().isEnabled())
        self.image_stack.load_image(self._image(QColor(200, 100, 0)))
        self.assertFalse(self._action().isEnabled())

    def test_disabled_outside_the_editing_state(self) -> None:
        """A stored batch does not make the action available in another application state."""
        self._complete_a_generation()
        self.window.set_image_selector_visible(False)
        AppStateTracker.set_app_state(APP_STATE_LOADING)
        self.assertFalse(self._action().isEnabled())
