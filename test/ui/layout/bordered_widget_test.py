"""Tests BorderedWidget's border color and line width properties."""
import sys

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QFrame

from src.ui.layout.bordered_widget import BorderedWidget, DEFAULT_LINE_WIDTH
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class BorderedWidgetTest(IntraPaintTestCase):
    """Changes a BorderedWidget's border properties."""

    def setUp(self) -> None:
        super().setUp()
        self.widget = BorderedWidget()

    def test_defaults(self) -> None:
        """A new widget draws a raised panel at the default line width."""
        self.assertEqual(self.widget.frameShape(), QFrame.Shape.Panel)
        self.assertEqual(self.widget.line_width, DEFAULT_LINE_WIDTH)

    def test_custom_color_draws_a_box(self) -> None:
        """A non-default color switches to a box frame, and the default color switches back to a panel."""
        default_color = self.widget.frame_color
        self.widget.frame_color = QColor('red')
        self.assertEqual(self.widget.frame_color, QColor('red'))
        self.assertEqual(self.widget.frameShape(), QFrame.Shape.Box)
        self.widget.frame_color = default_color
        self.assertEqual(self.widget.frameShape(), QFrame.Shape.Panel)

    def test_line_width(self) -> None:
        """line_width sets the frame's line width."""
        self.widget.line_width = 7
        self.assertEqual(self.widget.lineWidth(), 7)
