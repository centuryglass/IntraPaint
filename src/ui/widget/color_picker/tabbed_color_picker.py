"""The color picker: a header, an OKHSV ring + square, gradient sliders, saved and recent colors, and alpha + hex.

`ColorPickerLayout` arranges the parts, in tabs where space is short. Every part edits one color. `color_selected` fires
on every change, and `color_committed` only on a finished choice: a mouse release, a swatch click, a hex entry or a
screen pick. Callers record committed colors as recent colors (see `src.controller.color_controller`).
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QBoxLayout, QTabWidget, QApplication

from src.ui.layout.panel_fit import fresh_minimum_size
from src.ui.widget.color_picker import tab_icons
from src.ui.widget.color_picker.alpha_hex_row import AlphaHexRow
from src.ui.widget.color_picker.color_picker_header import ColorPickerHeader
from src.ui.widget.color_picker.color_slider_block import ColorSliderBlock
from src.ui.widget.color_picker.okhsv_ring_square import OkhsvRingSquare
from src.ui.widget.color_picker.saved_colors_panel import SavedColorsPanel, RecentColorsRow
from src.ui.widget.color_picker.screen_color import ScreenColorWidget

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.widget.color_picker'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


WHEEL_TAB_TITLE = _tr('&Wheel')
# noinspection SpellCheckingInspection
SLIDERS_TAB_TITLE = _tr('Sl&iders')
# noinspection SpellCheckingInspection
PALETTES_TAB_TITLE = _tr('Pa&lettes')
ALPHA_TAB_TITLE = _tr('&Alpha and hex')

# Largest ring in the compact side layout, so the tabs leave room for the rows below them.
COMPACT_RING_MAX_SIZE = 180
DIALOG_RING_MIN_SIZE = 260
# Largest share of the picker's width the ring takes in row layouts, and of its height in the tall column layout.
ROW_RING_MAX_WIDTH_FRACTION = 0.4
TALL_RING_MAX_HEIGHT_FRACTION = 0.45
QWIDGETSIZE_MAX = 16777215
SPACING = 4


class ColorPickerLayout(Enum):
    """Arrangements of the color picker's parts."""
    # Header, then Wheel / Sliders / Palettes tabs, then alpha + hex and recent colors.
    SIDE = 'side'
    # SIDE with icon-only tabs, a smaller ring and no recent colors.
    SIDE_COMPACT = 'side_compact'
    # One column with no tabs: header, ring, alpha + hex, sliders, saved colors, recent colors.
    SIDE_TALL = 'side_tall'
    # Four columns with no tabs: header + alpha + hex + recent colors, ring, two slider blocks, saved colors.
    BOTTOM_WIDE = 'bottom_wide'
    # Header + recent colors column, ring, then Sliders / Palettes tabs with alpha + hex below.
    BOTTOM_MEDIUM = 'bottom_medium'
    # Header column, ring, then icon-only Sliders / Palettes / Alpha and hex tabs.
    BOTTOM_SHORT = 'bottom_short'
    # Header, ring beside Sliders / Palettes tabs, then alpha + hex and recent colors.
    DIALOG = 'dialog'


# Layouts that sit in a row, where the ring's width follows the available height.
ROW_LAYOUTS = (ColorPickerLayout.BOTTOM_WIDE, ColorPickerLayout.BOTTOM_MEDIUM, ColorPickerLayout.BOTTOM_SHORT)


@dataclass
class _LayoutEntry:
    """A layout's container, built once and kept hidden while another layout is active."""
    container: QWidget
    tabs: Optional[QTabWidget] = None
    # (box layout, index, part, stretch) for every part, so `TabbedColorPicker._activate_layout` can put the parts back.
    slots: list[tuple[QBoxLayout, int, QWidget, int]] = field(default_factory=list)


