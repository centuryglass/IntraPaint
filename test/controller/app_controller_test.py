import gc
import os
import sys
import tempfile
import weakref
from unittest.mock import patch, MagicMock

from PySide6.QtCore import QEvent, QSize, QTimer
from PySide6.QtWidgets import QApplication, QStyleFactory, QWidget

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.controller.app_controller import AppController
from src.controller.image_generation.test_generator import TestGenerator
from src.ui.modal.settings_modal import SettingsModal
from src.ui.window.main_window import MainWindow
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
        AppConfig().add_option('theme', 'qdarktheme_dark')
        AppConfig().set('theme', 'qdarktheme_dark')
        AppConfig().set('font_point_size', QApplication.instance().font().pointSize() + 10)
        self.assertNotEqual(AppConfig().get('font_point_size'), QApplication.instance().font().pointSize())
        self.controller = AppController(self.args)
        self.assertTrue(MockQDarkTheme.setup_theme.called)
        self.assertFalse(MockQtMaterial.apply_stylesheet.called)
        self.assertEqual(AppConfig().get('font_point_size'), QApplication.instance().font().pointSize())

    @patch('src.ui.theme.qdarktheme')
    @patch('src.ui.theme.qt_material')
    def test_fix_styles_qt_material(self, MockQtMaterial, MockQDarkTheme):
        AppConfig()._reset()
        AppConfig().add_option('theme', 'qt_material_dark')
        AppConfig().set('theme', 'qt_material_dark')
        AppConfig().set('font_point_size', QApplication.instance().font().pointSize() + 10)
        self.assertNotEqual(AppConfig().get('font_point_size'), QApplication.instance().font().pointSize())
        self.controller = AppController(self.args)
        self.assertFalse(MockQDarkTheme.setup_theme.called)
        self.assertTrue(MockQtMaterial.apply_stylesheet.called)
        self.assertEqual(AppConfig().get('font_point_size'), QApplication.instance().font().pointSize())

    def test_style_change_pauses_garbage_collection(self):
        """QApplication.setStyle runs after a collection, with collection paused (see gc_paused)."""
        initial_style = AppConfig().get(AppConfig.STYLE)
        new_style = next(key for key in QStyleFactory.keys() if key.lower() != initial_style.lower())
        recorder = _GcStateRecorder()
        garbage = _unreachable_widget_cycle()
        try:
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
