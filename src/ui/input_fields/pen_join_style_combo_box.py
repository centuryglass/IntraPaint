"""QComboBox used to select between line join drawing styles."""
from typing import Optional

from PySide6.QtCore import Signal, QSize
from PySide6.QtGui import Qt, QPixmap, QPainter, QColor, QPen, QTransform
from PySide6.QtWidgets import QApplication, QComboBox, QWidget

from src.config.cache import Cache
from src.util.shared_constants import ICON_SIZE, SMALL_ICON_SIZE

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.input_fields.pen_join_style_combo_box'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


JOIN_STYLE_ROUND = 'Round'
JOIN_STYLE_BEVEL = 'Bevel'
JOIN_STYLE_MITER = 'Miter'

# Translated item text for each option name. The option names are what `Cache` stores.
JOIN_STYLE_LABELS = {
    JOIN_STYLE_ROUND: _tr('Round'),
    JOIN_STYLE_BEVEL: _tr('Bevel'),
    JOIN_STYLE_MITER: _tr('Miter'),
}

# Item data role holding the untranslated option name that is saved in `Cache`; the item text is its translation.
KEY_ROLE = Qt.ItemDataRole.UserRole + 1

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
        """Get the pen join style associated with an untranslated option name (the `JOIN_STYLE_*` constants)."""
        return PenJoinStyleComboBox._line_options[name]

    @staticmethod
    def draw_icon(join_style: Qt.PenJoinStyle, line_color: QColor | Qt.GlobalColor,
                  bg_color: Optional[QColor | Qt.GlobalColor] = None) -> QPixmap:
        """Draws the icon for a join style: a thick corner in the line color, over a contrasting background by
        default."""
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
            icon = PenJoinStyleComboBox.draw_icon(style, Qt.GlobalColor.black, Qt.GlobalColor.white)
            self.addItem(icon, JOIN_STYLE_LABELS[style_name], style)
            self.setItemData(self.count() - 1, style_name, KEY_ROLE)

        self.set_option(JOIN_STYLE_ROUND)

        if cache_key is None:
            return

        self.setToolTip(Cache().get_tooltip(cache_key))

        def _update_config(_: int) -> None:
            Cache().set(cache_key, self.option())
        self.currentIndexChanged.connect(_update_config)

        def _update_from_config(new_style_name: str) -> None:
            if new_style_name in PenJoinStyleComboBox._line_options and self.option() != new_style_name:
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
            raise ValueError(f'Unknown join style {style_name}')
        self.setCurrentIndex(index)

    def set_icon_colors(self, color: QColor, bg_color: Optional[QColor | Qt.GlobalColor] = None) -> None:
        """Updates all icons with new colors."""
        for style_name, style in PenJoinStyleComboBox._line_options.items():
            icon = PenJoinStyleComboBox.draw_icon(style, color, bg_color)
            index = self.findData(style_name, KEY_ROLE)
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
                self.set_option(text)
                return
        raise ValueError(f'Pen join style {value} not supported')
