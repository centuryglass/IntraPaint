"""The color picker as a panel that edits a config color, choosing its layout from its size and dock orientation."""
from typing import Optional

from PySide6.QtCore import Qt, QEvent, QSize
from PySide6.QtGui import QColor, QResizeEvent
from PySide6.QtWidgets import QWidget

from src.config.cache import Cache
from src.config.config_from_key import get_config_from_key
from src.controller import color_controller
from src.ui.layout.panel_fit import Orientation
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

# The most times one resize re-chooses the layout because switching layouts changed the panel's size.
MAX_LAYOUT_PASSES = 3

# The next layout to try when a layout's minimum size doesn't fit the panel. A size no layout fits gets the last-resort
# layout for the panel's orientation (`ColorControlPanel._last_resort_layout`).
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


def _qt_orientation(orientation: Orientation) -> Qt.Orientation:
    """Returns the dock orientation a `FitContent` orientation corresponds to: vertical for a side panel."""
    return Qt.Orientation.Vertical if orientation == Orientation.SIDE else Qt.Orientation.Horizontal


class ColorControlPanel(TabbedColorPicker):
    """The color picker as a panel that edits a config color, choosing its layout from its size and dock orientation.

    The panel reports the minimum size of its last-resort layout for its orientation: `SIDE_COMPACT` in a side dock,
    `BOTTOM_SHORT` in a top or bottom dock. Every size at or above that has a layout that fits, and the minimum is the
    same whichever layout is showing. A dock or scroll area that honors it never squeezes the picker.

    The panel is a `src.ui.layout.panel_fit.FitContent`. A dock reports its orientation through `set_orientation` and
    the panel plans for its own size. The Tools panel reports an orientation and the space it gives the panel through
    `set_fit_space`. The panel plans for that space. Where no layout fits it, the panel shows its last-resort layout
    and the Tools panel scrolls.

    Committed colors go to `color_controller.commit_color`. A panel editing the foreground color shows the
    foreground/background color pair in its header.
    """

    def __init__(self, config_key: Optional[str] = 'last_brush_color') -> None:
        swatch_widget = ColorPairWidget() if config_key == Cache.LAST_BRUSH_COLOR else None
        super().__init__(swatch_widget)
        self._orientation: Optional[Qt.Orientation] = None
        # The space a `FitContent` host gave the panel, or None while the panel plans for its own size:
        self._space: Optional[QSize] = None
        self._updating_layout = False
        self._config_key = config_key
        # No control is optional, so nothing ever goes in the host's More popover:
        self._overflow = QWidget()
        # Measured now so `minimumSizeHint` never has to switch layouts during a host's layout pass:
        self.layout_minimum(ColorPickerLayout.BOTTOM_SHORT)
        self.layout_minimum(ColorPickerLayout.SIDE_COMPACT)
        self.set_picker_layout(self._last_resort_layout())

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
        self.updateGeometry()
        self._update_layout()

    def fit_base_size(self, orientation: Orientation) -> QSize:
        """Returns the minimum size of the last-resort layout for the orientation, and shows that layout until the next
        `set_fit_space`."""
        self._orientation = _qt_orientation(orientation)
        self.set_picker_layout(self._last_resort_layout())
        return self.minimumSizeHint()

    def set_fit_space(self, orientation: Orientation, size: QSize) -> None:
        """Chooses the layout for the space the host gives the panel."""
        self._orientation = _qt_orientation(orientation)
        self._space = QSize(size)
        self.updateGeometry()
        self._update_layout()

    def overflow_content(self) -> QWidget:
        """Returns the widget for controls the panel leaves out, which is always empty."""
        return self._overflow

    def minimumSizeHint(self) -> QSize:
        """Returns the minimum size of the last-resort layout for the panel's orientation."""
        return self.layout_minimum(self._last_resort_layout())

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

    def event(self, event: Optional[QEvent]) -> bool:
        """Goes back to planning for its own size when the panel moves to a new parent, since the old host's space no
        longer applies."""
        if event is not None and event.type() == QEvent.Type.ParentChange:
            self._space = None
        return super().event(event)

    def _last_resort_layout(self) -> ColorPickerLayout:
        """Returns the layout that fits the smallest size the panel can be given."""
        return ColorPickerLayout.BOTTOM_SHORT if self._orientation == Qt.Orientation.Horizontal \
            else ColorPickerLayout.SIDE_COMPACT

    def _update_layout(self) -> None:
        """Uses the preferred layout for the panel's size, or the first fallback whose minimum size fits.

        A size that no layout fits gets the last-resort layout. Switching layouts can resize the panel through its dock.
        A resize during a switch is ignored, and the layout is chosen again afterwards for the size the panel ended up
        with.
        """
        if self._updating_layout or self.measuring:
            return
        self._updating_layout = True
        try:
            for _ in range(MAX_LAYOUT_PASSES):
                size = self.size() if self._space is None else self._space
                picker_layout = choose_layout(size, self._orientation)
                while True:
                    minimum = self.layout_minimum(picker_layout)
                    if minimum.width() <= size.width() and minimum.height() <= size.height():
                        break
                    if picker_layout not in FALLBACK_LAYOUTS:
                        picker_layout = self._last_resort_layout()
                        break
                    picker_layout = FALLBACK_LAYOUTS[picker_layout]
                self.set_picker_layout(picker_layout)
                if self._space is not None or self.size() == size:
                    break
        finally:
            self._updating_layout = False

    def _update_config_color(self, color: QColor) -> None:
        if self._config_key is not None:
            config = get_config_from_key(self._config_key)
            config.set_color(self._config_key, color)
