"""A `QDockWidget` that hosts one main window panel and tells the panel where it is docked.

- Orientation and size class come from the dock's area, floating state and size, through
  `src.ui.layout.panel_size_class`. A `DockPanel` gets them through `set_host_facts`. Other content with a
  `set_orientation` method gets the matching `Qt.Orientation` when the orientation changes, until it migrates to
  `DockPanel`.
- A tab group shows one dock at a time, and the edge rails act as its tabs. Opening a dock with `open_in_group`, its
  key, its toggle action or a mouse drop into a group closes the group's other docks. A dock in the background of a
  group is closed. `show` opens a dock without closing the others, so code opens docks with `open_in_group`.
- The dock's key (`shortcut_config_key`) opens and focuses the dock, or closes it if it is already open.
- A dock with no content is hidden and its toggle action is hidden too. It remembers whether it was open, and opens
  again when content arrives, unless another dock in its group is open by then.
- `QMainWindow.saveState` identifies docks by object name, so every dock needs a unique, permanent one. Renaming one
  drops its saved placement.
"""
from contextlib import contextmanager
from typing import Iterator, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QResizeEvent
from PySide6.QtWidgets import QDockWidget, QMainWindow, QWidget

from src.hotkey_filter import HotkeyFilter
from src.ui.layout.dock_panel import DockPanel
from src.ui.layout.panel_size_class import Orientation, orientation_for_dock
from src.ui.window.dock_state import read_dock_groups


def qt_orientation(orientation: Orientation) -> Qt.Orientation:
    """Returns the `Qt.Orientation` that unmigrated panels' `set_orientation` expects: vertical for side panels."""
    return Qt.Orientation.Vertical if orientation == Orientation.SIDE else Qt.Orientation.Horizontal


