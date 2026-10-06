"""Saved and recent color swatches for the color picker.

`SavedColorsPanel` shows `AppConfig.SAVED_COLORS` with a button that saves the current color, and a context menu that
removes one. A color dragged onto its grid is saved at the drop point, which also reorders saved colors.
`RecentColorsRow` shows `Cache.RECENT_COLORS`. Both follow their config key, so every picker shows the same lists.
A swatch click emits `color_clicked`, which the picker treats as a committed choice.
"""
from typing import Optional

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QMenu, QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller import color_controller
from src.ui.widget.color_picker.color_swatch_grid import ColorSwatchGrid

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.widget.color_picker.saved_colors_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


SAVED_COLORS_LABEL = _tr('Saved colors:')
SAVED_COLORS_TOOLTIP = _tr('Click a color to use it. Drag colors here to save them, or drag to reorder them. '
                           'Right-click a color to remove it.')
SAVE_BUTTON_LABEL = _tr('Save c&urrent color')
REMOVE_ACTION_LABEL = _tr('Remove')
RECENT_COLORS_LABEL = _tr('Recent colors:')
RECENT_COLORS_TOOLTIP = _tr('Colors you chose most recently, newest first. Click a color to use it again, or drag it '
                            'to the saved colors.')


class SavedColorsPanel(QWidget):
    """Saved color swatches with a button that saves the current color."""

    color_clicked = Signal(QColor)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._color = QColor(Qt.GlobalColor.black)
        layout = QVBoxLayout(self)
        label = QLabel(SAVED_COLORS_LABEL)
        layout.addWidget(label)
        self._grid = ColorSwatchGrid(accept_drops=True)
        self._grid.setToolTip(SAVED_COLORS_TOOLTIP)
        self._grid.color_dropped.connect(color_controller.insert_saved_color)
        self._grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._grid.customContextMenuRequested.connect(self._show_context_menu)
        self._grid.color_clicked.connect(self.color_clicked)
        label.setBuddy(self._grid)
        layout.addWidget(self._grid)
        self._save_button = QPushButton(SAVE_BUTTON_LABEL)
        self._save_button.clicked.connect(lambda: color_controller.save_color(self._color))
        layout.addWidget(self._save_button)
        layout.addStretch(1)
        self._grid.set_colors(color_controller.saved_colors())
        AppConfig().connect(self, AppConfig.SAVED_COLORS,
                            lambda _: self._grid.set_colors(color_controller.saved_colors()))

    @property
    def grid(self) -> ColorSwatchGrid:
        """The saved color swatches."""
        return self._grid

    @property
    def save_button(self) -> QPushButton:
        """The button that saves the current color."""
        return self._save_button

    def set_color(self, color: QColor) -> None:
        """Sets the color the save button saves, and highlights it if it is already saved."""
        self._color = QColor(color)
        self._grid.set_current_color(color)

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
