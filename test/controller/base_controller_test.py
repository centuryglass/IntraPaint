import os
import sys
import unittest
from unittest.mock import patch, MagicMock

from PyQt5.QtCore import QSize
from PyQt5.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.controller.base_controller import BaseInpaintController
from src.util.arg_parser import build_arg_parser

app = QApplication.instance() or QApplication(sys.argv)
exec_mock = MagicMock()


@patch('PyQt5.QtWidgets.QApplication.exec_', new=exec_mock)
class TestBaseInpaintController(unittest.TestCase):

    @patch('PyQt5.QtWidgets.QApplication.exec_', new=exec_mock)
    def setUp(self):
        while os.path.basename(os.getcwd()) not in ('IntraPaint', ''):
            os.chdir('..')
        AppConfig('test/resources/app_config_test.json')._reset()
        KeyConfig('test/resources/key_config_test.json')._reset()
        Cache('test/resources/cache_test.json')._reset()
        self.mock_screen = MagicMock()
        args = ['--window_size', '800x600']
        args = build_arg_parser(include_edit_params=False).parse_args(args)
        self.controller = BaseInpaintController(args)

    def test_init(self):
        self.assertIsInstance(self.controller, BaseInpaintController)
        self.assertEqual(self.controller._fixed_window_size, QSize(800, 600))
        self.assertIsNone(self.controller._window)
        self.assertIsNone(self.controller._layer_panel)
        self.assertIsNone(self.controller._settings_panel)
        self.assertIsNone(self.controller._nav_manager)
        self.assertIsNone(self.controller._worker)
        self.assertIsNone(self.controller._metadata)

    def test_get_config_categories(self):
        categories = self.controller.get_config_categories()
        self.assertNotIn('Stable-Diffusion', categories)
        self.assertNotIn('GLID-3-XL', categories)
        self.assertIn('Interface', categories)

    @patch('src.controller.base_controller.SettingsModal')
    def test_init_settings(self, MockSettingsModal):
        settings_modal = MockSettingsModal.return_value
        self.controller.init_settings(settings_modal)
        settings_modal.load_from_config.assert_called()

    @patch('src.controller.base_controller.SettingsModal')
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

    @patch('src.controller.base_controller.BaseInpaintController.fix_styles')
    @patch('src.controller.base_controller.MainWindow')
    @patch('src.controller.base_controller.get_screen_size')
    def test_window_init(self, MockGetScreenSize, MockMainWindow, _mock_fix_styles):
        mock_main_window = MockMainWindow.return_value
        MockGetScreenSize.return_value = QSize(1024, 768)
        self.controller.window_init()
        self.assertTrue(mock_main_window.show.called)
        self.assertTrue(mock_main_window.setGeometry.called)
        self.assertTrue(self.controller.fix_styles.called)

    @patch('src.controller.base_controller.qdarktheme')
    @patch('src.controller.base_controller.qt_material')
    def test_fix_styles_qdarktheme(self, MockQtMaterial, MockQDarkTheme):
        AppConfig().add_option('theme', 'qdarktheme_dark')
        AppConfig().set('theme', 'qdarktheme_dark')
        AppConfig().set('font_point_size', QApplication.instance().font().pointSize() + 10)
        self.assertNotEqual(AppConfig().get('font_point_size'), QApplication.instance().font().pointSize())
        self.controller.fix_styles()
        self.assertTrue(MockQDarkTheme.setup_theme.called)
        self.assertFalse(MockQtMaterial.apply_stylesheet.called)
        self.assertEqual(AppConfig().get('font_point_size'), QApplication.instance().font().pointSize())

    @patch('src.controller.base_controller.qdarktheme')
    @patch('src.controller.base_controller.qt_material')
    def test_fix_styles_qt_material(self, MockQtMaterial, MockQDarkTheme):
        AppConfig().add_option('theme', 'qt_material_dark')
        AppConfig().set('theme', 'qt_material_dark')
        AppConfig().set('font_point_size', QApplication.instance().font().pointSize() + 10)
        self.assertNotEqual(AppConfig().get('font_point_size'), QApplication.instance().font().pointSize())
        self.controller.fix_styles()
        self.assertFalse(MockQDarkTheme.setup_theme.called)
        self.assertTrue(MockQtMaterial.apply_stylesheet.called)
        self.assertEqual(AppConfig().get('font_point_size'), QApplication.instance().font().pointSize())

    @patch('src.controller.base_controller.QtExceptHook')
    @patch('src.controller.base_controller.MainWindow')
    @patch('src.controller.base_controller.BaseInpaintController.add_menu_action')
    @patch('src.controller.base_controller.BaseInpaintController.build_menus')
    @patch('src.controller.base_controller.SpacenavManager')
    def test_start_app(self, MockSpacenavManager, mock_build_menus, mock_add_menu_action, MockMainWindow,
                       MockQtExceptHook):
        self.controller.start_app()
        self.assertTrue(mock_build_menus.called)
        self.assertTrue(mock_add_menu_action.called)
        self.assertTrue(MockSpacenavManager.called)
        self.assertTrue(self.controller._window.show.called)
        self.assertTrue(MockQtExceptHook.called)
        self.assertTrue(exec_mock.called)

