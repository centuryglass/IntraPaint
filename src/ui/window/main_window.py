"""
Base implementation of the primary image editing window. On its own, provides an appropriate interface for GLID-3-XL
inpainting modes.  Other editing modes should provide subclasses with implementation-specific controls.
"""
import logging
import sys
from enum import Enum
from typing import Callable, Optional

from enum import StrEnum

from PySide6.QtCore import Qt, QRect, QSize, QObject, QTimer, Signal
from PySide6.QtGui import QIcon, QMouseEvent, QResizeEvent, QKeySequence, QCloseEvent, QImage, QAction, QMoveEvent, \
    QScreen, QShowEvent
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QStackedWidget, QApplication, QSizePolicy

from src.config.cache import Cache
from src.hotkey_filter import HotkeyFilter
from src.image.layers.image_stack import ImageStack
from src.ui.generated_image_selector import GeneratedImageSelector
from src.ui.layout.draggable_divider import DraggableDivider
from src.ui.layout.draggable_tabs.tab import Tab
from src.ui.layout.draggable_tabs.tab_box import TabBox
from src.ui.panel.image_panel import ImagePanel
from src.ui.panel.layer_ui.layer_panel import LayerPanel
from src.ui.panel.tool_panel import ToolPanel
from src.ui.panel.generators.generator_panel import GeneratorPanel

from src.ui.widget.loading_widget import LoadingWidget
from src.ui.window.navigation_window import NavigationWindow
from src.ui.window.window_geometry import capture_geometry
from src.util.application_state import AppStateTracker, APP_STATE_LOADING, APP_STATE_NO_IMAGE, APP_STATE_EDITING, \
    APP_STATE_SELECTION
from src.util.visual.display_size import get_screen_size
from src.util.shared_constants import TIMELAPSE_MODE_FLAG, APP_ICON_PATH
from src.util.validation import layout_debug, all_layout_info

logger = logging.getLogger(__name__)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.window.main_window'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


ACTION_NAME_MOVE_UP = _tr('Move up')
ACTION_NAME_MOVE_DOWN = _tr('Move down')
ACTION_NAME_MOVE_LEFT = _tr('Move left')
ACTION_NAME_MOVE_RIGHT = _tr('Move right')
ACTION_NAME_MOVE_ALL = _tr('Move all tabs here')


DEFAULT_LOADING_MESSAGE = _tr('Loading...')

VERTICAL_STRETCH_SUM = 100
AUTO_TAB_MOVE_THRESHOLD = 1200
USE_LOWER_CONTROL_TAB_THRESHOLD = 1600
CLAMP_DELAY_MS = 50


class TabBoxID(StrEnum):
    """Identifies all available tab box containers."""
    TOP_TAB_BOX_ID = 'TOP'
    BOTTOM_TAB_BOX_ID = 'BOTTOM'
    LEFT_TAB_BOX_ID = 'LEFT'
    RIGHT_TAB_BOX_ID = 'RIGHT'
    LOWER_TAB_BOX_ID = 'LOWER'


