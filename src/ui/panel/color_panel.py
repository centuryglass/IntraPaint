"""The color picker as a panel that edits a config color, choosing its layout from its size and dock orientation."""
from typing import Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QResizeEvent

from src.config.cache import Cache
from src.config.config_from_key import get_config_from_key
from src.controller import color_controller
from src.ui.widget.color_pair_widget import ColorPairWidget
from src.ui.widget.color_picker.tabbed_color_picker import TabbedColorPicker, ColorPickerLayout

# Side panels at least this tall show every part in one column, and narrower than this use icon-only tabs.
SIDE_TALL_MIN_HEIGHT = 900
SIDE_TALL_MIN_WIDTH = 260
SIDE_COMPACT_MAX_WIDTH = 280
SIDE_COMPACT_MAX_HEIGHT = 500
# Bottom panels at least this wide show every part in four columns, and shorter than this use the short layout.
BOTTOM_WIDE_MIN_WIDTH = 1100
BOTTOM_WIDE_MIN_HEIGHT = 260
BOTTOM_SHORT_MAX_HEIGHT = 240

# The next layout to try when a layout's minimum size doesn't fit the panel. SIDE_COMPACT is the last resort.
FALLBACK_LAYOUTS = {
    ColorPickerLayout.BOTTOM_WIDE: ColorPickerLayout.BOTTOM_MEDIUM,
    ColorPickerLayout.BOTTOM_MEDIUM: ColorPickerLayout.BOTTOM_SHORT,
    ColorPickerLayout.BOTTOM_SHORT: ColorPickerLayout.SIDE_COMPACT,
    ColorPickerLayout.SIDE_TALL: ColorPickerLayout.SIDE,
    ColorPickerLayout.SIDE: ColorPickerLayout.SIDE_COMPACT,
}


def choose_layout(size: QSize, orientation: Optional[Qt.Orientation]) -> ColorPickerLayout:
    """Returns the preferred layout for a panel of a given size in a dock of a given orientation.

    A vertical orientation is a side dock and a horizontal one a top or bottom dock. With no orientation, the panel
    uses the side layouts. The panel falls back through `FALLBACK_LAYOUTS` when the preferred layout doesn't fit.
    """
    width, height = size.width(), size.height()
    if orientation == Qt.Orientation.Horizontal:
        if width >= BOTTOM_WIDE_MIN_WIDTH and height >= BOTTOM_WIDE_MIN_HEIGHT:
            return ColorPickerLayout.BOTTOM_WIDE
        if height < BOTTOM_SHORT_MAX_HEIGHT:
            return ColorPickerLayout.BOTTOM_SHORT
        return ColorPickerLayout.BOTTOM_MEDIUM
    if height >= SIDE_TALL_MIN_HEIGHT and width >= SIDE_TALL_MIN_WIDTH:
        return ColorPickerLayout.SIDE_TALL
    if width < SIDE_COMPACT_MAX_WIDTH or height < SIDE_COMPACT_MAX_HEIGHT:
        return ColorPickerLayout.SIDE_COMPACT
    return ColorPickerLayout.SIDE


class ColorControlPanel(TabbedColorPicker):
    """The color picker as a panel that edits a config color, choosing its layout from its size and dock orientation.

    The panel reports the smallest minimum size of any layout it could fall back to, whatever its current layout, so a
    dock or scroll area can always shrink it, and the resize then picks a layout that fits. That is the compact
    layout's size, with the short layout's height in a top or bottom dock.

    Committed colors go to `color_controller.commit_color`. A panel editing the foreground color shows the
    foreground/background color pair in its header.
    """

    def __init__(self, config_key: Optional[str] = 'last_brush_color') -> None:
        swatch_widget = ColorPairWidget() if config_key == Cache.LAST_BRUSH_COLOR else None
        super().__init__(swatch_widget)
        self._orientation: Optional[Qt.Orientation] = None
        self._config_key = config_key
        self.set_picker_layout(ColorPickerLayout.BOTTOM_SHORT)
        self._short_minimum = super().minimumSizeHint()
        self.set_picker_layout(ColorPickerLayout.SIDE_COMPACT)
        self._compact_minimum = super().minimumSizeHint()

        if config_key is not None:
            config = get_config_from_key(config_key)
            initial_color = config.get_color(config_key, Qt.GlobalColor.black)
            self.set_current_color(initial_color)
            config.connect(self, config_key, self._apply_config_color)
            self.color_selected.connect(self._update_config_color)
            self.color_committed.connect(color_controller.commit_color)

    def _apply_config_color(self, color_str: str) -> None:
        self.set_current_color(QColor(color_str))

    def set_orientation(self, orientation: Optional[Qt.Orientation]) -> None:
        """Sets the dock orientation, and updates the layout to match."""
        self._orientation = orientation
        self._update_layout()

    def minimumSizeHint(self) -> QSize:
        """Returns the smallest minimum size of the layouts the panel can fall back to."""
        if self.picker_layout() == ColorPickerLayout.SIDE_COMPACT:
            self._compact_minimum = super().minimumSizeHint()
        elif self.picker_layout() == ColorPickerLayout.BOTTOM_SHORT:
            self._short_minimum = super().minimumSizeHint()
        if self._orientation == Qt.Orientation.Horizontal:
            return QSize(self._compact_minimum.width(),
                         min(self._compact_minimum.height(), self._short_minimum.height()))
        return QSize(self._compact_minimum)

    def hasHeightForWidth(self) -> bool:
        """The panel picks a layout for the height it gets, so it doesn't ask for one through its swatch grids."""
        return False

    def heightForWidth(self, unused_width: int) -> int:
        """The panel has no height-for-width; see `hasHeightForWidth`."""
        return -1

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """Updates the layout to match the new size."""
        self._update_layout()
        super().resizeEvent(event)

    def _update_layout(self) -> None:
        """Uses the preferred layout for the panel's size, or the first fallback whose minimum size fits."""
        size = self.size()
        picker_layout = choose_layout(size, self._orientation)
        while True:
            self.set_picker_layout(picker_layout)
            minimum = super().minimumSizeHint()
            fits = minimum.width() <= size.width() and minimum.height() <= size.height()
            if fits or picker_layout not in FALLBACK_LAYOUTS:
                break
            picker_layout = FALLBACK_LAYOUTS[picker_layout]

    def _update_config_color(self, color: QColor) -> None:
        if self._config_key is not None:
            config = get_config_from_key(self._config_key)
            config.set_color(self._config_key, color)