class TabbedColorPicker(ScreenColorWidget):
    """The color picker: a header, an OKHSV ring + square, gradient sliders, saved and recent colors, and alpha + hex.

    `swatch_widget` goes at the start of the header: the panel passes its color pair, the dialog its color comparison.

    Each layout's container is built the first time it's used and kept, so a layout switch moves the shared parts
    between existing containers and creates no widgets.

    A layout's minimum size (`layout_minimum`) is measured once, with the ring at its smallest, so it doesn't depend on
    the picker's size or on which layout was showing. The cache is cleared when the style, font or language changes.
    """

    color_committed = Signal(QColor)

    def __init__(self, swatch_widget: Optional[QWidget] = None,
                 picker_layout: ColorPickerLayout = ColorPickerLayout.SIDE) -> None:
        super().__init__()
        self._color = QColor(Qt.GlobalColor.black)
        self._outer_layout = QVBoxLayout(self)
        self._outer_layout.setContentsMargins(1, 1, 1, 1)
        self._layout_container: Optional[QWidget] = None
        self._entries: dict[ColorPickerLayout, _LayoutEntry] = {}
        self._building: Optional[_LayoutEntry] = None
        self._tabs: Optional[QTabWidget] = None
        self._current_tab_title: Optional[str] = None
        self._picker_layout: Optional[ColorPickerLayout] = None
        self._layout_minimums: dict[ColorPickerLayout, QSize] = {}
        self._measuring = False

        self._header = ColorPickerHeader(swatch_widget, self)
        self._header.pick_button.clicked.connect(self._start_screen_picking)
        self.color_previewed.connect(self._header.show_picking_preview)
        self.stopped_color_picking.connect(self._header.clear_picking_preview)
        self.screen_color_picked.connect(self._choose_color)

        self._ring_square = OkhsvRingSquare(self)
        self._slider_block = ColorSliderBlock(self)
        self._secondary_slider_block = ColorSliderBlock(self, secondary=True)
        self._alpha_hex_row = AlphaHexRow(self)
        for part in (self._ring_square, self._slider_block, self._secondary_slider_block, self._alpha_hex_row):
            part.color_changed.connect(self.set_current_color)
            part.color_committed.connect(self._commit)

        self._saved_panel = SavedColorsPanel(self)
        self._saved_panel.color_clicked.connect(self._choose_color)
        self._recent_row = RecentColorsRow(self)
        self._recent_row.color_clicked.connect(self._choose_color)

        self._update_parts()
        self.set_picker_layout(picker_layout)

    # Parts:

    @property
    def header(self) -> ColorPickerHeader:
        """The swatch widget, hex value and screen color pick button."""
        return self._header

    @property
    def ring_square(self) -> OkhsvRingSquare:
        """The OKHSV hue ring and saturation/value square."""
        return self._ring_square

    @property
    def slider_block(self) -> ColorSliderBlock:
        """The component sliders shown in every layout."""
        return self._slider_block

    @property
    def secondary_slider_block(self) -> ColorSliderBlock:
        """The second slider block, shown only in the wide layout."""
        return self._secondary_slider_block

    @property
    def alpha_hex_row(self) -> AlphaHexRow:
        """The alpha slider and hex field."""
        return self._alpha_hex_row

    @property
    def saved_colors_panel(self) -> SavedColorsPanel:
        """The saved colors panel."""
        return self._saved_panel

    @property
    def recent_colors_row(self) -> RecentColorsRow:
        """The recent colors row."""
        return self._recent_row

    @property
    def tab_widget(self) -> Optional[QTabWidget]:
        """The current layout's tabs, or None if it has none."""
        return self._tabs

    # Color:

    def selected_color(self) -> QColor:
        """Gets the current selected color."""
        return QColor(self._color)

    def set_current_color(self, color: QColor) -> None:
        """Sets the current selected color, shows it in every part, and emits `color_selected`."""
        color = QColor(color).toRgb()
        if color == self._color:
            return
        self._color = color
        self._update_parts()
        self.color_selected.emit(QColor(color))

    def _update_parts(self) -> None:
        for part in (self._ring_square, self._slider_block, self._secondary_slider_block, self._alpha_hex_row,
                     self._header, self._saved_panel, self._recent_row):
            part.set_color(self._color)

    def _commit(self, color: QColor) -> None:
        self.set_current_color(color)
        self.color_committed.emit(QColor(color))

    def _choose_color(self, color: QColor) -> None:
        """Selects and commits a color."""
        self._commit(color)

    def _start_screen_picking(self) -> None:
        if not self.color_picking_active:
            self.start_screen_color_picking()

    def keyPressEvent(self, a0) -> None:
        """Override to prevent closing with escape."""

    # Layout:

    def picker_layout(self) -> Optional[ColorPickerLayout]:
        """Returns the current arrangement."""
        return self._picker_layout

    @property
    def measuring(self) -> bool:
        """Whether the picker is measuring a layout. Resizes while it is don't reflect a change the picker's host
        asked for."""
        return self._measuring

    def layout_minimum(self, picker_layout: ColorPickerLayout) -> QSize:
        """Returns the smallest size a layout fits in, with the ring at its smallest.

        The size is measured the first time the layout shows, which builds it if needed. Measuring a layout that isn't
        showing switches to it and back.
        """
        known = self._layout_minimums.get(picker_layout)
        if known is not None:
            return QSize(known)
        previous = self._picker_layout
        if picker_layout == previous:
            self._measure_layout()
        else:
            self.set_picker_layout(picker_layout)
            if previous is not None:
                self.set_picker_layout(previous)
        return QSize(self._layout_minimums[picker_layout])

    def changeEvent(self, event: Optional[QEvent]) -> None:  # pylint: disable=invalid-name
        """Forgets the measured layout sizes when a change to the style, font or language would change them."""
        if event is not None and event.type() in (QEvent.Type.StyleChange, QEvent.Type.FontChange,
                                                  QEvent.Type.LanguageChange):
            self._layout_minimums.clear()
        super().changeEvent(event)

    def _measure_layout(self) -> None:
        """Measures the showing layout's minimum size, and leaves the ring fitted to the picker's size."""
        assert self._picker_layout is not None and self._layout_container is not None
        self._measuring = True
        try:
            self._fit_ring(QSize())
            size = fresh_minimum_size(self._layout_container)
            margins = self._outer_layout.contentsMargins()
            self._layout_minimums[self._picker_layout] = QSize(size.width() + margins.left() + margins.right(),
                                                              size.height() + margins.top() + margins.bottom())
        finally:
            self._measuring = False
        self._fit_ring()

    def set_picker_layout(self, picker_layout: ColorPickerLayout) -> None:
        """Rearranges the parts, keeping the selected tab if the new layout has it."""
        if picker_layout == self._picker_layout:
            return
        self._picker_layout = picker_layout
        if self._tabs is not None:
            self._current_tab_title = self._tabs.tabToolTip(self._tabs.currentIndex())
        if self._layout_container is not None:
            self._layout_container.hide()
        entry = self._entries.get(picker_layout)
        if entry is None:
            entry = self._build_entry(picker_layout)
        self._layout_container = entry.container
        self._tabs = entry.tabs
        if self._tabs is not None:
            for index in range(self._tabs.count()):
                if self._tabs.tabToolTip(index) == self._current_tab_title:
                    self._tabs.setCurrentIndex(index)
        self._header.set_vertical(picker_layout in (ColorPickerLayout.BOTTOM_MEDIUM, ColorPickerLayout.BOTTOM_SHORT))
        placed = self._activate_layout(entry)
        # The ring keeps the previous layout's fixed size until refitted. Showing first would report that stale size as
        # the minimum, and a dock that grows to fit it resizes the panel again mid-switch.
        measure = picker_layout not in self._layout_minimums
        self._fit_ring(QSize() if measure else None)
        for part in self._parts():
            if part not in placed:
                part.hide()
        for part in placed:
            part.show()
        entry.container.show()
        if measure:
            self._measure_layout()

    def _build_entry(self, picker_layout: ColorPickerLayout) -> _LayoutEntry:
        container = QWidget(self)
        container.hide()
        entry = _LayoutEntry(container)
        builders = {
            ColorPickerLayout.SIDE: self._build_side_layout,
            ColorPickerLayout.SIDE_COMPACT: lambda c: self._build_side_layout(c, compact=True),
            ColorPickerLayout.SIDE_TALL: self._build_side_tall_layout,
            ColorPickerLayout.BOTTOM_WIDE: self._build_bottom_wide_layout,
            ColorPickerLayout.BOTTOM_MEDIUM: self._build_bottom_medium_layout,
            ColorPickerLayout.BOTTOM_SHORT: self._build_bottom_short_layout,
            ColorPickerLayout.DIALOG: self._build_dialog_layout,
        }
        self._building = entry
        try:
            builders[picker_layout](container)
        finally:
            self._building = None
        self._outer_layout.addWidget(container)
        self._entries[picker_layout] = entry
        return entry

    @staticmethod
    def _activate_layout(entry: _LayoutEntry) -> list[QWidget]:
        """Puts back the parts that another layout took, and returns the parts the layout shows.

        Adding a widget to a layout removes it from the layout it was in, so a part sits in one layout at a time.
        Slots are in creation order, so each reinsertion lands at its original index.
        """
        for layout, index, part, stretch in entry.slots:
            if layout.indexOf(part) < 0:
                layout.insertWidget(index, part, stretch)
        return [part for _, _, part, _ in entry.slots]

    def _add(self, layout: QBoxLayout, part: QWidget, stretch: int = 0) -> None:
        """Adds a part to a layout of the layout being built, and records the slot for `_activate_layout`."""
        assert self._building is not None
        self._building.slots.append((layout, layout.count(), part, stretch))
        layout.addWidget(part, stretch)

    def resizeEvent(self, event) -> None:
        """Sizes the ring to the new picker size."""
        super().resizeEvent(event)
        self._fit_ring()

    def _fit_ring(self, available: Optional[QSize] = None) -> None:
        """Sizes the ring from the picker's size where the layout doesn't: its width in rows, its height in a column.

        `available` stands in for the picker's size, and an empty one gives the ring its smallest size. The ring never
        takes the room the rest of the layout needs for its own minimum size, once that is measured. Neither size
        depends on the ring's own position in the layout, so a scroll area can't grow the picker through it.
        """
        ring = self._ring_square
        margins = self._outer_layout.contentsMargins()
        if available is None:
            available = QSize(self.width() - margins.left() - margins.right(),
                              self.height() - margins.top() - margins.bottom())
        min_side = ring.minimumSizeHint().height()
        known = None if self._picker_layout is None else self._layout_minimums.get(self._picker_layout)
        rest_width = 0 if known is None else known.width() - margins.left() - margins.right() - min_side
        rest_height = 0 if known is None else known.height() - margins.top() - margins.bottom() - min_side
        width = None
        height = None
        if self._picker_layout in ROW_LAYOUTS:
            width = max(min(available.height(), int(available.width() * ROW_RING_MAX_WIDTH_FRACTION),
                            available.width() - rest_width), min_side)
        elif self._picker_layout == ColorPickerLayout.SIDE_TALL:
            height = max(min(available.width(), int(available.height() * TALL_RING_MAX_HEIGHT_FRACTION),
                             available.height() - rest_height), min_side)
        changed = False
        if width is not None:
            changed = ring.minimumWidth() != width or ring.maximumWidth() != width
            ring.setFixedWidth(width)
        else:
            ring.setMinimumWidth(DIALOG_RING_MIN_SIZE if self._picker_layout == ColorPickerLayout.DIALOG else 0)
            ring.setMaximumWidth(QWIDGETSIZE_MAX)
        if height is not None:
            changed = changed or ring.minimumHeight() != height or ring.maximumHeight() != height
            ring.setFixedHeight(height)
        else:
            ring.setMinimumHeight(DIALOG_RING_MIN_SIZE if self._picker_layout == ColorPickerLayout.DIALOG else 0)
            max_height = COMPACT_RING_MAX_SIZE if self._picker_layout == ColorPickerLayout.SIDE_COMPACT \
                else QWIDGETSIZE_MAX
            ring.setMaximumHeight(max_height)
        if changed and self._layout_container is not None and self._layout_container.layout() is not None:
            self._layout_container.layout().activate()

    def _parts(self) -> tuple[QWidget, ...]:
        return (self._header, self._ring_square, self._slider_block, self._secondary_slider_block,
                self._alpha_hex_row, self._saved_panel, self._recent_row)

    def _new_tabs(self, parent: QWidget, pages: list[tuple[str, QIcon, QWidget]], icon_only: bool) -> QTabWidget:
        """Creates the layout's tab widget."""
        tabs = QTabWidget(parent)
        for title, icon, page in pages:
            plain_title = title.replace('&', '')
            index = tabs.addTab(page, icon, '' if icon_only else title)
            tabs.setTabToolTip(index, plain_title)
        assert self._building is not None
        self._building.tabs = tabs
        return tabs

    def _page(self, parent: QWidget, *widgets: QWidget, stretch: bool = True) -> QWidget:
        """Wraps widgets in a tab page, stacked at the top."""
        page = QWidget(parent)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(SPACING, SPACING, SPACING, SPACING)
        for widget in widgets:
            self._add(layout, widget)
        if stretch:
            layout.addStretch(1)
        return page

    def _column(self, *widgets: QWidget, stretch: bool = True) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        for widget in widgets:
            self._add(layout, widget)
        if stretch:
            layout.addStretch(1)
        return layout

    def _build_side_layout(self, container: QWidget, compact: bool = False) -> None:
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        self._add(layout, self._header)
        tabs = self._new_tabs(container, [
            (WHEEL_TAB_TITLE, tab_icons.wheel_icon(), self._page(container, self._ring_square, stretch=False)),
            (SLIDERS_TAB_TITLE, tab_icons.sliders_icon(), self._page(container, self._slider_block)),
            (PALETTES_TAB_TITLE, tab_icons.palettes_icon(), self._page(container, self._saved_panel))
        ], icon_only=compact)
        layout.addWidget(tabs, stretch=1)
        self._add(layout, self._alpha_hex_row)
        if not compact:
            self._add(layout, self._recent_row)

    def _build_side_tall_layout(self, container: QWidget) -> None:
        container.setLayout(self._column(self._header, self._ring_square, self._alpha_hex_row, self._slider_block,
                                         self._saved_panel, self._recent_row))

    def _build_bottom_wide_layout(self, container: QWidget) -> None:
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._column(self._header, self._alpha_hex_row, self._recent_row), stretch=1)
        self._add(layout, self._ring_square)
        layout.addLayout(self._column(self._slider_block, self._secondary_slider_block), stretch=2)
        layout.addLayout(self._column(self._saved_panel), stretch=1)

    def _build_bottom_medium_layout(self, container: QWidget) -> None:
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._column(self._header, self._recent_row))
        self._add(layout, self._ring_square)
        tabs = self._new_tabs(container, [
            (SLIDERS_TAB_TITLE, tab_icons.sliders_icon(), self._page(container, self._slider_block)),
            (PALETTES_TAB_TITLE, tab_icons.palettes_icon(), self._page(container, self._saved_panel))
        ], icon_only=False)
        right_column = QVBoxLayout()
        right_column.addWidget(tabs, stretch=1)
        self._add(right_column, self._alpha_hex_row)
        layout.addLayout(right_column, stretch=1)

    def _build_bottom_short_layout(self, container: QWidget) -> None:
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._column(self._header))
        self._add(layout, self._ring_square)
        tabs = self._new_tabs(container, [
            (SLIDERS_TAB_TITLE, tab_icons.sliders_icon(), self._page(container, self._slider_block)),
            (PALETTES_TAB_TITLE, tab_icons.palettes_icon(), self._page(container, self._saved_panel)),
            (ALPHA_TAB_TITLE, tab_icons.alpha_icon(), self._page(container, self._alpha_hex_row))
        ], icon_only=True)
        layout.addWidget(tabs, stretch=1)

    def _build_dialog_layout(self, container: QWidget) -> None:
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        self._add(layout, self._header)
        row = QHBoxLayout()
        self._add(row, self._ring_square, stretch=1)
        tabs = self._new_tabs(container, [
            (SLIDERS_TAB_TITLE, tab_icons.sliders_icon(), self._page(container, self._slider_block)),
            (PALETTES_TAB_TITLE, tab_icons.palettes_icon(), self._page(container, self._saved_panel))
        ], icon_only=False)
        row.addWidget(tabs, stretch=1)
        layout.addLayout(row, stretch=1)
        self._add(layout, self._alpha_hex_row)
        self._add(layout, self._recent_row)