class PanelDock(QDockWidget):
    """Hosts one panel, forwards orientation and size class to it, and toggles it from a key."""

    _drop_rule_pauses = 0

    def __init__(self, title: str, object_name: str, window: QMainWindow, icon: Optional[QIcon] = None,
                 shortcut_config_key: Optional[str] = None) -> None:
        super().__init__(title, window)
        self._window = window
        self.setObjectName(object_name)
        if icon is not None:
            self.setWindowIcon(icon)
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable
                         | QDockWidget.DockWidgetFeature.DockWidgetMovable
                         | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self._shortcut_config_key = shortcut_config_key
        self._content: Optional[QWidget] = None
        self._open_when_available = True
        self._showing = False
        self._forwarded_orientation: Optional[Qt.Orientation] = None
        self.toggleViewAction().setVisible(False)
        self.toggleViewAction().setIcon(self.windowIcon())
        self.visibilityChanged.connect(self._visibility_changed)
        self.dockLocationChanged.connect(self._update_host_facts)
        self.topLevelChanged.connect(self._update_host_facts)
        self.topLevelChanged.connect(self._top_level_changed)
        self.toggleViewAction().triggered.connect(self._toggle_action_triggered)
        if shortcut_config_key is not None:
            HotkeyFilter.instance().register_config_keybinding(f'PanelDock_{id(self)}_shortcut',
                                                               self.toggle_from_key, shortcut_config_key)

    @staticmethod
    @contextmanager
    def placing_docks() -> Iterator[None]:
        """Stops a dock that stops floating from closing its group's other docks, while code places docks.

        Docking a floating dock outside a mouse drop, as `restoreState`, `setFloating(False)` and the dock menu's moves
        do, would otherwise close docks the caller means to keep open.
        """
        PanelDock._drop_rule_pauses += 1
        try:
            yield
        finally:
            PanelDock._drop_rule_pauses -= 1

    @property
    def shortcut_config_key(self) -> Optional[str]:
        """The `KeyConfig` key that toggles the dock, if it has one."""
        return self._shortcut_config_key

    @property
    def content(self) -> Optional[QWidget]:
        """The hosted panel, or None if the dock has nothing to show."""
        return self._content

    @property
    def is_available(self) -> bool:
        """Whether the dock has content, so it can be opened."""
        return self._content is not None

    @property
    def is_showing(self) -> bool:
        """Whether the dock's content is on screen: open, in a shown window."""
        return self._showing

    @property
    def open_when_available(self) -> bool:
        """Whether a dock with no content opens when content arrives."""
        return self._open_when_available

    def set_content(self, content: Optional[QWidget]) -> None:
        """Replaces the hosted panel. The old one is detached, not deleted. With None, the dock hides until content
        arrives, then reopens if it was open."""
        if content is self._content:
            return
        if self._content is not None:
            self._open_when_available = not self.isHidden()
            self._content.hide()
            self._content.setParent(None)
        self._content = content
        self._forwarded_orientation = None
        if content is None:
            self.toggleViewAction().setVisible(False)
            self.hide()
            return
        self.setWidget(content)
        content.show()
        self.toggleViewAction().setVisible(True)
        if self._open_when_available:
            if any(not mate.isHidden() for mate in self.group_mates()):
                self._open_when_available = False
            else:
                self.show()
        self._update_host_facts()

    def group_mates(self) -> list['PanelDock']:
        """Returns the other docks in this dock's tab group, open or closed, in tab order. A floating dock has none, and
        floating docks are left out."""
        if self.isFloating():
            return []
        groups = read_dock_groups(self._window.saveState().data())
        name = self.objectName()
        group = next((group for group in groups or [] if any(dock.name == name for dock in group.docks)), None)
        if group is None:
            return []
        docks = {dock.objectName(): dock for dock in
                 self._window.findChildren(PanelDock, options=Qt.FindChildOption.FindDirectChildrenOnly)}
        mates = [docks.get(saved.name) for saved in group.docks if saved.name != name]
        return [mate for mate in mates if mate is not None and not mate.isFloating()]

    def open_in_group(self) -> None:
        """Opens the dock in front of its tab group, and closes the group's other docks."""
        self.show()
        self.raise_()
        for mate in self.group_mates():
            mate.set_open(False)

    def sync_availability(self) -> None:
        """Hides the dock if it has no content, remembering whether it was open. Call after `restoreState`, which can
        show any dock."""
        if self._content is None:
            self._open_when_available = not self.isHidden()
            self.hide()

    def set_open(self, is_open: bool) -> None:
        """Opens the dock in its group or closes it, or with no content sets whether it opens once content arrives."""
        if self._content is None:
            self._open_when_available = is_open
        elif is_open:
            self.open_in_group()
        else:
            self.hide()

    def toggle_from_key(self) -> bool:
        """Closes the dock if it is showing, or opens it in its group and focuses it. Returns whether the key was
        used."""
        if self._content is None:
            return False
        if self._showing and not self.isHidden():
            self.hide()
            return True
        self.open_in_group()
        self.activateWindow()
        self._content.setFocus()
        return True

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """Updates the content's size class."""
        super().resizeEvent(event)
        self._update_host_facts()

    def _toggle_action_triggered(self, checked: bool) -> None:
        """Closes the group's other docks when the toggle action opens this one."""
        if checked and self._content is not None:
            self.open_in_group()

    def _top_level_changed(self, floating: bool) -> None:
        """Brings a dock dropped into a tab group to the front, as `open_in_group` does."""
        if not floating and PanelDock._drop_rule_pauses == 0 and not self.isHidden():
            for mate in self.group_mates():
                mate.set_open(False)

    def _visibility_changed(self, visible: bool) -> None:
        self._showing = visible
        if visible:
            self._update_host_facts()

    def _update_host_facts(self, *_args) -> None:
        if self._content is None:
            return
        orientation = orientation_for_dock(self._window.dockWidgetArea(self), self.isFloating(), self.size())
        if isinstance(self._content, DockPanel):
            self._content.set_host_facts(orientation, self.size())
        elif hasattr(self._content, 'set_orientation'):
            legacy_orientation = qt_orientation(orientation)
            if legacy_orientation != self._forwarded_orientation:
                self._forwarded_orientation = legacy_orientation
                self._content.set_orientation(legacy_orientation)
