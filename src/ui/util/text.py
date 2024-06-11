"""Utility functions for display text management."""
import logging
from PyQt5.QtCore import QSize
from PyQt5.QtGui import QFont, QFontMetrics

MAX_FONT_PT = 240
logger = logging.getLogger(__name__)

def find_text_size(text: str, font: QFont) -> QSize:
    """Returns the size in pixels required to render the text with the given font."""
    return QFontMetrics(font).boundingRect(text).size()


def max_font_size(text: str, font: QFont, bounds: QSize) -> int:
    """Returns the largest font size that will fit within the given bounds."""
    if len(text) == 0:
        return MAX_FONT_PT
    max_pt = 0
    test_size = QSize(0, 0)
    test_font = QFont(font)
    while max_pt < MAX_FONT_PT and test_size.width() < bounds.width() and test_size.height() < bounds.height():
        max_pt += 1
        test_font.setPointSize(max_pt)
        test_size = find_text_size(text, test_font)
    max_pt -= 1
    logger.debug(f'"{text}" fits in {bounds} at size {max_pt}')
    return max_pt
