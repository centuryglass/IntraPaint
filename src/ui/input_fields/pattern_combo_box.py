"""QComboBox used to select between brush/fill patterns"""
import logging
from typing import Optional

from PySide6.QtCore import Signal, QSize, QRect
from PySide6.QtGui import QBrush, Qt, QPixmap, QPainter, QColor
from PySide6.QtWidgets import QApplication, QComboBox

from src.config.cache import Cache
from src.util.shared_constants import ICON_SIZE

logger = logging.getLogger(__name__)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.input_fields.pattern_combo_box'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


BRUSH_PATTERN_SOLID = _tr('Solid')
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


class PatternComboBox(QComboBox):
    """QComboBox used to select between brush/fill patterns"""

    valueChanged = Signal(QBrush)

    _brush_options = {
        BRUSH_PATTERN_SOLID: QBrush(Qt.BrushStyle.SolidPattern),
        BRUSH_PATTERN_DENSE_1: QBrush(Qt.BrushStyle.Dense1Pattern),
        BRUSH_PATTERN_DENSE_2: QBrush(Qt.BrushStyle.Dense2Pattern),
        BRUSH_PATTERN_DENSE_3: QBrush(Qt.BrushStyle.Dense3Pattern),
        BRUSH_PATTERN_DENSE_4: QBrush(Qt.BrushStyle.Dense4Pattern),
        BRUSH_PATTERN_DENSE_5: QBrush(Qt.BrushStyle.Dense5Pattern),
        BRUSH_PATTERN_DENSE_6: QBrush(Qt.BrushStyle.Dense6Pattern),
        BRUSH_PATTERN_DENSE_7: QBrush(Qt.BrushStyle.Dense7Pattern),
        BRUSH_PATTERN_HORIZONTAL: QBrush(Qt.BrushStyle.HorPattern),
        BRUSH_PATTERN_VERTICAL: QBrush(Qt.BrushStyle.VerPattern),
        BRUSH_PATTERN_CROSSED: QBrush(Qt.BrushStyle.CrossPattern),
        BRUSH_PATTERN_DIAGONAL_1: QBrush(Qt.BrushStyle.BDiagPattern),
        BRUSH_PATTERN_DIAGONAL_2: QBrush(Qt.BrushStyle.FDiagPattern),
        BRUSH_PATTERN_DIAGONAL_CROSSED: QBrush(Qt.BrushStyle.DiagCrossPattern)
    }

    @staticmethod
    def get_brush(name: str) -> QBrush:
        """Get the brush associated with a particular name."""
        return QBrush(PatternComboBox._brush_options[name])

    def __init__(self, cache_key: Optional[str] = None):
        super().__init__()

        for brush_name, brush in PatternComboBox._brush_options.items():
            icon = PatternComboBox._draw_icon(brush, Qt.GlobalColor.white)
            self.addItem(icon, brush_name, brush)

        self.setCurrentText(BRUSH_PATTERN_SOLID)

        def _brush_change(idx: int) -> None:
            selected_brush = self.itemData(idx)
            assert isinstance(selected_brush, QBrush)
            self.valueChanged.emit(selected_brush)
        self.currentIndexChanged.connect(_brush_change)

        if cache_key is None:
            return

        def _update_config(new_brush_name: str) -> None:
            Cache().set(cache_key, new_brush_name)
        self.currentTextChanged.connect(_update_config)

        def _update_from_config(new_pattern_name: str) -> None:
            if new_pattern_name in PatternComboBox._brush_options and self.currentText() != new_pattern_name:
                self.setCurrentText(new_pattern_name)
        Cache().connect(self, cache_key, _update_from_config)
        _update_from_config(Cache().get(cache_key))

        def _apply_change_to_config(new_pattern_name: str) -> None:
            Cache().set(cache_key, new_pattern_name)
        self.currentTextChanged.connect(_apply_change_to_config)

    @staticmethod
    def _draw_icon(brush: QBrush, bg_color: QColor | Qt.GlobalColor) -> QPixmap:
        icon = QPixmap(QSize(ICON_SIZE, ICON_SIZE))
        icon.fill(bg_color)
        painter = QPainter(icon)
        painter.drawRect(QRect(0, 0, ICON_SIZE - 1, ICON_SIZE - 1))
        painter.fillRect(QRect(0, 0, ICON_SIZE, ICON_SIZE), brush)
        painter.end()
        return icon

    def set_icon_colors(self, color: QColor) -> None:
        """Updates all icons with a new color."""
        bg_color = Qt.GlobalColor.white if color.lightness() < 128 else Qt.GlobalColor.black
        for brush_name, brush in PatternComboBox._brush_options.items():
            brush = QBrush(color, brush.style())
            icon = PatternComboBox._draw_icon(brush, bg_color)
            index = self.findText(brush_name)
            self.setItemIcon(index, icon)

    def value(self) -> QBrush:
        """Returns the selected brush value."""
        selected_brush = self.currentData()
        assert isinstance(selected_brush, QBrush)
        return selected_brush

    def setValue(self, value: QBrush | Qt.BrushStyle) -> None:
        """Sets the current value from a brush or brush style."""
        if isinstance(value, QBrush):
            value = value.style()
        for text, brush in PatternComboBox._brush_options.items():
            if brush.style() == value:
                self.setCurrentText(text)
                return
        raise ValueError(f'Brush style {value} not supported')

