"""
Base implementation of the primary image editing window. On its own, provides an appropriate interface for GLID-3-XL
inpainting modes.  Other editing modes should provide subclasses with implementation-specific controls.
"""
import logging
import sys
from typing import Optional

from PySide6.QtCore import Qt, QRect, QSize, Signal
from PySide6.QtGui import QIcon, QMouseEvent, QResizeEvent, QKeySequence, QCloseEvent, QImage
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QStackedWidget, QApplication, QSizePolicy

from src.config.application_config import AppConfig
from src.hotkey_filter import HotkeyFilter
from src.image.layers.image_stack import ImageStack
from src.ui.generated_image_selector import GeneratedImageSelector
from src.ui.panel.image_panel import ImagePanel
from src.ui.panel.layer_ui.layer_panel import LayerPanel
from src.ui.panel.tool_panel import ToolPanel
from src.ui.layout.draggable_divider import DraggableDivider
from src.ui.layout.draggable_tabs.tab import Tab
from src.ui.layout.draggable_tabs.tab_box import TabBox
from src.ui.widget.loading_widget import LoadingWidget
from src.ui.window.image_window import ImageWindow
from src.util.application_state import AppStateTracker, APP_STATE_LOADING, APP_STATE_NO_IMAGE, APP_STATE_EDITING, \
    APP_STATE_SELECTION
from src.util.display_size import get_screen_size
from src.util.shared_constants import TIMELAPSE_MODE_FLAG, APP_ICON_PATH, PROJECT_DIR
from src.util.validation import layout_debug

logger = logging.getLogger(__name__)

MAIN_TAB_NAME = 'Main'
CONTROL_TAB_NAME = 'Image Generation'
DEFAULT_LOADING_MESSAGE = 'Loading...'
TAB_BOX_STRETCH = 50
IMAGE_PANEL_STRETCH = 300
AUTO_TAB_MOVE_THRESHOLD = 1200
USE_LOWER_CONTROL_TAB_THRESHOLD = 1600

TOP_TAB_BOX_ID = 'TOP'
BOTTOM_TAB_BOX_ID = 'BOTTOM'
LEFT_TAB_BOX_ID = 'LEFT'
RIGHT_TAB_BOX_ID = 'RIGHT'
LOWER_TAB_BOX_ID = 'LOWER'

TOOL_TAB_ICON = f'{PROJECT_DIR}/resources/icons/tabs/wrench.svg'
GEN_TAB_ICON = f'{PROJECT_DIR}/resources/icons/tabs/sparkle.svg'


