"""
AppController coordinates IntraPaint application behavior.
"""
import json
import logging
import os
import re
import sys
from argparse import Namespace
from typing import Optional, Any, List, Tuple, Callable, Set

from PIL import Image, UnidentifiedImageError, ExifTags
from PIL.ExifTags import IFD
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QMessageBox

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.controller.image_generation.glid3_webservice_generator import Glid3WebserviceGenerator, DEFAULT_GLID_URL
from src.controller.image_generation.glid3_xl_generator import Glid3XLGenerator
from src.controller.image_generation.image_generator import ImageGenerator
from src.controller.image_generation.null_generator import NullGenerator
from src.controller.image_generation.sd_webui_generator import SDWebUIGenerator, DEFAULT_SD_URL
from src.controller.image_generation.test_generator import TestGenerator
from src.image.filter.blur import BlurFilter
from src.image.filter.brightness_contrast import BrightnessContrastFilter
from src.image.filter.posterize import PosterizeFilter
from src.image.filter.rgb_color_balance import RGBColorBalanceFilter
from src.image.filter.sharpen import SharpenFilter
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.layer_stack import LayerStack
from src.image.layers.text_layer import TextLayer
from src.image.layers.transform_group import TransformGroup
from src.image.layers.transform_layer import TransformLayer
from src.image.open_raster import save_ora_image, read_ora_image
from src.ui.modal.image_scale_modal import ImageScaleModal
from src.ui.modal.modal_utils import show_error_dialog, request_confirmation, open_image_file, open_image_layers, \
    show_warning_dialog
from src.ui.modal.new_image_modal import NewImageModal
from src.ui.modal.resize_canvas_modal import ResizeCanvasModal
from src.ui.modal.settings_modal import SettingsModal
from src.ui.panel.layer_ui.layer_panel import LayerPanel
from src.ui.window.generator_setup_window import GeneratorSetupWindow
from src.ui.window.main_window import MainWindow
from src.undo_stack import UndoStack
from src.util.application_state import AppStateTracker, APP_STATE_NO_IMAGE, APP_STATE_EDITING, APP_STATE_LOADING, \
    APP_STATE_SELECTION
from src.util.display_size import get_screen_size
from src.util.image_utils import pil_image_scaling, create_transparent_image, METADATA_PARAMETER_KEY, load_image, \
    METADATA_COMMENT_KEY, IMAGE_FORMATS_SUPPORTING_ALPHA, image_is_fully_opaque, IMAGE_FORMATS_SUPPORTING_METADATA, \
    save_image_with_metadata, save_image, IMAGE_WRITE_FORMATS, IMAGE_READ_FORMATS, \
    IMAGE_FORMATS_SUPPORTING_PARTIAL_ALPHA, image_has_partial_alpha, IMAGE_FORMATS_WITH_FIXED_SIZE, \
    GREYSCALE_IMAGE_FORMATS
from src.util.menu_builder import MenuBuilder, menu_action, MENU_DATA_ATTR, MenuData
from src.util.optional_import import optional_import
from src.util.qtexcepthook import QtExceptHook

# Optional spacenav support and extended theming:
qdarktheme = optional_import('qdarktheme')
qt_material = optional_import('qt_material')
SpacenavManager = optional_import('src.controller.spacenav_manager', attr_name='SpacenavManager')

logger = logging.getLogger(__name__)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'controller.app_controller'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


GENERATION_MODE_SD_WEBUI = 'stable'
GENERATION_MODE_LOCAL_GLID = 'local'
GENERATION_MODE_WEB_GLID = 'web'
GENERATION_MODE_TEST = 'mock'
GENERATION_MODE_AUTO = 'auto'

MENU_FILE = _tr('File')
MENU_EDIT = _tr('Edit')
MENU_IMAGE = _tr('Image')
MENU_SELECTION = _tr('Selection')
MENU_LAYERS = _tr('Layers')
MENU_TOOLS = _tr('Tools')
MENU_FILTERS = _tr('Filters')

SUBMENU_MOVE = _tr('Move')
SUBMENU_SELECT = _tr('Select')
SUBMENU_TRANSFORM = _tr('Transform')

GENERATOR_LOAD_ERROR_TITLE = _tr('Loading image generator failed')
GENERATOR_LOAD_ERROR_MESSAGE = _tr('Unable to load the {generator_name} image generator')
CONFIRM_QUIT_TITLE = _tr('Quit now?')
CONFIRM_QUIT_MESSAGE = _tr('All unsaved changes will be lost.')
NEW_IMAGE_CONFIRMATION_TITLE = _tr('Create new image?')
NEW_IMAGE_CONFIRMATION_MESSAGE = _tr('This will discard all unsaved changes.')
SAVE_ERROR_TITLE = _tr('Save failed')
LOAD_ERROR_TITLE = _tr('Open failed')
RELOAD_ERROR_TITLE = _tr('Reload failed')
RELOAD_ERROR_MESSAGE_INVALID_FILE = _tr('Image path "{file_path}" is not a valid image file.')
RELOAD_ERROR_MESSAGE_NO_IMAGE = _tr('Enter an image path or click "Open Image" first.')
RELOAD_CONFIRMATION_TITLE = _tr('Reload image?')
RELOAD_CONFIRMATION_MESSAGE = _tr('This will discard all unsaved changes.')
METADATA_UPDATE_TITLE = _tr('Metadata updated')
METADATA_UPDATE_MESSAGE = _tr('On save, current image generation parameters will be stored within the image')
RESIZE_ERROR_TITLE = _tr('Resize failed')
GENERATE_ERROR_TITLE_UNEXPECTED = _tr('Inpainting failure')
GENERATE_ERROR_TITLE_NO_IMAGE = _tr('Save failed')
GENERATE_ERROR_TITLE_EXISTING_OP = _tr('Failed')
GENERATE_ERROR_MESSAGE_EXISTING_OP = _tr('Existing image generation operation not yet finished, wait a little longer.')
SETTINGS_ERROR_MESSAGE = _tr('Settings not supported in this mode.')
SETTINGS_ERROR_TITLE = _tr('Failed to open settings')
LOAD_LAYER_ERROR_TITLE = _tr('Opening layers failed')
LOAD_LAYER_ERROR_MESSAGE = _tr('Could not open the following images: ')

