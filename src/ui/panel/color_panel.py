"""Rearranges the Qt color dialog into a fixed panel widget."""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QResizeEvent, QShowEvent

from src.config.cache import Cache
from src.ui.widget.color_pick.tabbed_color_picker import TabbedColorPicker
from src.util.display_size import get_window_size


class ColorControlPanel(TabbedColorPicker):
    """Rearranges the Qt color dialog into a fixed panel widget."""

    def __init__(self, config_key: Optional[str] = 'last_brush_color', disable_extended_layouts=False) -> None:
        super().__init__()
        self._orientation: Optional[Qt.Orientation] = Qt.Orientation.Horizontal
        self._config_key = config_key
        self._disable_extended_layouts = disable_extended_layouts
        self.layout().setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        if config_key is not None:
            cache = Cache()
            initial_color = QColor(cache.get(Cache.LAST_BRUSH_COLOR))
            self.setCurrentColor(initial_color)
            cache.connect(self, Cache.LAST_BRUSH_COLOR, self._apply_config_color)
            self.currentColorChanged.connect(self._update_config_color)

    def _apply_config_color(self, color_str: str) -> None:
        self.setCurrentColor(QColor(color_str))

    def set_orientation(self, orientation: Optional[Qt.Orientation]):
        """Update the panel layout based on window size and requested orientation."""
        self._orientation = orientation
        if orientation is None:
            return
        self.set_default_mode()
        return
        window_size = get_window_size()
        panel_size = self.panel_size()
        if orientation == Qt.Orientation.Vertical:
            if not self._disable_extended_layouts and window_size.height() > panel_size.height() * 6:
                self.set_vertical_mode()
            elif not self._disable_extended_layouts and window_size.height() > panel_size.height() * 4:
                self.set_vertical_two_tab_mode()
            else:
                self.set_four_tab_mode()
        elif orientation == Qt.Orientation.Horizontal:
            if not self._disable_extended_layouts and window_size.width() > panel_size.width() * 6:
                self.set_horizontal_mode()
            elif window_size.width() > panel_size.width() * 4:
                self.set_horizontal_two_tab_mode()
            else:
                self.set_four_tab_mode()

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """Re-apply layout on size change."""
        self.set_orientation(self._orientation)

    def showEvent(self, event: Optional[QShowEvent]) -> None:
        """Re-apply layout whenever the panel is shown."""
        self.set_orientation(self._orientation)

    def _update_config_color(self, color: QColor) -> None:
        if self._config_key is not None:
            cache = Cache()
            cache.set(self._config_key, color.name(QColor.NameFormat.HexArgb))