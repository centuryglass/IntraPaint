"""Tests for File > Open Recent and for opening files dropped on the main window."""
import os
import sys
import tempfile
from unittest.mock import PropertyMock, patch

from PySide6.QtCore import QMimeData, QPoint, QSize, QUrl, Qt
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QImage
from PySide6.QtWidgets import QApplication

from src.image.layers.image_stack import ImageStack
from src.controller.app_controller import AppController, MENU_FILE, SUBMENU_RECENT_FILES
from src.util.application_state import AppStateTracker, APP_STATE_EDITING, APP_STATE_NO_IMAGE
from src.util.arg_parser import build_arg_parser
from src.util.recent_files import add_recent_file, clear_recent_files, recent_files
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class TestRecentFilesAndDrops(IntraPaintTestCase):
    """Drives the Open Recent submenu and the window's drop handling without opening dialogs."""

    def setUp(self) -> None:
        super().setUp()
        args = build_arg_parser(include_edit_params=False).parse_args(['--window_size', '800x600', '--mode', 'mock'])
        args.mode = 'mock'
        args.server_url = ''
        args.fast_ngrok_connection = False
        self.controller = AppController(args)
        self.window = self.controller._window
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        clear_recent_files()
        self.red_path = self._write_image('red.png', QColor('red'))
        self.blue_path = self._write_image('blue.png', QColor('blue'))

    def _write_image(self, name: str, color: QColor) -> str:
        path = os.path.join(self.temp_dir.name, name)
        image = QImage(QSize(16, 16), QImage.Format.Format_ARGB32)
        image.fill(color)
        self.assertTrue(image.save(path))
        return path

    def _without_image(self):
        """Makes the image stack report that no image is open, as it does at startup without one."""
        return patch.object(ImageStack, 'has_image', new_callable=PropertyMock, return_value=False)

    def _recent_actions(self):
        menu = self.controller._recent_files_menu
        menu.aboutToShow.emit()
        return [action for action in menu.actions() if not action.isSeparator()]

    def _drop(self, paths: list[str]) -> list[list[str]]:
        """Sends a drag-enter and a drop of local files to the window, returning what `files_dropped` reported."""
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(path) for path in paths])
        received: list[list[str]] = []
        self.window.files_dropped.connect(received.append)
        enter = QDragEnterEvent(QPoint(5, 5), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                                Qt.KeyboardModifier.NoModifier)
        self.window.dragEnterEvent(enter)
        if enter.isAccepted():
            self.window.dropEvent(QDropEvent(QPoint(5, 5), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                                             Qt.KeyboardModifier.NoModifier))
        return received

    def test_submenu_sits_in_file_menu(self) -> None:
        file_menu = self.controller.get_menu(MENU_FILE)
        self.assertIn(SUBMENU_RECENT_FILES, [action.text() for action in file_menu.actions()])

    def test_loading_records_recent_file(self) -> None:
        self.controller.load_image(self.red_path)
        self.assertEqual(recent_files(), [self.red_path])

    def test_menu_lists_files_and_disables_missing_ones(self) -> None:
        add_recent_file(self.red_path)
        add_recent_file(self.blue_path)
        os.remove(self.red_path)
        actions = self._recent_actions()
        self.assertEqual([action.text() for action in actions[:2]], ['blue.png', 'red.png'])
        self.assertEqual([action.isEnabled() for action in actions[:2]], [True, False])

    def test_menu_entry_opens_file(self) -> None:
        add_recent_file(self.blue_path)
        self._recent_actions()[0].trigger()
        self.assertEqual(recent_files(), [self.blue_path])

    def test_clear_entry_empties_list(self) -> None:
        add_recent_file(self.blue_path)
        self._recent_actions()[-1].trigger()
        self.assertEqual(recent_files(), [])
        self.assertFalse(self._recent_actions()[-1].isEnabled())

    def test_drop_rejects_unsupported_files(self) -> None:
        text_path = os.path.join(self.temp_dir.name, 'notes.txt')
        with open(text_path, 'w', encoding='utf-8') as text_file:
            text_file.write('not an image')
        self.assertEqual(self._drop([text_path, os.path.join(self.temp_dir.name, 'missing.png')]), [])

    def test_drop_without_image_loads_it(self) -> None:
        AppStateTracker.set_app_state(APP_STATE_NO_IMAGE)
        with self._without_image(), patch.object(self.controller, 'load_image') as mock_load:
            dropped = self._drop([self.red_path])
        self.assertEqual(dropped, [[self.red_path]])
        mock_load.assert_called_once_with(self.red_path)

    def test_drop_onto_open_image_adds_layer(self) -> None:
        self.controller.load_image(self.red_path)
        stack = self.controller._image_stack
        layer_count = len(stack.top_level_layers)
        with patch('src.controller.image_io.show_error_dialog') as mock_error:
            dropped = self._drop([self.blue_path])
        self.assertEqual(dropped, [[self.blue_path]])
        mock_error.assert_not_called()
        self.assertEqual(len(stack.top_level_layers), layer_count + 1)
        self.assertEqual(AppStateTracker.app_state(), APP_STATE_EDITING)
