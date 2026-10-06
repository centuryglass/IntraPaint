"""Test TextRect automatic scaling."""
from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtGui import QFont, QFontMetrics

from src.image.text_rect import TextRect
from test.base_test_case import IntraPaintTestCase


class TestTextRect(IntraPaintTestCase):
    """Test TextRect automatic scaling."""

    def test_text_scaled_to_bounds_fits_when_drawn(self) -> None:
        """Scaling text to bounds picks a font that render() can draw inside the bounds."""
        for text, size in (('Text', QSize(200, 60)), ('Two\nlines', QSize(200, 120)), ('Wide line', QSize(300, 40))):
            text_rect = TextRect()
            text_rect.font = QFont()
            text_rect.text = text
            text_rect.size = size
            text_rect.scale_text_to_bounds = True
            drawn_size = QFontMetrics(text_rect.font).boundingRect(QRect(QPoint(0, 0), size),
                                                                   int(text_rect.text_alignment), text).size()
            self.assertLessEqual(drawn_size.width(), size.width(), repr(text))
            self.assertLessEqual(drawn_size.height(), size.height(), repr(text))
            self.assertGreater(text_rect.font.pointSize(), 1, repr(text))
