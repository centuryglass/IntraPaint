"""
AppController coordinates almost all IntraPaint application behavior.

Primary responsibilities:

Initialization:
- Initialize all Config classes.
- Initialize application image data and control structures (via ImageStack).
- Create the main application window, connecting signal handlers and applying cached and command line arguments.
- Create or load the initial image, depending on command line options.
- Build the main application menu structure, and configure when all menu options should be enabled.
- Load application themes, styles, and other display options.
- Create the ToolController and ToolPanel, connecting appropriate signals.
- Prepare all available ImageGenerator options, applying an appropriate one based on availability and command line
  arguments.

Image generator management:
- Manage the set of available image generators.
- Provides the GeneratorSetupWindow that allows the user to view and select generators.
- Update settings, control panels, and menu options when the active generator changes.
- Show or hide image generation tools depending on whether the active generator actually has image generation
  capabilities.

Application menu handling:
- Defines the list of standard menu options, configures when they should be visible and/or enabled, and provides
  the methods that handle those menu options.
- Dynamically creates menu options for all image filters.
- Provides access to various ImageStack and ImageGenerator functions

Image I/O:
- Controls when and how image file dialogs are shown.
- Shows appropriate errors or warnings whenever saving/loading fails or does not preserve all data.
- Caches and applies image metadata.
- Provides the connection between the ImageStack and image files.

User settings:
- Creates the settings modal, ensures that it contains appropriate entries from the assorted Config classes
- Applies changes to config whenever the settings modal closes.
"""
import json
import logging
import os
import re
import sys
import webbrowser
from argparse import Namespace
from typing import Optional, Any, Callable

from PIL import Image, UnidentifiedImageError, ExifTags
from PIL.ExifTags import IFD
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage, Qt, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.controller.image_generation.glid3_webservice_generator import Glid3WebserviceGenerator, DEFAULT_GLID_URL
from src.controller.image_generation.glid3_xl_generator import Glid3XLGenerator
from src.controller.image_generation.image_generator import ImageGenerator
from src.controller.image_generation.null_generator import NullGenerator
from src.controller.image_generation.sd_comfyui_generator import SDComfyUIGenerator, DEFAULT_COMFYUI_URL
from src.controller.image_generation.sd_generator import MENU_STABLE_DIFFUSION
from src.controller.image_generation.sd_webui_generator import SDWebUIGenerator, DEFAULT_WEBUI_URL
from src.controller.image_generation.test_generator import TestGenerator
from src.controller.tool_controller import ToolController
from src.hotkey_filter import HotkeyFilter
from src.image.filter.blur import BlurFilter
from src.image.filter.brightness_contrast import BrightnessContrastFilter
from src.image.filter.posterize import PosterizeFilter
from src.image.filter.rgb_color_balance import RGBColorBalanceFilter
from src.image.filter.sharpen import SharpenFilter
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.image_stack_utils import resize_image_stack_to_content, crop_image_stack_to_selection, \
    scale_all_layers, crop_layer_to_selection, crop_image_stack_to_gen_area
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.image.layers.text_layer import TextLayer
from src.image.layers.transform_group import TransformGroup
from src.image.layers.transform_layer import TransformLayer
from src.image.open_raster import save_ora_image, read_ora_image, ORA_FILE_EXTENSION
from src.tools.base_tool import BaseTool
from src.tools.generation_area_tool import GenerationAreaTool
from src.ui.input_fields.pressure_curve_input import PressureCurveInput
from src.ui.layout.draggable_tabs.tab import Tab
from src.ui.modal.image_scale_modal import ImageScaleModal
from src.ui.modal.modal_utils import show_error_dialog, request_confirmation, open_image_file, open_image_layers, \
    show_warning_dialog
from src.ui.modal.new_image_modal import NewImageModal
from src.ui.modal.resize_canvas_modal import ResizeCanvasModal
from src.ui.modal.settings_modal import SettingsModal
from src.ui.panel.color_panel import ColorControlPanel
from src.ui.panel.generators.generator_panel import GeneratorPanel
from src.ui.panel.layer_ui.layer_panel import LayerPanel
from src.ui.panel.tool_panel import ToolPanel
from src.ui.widget.tool_tab import ToolTab
from src.ui.window.generator_setup_window import GeneratorSetupWindow
from src.ui.window.main_window import MainWindow, TabBoxID
from src.ui.window.navigation_window import NavigationWindow
from src.undo_stack import UndoStack
from src.util.active_text_field_tracker import ActiveTextFieldTracker
from src.util.application_state import AppStateTracker, APP_STATE_NO_IMAGE, APP_STATE_EDITING, APP_STATE_LOADING, \
    APP_STATE_SELECTION
from src.util.math_utils import clamp
from src.util.menu_builder import MenuBuilder, menu_action, MENU_DATA_ATTR, MenuData
from src.util.optional_import import optional_import
from src.util.pyinstaller import is_pyinstaller_bundle
from src.util.qtexcepthook import QtExceptHook
from src.util.shared_constants import PROJECT_DIR, PIL_SCALING_MODES
from src.util.visual.display_size import get_screen_size
from src.util.visual.image_format_utils import save_image_with_metadata, save_image, load_image, \
    IMAGE_FORMATS_SUPPORTING_METADATA, IMAGE_FORMATS_SUPPORTING_ALPHA, IMAGE_FORMATS_SUPPORTING_PARTIAL_ALPHA, \
    METADATA_PARAMETER_KEY, IMAGE_WRITE_FORMATS, IMAGE_READ_FORMATS, IMAGE_FORMATS_WITH_FIXED_SIZE, \
    GREYSCALE_IMAGE_FORMATS, METADATA_COMMENT_KEY, PIL_WRITE_FORMATS, QIMAGE_WRITE_FORMATS
from src.util.visual.image_utils import image_is_fully_opaque, image_has_partial_alpha, create_transparent_image

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


TOOL_PANEL_LAYER_TAB = _tr('Layers')
TOOL_PANEL_COLOR_TAB = _tr('Color')
TOOL_PANEL_NAV_TAB = _tr('Navigation')

GENERATION_MODE_SD_WEBUI = 'stable-diffusion-webui'
GENERATION_MODE_COMFYUI = 'comfyui'
GENERATION_MODE_LOCAL_GLID = 'glid-local'
GENERATION_MODE_WEB_GLID = 'glid-api'
GENERATION_MODE_NONE = 'none'
GENERATION_MODE_TEST = 'mock'
GENERATION_MODE_AUTO = 'auto'

