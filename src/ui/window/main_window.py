"""
The primary image editing window: the canvas in the center, with every other panel in a `PanelDock` around it.

- Docks float, tabify and nest freely. Their arrangement is saved with `saveState` (`save_dock_state`) and restored
  once at startup with `restore_dock_state`. `__init__` lays out the first-run layout, which stays when nothing is
  saved or a restore fails.
- Qt retires a dock group's old tab bar only when a dock is dropped by mouse, so each layout built in code leaves a
  stale bar. One `restoreState` and any number of `reset_dock_layout` calls leave theirs parked outside the window,
  but a second layout built before the window is first shown leaves one drawn over it. `__init__` lays docks out
  once for that reason.
- The Tools, Image Generation and ControlNet docks always exist, so a restore can place them even before their
  generator provides content. A dock without content stays hidden (see `PanelDock.set_content`).
- Icon rails along the window edges (`DockRails`) hold each dock's button, the recent tools and Generate.
- Right-clicking a dock's tab, title area or rail button opens its menu (`build_dock_menu`).
- While the generated image selector replaces the canvas, every dock and rail hides, and the layout from before comes
  back when it closes.
"""
import logging
import sys
from enum import StrEnum
from typing import Callable, Optional

from PySide6.QtCore import Qt, QPoint, QRect, QSize, QObject, QTimer, Signal, QByteArray
from PySide6.QtGui import QContextMenuEvent, QIcon, QMouseEvent, QResizeEvent, QKeySequence, QCloseEvent, QImage, \
    QAction, QMoveEvent, QScreen, QShowEvent
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QApplication, QSizePolicy, QMenu, QTabBar, QTabWidget, \
    QWidget

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.image.layers.image_stack import ImageStack
from src.ui.generated_image_selector import GeneratedImageSelector
from src.ui.panel.image_panel import ImagePanel
from src.ui.panel.layer_ui.layer_panel import LayerPanel

from src.controller.tool_controller import ToolController
from src.ui.widget.loading_widget import LoadingWidget
from src.ui.window.dock_menu import DockEdge, build_dock_menu, move_all_to_edge
from src.ui.window.dock_rail import DockGroup, DockRails, RailButton
from src.ui.window.navigation_window import NavigationWindow
from src.ui.window.panel_dock import PanelDock
from src.ui.window.window_geometry import capture_geometry
from src.util.application_state import AppStateTracker, APP_STATE_LOADING, APP_STATE_NO_IMAGE, APP_STATE_EDITING, \
    APP_STATE_SELECTION
from src.util.visual.display_size import get_screen_size
from src.util.shared_constants import TIMELAPSE_MODE_FLAG, APP_ICON_PATH, PROJECT_DIR
from src.util.validation import layout_debug

logger = logging.getLogger(__name__)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.window.main_window'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


TOOLS_DOCK_TITLE = _tr('Tools')
GENERATION_DOCK_TITLE = _tr('Image Generation')
CONTROLNET_DOCK_TITLE = _tr('ControlNet')
LAYERS_DOCK_TITLE = _tr('Layers')
COLOR_DOCK_TITLE = _tr('Color')
NAVIGATION_DOCK_TITLE = _tr('Navigation')

DEFAULT_LOADING_MESSAGE = _tr('Loading...')

CLAMP_DELAY_MS = 50

ICON_PATH_TOOLS_DOCK = f'{PROJECT_DIR}/resources/icons/tabs/wrench.svg'
ICON_PATH_GENERATION_DOCK = f'{PROJECT_DIR}/resources/icons/tabs/sparkle.svg'
ICON_PATH_CONTROLNET_DOCK = f'{PROJECT_DIR}/resources/icons/tabs/hex.svg'
ICON_PATH_LAYERS_DOCK = f'{PROJECT_DIR}/resources/icons/tabs/layers.svg'
ICON_PATH_COLOR_DOCK = f'{PROJECT_DIR}/resources/icons/tabs/colors.svg'
ICON_PATH_NAVIGATION_DOCK = f'{PROJECT_DIR}/resources/icons/tabs/navigation.svg'

