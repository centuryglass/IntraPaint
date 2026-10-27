"""A `QDockWidget` that hosts one main window panel and tells the panel where it is docked.

- A `DockPanel` gets the size it fills, which leaves out the dock's title bar, through `set_host_facts`, and picks
  its own orientation. Other content with a `set_orientation` method gets its orientation from the dock's area
  (`src.ui.layout.panel_fit.orientation_for_dock`), until it migrates to `DockPanel`.
- A tab group shows one dock at a time, and the edge rails act as its tabs. Opening a dock with `open_in_group`, its
  key, its toggle action or a mouse drop into a group closes the group's other docks and moves the dock to the front
  of the group's tab order. A dock in the background of a group is closed. `show` opens a dock without closing the
  others, so code opens docks with `open_in_group`.
- Code that moves an open dock out of its group calls `open_next_in_group` first, so the group stays open at its
  size with its next dock in front.
- A docked dock has no title bar; its rail button names it and moves it, and the notch in its upper-left corner
  (`DockNotch`) drags it. A floating dock shows the title bar set with
  `set_floating_title_bar`, or Qt's without one, and is dragged by it. `show_title_bar_for_drag` shows Qt's title bar
  while docked, so a rail button or notch drag can hand off to Qt's own dock drag (see `src.ui.window.qt_dock_drag`).
- The dock's owner can set a badge (`set_badge`), a short text its rail buttons draw while the dock is not showing.
- The dock's key (`shortcut_config_key`) opens and focuses the dock, or closes it if it is already open.
- A dock with no content is hidden and its toggle action is hidden too. It remembers whether it was open, and opens
  again when content arrives, unless another dock in its group is open by then.
- `QMainWindow.saveState` identifies docks by object name, so every dock needs a unique, permanent one. Renaming one
  drops its saved placement.
"""
from contextlib import contextmanager
from typing import Iterator, Optional
from weakref import ref

from PySide6.QtCore import QByteArray, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QResizeEvent
from PySide6.QtWidgets import QDockWidget, QMainWindow, QWidget

from src.hotkey_filter import HotkeyFilter
from src.ui.layout.dock_panel import DockPanel
from src.ui.layout.panel_fit import Orientation, orientation_for_dock
from src.ui.window.dock_notch import DockNotch
from src.ui.window.dock_state import SavedGroup, move_dock_in_tab_group, read_dock_groups
from src.ui.window.qt_dock_drag import start_qt_dock_drag


def qt_orientation(orientation: Orientation) -> Qt.Orientation:
    """Returns the `Qt.Orientation` that unmigrated panels' `set_orientation` expects: vertical for side panels."""
    return Qt.Orientation.Vertical if orientation == Orientation.SIDE else Qt.Orientation.Horizontal


class _NoTitleBar(QWidget):
    """The title bar of a docked dock: empty, so Qt draws none.

    `QDockWidget` adds its title bar's size hint to the dock's minimum size. A plain widget's invalid (-1, -1) hint
    would shrink that minimum below the content's, so the hint is zero.
    """

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns an empty size."""
        return QSize(0, 0)

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns an empty size."""
        return QSize(0, 0)


