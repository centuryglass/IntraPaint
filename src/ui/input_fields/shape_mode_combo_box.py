"""QComboBox used to select between shape types."""
from typing import Optional

from PySide6.QtCore import QSize, QPoint, QRect
from PySide6.QtGui import Qt, QPixmap, QPainter, QColor, QPen, QBrush, QIcon
from PySide6.QtWidgets import QComboBox, QWidget

from src.config.cache import Cache
from src.util.shared_constants import ICON_SIZE, SMALL_ICON_SIZE
from src.util.visual.shape_mode import ShapeMode


class ShapeModeComboBox(QComboBox):
    """QComboBox used to select between shape types."""

    @staticmethod
    def draw_icon(shape_mode: ShapeMode, line_pen: QPen, fill_brush: QBrush, vertex_count=3,
                  inner_radius_fraction=0.5, bg_color: Optional[QColor | Qt.GlobalColor] = None) -> QIcon:
        """Draw the icon for a ShapeMode, using the given pen, brush, polygon parameters, and background color."""
        drawn_icon_size = ICON_SIZE * 4
        pixmap = QPixmap(QSize(drawn_icon_size, drawn_icon_size))
        if line_pen.width() > 0 and line_pen.color().alpha() > 100:
            contrast_color = line_pen.color()
        else:
            contrast_color = fill_brush.color()
        if bg_color is None:
            bg_color = Qt.GlobalColor.white if contrast_color.lightness() < 128 else Qt.GlobalColor.black

        pixmap.fill(bg_color)

        # Draw the appropriate shape:
        bounds = QRect(QPoint(), QSize(drawn_icon_size, drawn_icon_size)).adjusted(8, 8, -8, -8)
        radius = (drawn_icon_size // 2) - 8
        inner_radius = round(inner_radius_fraction * radius)
        painter = QPainter(pixmap)
        painter.setPen(line_pen)
        path = shape_mode.painter_path(bounds, radius, vertex_count, inner_radius)
        painter.fillPath(path, fill_brush)
        painter.drawPath(path)
        painter.end()
        return QIcon(pixmap)

    def __init__(self, cache_key: Optional[str] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setIconSize(QSize(SMALL_ICON_SIZE, SMALL_ICON_SIZE))

        for mode in ShapeMode:
            mode_name = mode.display_text()
            icon = ShapeModeComboBox.draw_icon(mode, QPen(Qt.GlobalColor.black), QBrush(Qt.GlobalColor.white))
            self.addItem(icon, mode_name, mode)

        self.setCurrentText(ShapeMode.ELLIPSE.display_text())

        if cache_key is None:
            return

        self.setToolTip(Cache().get_tooltip(cache_key))

        def _update_config(new_mode_name: str) -> None:
            Cache().set(cache_key, new_mode_name)
        self.currentTextChanged.connect(_update_config)

        def _update_from_config(new_mode_name: str) -> None:
            if ShapeMode.is_valid_mode_str(new_mode_name) and self.currentText() != new_mode_name:
                self.setCurrentText(new_mode_name)
        Cache().connect(self, cache_key, _update_from_config)
        _update_from_config(Cache().get(cache_key))

        def _apply_change_to_config(new_style_name: str) -> None:
            Cache().set(cache_key, new_style_name)
        self.currentTextChanged.connect(_apply_change_to_config)

    def update_icon_style(self, line_pen: QPen, fill_brush: QBrush, vertex_count=3, inner_radius_fraction=0.5) -> None:
        """Updates all icons with new outline and fill styles."""
        for mode in ShapeMode:
            icon = ShapeModeComboBox.draw_icon(mode, line_pen, fill_brush, vertex_count, inner_radius_fraction)
            index = self.findText(mode.display_text())
            self.setItemIcon(index, icon)

    def value(self) -> ShapeMode:
        """Returns the selected shape mode."""
        selected_mode = self.currentData()
        assert isinstance(selected_mode, ShapeMode)
        return selected_mode

    def setValue(self, value: ShapeMode) -> None:
        """Sets the current selected shape mode."""
        mode_name = value.display_text()
        self.setCurrentText(mode_name)
