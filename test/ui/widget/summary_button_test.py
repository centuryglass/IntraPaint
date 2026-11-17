"""Tests for `SummaryButton`."""
from PySide6.QtWidgets import QPushButton

from src.ui.widget.summary_button import DEFAULT_MAX_LINES, SummaryButton
from test.base_test_case import IntraPaintTestCase


class SummaryButtonTest(IntraPaintTestCase):
    """The summary line adds to the preferred height only, and the height cap follows `set_max_lines`."""

    def test_minimum_height_ignores_the_summary(self) -> None:
        """The minimum size stays that of a plain button, and the preferred height grows by a line."""
        button = SummaryButton('Generate')
        plain = QPushButton('Generate')
        self.assertEqual(button.minimumSizeHint(), plain.sizeHint())
        button.set_summary('5 x 512x512')
        self.assertEqual(button.minimumSizeHint(), plain.sizeHint())
        self.assertGreater(button.sizeHint().height(), plain.sizeHint().height())

    def test_max_lines_caps_the_height(self) -> None:
        """Two lines of height take no spare room, and more let the button stretch."""
        button = SummaryButton('Generate')
        button.set_summary('5 x 512x512')
        self.assertEqual(button.maximumHeight(), button.sizeHint().height())
        button.set_max_lines(DEFAULT_MAX_LINES + 1)
        self.assertGreater(button.maximumHeight(), button.sizeHint().height())
