"""Various utility functions for drawing and placing text."""
from typing import Optional, cast

from PySide6.QtCore import QRect, QMargins, QSize, QPoint, Qt
from PySide6.QtGui import QFont, QPainter, QFontMetrics, QPainterPath, QTransform, QColor, QPalette, QImage, \
    QKeySequence
from PySide6.QtWidgets import QApplication

from src.util.visual.display_size import logger
from src.util.visual.geometry_utils import align_inner_bounds
from src.util.visual.image_utils import create_transparent_image, temp_rich_text_image
from src.util.shared_constants import PROJECT_DIR

ICON_LMB = f'{PROJECT_DIR}/resources/input_hints/lmb.svg'
ICON_MMB = f'{PROJECT_DIR}/resources/input_hints/mmb.svg'
ICON_RMB = f'{PROJECT_DIR}/resources/input_hints/rmb.svg'
ICON_V_SCROLL = f'{PROJECT_DIR}/resources/input_hints/v_scroll.svg'
# noinspection SpellCheckingInspection
ICON_H_SCROLL = f'{PROJECT_DIR}/resources/input_hints/horiz_scroll.svg'
MAX_FONT_PT = 240


def _find_line_size(font: QFont, text: str, exact=False) -> QSize:
    if exact:
        path = QPainterPath()
        path.addText(QPoint(), font, text)
        return path.boundingRect().size().toSize()
    metric = QFontMetrics(font)
    line_size = metric.boundingRect(text).size()
    max_height = metric.ascent() + metric.descent()
    line_size.setHeight(max(line_size.height(), max_height) + 2)
    line_size.setWidth(line_size.width() + 2)
    return line_size


def find_text_size(text: str, font: Optional[QFont] = None, multiline=True, exact=False,
                   orientation=Qt.Orientation.Horizontal) -> QSize:
    """Returns the size in pixels required to render the text with the given font."""
    if font is None:  # Use application default
        app = cast(QApplication, QApplication.instance())
        assert app is not None
        font = app.font()
    if not multiline:
        return _find_line_size(font, text, exact)
    lines = text.split('\n')
    size = QSize()
    for line in lines:
        if len(line) == 0:
            line = ' '
        line_size = _find_line_size(font, line, exact)
        size.setWidth(max(size.width(), line_size.width()))
        size.setHeight(size.height() + line_size.height())
    if orientation == Qt.Orientation.Vertical:
        return size.transposed()
    return size


def max_font_size(text: str, font: QFont, bounds: QSize, exact=False) -> int:
    """Returns the largest font size that will fit within the given bounds."""
    if len(text) == 0:
        return MAX_FONT_PT
    max_pt = 0
    test_size = QSize(0, 0)
    test_font = QFont(font)
    while max_pt < MAX_FONT_PT and test_size.width() < bounds.width() and test_size.height() < bounds.height():
        max_pt += 1
        test_font.setPointSize(max_pt)
        test_size = find_text_size(text, test_font, exact)
    max_pt -= 1
    logger.debug(f'"{text}" fits in {bounds} at size {max_pt}')
    return max_pt


def create_text_path(text: str, font: QFont, bounds: Optional[QRect] = None, alignment=Qt.AlignmentFlag.AlignCenter,
                     margins: Optional[QMargins] = None, orientation=Qt.Orientation.Horizontal) -> QPainterPath:
    """Creates a text path and ensures it's positioned correctly for the given bounds, margin, alignment, and
       orientation."""
    if orientation == Qt.Orientation.Vertical and bounds is not None:
        bounds = bounds.transposed()
    path = QPainterPath()
    if text.strip() == '':
        return path
    path.addText(QPoint(), font, text)
    text_bounds = path.boundingRect().toAlignedRect()
    if bounds is None and margins is not None:
        bounds = QRect(0, 0, text_bounds.width() + margins.left() + margins.right(),
                       text_bounds.height() + margins.top() + margins.bottom())
    top_left = QPoint() if bounds is None else bounds.topLeft()
    text_bounds.moveTo(top_left)
    if bounds is not None:
        text_bounds = text_bounds.intersected(bounds)
        align_inner_bounds(bounds, text_bounds, alignment, margins)
    offset = text_bounds.topLeft()

    if orientation == Qt.Orientation.Vertical:
        width = text_bounds.height() if bounds is None else bounds.height()
        offset = QPoint(width - offset.y() - text_bounds.height(), offset.x())
        path = QTransform().rotate(90).map(path)
    final_offset = offset - path.boundingRect().toAlignedRect().topLeft()
    path = QTransform.fromTranslate(final_offset.x(), final_offset.y()).map(path)
    assert isinstance(path, QPainterPath)
    path.setFillRule(Qt.FillRule.WindingFill)
    return path


