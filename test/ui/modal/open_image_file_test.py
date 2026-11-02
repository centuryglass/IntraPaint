"""Tests open_image_file."""
from unittest.mock import patch

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QFileDialog, QWidget

from src.ui.modal.modal_utils import open_image_file
from test.base_test_case import IntraPaintTestCase


class OpenImageFileTest(IntraPaintTestCase):
    """Tests the file dialog's size cap."""

    def test_dialog_capped_to_parent_window_screen(self) -> None:
        """The dialog's maximum size comes from the screen of the parent's top-level window."""
        window = QWidget()
        child = QWidget(window)
        cap = QSize(640, 480)
        with patch('src.ui.modal.modal_utils.get_screen_size', return_value=cap) as get_size, \
                patch.object(QFileDialog, 'exec', return_value=0), \
                patch.object(QFileDialog, 'setMaximumSize') as set_maximum:
            self.assertIsNone(open_image_file(child))
        self.assertEqual(get_size.call_count, 1)
        self.assertIs(get_size.call_args.args[0], window)
        set_maximum.assert_called_once_with(cap)
        get_size.reset_mock()
