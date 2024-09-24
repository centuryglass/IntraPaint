"""QComboBox used to select between brush/fill patterns"""
from typing import Optional

from PySide6.QtCore import QSize, QRect
from PySide6.QtGui import QBrush, Qt, QPixmap, QPainter, QColor
from PySide6.QtWidgets import QApplication, QComboBox, QWidget

from src.config.cache import Cache
from src.util.shared_constants import ICON_SIZE, SMALL_ICON_SIZE

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.input_fields.fill_style_combo_box'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


BRUSH_PATTERN_SOLID = _tr('Solid')
BRUSH_PATTERN_NONE = _tr('None')
BRUSH_PATTERN_DENSE_1 = _tr('Dithered, 94%')
BRUSH_PATTERN_DENSE_2 = _tr('Dithered, 88%')
BRUSH_PATTERN_DENSE_3 = _tr('Dithered, 62%')
BRUSH_PATTERN_DENSE_4 = _tr('Dithered, 50%')
BRUSH_PATTERN_DENSE_5 = _tr('Dithered, 38%')
BRUSH_PATTERN_DENSE_6 = _tr('Dithered, 12%')
BRUSH_PATTERN_DENSE_7 = _tr('Dithered, 6%')
BRUSH_PATTERN_HORIZONTAL = _tr('Horizontal lines')
BRUSH_PATTERN_VERTICAL = _tr('Vertical lines')
BRUSH_PATTERN_CROSSED = _tr('Crossed lines')
BRUSH_PATTERN_DIAGONAL_1 = _tr('Diagonal lines 1')
BRUSH_PATTERN_DIAGONAL_2 = _tr('Diagonal lines 2')
BRUSH_PATTERN_DIAGONAL_CROSSED = _tr('Diagonal crossed lines')


class FillStyleComboBox(QComboBox):
    """QComboBox used to select between brush/fill patterns"""

    _brush_styles = {
        BRUSH_PATTERN_SOLID: Qt.BrushStyle.SolidPattern,
        BRUSH_PATTERN_NONE: Qt.BrushStyle.NoBrush,
        BRUSH_PATTERN_DENSE_1: Qt.BrushStyle.Dense1Pattern,
        BRUSH_PATTERN_DENSE_2: Qt.BrushStyle.Dense2Pattern,
        BRUSH_PATTERN_DENSE_3: Qt.BrushStyle.Dense3Pattern,
        BRUSH_PATTERN_DENSE_4: Qt.BrushStyle.Dense4Pattern,
        BRUSH_PATTERN_DENSE_5: Qt.BrushStyle.Dense5Pattern,
        BRUSH_PATTERN_DENSE_6: Qt.BrushStyle.Dense6Pattern,
        BRUSH_PATTERN_DENSE_7: Qt.BrushStyle.Dense7Pattern,
        BRUSH_PATTERN_HORIZONTAL: Qt.BrushStyle.HorPattern,
        BRUSH_PATTERN_VERTICAL: Qt.BrushStyle.VerPattern,
        BRUSH_PATTERN_CROSSED: Qt.BrushStyle.CrossPattern,
        BRUSH_PATTERN_DIAGONAL_1: Qt.BrushStyle.BDiagPattern,
        BRUSH_PATTERN_DIAGONAL_2: Qt.BrushStyle.FDiagPattern,
        BRUSH_PATTERN_DIAGONAL_CROSSED: Qt.BrushStyle.DiagCrossPattern
    }

    @staticmethod
    def get_style(name: str) -> Qt.BrushStyle:
        """Returns the brush style associated with a particular name."""
        return FillStyleComboBox._brush_styles[name]

    def __init__(self, cache_key: Optional[str] = None, include_no_fill_option=False,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setIconSize(QSize(SMALL_ICON_SIZE, SMALL_ICON_SIZE))

        for brush_name, brush_style in FillStyleComboBox._brush_styles.items():
            if brush_name == BRUSH_PATTERN_NONE and not include_no_fill_option:
                continue
            icon = FillStyleComboBox._draw_icon(brush_style, Qt.GlobalColor.black, Qt.GlobalColor.white)
            self.addItem(icon, brush_name, brush_style)

        self.setCurrentText(BRUSH_PATTERN_SOLID)

        if cache_key is None:
            return
        self.setToolTip(Cache().get_tooltip(cache_key))

        def _update_config(new_brush_name: str) -> None:
            Cache().set(cache_key, new_brush_name)
        self.currentTextChanged.connect(_update_config)

        def _update_from_config(new_pattern_name: str) -> None:
            if new_pattern_name in FillStyleComboBox._brush_styles and self.currentText() != new_pattern_name:
                self.setCurrentText(new_pattern_name)
        Cache().connect(self, cache_key, _update_from_config)
        _update_from_config(Cache().get(cache_key))

        def _apply_change_to_config(new_pattern_name: str) -> None:
            Cache().set(cache_key, new_pattern_name)
        self.currentTextChanged.connect(_apply_change_to_config)

    @staticmethod
    def _draw_icon(brush_style: Qt.BrushStyle, color: QColor | Qt.GlobalColor,
                   bg_color: QColor | Qt.GlobalColor) -> QPixmap:
        icon = QPixmap(QSize(ICON_SIZE, ICON_SIZE))
        icon.fill(bg_color)
        painter = QPainter(icon)
        painter.drawRect(QRect(0, 0, ICON_SIZE - 1, ICON_SIZE - 1))
        brush = QBrush(brush_style)
        brush.setColor(color)
        painter.fillRect(QRect(0, 0, ICON_SIZE, ICON_SIZE), brush)
        painter.end()
        return icon

    def set_icon_colors(self, color: QColor) -> None:
        """Updates all icons with a new color."""
        bg_color = Qt.GlobalColor.white if color.lightness() < 128 else Qt.GlobalColor.black
        for brush_name, brush_style in FillStyleComboBox._brush_styles.items():
            icon = FillStyleComboBox._draw_icon(brush_style, color, bg_color)
            index = self.findText(brush_name)
            self.setItemIcon(index, icon)

    def value(self) -> Qt.BrushStyle:
        """Returns the selected brush value."""
        selected_style = self.currentData()
        assert isinstance(selected_style, Qt.BrushStyle)
        return selected_style

    def setValue(self, value: Qt.BrushStyle) -> None:
        """Sets the current value from a brush or brush style."""
        for text, brush in FillStyleComboBox._brush_styles.items():
            if brush.style() == value:
                self.setCurrentText(text)
                return
        raise ValueError(f'Brush style {value} not supported')
