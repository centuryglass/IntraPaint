"""The title bar of a floating `PanelDock`: its rail button, then buttons to dock and close it.

- An open floating dock's button is here instead of in a rail (see `DockRails.sync`).
- The rail button only shows the dock. It ignores the mouse, like the bar's empty space, so a press anywhere but the
  dock and close buttons reaches the dock and drags it, through the same mouse events on every platform.
- Right-clicking the bar opens the dock's menu.
"""
from typing import Callable, Optional
from weakref import ref

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QStyle, QToolButton, QWidget

from src.ui.window.dock_rail import RailButton
from src.ui.window.panel_dock import PanelDock

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.window.floating_title_bar'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


DOCK_TOOLTIP = _tr('Dock panel')
CLOSE_TOOLTIP = _tr('Hide panel')

TITLE_BAR_MARGIN = 2
TITLE_BUTTON_ICON_SIZE = 12


class FloatingTitleBar(QWidget):
    """Shows a floating dock's rail button, with buttons that dock and close it."""

    @property
    def _dock(self) -> PanelDock:
        # Held weakly, since the dock holds its title bar:
        dock = self._dock_ref()
        assert dock is not None, 'A floating title bar outlived its dock'
        return dock

    def __init__(self, dock: PanelDock, show_menu: Callable[[PanelDock, QPoint], None]) -> None:
        """`show_menu` opens the dock's menu at a screen position."""
        super().__init__()
        self._dock_ref = ref(dock)
        self._button = RailButton(dock)
        self._button.set_placement(False, Qt.Edge.BottomEdge)
        self._button.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        style = self.style()
        self._dock_button = self._title_button(style.standardIcon(QStyle.StandardPixmap.SP_TitleBarNormalButton),
                                               DOCK_TOOLTIP)
        self._dock_button.clicked.connect(lambda: dock.setFloating(False))
        self._close_button = self._title_button(style.standardIcon(QStyle.StandardPixmap.SP_TitleBarCloseButton),
                                                CLOSE_TOOLTIP)
        self._close_button.clicked.connect(dock.hide)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(TITLE_BAR_MARGIN, TITLE_BAR_MARGIN, TITLE_BAR_MARGIN, TITLE_BAR_MARGIN)
        layout.setSpacing(TITLE_BAR_MARGIN)
        layout.addWidget(self._button)
        layout.addStretch(1)
        layout.addWidget(self._dock_button)
        layout.addWidget(self._close_button)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda pos: show_menu(dock, self.mapToGlobal(pos)))

    @staticmethod
    def _title_button(icon, tooltip: str) -> QToolButton:
        button = QToolButton()
        button.setIcon(icon)
        button.setIconSize(QSize(TITLE_BUTTON_ICON_SIZE, TITLE_BUTTON_ICON_SIZE))
        button.setAutoRaise(True)
        button.setToolTip(tooltip)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return button

    @property
    def rail_button(self) -> RailButton:
        """Returns the dock's button shown in the bar."""
        return self._button

    @property
    def dock_button(self) -> QToolButton:
        """Returns the button that docks the dock."""
        return self._dock_button

    @property
    def close_button(self) -> QToolButton:
        """Returns the button that closes the dock."""
        return self._close_button
