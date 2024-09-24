"""QComboBox used to select between line drawing styles."""
import logging
from typing import Optional

from PySide6.QtCore import QSize, QPoint
from PySide6.QtGui import Qt, QPixmap, QPainter, QColor, QPen
from PySide6.QtWidgets import QApplication, QComboBox, QWidget

from src.config.cache import Cache
from src.util.shared_constants import ICON_SIZE, SMALL_ICON_SIZE

logger = logging.getLogger(__name__)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.input_fields.pen_style_combo_box'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


LINE_STYLE_SOLID = _tr('Solid')
LINE_STYLE_DASH = _tr('Dash')
LINE_STYLE_DOTTED = _tr('Dotted')
LINE_STYLE_DASH_DOT = _tr('Dash-dot')
LINE_STYLE_DASH_DOT_DOT = _tr('Dash-dot-dot')
LINE_STYLE_CUSTOM = _tr('Custom pattern')

ICON_LINE_WIDTH = 8


class PenStyleComboBox(QComboBox):
    """QComboBox used to select between line drawing styles."""

    _line_options = {
        LINE_STYLE_SOLID: Qt.PenStyle.SolidLine,
        LINE_STYLE_DASH: Qt.PenStyle.DashLine,
        LINE_STYLE_DOTTED: Qt.PenStyle.DotLine,
        LINE_STYLE_DASH_DOT: Qt.PenStyle.DashDotLine,
        LINE_STYLE_DASH_DOT_DOT: Qt.PenStyle.DashDotDotLine,
        LINE_STYLE_CUSTOM: Qt.PenStyle.CustomDashLine
    }

    @staticmethod
    def get_pen_style(name: str) -> Qt.PenStyle:
        """Get the pen style associated with a particular name."""
        return PenStyleComboBox._line_options[name]

    @staticmethod
    def _draw_icon(line_style: Qt.PenStyle, line_color: QColor | Qt.GlobalColor,
                   bg_color: Optional[QColor | Qt.GlobalColor] = None) -> QPixmap:
        if bg_color is None:
            bg_color = Qt.GlobalColor.white if line_color.lightness() < 128 else Qt.GlobalColor.black
        draw_icon_size = ICON_SIZE * 4
        icon = QPixmap(QSize(draw_icon_size, draw_icon_size))
        icon.fill(bg_color)
        painter = QPainter(icon)
        pen = QPen(line_color, ICON_LINE_WIDTH, line_style)
        if line_style == Qt.PenStyle.CustomDashLine:
            pen.setDashPattern([2, 2, 3, 2, 4, 2, 5, 2, 6, 2, 7, 2])
        painter.setPen(pen)
        line_points = []
        step_size = draw_icon_size // 6
        for step in range(step_size, step_size * 2 + 1, step_size):
            line_points += [
                QPoint(step, step),
                QPoint(draw_icon_size - step, step),
                QPoint(draw_icon_size - step, draw_icon_size - step),
                QPoint(step, draw_icon_size - step),
                QPoint(step, step + step_size)
            ]
        last_pt: Optional[QPoint] = None
        for point in line_points:
            if last_pt is None:
                last_pt = point
                continue
            painter.drawLine(last_pt, point)
            last_pt = point
        painter.end()
        return icon

    def __init__(self, cache_key: Optional[str] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setIconSize(QSize(SMALL_ICON_SIZE, SMALL_ICON_SIZE))

        for style_name, style in PenStyleComboBox._line_options.items():
            icon = PenStyleComboBox._draw_icon(style, Qt.GlobalColor.black, Qt.GlobalColor.white)
            self.addItem(icon, style_name, style)

        self.setCurrentText(LINE_STYLE_SOLID)

        if cache_key is None:
            return

        self.setToolTip(Cache().get_tooltip(cache_key))

        def _update_config(new_style_name: str) -> None:
            Cache().set(cache_key, new_style_name)
        self.currentTextChanged.connect(_update_config)

        def _update_from_config(new_style_name: str) -> None:
            if new_style_name in PenStyleComboBox._line_options and self.currentText() != new_style_name:
                self.setCurrentText(new_style_name)
        Cache().connect(self, cache_key, _update_from_config)
        _update_from_config(Cache().get(cache_key))

        def _apply_change_to_config(new_style_name: str) -> None:
            Cache().set(cache_key, new_style_name)
        self.currentTextChanged.connect(_apply_change_to_config)

    def set_icon_colors(self, color: QColor, bg_color: Optional[QColor | Qt.GlobalColor] = None) -> None:
        """Updates all icons with new colors."""
        for style_name, style in PenStyleComboBox._line_options.items():
            icon = PenStyleComboBox._draw_icon(style, color, bg_color)
            index = self.findText(style_name)
            self.setItemIcon(index, icon)

    def value(self) -> Qt.PenStyle:
        """Returns the selected line style."""
        selected_style = self.currentData()
        assert isinstance(selected_style, Qt.PenStyle)
        return selected_style

    def setValue(self, value: QPen | Qt.PenStyle) -> None:
        """Sets the current value from a pen or pen style."""
        if isinstance(value, QPen):
            value = value.style()
        for text, style in PenStyleComboBox._line_options.items():
            if style == value:
                self.setCurrentText(text)
                return
        raise ValueError(f'Pen style {value} not supported')
