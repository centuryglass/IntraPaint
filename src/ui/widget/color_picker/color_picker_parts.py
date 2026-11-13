"""The color picker's parts, kept on one color: a header, an OKHSV ring + square, gradient sliders with alpha, and
saved and recent colors.

`ColorPickerParts` owns no layout. Its owner places the parts: `src.ui.panel.color_panel.ColorControlPanel` plans them
by fit, and `src.ui.modal.color_dialog.ColorDialog` gives them one arrangement. `color_selected` fires on every change,
and `color_committed` only on a finished choice: a mouse release, a swatch click, a hex entry or a screen pick. Callers
record committed colors as recent colors (see `src.controller.color_controller`).
"""
from typing import Optional

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

from src.ui.widget.color_picker.color_picker_header import ColorPickerHeader
from src.ui.widget.color_picker.color_slider_block import ColorSliderBlock
from src.ui.widget.color_picker.okhsv_ring_square import OkhsvRingSquare
from src.ui.widget.color_picker.saved_colors_panel import SavedColorsPanel, RecentColorsRow


class ColorPickerParts(QObject):
    """The color picker's parts, kept on one color.

    `swatch_widget` goes at the start of the header: the panel passes its color pair, the dialog its color comparison.
    With `section_controls`, the saved colors panel and recent colors row leave their labels and buttons to the owner's
    section headers.
    """

    color_selected = Signal(QColor)
    color_committed = Signal(QColor)

    def __init__(self, swatch_widget: Optional[QWidget] = None, section_controls: bool = False,
                 parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._color = QColor(Qt.GlobalColor.black)
        self._header = ColorPickerHeader(swatch_widget)
        self._header.color_entered.connect(self._commit)
        self._header.screen_color_picked.connect(self._commit)
        self._ring_square = OkhsvRingSquare()
        self._slider_block = ColorSliderBlock()
        for part in (self._ring_square, self._slider_block):
            part.color_changed.connect(self.set_current_color)
            part.color_committed.connect(self._commit)
        self._saved_panel = SavedColorsPanel(inline_controls=not section_controls)
        self._saved_panel.color_clicked.connect(self._commit)
        self._recent_row = RecentColorsRow(labeled=not section_controls)
        self._recent_row.color_clicked.connect(self._commit)
        self._update_parts()

    @property
    def header(self) -> ColorPickerHeader:
        """The swatch widget, hex field and screen color pick button."""
        return self._header

    @property
    def ring_square(self) -> OkhsvRingSquare:
        """The OKHSV hue ring and saturation/value square."""
        return self._ring_square

    @property
    def slider_block(self) -> ColorSliderBlock:
        """The component and alpha sliders."""
        return self._slider_block

    @property
    def saved_colors_panel(self) -> SavedColorsPanel:
        """The saved colors panel."""
        return self._saved_panel

    @property
    def recent_colors_row(self) -> RecentColorsRow:
        """The recent colors row."""
        return self._recent_row

    def widgets(self) -> tuple[QWidget, ...]:
        """Returns every part, in reading order."""
        return self._header, self._ring_square, self._slider_block, self._recent_row, self._saved_panel

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
        for part in (self._ring_square, self._slider_block, self._header, self._saved_panel, self._recent_row):
            part.set_color(self._color)

    def _commit(self, color: QColor) -> None:
        """Selects and commits a color."""
        self.set_current_color(color)
        self.color_committed.emit(QColor(color))
