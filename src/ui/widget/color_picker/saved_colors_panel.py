"""Saved and recent color swatches for the color picker.

`SavedColorsPanel` shows `AppConfig.SAVED_COLORS` in a scrolling grid, with buttons that save or remove the current
color and a context menu that removes any swatch. A color dragged onto its grid is saved at the drop point, which also
reorders saved colors. The list holds at most `color_controller.MAX_SAVED_COLORS`.
`RecentColorsRow` shows `Cache.RECENT_COLORS`. Both follow their config key, so every picker shows the same lists.
A swatch click emits `color_clicked`, which the picker treats as a committed choice.
"""
from typing import Optional

from PySide6.QtCore import Qt, Signal, QPoint, QSize
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMenu, QApplication, \
    QScrollArea, QFrame

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller import color_controller
from src.ui.widget.color_picker.color_swatch_grid import ColorSwatchGrid, SWATCH_SIZE, SWATCH_SPACING

# The saved colors scroll once they need more rows than MAX_VISIBLE_ROWS, and the layout may shrink the grid's visible
# area to MIN_VISIBLE_ROWS.
MAX_VISIBLE_ROWS = 6
MIN_VISIBLE_ROWS = 2

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.widget.color_picker.saved_colors_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


SAVED_COLORS_LABEL = _tr('Saved colors ({count}/{max_count}):')
SAVED_COLORS_TOOLTIP = _tr('Click a color to use it. Drag colors here to save them, or drag to reorder them. '
                           'Right-click a color to remove it.')
SAVE_BUTTON_LABEL = _tr('Sa&ve')
SAVE_BUTTON_TOOLTIP = _tr('Add the current color to the saved colors')
SAVE_BUTTON_FULL_TOOLTIP = _tr('The saved colors are full. Remove one to save another.')
REMOVE_BUTTON_LABEL = _tr('Re&move')
REMOVE_BUTTON_TOOLTIP = _tr('Remove the current color from the saved colors')
REMOVE_ACTION_LABEL = _tr('Remove')
RECENT_COLORS_LABEL = _tr('Recent colors:')
RECENT_COLORS_TOOLTIP = _tr('Colors you chose most recently, newest first. Click a color to use it again, or drag it '
                            'to the saved colors.')


class _GridScrollArea(QScrollArea):
    """Scrolls a swatch grid, showing every row up to MAX_VISIBLE_ROWS and shrinking to MIN_VISIBLE_ROWS."""

    def __init__(self, grid: ColorSwatchGrid) -> None:
        super().__init__()
        self._grid = grid
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(grid)

    def sizeHint(self) -> QSize:
        """Asks for the full maximum height, so layouts show every row they have room for."""
        return QSize(super().sizeHint().width(), self.maximumHeight())

    def resizeEvent(self, event) -> None:
        """Updates the height limits for the new width."""
        super().resizeEvent(event)
        self.update_height_limits()

    def update_height_limits(self) -> None:
        """Sets the height limits from the grid's rows at the current width."""
        content_height = self._grid.heightForWidth(max(self.viewport().width(), SWATCH_SIZE))
        row_step = SWATCH_SIZE + SWATCH_SPACING
        maximum = min(content_height, MAX_VISIBLE_ROWS * row_step - SWATCH_SPACING)
        minimum = min(content_height, MIN_VISIBLE_ROWS * row_step - SWATCH_SPACING)
        if maximum != self.maximumHeight() or minimum != self.minimumHeight():
            self.setMaximumHeight(maximum)
            self.setMinimumHeight(minimum)
            # The size hint follows the maximum height, so layouts need to re-read it.
            self.updateGeometry()


