"""The color picker: a header, an OKHSV ring + square, gradient sliders, saved and recent colors, and alpha + hex.

`ColorPickerLayout` arranges the parts, in tabs where space is short. Every part edits one color. `color_selected` fires
on every change, and `color_committed` only on a finished choice: a mouse release, a swatch click, a hex entry or a
screen pick. Callers record committed colors as recent colors (see `src.controller.color_controller`).
"""
from enum import Enum
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QApplication

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
# Largest share of the picker's width the ring takes in row layouts.
ROW_RING_MAX_WIDTH_FRACTION = 0.4
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


class TabbedColorPicker(ScreenColorWidget):
    """The color picker: a header, an OKHSV ring + square, gradient sliders, saved and recent colors, and alpha + hex.

    `swatch_widget` goes at the start of the header: the panel passes its color pair, the dialog its color comparison.
    """

    color_committed = Signal(QColor)

    def __init__(self, swatch_widget: Optional[QWidget] = None,
                 picker_layout: ColorPickerLayout = ColorPickerLayout.SIDE) -> None:
        super().__init__()
        self._color = QColor(Qt.GlobalColor.black)
        self._outer_layout = QVBoxLayout(self)
        self._outer_layout.setContentsMargins(1, 1, 1, 1)
        self._layout_container: Optional[QWidget] = None
        self._tabs: Optional[QTabWidget] = None
        self._current_tab_title: Optional[str] = None
        self._picker_layout: Optional[ColorPickerLayout] = None

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

    def set_picker_layout(self, picker_layout: ColorPickerLayout) -> None:
        """Rearranges the parts, keeping the selected tab if the new layout has it."""
        if picker_layout == self._picker_layout:
            return
        self._picker_layout = picker_layout
        if self._tabs is not None:
            self._current_tab_title = self._tabs.tabToolTip(self._tabs.currentIndex())
        self._clear_layout()
        container = QWidget(self)
        builders = {
            ColorPickerLayout.SIDE: self._build_side_layout,
            ColorPickerLayout.SIDE_COMPACT: lambda c: self._build_side_layout(c, compact=True),
            ColorPickerLayout.SIDE_TALL: self._build_side_tall_layout,
            ColorPickerLayout.BOTTOM_WIDE: self._build_bottom_wide_layout,
            ColorPickerLayout.BOTTOM_MEDIUM: self._build_bottom_medium_layout,
            ColorPickerLayout.BOTTOM_SHORT: self._build_bottom_short_layout,
            ColorPickerLayout.DIALOG: self._build_dialog_layout,
        }
        placed = builders[picker_layout](container)
        for part in placed:
            part.show()
        self._outer_layout.addWidget(container)
        container.show()
        self._layout_container = container
        self._fit_ring()

    def resizeEvent(self, event) -> None:
        """Sizes the ring in row layouts, where its width follows the available height."""
        super().resizeEvent(event)
        self._fit_ring()

    def _fit_ring(self) -> None:
        ring = self._ring_square
        if self._picker_layout in ROW_LAYOUTS:
            margins = self._outer_layout.contentsMargins()
            available_height = self.height() - margins.top() - margins.bottom()
            side = min(available_height, int(self.width() * ROW_RING_MAX_WIDTH_FRACTION))
            side = max(side, ring.minimumSizeHint().height())
            if ring.minimumWidth() != side or ring.maximumWidth() != side:
                ring.setFixedWidth(side)
                if self._layout_container is not None and self._layout_container.layout() is not None:
                    self._layout_container.layout().activate()
            return
        ring.setMinimumWidth(0)
        ring.setMaximumWidth(16777215)
        if self._picker_layout == ColorPickerLayout.SIDE_COMPACT:
            ring.setMaximumHeight(COMPACT_RING_MAX_SIZE)
        else:
            ring.setMaximumHeight(16777215)
        if self._picker_layout == ColorPickerLayout.DIALOG:
            ring.setMinimumSize(DIALOG_RING_MIN_SIZE, DIALOG_RING_MIN_SIZE)
        else:
            ring.setMinimumSize(0, 0)

    def _clear_layout(self) -> None:
        for part in self._parts():
            part.hide()
            part.setParent(self)
        self._tabs = None
        if self._layout_container is not None:
            self._outer_layout.removeWidget(self._layout_container)
            self._layout_container.hide()
            self._layout_container.deleteLater()
            self._layout_container = None

    def _parts(self) -> tuple[QWidget, ...]:
        return (self._header, self._ring_square, self._slider_block, self._secondary_slider_block,
                self._alpha_hex_row, self._saved_panel, self._recent_row)

    def _new_tabs(self, parent: QWidget, pages: list[tuple[str, QIcon, QWidget]], icon_only: bool) -> QTabWidget:
        """Creates the layout's tab widget, selecting the tab that was open in the last layout if it has one."""
        tabs = QTabWidget(parent)
        for title, icon, page in pages:
            plain_title = title.replace('&', '')
            index = tabs.addTab(page, icon, '' if icon_only else title)
            tabs.setTabToolTip(index, plain_title)
            if plain_title == self._current_tab_title:
                tabs.setCurrentIndex(index)
        self._tabs = tabs
        return tabs

    @staticmethod
    def _page(parent: QWidget, *widgets: QWidget, stretch: bool = True) -> QWidget:
        """Wraps widgets in a tab page, stacked at the top."""
        page = QWidget(parent)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(SPACING, SPACING, SPACING, SPACING)
        for widget in widgets:
            layout.addWidget(widget)
        if stretch:
            layout.addStretch(1)
        return page

    @staticmethod
    def _column(*widgets: QWidget, stretch: bool = True) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        for widget in widgets:
            layout.addWidget(widget)
        if stretch:
            layout.addStretch(1)
        return layout

    def _build_side_layout(self, container: QWidget, compact: bool = False) -> list[QWidget]:
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        self._header.set_vertical(False)
        layout.addWidget(self._header)
        tabs = self._new_tabs(container, [
            (WHEEL_TAB_TITLE, tab_icons.wheel_icon(), self._page(container, self._ring_square, stretch=False)),
            (SLIDERS_TAB_TITLE, tab_icons.sliders_icon(), self._page(container, self._slider_block)),
            (PALETTES_TAB_TITLE, tab_icons.palettes_icon(), self._page(container, self._saved_panel))
        ], icon_only=compact)
        layout.addWidget(tabs, stretch=1)
        layout.addWidget(self._alpha_hex_row)
        placed: list[QWidget] = [self._header, self._ring_square, self._slider_block, self._saved_panel,
                                 self._alpha_hex_row]
        if not compact:
            layout.addWidget(self._recent_row)
            placed.append(self._recent_row)
        return placed

    def _build_side_tall_layout(self, container: QWidget) -> list[QWidget]:
        self._header.set_vertical(False)
        parts = (self._header, self._ring_square, self._alpha_hex_row, self._slider_block, self._saved_panel,
                 self._recent_row)
        container.setLayout(self._column(*parts))
        return list(parts)

    def _build_bottom_wide_layout(self, container: QWidget) -> list[QWidget]:
        self._header.set_vertical(False)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._column(self._header, self._alpha_hex_row, self._recent_row), stretch=1)
        layout.addWidget(self._ring_square)
        layout.addLayout(self._column(self._slider_block, self._secondary_slider_block), stretch=2)
        layout.addLayout(self._column(self._saved_panel), stretch=1)
        return [self._header, self._alpha_hex_row, self._recent_row, self._ring_square, self._slider_block,
                self._secondary_slider_block, self._saved_panel]

    def _build_bottom_medium_layout(self, container: QWidget) -> list[QWidget]:
        self._header.set_vertical(True)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._column(self._header, self._recent_row))
        layout.addWidget(self._ring_square)
        tabs = self._new_tabs(container, [
            (SLIDERS_TAB_TITLE, tab_icons.sliders_icon(), self._page(container, self._slider_block)),
            (PALETTES_TAB_TITLE, tab_icons.palettes_icon(), self._page(container, self._saved_panel))
        ], icon_only=False)
        right_column = QVBoxLayout()
        right_column.addWidget(tabs, stretch=1)
        right_column.addWidget(self._alpha_hex_row)
        layout.addLayout(right_column, stretch=1)
        return [self._header, self._recent_row, self._ring_square, self._slider_block, self._saved_panel,
                self._alpha_hex_row]

    def _build_bottom_short_layout(self, container: QWidget) -> list[QWidget]:
        self._header.set_vertical(True)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._column(self._header))
        layout.addWidget(self._ring_square)
        tabs = self._new_tabs(container, [
            (SLIDERS_TAB_TITLE, tab_icons.sliders_icon(), self._page(container, self._slider_block)),
            (PALETTES_TAB_TITLE, tab_icons.palettes_icon(), self._page(container, self._saved_panel)),
            (ALPHA_TAB_TITLE, tab_icons.alpha_icon(), self._page(container, self._alpha_hex_row))
        ], icon_only=True)
        layout.addWidget(tabs, stretch=1)
        return [self._header, self._ring_square, self._slider_block, self._saved_panel, self._alpha_hex_row]

    def _build_dialog_layout(self, container: QWidget) -> list[QWidget]:
        self._header.set_vertical(False)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._header)
        row = QHBoxLayout()
        row.addWidget(self._ring_square, stretch=1)
        tabs = self._new_tabs(container, [
            (SLIDERS_TAB_TITLE, tab_icons.sliders_icon(), self._page(container, self._slider_block)),
            (PALETTES_TAB_TITLE, tab_icons.palettes_icon(), self._page(container, self._saved_panel))
        ], icon_only=False)
        row.addWidget(tabs, stretch=1)
        layout.addLayout(row, stretch=1)
        layout.addWidget(self._alpha_hex_row)
        layout.addWidget(self._recent_row)
        return [self._header, self._ring_square, self._slider_block, self._saved_panel, self._alpha_hex_row,
                self._recent_row]
