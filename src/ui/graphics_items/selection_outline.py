"""A polygon outline used to represent selected image content."""
from typing import Optional

from PySide6.QtGui import QPolygonF, QColor, Qt
from PySide6.QtWidgets import QGraphicsView, QGraphicsItem

from src.config.application_config import AppConfig
from src.ui.graphics_items.polygon_outline import PolygonOutline


class SelectionOutline(PolygonOutline):
    """Displays polygon outlines as animated dashes with subtle color changes.

    The fill shows only while `show_overlay` and `AppConfig.SHOW_SELECTION_OVERLAY` are both set. Without it the
    outline still draws, and keeps animating if `AppConfig.ANIMATE_SELECTION_OUTLINE` is set.
    """

    def __init__(self,
                 view: QGraphicsView,
                 polygons: Optional[list[QPolygonF]] = None,
                 parent: Optional[QGraphicsItem] = None):
        super().__init__(view, polygons, parent)

        config = AppConfig()
        self._show_overlay = True
        self._overlay_enabled = config.get(AppConfig.SHOW_SELECTION_OVERLAY)
        self._animate_fill_setting = config.get(AppConfig.ANIMATE_SELECTION_FILL)

        config.connect(self, AppConfig.SELECTION_COLOR, lambda _: self._update_fill())

        def _update_outline_animate(should_animate: bool) -> None:
            self.animated_outline = should_animate

        config.connect(self, AppConfig.ANIMATE_SELECTION_OUTLINE, _update_outline_animate)
        _update_outline_animate(config.get(AppConfig.ANIMATE_SELECTION_OUTLINE))

        def _update_fill_animate(should_animate: bool) -> None:
            self._animate_fill_setting = should_animate
            self._update_fill()

        config.connect(self, AppConfig.ANIMATE_SELECTION_FILL, _update_fill_animate)

        def _update_overlay_enabled(enabled: bool) -> None:
            self._overlay_enabled = enabled
            self._update_fill()

        config.connect(self, AppConfig.SHOW_SELECTION_OVERLAY, _update_overlay_enabled)
        self._update_fill()

    @property
    def show_overlay(self) -> bool:
        """Returns whether this outline may be filled with a non-transparent pattern."""
        return self._show_overlay

    @show_overlay.setter
    def show_overlay(self, should_show: bool) -> None:
        """Sets whether this outline may be filled with a non-transparent pattern."""
        if should_show == self._show_overlay:
            return
        self._show_overlay = should_show
        self._update_fill()

    def _update_fill(self) -> None:
        """Applies the fill color and fill animation for the current overlay settings.

        A hidden fill stops animating, so the animation runs only for an animated outline.
        """
        fill_visible = self._show_overlay and self._overlay_enabled
        if fill_visible:
            color = AppConfig().get_color(AppConfig.SELECTION_COLOR, Qt.GlobalColor.red)
        else:
            color = QColor(Qt.GlobalColor.transparent)
        self.fill_color = color
        self.animated_fill = fill_visible and self._animate_fill_setting