class MainWindow(QMainWindow):
    """Main user interface for inpainting."""

    generate_signal = Signal()

    def __init__(self, image_stack: ImageStack):
        """Initializes the main application window and sets up the default UI layout and menu options.

        image_stack : ImageStack
            Image layers being edited.
        controller : BaseController
            Object managing application behavior.
        """
        super().__init__()
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))
        self.setMinimumSize(QSize(0, 0))

        if '--dev' in sys.argv:
            def _dbg_layout():
                layout_debug(self)
                return True
            HotkeyFilter.instance().register_keybinding(_dbg_layout, QKeySequence('U'))

        # Initialize UI/editing data model:
        self._image_stack = image_stack
        self._image_selector: Optional[GeneratedImageSelector] = None

        self._layer_panel: Optional[LayerPanel] = None
        self._image_window = ImageWindow(image_stack)

        # Create components, build layout:
        self._main_widget = QWidget(self)
        self._layout = QVBoxLayout(self._main_widget)
        self._layout.setContentsMargins(0, 0, 0, 0)
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
        self._top_tab_box = TabBox(Qt.Orientation.Horizontal, True)
        self._layout.addWidget(self._top_tab_box, stretch=TAB_BOX_STRETCH)
        self._layout.addWidget(DraggableDivider())

        self._image_panel = ImagePanel(image_stack, True)
        self._layout.addWidget(self._image_panel, stretch=IMAGE_PANEL_STRETCH)
        self._layout.addWidget(DraggableDivider())

        self._lower_tab_box = TabBox(Qt.Orientation.Horizontal, False)
        self._layout.addWidget(self._lower_tab_box, stretch=TAB_BOX_STRETCH)
        self._layout.addWidget(DraggableDivider())

        self._bottom_tab_box = TabBox(Qt.Orientation.Horizontal, False)
        self._layout.addWidget(self._bottom_tab_box, stretch=TAB_BOX_STRETCH)

        # Create tabs:
        # TODO: Connect tab placement to config

        # Image/Mask editing layout:
        self._tool_panel = ToolPanel(image_stack, self._image_panel, self.generate_signal.emit)
        self._tool_tab = Tab('Tools', self._tool_panel)
        self._tool_tab.setIcon(QIcon(TOOL_TAB_ICON))

        tab_box = self._get_tab_box(AppConfig().get(AppConfig.TOOL_TAB_BAR))
        if tab_box is None:
            tab_box = self._lower_tab_box if screen_size.height() > AUTO_TAB_MOVE_THRESHOLD \
                else self._image_panel.right_tab_box
            assert tab_box is not None
        tab_box.add_widget(self._tool_tab, 0)

        self._control_panel: Optional[QWidget] = None
        self._control_tab = Tab(CONTROL_TAB_NAME)
        self._control_tab.setIcon(QIcon(GEN_TAB_ICON))

        for tab_box, tab_box_key in ((self._top_tab_box, TOP_TAB_BOX_ID),
                                     (self._lower_tab_box, LOWER_TAB_BOX_ID),
                                     (self._bottom_tab_box, BOTTOM_TAB_BOX_ID),
                                     (self._image_panel.left_tab_box, LEFT_TAB_BOX_ID),
                                     (self._image_panel.right_tab_box, RIGHT_TAB_BOX_ID)):
            assert tab_box is not None

            def _tab_added(tab, key=tab_box_key):
                if tab == self._tool_tab:
                    AppConfig().set(AppConfig.TOOL_TAB_BAR, key)
                elif tab == self._control_tab:
                    AppConfig().set(AppConfig.GENERATION_TAB_BAR, key)
                else:
                    AppConfig().set(AppConfig.CONTROLNET_TAB_BAR, key)
            tab_box.tab_added.connect(_tab_added)

        for panel in (self._image_panel, self._tool_panel):
            AppStateTracker.set_enabled_states(panel, [APP_STATE_EDITING])
        self.resizeEvent(None)

    def set_control_panel(self, control_panel: Optional[QWidget]) -> None:
        """Sets the image generation control panel."""
        assert control_panel is None or control_panel != self._control_panel
        self._control_panel = control_panel
        self._control_tab.content_widget = control_panel
        tab_parent = self._control_tab.parent()
        if tab_parent is None:
            tab_box = self._get_tab_box(AppConfig().get(AppConfig.GENERATION_TAB_BAR))
            if tab_box is None:
                if self.height() > USE_LOWER_CONTROL_TAB_THRESHOLD:
                    tab_box = self._bottom_tab_box
                elif self.height() > AUTO_TAB_MOVE_THRESHOLD:
                    tab_box = self._lower_tab_box
                else:
                    tab_box = self._image_panel.right_tab_box
                assert tab_box is not None
            tab_box.add_widget(self._control_tab)

    def add_tab(self, tab: Tab, tab_box_key: str = '') -> None:
        """Adds a new tab to one of the window's tab boxes."""
        tab_box = self._get_tab_box(tab_box_key)
        if tab_box is None:
            if self.height() > USE_LOWER_CONTROL_TAB_THRESHOLD:
                tab_box = self._bottom_tab_box
            elif self.height() > AUTO_TAB_MOVE_THRESHOLD:
                tab_box = self._lower_tab_box
            else:
                tab_box = self._image_panel.right_tab_box
            assert tab_box is not None
        assert tab_box is not None
        tab_box.add_widget(tab)

    def remove_tab(self, tab: Tab) -> None:
        """Removes a tab if it is found in any of the window's tab boxes."""
        for tab_box in (self._top_tab_box, self._lower_tab_box, self._bottom_tab_box,
                        self._image_panel.left_tab_box, self._image_panel.right_tab_box):
            assert tab_box is not None
            if tab_box.contains_widget(tab):
                tab_box.remove_widget(tab)
                return

    def show_image_window(self) -> None:
        """Show or raise the image window."""
        self._image_window.show()
        self._image_window.raise_()

    def is_image_selector_visible(self) -> bool:
        """Returns whether the generated image selection screen is showing."""
        return hasattr(self, '_image_selector') and self._central_widget.currentWidget() == self._image_selector

    def set_image_selector_visible(self, visible: bool):
        """Shows or hides the generated image selection screen."""
        is_visible = self.is_image_selector_visible()
        if visible == is_visible:
            return
        if visible:
            if self._image_selector is None:
                self._image_selector = GeneratedImageSelector(self._image_stack,
                                                              lambda: self.set_image_selector_visible(False))
            else:
                self._image_selector.reset()
            self._central_widget.addWidget(self._image_selector)
            self._central_widget.setCurrentWidget(self._image_selector)
            self.installEventFilter(self._image_selector)
        else:
            AppStateTracker.set_app_state(APP_STATE_EDITING)
            self.removeEventFilter(self._image_selector)
            self._central_widget.setCurrentWidget(self._main_widget)
            self._central_widget.removeWidget(self._image_selector)

    def load_sample_preview(self, image: QImage, idx: int) -> None:
        """Adds an image to the generated image selection screen."""
        if self._image_selector is None:
            logger.error(f'Tried to load sample {idx} after sampleSelector was closed')
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

    def resizeEvent(self, unused_event: Optional[QResizeEvent]) -> None:
        """Applies the most appropriate layout when the window size changes."""
        screen_size = get_screen_size(self, False)
        if not screen_size.isNull() and screen_size != self.maximumSize():
            self.setMaximumSize(screen_size)
        if hasattr(self, '_loading_widget') and TIMELAPSE_MODE_FLAG not in sys.argv:
            loading_widget_size = int(self.height() / 8)
            loading_bounds = QRect(self.width() // 2 - loading_widget_size // 2, loading_widget_size * 3,
                                   loading_widget_size, loading_widget_size)
            self._loading_widget.setGeometry(loading_bounds)

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Suppresses mouse events when the loading spinner is active."""
        if not self._is_loading:
            super().mousePressEvent(event)

    def closeEvent(self, unused_event: Optional[QCloseEvent]) -> None:
        """Close the application when the main window is closed."""
        QApplication.exit()

    def _get_tab_box(self, tab_box_key: str) -> Optional[TabBox]:
        """Look up a tab box from its expected name in config."""
        if tab_box_key == TOP_TAB_BOX_ID:
            return self._top_tab_box
        if tab_box_key == LOWER_TAB_BOX_ID:
            return self._lower_tab_box
        if tab_box_key == BOTTOM_TAB_BOX_ID:
            return self._bottom_tab_box
        if tab_box_key == LEFT_TAB_BOX_ID:
            return self._image_panel.left_tab_box
        if tab_box_key == RIGHT_TAB_BOX_ID:
            return self._image_panel.right_tab_box
        return None
