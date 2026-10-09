"""Tests for the Ink theme's signal color: where it is marked, and how marked controls and icons draw."""
import sys
from unittest.mock import patch

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QCheckBox, QMessageBox, QPushButton

from src.ui.ink_style import SIGNAL_PROPERTY, InkStyle, ink_colors, set_signal, signal_color
from src.ui.modal.modal_utils import request_confirmation, show_error_dialog
from src.ui.theme import THEME_SYSTEM, apply_theme, THEME_INK
from src.util.visual.palette_icon import palette_icon
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

ICON_PATH = 'resources/icons/layer/minus_icon.svg'
ICON_SIZE = 16


def _icon_colors(icon_path: str, signal: bool) -> set[int]:
    image = palette_icon(icon_path, signal=signal).pixmap(ICON_SIZE, ICON_SIZE).toImage()
    return {image.pixel(x, y) for x in range(image.width()) for y in range(image.height())
            if QColor(image.pixel(x, y)).alpha() > 0xf0}


def _render(widget: QPushButton | QCheckBox) -> QImage:
    widget.resize(widget.sizeHint())
    return widget.grab().toImage()


class SignalColorTest(IntraPaintTestCase):
    """The test session applies THEME_INK in conftest.py, so each test starts and ends with it applied."""

    def tearDown(self) -> None:
        apply_theme(THEME_INK)
        super().tearDown()

    def test_ink_style_has_signal_color(self):
        self.assertIsInstance(QApplication.style(), InkStyle)
        self.assertEqual('#ff5145', signal_color().name())
        self.assertEqual('#303134', ink_colors().canvas_surround.name())

    def test_signal_color_missing_without_ink_style(self):
        apply_theme(THEME_SYSTEM)
        self.assertIsNone(signal_color())
        self.assertIsNone(ink_colors())

    def test_signal_button_draws_in_signal_color(self):
        plain = QPushButton('Discard')
        marked = QPushButton('Discard')
        set_signal(marked)
        self.assertTrue(marked.property(SIGNAL_PROPERTY))
        marked_image = _render(marked)
        self.assertNotEqual(_render(plain), marked_image)
        self.assertIn(signal_color().rgb(), {marked_image.pixel(x, marked_image.height() // 2)
                                              for x in range(marked_image.width())})

    def test_signal_check_box_fills_with_signal_color(self):
        plain = QCheckBox()
        plain.setChecked(True)
        marked = QCheckBox()
        marked.setChecked(True)
        set_signal(marked)
        marked_image = _render(marked)
        self.assertNotEqual(_render(plain), marked_image)
        marked_colors = {marked_image.pixel(x, y) for x in range(marked_image.width())
                         for y in range(marked_image.height())}
        self.assertIn(signal_color().rgb(), marked_colors)

    def test_signal_icon_uses_signal_color(self):
        self.assertIn(signal_color().rgb(), _icon_colors(ICON_PATH, signal=True))
        self.assertNotIn(signal_color().rgb(), _icon_colors(ICON_PATH, signal=False))

    def test_signal_icon_unchanged_without_signal_color(self):
        apply_theme(THEME_SYSTEM)
        self.assertEqual(_icon_colors(ICON_PATH, signal=False), _icon_colors(ICON_PATH, signal=True))

    def test_confirmation_marks_confirm_button_only_when_discarding_work(self):
        marked: dict[str, bool] = {}

        def _record(box: QMessageBox) -> int:
            button = box.button(QMessageBox.StandardButton.Ok)
            cancel = box.button(QMessageBox.StandardButton.Cancel)
            marked['confirm'] = bool(button.property(SIGNAL_PROPERTY))
            marked['cancel'] = bool(cancel.property(SIGNAL_PROPERTY))
            return int(QMessageBox.StandardButton.Ok)

        with patch.object(QMessageBox, 'exec', _record, create=True):
            self.assertTrue(request_confirmation(None, 'title', 'message', discards_work=True))
            self.assertEqual({'confirm': True, 'cancel': False}, marked)
            self.assertTrue(request_confirmation(None, 'title', 'message'))
            self.assertEqual({'confirm': False, 'cancel': False}, marked)

    def test_error_dialog_marks_ok_button_only_with_signal(self):
        marked: list[bool] = []

        def _record(box: QMessageBox) -> int:
            marked.append(bool(box.button(QMessageBox.StandardButton.Ok).property(SIGNAL_PROPERTY)))
            return 0

        with patch.object(QMessageBox, 'exec', _record, create=True):
            show_error_dialog(None, 'title', 'message', signal=True)
            show_error_dialog(None, 'title', 'message')
        self.assertEqual([True, False], marked)
