"""Tests the Filters menu's Repeat last filter action."""
import sys
from unittest.mock import patch

from PySide6.QtGui import QAction, QColor, QImage
from PySide6.QtWidgets import QApplication

from src.controller.app_controller import AppController, MENU_FILTERS
from src.ui.modal.image_filter_modal import ImageFilterModal
from src.undo_stack import UndoStack
from src.util.arg_parser import build_arg_parser
from src.util.async_task import AsyncTask
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

RED = QColor(255, 0, 0)
CYAN = QColor(0, 255, 255)


class TestRepeatLastFilter(IntraPaintTestCase):
    """Applies a filter through its dialog, then repeats it from the Filters menu."""

    def setUp(self):
        super().setUp()
        args = build_arg_parser(include_edit_params=False).parse_args(['--window_size', '800x600', '--mode', 'mock'])
        args.mode = 'mock'
        args.server_url = ''
        args.fast_ngrok_connection = False
        self.controller = AppController(args)
        self.image_stack = self.controller._image_stack
        layer = self.image_stack.active_layer
        image = QImage(layer.size, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(RED)
        layer.set_image(image)
        self.repeat_action = self.controller._repeat_filter_action

    def _filter_action(self, title: str) -> QAction:
        """Returns the Filters menu action with the given title."""
        for action in self.controller.get_menu(MENU_FILTERS).actions():
            if action.text() == title:
                return action
        raise ValueError(f'No {title} action')

    def _pixel(self) -> QColor:
        return self.image_stack.active_layer.image.pixelColor(0, 0)

    def test_repeat_applies_the_last_filter_again(self):
        """Repeat applies the last dialog-applied filter as one undo step, with no dialog, and names it."""
        self.assertFalse(self.repeat_action.isEnabled())
        self.assertEqual(self.repeat_action.text(), 'Repeat last filter')
        self.assertEqual(self.repeat_action.shortcut().toString(), 'Ctrl+F')
        undo_stack = UndoStack()
        start_count = undo_stack.undo_count()
        with patch.object(AsyncTask, 'start', AsyncTask.run), \
                patch.object(ImageFilterModal, 'exec', ImageFilterModal._apply_change):
            self._filter_action('Invert...').trigger()
            self.assertEqual(self._pixel(), CYAN)
            self.assertEqual(undo_stack.undo_count(), start_count + 1)
            self.assertTrue(self.repeat_action.isEnabled())
            self.assertEqual(self.repeat_action.text(), 'Repeat Invert')

            with patch.object(ImageFilterModal, '__init__', side_effect=AssertionError('dialog opened')):
                self.repeat_action.trigger()
        self.assertEqual(self._pixel(), RED)
        self.assertEqual(undo_stack.undo_count(), start_count + 2)
        undo_stack.undo()
        self.assertEqual(self._pixel(), CYAN)

    def test_repeat_keeps_active_layer_only_choice(self):
        """Repeat filters every layer when the dialog's "active layer only" box was cleared, whatever is active."""
        first_layer = self.image_stack.active_layer
        second_layer = self.image_stack.create_layer()
        image = QImage(second_layer.size, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(RED)
        second_layer.set_image(image)

        def _apply_to_all_layers(modal: ImageFilterModal) -> None:
            modal._active_only_checkbox.setChecked(False)
            modal._apply_change()

        with patch.object(AsyncTask, 'start', AsyncTask.run), \
                patch.object(ImageFilterModal, 'exec', _apply_to_all_layers):
            self._filter_action('Invert...').trigger()
            self.assertEqual(first_layer.image.pixelColor(0, 0), CYAN)
            self.assertEqual(second_layer.image.pixelColor(0, 0), CYAN)
            self.repeat_action.trigger()
        self.assertEqual(first_layer.image.pixelColor(0, 0), RED)
        self.assertEqual(second_layer.image.pixelColor(0, 0), RED)
