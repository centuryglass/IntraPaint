"""Tests AppController copy, cut and paste exchanging images with the system clipboard.

The Qt clipboard is shared across tests, so every test starts by placing known content on it.
"""
import os
import sys
import tempfile

from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from src.controller.app_controller import AppController
from src.image.layers.image_layer import ImageLayer
from src.util.arg_parser import build_arg_parser
from src.util.system_clipboard import clipboard_image_is_own_copy, get_clipboard_image
from test.base_test_case import IntraPaintTestCase, assert_images_equal
from test.image.layers.image_stack_state import select_rect

app = QApplication.instance() or QApplication(sys.argv)

CANVAS_SIZE = QSize(64, 48)
CANVAS_COLOR = QColor(40, 120, 200)
PASTE_COLOR = QColor(0, 200, 60)
SELECTION = QRect(10, 8, 24, 16)


def _filled_image(size: QSize, color: QColor) -> QImage:
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color)
    return image


class AppControllerClipboardTest(IntraPaintTestCase):

    def setUp(self) -> None:
        super().setUp()
        args = ['--window_size', '800x600', '--mode', 'mock']
        self.args = build_arg_parser(include_edit_params=False).parse_args(args)
        self.args.mode = 'mock'
        self.args.server_url = ''
        self.args.fast_ngrok_connection = False
        self.controller = AppController(self.args)
        self.image_stack = self.controller._image_stack
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        image_path = os.path.join(temp_dir.name, 'base_image.png')
        self.assertTrue(_filled_image(CANVAS_SIZE, CANVAS_COLOR).save(image_path))
        self.controller.load_image(image_path)
        select_rect(self.image_stack, SELECTION)

    def _expected_selection_image(self) -> QImage:
        """Returns the filled image copy and cut are expected to place on the clipboard."""
        return _filled_image(SELECTION.size(), CANVAS_COLOR)

    def test_copy_publishes_system_clipboard_image(self) -> None:
        """Copying places the selected content on the system clipboard as IntraPaint's own copy."""
        self.controller.copy()
        self.assertTrue(clipboard_image_is_own_copy())
        read_back = get_clipboard_image()
        assert read_back is not None
        assert_images_equal(read_back, self._expected_selection_image())

    def test_cut_publishes_system_clipboard_image(self) -> None:
        """Cutting places the removed content on the system clipboard as IntraPaint's own copy."""
        self.controller.cut()
        self.assertTrue(clipboard_image_is_own_copy())
        read_back = get_clipboard_image()
        assert read_back is not None
        assert_images_equal(read_back, self._expected_selection_image())

    def test_paste_after_internal_copy_pastes_in_place(self) -> None:
        """Pasting after an internal copy uses the copy buffer, restoring the copied content's position."""
        self.controller.copy()
        self.controller.paste()
        pasted = self.image_stack.active_layer
        assert isinstance(pasted, ImageLayer)
        self.assertEqual('Paste layer', pasted.name)
        self.assertEqual(SELECTION, pasted.transformed_bounds)

    def test_paste_external_image_centers_on_generation_area(self) -> None:
        """Pasting an image copied by another program adds a layer centered on the generation area."""
        foreign = _filled_image(QSize(20, 20), PASTE_COLOR)
        QApplication.clipboard().setImage(foreign)
        expected_center = self.image_stack.generation_area.center()
        self.controller.paste()
        pasted = self.image_stack.active_layer
        assert isinstance(pasted, ImageLayer)
        self.assertEqual('Paste layer', pasted.name)
        assert_images_equal(pasted.image, foreign)
        self.assertEqual(pasted.transformed_bounds.center(), expected_center)

    def test_paste_external_image_centers_in_view(self) -> None:
        """With no generator in use, pasting an image copied by another program centers it in the visible view."""
        self.controller.load_image_generator(self.controller._null_generator)
        foreign = _filled_image(QSize(20, 20), PASTE_COLOR)
        QApplication.clipboard().setImage(foreign)
        expected_center = self.controller._image_viewer.visible_scene_bounds.center().toPoint()
        self.controller.paste()
        pasted = self.image_stack.active_layer
        assert isinstance(pasted, ImageLayer)
        self.assertEqual(pasted.transformed_bounds.center(), expected_center)

    def test_clipboard_image_enables_paste(self) -> None:
        """The paste action enables when the system clipboard gains image content from another program."""
        paste_action = self.controller.get_action_for_method(self.controller.paste)
        self.assertFalse(paste_action.isEnabled())
        QApplication.clipboard().setImage(_filled_image(QSize(20, 20), PASTE_COLOR))
        self.assertTrue(paste_action.isEnabled())


if __name__ == '__main__':
    unittest.main()