# A saved dock layout carries this version, and `restore_dock_state` rejects any other. Increase it when the docks
# change in a way an older layout can't describe.
DOCK_STATE_VERSION = 2

# First-run dock sizes, across the dock area: width for a side area, height for a strip area.
DEFAULT_SIDE_DOCK_WIDTH = 340
DEFAULT_STRIP_DOCK_HEIGHT = 240

# First-run share of a side area's height (or a strip area's width) that the upper dock group takes:
UPPER_GROUP_SHARE = 0.6


class DockID(StrEnum):
    """The main window's dock object names. `saveState` stores placement by name, so renaming one drops it."""
    TOOLS = 'tools_dock'
    GENERATION = 'generation_dock'
    CONTROLNET = 'controlnet_dock'
    LAYERS = 'layers_dock'
    COLOR = 'color_dock'
    NAVIGATION = 'navigation_dock'


class MainWindow(QMainWindow):
    """Main user interface for inpainting."""

    generate_signal = Signal()
    cancel_generation = Signal()
    previous_options_available = Signal(bool)
    """Emitted when `can_restore_previous_options` changes."""

    def __init__(self, image_stack: ImageStack):
        """Builds the window around the canvas, with empty docks in the first-run layout.

        image_stack : ImageStack
            Image layers being edited.
        """
        super().__init__()
        # Called on every close request; returning False keeps the window open. None closes without asking.
        self.confirm_close: Optional[Callable[[], bool]] = None
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))
        self.setMinimumSize(QSize(0, 0))
        # One coalesced re-clamp for every move, resize and display change:
        self._clamp_timer = QTimer(self)
        self._clamp_timer.setSingleShot(True)
        self._clamp_timer.setInterval(CLAMP_DELAY_MS)
        self._clamp_timer.timeout.connect(self._clamp_to_screen)
        self._watched_displays: set[QObject] = set()
        self._display_signals_connected = False

        if '--dev' in sys.argv:
            def _dbg_layout():
                layout_debug(self)
                return True
            HotkeyFilter.instance().register_keybinding('Debug_layout_dump', _dbg_layout, QKeySequence('Alt+U'))

        # Initialize UI/editing data model:
        self._image_stack = image_stack
        self._image_selector: Optional[GeneratedImageSelector] = None
        self._previous_options_available = False

        # The central widget shows the canvas, or the generated image selector in its place:
        self._image_panel = ImagePanel(image_stack, include_rulers=True)
        self._image_panel.setContentsMargins(1, 1, 1, 1)
        self._main_widget = self._image_panel
        self._central_widget = QStackedWidget(self)
        self._central_widget.addWidget(self._main_widget)
        self.setCentralWidget(self._central_widget)
        self._central_widget.setCurrentWidget(self._main_widget)
        # The dock layout from before the image selector hid the docks:
        self._dock_state_before_selector: Optional[QByteArray] = None
        self._docks_open_before_selector: list[PanelDock] = []
        self._docks_showing_before_selector: list[PanelDock] = []

        # Loading indicator:
        self._is_loading = False
        self._loading_widget = LoadingWidget()
        screen_size = get_screen_size(self)
        if TIMELAPSE_MODE_FLAG in sys.argv:
            # Show spinner in a new window so timelapse footage isn't mostly loading screens:
            self._loading_widget.setGeometry(50, screen_size.height() - 350, 300, 300)
            self._loading_widget.show()
            self._loading_widget.paused = True
        else:
            self._loading_widget.setParent(self)
            self._loading_widget.setGeometry(self.frameGeometry())
            self._loading_widget.hide()

            def _show_spinner_when_busy(app_state: str) -> None:
                self.set_is_loading(app_state == APP_STATE_LOADING)
            AppStateTracker.signal().connect(_show_spinner_when_busy)

        # Docks:
        self.setDockNestingEnabled(True)
        # `dock_menu._settle` finds each group's tab bar above its docks, so it changes with this:
        self.setTabPosition(Qt.DockWidgetArea.AllDockWidgetAreas, QTabWidget.TabPosition.North)
        # Top and bottom areas span the full window width:
        self.setCorner(Qt.Corner.TopLeftCorner, Qt.DockWidgetArea.TopDockWidgetArea)
        self.setCorner(Qt.Corner.TopRightCorner, Qt.DockWidgetArea.TopDockWidgetArea)
        self.setCorner(Qt.Corner.BottomLeftCorner, Qt.DockWidgetArea.BottomDockWidgetArea)
        self.setCorner(Qt.Corner.BottomRightCorner, Qt.DockWidgetArea.BottomDockWidgetArea)
        self._tools_dock = PanelDock(TOOLS_DOCK_TITLE, DockID.TOOLS, self, QIcon(ICON_PATH_TOOLS_DOCK),
                                     KeyConfig.SELECT_TOOL_TAB)
        self._generation_dock = PanelDock(GENERATION_DOCK_TITLE, DockID.GENERATION, self,
                                          QIcon(ICON_PATH_GENERATION_DOCK), KeyConfig.SELECT_GENERATOR_TAB)
        self._controlnet_dock = PanelDock(CONTROLNET_DOCK_TITLE, DockID.CONTROLNET, self,
                                          QIcon(ICON_PATH_CONTROLNET_DOCK), KeyConfig.SELECT_CONTROLNET_TAB)
        self._layers_dock = PanelDock(LAYERS_DOCK_TITLE, DockID.LAYERS, self, QIcon(ICON_PATH_LAYERS_DOCK))
        self._color_dock = PanelDock(COLOR_DOCK_TITLE, DockID.COLOR, self, QIcon(ICON_PATH_COLOR_DOCK))
        self._navigation_dock = PanelDock(NAVIGATION_DOCK_TITLE, DockID.NAVIGATION, self,
                                          QIcon(ICON_PATH_NAVIGATION_DOCK))
        self._rails = DockRails(self)
        for dock in self.upper_docks:
            self._rails.add_dock(dock, DockGroup.UPPER)
        for dock in self.lower_docks:
            self._rails.add_dock(dock, DockGroup.LOWER)
        self._rails.set_tools_dock(self._tools_dock)
        self._rails.set_generation_dock(self._generation_dock)
        self._rails.generate_button.clicked.connect(self.generate_signal)
        self.reset_dock_layout()

        # Optional extra windows:
        self._layer_panel: Optional[LayerPanel] = None
        self._navigation_window = NavigationWindow(image_stack, self._image_panel.image_viewer)

        AppStateTracker.set_enabled_states(self._image_panel, [APP_STATE_EDITING])
        self.resizeEvent(None)

    @property
    def upper_docks(self) -> list[PanelDock]:
        """Returns the docks tabified in the upper group of the first-run layout, in tab order."""
        return [self._tools_dock, self._generation_dock, self._controlnet_dock]

    @property
    def lower_docks(self) -> list[PanelDock]:
        """Returns the docks tabified in the lower group of the first-run layout, in tab order."""
        return [self._layers_dock, self._color_dock, self._navigation_dock]

    @property
    def docks(self) -> list[PanelDock]:
        """Returns every dock, upper group first."""
        return [*self.upper_docks, *self.lower_docks]

    @property
    def layers_dock(self) -> PanelDock:
        """Returns the dock holding the layer panel."""
        return self._layers_dock

    @property
    def color_dock(self) -> PanelDock:
        """Returns the dock holding the color picker."""
        return self._color_dock

    @property
    def navigation_dock(self) -> PanelDock:
        """Returns the dock holding the navigation panel."""
        return self._navigation_dock

    @property
    def tools_dock(self) -> PanelDock:
        """Returns the dock holding the tool panel."""
        return self._tools_dock

    @property
    def generation_dock(self) -> PanelDock:
        """Returns the dock holding the active generator's control panel."""
        return self._generation_dock

    @property
    def controlnet_dock(self) -> PanelDock:
        """Returns the dock holding the ControlNet panel, empty unless the active generator supports ControlNet."""
        return self._controlnet_dock

    def set_tool_controller(self, tool_controller: ToolController) -> None:
        """Shows the controller's recent tools in the rail of the Tools dock."""
        self._rails.set_tool_controller(tool_controller)

    @property
    def rails(self) -> DockRails:
        """Returns the icon rails along the window edges."""
        return self._rails

    def dock_toggle_actions(self) -> list[QAction]:
        """Returns each dock's show/hide action, for the menu. An action is hidden while its dock has no content."""
        return [dock.toggleViewAction() for dock in self.docks]

    def move_all_docks_to_edge(self, edge: DockEdge) -> None:
        """Moves every dock that has content into one tab group along a window edge."""
        move_all_to_edge(self, self.docks, edge)

    def dock_menu(self, dock: PanelDock) -> QMenu:
        """Builds the context menu for a dock (see `build_dock_menu`)."""
        return build_dock_menu(self, dock, self.docks)

    def dock_at(self, widget: Optional[QWidget], global_pos: QPoint) -> Optional[PanelDock]:
        """Returns the dock whose tab, title area or rail button is at a screen position, given the widget there."""
        while widget is not None and widget is not self:
            if isinstance(widget, RailButton):
                return widget.dock
            if isinstance(widget, QTabBar) and widget.parent() is self:
                tab_index = widget.tabAt(widget.mapFromGlobal(global_pos))
                if tab_index < 0:
                    return None
                tab_text = widget.tabText(tab_index)
                return next((dock for dock in self.docks if dock.windowTitle() == tab_text), None)
            if isinstance(widget, PanelDock):
                content = widget.content
                if content is not None and widget.mapFromGlobal(global_pos).y() >= content.geometry().top():
                    return None
                return widget
            widget = widget.parentWidget()
        return None

    def contextMenuEvent(self, event: Optional[QContextMenuEvent]) -> None:  # pylint: disable=invalid-name
        """Shows the dock menu over a dock's tab, title area or rail button, and Qt's own menu elsewhere."""
        if event is None:
            return
        dock = self.dock_at(QApplication.widgetAt(event.globalPos()), event.globalPos())
        if dock is None:
            super().contextMenuEvent(event)
            return
        menu = self.dock_menu(dock)
        menu.exec(event.globalPos())
        menu.deleteLater()

    def reset_dock_layout(self) -> None:
        """Puts every dock back in the first-run layout and opens it.

        The upper docks (Tools, Image generation, ControlNet) are tabified in the right area, or in the bottom area
        on a screen taller than wide, with Tools in front. The lower docks (Layers, Color, Navigation) are tabified
        in a second group under it, or beside it in the bottom area, with Layers in front. Any dock can be dragged
        into either group.
        """
        self.set_image_selector_visible(False)
        screen_size = get_screen_size(self)
        portrait = screen_size.height() > screen_size.width()
        area = Qt.DockWidgetArea.BottomDockWidgetArea if portrait else Qt.DockWidgetArea.RightDockWidgetArea
        group_split = Qt.Orientation.Horizontal if portrait else Qt.Orientation.Vertical
        first_dock = self.upper_docks[0]
        first_lower_dock = self.lower_docks[0]
        # Each dock is shown while it is placed, and docks are moved without removeDockWidget. Tabifying hidden docks,
        # or removing and re-adding tabified ones, leaves stale tab bars drawn over the window. The upper group is
        # placed first, then the lower group after it in the split direction. Without that direction, or when
        # splitting after tabifying, Qt merges the groups into one tab bar.
        for dock in self.docks:
            dock.hide()
        for docks in (self.upper_docks, self.lower_docks):
            for dock in docks:
                dock.setFloating(False)
                self.addDockWidget(area, dock, group_split)
                dock.show()
            for dock in docks[1:]:
                dock.hide()
            for dock in docks[1:]:
                self.tabifyDockWidget(docks[0], dock)
                dock.show()
        group_docks = [first_dock, first_lower_dock]
        group_sizes = [UPPER_GROUP_SHARE, 1 - UPPER_GROUP_SHARE]
        if portrait:
            self.resizeDocks([first_dock], [DEFAULT_STRIP_DOCK_HEIGHT], Qt.Orientation.Vertical)
            self.resizeDocks(group_docks, [round(size * 1000) for size in group_sizes], Qt.Orientation.Horizontal)
        else:
            self.resizeDocks([first_dock], [DEFAULT_SIDE_DOCK_WIDTH], Qt.Orientation.Horizontal)
            self.resizeDocks(group_docks, [round(size * 1000) for size in group_sizes], Qt.Orientation.Vertical)
        first_lower_dock.raise_()
        first_dock.raise_()
        for dock in self.docks:
            dock.set_open(True)
            dock.sync_availability()
        self._rails.sync()

    def save_dock_state(self) -> str:
        """Returns the dock layout as text for `restore_dock_state`, as it was before the image selector hid it."""
        state = self._dock_state_before_selector if self._dock_state_before_selector is not None \
            else self._save_state_with_waiting_docks()
        return state.toBase64().data().decode()

    def restore_dock_state(self, saved_state: str) -> bool:
        """Restores a layout from `save_dock_state`, returning whether it did.

        Call it once, at startup, after restoring the window geometry so docks are fitted to the restored window size.
        Qt keeps docks inside the window and moves floating docks onto a current display. Empty, invalid or
        wrong-version text leaves the first-run layout from `__init__` in place.
        """
        if saved_state == '':
            return False
        # A failed restore changes nothing, so the first-run layout from __init__ stays:
        if not self.restoreState(QByteArray.fromBase64(saved_state.encode()), DOCK_STATE_VERSION):
            logger.warning('Could not restore the saved panel layout, using the default layout')
            return False
        for dock in self.docks:
            dock.sync_availability()
        self._rails.sync()
        return True

    def _save_state_with_waiting_docks(self) -> QByteArray:
        """Saves the dock layout with each empty dock that would open once filled shown, so it reopens after a restart
        even if its generator wasn't connected at exit."""
        waiting = [dock for dock in self.docks if not dock.is_available and dock.open_when_available]
        for dock in waiting:
            dock.show()
        state = self.saveState(DOCK_STATE_VERSION)
        for dock in waiting:
            dock.hide()
        return state

    @property
    def navigation_window(self) -> NavigationWindow:
        """Access the navigation window."""
        return self._navigation_window

    def show_navigation_window(self) -> None:
        """Show or raise the navigation window."""
        if not self._navigation_window.isVisible():
            Cache().load_bounds(Cache.SAVED_NAVIGATION_WINDOW_POS, self._navigation_window)
            self._navigation_window.show()
            self._navigation_window.raise_()

    def is_image_selector_visible(self) -> bool:
        """Returns whether the generated image selection screen is showing."""
        return hasattr(self, '_image_selector') and self._central_widget.currentWidget() == self._image_selector

    def _ensure_image_selector(self) -> GeneratedImageSelector:
        """Returns the generated image selection screen, creating it on first use."""
        if self._image_selector is None:
            self._image_selector = GeneratedImageSelector(self._image_stack,
                                                          lambda: self.set_image_selector_visible(False))
            self._image_selector.cancel_generation.connect(self.cancel_generation)
            self._image_selector.previous_options_available.connect(self._report_previous_options_available)
        return self._image_selector

    def set_image_selector_visible(self, visible: bool):
        """Shows or hides the generated image selection screen.

        Showing it displays whichever batch the selector holds. To pick the batch, call `show_generated_options` or
        `restore_previous_image_selection_options` instead.
        """
        is_visible = self.is_image_selector_visible()
        if visible == is_visible:
            return
        if visible:
            selector = self._ensure_image_selector()
            AppStateTracker.set_app_state(APP_STATE_SELECTION)
            self._dock_state_before_selector = self._save_state_with_waiting_docks()
            self._docks_open_before_selector = [dock for dock in self.docks if not dock.isHidden()]
            self._docks_showing_before_selector = [dock for dock in self._docks_open_before_selector
                                                   if dock.is_showing]
            for dock in self.docks:
                dock.hide()
            self._rails.set_suspended(True)
            self._central_widget.addWidget(selector)
            self._central_widget.setCurrentWidget(selector)
            self.installEventFilter(selector)
        else:
            assert self._image_selector is not None
            # Stores the batch for re-opening when the selector didn't close itself, as when a generation fails:
            self._image_selector.archive_current_options()
            AppStateTracker.set_app_state(APP_STATE_EDITING)
            self.removeEventFilter(self._image_selector)
            self._central_widget.setCurrentWidget(self._main_widget)
            self._central_widget.removeWidget(self._image_selector)
            self._rails.set_suspended(False)
            # Hidden docks keep their place, so showing them again brings the layout back without rebuilding it:
            for dock in self._docks_open_before_selector:
                if dock.is_available:
                    dock.show()
            # Qt forgets split sizes while every dock in an area is hidden, so the saved sizes are put back:
            if self._dock_state_before_selector is not None:
                self.restoreState(self._dock_state_before_selector, DOCK_STATE_VERSION)
                for dock in self.docks:
                    dock.sync_availability()
            for dock in self._docks_showing_before_selector:
                dock.raise_()
            self._dock_state_before_selector = None
            self._docks_open_before_selector = []
            self._docks_showing_before_selector = []
        self._report_previous_options_available()

    def show_generated_options(self, paste_mask: Optional[QImage] = None) -> None:
        """Shows the selection screen for a generation that is starting, with placeholders for the results.

        Inpainted results are clipped by paste_mask when applied, or by the selection if it is None.
        """
        self._ensure_image_selector().start_new_options(paste_mask)
        self.set_image_selector_visible(True)

    def can_restore_previous_options(self) -> bool:
        """Returns whether the selection screen is hidden and has a stored batch it can show again."""
        if self._image_selector is None:
            return False
        return not self.is_image_selector_visible() and self._image_selector.can_restore_previous()

    def restore_previous_image_selection_options(self) -> None:
        """Re-opens the selection screen showing the last batch of generated options."""
        # Batches are only stored in the selector, so it exists if one is stored:
        assert self._image_selector is not None
        self._image_selector.restore_previous_options()
        self.set_image_selector_visible(True)

    def _report_previous_options_available(self, _available: Optional[bool] = None) -> None:
        """Emits `previous_options_available` when `can_restore_previous_options` changes.

        `_available` is the selector's own value, which ignores whether the selection screen is showing.
        """
        available = self.can_restore_previous_options()
        if available != self._previous_options_available:
            self._previous_options_available = available
            self.previous_options_available.emit(available)

    def load_sample_preview(self, image: QImage, idx: int) -> None:
        """Adds an image to the generated image selection screen, or drops it if the screen is hidden.

        Closing the screen removes the batch's placeholders, so a result arriving after that has no slot to fill.
        """
        if self._image_selector is None:
            logger.error(f'Tried to load sample {idx} after sampleSelector was closed')
        elif not self.is_image_selector_visible():
            logger.info(f'Dropped sample {idx}: the selection screen closed before it arrived')
        else:
            self._image_selector.add_image_option(image, idx)

    def set_is_loading(self, is_loading: bool, message: Optional[str] = None) -> None:
        """Sets whether the loading spinner is shown, optionally setting loading spinner message text."""
        if is_loading:
            AppStateTracker.set_app_state(APP_STATE_LOADING)
            self._loading_widget.show()
            self._loading_widget.raise_()
            self._loading_widget.message = message if message is not None else DEFAULT_LOADING_MESSAGE
        else:
            if AppStateTracker.app_state() == APP_STATE_LOADING:
                if self.is_image_selector_visible():
                    AppStateTracker.set_app_state(APP_STATE_SELECTION)
                elif self._image_stack.has_image:
                    AppStateTracker.set_app_state(APP_STATE_EDITING)
                else:
                    AppStateTracker.set_app_state(APP_STATE_NO_IMAGE)
            if TIMELAPSE_MODE_FLAG in sys.argv:
                self._loading_widget.paused = True
            else:
                self._loading_widget.hide()
        self._is_loading = is_loading
        self.update()

    def set_loading_message(self, message: str) -> None:
        """Sets the loading spinner message text."""
        if self._loading_widget.isVisible():
            self._loading_widget.message = message

    def _clamp_to_screen(self) -> None:
        """Shrinks the window to the available size of the display it is on."""
        screen_size = get_screen_size(self, False)
        if screen_size.isNull():
            return
        window_size = self.frameGeometry().size()
        if window_size.width() > screen_size.width() or window_size.height() > screen_size.height():
            self.resize(min(window_size.width(), screen_size.width()),
                        min(window_size.height(), screen_size.height()))

    def _watch_displays(self) -> None:
        """Schedules a re-clamp when the window changes screens or a display's usable area changes."""
        window_handle = self.windowHandle()
        if window_handle is not None and window_handle not in self._watched_displays:
            self._watched_displays.add(window_handle)
            window_handle.screenChanged.connect(self._clamp_timer.start)
        for screen in QApplication.screens():
            if screen not in self._watched_displays:
                self._watched_displays.add(screen)
                screen.availableGeometryChanged.connect(self._clamp_timer.start)
        app = QApplication.instance()
        if app is not None and not self._display_signals_connected:
            self._display_signals_connected = True
            app.screenAdded.connect(self._on_screens_changed)
            app.screenRemoved.connect(self._on_screens_changed)

    def _on_screens_changed(self, unused_screen: Optional[QScreen] = None) -> None:
        self._watch_displays()
        self._clamp_timer.start()

    def showEvent(self, event: Optional[QShowEvent]) -> None:
        """Starts watching display changes once the window has a native handle."""
        super().showEvent(event)
        self._watch_displays()

    def moveEvent(self, unused_event: Optional[QMoveEvent]) -> None:
        """Schedules a re-clamp as the window moves between displays."""
        if self.isVisible():
            self._clamp_timer.start()

    def resizeEvent(self, unused_event: Optional[QResizeEvent]) -> None:
        """Updates the loading indicator bounds and schedules a re-clamp."""
        if self.isVisible():
            self._clamp_timer.start()
        if hasattr(self, '_loading_widget') and TIMELAPSE_MODE_FLAG not in sys.argv:
            loading_widget_size = int(self.height() / 3)
            loading_bounds = QRect(self.width() // 2 - loading_widget_size // 2,
                                   self.height() // 2 - loading_widget_size // 2,
                                   loading_widget_size, loading_widget_size)
            self._loading_widget.setGeometry(loading_bounds)

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Suppresses mouse events when the loading spinner is active."""
        if not self._is_loading:
            super().mousePressEvent(event)

    def closeEvent(self, event: Optional[QCloseEvent]) -> None:
        """Asks `confirm_close` for permission, then closes the application. Ignores the event if it declines."""
        if self.confirm_close is not None and not self.confirm_close():
            if event is not None:
                event.ignore()
            return
        Cache().set(Cache.SAVED_MAIN_WINDOW_GEOMETRY, capture_geometry(self).to_json())
        Cache().set(Cache.SAVED_MAIN_WINDOW_STATE, self.save_dock_state())
        QApplication.exit()

    def close_without_confirmation(self) -> None:
        """Closes the window and exits the application without consulting `confirm_close`."""
        confirm_close = self.confirm_close
        self.confirm_close = None
        try:
            self.close()
        finally:
            self.confirm_close = confirm_close

    @property
    def image_panel(self) -> ImagePanel:
        """Returns the window's ImagePanel."""
        return self._image_panel