TITLE_CONFIRM_METADATA_INIT = _tr('Save image generation metadata?')
MESSAGE_CONFIRM_METADATA_INIT = _tr('No image metadata is cached, would you like to save image generation parameters to'
                                    ' this image?')
TITLE_CONFIRM_METADATA_UPDATE = _tr('Update image generation metadata?')
MESSAGE_CONFIRM_METADATA_UPDATE = _tr('Image generation parameters have changed, would you like this image to be saved'
                                      ' with the most recent values?')

# Warnings when saving images cause data loss:
LAYERS_NOT_SAVED_TITLE = _tr('Image saved without layer data')
LAYERS_NOT_SAVED_MESSAGE = _tr('To save layer data, images must be saved in .ora format.')

ALPHA_NOT_SAVED_TITLE = _tr('Image saved without full transparency')
ALPHA_NOT_SAVED_MESSAGE = _tr('To preserve transparency, save using one of the following file formats:'
                              ' {alpha_formats}')

METADATA_NOT_SAVED_TITLE = _tr('Image saved without image generation metadata')
METADATA_NOT_SAVED_MESSAGE = _tr('To preserve image generation metadata, save using one of the following file formats:'
                                 ' {metadata_formats}')

WRITE_ONLY_SAVE_TITLE = _tr('Image saved in a write-only format')
WRITE_ONLY_SAVE_MESSAGE = _tr('IntraPaint can write images in the {file_format} format, but cannot load them. Use '
                              'another file format if you want to be able to load this image in IntraPaint again.')

FIXED_SIZE_SAVE_TITLE = _tr('Image saved in a format that changes size')
FIXED_SIZE_SAVE_MESSAGE = _tr('The image is {width_px}x{height_px}, but the {file_format} format saves all images at'
                              ' {saved_width_px}x{saved_height_px} resolution. Use another file format if you want'
                              ' to preserve the original image size.')

NO_COLOR_SAVE_TITLE = _tr('Image saved without color')
NO_COLOR_SAVE_MESSAGE = _tr('The {file_format} format saves the image without color. Use another format if you want'
                            ' to preserve image colors.')

IGNORED_APPCONFIG_CATEGORIES = ('Stable-Diffusion', 'GLID-3-XL')
DEV_APPCONFIG_CATEGORY = 'Developer'


def _get_config_categories() -> List[str]:
    categories = AppConfig().get_categories()
    for ignored in IGNORED_APPCONFIG_CATEGORIES:
        if ignored in categories:
            categories.remove(ignored)
    if DEV_APPCONFIG_CATEGORY in categories and '--dev' not in sys.argv:
        categories.remove(DEV_APPCONFIG_CATEGORY)
    return categories


