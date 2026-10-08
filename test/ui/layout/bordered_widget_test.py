"""Tests BorderedWidget's border color and line width properties, and the border it draws."""
import sys

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage, QPalette
from PySide6.QtWidgets import QApplication

from src.ui.layout.bordered_widget import BorderedWidget, DEFAULT_LINE_WIDTH
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

WIDGET_SIZE = QSize(40, 30)


class BorderedWidgetTest(IntraPaintTestCase):
    """Changes a BorderedWidget's border properties."""

    def setUp(self) -> None:
        super().setUp()
        self.widget = BorderedWidget()
        self.widget.resize(WIDGET_SIZE)

    def _render(self) -> QImage:
        return self.widget.grab().toImage()

    def test_defaults(self) -> None:
        """A new widget draws its border in the palette's ink color, at the default line width."""
        ink = self.widget.palette().color(QPalette.ColorRole.Shadow)
        self.assertEqual(self.widget.frame_color, ink)
        self.assertEqual(self.widget.line_width, DEFAULT_LINE_WIDTH)
        self.assertEqual(self.widget.frameWidth(), DEFAULT_LINE_WIDTH)
        image = self._render()
        self.assertEqual(image.pixelColor(0, 0), ink)
        self.assertEqual(image.pixelColor(WIDGET_SIZE.width() - 1, WIDGET_SIZE.height() - 1), ink)
        self.assertEqual(image.pixelColor(WIDGET_SIZE.width() // 2, WIDGET_SIZE.height() // 2),
                         self.widget.palette().color(QPalette.ColorRole.Window))

    def test_custom_color(self) -> None:
        """A custom color draws the border in that color, and the default color follows the palette again."""
        default_color = self.widget.frame_color
        self.widget.frame_color = QColor('red')
        self.assertEqual(self.widget.frame_color, QColor('red'))
        self.assertEqual(self._render().pixelColor(0, 0), QColor('red'))
        self.widget.frame_color = default_color
        palette = self.widget.palette()
        palette.setColor(QPalette.ColorRole.Shadow, QColor('blue'))
        self.widget.setPalette(palette)
        self.assertEqual(self.widget.frame_color, QColor('blue'))

    def test_line_width(self) -> None:
        """line_width sets the frame's line width, the border's thickness and the contents margins."""
        self.widget.line_width = 4
        self.assertEqual(self.widget.lineWidth(), 4)
        self.assertEqual(self.widget.contentsRect(), self.widget.rect().adjusted(4, 4, -4, -4))
        image = self._render()
        self.assertEqual(image.pixelColor(3, 3), self.widget.frame_color)
        self.assertNotEqual(image.pixelColor(4, 4), self.widget.frame_color)

    def test_zero_line_width_draws_no_border(self) -> None:
        """A zero line width draws no border."""
        self.widget.line_width = 0
        self.assertEqual(self._render().pixelColor(0, 0), self.widget.palette().color(QPalette.ColorRole.Window))