class PanelDock(QDockWidget):
    """Hosts one panel, forwards orientation and size to it, and toggles it from a key."""

    _drop_rule_pauses = 0

    badge_changed = Signal()
    # Emitted after the dock moves within its tab group's order, which Qt reports with no signal of its own:
    tab_order_changed = Signal()

    @property
    def _window(self) -> QMainWindow:
        # Held weakly, since the window holds this object:
        window = self._window_ref()
        assert window is not None, 'A dock outlived its window'
        return window

    def __init__(self, title: str, object_name: str, window: QMainWindow, icon: Optional[QIcon] = None,
                 shortcut_config_key: Optional[str] = None) -> None:
        super().__init__(title, window)
        self._window_ref = ref(window)
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
        self._badge_text = ''
        self._badge_tooltip = ''
        # The orientation last reported to content with `set_orientation`:
        self._orientation: Optional[Orientation] = None
        self._no_title_bar = _NoTitleBar()
        self._floating_title_bar: Optional[QWidget] = None
        self.setTitleBarWidget(self._no_title_bar)
        self._notch = DockNotch(self, self._start_notch_drag)
        self._notch.move(0, 0)
        self._notch.raise_()
        self.toggleViewAction().setVisible(False)
        self.toggleViewAction().setIcon(self.windowIcon())
        self.visibilityChanged.connect(self._visibility_changed)
        self.dockLocationChanged.connect(self._update_host_facts)
        self.topLevelChanged.connect(self._update_host_facts)
        self.topLevelChanged.connect(self._top_level_changed)
        self.topLevelChanged.connect(self._update_title_bar)
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
    def badge_text(self) -> str:
        """Short text the dock's rail buttons show as a badge while the dock is not showing, or '' for none."""
        return self._badge_text

    @property
    def badge_tooltip(self) -> str:
        """Tooltip line describing the badge, or '' for none."""
        return self._badge_tooltip

    def set_badge(self, text: str, tooltip: str = '') -> None:
        """Sets the badge text and its tooltip line. Empty text removes the badge."""
        if text != self._badge_text or tooltip != self._badge_tooltip:
            self._badge_text = text
            self._badge_tooltip = tooltip
            self.badge_changed.emit()

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
        self._orientation = None
        if content is None:
            self.toggleViewAction().setVisible(False)
            self.hide()
            return
        self.setWidget(content)
        content.show()
        self._notch.raise_()
        self.toggleViewAction().setVisible(True)
        if self._open_when_available:
            if any(not mate.isHidden() for mate in self.group_mates()):
                self._open_when_available = False
            else:
                self.show()
        self._update_host_facts()

    def _saved_group(self) -> Optional[SavedGroup]:
        """Returns this dock's tab group in the current layout, or None if it isn't in the layout."""
        groups = read_dock_groups(self._window.saveState().data())
        name = self.objectName()
        return next((group for group in groups or [] if any(dock.name == name for dock in group.docks)), None)

    def group(self) -> list['PanelDock']:
        """Returns the docks in this dock's tab group, this one included, open or closed, in tab order. A floating
        dock's group is itself alone, and floating docks are left out of other groups."""
        if self.isFloating():
            return [self]
        group = self._saved_group()
        if group is None:
            return [self]
        docks = {dock.objectName(): dock for dock in
                 self._window.findChildren(PanelDock, options=Qt.FindChildOption.FindDirectChildrenOnly)}
        members = [docks.get(saved.name) for saved in group.docks]
        return [dock for dock in members if dock is self or (dock is not None and not dock.isFloating())]

    def group_mates(self) -> list['PanelDock']:
        """Returns the other docks in this dock's tab group, open or closed, in tab order. A floating dock has none, and
        floating docks are left out."""
        return [dock for dock in self.group() if dock is not self]

    def open_in_group(self) -> None:
        """Opens the dock in front of its tab group, closes the group's other docks, and moves the dock to the front
        of the group's tab order."""
        self.show()
        self.raise_()
        for mate in self.group_mates():
            mate.set_open(False)
        self._move_to_group_front()

    def open_next_in_group(self) -> Optional['PanelDock']:
        """Opens the first other dock with content in this dock's tab group, behind this one, if this dock is open and
        docked, and returns it. Call before moving an open dock out of its group, so the group keeps its place and
        size."""
        if self.isHidden() or self.isFloating():
            return None
        successor = next((mate for mate in self.group_mates() if mate.is_available), None)
        if successor is not None and successor.isHidden():
            successor.show()
            return successor
        return None

    def move_in_group(self, before: Optional['PanelDock']) -> bool:
        """Moves the dock within its tab group's order, just before another dock of the group, or to the group's end
        with None. Returns whether the order changed."""
        return self._move_before(None if before is None else before.objectName())

    def _move_before(self, before: Optional[str]) -> bool:
        state = self._window.saveState().data()
        moved = move_dock_in_tab_group(state, self.objectName(), before)
        if moved is None or moved == state:
            return False
        with PanelDock.placing_docks():
            self._window.restoreState(QByteArray(moved))
        self.tab_order_changed.emit()
        return True

    def _move_to_group_front(self) -> None:
        if self.isFloating():
            return
        group = self._saved_group()
        if group is not None and len(group.docks) > 1 and group.docks[0].name != self.objectName():
            self._move_before(group.docks[0].name)

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
        """Updates the content's orientation and size."""
        super().resizeEvent(event)
        self._notch.raise_()
        self._update_host_facts()

    def _start_notch_drag(self, global_pos: QPoint) -> None:
        start_qt_dock_drag(self._window, self, global_pos)

    @property
    def notch(self) -> DockNotch:
        """The corner triangle that drags the dock while it is docked."""
        return self._notch

    def show_title_bar_for_drag(self) -> None:
        """Shows Qt's title bar while docked, so a press on it starts Qt's dock drag. The bar hides again once the
        dock is docked, or with `restore_title_bar`."""
        self.setTitleBarWidget(None)

    def set_floating_title_bar(self, title_bar: Optional[QWidget]) -> None:
        """Sets the title bar shown while floating, or Qt's with None. Mouse events the bar ignores reach the dock,
        so pressing on its empty space drags the dock."""
        self._floating_title_bar = title_bar
        self.restore_title_bar()

    def restore_title_bar(self) -> None:
        """Shows the floating title bar while floating, and none while docked."""
        self._update_title_bar(self.isFloating())

    def _update_title_bar(self, floating: bool) -> None:
        wanted = self._floating_title_bar if floating else self._no_title_bar
        if self.titleBarWidget() is not wanted:
            self.setTitleBarWidget(wanted)
        self._notch.setVisible(not floating)
        self._notch.raise_()

    def _toggle_action_triggered(self, checked: bool) -> None:
        """Closes the group's other docks when the toggle action opens this one."""
        if checked and self._content is not None:
            self.open_in_group()

    def _top_level_changed(self, floating: bool) -> None:
        """Brings a dock dropped into a tab group to the front, as `open_in_group` does.

        Qt is still placing the dock when it reports the change, so the tab order changes once control returns to
        the event loop.
        """
        if not floating and PanelDock._drop_rule_pauses == 0 and not self.isHidden():
            for mate in self.group_mates():
                mate.set_open(False)
            QTimer.singleShot(0, self, self._move_dropped_dock_to_front)

    def _move_dropped_dock_to_front(self) -> None:
        if not self.isHidden():
            self._move_to_group_front()

    def _visibility_changed(self, visible: bool) -> None:
        self._showing = visible
        if visible:
            self._update_host_facts()

    def _update_host_facts(self, *_args) -> None:
        if self._content is None:
            return
        if isinstance(self._content, DockPanel):
            self._content.set_host_facts(self._content.size())
            return
        orientation = orientation_for_dock(self._window.dockWidgetArea(self), self.isFloating(), self.size(),
                                           self._orientation)
        changed = orientation != self._orientation
        self._orientation = orientation
        if changed and hasattr(self._content, 'set_orientation'):
            self._content.set_orientation(qt_orientation(orientation))