class AppController(MenuBuilder):
    """AppController coordinates IntraPaint application behavior."""

    def __init__(self, args: Namespace) -> None:
        super().__init__()
        app = QApplication.instance() or QApplication(sys.argv)
        config = AppConfig()
        config.apply_args(args)
        self._layer_panel: Optional[LayerPanel] = None
        self._generator_window: Optional[GeneratorSetupWindow] = None

        # Initialize edited image data structures:
        self._image_stack = ImageStack(config.get(AppConfig.DEFAULT_IMAGE_SIZE), config.get(AppConfig.EDIT_SIZE),
                                       config.get(AppConfig.MIN_EDIT_SIZE), config.get(AppConfig.MAX_EDIT_SIZE))

        self._metadata: Optional[dict[str, Any]] = None
        self._exif: Optional[Image.Exif] = None

        # Initialize main window:
        self._window = MainWindow(self._image_stack)
        self.menu_window = self._window
        self._window.generate_signal.connect(self.start_and_manage_inpainting)
        if args.window_size is not None:
            width, height = (int(dim) for dim in args.window_size.split('x'))
            self._window.setGeometry(0, 0, width, height)
            self._window.setMaximumSize(width, height)
            self._window.setMinimumSize(width, height)
        else:
            size = get_screen_size(self._window)
            self._window.setGeometry(0, 0, size.width(), size.height())
            self._window.setMaximumSize(size)
        if args.init_image is not None:
            self.load_image(file_path=args.init_image)

        # Prepare generator options:
        self._sd_generator = SDWebUIGenerator(self._window, self._image_stack, args)
        self._glid_generator = Glid3XLGenerator(self._window, self._image_stack, args)
        self._glid_web_generator = Glid3WebserviceGenerator(self._window, self._image_stack, args)
        self._test_generator = TestGenerator(self._window, self._image_stack)
        self._null_generator = NullGenerator(self._window, self._image_stack)
        self._generator: ImageGenerator = self._null_generator

        # Load settings:
        self._settings_modal = SettingsModal(self._window)
        self.init_settings(self._settings_modal)
        self._settings_modal.changes_saved.connect(self.update_settings)

        # TODO: Spacemouse support is broken due to some strange thread management issues that popped up around the
        #       transition to Qt6. The feature was fairly underwhelming anyway, so fixing it is low priority.
        # # Configure support for spacemouse panning, if relevant:
        # if SpacenavManager is not None and self._window is not None:
        #     assert SpacenavManager is not None
        #     nav_manager = SpacenavManager(self._window, self._image_stack)
        #     nav_manager.start_thread()
        #     self._nav_manager = nav_manager

        # Set up menus:
        self.build_menus()
        # Since image filter menus follow a very simple pattern, add them here instead of using @menu_action:
        for filter_class in (RGBColorBalanceFilter,
                             BrightnessContrastFilter,
                             BlurFilter,
                             SharpenFilter,
                             PosterizeFilter):
            image_filter = filter_class(self._image_stack)

            def _open_filter_modal(filter_instance=image_filter) -> None:
                modal = filter_instance.get_filter_modal()
                modal.exec()

            config_key = image_filter.get_config_key()
            action = self.add_menu_action(MENU_FILTERS,
                                          _open_filter_modal,
                                          config_key)
            assert action is not None
            AppStateTracker.set_enabled_states(action, [APP_STATE_EDITING])

        self._last_active = self._image_stack.active_layer
        self._lock_connection = self._last_active.lock_changed.connect(
            lambda _layer, _lock: self._update_enabled_actions())

        def _active_changed(active_layer: Layer) -> None:
            self._last_active.lock_changed.disconnect(self._lock_connection)
            self._last_active = active_layer
            self._lock_connection = self._last_active.lock_changed.connect(
                lambda _layer, _lock: self._update_enabled_actions())
            self._update_enabled_actions()

        self._image_stack.active_layer_changed.connect(_active_changed)
        self._image_stack.selection_layer.content_changed.connect(lambda _layer: self._update_enabled_actions())
        UndoStack().undo_count_changed.connect(lambda _count: self._update_enabled_actions())  # type: ignore
        UndoStack().redo_count_changed.connect(lambda _count: self._update_enabled_actions())  # type: ignore

        # Load and apply styling and themes:

        def _apply_style(new_style: str) -> None:
            app.setStyle(new_style)

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
                qt_material.apply_stylesheet(app, theme=xml_file)
            elif theme != 'None':
                logger.error(f'Failed to load theme {theme}')

        config.connect(self, AppConfig.THEME, _apply_theme)
        _apply_theme(config.get(AppConfig.THEME))

        def _apply_font(font_pt: int) -> None:
            font = app.font()
            font.setPointSize(font_pt)
            app.setFont(font)

        config.connect(self, AppConfig.FONT_POINT_SIZE, _apply_font)
        _apply_font(config.get(AppConfig.FONT_POINT_SIZE))

        # Load image generator, if any:
        mode = args.mode
        match mode:
            case _ if mode == GENERATION_MODE_SD_WEBUI:
                self.load_image_generator(self._sd_generator)
            case _ if mode == GENERATION_MODE_WEB_GLID:
                self.load_image_generator(self._glid_web_generator)
            case _ if mode == GENERATION_MODE_LOCAL_GLID:
                self.load_image_generator(self._glid_generator)
            case _ if mode == GENERATION_MODE_TEST:
                self.load_image_generator(self._test_generator)
            case _:
                if mode != GENERATION_MODE_AUTO:
                    logger.error(f'Unexpected mode {mode}, defaulting to mode=auto')
                server_url = args.server_url
                if server_url == DEFAULT_SD_URL:
                    self.load_image_generator(self._sd_generator)
                elif server_url == DEFAULT_GLID_URL:
                    self.load_image_generator(self._glid_web_generator)
                if self._sd_generator.is_available():
                    self.load_image_generator(self._sd_generator)
                    return
                if self._glid_web_generator.is_available():
                    self.load_image_generator(self._glid_generator)
                    return
                if args.dev:
                    self.load_image_generator(self._test_generator)
                else:
                    if self._glid_generator.is_available():
                        self.load_image_generator(self._glid_generator)
                        return
                logger.info('No valid generator detected, starting with none enabled.')

    def start_app(self) -> None:
        """Start the application."""
        app = QApplication.instance() or QApplication(sys.argv)
        if AppConfig().get(AppConfig.USE_ERROR_HANDLER):
            QtExceptHook().enable()
        self._window.show()
        AppStateTracker.set_app_state(APP_STATE_EDITING if self._image_stack.has_image else APP_STATE_NO_IMAGE)
        app.exec()

    def load_image_generator(self, generator: ImageGenerator) -> None:
        """Load an image generator, updating controls and settings."""
        if not generator.configure_or_connect():
            show_error_dialog(self._window, GENERATOR_LOAD_ERROR_TITLE,
                              GENERATOR_LOAD_ERROR_MESSAGE.format(generator_name=generator.get_display_name()))
            return
        if self._generator is not None:
            for tab in self._generator.get_extra_tabs():
                self._window.remove_tab(tab)
            self._generator.unload_settings(self._settings_modal)
            self._generator.clear_menus()
            self._generator.disconnect_or_disable()
        self._generator = generator
        self._generator.menu_window = self._window
        self._generator.init_settings(self._settings_modal)
        self._generator.build_menus()
        self._window.set_control_panel(self._generator.get_control_panel())
        for tab in self._generator.get_extra_tabs():
            # Remember to adjust this if you add any other generator-specific tabs
            self._window.add_tab(tab, AppConfig().get(AppConfig.CONTROLNET_TAB_BAR))
        if self._generator_window is not None:
            self._generator_window.mark_active_generator(generator)

    def init_settings(self, settings_modal: SettingsModal) -> None:
        """Load application settings into a SettingsModal"""
        categories = _get_config_categories()
        settings_modal.load_from_config(AppConfig(), categories)
        settings_modal.load_from_config(KeyConfig())
        if self._generator is not None:
            self._generator.init_settings(settings_modal)

    def refresh_settings(self, settings_modal: SettingsModal):
        """Updates a SettingsModal to reflect any changes."""
        config = AppConfig()
        categories = _get_config_categories()
        settings = {}
        for category in categories:
            for key in config.get_category_keys(category):
                settings[key] = config.get(key)
        settings_modal.update_settings(settings)
        if self._generator is not None:
            self._generator.refresh_settings(settings_modal)

    def update_settings(self, changed_settings: dict):
        """
        Apply changed settings from a SettingsModal.

        Parameters
        ----------
        changed_settings : dict
            Set of changes loaded from a SettingsModal.
        """
        app_config = AppConfig()
        categories = _get_config_categories()
        base_keys = [key for cat in categories for key in app_config.get_category_keys(cat)]
        key_keys = KeyConfig().get_keys()
        for key, value in changed_settings.items():
            if key in base_keys:
                app_config.set(key, value)
            elif key in key_keys:
                KeyConfig().set(key, value)
        if self._generator is not None:
            self._generator.update_settings(changed_settings)

    def _update_enabled_actions(self) -> None:
        self.get_action_for_method(self.undo).setEnabled(UndoStack().undo_count() > 0)
        self.get_action_for_method(self.redo).setEnabled(UndoStack().redo_count() > 0)

        def _test_state(menu_action_method: Callable[..., None]) -> bool:
            app_state = AppStateTracker.app_state()
            assert callable(menu_action_method) and hasattr(menu_action_method, MENU_DATA_ATTR)
            data = getattr(menu_action_method, MENU_DATA_ATTR, None)
            assert isinstance(data, MenuData)
            if data.valid_app_states is None:
                return True
            return app_state in data.valid_app_states

        selection_is_empty = self._image_stack.selection_layer.empty
        selection_methods: Set[Callable[..., None]] = {
            self.cut,
            self.copy,
            self.clear,
            self.grow_selection,
            self.shrink_selection
        }
        unlocked_layer_methods: Set[Callable[..., None]] = {
            self.cut,
            self.clear,
            self.layer_mirror_horizontal,
            self.layer_mirror_vertical,
            self.layer_rotate_cw,
            self.layer_rotate_ccw,
            self.delete_layer,
            self.merge_layer_down,
            self.layer_to_image_size,
            self.crop_layer_to_content

        }
        not_bottom_layer_methods: Set[Callable[..., None]] = {
            self.select_next_layer,
            self.move_layer_down
        }
        not_top_layer_methods: Set[Callable[..., None]] = {
            self.select_previous_layer,
            self.move_layer_up,
            self.move_layer_to_top
        }
        not_layer_stack_methods: Set[Callable[..., None]] = {
            self.select_previous_layer,
            self.move_layer_up,
            self.move_layer_down,
            self.move_layer_to_top
        }
        not_layer_group_methods: Set[Callable[..., None]] = {self.merge_layer_down}

        not_text_layer_methods: Set[Callable[..., None]] = {self.crop_layer_to_content}

        managed_menu_methods = selection_methods | unlocked_layer_methods | not_bottom_layer_methods \
                               | not_top_layer_methods | not_layer_stack_methods | not_layer_group_methods

        active_layer = self._image_stack.active_layer
        is_top_layer = active_layer == self._image_stack.layer_stack or self._image_stack.prev_layer(active_layer) \
            in (None, self._image_stack.layer_stack)
        is_bottom_layer = active_layer != self._image_stack.layer_stack \
            and self._image_stack.next_layer(active_layer) is None
        for menu_method in managed_menu_methods:
            action = self.get_action_for_method(menu_method)
            assert action is not None
            if not _test_state(menu_method):
                action.setEnabled(False)
                continue
            action.setEnabled(True)
            for method_set, disable_condition in ((selection_methods, selection_is_empty),
                                                  (unlocked_layer_methods, active_layer.locked),
                                                  (not_bottom_layer_methods, is_bottom_layer),
                                                  (not_top_layer_methods, is_top_layer),
                                                  (not_layer_stack_methods,
                                                   active_layer == self._image_stack.layer_stack),
                                                  (not_layer_group_methods, isinstance(active_layer, LayerStack)),
                                                  (not_text_layer_methods, isinstance(active_layer, TextLayer))):
                if menu_method in method_set and disable_condition:
                    action.setEnabled(False)
                    break

    # Menu action definitions:

    # File menu:

    @menu_action(MENU_FILE, 'new_image_shortcut', 0,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_NO_IMAGE])
    def new_image(self) -> None:
        """Open a new image creation modal."""
        default_size = AppConfig().get(AppConfig.DEFAULT_IMAGE_SIZE)
        image_modal = NewImageModal(default_size.width(), default_size.height())
        image_size = image_modal.show_image_modal()
        if image_size and (not self._image_stack.has_image or request_confirmation(self._window,
                                                                                   NEW_IMAGE_CONFIRMATION_TITLE,
                                                                                   NEW_IMAGE_CONFIRMATION_MESSAGE)):
            new_image = create_transparent_image(image_size)
            Cache().set(Cache.LAST_FILE_PATH, '')
            self._image_stack.load_image(new_image)
            self._metadata = None
            self._exif = None
            AppStateTracker.set_app_state(APP_STATE_EDITING)

    @menu_action(MENU_FILE, 'save_shortcut', priority=1,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_SELECTION, APP_STATE_LOADING])
    def save_image(self) -> None:
        """Saves the edited image, only opening the save dialog if no previous image path is cached."""
        image_path = Cache().get(Cache.LAST_FILE_PATH)
        if not os.path.isfile(image_path):
            image_path = None
        self.save_image_as(file_path=image_path)

    @menu_action(MENU_FILE, 'save_as_shortcut', priority=2,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_SELECTION, APP_STATE_LOADING])
    def save_image_as(self, file_path: Optional[str] = None) -> None:
        """Open a save dialog, and save the edited image to disk, preserving any metadata."""
        cache = Cache()
        config = AppConfig()
        try:
            if not isinstance(file_path, str):
                selected_path = open_image_file(self._window, mode='save',
                                                selected_file=cache.get(Cache.LAST_FILE_PATH))
                if not isinstance(selected_path, str):
                    return
                file_path = selected_path
            assert isinstance(file_path, str)
            delimiter_index = file_path.rfind('.')
            if delimiter_index < 0:
                raise ValueError(f'Invalid path {file_path} missing extension')
            file_format = file_path[delimiter_index + 1:].upper()

            # Check if metadata is out of date, ask if it should update:
            if file_format in IMAGE_FORMATS_SUPPORTING_METADATA and not isinstance(self._generator, NullGenerator):
                if not self._metadata_will_be_saved():
                    update_metadata = request_confirmation(self._window, TITLE_CONFIRM_METADATA_INIT,
                                                           MESSAGE_CONFIRM_METADATA_INIT,
                                                           AppConfig.ALWAYS_INIT_METADATA_ON_SAVE,
                                                           QMessageBox.StandardButton.Yes,
                                                           QMessageBox.StandardButton.No)
                elif not self._metadata_is_latest():
                    update_metadata = request_confirmation(self._window, TITLE_CONFIRM_METADATA_UPDATE,
                                                           MESSAGE_CONFIRM_METADATA_UPDATE,
                                                           AppConfig.ALWAYS_UPDATE_METADATA_ON_SAVE,
                                                           QMessageBox.StandardButton.Yes,
                                                           QMessageBox.StandardButton.No)
                else:
                    update_metadata = False
                if update_metadata:
                    self.update_metadata(False)

            if file_path.lower().endswith('.ora'):
                save_ora_image(self._image_stack, file_path, json.dumps(self._metadata))
            else:
                image = self._image_stack.qimage()

                # Check for data loss conditions that should be mentioned:
                warn_save_discards_layers = (config.get(AppConfig.WARN_BEFORE_LAYERLESS_SAVE)
                                             and self._image_stack.layer_stack.count > 1)
                warn_save_discards_alpha = (config.get(AppConfig.WARN_BEFORE_RGB_SAVE)
                                            and ((file_format not in IMAGE_FORMATS_SUPPORTING_ALPHA
                                                  and not image_is_fully_opaque(image))
                                                 or (file_format in IMAGE_FORMATS_SUPPORTING_PARTIAL_ALPHA
                                                     and image_has_partial_alpha(image))))
                warn_save_discards_metadata = (config.get(AppConfig.WARN_BEFORE_SAVE_WITHOUT_METADATA)
                                               and self._metadata is not None
                                               and METADATA_PARAMETER_KEY in self._metadata
                                               and file_format not in IMAGE_FORMATS_SUPPORTING_METADATA)
                warn_save_is_write_only = (config.get(AppConfig.WARN_BEFORE_WRITE_ONLY_SAVE)
                                           and file_format in IMAGE_WRITE_FORMATS
                                           and file_format not in IMAGE_READ_FORMATS)
                warn_save_changes_size = (config.get(AppConfig.WARN_BEFORE_FIXED_SIZE_SAVE)
                                          and file_format in IMAGE_FORMATS_WITH_FIXED_SIZE
                                          and image.size() != IMAGE_FORMATS_WITH_FIXED_SIZE[file_format])
                warn_save_removes_color = (config.get(AppConfig.WARN_BEFORE_COLOR_LOSS)
                                           and file_format in GREYSCALE_IMAGE_FORMATS)
                if file_format in IMAGE_FORMATS_SUPPORTING_METADATA:

                    try:
                        save_image_with_metadata(image, file_path, self._metadata, self._exif)
                    except ValueError:
                        logger.error(f'Format {file_format} should support metadata, but saving with metadata failed.')
                        warn_save_discards_metadata = config.get(AppConfig.WARN_BEFORE_SAVE_WITHOUT_METADATA)
                        save_image(image, file_path, self._exif)
                else:
                    save_image(image, file_path, self._exif)

                # Show data loss warnings, if not disabled:
                alpha_loss_message = ALPHA_NOT_SAVED_MESSAGE
                metadata_loss_message = METADATA_NOT_SAVED_MESSAGE
                fixed_size_message = FIXED_SIZE_SAVE_MESSAGE
                color_loss_message = NO_COLOR_SAVE_MESSAGE
                write_only_message = WRITE_ONLY_SAVE_MESSAGE

                def _extension_str(extensions: Tuple[str, ...]) -> str:
                    return ', '.join((f'.{ext.lower()}' for ext in extensions))
                format_str = f'.{file_format.lower()}'

                if warn_save_discards_alpha:
                    alpha_loss_message = alpha_loss_message.format(
                        alpha_formats=_extension_str(IMAGE_FORMATS_SUPPORTING_ALPHA))
                if warn_save_discards_metadata:
                    metadata_loss_message = metadata_loss_message.format(
                        metadata_formats=_extension_str(IMAGE_FORMATS_SUPPORTING_METADATA))
                if warn_save_changes_size:
                    final_size = IMAGE_FORMATS_WITH_FIXED_SIZE[file_format]
                    fixed_size_message = fixed_size_message.format(width_px=image.width(),
                                                                   height_px=image.height(),
                                                                   file_format=format_str,
                                                                   saved_width_px=final_size.width(),
                                                                   saved_height_px=final_size.height())
                if warn_save_is_write_only:
                    write_only_message = write_only_message.format(file_format=format_str)
                if warn_save_removes_color:
                    color_loss_message = color_loss_message.format(file_format=format_str)

                for loss_condition, warn_on_save_config_key, title, message in (
                        (warn_save_discards_layers, AppConfig.WARN_BEFORE_LAYERLESS_SAVE, LAYERS_NOT_SAVED_TITLE,
                         LAYERS_NOT_SAVED_MESSAGE),
                        (warn_save_discards_alpha, AppConfig.WARN_BEFORE_RGB_SAVE, ALPHA_NOT_SAVED_TITLE,
                         alpha_loss_message),
                        (warn_save_discards_metadata, AppConfig.WARN_BEFORE_SAVE_WITHOUT_METADATA,
                         METADATA_NOT_SAVED_TITLE, metadata_loss_message),
                        (warn_save_is_write_only, AppConfig.WARN_BEFORE_WRITE_ONLY_SAVE, WRITE_ONLY_SAVE_TITLE,
                         write_only_message),
                        (warn_save_changes_size, AppConfig.WARN_BEFORE_FIXED_SIZE_SAVE, FIXED_SIZE_SAVE_TITLE,
                         fixed_size_message),
                        (warn_save_removes_color, AppConfig.WARN_BEFORE_COLOR_LOSS, NO_COLOR_SAVE_TITLE,
                         color_loss_message)):
                    if loss_condition:
                        show_warning_dialog(self._window, title, message, warn_on_save_config_key)
            cache.set(Cache.LAST_FILE_PATH, file_path)
        except (IOError, TypeError) as save_err:
            show_error_dialog(self._window, SAVE_ERROR_TITLE, str(save_err))
            raise save_err

    @menu_action(MENU_FILE, 'load_shortcut', 3,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_NO_IMAGE])
    def load_image(self, file_path: Optional[str | List[str]] = None) -> None:
        """Open a loading dialog, then load the selected image for editing."""
        cache = Cache()
        config = AppConfig()
        if file_path is None:
            selected_path = open_image_file(self._window)
            if not isinstance(selected_path, (str, list)):
                return
            file_path = selected_path
        if isinstance(file_path, list):
            if len(file_path) != 1:
                logger.warning(f'Expected single image, got list with length {len(file_path)}')
            file_path = file_path[0]
        assert isinstance(file_path, str)
        self._exif = Image.Exif()
        self._metadata = None
        try:
            assert file_path is not None
            if file_path.lower().endswith('.ora'):
                metadata = read_ora_image(self._image_stack, file_path)
                if metadata is not None and len(metadata) > 0:
                    self._metadata = json.loads(metadata)
            else:
                image, exif, image_info = load_image(file_path)
                # try and load metadata:
                if image_info is not None:
                    if METADATA_COMMENT_KEY in image_info and METADATA_PARAMETER_KEY not in image_info:
                        image_info[METADATA_PARAMETER_KEY] = image_info[METADATA_COMMENT_KEY]
                    self._metadata = image_info
                if exif is not None:
                    if isinstance(exif, Image.Exif):
                        self._exif = exif
                    elif (self._metadata is None or METADATA_PARAMETER_KEY
                          not in self._metadata) and isinstance(exif, dict):
                        self._metadata = exif
                        if 'exif' in exif:
                            self._exif.load(exif['exif'])
                if (self._metadata is None or METADATA_PARAMETER_KEY not in self._metadata) and self._exif is not None:
                    exif_tags = self._exif.get_ifd(IFD.Exif)
                    description = exif_tags.get(ExifTags.Base.ImageDescription)
                    if description is None:
                        description = self._exif.get(ExifTags.Base.ImageDescription)
                    if description is not None:
                        if self._metadata is None:
                            self._metadata = {}
                        self._metadata[METADATA_PARAMETER_KEY] = description
                self._image_stack.load_image(QImage(file_path))
            cache.set(Cache.LAST_FILE_PATH, file_path)

            # File loaded, attempt to apply metadata:
            if self._metadata is not None and METADATA_PARAMETER_KEY in self._metadata:
                param_str = self._metadata[METADATA_PARAMETER_KEY]
                if param_str is not None and not isinstance(param_str, str):
                    # noinspection PyTypeChecker
                    param_str = str(param_str, encoding='utf-8')
                match = re.match(r'^(.*\n?.*)\nSteps: ?(\d+), Sampler: ?(.*), CFG scale: ?(.*), Seed: ?(.+),'
                                 r' Size: ?(.+)x(.+)',  param_str)
                if match:
                    prompt = match.group(1)
                    negative = ''
                    steps = int(match.group(2))
                    sampler = match.group(3)
                    cfg_scale = float(match.group(4))
                    seed = int(match.group(5))
                    width = int(match.group(6))
                    height = int(match.group(7))
                    divider_match = re.match('^(.*)\nNegative prompt: ?(.*)$', prompt)
                    if divider_match:
                        prompt = divider_match.group(1)
                        negative = divider_match.group(2)
                    logger.info('Detected saved image gen data, applying to UI')
                    try:
                        config.set(AppConfig.PROMPT, prompt)
                        config.set(AppConfig.NEGATIVE_PROMPT, negative)
                        config.set(AppConfig.SAMPLING_STEPS, steps)
                        try:
                            config.set(AppConfig.SAMPLING_METHOD, sampler)
                        except ValueError:
                            logger.error(f'sampler "{sampler}" used to generate this image is not supported.')
                        config.set(AppConfig.GUIDANCE_SCALE, cfg_scale)
                        config.set(AppConfig.SEED, seed)
                        config.set(AppConfig.GENERATION_SIZE, QSize(width, height))
                    except (TypeError, RuntimeError) as err:
                        logger.error(f'Failed to load image gen data from metadata: {err}')
                else:
                    logger.warning('image parameters do not match expected patterns, cannot be used. '
                                   f'parameters:{param_str}')
            AppStateTracker.set_app_state(APP_STATE_EDITING)
        except (UnidentifiedImageError, OSError) as err:
            show_error_dialog(self._window, LOAD_ERROR_TITLE, err)
            return

    @menu_action(MENU_FILE, 'load_layers_shortcut', 4,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_NO_IMAGE])
    def load_image_layers(self) -> None:
        """Open one or more images as layers."""
        layer_paths, layers_selected = open_image_layers(self._window)
        if not layers_selected or not layer_paths or len(layer_paths) == 0:
            return
        layers: List[Tuple[QImage, str]] = []
        errors: List[str] = []
        for layer_path in layer_paths:
            try:
                image, _, _ = load_image(layer_path)
                layers.append((image, layer_path))
            except IOError:
                errors.append(layer_path)
        if not self._image_stack.has_image:
            width = 0
            height = 0
            for image, _ in layers:
                width = max(width, image.width())
                height = max(height, image.height())
            base_layer = create_transparent_image(QSize(width, height))
            self._image_stack.load_image(base_layer)
        for image, image_path in layers:
            name = os.path.basename(image_path)
            self._image_stack.create_layer(name, image)
        if len(errors) > 0:
            show_error_dialog(self._window, LOAD_LAYER_ERROR_TITLE, LOAD_LAYER_ERROR_MESSAGE + ','.join(errors))
        if self._image_stack.has_image:
            AppStateTracker.set_app_state(APP_STATE_EDITING)

    @menu_action(MENU_FILE, 'reload_shortcut', 5, valid_app_states=[APP_STATE_EDITING])
    def reload_image(self) -> None:
        """Reload the edited image from disk after getting confirmation from a confirmation dialog."""
        file_path = Cache().get(Cache.LAST_FILE_PATH)
        if file_path == '':
            show_error_dialog(self._window, RELOAD_ERROR_TITLE, RELOAD_ERROR_MESSAGE_NO_IMAGE)
            return
        if not os.path.isfile(file_path):
            show_error_dialog(self._window, RELOAD_ERROR_TITLE,
                              RELOAD_ERROR_MESSAGE_INVALID_FILE.format(file_path=file_path))
            return
        if not self._image_stack.has_image or request_confirmation(self._window,
                                                                   RELOAD_CONFIRMATION_TITLE,
                                                                   RELOAD_CONFIRMATION_MESSAGE):
            self.load_image(file_path=file_path)

    @menu_action(MENU_FILE, 'quit_shortcut', 6)
    def quit(self) -> None:
        """Quit the application after getting confirmation from the user."""
        if request_confirmation(self._window, CONFIRM_QUIT_TITLE, CONFIRM_QUIT_MESSAGE):
            self._window.close()

    # Edit menu:

    @menu_action(MENU_EDIT, 'undo_shortcut', 100,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_NO_IMAGE])
    def undo(self) -> None:
        """Revert the most recent significant change made."""
        UndoStack().undo()

    @menu_action(MENU_EDIT, 'redo_shortcut', 101, valid_app_states=[APP_STATE_EDITING, APP_STATE_NO_IMAGE])
    def redo(self) -> None:
        """Restore the most recent reverted change."""
        UndoStack().redo()

    @menu_action(MENU_EDIT, 'cut_shortcut', 102, valid_app_states=[APP_STATE_EDITING])
    def cut(self) -> None:
        """Cut selected content from the active image layer."""
        self._image_stack.cut_selected()

    @menu_action(MENU_EDIT, 'copy_shortcut', 103, valid_app_states=[APP_STATE_EDITING])
    def copy(self) -> None:
        """Copy selected content from the active image layer."""
        self._image_stack.copy_selected()

    @menu_action(MENU_EDIT, 'paste_shortcut', 104, valid_app_states=[APP_STATE_EDITING])
    def paste(self) -> None:
        """Paste copied image content into a new layer."""
        self._image_stack.paste()

    @menu_action(MENU_EDIT, 'clear_shortcut', 105, valid_app_states=[APP_STATE_EDITING])
    def clear(self) -> None:
        """Clear selected content from the active image layer."""
        self._image_stack.clear_selected()

    @menu_action(MENU_EDIT, 'settings_shortcut', 106)
    def show_settings(self) -> None:
        """Show the settings window."""
        if self._settings_modal is None:
            self._settings_modal = SettingsModal(self._window)
            self.init_settings(self._settings_modal)
            self._settings_modal.changes_saved.connect(self.update_settings)
        self.refresh_settings(self._settings_modal)
        self._settings_modal.show_modal()

    # Image menu:

    @menu_action(MENU_IMAGE, 'resize_canvas_shortcut', 200, valid_app_states=[APP_STATE_EDITING])
    def resize_canvas(self) -> None:
        """Crop or extend the edited image without scaling its contents based on user input into a popup modal."""
        resize_modal = ResizeCanvasModal(self._image_stack.qimage())
        new_size, offset = resize_modal.show_resize_modal()
        if new_size is None or offset is None:
            return
        self._image_stack.resize_canvas(new_size, offset.x(), offset.y())

    @menu_action(MENU_IMAGE, 'scale_image_shortcut', 201, valid_app_states=[APP_STATE_EDITING])
    def scale_image(self) -> None:
        """Scale the edited image based on user input into a popup modal."""
        width = self._image_stack.width
        height = self._image_stack.height
        scale_modal = ImageScaleModal(width, height)
        new_size = scale_modal.show_image_modal()
        if new_size is not None:
            if self._generator is not None:
                if self._generator.upscale(new_size):
                    return
            self._scale(new_size)

    def _metadata_will_be_saved(self) -> bool:
        return self._metadata is not None and METADATA_PARAMETER_KEY in self._metadata

    @staticmethod
    def _updated_metadata_params() -> str:
        config = AppConfig()
        prompt = config.get(AppConfig.PROMPT)
        negative = config.get(AppConfig.NEGATIVE_PROMPT)
        steps = config.get(AppConfig.SAMPLING_STEPS)
        sampler = config.get(AppConfig.SAMPLING_METHOD)
        cfg_scale = config.get(AppConfig.GUIDANCE_SCALE)
        seed = config.get(AppConfig.SEED)
        size = config.get(AppConfig.GENERATION_SIZE)
        return f'{prompt}\nNegative prompt: {negative}\nSteps: {steps}, Sampler: {sampler}, CFG scale:' + \
               f'{cfg_scale}, Seed: {seed}, Size: {size.width()}x{size.height()}'

    def _metadata_is_latest(self) -> bool:
        if not self._metadata_will_be_saved():
            return False
        return self._metadata is not None and self._updated_metadata_params() == self._metadata[METADATA_PARAMETER_KEY]

    @menu_action(MENU_IMAGE, 'update_metadata_shortcut', 202,
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
        params = self._updated_metadata_params()
        if self._metadata is None:
            self._metadata = {}
        self._metadata[METADATA_PARAMETER_KEY] = params
        if self._exif is None:
            self._exif = Image.Exif()
        exif_tags = self._exif.get_ifd(IFD.Exif)
        exif_tags[ExifTags.Base.ImageDescription.value] = params
        if show_messagebox:
            message_box = QMessageBox()
            message_box.setWindowTitle(METADATA_UPDATE_TITLE)
            message_box.setText(METADATA_UPDATE_MESSAGE)
            message_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            message_box.exec()

    @menu_action(MENU_IMAGE, 'generate_shortcut', 203, valid_app_states=[APP_STATE_EDITING])
    def start_and_manage_inpainting(self) -> None:
        """Start inpainting/image editing based on the current state of the UI."""
        if AppStateTracker.app_state() != APP_STATE_EDITING:
            return
        if self._generator == self._null_generator:
            self.show_generator_window()
        else:
            self._generator.start_and_manage_image_generation()

    # Selection menu:
    @menu_action(MENU_SELECTION, 'select_all_shortcut', 300, valid_app_states=[APP_STATE_EDITING])
    def select_all(self) -> None:
        """Selects the entire image."""
        self._image_stack.selection_layer.select_all()

    @menu_action(MENU_SELECTION, 'select_none_shortcut', 301, valid_app_states=[APP_STATE_EDITING])
    def select_none(self) -> None:
        """Clears the selection."""
        self._image_stack.selection_layer.clear()

    @menu_action(MENU_SELECTION, 'invert_selection_shortcut', 302,
                 valid_app_states=[APP_STATE_EDITING])
    def invert_selection(self) -> None:
        """Swaps selected and unselected areas."""
        self._image_stack.selection_layer.invert_selection()

    @menu_action(MENU_SELECTION, 'select_layer_content_shortcut', 303,
                 valid_app_states=[APP_STATE_EDITING])
    def select_active_layer_content(self) -> None:
        """Selects all pixels in the active layer that are not fully transparent."""
        self._image_stack.select_active_layer_content()

    @menu_action(MENU_SELECTION, 'grow_selection_shortcut', 304, valid_app_states=[APP_STATE_EDITING])
    def grow_selection(self, num_pixels=1) -> None:
        """Expand the selection by a given pixel count, 1 by default."""
        self._image_stack.selection_layer.grow_or_shrink_selection(num_pixels)

    @menu_action(MENU_SELECTION, 'shrink_selection_shortcut', 305,
                 valid_app_states=[APP_STATE_EDITING])
    def shrink_selection(self, num_pixels=1) -> None:
        """Contract the selection by a given pixel count, 1 by default."""
        self._image_stack.selection_layer.grow_or_shrink_selection(-num_pixels)

    # Layer menu:

    @menu_action(f'{MENU_LAYERS}.{SUBMENU_SELECT}', 'select_previous_layer_shortcut', 400,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_SELECTION])
    def select_previous_layer(self) -> None:
        """Select the layer above the current active layer."""
        self._image_stack.offset_active_selection(-1)

    @menu_action(f'{MENU_LAYERS}.{SUBMENU_SELECT}', 'select_next_layer_shortcut', 401,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_SELECTION])
    def select_next_layer(self) -> None:
        """Select the layer below the current active layer."""
        self._image_stack.offset_active_selection(1)

    @menu_action(f'{MENU_LAYERS}.{SUBMENU_MOVE}', 'move_layer_up_shortcut', 410,
                 valid_app_states=[APP_STATE_EDITING])
    def move_layer_up(self) -> None:
        """Move the active layer up in the image."""
        self._image_stack.move_layer_by_offset(-1)

    @menu_action(f'{MENU_LAYERS}.{SUBMENU_MOVE}', 'move_layer_down_shortcut', 411,
                 valid_app_states=[APP_STATE_EDITING])
    def move_layer_down(self) -> None:
        """Move the active layer down in the image."""
        self._image_stack.move_layer_by_offset(1)

    @menu_action(f'{MENU_LAYERS}.{SUBMENU_MOVE}', 'move_layer_to_top_shortcut', 412,
                 valid_app_states=[APP_STATE_EDITING])
    def move_layer_to_top(self) -> None:
        """Move the active layer to the top of the layer stack."""
        self._image_stack.move_layer(self._image_stack.active_layer, self._image_stack.layer_stack, 0)

    def _get_active_transform_layer(self) -> TransformLayer:
        active_layer = self._image_stack.active_layer
        if isinstance(active_layer, TransformLayer):
            return active_layer
        assert isinstance(active_layer, LayerStack)
        return TransformGroup(active_layer)

    @menu_action(f'{MENU_LAYERS}.{SUBMENU_TRANSFORM}', 'layer_mirror_horizontal_shortcut', 430,
                 valid_app_states=[APP_STATE_EDITING])
    def layer_mirror_horizontal(self) -> None:
        """Flip the active layer horizontally."""
        layer = self._get_active_transform_layer()
        layer.flip_horizontal()

    @menu_action(f'{MENU_LAYERS}.{SUBMENU_TRANSFORM}', 'layer_mirror_vertical_shortcut', 431,
                 valid_app_states=[APP_STATE_EDITING])
    def layer_mirror_vertical(self) -> None:
        """Flip the active layer vertically."""
        layer = self._get_active_transform_layer()
        layer.flip_vertical()

    @menu_action(f'{MENU_LAYERS}.{SUBMENU_TRANSFORM}', 'layer_rotate_cw_shortcut', 432,
                 valid_app_states=[APP_STATE_EDITING])
    def layer_rotate_cw(self) -> None:
        """Rotate the active layer 90 degrees clockwise."""
        layer = self._get_active_transform_layer()
        layer.rotate(90)

    @menu_action(f'{MENU_LAYERS}.{SUBMENU_TRANSFORM}', 'layer_rotate_ccw_shortcut', 433,
                 valid_app_states=[APP_STATE_EDITING])
    def layer_rotate_ccw(self) -> None:
        """Rotate the active layer 90 degrees counter-clockwise."""
        layer = self._get_active_transform_layer()
        layer.rotate(-90)

    @menu_action(MENU_LAYERS, 'new_layer_shortcut', 440,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_SELECTION])
    def new_layer(self) -> None:
        """Create a new image layer above the active layer."""
        self._image_stack.create_layer()

    @menu_action(MENU_LAYERS, 'new_layer_group_shortcut', 441,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_SELECTION])
    def new_layer_group(self) -> None:
        """Create a new layer group above the active layer."""
        self._image_stack.create_layer_group()

    @menu_action(MENU_LAYERS, 'copy_layer_shortcut', 442,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_SELECTION])
    def copy_layer(self) -> None:
        """Create a copy of the active layer."""
        self._image_stack.copy_layer()

    @menu_action(MENU_LAYERS, 'delete_layer_shortcut', 443, valid_app_states=[APP_STATE_EDITING])
    def delete_layer(self) -> None:
        """Delete the active layer."""
        self._image_stack.remove_layer()

    @menu_action(MENU_LAYERS, 'merge_layer_down_shortcut', 444, valid_app_states=[APP_STATE_EDITING])
    def merge_layer_down(self) -> None:
        """Merge the active layer with the one beneath it."""
        self._image_stack.merge_layer_down()

    @menu_action(MENU_LAYERS, 'layer_to_image_size_shortcut', 445,
                 valid_app_states=[APP_STATE_EDITING])
    def layer_to_image_size(self) -> None:
        """Crop or expand the active layer to match the image size."""
        self._image_stack.layer_to_image_size()

    @menu_action(MENU_LAYERS, 'crop_to_content_shortcut', 446,
                 valid_app_states=[APP_STATE_EDITING])
    def crop_layer_to_content(self) -> None:
        """Crop the active layer to remove fully transparent border pixels."""
        layer = self._image_stack.active_layer
        assert isinstance(layer, (ImageLayer, LayerStack))
        layer.crop_to_content()

    # Tool menu:

    @menu_action(MENU_TOOLS, 'show_layer_menu_shortcut', 500)
    def show_layer_panel(self) -> None:
        """Opens the layer panel window"""
        if self._layer_panel is None:
            self._layer_panel = LayerPanel(self._image_stack)
        self._layer_panel.show()
        self._layer_panel.raise_()

    @menu_action(MENU_TOOLS, 'image_window_shortcut', 501)
    def show_image_window(self) -> None:
        """Show the image preview window."""
        self._window.show_image_window()

    @menu_action(MENU_TOOLS, 'generator_select_shortcut', 502)
    def show_generator_window(self) -> None:
        """Show the generator selection window."""
        if self._generator_window is None:
            self._generator_window = GeneratorSetupWindow()
            self._generator_window.add_generator(self._sd_generator)
            self._generator_window.add_generator(self._glid_generator)
            self._generator_window.add_generator(self._glid_web_generator)
            if '--dev' in sys.argv or self._generator == self._test_generator:
                self._generator_window.add_generator(self._test_generator)
            self._generator_window.add_generator(self._null_generator)
            self._generator_window.activate_signal.connect(self.load_image_generator)
        self._generator_window.mark_active_generator(self._generator)
        self._generator_window.show()
        self._generator_window.raise_()

    # Internal/protected:

    def _scale(self, new_size: QSize) -> None:  # Override to allow alternate or external upscalers:
        image = self._image_stack.qimage()
        if image.size() == new_size:
            return
        scaled_image = pil_image_scaling(image, new_size)
        self._image_stack.load_image(scaled_image)