MENU_FILE = _tr('File')
MENU_EDIT = _tr('Edit')
MENU_IMAGE = _tr('Image')
MENU_SELECTION = _tr('Selection')
MENU_LAYERS = _tr('Layers')
MENU_FILTERS = _tr('Filters')
MENU_HELP = _tr('Help')

SUBMENU_MOVE = _tr('Move')
SUBMENU_SELECT = _tr('Select')
SUBMENU_TRANSFORM = _tr('Transform')

CONTROL_TAB_NAME = _tr('Image Generation')

ICON_PATH_GEN_TAB = f'{PROJECT_DIR}/resources/icons/tabs/sparkle.svg'
ICON_PATH_LAYER_TAB = f'{PROJECT_DIR}/resources/icons/tabs/layers.svg'
ICON_PATH_NAVIGATION_TAB = f'{PROJECT_DIR}/resources/icons/tabs/navigation.svg'
ICON_PATH_COLOR_TAB = f'{PROJECT_DIR}/resources/icons/tabs/colors.svg'
HELP_INDEX_LINK = 'https://github.com/centuryglass/IntraPaint/blob/master/doc/help_index.md'

GENERATOR_LOAD_ERROR_TITLE = _tr('Loading image generator failed')
GENERATOR_LOAD_ERROR_MESSAGE = _tr('Unable to load the {generator_name} image generator')
CONFIRM_QUIT_TITLE = _tr('Quit now?')
CONFIRM_QUIT_MESSAGE = _tr('All unsaved changes will be lost.')
NEW_IMAGE_CONFIRMATION_TITLE = _tr('Create new image?')
NEW_IMAGE_CONFIRMATION_MESSAGE = _tr('This will discard all unsaved changes.')
SAVE_ERROR_TITLE = _tr('Save failed')
LOAD_ERROR_TITLE = _tr('Open failed')
SAVE_ERROR_MESSAGE_UNKNOWN_ISSUE = _tr('Saving as "{file_path}" failed due to an unknown error, please open a new issue'
                                       ' on the IntraPaint GitHub page, and let me know what file format you tried '
                                       'and any other details that might be relevant. Meanwhile, try saving in a'
                                       ' different format or to a different disk.')
SAVE_ERROR_MESSAGE_INVALID_EXTENSION = _tr('Saving files with the  "{extension}" extension is not supported, try again'
                                           ' with a supported image file format.')
SAVE_ERROR_MESSAGE_NO_EXTENSION = _tr('Tried to save with no file extension as "{file_path}", add a valid image file'
                                      ' extension and try again.')
RELOAD_ERROR_TITLE = _tr('Reload failed')
RELOAD_ERROR_MESSAGE_INVALID_FILE = _tr('Image path "{file_path}" is not a valid image file.')
RELOAD_ERROR_MESSAGE_NO_IMAGE = _tr('Enter an image path or click "Open Image" first.')
RELOAD_CONFIRMATION_TITLE = _tr('Reload image?')
RELOAD_CONFIRMATION_MESSAGE = _tr('This will discard all unsaved changes.')
METADATA_UPDATE_TITLE = _tr('Metadata updated')
METADATA_UPDATE_MESSAGE = _tr('On save, current image generation parameters will be stored within the image')
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

IGNORED_APPCONFIG_CATEGORIES = (QApplication.translate('application_config', 'Stable Diffusion'),
                                QApplication.translate('application_config', 'GLID-3-XL'))
DEV_APPCONFIG_CATEGORY = QApplication.translate('application_config', 'Developer')


