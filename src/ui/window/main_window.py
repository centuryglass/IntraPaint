"""
Base implementation of the primary image editing window. On its own, provides an appropriate interface for GLID-3-XL
inpainting modes.  Other editing modes should provide subclasses with implementation-specific controls.
"""
import logging
import sys
from typing import Optional, Any

from PyQt6.QtCore import Qt, QRect, QSize
from PyQt6.QtGui import QIcon, QMouseEvent, QResizeEvent, QKeySequence, QCloseEvent, QImage
from PyQt6.QtWidgets import QMainWindow, QGridLayout, QLabel, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, \
    QStackedWidget, QBoxLayout, QApplication, QTabWidget, QSizePolicy, QLayout

from src.config.application_config import AppConfig
from src.hotkey_filter import HotkeyFilter
from src.image.layers.image_stack import ImageStack
from src.ui.generated_image_selector import GeneratedImageSelector
from src.ui.panel.image_panel import ImagePanel
from src.ui.panel.layer_panel import LayerPanel
from src.ui.panel.tool_panel import ToolPanel
from src.ui.widget.loading_widget import LoadingWidget
from src.ui.window.image_window import ImageWindow
from src.util.application_state import AppStateTracker, APP_STATE_LOADING, APP_STATE_NO_IMAGE, APP_STATE_EDITING, \
    APP_STATE_SELECTION
from src.util.display_size import get_screen_size
from src.util.shared_constants import TIMELAPSE_MODE_FLAG, PROJECT_DIR

logger = logging.getLogger(__name__)

MAIN_TAB_NAME = 'Main'
CONTROL_TAB_NAME = 'Image Generation'
CONTROL_PANEL_STRETCH = 5
MAX_TABS = 2
LAYOUT_SWAP_HEIGHT = 1000
LAYOUT_SWAP_BUFFER = 50
DEFAULT_LOADING_MESSAGE = 'Loading...'