class TabMoveActions(Enum):
    """Identifies the menu actions used to move tabs."""
    MOVE_LEFT = 0
    MOVE_RIGHT = 1
    MOVE_UP_TO_TOP = 2
    MOVE_UP_TO_LOWER = 3
    MOVE_DOWN_TO_LOWER = 4
    MOVE_DOWN_TO_BOTTOM = 5

    def display_name(self) -> str:
        """Returns the appropriate action display name."""
        match self:
            case TabMoveActions.MOVE_LEFT:
                return ACTION_NAME_MOVE_LEFT
            case TabMoveActions.MOVE_RIGHT:
                return ACTION_NAME_MOVE_RIGHT
            case TabMoveActions.MOVE_UP_TO_LOWER | TabMoveActions.MOVE_UP_TO_TOP:
                return ACTION_NAME_MOVE_UP
            case _:
                return ACTION_NAME_MOVE_DOWN

    def is_valid_for_tab_box(self, box_id: TabBoxID) -> bool:
        """Returns whether the action type is valid for a tab within a particular tab box"""
        match self:
            case TabMoveActions.MOVE_LEFT:
                return box_id != TabBoxID.LEFT_TAB_BOX_ID
            case TabMoveActions.MOVE_RIGHT:
                return box_id != TabBoxID.RIGHT_TAB_BOX_ID
            case TabMoveActions.MOVE_UP_TO_LOWER:
                return box_id == TabBoxID.BOTTOM_TAB_BOX_ID
            case TabMoveActions.MOVE_UP_TO_TOP:
                return box_id not in (TabBoxID.BOTTOM_TAB_BOX_ID, TabBoxID.TOP_TAB_BOX_ID)
            case TabMoveActions.MOVE_DOWN_TO_BOTTOM:
                return box_id == TabBoxID.LOWER_TAB_BOX_ID
            case _:
                assert self == TabMoveActions.MOVE_DOWN_TO_LOWER
                return box_id not in (TabBoxID.BOTTOM_TAB_BOX_ID, TabBoxID.LOWER_TAB_BOX_ID)

    def destination_tab_box_id(self) -> TabBoxID:
        """Returns the tab box the action moves tabs into."""
        match self:
            case TabMoveActions.MOVE_LEFT:
                return TabBoxID.LEFT_TAB_BOX_ID
            case TabMoveActions.MOVE_RIGHT:
                return TabBoxID.RIGHT_TAB_BOX_ID
            case TabMoveActions.MOVE_UP_TO_LOWER:
                return TabBoxID.LOWER_TAB_BOX_ID
            case TabMoveActions.MOVE_UP_TO_TOP:
                return TabBoxID.TOP_TAB_BOX_ID
            case TabMoveActions.MOVE_DOWN_TO_BOTTOM:
                return TabBoxID.BOTTOM_TAB_BOX_ID
            case _:
                assert self == TabMoveActions.MOVE_DOWN_TO_LOWER
                return TabBoxID.LOWER_TAB_BOX_ID


