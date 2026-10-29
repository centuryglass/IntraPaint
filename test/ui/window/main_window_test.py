"""Test main window layout and functionality."""
import sys
from unittest.mock import Mock, patch

from PySide6.QtCore import QSize
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication

from src.image.layers.image_stack import ImageStack
from src.ui.window.main_window import MainWindow
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class MainWindowTest(IntraPaintTestCase):
    """Test main window layout and functionality."""

    def setUp(self) -> None:
        super().setUp()
        test_size = QSize(512, 512)
        self._image_stack = ImageStack(test_size, test_size, test_size, test_size)
        self._controller = Mock()
        self.window = MainWindow(self._image_stack)
        self.window.show()

    @patch('src.util.visual.display_size.get_screen_size', new_callable=lambda: QSize(800, 600))
    def test_panel_layout(self, _) -> None:
        """Test orientation/layout changes as window size changes."""
        large_vertical = QSize(2000, 4000)
        large_horizontal = QSize(4000, 2000)
        small_horizontal = QSize(1024, 768)
        assert self.window is not None
        self.assertTrue(self.window.isVisible())
        self.assertFalse(self.window.geometry().isEmpty())
        # TODO: rewrite once tabbed layout design is stable

    def test_clamp_fits_frame_to_screen_and_settles(self) -> None:
        """Clamping fits the window's frame to the screen, so the resize it makes doesn't schedule another resize."""
        screen = QSize(700, 500)
        window = self.window
        window.resize(900, 700)
        frame_margins = window.frameGeometry().size() - window.size()
        with patch('src.ui.window.main_window.get_screen_size', return_value=screen):
            window._clamp_to_screen()  # pylint: disable=protected-access
            self.assertLessEqual(window.frameGeometry().width(), screen.width())
            self.assertLessEqual(window.frameGeometry().height(), screen.height())
            self.assertEqual(window.size(), screen - frame_margins)
            with patch.object(window, 'resize') as resize:
                window._clamp_to_screen()  # pylint: disable=protected-access
            resize.assert_not_called()

    @patch('src.ui.window.main_window.QApplication.exit')
    def test_close_without_confirmation_handler_exits(self, mock_exit) -> None:
        """A window with no `confirm_close` handler closes and exits the application."""
        self.assertTrue(self.window.close())
        mock_exit.assert_called_once()

    @patch('src.ui.window.main_window.QApplication.exit')
    def test_close_confirmed_exits(self, mock_exit) -> None:
        """Closing asks `confirm_close` once and exits when it agrees."""
        confirm = Mock(return_value=True)
        self.window.confirm_close = confirm
        self.window.close()
        confirm.assert_called_once()
        mock_exit.assert_called_once()

    @patch('src.ui.window.main_window.QApplication.exit')
    def test_close_cancelled_keeps_window_open(self, mock_exit) -> None:
        """The close event is ignored and the application keeps running when `confirm_close` declines."""
        confirm = Mock(return_value=False)
        self.window.confirm_close = confirm
        event = QCloseEvent()
        event.accept()
        self.window.closeEvent(event)
        self.assertFalse(event.isAccepted())
        self.assertFalse(self.window.close())
        self.assertTrue(self.window.isVisible())
        mock_exit.assert_not_called()

    @patch('src.ui.window.main_window.QApplication.exit')
    def test_close_without_confirmation_skips_handler(self, mock_exit) -> None:
        """`close_without_confirmation` exits without asking, and restores the handler afterwards."""
        confirm = Mock(return_value=False)
        self.window.confirm_close = confirm
        self.window.close_without_confirmation()
        confirm.assert_not_called()
        mock_exit.assert_called_once()
        self.assertIs(self.window.confirm_close, confirm)

    def test_loading_widget_stays_hidden_over_selection_screen(self) -> None:
        """While the selection screen shows, its unfilled options show the loading state, so the full-window indicator
        stays hidden and the progress text goes to the screen."""
        self.window.show_generated_options(None)
        self.window.set_is_loading(True)
        self.window.set_loading_message('step 3/20')
        self.assertFalse(self.window._loading_widget.isVisible())  # pylint: disable=protected-access
        selector = self.window._image_selector  # pylint: disable=protected-access
        self.assertEqual(selector._progress_text, 'step 3/20')  # pylint: disable=protected-access

    def test_loading_widget_is_topmost_over_the_canvas(self) -> None:
        """Outside the selection screen, the loading indicator is the topmost child while a task runs."""
        self.window.set_is_loading(True)
        loading_widget = self.window._loading_widget  # pylint: disable=protected-access
        self.assertTrue(loading_widget.isVisible())
        child_widgets = [child for child in self.window.children() if child.isWidgetType()]
        self.assertIs(child_widgets[-1], loading_widget)
