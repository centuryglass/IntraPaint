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


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


LINE_STYLE_SOLID = 'Solid'
LINE_STYLE_DASH = 'Dash'
LINE_STYLE_DOTTED = 'Dotted'
LINE_STYLE_DASH_DOT = 'Dash-dot'
LINE_STYLE_DASH_DOT_DOT = 'Dash-dot-dot'
LINE_STYLE_CUSTOM = 'Custom pattern'

# Translated item text for each option name. The option names are what `Cache` stores.
_LINE_LABELS = {
    LINE_STYLE_SOLID: _tr('Solid'),
    LINE_STYLE_DASH: _tr('Dash'),
    LINE_STYLE_DOTTED: _tr('Dotted'),
    LINE_STYLE_DASH_DOT: _tr('Dash-dot'),
    LINE_STYLE_DASH_DOT_DOT: _tr('Dash-dot-dot'),
    LINE_STYLE_CUSTOM: _tr('Custom pattern'),
}

# Item data role holding the untranslated option name that is saved in `Cache`; the item text is its translation.
KEY_ROLE = Qt.ItemDataRole.UserRole + 1

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
        """Get the pen style associated with an untranslated option name (the `LINE_STYLE_*` constants)."""
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
            self.addItem(icon, _LINE_LABELS[style_name], style)
            self.setItemData(self.count() - 1, style_name, KEY_ROLE)

        self.set_option(LINE_STYLE_SOLID)

        if cache_key is None:
            return

        self.setToolTip(Cache().get_tooltip(cache_key))

        def _update_config(_: int) -> None:
            Cache().set(cache_key, self.option())
        self.currentIndexChanged.connect(_update_config)

        def _update_from_config(new_style_name: str) -> None:
            if new_style_name in PenStyleComboBox._line_options and self.option() != new_style_name:
                self.set_option(new_style_name)
        Cache().connect(self, cache_key, _update_from_config)
        _update_from_config(Cache().get(cache_key))

    def option(self) -> str:
        """Returns the untranslated name of the selected option."""
        return str(self.currentData(KEY_ROLE))

    def set_option(self, style_name: str) -> None:
        """Selects an option by its untranslated name."""
        index = self.findData(style_name, KEY_ROLE)
        if index < 0:
            raise ValueError(f'Unknown line style {style_name}')
        self.setCurrentIndex(index)

    def set_icon_colors(self, color: QColor, bg_color: Optional[QColor | Qt.GlobalColor] = None) -> None:
        """Updates all icons with new colors."""
        for style_name, style in PenStyleComboBox._line_options.items():
            icon = PenStyleComboBox._draw_icon(style, color, bg_color)
            index = self.findData(style_name, KEY_ROLE)
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
                self.set_option(text)
                return
        raise ValueError(f'Pen style {value} not supported')