class MainWindow(QMainWindow):
    """Main user interface for inpainting."""

    generate_signal = Signal()
    cancel_generation = Signal()
    previous_options_available = Signal(bool)
    """Emitted when `can_restore_previous_options` changes."""

    def __init__(self, image_stack: ImageStack):
        """Initializes the main application window and sets up the default UI layout and menu options.

        image_stack : ImageStack
            Image layers being edited.
        controller : BaseController
            Object managing application behavior.
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

        # Create components, build layout:
        self._main_widget = QWidget(self)
        self._layout = QVBoxLayout(self._main_widget)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)
        self._central_widget = QStackedWidget(self)
        self._central_widget.addWidget(self._main_widget)
        self.setCentralWidget(self._central_widget)
        self._central_widget.setCurrentWidget(self._main_widget)

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

        # Main page contents:
        self._last_open_box = TabBoxID.RIGHT_TAB_BOX_ID
        self._top_tab_box = TabBox(Qt.Orientation.Horizontal, True)
        self._layout.addWidget(self._top_tab_box, stretch=1)
        self._top_divider = DraggableDivider()
        self._layout.addWidget(self._top_divider)

        self._image_panel = ImagePanel(image_stack, True, include_rulers=True)
        self._image_panel.setContentsMargins(1, 1, 1, 1)
        self._layout.addWidget(self._image_panel, stretch=VERTICAL_STRETCH_SUM)

        self._lower_divider = DraggableDivider()
        self._layout.addWidget(self._lower_divider)
        self._lower_tab_box = TabBox(Qt.Orientation.Horizontal, False)
        self._layout.addWidget(self._lower_tab_box, stretch=1)

        self._bottom_divider = DraggableDivider()
        self._layout.addWidget(self._bottom_divider)
        self._bottom_tab_box = TabBox(Qt.Orientation.Horizontal, False)
        self._layout.addWidget(self._bottom_tab_box, stretch=1)

        def _show_or_hide_top_divider(_=None) -> None:
            self._top_divider.setVisible(self._top_tab_box.count > 0 and self._top_tab_box.is_open)
        for signal in (self._top_tab_box.box_toggled, self._top_tab_box.tab_added,
                       self._top_tab_box.tab_removed):
            signal.connect(_show_or_hide_top_divider)
        _show_or_hide_top_divider()

        def _show_or_hide_lower_divider(_=None) -> None:
            self._lower_divider.setVisible(self._lower_tab_box.count > 0 and self._lower_tab_box.is_open)
        for signal in (self._lower_tab_box.box_toggled, self._lower_tab_box.tab_added,
                       self._lower_tab_box.tab_removed):
            signal.connect(_show_or_hide_lower_divider)
        _show_or_hide_lower_divider()

        def _show_or_hide_bottom_divider(_=None) -> None:
            self._bottom_divider.setVisible(self._bottom_tab_box.count > 0 and self._bottom_tab_box.is_open)
        for signal in (self._bottom_tab_box.box_toggled, self._bottom_tab_box.tab_added,
                       self._bottom_tab_box.tab_removed):
            signal.connect(_show_or_hide_bottom_divider)
        _show_or_hide_bottom_divider()

        # Optional extra windows:
        self._layer_panel: Optional[LayerPanel] = None
        self._navigation_window = NavigationWindow(image_stack, self._image_panel.image_viewer)

        # Image/Mask editing layout:

        self._tab_actions: dict[Tab, dict[TabMoveActions, QAction]] = {}
        self._tab_bar_actions: list[QAction] = []
        for tab_box_id in TabBoxID:
            assert isinstance(tab_box_id, TabBoxID)
            tab_box = self._get_tab_box(tab_box_id)
            tab_box.box_will_open.connect(self._prepare_for_tab_box_open)

            def _on_open(is_open: bool, box_id=tab_box_id) -> None:
                if is_open:
                    self._tab_open_slot(box_id)
            tab_box.box_toggled.connect(_on_open)

            def _tab_added(tab, box_id=tab_box_id):
                # Remember to update this after adding any new tabs
                if isinstance(tab.content_widget, ToolPanel):
                    Cache().set(Cache.TOOL_TAB_BAR, box_id)
                elif isinstance(tab.content_widget, GeneratorPanel):
                    Cache().set(Cache.GENERATION_TAB_BAR, box_id)
                else:
                    Cache().set(Cache.CONTROLNET_TAB_BAR, box_id)
                self._update_tab_actions(tab, box_id)
            tab_box.tab_added.connect(_tab_added)

            def _move_all(_, box=tab_box, box_id=tab_box_id) -> None:
                all_tabs: list[Tab] = []
                for other_box_id in TabBoxID:
                    assert isinstance(other_box_id, TabBoxID)
                    if other_box_id == box_id:
                        continue
                    other_tab_box = self._get_tab_box(other_box_id)
                    all_tabs += other_tab_box.tabs
                for tab in all_tabs:
                    box.add_widget(tab)
            move_all_action = QAction()
            move_all_action.setText(ACTION_NAME_MOVE_ALL)
            move_all_action.triggered.connect(_move_all)
            tab_box.add_tab_bar_action(move_all_action)
            if '--dev' in sys.argv:  # Developer mode only: add layout debug action
                def _tab_box_debug(_, box=tab_box, box_id=tab_box_id):
                    print(f'\n{box_id} DEBUG:')
                    print('\tBOX:')
                    box_info = all_layout_info(box)
                    for k, v in box_info.items():
                        print(f'\t\t{k}: {v}')
                    print('\tBAR:')
                    # noinspection PyProtectedMember
                    bar_info = all_layout_info(box._tab_bar)
                    for k, v in bar_info.items():
                        print(f'\t\t{k}: {v}')
                debug_action = QAction()
                debug_action.setText('LAYOUT DEBUG')
                debug_action.triggered.connect(_tab_box_debug)
                tab_box.add_tab_bar_action(debug_action)
                self._tab_bar_actions.append(debug_action)
            self._tab_bar_actions.append(move_all_action)

        AppStateTracker.set_enabled_states(self._image_panel, [APP_STATE_EDITING])
        self.resizeEvent(None)

    def _init_tab_actions(self, tab: Tab) -> None:
        if tab not in self._tab_actions:
            self._tab_actions[tab] = {}
        for action_type in TabMoveActions:
            if action_type in self._tab_actions[tab]:
                continue
            new_tab_box = self._get_tab_box(action_type.destination_tab_box_id())
            action_text = action_type.display_name()

            def _move_to_panel(_, moving_tab=tab, destination_box=new_tab_box) -> None:
                destination_box.add_widget(moving_tab)
            action = QAction(action_text)
            action.triggered.connect(_move_to_panel)
            self._tab_actions[tab][action_type] = action

        if '--dev' in sys.argv:  # Developer mode only: add layout debug action
            def _tab_debug(_, dbg_tab=tab):
                print(f'\nTAB "{dbg_tab.text()}" DEBUG:')
                print('\tMAIN:')
                tab_info = all_layout_info(dbg_tab)
                for k, v in tab_info.items():
                    print(f'\t\t{k}: {v}')
                for i, widget in enumerate(dbg_tab.tab_bar_widgets):
                    print(f'\tWIDGET {i}:')
                    widget_info = all_layout_info(widget)
                    for k, v in widget_info.items():
                        print(f'\t\t{k}: {v}')
            tab_action = QAction('TAB DEBUG')
            tab_action.triggered.connect(_tab_debug)
            tab.addAction(tab_action)
            # noinspection PyTypeChecker
            self._tab_actions[tab]['DEBUG'] = tab_action  # type: ignore

    def _update_tab_actions(self, tab: Tab, tab_box_key: TabBoxID) -> None:
        self._init_tab_actions(tab)
        for action_type in TabMoveActions:
            action = self._tab_actions[tab][action_type]
            action_included = action in tab.actions()
            should_include = action_type.is_valid_for_tab_box(tab_box_key)
            if action_included and not should_include:
                tab.removeAction(action)
            elif not action_included and should_include:
                tab.addAction(action)

    def add_tab(self, tab: Tab, tab_box_id: Optional[TabBoxID] = None) -> None:
        """Adds a new tab to one of the window's tab boxes."""
        if tab_box_id is None:
            if self.height() > USE_LOWER_CONTROL_TAB_THRESHOLD:
                tab_box_id = TabBoxID.BOTTOM_TAB_BOX_ID
            elif self.height() > AUTO_TAB_MOVE_THRESHOLD:
                tab_box_id = TabBoxID.LOWER_TAB_BOX_ID
            else:
                tab_box_id = TabBoxID.RIGHT_TAB_BOX_ID
        tab_box = self._get_tab_box(tab_box_id)
        self._update_tab_actions(tab, tab_box_id)
        tab_box.add_widget(tab)

    def remove_tab(self, tab: Tab) -> None:
        """Removes a tab if it is found in any of the window's tab boxes."""
        for tab_box in (self._top_tab_box, self._lower_tab_box, self._bottom_tab_box,
                        self._image_panel.left_tab_box, self._image_panel.right_tab_box):
            assert tab_box is not None
            if tab_box.contains_widget(tab):
                tab_box.remove_widget(tab)
                return

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
        self._report_previous_options_available()

    def show_generated_options(self) -> None:
        """Shows the selection screen for a generation that is starting, with placeholders for the results."""
        self._ensure_image_selector().start_new_options()
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

    def _prepare_for_tab_box_open(self, opening_tab_box: TabBox) -> None:
        """When tabs are arranged across multiple panels, opening a new tab will often make the window extend
           beyond the window bounds. This is obnoxious, so make sure to close other tabs before opening a new one
           if this would happen."""
        assert not opening_tab_box.is_open  # It shouldn't be open yet, otherwise this whole function is irrelevant
        opening_box_id = None
        tab_boxes: dict[TabBoxID, TabBox] = {}
        for box_id_str in TabBoxID:
            tab_box_id = TabBoxID(box_id_str)
            tab_box = self._get_tab_box(tab_box_id)
            if tab_box == opening_tab_box:
                opening_box_id = tab_box_id
            tab_boxes[tab_box_id] = tab_box
        assert opening_box_id is not None
        horizontal_tab_box_ids = [TabBoxID.TOP_TAB_BOX_ID, TabBoxID.BOTTOM_TAB_BOX_ID, TabBoxID.LOWER_TAB_BOX_ID]
        vertical_tab_box_ids = [TabBoxID.LEFT_TAB_BOX_ID, TabBoxID.RIGHT_TAB_BOX_ID]

        parallel_tabs = list(horizontal_tab_box_ids if opening_box_id in horizontal_tab_box_ids
                             else vertical_tab_box_ids)
        parallel_tabs.remove(opening_box_id)
        perpendicular_tabs = horizontal_tab_box_ids if opening_box_id in vertical_tab_box_ids else vertical_tab_box_ids
        to_close: set[TabBox] = set()
        max_size = self.size()
        min_opening_box_size = opening_tab_box.minimum_active_size

        if opening_box_id in horizontal_tab_box_ids:
            perpendicular_width = 0
            perpendicular_height = 0
            parallel_width = 0
            parallel_height = max_size.height() // 6  # Minimum space for the ImageView
            for perpendicular_id in perpendicular_tabs:
                tab_box_min = tab_boxes[perpendicular_id].sizeHint()
                perpendicular_height = max(tab_box_min.height(), perpendicular_height)
                perpendicular_width += tab_box_min.width()
            for parallel_id in parallel_tabs:
                tab_box_min = tab_boxes[parallel_id].sizeHint()
                parallel_width = max(parallel_width, tab_box_min.width())
                parallel_height += tab_box_min.height()
            # Check if height would be exceeded:
            if parallel_height + perpendicular_height + min_opening_box_size.height() > max_size.height():
                for tab_id in perpendicular_tabs:
                    to_close.add(tab_boxes[tab_id])
            if parallel_height + min_opening_box_size.height() >= max_size.height():
                for tab_id in parallel_tabs:
                    to_close.add(tab_boxes[tab_id])
            # Check if width would be exceeded:
            if max(parallel_width, min_opening_box_size.width()) + perpendicular_width > max_size.width():
                for tab_id in perpendicular_tabs:
                    to_close.add(tab_boxes[tab_id])
        else:
            assert opening_box_id in vertical_tab_box_ids
            perpendicular_width = 0
            perpendicular_height = 0
            parallel_width = max_size.width() // 6  # Minimum space for the ImageView
            parallel_height = 0
            for perpendicular_id in perpendicular_tabs:
                tab_box_min = tab_boxes[perpendicular_id].sizeHint()
                perpendicular_height += tab_box_min.height()
                perpendicular_width = max(perpendicular_width, tab_box_min.width())
            for parallel_id in parallel_tabs:
                tab_box_min = tab_boxes[parallel_id].sizeHint()
                parallel_width += tab_box_min.width()
                parallel_height = max(parallel_height, tab_box_min.height())
            # Check if width would be exceeded:
            if parallel_width + perpendicular_width + min_opening_box_size.width() > max_size.width():
                for tab_id in perpendicular_tabs:
                    to_close.add(tab_boxes[tab_id])
            if parallel_width + min_opening_box_size.width() > max_size.width():
                for tab_id in parallel_tabs:
                    to_close.add(tab_boxes[tab_id])
            # Check if height would be exceeded:
            if max(parallel_height, min_opening_box_size.height()) + perpendicular_height > max_size.height():
                for tab_id in perpendicular_tabs:
                    to_close.add(tab_boxes[tab_id])
        for tab_box in to_close:
            tab_box.is_open = False

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

    def _tab_open_slot(self, tab_box_id: TabBoxID):
        """If the screen is too small to fit perpendicular tabs, automatically close them when a new tab opens."""
        self._last_open_box = tab_box_id
        opened_box = self._get_tab_box(tab_box_id)
        if not opened_box.is_open:
            opened_box.is_open = True

    def _get_tab_box(self, tab_box_id: TabBoxID) -> TabBox:
        """Look up a tab box from its expected name in config."""
        match tab_box_id:
            case TabBoxID.TOP_TAB_BOX_ID:
                return self._top_tab_box
            case TabBoxID.LOWER_TAB_BOX_ID:
                return self._lower_tab_box
            case TabBoxID.BOTTOM_TAB_BOX_ID:
                return self._bottom_tab_box
            case TabBoxID.LEFT_TAB_BOX_ID:
                left_box = self._image_panel.left_tab_box
                assert left_box is not None
                return left_box
            case _:
                assert tab_box_id == TabBoxID.RIGHT_TAB_BOX_ID
                right_box = self._image_panel.right_tab_box
                assert right_box is not None
                return right_box
