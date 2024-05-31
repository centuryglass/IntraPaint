"""
Base implementation of the primary image editing window. On its own, provides an appropriate interface for GLID-3-XL
inpainting modes.  Other editing modes should provide subclasses with implementation-specific controls.
"""
import math
from typing import Callable, Optional, Any

from PIL import Image
from PyQt5.QtCore import Qt, QRect, QSize
from PyQt5.QtGui import QIcon, QMouseEvent, QResizeEvent, QHideEvent, QPixmap
from PyQt5.QtWidgets import QMainWindow, QGridLayout, QLabel, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, \
    QComboBox, QStackedWidget, QAction, QMenuBar, QBoxLayout, QApplication

from src.config.application_config import AppConfig
from src.image.layer_stack import LayerStack
from src.ui.config_control_setup import connected_textedit, connected_spinbox, connected_checkbox
from src.ui.modal.modal_utils import request_confirmation
from src.ui.modal.settings_modal import SettingsModal
from src.ui.panel.layer_panel import LayerPanel
from src.ui.panel.tool_panel import ToolPanel
from src.ui.sample_selector import SampleSelector
from src.ui.widget.loading_widget import LoadingWidget
from src.ui.image_viewer import ImageViewer
from src.undo_stack import undo, redo


class MainWindow(QMainWindow):
    """Main user interface for inpainting."""

    def __init__(self,
                 config: AppConfig,
                 layer_stack: LayerStack,
                 controller: Any):
        """Initializes the main application window and sets up the default UI layout and menu options.

        config : AppConfig
            Shared application configuration object.
        layer_stack : LayerStack
            Image layers being edited.
        controller : BaseController
            Object managing application behavior.
        """
        super().__init__()
        self.setWindowIcon(QIcon('resources/icon.png'))

        # Initialize UI/editing data model:
        self._controller = controller
        self._config = config
        self._layer_stack = layer_stack
        self._sample_selector = None
        self._layout_mode = 'horizontal'
        self._orientation = None

        self._layer_panel: Optional[LayerPanel] = None

        # Create components, build layout:
        self._layout = QVBoxLayout()
        self._reactive_widget = None
        self._reactive_layout = None
        self._main_page_widget = QWidget(self)
        self._main_page_widget.setLayout(self._layout)
        self._main_tab_widget = None
        self._main_widget = self._main_page_widget
        self._central_widget = QStackedWidget(self)
        self._central_widget.addWidget(self._main_widget)
        self.setCentralWidget(self._central_widget)
        self._central_widget.setCurrentWidget(self._main_widget)

        # Loading widget (for interrogate):
        self._is_loading = False
        self._loading_widget = LoadingWidget()
        self._loading_widget.setParent(self)
        self._loading_widget.setGeometry(self.frameGeometry())
        self._loading_widget.hide()

        # Image/Mask editing layout:
        self._image_viewer = ImageViewer(self, layer_stack, config)
        self._layout.addWidget(self._image_viewer)

        self._tool_panel = ToolPanel(layer_stack, self._image_viewer, config)
        # Set up menu:
        self._menu = self.menuBar()

        def add_action(name: str,
                       shortcut: Optional[str],
                       on_trigger: Callable,
                       menu: QMenuBar) -> None:
            """Adds an action to the menu bar."""
            action = QAction(name, self)
            if shortcut is not None:
                action.setShortcut(shortcut)
            action.triggered.connect(on_trigger)
            menu.addAction(action)

        # File:
        file_menu = self._menu.addMenu('File')

        def if_not_selecting(fn: Callable[[], Any]) -> None:
            """Only run the requested action if the sample selector is closed."""
            if not self.is_sample_selector_visible():
                fn()

        add_action('New Image', 'Ctrl+N', lambda: if_not_selecting(controller.new_image), file_menu)
        add_action('Save', 'Ctrl+S', controller.save_image, file_menu)
        add_action('Load', 'Ctrl+O', lambda: if_not_selecting(controller.load_image), file_menu)
        add_action('Reload', 'F5', lambda: if_not_selecting(controller.reload_image), file_menu)

        def try_quit() -> None:
            """Quits the application if the user confirms."""
            if request_confirmation(self, 'Quit now?', 'All unsaved changes will be lost.'):
                self.close()

        add_action('Quit', 'Ctrl+Q', try_quit, file_menu)

        # Edit:
        edit_menu = self._menu.addMenu('Edit')
        add_action('Undo', 'Ctrl+Z', lambda: if_not_selecting(undo), edit_menu)
        add_action('Redo', 'Ctrl+Shift+Z', lambda: if_not_selecting(redo), edit_menu)
        add_action('Generate', 'F4', lambda: if_not_selecting(controller.start_and_manage_inpainting),
                   edit_menu)

        # Image:
        image_menu = self._menu.addMenu('Image')
        add_action('Resize canvas', 'F2', lambda: if_not_selecting(controller.resize_canvas), image_menu)
        add_action('Scale image', 'F3', lambda: if_not_selecting(controller.scale_image), image_menu)
        add_action('Update image metadata', None, controller.update_metadata, image_menu)

        # Tools:
        tool_menu = self._menu.addMenu('Tools')
        # add_action('Toggle pen/eraser tool', 'F7', lambda: if_not_selecting(mask_tool_toggle), tool_menu)
        add_action('Clear mask', 'F8', lambda: if_not_selecting(layer_stack.mask_layer.clear), tool_menu)

        def show_layers() -> None:
            """Show the layer panel."""
            if self._layer_panel is None:
                self._layer_panel = LayerPanel(self._layer_stack)
            self._layer_panel.show()
            self._layer_panel.raise_()

        add_action('Show layers', None, show_layers, tool_menu)

        self._settings = SettingsModal(self)
        if controller.init_settings(self._settings):
            self._settings.changes_saved.connect(controller.update_settings)

            def show_settings() -> None:
                """Creates and shows the settings modal."""
                controller.refresh_settings(self._settings)
                frame = self.frameGeometry()
                frame.setX(frame.x() + (frame.width() // 8))
                frame.setY(frame.y() + (frame.height() // 8))
                frame.setWidth(math.floor(self.width() * 0.75))
                frame.setHeight(math.floor(self.height() * 0.75))
                self._settings.setGeometry(frame)
                self._settings.show_modal()

            add_action('Settings', 'F9', lambda: if_not_selecting(show_settings), tool_menu)

        # TODO: the following are specific to the A1111 stable-diffusion api and should move to
        #       stable_diffusion_controller:
        if 'LCM' in config.get_options(AppConfig.SAMPLING_METHOD):
            try:
                loras = [lora['name'] for lora in config.get(AppConfig.LORA_MODELS)]
                if 'lcm-lora-sdv1-5' in loras:
                    def set_lcm_mode() -> None:
                        """Apply all settings you'd want when using the sd1.5 LCM LORA."""
                        lora_key = '<lora:lcm-lora-sdv1-5:1>'
                        prompt = config.get(AppConfig.PROMPT)
                        if lora_key not in prompt:
                            config.set(AppConfig.PROMPT, f'{prompt} {lora_key}')
                        config.set(AppConfig.GUIDANCE_SCALE, 1.5)
                        config.set(AppConfig.SAMPLING_STEPS, 8)
                        config.set(AppConfig.SAMPLING_METHOD, 'LCM')
                        config.set(AppConfig.SEED, -1)
                        if config.get(AppConfig.BATCH_SIZE) < 5:
                            config.set(AppConfig.BATCH_SIZE, 5)
                        image_size = self._layer_stack.size
                        if image_size.width() < 1200 and image_size.height() < 1200:
                            config.set(AppConfig.EDIT_SIZE, image_size)
                        else:
                            size = QSize(min(image_size.width(), 1024), min(image_size.height(), 1024))
                            config.set(AppConfig.EDIT_SIZE, size)

                    add_action('LCM Mode', 'F10', set_lcm_mode, tool_menu)
            except RuntimeError:
                print('Failed to check loras for lcm lora')

        # Build config + control layout (varying based on implementation):
        self._build_control_layout(controller)

    def _get_appropriate_orientation(self) -> Qt.Orientation:
        """Returns whether the window's image and tool layout should be vertical or horizontal."""
        return Qt.Orientation.Vertical if self.height() > (self.width() * 1.2) else Qt.Orientation.Horizontal

    def refresh_layout(self) -> None:
        """Update orientation and layout based on window dimensions."""
        orientation = self._get_appropriate_orientation()
        if orientation == self._orientation:
            return
        self._orientation = orientation
        last_reactive_widget = self._reactive_widget
        if self._reactive_layout is not None:
            for panel in (self._image_viewer, self._tool_panel):
                self._reactive_layout.removeWidget(panel)
        self._reactive_widget = QWidget(self)
        self._reactive_layout = QVBoxLayout(self._reactive_widget) if orientation == Qt.Orientation.Vertical \
            else QHBoxLayout(self._reactive_widget)
        self._reactive_layout.addWidget(self._image_viewer, stretch=80)
        self._reactive_layout.addWidget(self._tool_panel, stretch=2)
        self._tool_panel.set_orientation(orientation)
        self._layout.insertWidget(0, self._reactive_widget)
        if last_reactive_widget is not None:
            last_reactive_widget.setParent(None)

    def _create_scale_mode_selector(self, parent: QWidget, config_key: str) -> QComboBox:
        """Returns a combo box that selects between image scaling algorithms."""
        scale_mode_list = QComboBox(parent)
        filter_types = [
            ('Bilinear', Image.BILINEAR),
            ('Nearest', Image.NEAREST),
            ('Hamming', Image.HAMMING),
            ('Bicubic', Image.BICUBIC),
            ('Lanczos', Image.LANCZOS),
            ('Box', Image.BOX)
        ]
        for name, image_filter in filter_types:
            scale_mode_list.addItem(name, image_filter)
        scale_mode_list.setCurrentIndex(scale_mode_list.findData(self._config.get(config_key)))

        def set_scale_mode(mode_index: int):
            """Applies the selected scaling mode to config."""
            mode = scale_mode_list.itemData(mode_index)
            if mode:
                self._config.set(config_key, mode)

        scale_mode_list.currentIndexChanged.connect(set_scale_mode)
        scale_mode_list.setToolTip(self._config.get_tooltip(config_key))
        return scale_mode_list

    def _build_control_layout(self, controller) -> None:
        """Adds image editing controls to the layout."""
        inpaint_panel = QWidget(self)
        text_prompt_textbox = connected_textedit(inpaint_panel, self._config, AppConfig.PROMPT)
        negative_prompt_textbox = connected_textedit(inpaint_panel, self._config, AppConfig.NEGATIVE_PROMPT)

        batch_size_spinbox = connected_spinbox(inpaint_panel, self._config, AppConfig.BATCH_SIZE)

        batch_count_spinbox = connected_spinbox(inpaint_panel, self._config, AppConfig.BATCH_COUNT)

        inpaint_button = QPushButton()
        inpaint_button.setText('Start inpainting')
        inpaint_button.clicked.connect(controller.start_and_manage_inpainting)

        more_options_bar = QHBoxLayout()
        guidance_scale_spinbox = connected_spinbox(inpaint_panel, self._config, AppConfig.GUIDANCE_SCALE)

        skip_steps_spinbox = connected_spinbox(inpaint_panel, self._config, AppConfig.SKIP_STEPS)

        enable_scale_checkbox = connected_checkbox(inpaint_panel, self._config, AppConfig.INPAINT_FULL_RES)
        enable_scale_checkbox.setText(self._config.get_label(AppConfig.INPAINT_FULL_RES))

        upscale_mode_label = QLabel(inpaint_panel)
        upscale_mode_label.setText(self._config.get_label(AppConfig.UPSCALE_MODE))
        upscale_mode_list = self._create_scale_mode_selector(inpaint_panel, AppConfig.UPSCALE_MODE)
        downscale_mode_label = QLabel(inpaint_panel)
        downscale_mode_label.setText(self._config.get_label(AppConfig.DOWNSCALE_MODE))
        downscale_mode_list = self._create_scale_mode_selector(inpaint_panel, AppConfig.DOWNSCALE_MODE)

        more_options_bar.addWidget(QLabel(self._config.get_label(AppConfig.GUIDANCE_SCALE), inpaint_panel),
                                   stretch=0)
        more_options_bar.addWidget(guidance_scale_spinbox, stretch=20)
        more_options_bar.addWidget(QLabel(self._config.get_label(AppConfig.SKIP_STEPS), inpaint_panel), stretch=0)
        more_options_bar.addWidget(skip_steps_spinbox, stretch=20)
        more_options_bar.addWidget(enable_scale_checkbox, stretch=10)
        more_options_bar.addWidget(upscale_mode_label, stretch=0)
        more_options_bar.addWidget(upscale_mode_list, stretch=10)
        more_options_bar.addWidget(downscale_mode_label, stretch=0)
        more_options_bar.addWidget(downscale_mode_list, stretch=10)

        # Build layout with labels:
        layout = QGridLayout()
        layout.addWidget(QLabel(self._config.get_label(AppConfig.PROMPT), inpaint_panel), 1, 1, 1, 1)
        layout.addWidget(text_prompt_textbox, 1, 2, 1, 1)
        layout.addWidget(QLabel(self._config.get_label(AppConfig.NEGATIVE_PROMPT), inpaint_panel), 2, 1, 1, 1)
        layout.addWidget(negative_prompt_textbox, 2, 2, 1, 1)
        layout.addWidget(QLabel(self._config.get_label(AppConfig.BATCH_SIZE), inpaint_panel), 1, 3, 1, 1)
        layout.addWidget(batch_size_spinbox, 1, 4, 1, 1)
        layout.addWidget(QLabel(self._config.get_label(AppConfig.BATCH_COUNT), inpaint_panel), 2, 3, 1, 1)
        layout.addWidget(batch_count_spinbox, 2, 4, 1, 1)
        layout.addWidget(inpaint_button, 2, 5, 1, 1)
        layout.setColumnStretch(2, 255)  # Maximize prompt input

        layout.addLayout(more_options_bar, 3, 1, 1, 4)
        inpaint_panel.setLayout(layout)
        self.layout().addWidget(inpaint_panel, stretch=20)
        self.resizeEvent(None)

    def is_sample_selector_visible(self) -> bool:
        """Returns whether the generated image selection screen is showing."""
        return hasattr(self, '_sample_selector') and self._central_widget.currentWidget() == self._sample_selector

    def set_sample_selector_visible(self, visible: bool):
        """Shows or hides the generated image selection screen."""
        is_visible = self.is_sample_selector_visible()
        if visible == is_visible:
            return
        if visible:
            if self._config.get(AppConfig.EDIT_MODE) == 'Inpaint':
                mask = self._layer_stack.mask_layer.pil_mask_image
            else:
                mask = QPixmap(self._layer_stack.selection.size())
                mask.fill(Qt.red)
            self._sample_selector = SampleSelector(
                self._config,
                self._layer_stack,
                mask,
                lambda: self.set_sample_selector_visible(False),
                self._controller.select_and_apply_sample)
            self._central_widget.addWidget(self._sample_selector)
            self._central_widget.setCurrentWidget(self._sample_selector)
            self.installEventFilter(self._sample_selector)
        else:
            self.removeEventFilter(self._sample_selector)
            self._central_widget.setCurrentWidget(self._main_widget)
            self._central_widget.removeWidget(self._sample_selector)
            del self._sample_selector
            self._sample_selector = None

    def load_sample_preview(self, image: Image.Image, idx: int) -> None:
        """Adds an image to the generated image selection screen."""
        if self._sample_selector is None:
            print(f'Tried to load sample {idx} after sampleSelector was closed')
        else:
            self._sample_selector.load_sample_image(image, idx)

    def set_is_loading(self, is_loading: bool, message: Optional[str] = None) -> None:
        """Sets whether the loading spinner is shown, optionally setting loading spinner message text."""
        if self._sample_selector is not None:
            self._sample_selector.set_is_loading(is_loading, message)
        else:
            if is_loading:
                self._loading_widget.show()
                if message:
                    self._loading_widget.set_message(message)
                else:
                    self._loading_widget.set_message('Loading...')
            else:
                self._loading_widget.hide()
            self._is_loading = is_loading
            self.update()

    def set_loading_message(self, message: str) -> None:
        """Sets the loading spinner message text."""
        if self._sample_selector is not None:
            self._sample_selector.set_loading_message(message)

    def resizeEvent(self, unused_event: Optional[QResizeEvent]) -> None:
        """Applies the most appropriate layout when the window size changes."""
        if hasattr(self, '_loading_widget'):
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

    def hideEvent(self, unused_event: Optional[QHideEvent]) -> None:
        """Close the application when the main window is hidden."""
        QApplication.exit()