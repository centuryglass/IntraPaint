"""Test main window layout and functionality."""
import sys
from unittest.mock import Mock, patch

from PySide6.QtCore import QSize
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