def _get_config_categories() -> list[str]:
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
        cache = Cache()
        cache.apply_args(args)
        self._layer_panel: Optional[LayerPanel] = None
        self._generator_window: Optional[GeneratorSetupWindow] = None

        # Initialize edited image data structures:
        self._image_stack = ImageStack(config.get(AppConfig.DEFAULT_IMAGE_SIZE), cache.get(Cache.EDIT_SIZE),
                                       config.get(AppConfig.MIN_EDIT_SIZE), config.get(AppConfig.MAX_EDIT_SIZE))

        self._metadata: Optional[dict[str, Any]] = None
        self._exif: Optional[Image.Exif] = None

        # Initialize main window:
        self._window = MainWindow(self._image_stack)
        self.menu_window = self._window
        self._image_viewer = self._window.image_panel.image_viewer
        self._window.generate_signal.connect(self.start_and_manage_inpainting)
        if args.window_size is not None:
            width, height = (int(dim) for dim in args.window_size.split('x'))
            self._window.setGeometry(0, 0, width, height)
            self._window.setMaximumSize(width, height)
            self._window.setMinimumSize(width, height)
        else:
            if not Cache().load_bounds(Cache.SAVED_MAIN_WINDOW_POS, self._window):
                size = get_screen_size(self._window)
                x = 0
                y = 0
                width = size.width()
                height = size.height()
                self._window.setGeometry(x, y, width, height)
        if args.init_image is not None:
            self.load_image(file_path=args.init_image)
        if not self._image_stack.has_image:
            image = QImage(config.get(AppConfig.DEFAULT_IMAGE_SIZE), QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Cache().get_color(Cache.NEW_IMAGE_BACKGROUND_COLOR, Qt.GlobalColor.white))
            self._image_stack.load_image(image)

        # Set up menus in the expected order, so menus don't need to be shown in the order they're initialized:
        ordered_menus = [
            MENU_FILE,
            MENU_EDIT,
            MENU_IMAGE,
            MENU_SELECTION,
            MENU_LAYERS,
            MENU_FILTERS,
            MENU_STABLE_DIFFUSION,
            MENU_HELP
        ]
        for menu_name in ordered_menus:
            self.add_menu(menu_name)

        self._generator: Optional[ImageGenerator] = None

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

        # Since image filter menus follow a very simple pattern, add them here instead of using @menu_action.
        # At the same time, make sure the filter tool's list of available options contains all filters.
        filter_class_names: list[str] = []
        for filter_class in (RGBColorBalanceFilter,
                             BrightnessContrastFilter,
                             BlurFilter,
                             SharpenFilter,
                             PosterizeFilter):
            image_filter = filter_class(self._image_stack)
            filter_class_names.append(image_filter.get_name())

            def _open_filter_modal(filter_instance=image_filter) -> None:
                modal = filter_instance.get_filter_modal()
                self._set_alt_window_centered_bounds(modal)
                modal.exec()

            config_key = image_filter.get_config_key()
            action = self.add_menu_action(MENU_FILTERS,
                                          _open_filter_modal,
                                          config_key)
            assert action is not None
            AppStateTracker.set_enabled_states(action, [APP_STATE_EDITING])
        cache.update_options(Cache.FILTER_TOOL_SELECTED_FILTER, filter_class_names)  # type: ignore

        # Because Qt has its own bindings on the cut/copy/clear/paste keyboard events, we need to bind these at the
        # hotkeyFilter to ensure that the menu hotkeys can override the Qt bindings. The goal is to ensure that even
        # when a text field is active, these events will get handled in the context of the ImageStack if they wouldn't
        # do anything to the text.
        for binding_key, handler in ((KeyConfig.UNDO_SHORTCUT, self.undo),
                                     (KeyConfig.REDO_SHORTCUT, self.redo),
                                     (KeyConfig.CUT_SHORTCUT, self.cut),
                                     (KeyConfig.COPY_SHORTCUT, self.copy),
                                     (KeyConfig.PASTE_SHORTCUT, self.paste),
                                     (KeyConfig.CLEAR_SHORTCUT, self.clear)):
            HotkeyFilter.instance().register_config_keybinding(f'AppController_{binding_key}', handler,
                                                               binding_key)
        # We'll also want flags for tracking whether cut/copy/paste/clear are currently valid for image content, so
        # that we don't need to recalculate that every time they become invalid for an active text field:
        self._can_copy_image = False
        self._can_paste_image = False
        self._can_clear_or_cut_image = False

        # Finally, track active text inputs, so we always know when text-relevant events should be available:
        self._active_text_field_tracker = ActiveTextFieldTracker()
        self._active_text_field_tracker.status_changed.connect(self._update_enabled_text_relevant_actions)

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
        self._image_stack.selection_layer.content_changed.connect(
            lambda _layer, _bounds: self._update_enabled_actions())
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

        # ToolPanel/ToolController: Set up editing tools:
        self._tool_controller = ToolController(self._image_stack, self._image_viewer)
        self._tool_panel = ToolPanel()
        self._generation_area_tool = GenerationAreaTool(self._image_stack, self._image_viewer)
        self._last_active_tool: Optional[BaseTool] = None

        # Add utility widgets to the tool panel:
        self._tool_panel_navigation_panel = NavigationWindow(self._image_stack, self._image_viewer,
                                                             include_zoom_controls=False, use_keybindings=False)
        self._tool_panel.add_utility_widget_tab(LayerPanel(self._image_stack), TOOL_PANEL_LAYER_TAB,
                                                QIcon(ICON_PATH_LAYER_TAB))
        self._tool_panel_color_picker = ColorControlPanel(disable_extended_layouts=True)
        self._tool_panel_color_picker.set_four_tab_mode()
        self._tool_panel.add_utility_widget_tab(self._tool_panel_color_picker, TOOL_PANEL_COLOR_TAB,
                                                QIcon(ICON_PATH_COLOR_TAB))
        self._tool_panel.add_utility_widget_tab(self._tool_panel_navigation_panel, TOOL_PANEL_NAV_TAB,
                                                QIcon(ICON_PATH_NAVIGATION_TAB))

        # Add all tools to the panel except for the generation area tool:
        for tool in self._tool_controller.tools:
            self._tool_panel.add_tool_button(tool)

        # Connect signal handlers:
        self._tool_panel.tool_selected.connect(self._tool_controller.set_active_tool)
        self._tool_controller.active_tool_changed.connect(self._tool_panel.setup_active_tool)
        self._tool_controller.tool_added.connect(self._tool_panel.add_tool_button)
        self._tool_controller.tool_removed.connect(self._tool_panel.remove_tool_button)

        def _update_image_cursor() -> None:
            updated_active_tool = self._tool_controller.active_tool
            if updated_active_tool is not None:
                self._image_viewer.set_cursor(updated_active_tool.cursor)

        def _update_cursor_and_control_hint(new_active_tool: BaseTool) -> None:
            self._window.image_panel.set_control_hint(new_active_tool.get_input_hint())
            if self._last_active_tool is not None:
                self._last_active_tool.cursor_change.disconnect(_update_image_cursor)
            new_active_tool.cursor_change.connect(_update_image_cursor)
            self._last_active_tool = new_active_tool
            _update_image_cursor()

        self._tool_controller.active_tool_changed.connect(_update_cursor_and_control_hint)
        active_tool = self._tool_controller.active_tool
        assert active_tool is not None
        _update_cursor_and_control_hint(active_tool)
        self._tool_panel.setup_active_tool(active_tool)

        # Set up main window tabs:
        self._tool_tab = ToolTab(self._tool_panel, self._tool_controller, parent=self._window)
        try:
            tool_tab_box_id = TabBoxID(Cache().get(Cache.TOOL_TAB_BAR))
        except ValueError:
            tool_tab_box_id = None  # Invalid cache entry, use default placement
        self._window.add_tab(self._tool_tab, tool_tab_box_id)

        self._generator_control_panel: Optional[GeneratorPanel] = None
        self._generator_tab = Tab(CONTROL_TAB_NAME, None, KeyConfig.SELECT_GENERATOR_TAB, parent=self._window)
        self._generator_tab.hide()
        self._generator_tab.setIcon(QIcon(ICON_PATH_GEN_TAB))

        # Prepare image generator options, and select one based on availability and command line arguments.
        self._null_generator = NullGenerator(self._window, self._image_stack)
        self._sd_webui_generator = SDWebUIGenerator(self._window, self._image_stack, args)
        self._sd_comfyui_generator = SDComfyUIGenerator(self._window, self._image_stack, args)
        if not is_pyinstaller_bundle():
            self._glid_generator = Glid3XLGenerator(self._window, self._image_stack, args)
        self._glid_web_generator = Glid3WebserviceGenerator(self._window, self._image_stack, args)
        self._test_generator = TestGenerator(self._window, self._image_stack)

        mode = args.mode
        match mode:
            case _ if mode == GENERATION_MODE_NONE:
                self.load_image_generator(self._null_generator)
            case _ if mode == GENERATION_MODE_SD_WEBUI:
                self.load_image_generator(self._sd_webui_generator)
            case _ if mode == GENERATION_MODE_COMFYUI:
                self.load_image_generator(self._sd_comfyui_generator)
            case _ if mode == GENERATION_MODE_WEB_GLID and not is_pyinstaller_bundle():
                self.load_image_generator(self._glid_web_generator)
            case _ if mode == GENERATION_MODE_LOCAL_GLID and not is_pyinstaller_bundle():
                self.load_image_generator(self._glid_generator)
            case _ if mode == GENERATION_MODE_TEST:
                self.load_image_generator(self._test_generator)
            case _:
                if mode != GENERATION_MODE_AUTO:
                    logger.error(f'Unexpected mode {mode}, defaulting to mode=auto')
                server_url = args.server_url
                if server_url == DEFAULT_WEBUI_URL:
                    self.load_image_generator(self._sd_webui_generator)
                elif server_url == DEFAULT_COMFYUI_URL:
                    self.load_image_generator(self._sd_comfyui_generator)
                elif server_url == DEFAULT_GLID_URL:
                    self.load_image_generator(self._glid_web_generator)
                if self._sd_webui_generator.is_available():
                    self.load_image_generator(self._sd_webui_generator)
                elif self._sd_comfyui_generator.is_available():
                    self.load_image_generator(self._sd_comfyui_generator)
                elif self._glid_web_generator.is_available():
                    self.load_image_generator(self._glid_generator)
                elif args.dev:
                    self.load_image_generator(self._test_generator)
                elif not is_pyinstaller_bundle() and self._glid_generator.is_available():
                    self.load_image_generator(self._glid_generator)
                else:
                    logger.info('No valid generator detected, starting with null generator enabled.')
                    self.load_image_generator(self._null_generator)

        # Restore previous active tool, save future active tool changes
        last_active_tool_name = cache.get(Cache.LAST_ACTIVE_TOOL)
        last_active_tool = self._tool_controller.find_tool_by_label(last_active_tool_name)
        if last_active_tool is not None:
            self._tool_controller.active_tool = last_active_tool

        def _update_last_active_tool(new_active_tool: BaseTool) -> None:
            tool_value = '' if not isinstance(new_active_tool, BaseTool) else new_active_tool.label
            cache.set(Cache.LAST_ACTIVE_TOOL, tool_value)

        self._tool_controller.active_tool_changed.connect(_update_last_active_tool)

    def start_app(self) -> None:
        """Start the application."""
        app = QApplication.instance() or QApplication(sys.argv)
        if AppConfig().get(AppConfig.USE_ERROR_HANDLER):
            QtExceptHook().enable()
        self._window.show()
        self._update_enabled_actions()

        # Discard anything saved to the undo stack during the setup process:
        UndoStack().clear()

        AppStateTracker.set_app_state(APP_STATE_EDITING if self._image_stack.has_image else APP_STATE_NO_IMAGE)
        app.exec()

    def load_image_generator(self, generator: ImageGenerator) -> None:
        """Load an image generator, updating controls and settings."""
        # if not generator.is_available():
        #     show_error_dialog(self._window, GENERATOR_LOAD_ERROR_TITLE,
        #                       GENERATOR_LOAD_ERROR_MESSAGE.format(generator_name=generator.get_display_name()))
        #     return
        # unload last generator:
        last_generator = self._null_generator if self._generator is None else self._generator
        if self._generator is not None:
            for tab in self._generator.get_extra_tabs():
                self._window.remove_tab(tab)
            if self._generator_control_panel is not None:
                for tab_bar_widget in self._generator_control_panel.get_tab_bar_widgets():
                    self._generator_tab.remove_tab_bar_widget(tab_bar_widget)
            self._generator.unload_settings(self._settings_modal)
            self._generator.clear_menus()
            self._generator.disconnect_or_disable()

        # load new generator:
        if not generator.configure_or_connect():
            show_error_dialog(self._window, GENERATOR_LOAD_ERROR_TITLE,
                              GENERATOR_LOAD_ERROR_MESSAGE.format(generator_name=generator.get_display_name()))
            assert generator != self._null_generator
            self.load_image_generator(self._null_generator if last_generator == generator else last_generator)
            return
        self._generator = generator
        self._generator.menu_window = self._window
        self._generator.init_settings(self._settings_modal)
        self._generator.build_menus()

        prev_panel_was_none = self._generator_control_panel is None
        self._generator_control_panel = self._generator.get_control_panel()
        self._generator_tab.content_widget = self._generator_control_panel
        if self._generator_control_panel is not None:
            for tab_bar_widget in self._generator_control_panel.get_tab_bar_widgets():
                self._generator_tab.add_tab_bar_widget(tab_bar_widget)
        if self._generator_control_panel is None and not prev_panel_was_none:
            self._window.remove_tab(self._generator_tab)
        elif prev_panel_was_none and self._generator_control_panel is not None:
            try:
                generation_tab_box_id = TabBoxID(Cache().get(Cache.GENERATION_TAB_BAR))
            except ValueError:
                generation_tab_box_id = None
            self._window.add_tab(self._generator_tab, generation_tab_box_id)
            self._generator_tab.show()
        for tab in self._generator.get_extra_tabs():
            # Remember to adjust this if you add any other generator-specific tabs
            try:
                box_id: Optional[TabBoxID] = TabBoxID(Cache().get(Cache.CONTROLNET_TAB_BAR))
            except ValueError:
                box_id = None
            self._window.add_tab(tab, box_id)
            tab.show()
        if self._generator_window is not None:
            self._generator_window.mark_active_generator(generator)

        # Generation area tool management:
        gen_area_tool = self._tool_controller.find_tool_by_class(GenerationAreaTool)

        # Remove gen area tool if null generator was activated, add it if a non-null generator was activated:
        show_image_gen_controls = generator != self._null_generator
        if gen_area_tool is not None and not show_image_gen_controls:
            self._tool_controller.remove_tool(gen_area_tool)
        elif gen_area_tool is None and show_image_gen_controls:
            self._tool_controller.add_tool(self._generation_area_tool)
        image_panels = (self._window.image_panel, self._tool_panel_navigation_panel, self._window.navigation_window)
        for image_panel in image_panels:
            image_panel.set_image_generation_controls_visible(show_image_gen_controls)
        generate_action = self.get_action_for_method(self.start_and_manage_inpainting)
        generate_action.setEnabled(self._generator is not None and not isinstance(self._generator, NullGenerator))
        self._update_enabled_actions()

    def init_settings(self, settings_modal: SettingsModal) -> None:
        """Load application settings into a SettingsModal"""
        categories = _get_config_categories()
        app_config = AppConfig()
        settings_modal.load_from_config(app_config, categories)
        settings_modal.load_from_config(KeyConfig())
        if self._generator is not None:
            self._generator.init_settings(settings_modal)
        # Add custom setting controls:
        pressure_curve_input = PressureCurveInput()
        curve_values = app_config.get(AppConfig.TABLET_PRESSURE_CURVE)
        try:
            pressure_curve_input.setValue(curve_values)
        except ValueError:
            app_config.set(AppConfig.TABLET_PRESSURE_CURVE, pressure_curve_input.value())
        settings_modal.add_custom_control(pressure_curve_input, app_config, AppConfig.TABLET_PRESSURE_CURVE)

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

        def _test_state(menu_action_method: Callable[..., None]) -> bool:
            app_state = AppStateTracker.app_state()
            assert callable(menu_action_method) and hasattr(menu_action_method, MENU_DATA_ATTR)
            data = getattr(menu_action_method, MENU_DATA_ATTR, None)
            assert isinstance(data, MenuData)
            if data.valid_app_states is None:
                return True
            return app_state in data.valid_app_states

        selection_is_empty = self._image_stack.selection_layer.empty
        selection_methods: set[Callable[..., None]] = {
            self.grow_selection,
            self.shrink_selection,
            self.crop_image_to_selection,
            self.crop_layer_to_selection
        }
        unlocked_layer_methods: set[Callable[..., None]] = {
            self.layer_mirror_horizontal,
            self.layer_mirror_vertical,
            self.layer_rotate_cw,
            self.layer_rotate_ccw,
            self.delete_layer,
            self.merge_layer_down,
            self.flatten_layer,
            self.layer_to_image_size,
            self.crop_layer_to_content,
            self.crop_layer_to_selection

        }
        not_bottom_layer_methods: set[Callable[..., None]] = {
            self.select_next_layer,
            self.move_layer_down,
            self.merge_layer_down
        }
        not_top_layer_methods: set[Callable[..., None]] = {
            self.select_previous_layer,
            self.move_layer_up,
            self.move_layer_to_top
        }
        not_layer_stack_methods: set[Callable[..., None]] = {
            self.select_previous_layer,
            self.move_layer_up,
            self.move_layer_down,
            self.move_layer_to_top,
            self.flatten_layer,
            self.copy_layer,
            self.delete_layer
        }
        not_flat_methods: set[Callable[..., None]] = {self.flatten_layer}
        not_layer_group_methods: set[Callable[..., None]] = {
            self.merge_layer_down,
            self.layer_to_image_size
        }

        not_text_layer_methods: set[Callable[..., None]] = {self.crop_layer_to_content}

        managed_menu_methods = selection_methods | unlocked_layer_methods | not_bottom_layer_methods \
                               | not_top_layer_methods | not_layer_stack_methods | not_layer_group_methods

        active_layer = self._image_stack.active_layer
        is_top_layer = active_layer == self._image_stack.layer_stack or self._image_stack.prev_layer(active_layer) \
                       in (None, self._image_stack.layer_stack)
        is_bottom_layer = active_layer != self._image_stack.layer_stack \
                          and self._image_stack.next_layer(active_layer) is None
        is_locked = active_layer.locked or active_layer.parent_locked
        for menu_method in managed_menu_methods:
            action = self.get_action_for_method(menu_method)
            assert action is not None
            if not _test_state(menu_method):
                action.setEnabled(False)
                continue
            action.setEnabled(True)
            for method_set, disable_condition in ((selection_methods, selection_is_empty),
                                                  (unlocked_layer_methods, is_locked),
                                                  (not_bottom_layer_methods, is_bottom_layer),
                                                  (not_top_layer_methods, is_top_layer),
                                                  (not_layer_stack_methods,
                                                   active_layer == self._image_stack.layer_stack),
                                                  (not_flat_methods, self._image_stack.layer_is_flat(active_layer)),
                                                  (not_layer_group_methods, isinstance(active_layer, LayerGroup)),
                                                  (not_text_layer_methods, isinstance(active_layer, TextLayer))):
                if menu_method in method_set and disable_condition:
                    action.setEnabled(False)
                    break

        # Hide everything related to generation area if no generator is in use:
        crop_to_gen_action = self.get_action_for_method(self.crop_image_to_gen_area)
        crop_to_gen_action.setVisible(self._generator != self._null_generator)

        # "Merge down" should also check the next layer:
        merge_down_action = self.get_action_for_method(self.merge_layer_down)
        if merge_down_action.isEnabled():
            next_layer = self._image_stack.next_layer(active_layer)
            if next_layer is None or next_layer.locked or next_layer.parent_locked or not next_layer.visible \
                    or not isinstance(next_layer, TransformLayer) \
                    or next_layer.layer_parent != active_layer.layer_parent:
                merge_down_action.setEnabled(False)

        self._can_clear_or_cut_image = not is_locked and not selection_is_empty
        self._can_copy_image = not selection_is_empty
        self._update_enabled_text_relevant_actions()

    def _update_enabled_text_relevant_actions(self) -> None:
        """Update menu action enablement state that varies when a text input is active."""
        for method, valid_for_image, valid_for_text in (
                (self.undo, UndoStack().undo_count() > 0, self._active_text_field_tracker.focused_can_undo()),
                (self.redo, UndoStack().redo_count() > 0, self._active_text_field_tracker.focused_can_redo()),
                (self.copy, self._can_copy_image, self._active_text_field_tracker.focused_can_copy()),
                (self.paste, self._can_paste_image, self._active_text_field_tracker.focused_can_paste()),
                (self.cut, self._can_clear_or_cut_image, self._active_text_field_tracker.focused_can_cut_or_clear()),
                (self.clear, self._can_clear_or_cut_image, self._active_text_field_tracker.focused_can_cut_or_clear())):
            self.get_action_for_method(method).setEnabled(valid_for_image or valid_for_text)

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
            new_image = QImage(image_size, QImage.Format.Format_ARGB32_Premultiplied)
            new_image.fill(Cache().get_color(Cache.NEW_IMAGE_BACKGROUND_COLOR, Qt.GlobalColor.white))
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
        error_handled = False
        try:
            if not isinstance(file_path, str):
                self._window.setUpdatesEnabled(False)
                selected_path = open_image_file(self._window, mode='save',
                                                selected_file=cache.get(Cache.LAST_FILE_PATH))
                self._window.setUpdatesEnabled(True)
                self._window.update()
                self._window.repaint()
                if not isinstance(selected_path, str):
                    return
                file_path = selected_path
            assert isinstance(file_path, str)
            delimiter_index = file_path.rfind('.')
            if delimiter_index < 0:
                raise ValueError(SAVE_ERROR_MESSAGE_NO_EXTENSION.format(file_path=file_path))
            file_format = file_path[delimiter_index + 1:].upper()
            if (file_format not in QIMAGE_WRITE_FORMATS and file_format not in PIL_WRITE_FORMATS
                    and file_format != 'ORA'):
                raise ValueError(SAVE_ERROR_MESSAGE_INVALID_EXTENSION.format(extension=file_format))

            # Check if metadata is out of date, ask if it should update:
            if file_format in IMAGE_FORMATS_SUPPORTING_METADATA and self._generator is not None \
                    and not isinstance(self._generator, NullGenerator):
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

            if file_path.lower().endswith(ORA_FILE_EXTENSION):

                class _Encoder(json.JSONEncoder):

                    def default(self, o):
                        """Convert byte strings to ASCII when serializing."""
                        if isinstance(o, bytes):
                            return o.decode()
                        return super().default(o)

                save_ora_image(self._image_stack, file_path, json.dumps(self._metadata, cls=_Encoder))
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

                def _extension_str(extensions: tuple[str, ...]) -> str:
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
            if not os.path.isfile(file_path):
                raise RuntimeError(SAVE_ERROR_MESSAGE_UNKNOWN_ISSUE.format(file_path=file_path))
            cache.set(Cache.LAST_FILE_PATH, file_path)
        except (IOError, TypeError, ValueError, RuntimeError) as save_err:
            error_handled = True
            logger.error(f'save failed: {save_err}')
            show_error_dialog(self._window, SAVE_ERROR_TITLE, str(save_err))
        finally:
            if isinstance(file_path, str) and not os.path.isfile(file_path) and not error_handled:
                show_error_dialog(self._window, SAVE_ERROR_TITLE,
                                  SAVE_ERROR_MESSAGE_UNKNOWN_ISSUE.format(file_path=file_path))
            self._window.setUpdatesEnabled(True)
            self._window.update()
            self._window.repaint()

    @menu_action(MENU_FILE, 'load_shortcut', 3,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_NO_IMAGE])
    def load_image(self, file_path: Optional[str | list[str]] = None) -> None:
        """Open a loading dialog, then load the selected image for editing."""
        cache = Cache()
        if file_path is None:
            self._window.setUpdatesEnabled(False)
            selected_path = open_image_file(self._window)
            self._window.setUpdatesEnabled(True)
            self._window.update()
            self._window.repaint()
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
                self._image_stack.load_image(image)
            cache.set(Cache.LAST_FILE_PATH, file_path)

            # File loaded, attempt to apply metadata:
            if self._metadata is not None and METADATA_PARAMETER_KEY in self._metadata:
                param_str = self._metadata[METADATA_PARAMETER_KEY]
                if param_str is not None and not isinstance(param_str, str):
                    # noinspection PyTypeChecker
                    param_str = str(param_str, encoding='utf-8')
                match = re.match(r'^((?:.|\n)*)\nSteps: ?(\d+), Sampler: ?(.*), CFG scale: ?(.*), Seed: ?(.+),'
                                 r' Size: ?(\d+)x?(\d+)', param_str)
                if match:
                    prompt = match.group(1)
                    negative = ''
                    steps = int(match.group(2))
                    sampler = match.group(3)
                    cfg_scale = float(match.group(4))
                    seed = int(match.group(5))
                    divider_match = re.match('^((?:.|\n)*)\nNegative prompt: ?(.*)$', prompt)
                    if divider_match:
                        prompt = divider_match.group(1)
                        negative = divider_match.group(2)
                    logger.info('Detected saved image gen data, applying to UI')
                    try:
                        cache.set(Cache.PROMPT, prompt)
                        cache.set(Cache.NEGATIVE_PROMPT, negative)
                        cache.set(Cache.SAMPLING_STEPS, steps)
                        try:
                            cache.set(Cache.SAMPLING_METHOD, sampler)
                        except ValueError:
                            logger.error(f'sampler "{sampler}" used to generate this image is not supported.')
                        cache.set(Cache.GUIDANCE_SCALE, cfg_scale)
                        cache.set(Cache.SEED, seed)
                    except (TypeError, RuntimeError) as err:
                        logger.error(f'Failed to load image gen data from metadata: {err}')
                else:
                    logger.warning('image parameters do not match expected patterns, cannot be used. '
                                   f'parameters:{param_str}')
            AppStateTracker.set_app_state(APP_STATE_EDITING)
        except (UnidentifiedImageError, OSError) as err:
            show_error_dialog(self._window, LOAD_ERROR_TITLE, err)
            return
        finally:
            self._window.setUpdatesEnabled(True)
            self._window.update()
            self._window.repaint()

    @menu_action(MENU_FILE, 'load_layers_shortcut', 4,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_NO_IMAGE])
    def load_image_layers(self) -> None:
        """Open one or more images as layers."""
        layer_paths, layers_selected = open_image_layers(self._window)
        if not layers_selected or not layer_paths or len(layer_paths) == 0:
            return
        layers: list[tuple[QImage, str]] = []
        errors: list[str] = []
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
    def quit(self, skip_confirmation: bool = False) -> None:
        """Quit the application after getting confirmation from the user."""
        if skip_confirmation or request_confirmation(self._window, CONFIRM_QUIT_TITLE, CONFIRM_QUIT_MESSAGE):
            self._window.close()

    # Edit menu:

    @menu_action(MENU_EDIT, 'undo_shortcut', 100,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_NO_IMAGE])
    def undo(self) -> None:
        """Revert the most recent significant change made."""
        if self._active_text_field_tracker.focused_can_undo():
            text_field = self._active_text_field_tracker.focused_text_input
            assert text_field is not None
            text_field.undo()
        else:
            UndoStack().undo()

    @menu_action(MENU_EDIT, 'redo_shortcut', 101,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_NO_IMAGE])
    def redo(self) -> None:
        """Restore the most recent reverted change."""
        if self._active_text_field_tracker.focused_can_redo():
            text_field = self._active_text_field_tracker.focused_text_input
            assert text_field is not None
            text_field.redo()
        else:
            UndoStack().redo()

    @menu_action(MENU_EDIT, 'cut_shortcut', 102, valid_app_states=[APP_STATE_EDITING])
    def cut(self) -> None:
        """Cut selected content from the active image layer, or selected text in an active text field."""
        if self._active_text_field_tracker.focused_can_cut_or_clear():
            text_field = self._active_text_field_tracker.focused_text_input
            assert text_field is not None
            text_field.cut()
        else:
            self._image_stack.cut_selected()
            if not self._can_paste_image:
                self._can_paste_image = True
                self._update_enabled_actions()

    @menu_action(MENU_EDIT, 'copy_shortcut', 103, valid_app_states=[APP_STATE_EDITING])
    def copy(self) -> None:
        """Copy selected content from the active image layer, or selected text in an active text field."""
        if self._active_text_field_tracker.focused_can_copy():
            text_field = self._active_text_field_tracker.focused_text_input
            assert text_field is not None
            text_field.copy()
        else:
            self._image_stack.copy_selected()
            if not self._can_paste_image:
                self._can_paste_image = True
                self._update_enabled_actions()

    @menu_action(MENU_EDIT, 'paste_shortcut', 104, valid_app_states=[APP_STATE_EDITING])
    def paste(self) -> None:
        """Paste copied image content into a new layer, or copied text in an active text field."""
        if self._active_text_field_tracker.focused_can_paste():
            text_field = self._active_text_field_tracker.focused_text_input
            assert text_field is not None
            text_field.paste()
        else:
            self._image_stack.paste()

    @menu_action(MENU_EDIT, 'clear_shortcut', 105, valid_app_states=[APP_STATE_EDITING])
    def clear(self) -> None:
        """Clear selected content from the active image layer, or selected text in an active text field."""
        if self._active_text_field_tracker.focused_can_cut_or_clear():
            self._active_text_field_tracker.clear_selected_in_focused()
        else:
            self._image_stack.clear_selected()

    @menu_action(MENU_EDIT, 'settings_shortcut', 106)
    def show_settings(self) -> None:
        """Show the settings window."""
        if self._settings_modal is None:
            self._settings_modal = SettingsModal(self._window)
            self.init_settings(self._settings_modal)
            self._settings_modal.changes_saved.connect(self.update_settings)
        self.refresh_settings(self._settings_modal)
        self._set_alt_window_fractional_bounds(self._settings_modal)
        self._settings_modal.show_modal()

    # Image menu:

    @menu_action(MENU_IMAGE, 'navigation_window_shortcut', 199)
    def show_navigation_window(self) -> None:
        """Show the image preview window."""
        self._window.show_navigation_window()

    @menu_action(MENU_IMAGE, 'resize_canvas_shortcut', 200, valid_app_states=[APP_STATE_EDITING])
    def resize_canvas(self) -> None:
        """Crop or extend the edited image without scaling its contents based on user input into a popup modal."""
        resize_modal = ResizeCanvasModal(self._image_stack)
        self._set_alt_window_centered_bounds(resize_modal)
        new_size, offset = resize_modal.show_resize_modal()
        if new_size is None or offset is None:
            return
        self._image_stack.resize_canvas(new_size, offset.x(), offset.y())

    @menu_action(MENU_IMAGE, 'scale_image_shortcut', 201, valid_app_states=[APP_STATE_EDITING])
    def scale_image(self) -> None:
        """Scale the edited image based on user input into a popup modal."""
        width = self._image_stack.width
        height = self._image_stack.height
        # TODO: more consideration re. scaling with multiple layers
        is_multi_layer = False  # (len(self._image_stack.image_layers) + len(self._image_stack.text_layers)) > 1
        scale_modal = ImageScaleModal(width, height, is_multi_layer)
        self._set_alt_window_centered_bounds(scale_modal)
        new_size = scale_modal.show_image_modal()
        if new_size is not None:
            if self._generator is not None:
                if self._generator.upscale(new_size):
                    return
            self._scale(new_size)

    @menu_action(MENU_IMAGE, 'crop_image_shortcut', 202, valid_app_states=[APP_STATE_EDITING])
    def crop_image_to_selection(self) -> None:
        """Crop the image to fit selected content."""
        crop_image_stack_to_selection(self._image_stack)

    @menu_action(MENU_IMAGE, 'crop_image_to_gen_shortcut', 202, valid_app_states=[APP_STATE_EDITING])
    def crop_image_to_gen_area(self) -> None:
        """Crop the image to fit the generation area."""
        crop_image_stack_to_gen_area(self._image_stack)

    @menu_action(MENU_IMAGE, 'image_to_layers_shortcut', 203, valid_app_states=[APP_STATE_EDITING])
    def resize_image_to_content(self) -> None:
        """Update the image size to match all layer content."""
        resize_image_stack_to_content(self._image_stack)

    def _metadata_will_be_saved(self) -> bool:
        return self._metadata is not None and METADATA_PARAMETER_KEY in self._metadata

    @staticmethod
    def _updated_metadata_params() -> str:
        cache = Cache()
        prompt = cache.get(Cache.PROMPT)
        negative = cache.get(Cache.NEGATIVE_PROMPT)
        steps = cache.get(Cache.SAMPLING_STEPS)
        sampler = cache.get(Cache.SAMPLING_METHOD)
        cfg_scale = cache.get(Cache.GUIDANCE_SCALE)
        seed = cache.get(Cache.SEED)
        size = cache.get(Cache.GENERATION_SIZE)
        return f'{prompt}\nNegative prompt: {negative}\nSteps: {steps}, Sampler: {sampler}, CFG scale:' + \
            f'{cfg_scale}, Seed: {seed}, Size: {size.width()}x{size.height()}'

    def _metadata_is_latest(self) -> bool:
        if not self._metadata_will_be_saved():
            return False
        return self._metadata is not None and self._updated_metadata_params() == self._metadata[METADATA_PARAMETER_KEY]

    @menu_action(MENU_IMAGE, 'update_metadata_shortcut', 204,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_SELECTION])
    def update_metadata(self, show_messagebox: bool = True) -> None:
        """
        Adds image editing parameters from config to the image metadata, in a format compatible with the A1111
        Stable Diffusion WebUI. Parameters will be applied to the image file when save_image is called.

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

    @menu_action(MENU_IMAGE, 'generator_select_shortcut', 205)
    def show_generator_window(self) -> None:
        """Show the generator selection window."""
        assert self._generator is not None
        if self._generator_window is None:
            self._generator_window = GeneratorSetupWindow()
            self._generator_window.add_generator(self._sd_webui_generator)
            self._generator_window.add_generator(self._sd_comfyui_generator)
            if not is_pyinstaller_bundle():
                self._generator_window.add_generator(self._glid_generator)
            self._generator_window.add_generator(self._glid_web_generator)
            if '--dev' in sys.argv or self._generator == self._test_generator:
                self._generator_window.add_generator(self._test_generator)
            self._generator_window.add_generator(self._null_generator)
            self._generator_window.activate_signal.connect(self.load_image_generator)
        self._generator_window.mark_active_generator(self._generator)
        self._set_alt_window_fractional_bounds(self._generator_window)
        self._generator_window.show()
        self._generator_window.raise_()

    @menu_action(MENU_IMAGE, 'generate_shortcut', 206, valid_app_states=[APP_STATE_EDITING])
    def start_and_manage_inpainting(self) -> None:
        """Start inpainting/image editing based on the current state of the UI."""
        if AppStateTracker.app_state() != APP_STATE_EDITING:
            return
        if self._generator == self._null_generator:
            self.show_generator_window()
        else:
            assert self._generator is not None
            self._generator.start_and_manage_image_generation()

    # Selection menu:
    @menu_action(MENU_SELECTION, 'select_all_shortcut', 300, valid_app_states=[APP_STATE_EDITING])
    def select_all(self) -> None:
        """Selects the entire image."""
        self._image_stack.selection_layer.image = self._image_stack.qimage(crop_to_image=False)

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
        self._image_stack.select_layer_content()

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
    @menu_action(MENU_LAYERS, 'show_layer_menu_shortcut', 399)
    def show_layer_panel(self) -> None:
        """Opens the layer panel window"""
        if self._layer_panel is None:
            self._layer_panel = LayerPanel(self._image_stack)
            if not Cache().load_bounds(Cache.SAVED_LAYER_WINDOW_POS, self._layer_panel):
                width = int(self._layer_panel.sizeHint().width() * 1.5)
                height = self._window.height() // 3
                x = self._window.x() + self._window.width() - int(width * 1.5)
                y = self._window.y() + height
                Cache().set(Cache.SAVED_LAYER_WINDOW_POS, f'{x},{y},{width},{height}')
                Cache().load_bounds(Cache.SAVED_LAYER_WINDOW_POS, self._layer_panel)
        self._layer_panel.show()
        self._layer_panel.raise_()

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
        assert isinstance(active_layer, LayerGroup)
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

    @menu_action(MENU_LAYERS, 'flatten_layer_shortcut', 444, valid_app_states=[APP_STATE_EDITING])
    def flatten_layer(self) -> None:
        """Simplifies the active layer."""
        self._image_stack.flatten_layer()

    @menu_action(MENU_LAYERS, 'layer_to_image_size_shortcut', 445,
                 valid_app_states=[APP_STATE_EDITING])
    def layer_to_image_size(self) -> None:
        """Crop or expand the active layer to match the image size."""
        self._image_stack.layer_to_image_size()

    @menu_action(MENU_LAYERS, 'crop_layer_to_selection_shortcut', 446, valid_app_states=[APP_STATE_EDITING])
    def crop_layer_to_selection(self) -> None:
        """Crop the active layer to fit overlapping selection bounds."""
        crop_layer_to_selection(self._image_stack)

    @menu_action(MENU_LAYERS, 'crop_to_content_shortcut', 447,
                 valid_app_states=[APP_STATE_EDITING])
    def crop_layer_to_content(self) -> None:
        """Crop the active layer to remove fully transparent border pixels."""
        layer = self._image_stack.active_layer
        assert isinstance(layer, (ImageLayer, LayerGroup))
        layer.crop_to_content()

    @menu_action(MENU_HELP, 'help_index_shortcut', 600)
    def open_help_index(self) -> None:
        """Open the IntraPaint documentation index in a browser window."""
        webbrowser.open(HELP_INDEX_LINK)

    # Internal/protected:

    def _set_alt_window_fractional_bounds(self, alt_window: QWidget, preferred_scale: float = 0.8) -> None:
        """Set a new window's bounds centered over the main window bounds, scaled to a given fraction of the main
           window dimensions, restricted to ensure it's not smaller than the minimum size hint or larger than the
           screen."""
        window_bounds = self._window.geometry()
        screen_size = get_screen_size(self._window)
        center = window_bounds.center()
        minimum_size = alt_window.minimumSizeHint()
        window_bounds.setWidth(clamp(int(window_bounds.width() * preferred_scale),
                                     min(minimum_size.width(), screen_size.width(), window_bounds.width()),
                                     screen_size.width()))
        window_bounds.setHeight(clamp(int(window_bounds.height() * preferred_scale),
                                      min(minimum_size.height(), screen_size.height(), window_bounds.height()),
                                      screen_size.height()))
        window_bounds.moveCenter(center)
        alt_window.setGeometry(window_bounds)

    def _set_alt_window_centered_bounds(self, alt_window: QWidget) -> None:
        """Set a new window's bounds centered over the main window bounds, scaled to the sizeHint."""
        window_bounds = self._window.geometry()
        center = window_bounds.center()
        size_hint = alt_window.sizeHint()
        window_bounds.setWidth(size_hint.width())
        window_bounds.setHeight(size_hint.height())
        window_bounds.moveCenter(center)
        alt_window.setGeometry(window_bounds)

    def _scale(self, new_size: QSize) -> None:  # Override to allow alternate or external upscalers:
        scaling_mode_name = Cache().get(Cache.SCALING_MODE)
        scaling_mode = PIL_SCALING_MODES.get(scaling_mode_name, None)
        scale_all_layers(self._image_stack, new_size.width(), new_size.height(), scaling_mode)
