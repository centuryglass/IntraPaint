import os
import sys
import unittest
from unittest.mock import patch, MagicMock

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.controller.app_controller import AppController
from src.controller.image_generation.test_generator import TestGenerator
from src.ui.modal.settings_modal import SettingsModal
from src.ui.window.main_window import MainWindow
from src.util.arg_parser import build_arg_parser

app = QApplication.instance() or QApplication(sys.argv)
exec_mock = MagicMock()


@patch('PyQt6.QtWidgets.QApplication.exec', new=exec_mock)
class TestAppController(unittest.TestCase):

    @patch('PyQt6.QtWidgets.QApplication.exec', new=exec_mock)
    def setUp(self):
        while os.path.basename(os.getcwd()) not in ('IntraPaint', ''):
            os.chdir('..')
        AppConfig('test/resources/app_config_test.json')._reset()
        KeyConfig('test/resources/key_config_test.json')._reset()
        Cache('test/resources/cache_test.json')._reset()
        self.mock_screen = MagicMock()
        args = ['--window_size', '800x600', '--mode', 'mock']
        self.args = build_arg_parser(include_edit_params=False).parse_args(args)
        self.args.mode = 'mock'
        self.args.server_url = ''
        self.args.fast_ngrok_connection = False
        self.controller = AppController(self.args)

    @patch('src.controller.app_controller.MainWindow')
    @patch('src.controller.app_controller.get_screen_size')
    def test_init(self, MockGetScreenSize, MockMainWindow):
        mock_main_window = MockMainWindow.return_value
        MockGetScreenSize.return_value = QSize(1024, 768)
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

    def test_update_settings(self):
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

        self.assertEqual(changed_settings['max_undo'], AppConfig().get('max_undo'))
        self.assertEqual(changed_settings['zoom_in'], KeyConfig().get('zoom_in'))
        KeyConfig().set('zoom_in', 'PgUp')

    @patch('src.controller.app_controller.qdarktheme')
    @patch('src.controller.app_controller.qt_material')
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

    @patch('src.controller.app_controller.qdarktheme')
    @patch('src.controller.app_controller.qt_material')
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

    @patch('src.controller.image_generation.test_generator.TestGenerator.build_menus')
    @patch('src.controller.app_controller.SettingsModal')
    @patch('src.controller.app_controller.QtExceptHook')
    @patch('src.controller.app_controller.MainWindow')
    @patch('src.controller.app_controller.AppController.clear_menus')
    @patch('src.controller.app_controller.AppController.add_menu_action')
    @patch('src.controller.app_controller.AppController.build_menus')
    @patch('src.controller.app_controller.SpacenavManager')
    def test_start_app(self, MockSpacenavManager, mock_build_menus, mock_add_menu_action, mock_clear_menus, MockMainWindow,
                       MockQtExceptHook, MockSettingsModal, _):
        self.controller = AppController(self.args)
        self.controller.start_app()
        self.assertTrue(mock_build_menus.called)
        self.assertTrue(mock_add_menu_action.called)
        self.assertTrue(MockSpacenavManager.called)
        self.assertTrue(self.controller._window.show.called)
        self.assertTrue(MockQtExceptHook.called)
        self.assertTrue(exec_mock.called)

