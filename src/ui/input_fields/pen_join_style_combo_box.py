"""QComboBox used to select between line join drawing styles."""
from typing import Optional

from PySide6.QtCore import Signal, QSize
from PySide6.QtGui import Qt, QPixmap, QPainter, QColor, QPen, QTransform
from PySide6.QtWidgets import QApplication, QComboBox, QWidget

from src.config.cache import Cache
from src.util.shared_constants import ICON_SIZE, SMALL_ICON_SIZE

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.input_fields.pen_join_style_combo_box'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


JOIN_STYLE_ROUND = _tr('Round')
JOIN_STYLE_BEVEL = _tr('Bevel')
JOIN_STYLE_MITER = _tr('Miter')

ICON_LINE_WIDTH = 64


class PenJoinStyleComboBox(QComboBox):
    """QComboBox used to select between line drawing styles."""

    valueChanged = Signal(Qt.PenStyle)

    _line_options = {
        JOIN_STYLE_ROUND: Qt.PenJoinStyle.RoundJoin,
        JOIN_STYLE_BEVEL: Qt.PenJoinStyle.BevelJoin,
        JOIN_STYLE_MITER: Qt.PenJoinStyle.MiterJoin
    }

    @staticmethod
    def get_join_style(name: str) -> Qt.PenJoinStyle:
        """Get the pen join style associated with a particular name."""
        return PenJoinStyleComboBox._line_options[name]

    @staticmethod
    def _draw_icon(join_style: Qt.PenJoinStyle, line_color: QColor | Qt.GlobalColor,
                   bg_color: Optional[QColor | Qt.GlobalColor] = None) -> QPixmap:
        if bg_color is None:
            bg_color = Qt.GlobalColor.white if line_color.lightness() < 128 else Qt.GlobalColor.black
        draw_icon_size = ICON_SIZE * 4
        icon = QPixmap(QSize(draw_icon_size, draw_icon_size))
        icon.fill(bg_color)
        painter = QPainter(icon)
        pen = QPen(line_color, ICON_LINE_WIDTH, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, join_style)
        painter.setPen(pen)
        transform = QTransform().rotate(45.0) * QTransform.fromTranslate(draw_icon_size // 2, draw_icon_size // 2)
        painter.setTransform(transform)
        painter.drawRect(0, 0, draw_icon_size, draw_icon_size)
        painter.end()
        return icon

    def __init__(self, cache_key: Optional[str] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setIconSize(QSize(SMALL_ICON_SIZE, SMALL_ICON_SIZE))

        for style_name, style in PenJoinStyleComboBox._line_options.items():
            icon = PenJoinStyleComboBox._draw_icon(style, Qt.GlobalColor.black, Qt.GlobalColor.white)
            self.addItem(icon, style_name, style)

        self.setCurrentText(JOIN_STYLE_ROUND)

        if cache_key is None:
            return

        self.setToolTip(Cache().get_tooltip(cache_key))

        def _update_config(new_style_name: str) -> None:
            Cache().set(cache_key, new_style_name)
        self.currentTextChanged.connect(_update_config)

        def _update_from_config(new_style_name: str) -> None:
            if new_style_name in PenJoinStyleComboBox._line_options and self.currentText() != new_style_name:
                self.setCurrentText(new_style_name)
        Cache().connect(self, cache_key, _update_from_config)
        _update_from_config(Cache().get(cache_key))

        def _apply_change_to_config(new_style_name: str) -> None:
            Cache().set(cache_key, new_style_name)
        self.currentTextChanged.connect(_apply_change_to_config)

    def set_icon_colors(self, color: QColor, bg_color: Optional[QColor | Qt.GlobalColor] = None) -> None:
        """Updates all icons with new colors."""
        for style_name, style in PenJoinStyleComboBox._line_options.items():
            icon = PenJoinStyleComboBox._draw_icon(style, color, bg_color)
            index = self.findText(style_name)
            self.setItemIcon(index, icon)

    def value(self) -> Qt.PenJoinStyle:
        """Returns the selected line join style."""
        selected_style = self.currentData()
        assert isinstance(selected_style, Qt.PenJoinStyle)
        return selected_style

    def setValue(self, value: QPen | Qt.PenJoinStyle) -> None:
        """Sets the current value from a pen or pen style."""
        if isinstance(value, QPen):
            value = value.joinStyle()
        for text, style in PenJoinStyleComboBox._line_options.items():
            if style == value:
                self.setCurrentText(text)
                return
        raise ValueError(f'Pen join style {value} not supported')
