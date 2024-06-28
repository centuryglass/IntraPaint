"""
BaseController coordinates primary application functionality across all operation modes. Each image generation and
editing method supported by IntraPaint should have its own BaseController subclass.
"""
import os
import sys
import re
from typing import Optional, Callable, Any, List, Tuple
from argparse import Namespace
import logging
from PIL import Image, ImageFilter, UnidentifiedImageError, PngImagePlugin
from PyQt5.QtWidgets import QApplication, QMessageBox, QMainWindow
from PyQt5.QtCore import QObject, QRect, QPoint, QThread, QSize, pyqtSignal, Qt
from PyQt5.QtGui import QScreen, QImage, QPainter

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.filter.posterize import PosterizeFilter
from src.image.filter.blur import BlurFilter
from src.image.filter.rgb_color_balance import RGBColorBalanceFilter
from src.image.filter.sharpen import SharpenFilter
from src.image.filter.brightness_contrast import BrightnessContrastFilter
from src.ui.panel.layer_panel import LayerPanel
from src.util.application_state import AppStateTracker, APP_STATE_NO_IMAGE, APP_STATE_EDITING, APP_STATE_LOADING, \
    APP_STATE_SELECTION
from src.util.menu_builder import MenuBuilder, menu_action
from src.util.optional_import import optional_import
from src.config.application_config import AppConfig
from src.image.layer_stack import LayerStack

from src.ui.window.main_window import MainWindow
from src.ui.modal.new_image_modal import NewImageModal
from src.ui.modal.resize_canvas_modal import ResizeCanvasModal
from src.ui.modal.image_scale_modal import ImageScaleModal
from src.ui.modal.modal_utils import show_error_dialog, request_confirmation, open_image_file, open_image_layers
from src.ui.modal.settings_modal import SettingsModal
from src.util.display_size import get_screen_size
from src.util.image_utils import pil_image_to_qimage, qimage_to_pil_image
from src.util.qtexcepthook import QtExceptHook
from src.util.shared_constants import EDIT_MODE_INPAINT, PIL_SCALING_MODES

from src.util.validation import assert_type
from src.undo_stack import commit_action, undo, redo

# Optional spacenav support and extended theming:
qdarktheme = optional_import('qdarktheme')
qt_material = optional_import('qt_material')
SpacenavManager = optional_import('spacenav_manager', 'src.controller', 'SpacenavManager')

logger = logging.getLogger(__name__)

MENU_FILE = 'File'
MENU_EDIT = 'Edit'
MENU_IMAGE = 'Image'
MENU_SELECTION = 'Selection'
MENU_LAYERS = 'Layers'
MENU_TOOLS = 'Tools'
MENU_FILTERS = 'Filters'

CONFIRM_QUIT_TITLE = 'Quit now?'
CONFIRM_QUIT_MESSAGE = 'All unsaved changes will be lost.'
NEW_IMAGE_CONFIRMATION_TITLE = 'Create new image?'
NEW_IMAGE_CONFIRMATION_MESSAGE = 'This will discard all unsaved changes.'
SAVE_ERROR_MESSAGE_NO_IMAGE = 'Open or create an image first before trying to save.'
SAVE_ERROR_TITLE = 'Save failed'
LOAD_ERROR_TITLE = 'Open failed'
RELOAD_ERROR_MESSAGE_NO_IMAGE = 'Enter an image path or click "Open Image" first.'
RELOAD_ERROR_TITLE = 'Reload failed'
RELOAD_CONFIRMATION_TITLE = 'Reload image?'
RELOAD_CONFIRMATION_MESSAGE = 'This will discard all unsaved changes.'
METADATA_UPDATE_TITLE = 'Metadata updated'
METADATA_UPDATE_MESSAGE = 'On save, current image generation parameters will be stored within the image'
RESIZE_ERROR_TITLE = 'Resize failed'
RESIZE_ERROR_MESSAGE_NO_IMAGE = 'Open or create an image first before trying to resize.'
SCALING_ERROR_TITLE = 'Scaling failed'
SCALING_ERROR_MESSAGE_NO_IMAGE = 'Open or create an image first before trying to scale.'
GENERATE_ERROR_TITLE_UNEXPECTED = 'Inpainting failure'
GENERATE_ERROR_TITLE_NO_IMAGE = 'Save failed'
GENERATE_ERROR_MESSAGE_NO_IMAGE = 'Open or create an image first before trying to start image generation.'
GENERATE_ERROR_TITLE_EXISTING_OP = 'Failed'
GENERATE_ERROR_MESSAGE_EXISTING_OP = 'Existing image generation operation not yet finished, wait a little longer.'
SETTINGS_ERROR_MESSAGE = 'Settings not supported in this mode.'
SETTINGS_ERROR_TITLE = 'Failed to open settings'
LOAD_LAYER_ERROR_TITLE = 'Opening layers failed'
LOAD_LAYER_ERROR_MESSAGE = 'Could not open the following images: '