class MainWindow(QMainWindow):
    """Main user interface for inpainting."""

    def __init__(self, image_stack: ImageStack, controller: Any):
        """Initializes the main application window and sets up the default UI layout and menu options.

        image_stack : ImageStack
            Image layers being edited.
        controller : BaseController
            Object managing application behavior.
        """
        super().__init__()
        self.setWindowIcon(QIcon(f'{PROJECT_DIR}/resources/icons/app_icon.png'))
        self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))
        self.setMinimumSize(QSize(0, 0))

        # Initialize UI/editing data model:
        self._controller = controller
        self._image_stack = image_stack
        self._image_selector: Optional[GeneratedImageSelector] = None
        self._orientation: Optional[Qt.Orientation] = None

        self._layer_panel: Optional[LayerPanel] = None
        self._image_window = ImageWindow(image_stack)

        # Create components, build layout:
        self._main_widget = QTabWidget(self)
        self._main_widget.setTabBarAutoHide(True)
        self._main_page_tab = QWidget()
        self._main_widget.addTab(self._main_page_tab, MAIN_TAB_NAME)
        self._layout = QVBoxLayout(self._main_page_tab)
        self._reactive_widget: Optional[QWidget] = None
        self._reactive_layout: Optional[QLayout] = None
        self._central_widget = QStackedWidget(self)
        self._central_widget.addWidget(self._main_widget)
        self.setCentralWidget(self._central_widget)
        self._central_widget.setCurrentWidget(self._main_widget)

        # Connect number keys to tabs when tab widget is visible:
        for i in range(min(MAX_TABS, 9)):
            tab_index_key = QKeySequence(str(i + 1))

            def _try_tab_focus(idx=i) -> bool:
                if not self._central_widget.isVisible():
                    return False
                return self.focus_tab(idx)

            HotkeyFilter.instance().register_keybinding(_try_tab_focus, tab_index_key, Qt.KeyboardModifier.NoModifier)
        # Loading widget (for interrogate):
        self._is_loading = False
        self._loading_widget = LoadingWidget()
        if TIMELAPSE_MODE_FLAG in sys.argv:
            # Show spinner in a new window so timelapse footage isn't mostly loading screens:
            screen_size = get_screen_size(self)
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

        # Image/Mask editing layout:
        self._image_panel = ImagePanel(image_stack)
        self._layout.addWidget(self._image_panel)

        self._tool_panel = ToolPanel(image_stack, self._image_panel,
                                     controller.start_and_manage_inpainting)

        # Build config + control layout (varying based on implementation):
        self._control_panel = self._build_control_panel(controller)
        self._main_widget.addTab(self._control_panel, CONTROL_TAB_NAME)
        self._layout.addWidget(self._control_panel, stretch=CONTROL_PANEL_STRETCH)

        for panel in (self._image_panel, self._tool_panel, self._control_panel):
            AppStateTracker.set_enabled_states(panel, [APP_STATE_EDITING])
        self.resizeEvent(None)

    def _get_appropriate_orientation(self) -> Qt.Orientation:
        """Returns whether the window's image and tool layout should be vertical or horizontal."""
        if self._orientation == Qt.Orientation.Vertical:
            height_threshold = LAYOUT_SWAP_HEIGHT - LAYOUT_SWAP_BUFFER
        else:
            height_threshold = LAYOUT_SWAP_HEIGHT + LAYOUT_SWAP_BUFFER
        return Qt.Orientation.Vertical if self.height() > height_threshold else Qt.Orientation.Horizontal

    def show_image_window(self) -> None:
        """Show or raise the image window."""
        self._image_window.show()
        self._image_window.raise_()

    def refresh_layout(self) -> None:
        """Update orientation and layout based on window dimensions."""

        tab_names = [self._main_widget.tabText(i) for i in range(self._main_widget.count())]

        # Flip the orientation if necessary:
        orientation = self._get_appropriate_orientation()
        if self._reactive_layout is None or (orientation != self._orientation):
            self._orientation = orientation
            last_reactive_widget = self._reactive_widget
            if self._reactive_layout is not None:
                for item in self._reactive_layout.children():
                    self._reactive_layout.removeItem(item)
            self._reactive_widget = QWidget(self)
            reactive_layout = QVBoxLayout(self._reactive_widget) if orientation == Qt.Orientation.Vertical \
                else QHBoxLayout(self._reactive_widget)
            self._reactive_layout = reactive_layout
            reactive_layout.setContentsMargins(0, 0, 0, 0)
            reactive_layout.setSpacing(0)
            reactive_layout.addWidget(self._image_panel, stretch=80)
            reactive_layout.addWidget(self._tool_panel, stretch=0)
            self._tool_panel.set_orientation(Qt.Orientation.Vertical if orientation == Qt.Orientation.Horizontal
                                             else Qt.Orientation.Horizontal)
            self._tool_panel.show()
            self._layout.insertWidget(0, self._reactive_widget)
            self._reactive_widget.show()
            if last_reactive_widget is not None:
                last_reactive_widget.setParent(None)

        # Include or tab control panel based on orientation:
        if self._orientation == Qt.Orientation.Vertical:
            if CONTROL_TAB_NAME in tab_names:
                self._main_widget.removeTab(tab_names.index(CONTROL_TAB_NAME))
            if self._control_panel not in self._layout.children():
                self._layout.addWidget(self._control_panel)
                self._control_panel.setVisible(True)
            self._tool_panel.show_generate_button(False)
        else:  # horizontal
            if self._control_panel in self._layout.children():
                self._layout.removeWidget(self._control_panel)
            if CONTROL_TAB_NAME not in tab_names:
                self._main_widget.addTab(self._control_panel, CONTROL_TAB_NAME)
            self._tool_panel.show_generate_button(True)

        # Restrict the tool panel to a reasonable portion of the screen:
        if self._orientation == Qt.Orientation.Vertical:
            self._tool_panel.setMaximumSize(self.width(), self.height() // 3)
        else:
            self._tool_panel.setMaximumSize(self.width() // 2, self.height())

    def _build_control_panel(self, controller) -> QWidget:
        """Adds image editing controls to the layout."""
        config = AppConfig()
        inpaint_panel = QWidget(self)
        text_prompt_textbox = config.get_control_widget(AppConfig.PROMPT, multi_line=False)
        negative_prompt_textbox = config.get_control_widget(AppConfig.NEGATIVE_PROMPT, multi_line=False)

        batch_size_spinbox = config.get_control_widget(AppConfig.BATCH_SIZE)

        batch_count_spinbox = config.get_control_widget(AppConfig.BATCH_COUNT)

        inpaint_button = QPushButton()
        inpaint_button.setText('Start inpainting')
        inpaint_button.clicked.connect(controller.start_and_manage_inpainting)

        more_options_bar = QHBoxLayout()
        guidance_scale_spinbox = config.get_control_widget(AppConfig.GUIDANCE_SCALE)

        skip_steps_spinbox = config.get_control_widget(AppConfig.SKIP_STEPS)

        enable_scale_checkbox = config.get_control_widget(AppConfig.INPAINT_FULL_RES)
        enable_scale_checkbox.setText(config.get_label(AppConfig.INPAINT_FULL_RES))

        upscale_mode_label = QLabel(config.get_label(AppConfig.UPSCALE_MODE), inpaint_panel)
        upscale_mode_list = config.get_control_widget(AppConfig.UPSCALE_MODE)
        downscale_mode_label = QLabel(config.get_label(AppConfig.DOWNSCALE_MODE), inpaint_panel)
        downscale_mode_list = config.get_control_widget(AppConfig.DOWNSCALE_MODE)

        more_options_bar.addWidget(QLabel(config.get_label(AppConfig.GUIDANCE_SCALE), inpaint_panel), stretch=0)
        more_options_bar.addWidget(guidance_scale_spinbox, stretch=20)
        more_options_bar.addWidget(QLabel(config.get_label(AppConfig.SKIP_STEPS), inpaint_panel), stretch=0)
        more_options_bar.addWidget(skip_steps_spinbox, stretch=20)
        more_options_bar.addWidget(enable_scale_checkbox, stretch=10)
        more_options_bar.addWidget(upscale_mode_label, stretch=0)
        more_options_bar.addWidget(upscale_mode_list, stretch=10)
        more_options_bar.addWidget(downscale_mode_label, stretch=0)
        more_options_bar.addWidget(downscale_mode_list, stretch=10)

        # Build layout with labels:
        layout = QGridLayout()
        layout.addWidget(QLabel(config.get_label(AppConfig.PROMPT), inpaint_panel), 1, 1, 1, 1)
        layout.addWidget(text_prompt_textbox, 1, 2, 1, 1)
        layout.addWidget(QLabel(config.get_label(AppConfig.NEGATIVE_PROMPT), inpaint_panel), 2, 1, 1, 1)
        layout.addWidget(negative_prompt_textbox, 2, 2, 1, 1)
        layout.addWidget(QLabel(config.get_label(AppConfig.BATCH_SIZE), inpaint_panel), 1, 3, 1, 1)
        layout.addWidget(batch_size_spinbox, 1, 4, 1, 1)
        layout.addWidget(QLabel(config.get_label(AppConfig.BATCH_COUNT), inpaint_panel), 2, 3, 1, 1)
        layout.addWidget(batch_count_spinbox, 2, 4, 1, 1)
        layout.addWidget(inpaint_button, 2, 5, 1, 1)
        layout.setColumnStretch(2, 255)  # Maximize prompt input

        layout.addLayout(more_options_bar, 3, 1, 1, 4)
        inpaint_panel.setLayout(layout)
        return inpaint_panel

    def focus_tab(self, tab_index: int) -> bool:
        """Attempt to focus a tab index, returning whether changing focus was possible."""
        if self.is_image_selector_visible() or not (0 <= tab_index < self._main_widget.count()) \
                or tab_index == self._main_widget.currentIndex():
            return False
        self._main_widget.setCurrentIndex(tab_index)
        return True

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
                                                              lambda: self.set_image_selector_visible(False),
                                                              self._controller.select_and_apply_sample)
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
        if hasattr(self, '_loading_widget') and TIMELAPSE_MODE_FLAG not in sys.argv:
            loading_widget_size = int(self.height() / 8)
            loading_bounds = QRect(self.width() // 2 - loading_widget_size // 2, loading_widget_size * 3,
                                   loading_widget_size, loading_widget_size)
            self._loading_widget.setGeometry(loading_bounds)
        self.refresh_layout()

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Suppresses mouse events when the loading spinner is active."""
        if not self._is_loading:
            super().mousePressEvent(event)

    def layout(self) -> QBoxLayout:
        """Gets the window's layout as QBoxLayout."""
        return self._layout

    def closeEvent(self, unused_event: Optional[QCloseEvent]) -> None:
        """Close the application when the main window is closed."""
        QApplication.exit()