class SavedColorsPanel(QWidget):
    """Saved color swatches in a scrolling grid, with buttons that save or remove the current color."""

    color_clicked = Signal(QColor)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._color = QColor(Qt.GlobalColor.black)
        layout = QVBoxLayout(self)
        self._label = QLabel()
        layout.addWidget(self._label)
        self._grid = ColorSwatchGrid(accept_drops=True)
        self._grid.setToolTip(SAVED_COLORS_TOOLTIP)
        self._grid.color_dropped.connect(color_controller.insert_saved_color)
        self._grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._grid.customContextMenuRequested.connect(self._show_context_menu)
        self._grid.color_clicked.connect(self.color_clicked)
        self._label.setBuddy(self._grid)
        self._scroll_area = _GridScrollArea(self._grid)
        layout.addWidget(self._scroll_area)

        button_row = QHBoxLayout()
        self._save_button = QPushButton(SAVE_BUTTON_LABEL)
        self._save_button.clicked.connect(lambda: color_controller.save_color(self._color))
        button_row.addWidget(self._save_button, stretch=1)
        self._remove_button = QPushButton(REMOVE_BUTTON_LABEL)
        self._remove_button.setToolTip(REMOVE_BUTTON_TOOLTIP)
        self._remove_button.clicked.connect(self._remove_current_color)
        button_row.addWidget(self._remove_button)
        layout.addLayout(button_row)
        layout.addStretch(1)
        self._update_colors()
        AppConfig().connect(self, AppConfig.SAVED_COLORS, lambda _: self._update_colors())

    @property
    def grid(self) -> ColorSwatchGrid:
        """The saved color swatches."""
        return self._grid

    @property
    def scroll_area(self) -> QScrollArea:
        """The scroll area holding the grid."""
        return self._scroll_area

    @property
    def label(self) -> QLabel:
        """The label above the grid, with the saved color count."""
        return self._label

    @property
    def save_button(self) -> QPushButton:
        """The button that saves the current color."""
        return self._save_button

    @property
    def remove_button(self) -> QPushButton:
        """The button that removes the current color from the saved colors."""
        return self._remove_button

    def set_color(self, color: QColor) -> None:
        """Sets the color the buttons save or remove, and highlights it if it is already saved."""
        self._color = QColor(color)
        self._grid.set_current_color(color)
        self._update_buttons()

    def _update_colors(self) -> None:
        colors = color_controller.saved_colors()
        self._grid.set_colors(colors)
        self._label.setText(SAVED_COLORS_LABEL.format(count=len(colors),
                                                      max_count=color_controller.MAX_SAVED_COLORS))
        self._update_buttons()
        self._scroll_area.update_height_limits()

    def _update_buttons(self) -> None:
        is_saved = color_controller.saved_color_index(self._color) >= 0
        is_full = color_controller.saved_colors_full()
        self._save_button.setEnabled(not is_saved and not is_full)
        self._save_button.setToolTip(SAVE_BUTTON_FULL_TOOLTIP if is_full and not is_saved else SAVE_BUTTON_TOOLTIP)
        self._remove_button.setEnabled(is_saved)

    def _remove_current_color(self) -> None:
        index = color_controller.saved_color_index(self._color)
        if index >= 0:
            color_controller.remove_saved_color(index)

    def _show_context_menu(self, point: QPoint) -> None:
        index = self._grid.index_at(point)
        if index < 0:
            return
        menu = QMenu(self)
        remove_action = menu.addAction(REMOVE_ACTION_LABEL)
        if menu.exec(self._grid.mapToGlobal(point)) == remove_action:
            color_controller.remove_saved_color(index)


class RecentColorsRow(QWidget):
    """Recent color swatches, newest first."""

    color_clicked = Signal(QColor)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(RECENT_COLORS_LABEL)
        layout.addWidget(label)
        self._grid = ColorSwatchGrid()
        self._grid.setToolTip(RECENT_COLORS_TOOLTIP)
        self._grid.color_clicked.connect(self.color_clicked)
        label.setBuddy(self._grid)
        layout.addWidget(self._grid)
        self._grid.set_colors(color_controller.recent_colors())
        Cache().connect(self, Cache.RECENT_COLORS, lambda _: self._grid.set_colors(color_controller.recent_colors()))

    @property
    def grid(self) -> ColorSwatchGrid:
        """The recent color swatches."""
        return self._grid

    def set_color(self, color: QColor) -> None:
        """Highlights a color if it is in the list."""
        self._grid.set_current_color(color)
