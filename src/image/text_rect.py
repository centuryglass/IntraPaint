"""Represents exact instructions for rendering text data into an image."""
import json
from typing import Optional, Any, Self

from PySide6.QtCore import QRect, QSize, QPoint
from PySide6.QtGui import QColor, Qt, QFont, QPainter, QImage
from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.util.visual.image_utils import create_transparent_image
from src.util.visual.text_drawing_utils import find_text_size, max_font_size


class TextRectKeys:
    """Keys used for TextRect serialization:"""
    FONT = 'font'
    TEXT = 'text'
    SIZE = 'size'
    TEXT_COLOR = 'text_color'
    BG_COLOR = 'bg_color'
    ALIGNMENT = 'alignment'
    FILL_BG = 'fill_background'
    AUTO_SCALE_MODE = 'scale_mode'
    ALL = [FONT, TEXT, SIZE, TEXT_COLOR, BG_COLOR, ALIGNMENT, FILL_BG]


SCALE_MODE_NONE = 'none'
SCALE_MODE_BOUNDS_TO_TEXT = 'bounds to text'
SCALE_MODE_TEXT_TO_BOUNDS = 'text to bounds'

DEFAULT_SIZE = QSize(100, 100)


class TextRect:
    """Data class specifying a block of text, along with exactly where and how it should be rendered."""

    def __init__(self, source: Optional[Self | dict[str, Any]] = None) -> None:
        if isinstance(source, TextRect):
            self._text = source.text
            self._font = source.font
            self._text_color = source.text_color
            self._background_color = source.background_color
            self._size = source.size
            self._text_alignment = Qt.AlignmentFlag(source.text_alignment)
            self._fill_background: bool = source.fill_background
            self._scale_mode: str = source._scale_mode
        elif isinstance(source, dict):
            for key in TextRectKeys.ALL:
                assert key in source, f'Missing expected key {key}'
            self._text = source[TextRectKeys.TEXT]
            self._font = QFont()
            self._font.fromString(source[TextRectKeys.FONT])
            self._text_color = QColor(source[TextRectKeys.TEXT_COLOR])
            self._background_color = QColor(source[TextRectKeys.BG_COLOR])
            self._size = QSize(*source[TextRectKeys.SIZE][:2])
            self._text_alignment = Qt.AlignmentFlag(source[TextRectKeys.ALIGNMENT])
            self._fill_background = source[TextRectKeys.FILL_BG]
            self._scale_mode = source[TextRectKeys.AUTO_SCALE_MODE]
        else:
            self._text = ''
            self._font = QApplication.font()
            self._text_color = Cache().get_color(Cache.LAST_BRUSH_COLOR, Qt.GlobalColor.black)
            self._background_color = Cache().get_color(Cache.TEXT_BACKGROUND_COLOR, Qt.GlobalColor.white)
            self._size = QSize(DEFAULT_SIZE)
            self._text_alignment = Qt.AlignmentFlag.AlignLeft
            self._fill_background = False
            self._scale_mode = SCALE_MODE_NONE

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TextRect):
            return False
        return (self._text == other._text and self._font.isCopyOf(other._font)
                and self._text_color == other._text_color and self._background_color == other._background_color
                and self._size == other._size and self._text_alignment == other._text_alignment
                and self._fill_background == other._fill_background
                and self._scale_mode == other._scale_mode)

    @staticmethod
    def deserialize(text_data: str) -> 'TextRect':
        """Create a TextRect from serialized data"""
        data_dict = json.loads(text_data)
        assert isinstance(data_dict, dict)
        return TextRect(data_dict)

    def serialize(self, exclude_text=False) -> str:
        """Serialize this object as a JSON string."""
        data_dict: dict[str, Any] = {
            TextRectKeys.TEXT: self._text if not exclude_text else '',
            TextRectKeys.FONT: self._font.toString(),
            TextRectKeys.TEXT_COLOR: self._text_color.name(QColor.NameFormat.HexArgb),
            TextRectKeys.BG_COLOR: self._background_color.name(QColor.NameFormat.HexArgb),
            TextRectKeys.SIZE: [self._size.width(), self._size.height()]
            if not exclude_text else [0, 0, DEFAULT_SIZE.width(), DEFAULT_SIZE.height()],
            TextRectKeys.ALIGNMENT: self._text_alignment.value,
            TextRectKeys.FILL_BG: self.fill_background,
            TextRectKeys.AUTO_SCALE_MODE: self._scale_mode
        }
        return json.dumps(data_dict)

    @property
    def text(self) -> str:
        """Returns the rendered text."""
        return self._text

    @text.setter
    def text(self, new_text: str) -> None:
        self._text = new_text
        self._apply_auto_scale()

    @property
    def font(self) -> QFont:
        """Returns a copy of the text drawing font."""
        return QFont(self._font)

    @font.setter
    def font(self, new_font: QFont) -> None:
        self._font = QFont(new_font)
        self._apply_auto_scale()

    @property
    def text_color(self) -> QColor:
        """Returns the text color."""
        return QColor(self._text_color)

    @text_color.setter
    def text_color(self, new_color: QColor) -> None:
        self._text_color = QColor(new_color)

    @property
    def background_color(self) -> QColor:
        """Returns the text background color (possibly not rendered)."""
        return QColor(self._background_color)

    @background_color.setter
    def background_color(self, new_color: QColor) -> None:
        self._background_color = QColor(new_color)

    @property
    def size(self) -> QSize:
        """Returns the text size."""
        return QSize(self._size)

    @size.setter
    def size(self, new_size: QSize) -> None:
        self._size = QSize(new_size)
        self._apply_auto_scale()

    @property
    def text_alignment(self) -> Qt.AlignmentFlag:
        """Returns the text alignment."""
        return self._text_alignment

    @text_alignment.setter
    def text_alignment(self, new_alignment: Qt.AlignmentFlag) -> None:
        assert new_alignment.is_integer()
        self._text_alignment = new_alignment

    @property
    def fill_background(self) -> bool:
        """Returns whether the background should be filled."""
        return self._fill_background

    @fill_background.setter
    def fill_background(self, should_fill: bool) -> None:
        self._fill_background = should_fill

    @property
    def scale_bounds_to_text(self) -> bool:
        """Returns whether bounds size is automatically adjusted to fit the text."""
        return self._scale_mode == SCALE_MODE_BOUNDS_TO_TEXT

    @scale_bounds_to_text.setter
    def scale_bounds_to_text(self, should_scale: bool) -> None:
        if should_scale:
            if self._scale_mode != SCALE_MODE_BOUNDS_TO_TEXT:
                self._scale_mode = SCALE_MODE_BOUNDS_TO_TEXT
                self._apply_auto_scale()
        else:
            if self._scale_mode == SCALE_MODE_BOUNDS_TO_TEXT:
                self._scale_mode = SCALE_MODE_NONE

    @property
    def scale_text_to_bounds(self) -> bool:
        """Returns whether text size is automatically adjusted to fit the bounds."""
        return self._scale_mode == SCALE_MODE_TEXT_TO_BOUNDS

    @scale_text_to_bounds.setter
    def scale_text_to_bounds(self, should_scale: bool) -> None:
        if should_scale:
            if self._scale_mode != SCALE_MODE_TEXT_TO_BOUNDS:
                self._scale_mode = SCALE_MODE_TEXT_TO_BOUNDS
                self._apply_auto_scale()
        else:
            if self._scale_mode == SCALE_MODE_TEXT_TO_BOUNDS:
                self._scale_mode = SCALE_MODE_NONE

    def _apply_auto_scale(self) -> None:
        if self._scale_mode == SCALE_MODE_BOUNDS_TO_TEXT:
            text = '  ' if len(self._text) == 0 else self._text
            self._size = find_text_size(text, self._font)
        elif self._scale_mode == SCALE_MODE_TEXT_TO_BOUNDS:
            if len(self._text) == 0:
                return
            max_pt_size = max_font_size(self._text, self._font, self._size, True)
            if max_pt_size > 0:
                self._font.setPointSize(max_pt_size)

    def render(self, painter: QPainter) -> None:
        """Renders the text into a painter."""
        painter.save()
        bounds = QRect(QPoint(), self._size)
        if self._fill_background:
            painter.fillRect(bounds, self._background_color)
        painter.setFont(self._font)
        painter.setPen(self._text_color)
        painter.setRenderHint(QPainter.RenderHint.LosslessImageRendering, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.drawText(bounds, self._text, self._text_alignment)
        painter.restore()

    def render_to_image(self) -> QImage:
        """Renders the text into a new image."""
        image_rect = QRect(QPoint(), self._size)
        if image_rect.isEmpty():
            return QImage()
        image = create_transparent_image(image_rect.size())
        painter = QPainter(image)
        self.render(painter)
        painter.end()
        return image