METADATA_PARAMETER_KEY = 'parameters'
IGNORED_APPCONFIG_CATEGORIES = ('Stable-Diffusion', 'GLID-3-XL')


class BaseInpaintController(MenuBuilder):
    """Shared base class for managing inpainting.

    At a bare minimum, subclasses will need to implement self._inpaint.
    """

    def __init__(self, args: Namespace) -> None:
        super().__init__()
        self._app = QApplication(sys.argv)
        screen = self._app.primaryScreen()
        self._fixed_window_size = args.window_size
        if self._fixed_window_size is not None:
            x, y = (int(dim) for dim in self._fixed_window_size.split('x'))
            self._fixed_window_size = QSize(x, y)

        def screen_area(screen_option: Optional[QScreen]) -> int:
            """Calculate the area of an available screen."""
            if screen_option is None:
                return 0
            return screen_option.availableGeometry().width() * screen_option.availableGeometry().height()

        for s in self._app.screens():
            if screen_area(s) > screen_area(screen):
                screen = s
        config = AppConfig.instance()
        self._adjust_config_defaults()
        config.apply_args(args)

        self._layer_stack = LayerStack(config.get(AppConfig.DEFAULT_IMAGE_SIZE), config.get(AppConfig.EDIT_SIZE),
                                       config.get(AppConfig.MIN_EDIT_SIZE), config.get(AppConfig.MAX_EDIT_SIZE))
        self._init_image = args.init_image

        self._window: Optional[QMainWindow] = None
        self._layer_panel: Optional[LayerPanel] = None
        self._settings_panel: Optional[SettingsModal] = None
        self._nav_manager: Optional['SpacenavManager'] = None
        self._worker: Optional[QObject] = None
        self._metadata: Optional[dict[str, Any]] = None
        self._thread: Optional[QThread] = None

    def _adjust_config_defaults(self):
        """no-op, override to adjust config before data initialization."""

    def is_busy(self) -> bool:
        """Return whether the application is in the middle of something that should not be interrupted."""
        if self._thread is not None:
            return True
        if self._window is not None and hasattr(self._window, 'is_busy'):
            return self._window.is_busy()
        return False

    def get_config_categories(self) -> List[str]:
        """Return the list of AppConfig categories BaseInpaintController manages within the settings modal."""
        categories = AppConfig.instance().get_categories()
        for ignored in IGNORED_APPCONFIG_CATEGORIES:
            categories.remove(ignored)
        return categories

    def init_settings(self, settings_modal: SettingsModal) -> None:
        """ 
        Function to override initialize a SettingsModal with implementation-specific settings. This will initialize all
        universal settings, subclasses will need to extend this or override get_config_categories to add more.
        """
        settings_modal.load_from_config(AppConfig.instance(), self.get_config_categories())
        settings_modal.load_from_config(KeyConfig.instance())

    def refresh_settings(self, settings_modal: SettingsModal):
        """
        Updates a SettingsModal to reflect any changes.

        Parameters
        ----------
        settings_modal : SettingsModal
        """
        config = AppConfig.instance()
        categories = self.get_config_categories()
        settings = {}
        for category in categories:
            for key in config.get_category_keys(category):
                settings[key] = config.get(key)
        settings_modal.update_settings(settings)

    def update_settings(self, changed_settings: dict):
        """
        Apply changed settings from a SettingsModal.  This should only be called in
        a child class instance that previously returned true after init_settings was called.

        Parameters
        ----------
        changed_settings : dict
            Set of changes loaded from a SettingsModal.
        """
        app_config = AppConfig.instance()
        categories = self.get_config_categories()
        base_keys = [key for cat in categories for key in app_config.get_category_keys(cat)]
        key_keys = KeyConfig.instance().get_keys()
        for key, value in changed_settings.items():
            if key in base_keys:
                app_config.set(key, value)
            elif key in key_keys:
                KeyConfig.instance().set(key, value)

    def window_init(self):
        """Initialize and show the main application window."""
        self._window = MainWindow(self._layer_stack, self)
        if self._fixed_window_size is not None:
            size = self._fixed_window_size
            self._window.setGeometry(0, 0, size.width(), size.height())
            self._window.setMaximumSize(self._fixed_window_size)
            self._window.setMinimumSize(self._fixed_window_size)
        else:
            size = get_screen_size(self._window)
            self._window.setGeometry(0, 0, size.width(), size.height())
            self._window.setMaximumSize(size)
        self.fix_styles()
        if self._init_image is not None:
            logger.info('loading init image:')
            self.load_image(file_path=self._init_image)
        self._window.show()

    def fix_styles(self) -> None:
        """Update application styling based on theme configuration, UI configuration, and available theme modules."""
        config = AppConfig.instance()

        def _apply_style(new_style: str) -> None:
            self._app.setStyle(new_style)

        config.connect(self, AppConfig.STYLE, _apply_style)
        _apply_style(config.get(AppConfig.STYLE))

        def _apply_theme(theme: str) -> None:
            if theme.startswith('qdarktheme_') and qdarktheme is not None and hasattr(qdarktheme, 'setup_theme'):
                if theme.endswith('_light'):
                    qdarktheme.setup_theme('light')
                elif theme.endswith('_auto'):
                    qdarktheme.setup_theme('auto')
                else:
                    qdarktheme.setup_theme()
            elif theme.startswith('qt_material_') and qt_material is not None:
                xml_file = theme[len('qt_material_'):]
                qt_material.apply_stylesheet(self._app, theme=xml_file)
            elif theme != 'None':
                logger.error(f'Failed to load theme {theme}')

        config.connect(self, AppConfig.THEME, _apply_theme)
        _apply_theme(config.get(AppConfig.THEME))

        def _apply_font(font_pt: int) -> None:
            font = self._app.font()
            font.setPointSize(font_pt)
            self._app.setFont(font)

        config.connect(self, AppConfig.FONT_POINT_SIZE, _apply_font)
        _apply_font(config.get(AppConfig.FONT_POINT_SIZE))

    def start_app(self) -> None:
        """Start the application after performing any additional required setup steps."""
        self.window_init()
        assert self._window is not None

        # Configure support for spacemouse panning, if relevant:
        if SpacenavManager is not None and self._window is not None:
            self._nav_manager = SpacenavManager(self._window, self._layer_stack)
            self._nav_manager.start_thread()

        # initialize menus:
        self.build_menus(self._window)
        # Since image filter menus follow a very simple pattern, add them here instead of using @menu_action:
        for filter_class in (RGBColorBalanceFilter,
                             BrightnessContrastFilter,
                             BlurFilter,
                             SharpenFilter,
                             PosterizeFilter):
            image_filter = filter_class()

            def _open_filter_modal(filter_instance=image_filter) -> None:
                modal = filter_instance.get_filter_modal(self._layer_stack)
                modal.exec_()

            config_key = image_filter.get_config_key()
            action = self.add_menu_action(self._window,
                                          MENU_FILTERS,
                                          _open_filter_modal,
                                          config_key)
            AppStateTracker.set_enabled_states(action, [APP_STATE_EDITING])

        AppStateTracker.set_app_state(APP_STATE_EDITING if self._layer_stack.has_image else APP_STATE_NO_IMAGE)
        QtExceptHook().enable()
        self._app.exec_()
        sys.exit()

    # Menu action definitions:

    # File menu:

    @menu_action(MENU_FILE, 'new_image_shortcut', 0,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_NO_IMAGE])
    def new_image(self) -> None:
        """Open a new image creation modal."""
        assert self._window is not None
        default_size = AppConfig.instance().get(AppConfig.DEFAULT_IMAGE_SIZE)
        image_modal = NewImageModal(default_size.width(), default_size.height())
        image_size = image_modal.show_image_modal()
        if image_size and (not self._layer_stack.has_image or request_confirmation(self._window,
                                                                                   NEW_IMAGE_CONFIRMATION_TITLE,
                                                                                   NEW_IMAGE_CONFIRMATION_MESSAGE)):
            new_image = Image.new('RGB', (image_size.width(), image_size.height()), color='white')
            self._layer_stack.set_image(new_image)
            for i in range(1, self._layer_stack.count):
                self._layer_stack.get_layer_by_index(i).clear()
            self._metadata = None
            AppStateTracker.set_app_state(APP_STATE_EDITING)

    @menu_action(MENU_FILE, 'save_shortcut', priority=1,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_SELECTION, APP_STATE_LOADING])
    def save_image(self) -> None:
        """Saves the edited image, only opening the save dialog if no previous image path is cached."""
        image_path = Cache.instance().get(Cache.LAST_FILE_PATH)
        if not os.path.isfile(image_path):
            image_path = None
        self.save_image_as(file_path=image_path)

    @menu_action(MENU_FILE, 'save_as_shortcut', priority=2,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_SELECTION, APP_STATE_LOADING])
    def save_image_as(self, file_path: Optional[str] = None) -> None:
        """Open a save dialog, and save the edited image to disk, preserving any metadata."""
        assert self._window is not None
        cache = Cache.instance()
        if not self._layer_stack.has_image:
            show_error_dialog(self._window, SAVE_ERROR_TITLE, SAVE_ERROR_MESSAGE_NO_IMAGE)
            return
        try:
            if not isinstance(file_path, str):
                file_path, file_selected = open_image_file(self._window, mode='save',
                                                           selected_file=cache.get(Cache.LAST_FILE_PATH))
                if not file_path or not file_selected:
                    return
            assert_type(file_path, str)
            if file_path.endswith('.inpt'):
                self._layer_stack.save_layer_stack_file(file_path, self._metadata)
            else:
                image = self._layer_stack.pil_image(saved_only=True)
                if self._metadata is not None:
                    info = PngImagePlugin.PngInfo()
                    for key in self._metadata:
                        try:
                            info.add_itxt(key, self._metadata[key])
                        except AttributeError as png_err:
                            # Encountered some sort of image metadata that PIL knows how to read but not how to write.
                            # I've seen this a few times, mostly with images edited in Krita. This data isn't important
                            # to me, so it'll just be discarded. If it's important to you, open a GitHub issue with
                            # details or submit a PR, and I'll take care of it.
                            print(f'failed to preserve "{key}" in metadata: {png_err}')
                    image.save(file_path, 'PNG', pnginfo=info)
                else:
                    image.save(file_path, 'PNG')
            cache.set(Cache.LAST_FILE_PATH, file_path)
        except (IOError, TypeError) as save_err:
            show_error_dialog(self._window, SAVE_ERROR_TITLE, str(save_err))
            raise save_err

    @menu_action(MENU_FILE, 'load_shortcut', 3,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_NO_IMAGE])
    def load_image(self, file_path: Optional[str] = None) -> None:
        """Open a loading dialog, then load the selected image for editing."""
        assert self._window is not None
        cache = Cache.instance()
        config = AppConfig.instance()
        if file_path is None:
            file_path, file_selected = open_image_file(self._window)
            if not file_path or not file_selected:
                return
        if isinstance(file_path, list):
            logger.warning(f'Expected single image, got list with length {len(file_path)}')
            file_path = file_path[0]
        assert_type(file_path, str)
        try:
            if file_path.endswith('.inpt'):
                self._metadata = self._layer_stack.load_layer_stack_file(file_path)
            else:
                image = Image.open(file_path)
                # try and load metadata:
                if hasattr(image, 'info') and image.info is not None:
                    self._metadata = image.info
                else:
                    self._metadata = None
                self._layer_stack.set_image(QImage(file_path))
            cache.set(Cache.LAST_FILE_PATH, file_path)

            # File loaded, attempt to apply metadata:
            if self._metadata is not None and METADATA_PARAMETER_KEY in self._metadata:
                param_str = self._metadata[METADATA_PARAMETER_KEY]
                match = re.match(r'^(.*\n?.*)\nSteps: ?(\d+), Sampler: ?(.*), CFG scale: ?(.*), Seed: ?(.+), Size.*',
                                 param_str)
                if match:
                    prompt = match.group(1)
                    negative = ''
                    steps = int(match.group(2))
                    sampler = match.group(3)
                    cfg_scale = float(match.group(4))
                    seed = int(match.group(5))
                    divider_match = re.match('^(.*)\nNegative prompt: ?(.*)$', prompt)
                    if divider_match:
                        prompt = divider_match.group(1)
                        negative = divider_match.group(2)
                    logger.info('Detected saved image gen data, applying to UI')
                    try:
                        config.set(AppConfig.PROMPT, prompt)
                        config.set(AppConfig.NEGATIVE_PROMPT, negative)
                        config.set(AppConfig.SAMPLING_STEPS, steps)
                        config.set(AppConfig.SAMPLING_METHOD, sampler)
                        config.set(AppConfig.GUIDANCE_SCALE, cfg_scale)
                        config.set(AppConfig.SEED, seed)
                    except (TypeError, RuntimeError) as err:
                        logger.error(f'Failed to load image gen data from metadata: {err}')
                else:
                    logger.warning('image parameters do not match expected patterns, cannot be used. '
                                   f'parameters:{param_str}')
            AppStateTracker.set_app_state(APP_STATE_EDITING)
        except UnidentifiedImageError as err:
            show_error_dialog(self._window, LOAD_ERROR_TITLE, err)
            return

    @menu_action(MENU_FILE, 'load_layers_shortcut', 4,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_NO_IMAGE])
    def load_image_layers(self) -> None:
        """Open one or more images as layers."""
        assert self._window is not None
        layer_paths, layers_selected = open_image_layers(self._window)
        if not layers_selected or not layer_paths or len(layer_paths) == 0:
            return
        layers: List[Tuple[QImage, str]] = []
        errors: List[str] = []
        for layer_path in layer_paths:
            try:
                image = QImage(layer_path)
                layers.append((image, layer_path))
            except IOError:
                errors.append(layer_path)
        if not self._layer_stack.has_image:
            width = 0
            height = 0
            for image, _ in layers:
                width = max(width, image.width())
                height = max(height, image.height())
            base_layer = QImage(QSize(width, height), QImage.Format_ARGB32_Premultiplied)
            base_layer.fill(Qt.GlobalColor.transparent)
            self._layer_stack.set_image(base_layer)
        for image, image_path in layers:
            name = os.path.basename(image_path)
            self._layer_stack.create_layer(name, image)
        if len(errors) > 0:
            show_error_dialog(self._window, LOAD_LAYER_ERROR_TITLE, LOAD_LAYER_ERROR_MESSAGE + ','.join(errors))
        if self._layer_stack.has_image:
            AppStateTracker.set_app_state(APP_STATE_EDITING)

    @menu_action(MENU_FILE, 'reload_shortcut', 5, valid_app_states=[APP_STATE_EDITING])
    def reload_image(self) -> None:
        """Reload the edited image from disk after getting confirmation from a confirmation dialog."""
        assert self._window is not None
        file_path = Cache.instance().get(Cache.LAST_FILE_PATH)
        if file_path == '':
            show_error_dialog(self._window, RELOAD_ERROR_TITLE, RELOAD_ERROR_MESSAGE_NO_IMAGE)
            return
        if not os.path.isfile(file_path):
            show_error_dialog(self._window, RELOAD_ERROR_TITLE, f'Image path "{file_path}" is not a valid file.')
            return
        if not self._layer_stack.has_image or request_confirmation(self._window,
                                                                   RELOAD_CONFIRMATION_TITLE,
                                                                   RELOAD_CONFIRMATION_MESSAGE):
            self.load_image(file_path=file_path)

    @menu_action(MENU_FILE, 'quit_shortcut', 6)
    def quit(self) -> None:
        """Quit the application after getting confirmation from the user."""
        if self._window is not None and request_confirmation(self._window, CONFIRM_QUIT_TITLE, CONFIRM_QUIT_MESSAGE):
            self._window.close()

    # Edit menu:

    @menu_action(MENU_EDIT, 'undo_shortcut', 10,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_NO_IMAGE])
    def undo(self) -> None:
        """Revert the most recent significant change made."""
        undo()

    @menu_action(MENU_EDIT, 'redo_shortcut', 11, valid_app_states=[APP_STATE_EDITING, APP_STATE_NO_IMAGE])
    def redo(self) -> None:
        """Restore the most recent reverted change."""
        redo()

    @menu_action(MENU_EDIT, 'cut_shortcut', 12, valid_app_states=[APP_STATE_EDITING])
    def cut(self) -> None:
        """Cut selected content from the active image layer."""
        self._layer_stack.cut_selected()

    @menu_action(MENU_EDIT, 'copy_shortcut', 13, valid_app_states=[APP_STATE_EDITING])
    def copy(self) -> None:
        """Copy selected content from the active image layer."""
        self._layer_stack.copy_selected()

    @menu_action(MENU_EDIT, 'paste_shortcut', 14, valid_app_states=[APP_STATE_EDITING])
    def paste(self) -> None:
        """Paste copied image content into a new layer."""
        self._layer_stack.paste()

    # Image menu:

    @menu_action(MENU_IMAGE, 'resize_canvas_shortcut', 20, valid_app_states=[APP_STATE_EDITING])
    def resize_canvas(self) -> None:
        """Crop or extend the edited image without scaling its contents based on user input into a popup modal."""
        assert self._window is not None
        if not self._layer_stack.has_image:
            show_error_dialog(self._window, RESIZE_ERROR_TITLE, RESIZE_ERROR_MESSAGE_NO_IMAGE)
            return
        resize_modal = ResizeCanvasModal(self._layer_stack.qimage())
        new_size, offset = resize_modal.show_resize_modal()
        if new_size is None or offset is None:
            return
        self._layer_stack.resize_canvas(new_size, offset.x(), offset.y())

    @menu_action(MENU_IMAGE, 'scale_image_shortcut', 21, valid_app_states=[APP_STATE_EDITING])
    def scale_image(self) -> None:
        """Scale the edited image based on user input into a popup modal."""
        assert self._window is not None
        if not self._layer_stack.has_image:
            show_error_dialog(self._window, SCALING_ERROR_TITLE, SCALING_ERROR_MESSAGE_NO_IMAGE)
            return
        width = self._layer_stack.width
        height = self._layer_stack.height
        scale_modal = ImageScaleModal(width, height)
        new_size = scale_modal.show_image_modal()
        if new_size is not None:
            self._scale(new_size)

    @menu_action(MENU_IMAGE, 'update_metadata_shortcut',
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_SELECTION])
    def update_metadata(self, show_messagebox: bool = True) -> None:
        """
        Adds image editing parameters from config to the image metadata, in a format compatible with the A1111
        stable-diffusion webui. Parameters will be applied to the image file when save_image is called.

        Parameters
        ----------
        show_messagebox: bool
            If true, show a messagebox after the update to let the user know what happened.
        """
        assert self._window is not None
        config = AppConfig.instance()
        prompt = config.get(AppConfig.PROMPT)
        negative = config.get(AppConfig.NEGATIVE_PROMPT)
        steps = config.get(AppConfig.SAMPLING_STEPS)
        sampler = config.get(AppConfig.SAMPLING_METHOD)
        cfg_scale = config.get(AppConfig.GUIDANCE_SCALE)
        seed = config.get(AppConfig.SEED)
        params = f'{prompt}\nNegative prompt: {negative}\nSteps: {steps}, Sampler: {sampler}, CFG scale:' + \
                 f'{cfg_scale}, Seed: {seed}, Size: 512x512'
        if self._metadata is None:
            self._metadata = {}
        self._metadata[METADATA_PARAMETER_KEY] = params
        if show_messagebox:
            message_box = QMessageBox()
            message_box.setWindowTitle(METADATA_UPDATE_TITLE)
            message_box.setText(METADATA_UPDATE_MESSAGE)
            message_box.setStandardButtons(QMessageBox.Ok)
            message_box.exec()

    @menu_action(MENU_IMAGE, 'generate_shortcut', 23, valid_app_states=[APP_STATE_EDITING])
    def start_and_manage_inpainting(self) -> None:
        """Start inpainting/image editing based on the current state of the UI."""
        assert self._window is not None
        config = AppConfig.instance()
        if not self._layer_stack.has_image:
            show_error_dialog(self._window, GENERATE_ERROR_TITLE_NO_IMAGE, GENERATE_ERROR_MESSAGE_NO_IMAGE)
            return
        if self._thread is not None:
            show_error_dialog(self._window, GENERATE_ERROR_TITLE_EXISTING_OP, GENERATE_ERROR_MESSAGE_EXISTING_OP)
            return
        upscale_mode = PIL_SCALING_MODES[config.get(AppConfig.UPSCALE_MODE)]
        downscale_mode = PIL_SCALING_MODES[config.get(AppConfig.DOWNSCALE_MODE)]

        def resize_image(pil_image: Image.Image, width: int, height: int) -> Image.Image:
            """Resize a PIL image using the appropriate scaling mode:"""
            if width == pil_image.width and height == pil_image.height:
                return pil_image
            if width > pil_image.width or height > pil_image.height:
                return pil_image.resize((width, height), upscale_mode)
            return pil_image.resize((width, height), downscale_mode)

        source_selection = qimage_to_pil_image(self._layer_stack.qimage_generation_area_content())

        inpaint_image = source_selection.copy()
        inpaint_mask = self._layer_stack.selection_layer.pil_mask_image

        # If necessary, scale image and mask to match the image generation size.
        generation_size = config.get(AppConfig.GENERATION_SIZE)
        if inpaint_image.width != generation_size.width() or inpaint_image.height != generation_size.height():
            inpaint_image = resize_image(inpaint_image, generation_size.width(), generation_size.height())
        if inpaint_mask.width != generation_size.width() or inpaint_mask.height != generation_size.height():
            inpaint_mask = resize_image(inpaint_mask, generation_size.width(), generation_size.height())

        do_inpaint = self._inpaint

        class InpaintThreadWorker(QObject):
            """Handles inpainting within its own thread."""
            finished = pyqtSignal()
            image_ready = pyqtSignal(Image.Image, int)
            status_signal = pyqtSignal(dict)
            error_signal = pyqtSignal(Exception)

            def run(self) -> None:
                """Start the inpainting thread."""
                try:
                    do_inpaint(inpaint_image, inpaint_mask, self.image_ready.emit, self.status_signal)
                except (IOError, ValueError, RuntimeError) as err:
                    self.error_signal.emit(err)
                self.finished.emit()

        worker = InpaintThreadWorker()

        def handle_error(err: BaseException) -> None:
            """Close sample selector and show an error popup if anything goes wrong."""
            assert self._window is not None
            self._window.set_image_selector_visible(False)
            show_error_dialog(self._window, GENERATE_ERROR_TITLE_UNEXPECTED, err)

        worker.error_signal.connect(handle_error)
        worker.status_signal.connect(self._apply_status_update)

        def load_sample_preview(img: Image.Image, idx: int) -> None:
            """Apply image mask to inpainting results."""
            assert self._window is not None
            if config.get(AppConfig.EDIT_MODE) == EDIT_MODE_INPAINT:
                def point_fn(p: int) -> int:
                    """Convert pixel to 1-bit."""
                    return 255 if p < 1 else 0

                mask_alpha = inpaint_mask.convert('L').point(point_fn).filter(ImageFilter.GaussianBlur())
                mask_alpha = resize_image(mask_alpha, img.width, img.height)
                base = resize_image(source_selection, img.width, img.height)
                img = Image.composite(base, img, mask_alpha)
            self._window.load_sample_preview(pil_image_to_qimage(img), idx)

        worker.image_ready.connect(load_sample_preview)

        AppStateTracker.set_app_state(APP_STATE_LOADING)
        self._window.set_image_selector_visible(True)
        self._start_thread(worker)

    def select_and_apply_sample(self, sample_image: Image.Image | QImage) -> None:
        """Apply an AI-generated image change to the edited image.

        Parameters
        ----------
        sample_image : PIL Image
            Data to be inserted into the edited image generation area bounds.
        """
        if sample_image is not None:
            if isinstance(sample_image, Image.Image):
                image = pil_image_to_qimage(sample_image).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
            else:
                image = sample_image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
            if AppConfig.instance().get(AppConfig.EDIT_MODE) == "Inpaint":
                inpaint_mask = self._layer_stack.selection_layer.cropped_image_content(
                    self._layer_stack.generation_area)
                painter = QPainter(image)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
                painter.drawImage(QRect(QPoint(0, 0), image.size()), inpaint_mask)
                painter.end()
            bounds = self._layer_stack.generation_area
            layer = self._layer_stack.active_layer
            if layer is None:
                self._layer_stack.create_layer(image_data=image)
            else:
                pos = layer.position
                prev_image = layer.cropped_image_content(bounds)

                def apply_selection():
                    """Inserts the generated image into the active layer."""
                    layer.insert_image_content(image, QRect(bounds.topLeft() - pos, bounds.size()),
                                               QPainter.CompositionMode.CompositionMode_SourceOver)

                def undo_selection():
                    """Revert the image generation area to its previous state."""
                    layer.insert_image_content(prev_image, bounds)

                commit_action(apply_selection, undo_selection)
            AppStateTracker.set_app_state(APP_STATE_EDITING)

    # Selection menu:
    @menu_action(MENU_SELECTION, 'select_all_shortcut', 30, valid_app_states=[APP_STATE_EDITING])
    def select_all(self) -> None:
        """Selects the entire image."""
        if self._layer_stack.has_image:
            self._layer_stack.selection_layer.select_all()

    @menu_action(MENU_SELECTION, 'select_none_shortcut', 31, valid_app_states=[APP_STATE_EDITING])
    def select_none(self) -> None:
        """Clears the selection."""
        self._layer_stack.selection_layer.clear()

    @menu_action(MENU_SELECTION, 'invert_selection_shortcut', 32, valid_app_states=[APP_STATE_EDITING])
    def invert_selection(self) -> None:
        """Swaps selected and unselected areas."""
        if self._layer_stack.has_image:
            self._layer_stack.selection_layer.invert_selection()

    @menu_action(MENU_SELECTION, 'select_layer_content_shortcut', valid_app_states=[APP_STATE_EDITING])
    def select_active_layer_content(self) -> None:
        """Selects all pixels in the active layer that are not fully transparent."""
        active_layer = self._layer_stack.active_layer
        if active_layer is not None:
            self._layer_stack.selection_layer.qimage = active_layer.qimage

    @menu_action(MENU_SELECTION, 'grow_selection_shortcut', valid_app_states=[APP_STATE_EDITING])
    def grow_selection(self, num_pixels=1) -> None:
        """Expand the selection by a given pixel count, 1 by default."""
        if self._layer_stack.has_image:
            self._layer_stack.selection_layer.grow_or_shrink_selection(num_pixels)

    @menu_action(MENU_SELECTION, 'shrink_selection_shortcut', valid_app_states=[APP_STATE_EDITING])
    def shrink_selection(self, num_pixels=1) -> None:
        """Contract the selection by a given pixel count, 1 by default."""
        if self._layer_stack.has_image:
            self._layer_stack.selection_layer.grow_or_shrink_selection(-num_pixels)

    # Layer menu:
    @menu_action(MENU_LAYERS, 'new_layer_shortcut', 40,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_SELECTION])
    def new_layer(self) -> None:
        """Create a new image layer above the active layer."""
        if self._layer_stack.has_image:
            self._layer_stack.create_layer()

    @menu_action(MENU_LAYERS, 'copy_layer_shortcut', 41,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_SELECTION])
    def copy_layer(self) -> None:
        """Create a copy of the active layer."""
        if self._layer_stack.has_image:
            self._layer_stack.copy_layer()

    @menu_action(MENU_LAYERS, 'delete_layer_shortcut', 42, valid_app_states=[APP_STATE_EDITING])
    def delete_layer(self) -> None:
        """Delete the active layer."""
        self._layer_stack.remove_layer()

    @menu_action(MENU_LAYERS, 'select_previous_layer_shortcut', 43,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_SELECTION])
    def select_previous_layer(self) -> None:
        """Select the layer above the current active layer."""
        self._layer_stack.offset_active_selection(-1)

    @menu_action(MENU_LAYERS, 'select_next_layer_shortcut', 44,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_SELECTION])
    def select_next_layer(self) -> None:
        """Select the layer below the current active layer."""
        self._layer_stack.offset_active_selection(1)

    @menu_action(MENU_LAYERS, 'move_layer_up_shortcut', 45, valid_app_states=[APP_STATE_EDITING])
    def move_layer_up(self) -> None:
        """Move the active layer up in the image."""
        self._layer_stack.move_layer(-1)

    @menu_action(MENU_LAYERS, 'move_layer_down_shortcut', 46, valid_app_states=[APP_STATE_EDITING])
    def move_layer_down(self) -> None:
        """Move the active layer down in the image."""
        self._layer_stack.move_layer(1)

    @menu_action(MENU_LAYERS, 'merge_layer_down_shortcut', valid_app_states=[APP_STATE_EDITING])
    def merge_layer_down(self) -> None:
        """Merge the active layer with the one beneath it."""
        self._layer_stack.merge_layer_down()

    @menu_action(MENU_LAYERS, 'layer_to_image_size_shortcut', 48, valid_app_states=[APP_STATE_EDITING])
    def layer_to_image_size(self) -> None:
        """Crop or expand the active layer to match the image size."""
        self._layer_stack.layer_to_image_size()

    @menu_action(MENU_LAYERS, 'crop_to_content_shortcut', 49, valid_app_states=[APP_STATE_EDITING])
    def crop_layer_to_content(self) -> None:
        """Crop the active layer to remove fully transparent border pixels."""
        layer = self._layer_stack.active_layer
        if layer is not None:
            layer.crop_to_content()

    # Tool menu:
    @menu_action(MENU_TOOLS, 'show_layer_menu_shortcut', 50)
    def show_layer_panel(self) -> None:
        """Opens the layer panel window"""
        if self._layer_panel is None:
            self._layer_panel = LayerPanel(self._layer_stack)
            self._layer_panel.show()
            self._layer_panel.raise_()

    @menu_action(MENU_TOOLS, 'settings_shortcut', 51)
    def show_settings(self) -> None:
        """Show the settings window."""
        if self._settings_panel is None:
            assert self._window is not None
            self._settings_panel = SettingsModal(self._window)
            self.init_settings(self._settings_panel)
            self._settings_panel.changes_saved.connect(self.update_settings)
        self.refresh_settings(self._settings_panel)
        self._settings_panel.show_modal()

    @menu_action(MENU_TOOLS, 'image_window_shortcut', 52)
    def show_image_window(self) -> None:
        """Show the image preview window."""
        assert self._window is not None
        self._window.show_image_window()

    # Internal/protected:

    def _scale(self, new_size: QSize) -> None:  # Override to allow alternate or external upscalers:
        config = AppConfig.instance()
        width = self._layer_stack.width
        height = self._layer_stack.height
        if new_size is None or (new_size.width() == width and new_size.height() == height):
            return
        image = self._layer_stack.pil_image()
        if new_size.width() <= width and new_size.height() <= height:  # downscaling
            scale_mode = PIL_SCALING_MODES[config.get(AppConfig.DOWNSCALE_MODE)]
        else:
            scale_mode = PIL_SCALING_MODES[config.get(AppConfig.UPSCALE_MODE)]
        scaled_image = image.resize((new_size.width(), new_size.height()), scale_mode)
        self._layer_stack.set_image(scaled_image)

    def _start_thread(self, thread_worker: QObject, loading_text: Optional[str] = None) -> None:
        assert self._window is not None
        self._window.set_is_loading(True, loading_text)
        self._thread = QThread()
        self._worker = thread_worker
        self._worker.moveToThread(self._thread)

        def clear_worker() -> None:
            """Clean up thread worker object on finish."""
            assert self._window is not None and self._worker is not None
            if self._thread is not None:
                self._thread.quit()
            self._window.set_is_loading(False)
            self._worker.deleteLater()
            self._worker = None

        self._worker.finished.connect(clear_worker)
        self._thread.started.connect(self._worker.run)

        def clear_old_thread() -> None:
            """Cleanup async task thread on finish."""
            assert self._thread is not None
            AppStateTracker.set_app_state(APP_STATE_EDITING)
            self._thread.deleteLater()
            self._thread = None

        self._thread.finished.connect(clear_old_thread)
        self._thread.start()
        AppStateTracker.set_app_state(APP_STATE_LOADING)

    # Image generation handling:
    def _inpaint(self,
                 source_image_section: Optional[Image.Image],
                 mask: Optional[Image.Image],
                 save_image: Callable[[Image.Image, int], None],
                 status_signal: pyqtSignal) -> None:
        """Unimplemented method for handling image inpainting.

        Parameters
        ----------
        source_image_section : PIL Image, optional
            Image selection to edit
        mask : PIL Image, optional
            Mask marking edited image region.
        save_image : function (PIL Image, int)
            Function used to return each image response and its index.
        status_signal : pyqtSignal
            Signal to emit when status updates are available.
        """
        raise NotImplementedError('_inpaint method not implemented.')

    def _apply_status_update(self, unused_status_dict: dict) -> None:
        """Optional unimplemented method for handling image editing status updates."""
