"""A polygon outline used to represent selected image content."""
from typing import Optional

from PySide6.QtGui import QPolygonF, QColor, Qt
from PySide6.QtWidgets import QGraphicsView, QGraphicsItem

from src.config.application_config import AppConfig
from src.ui.graphics_items.polygon_outline import PolygonOutline


class SelectionOutline(PolygonOutline):
    """Displays polygon outlines as animated dashes with subtle color changes."""

    def __init__(self,
                 view: QGraphicsView,
                 polygons: Optional[list[QPolygonF]] = None,
                 parent: Optional[QGraphicsItem] = None):
        super().__init__(view, polygons, parent)

        config = AppConfig()
        self._show_overlay = True

        def _update_fill_color(color_str: str) -> None:
            if not QColor.isValidColor(color_str) or not self._show_overlay:
                return
            self.fill_color = QColor(color_str)

        config.connect(self, AppConfig.SELECTION_COLOR, _update_fill_color)
        _update_fill_color(config.get(AppConfig.SELECTION_COLOR))

        def _update_outline_animate(should_animate: bool) -> None:
            self.animated_outline = should_animate

        config.connect(self, AppConfig.ANIMATE_SELECTION_OUTLINE, _update_outline_animate)
        _update_outline_animate(config.get(AppConfig.ANIMATE_SELECTION_OUTLINE))

        def _update_fill_animate(should_animate: bool) -> None:
            self.animated_fill = should_animate

        config.connect(self, AppConfig.ANIMATE_SELECTION_FILL, _update_fill_animate)
        _update_fill_animate(config.get(AppConfig.ANIMATE_SELECTION_FILL))

    @property
    def show_overlay(self) -> bool:
        """Returns whether the outline should be filled with a non-transparent pattern."""
        return self._show_overlay

    @show_overlay.setter
    def show_overlay(self, should_show: bool) -> None:
        """Sets whether the outline should be filled with a non-transparent pattern."""
        if should_show == self._show_overlay:
            return
        if should_show:
            color = AppConfig().get_color(AppConfig.SELECTION_COLOR, Qt.GlobalColor.red)
        else:
            color = QColor(Qt.GlobalColor.transparent)
        self.fill_color = color