def draw_text_path(path: QPainterPath, painter: QPainter, text_color: Optional[QColor | Qt.GlobalColor] = None) -> None:
    """Draws a text path."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.LosslessImageRendering, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    if text_color is None:
        app_palette = QApplication.palette()
        assert isinstance(app_palette, QPalette)
        text_color = app_palette.color(QPalette.ColorRole.Text)
    assert isinstance(path, QPainterPath)
    painter.fillPath(path, text_color)
    painter.restore()


def rich_text_key_hint(key_str: str) -> str:
    """Returns a styled key hint."""

    def _draw_text_image() -> QImage:
        margins = QMargins(3, 3, 3, 3)
        font = QApplication.font()
        text_path = create_text_path(key_str, font, margins=margins)
        text_bounds = text_path.boundingRect().toAlignedRect()
        if len(key_str) < 2:
            height = max(text_bounds.height(), text_bounds.width())
            dy = height - text_bounds.height()
            if dy > 0:
                text_bounds.setHeight(height)
                text_path = QTransform.fromTranslate(0, dy // 2).map(text_path)
            else:
                width = max(text_bounds.width(), text_bounds.height())
                dx = width - text_bounds.width()
                if dx > 0:
                    text_bounds.setWidth(width)
                    text_path = QTransform.fromTranslate(dx // 2, 0).map(text_path)
        image_bounds = QRect(0, 0, text_bounds.width() + margins.left() + margins.right(),
                             text_bounds.height() + margins.top() + margins.bottom())
        image = create_transparent_image(image_bounds.size())
        palette = QApplication.palette()
        bg_color = palette.color(QPalette.ColorRole.Base)
        text_color = palette.color(QPalette.ColorRole.BrightText)
        key_rect_path = QPainterPath()
        key_rect_path.addRoundedRect(image_bounds.adjusted(0, 0, -1, -1), 3, 3)
        painter = QPainter(image)
        painter.fillPath(key_rect_path, bg_color)
        painter.setPen(text_color)
        painter.drawPath(key_rect_path)
        draw_text_path(text_path, painter, text_color)
        painter.end()
        return image

    return temp_rich_text_image(key_str, _draw_text_image)


def rich_text_code_block(code_string: str) -> str:
    """Formats some text as a rich text code block."""
    return ('<pre style="font-family: \'Courier New\', monospace; background-color: #f0f0f0; color: #000000;'
            f' padding: 5px; border: 1px solid #ccc; margin-right: 100px;">{code_string}</pre>')


def _rich_text_image(img_path: str) -> str:
    return f'<img src="{img_path}"/>'


def left_button_hint_text() -> str:
    """Returns a rich-text inline image representing the left mouse button."""
    return _rich_text_image(ICON_LMB)


def middle_button_hint_text() -> str:
    """Returns a rich-text inline image representing the middle mouse button."""
    return _rich_text_image(ICON_MMB)


def right_button_hint_text() -> str:
    """Returns a rich-text inline image representing the right mouse button."""
    return _rich_text_image(ICON_RMB)


def vertical_scroll_hint_text() -> str:
    """Returns a rich-text inline image representing scroll wheel vertical scrolling."""
    return _rich_text_image(ICON_V_SCROLL)


def horizontal_scroll_hint_text() -> str:
    """Returns a rich-text inline image representing scroll wheel horizontal scrolling."""
    return _rich_text_image(ICON_H_SCROLL)


def get_key_display_string(keys: QKeySequence | Qt.Key | int | str, rich_text: bool = True) -> str:
    """Creates a display string representing a set of keys, replacing common symbols with appropriate characters."""
    if isinstance(keys, (Qt.Key, int)):
        keys = QKeySequence(keys)
    text = keys if isinstance(keys, str) else keys.toString()
    symbol_map = {
        'Ctrl+': '⌃',
        'Ctrl': '⌃',
        'Alt+': '⎇',
        'Alt': '⎇',
        'Meta+': '⌘',
        'Meta': '⌘',
        'Shift+': '⇧',
        'Shift': '⇧',
        'Enter': '⏎',
        'Del': '⌫',
        'Home': '⇱',
        'End': '⇲',
        'PgUp': '⇞',
        'PgDown': '⇟',
        'Up': '↑',
        'Down': '↓',
        'Left': '←',
        'Right': '→'
    }
    for key, symbol in symbol_map.items():
        text = text.replace(key, symbol)
    if rich_text:
        return rich_text_key_hint(text)
    return text
