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
- Provides the File menu actions, which delegate to ImageIO (`src/controller/image_io.py`).

User settings:
- Creates the settings modal, ensures that it contains appropriate entries from the assorted Config classes
- Applies changes to config whenever the settings modal closes.
"""
import logging
import os
import sys
import webbrowser
from argparse import Namespace
from typing import Any, Optional, Callable
from weakref import WeakSet

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QTransform
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QWidget

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.controller import color_controller
from src.controller.autosave_controller import AutosaveController
from src.controller.generation_area_controller import GenerationAreaController
from src.controller.image_generation.glid3_webservice_generator import Glid3WebserviceGenerator, DEFAULT_GLID_URL
from src.controller.image_generation.glid3_xl_generator import Glid3XLGenerator
from src.controller.image_generation.image_generator import ImageGenerator
from src.controller.image_generation.null_generator import NullGenerator
from src.controller.image_generation.sd_adapters.controlnet_adapter import count_enabled_units
from src.controller.image_generation.sd_comfyui_generator import SDComfyUIGenerator, DEFAULT_COMFYUI_URL
from src.controller.image_generation.sd_generator import MENU_GENERATION, STABLE_DIFFUSION_CONFIG_CATEGORY, \
    SDGenerator
from src.controller.image_generation.sd_webui_generator import SDWebUIGenerator, DEFAULT_WEBUI_URL
from src.controller.image_generation.test_generator import TestGenerator
from src.controller.image_io import ImageIO, UNTITLED_FILE_NAME
from src.controller.tool_controller import ToolController
from src.hotkey_filter import HotkeyFilter
from src.image.image_metadata import ImageMetadata
from src.image.filter.blur import BlurFilter
from src.image.filter.brightness_contrast import BrightnessContrastFilter
from src.image.filter.filter import ImageFilter
from src.image.filter.invert import InvertFilter
from src.image.filter.posterize import PosterizeFilter
from src.image.filter.rgb_color_balance import RGBColorBalanceFilter
from src.image.filter.saturation import SaturationFilter
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
from src.tools.base_tool import BaseTool
from src.tools.generation_area_tool import GenerationAreaTool
from src.ui.input_fields.pressure_curve_input import PressureCurveInput
from src.ui.modal.image_scale_modal import ImageScaleModal
from src.ui.modal.layout_name_modal import prompt_layout_name, TITLE_SAVE
from src.ui.modal.manage_layouts_modal import ManageLayoutsModal
from src.ui.modal.modal_utils import show_error_dialog, show_warning_dialog
from src.ui.modal.new_image_modal import NewImageModal
from src.ui.modal.resize_canvas_modal import ResizeCanvasModal
from src.ui.modal.settings_modal import SettingsModal
from src.ui.panel.color_panel import ColorControlPanel
from src.ui.panel.generators.stable_diffusion_panel import StableDiffusionPanel
from src.ui.panel.layer_ui.layer_panel import LayerPanel
from src.ui.panel.tool_panel import ToolPanel
from src.ui.theme import apply_appearance_config
from src.ui.window import saved_layouts
from src.ui.window.dock_menu import MENU_MOVE_ALL_TO_EDGE, edge_title
from src.ui.window.dock_placement import DockEdge
from src.ui.window.generator_setup_window import GeneratorSetupWindow
from src.ui.window.main_window import MainWindow
from src.ui.window.metadata_window import MetadataWindow
from src.ui.window.navigation_window import NavigationWindow
from src.ui.window.window_geometry import restore_window
from src.undo_stack import UndoStack
from src.util.active_text_field_tracker import ActiveTextFieldTracker
from src.util.application_state import AppStateTracker, APP_STATE_NO_IMAGE, APP_STATE_EDITING, APP_STATE_LOADING, \
    APP_STATE_SELECTION
from src.util.math_utils import clamp
from src.util.menu_builder import MenuBuilder, menu_action, MENU_DATA_ATTR, MenuData
from src.util.optional_import import optional_import
from src.util.pyinstaller import is_pyinstaller_bundle
from src.util.qtexcepthook import QtExceptHook
from src.util.recent_files import recent_files, clear_recent_files
from src.util.shared_constants import EDIT_MODE_INPAINT
from src.util.shared_text import PIL_SCALING_MODES
from src.util.system_clipboard import clipboard_has_image, clipboard_image_is_own_copy, get_clipboard_image, \
    set_clipboard_image
from src.util.visual.display_size import get_screen_size

# Optional spacenav support:
SpacenavManager = optional_import('src.controller.spacenav_manager', attr_name='SpacenavManager')

logger = logging.getLogger(__name__)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'controller.app_controller'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


APP_NAME = 'IntraPaint'
APP_VERSION = 'v1.4.0'  # x-release-please-version

UNDO_LIMIT_RESTART_TITLE = _tr('Restart required')
UNDO_LIMIT_RESTART_MESSAGE = _tr('The new maximum undo count will apply after IntraPaint is restarted.')

GENERATION_MODE_SD_WEBUI = 'stable-diffusion-webui'
GENERATION_MODE_COMFYUI = 'comfyui'
GENERATION_MODE_LOCAL_GLID = 'glid-local'
GENERATION_MODE_WEB_GLID = 'glid-api'
GENERATION_MODE_NONE = 'none'
GENERATION_MODE_TEST = 'mock'
GENERATION_MODE_AUTO = 'auto'

CONTROLNET_BADGE_TOOLTIP_ONE = _tr('ControlNet: 1 unit on', 'Tooltip of the ControlNet rail button')
CONTROLNET_BADGE_TOOLTIP_MANY = _tr('ControlNet: {count} units on', 'Tooltip of the ControlNet rail button')
CONTROLNET_BADGE_SKIPPED = '!'
CONTROLNET_BADGE_TOOLTIP_SKIPPED = _tr('ControlNet: {count} of {enabled} units on are skipped. Inpainting units only '
                                       'apply in Inpaint mode.', 'Tooltip of the ControlNet rail button')
MENU_FILE = _tr('&File')
MENU_EDIT = _tr('&Edit')
MENU_VIEW = _tr('&View')
MENU_IMAGE = _tr('&Image')
MENU_LAYER = _tr('&Layer')
MENU_SELECT = _tr('&Select')
MENU_FILTERS = _tr('Fil&ters')
REPEAT_FILTER_TITLE = _tr('Repeat {filter_name}')
MENU_WINDOW = _tr('&Window')
MENU_HELP = _tr('&Help')
LAYOUT_ACTION_PROPERTY = 'saved_layout_entry'
TITLE_LAYOUT_ERROR = _tr('Layout not applied')
MESSAGE_LAYOUT_ERROR = _tr('The layout "{layout_name}" could not be restored. It may be corrupt or saved by an older '
                           'version. Delete it in Manage layouts.')
MENU_WINDOW_LAYOUTS = MENU_WINDOW + '.' + _tr('Layouts')
MENU_WINDOW_MOVE_ALL_PANELS = MENU_WINDOW + '.' + MENU_MOVE_ALL_TO_EDGE

SUBMENU_RECENT_FILES = _tr('Open recent')
MENU_ACTION_CLEAR_RECENT = _tr('Clear recent files')
SUBMENU_STACK = _tr('Stack')
SUBMENU_TRANSFORM = _tr('Transform')

PROJECT_LINK = 'https://github.com/centuryglass/IntraPaint'
HELP_INDEX_LINK = f'{PROJECT_LINK}/blob/master/doc/help_index.md'
ISSUES_LINK = f'{PROJECT_LINK}/issues'
RELEASES_LINK = f'{PROJECT_LINK}/releases'
LICENSE_LINK = f'{PROJECT_LINK}/blob/master/LICENSE'
ABOUT_TITLE = _tr('About IntraPaint')
ABOUT_TEXT = _tr('<h3>IntraPaint {version}</h3>'
                 '<p>An image editor that combines digital painting tools with AI image generation and inpainting.</p>'
                 '<p>Free software, released under the <a href="{license_link}">GNU General Public License v3</a>.</p>'
                 '<p><a href="{project_link}">Project page</a> - <a href="{issues_link}">Report a bug</a></p>')
# The settings window category holding the editing, navigation and tool keys:
KEYBINDINGS_CATEGORY = QApplication.translate('config.key_config', 'Keybindings')

GENERATOR_LOAD_ERROR_TITLE = _tr('Loading image generator failed')
GENERATOR_LOAD_ERROR_MESSAGE = _tr('Unable to load the {generator_name} image generator')
CONFIRM_QUIT_BUTTON = _tr('Quit without saving')
NEW_IMAGE_CONFIRMATION_BUTTON = _tr('Create without saving')

IGNORED_APPCONFIG_CATEGORIES = (QApplication.translate('config.application_config', 'Stable Diffusion'),
                                QApplication.translate('config.application_config', 'GLID-3-XL'))
DEV_APPCONFIG_CATEGORY = QApplication.translate('config.application_config', 'Developer')


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
        app.setApplicationName(APP_NAME)
        app.setApplicationDisplayName(APP_NAME)
        app.setApplicationVersion(APP_VERSION)
        config = AppConfig()
        cache = Cache()
        cache.apply_args(args)
        self._layer_dock_panel: Optional[LayerPanel] = None
        self._generator_window: Optional[GeneratorSetupWindow] = None
        self._metadata_window: Optional[MetadataWindow] = None

        # Apply style and theme before creating widgets, which copy the palette and font when they're created:
        apply_appearance_config(config, self)

        # Initialize edited image data structures:
        self._generator: Optional[ImageGenerator] = None
        self._image_stack = ImageStack(config.get(AppConfig.DEFAULT_IMAGE_SIZE), cache.get(Cache.EDIT_SIZE),
                                       config.get(AppConfig.MIN_EDIT_SIZE), config.get(AppConfig.MAX_EDIT_SIZE))
        self._generation_area_controller = GenerationAreaController(self._image_stack)

        # Initialize main window:
        self._window = MainWindow(self._image_stack)
        self._recent_files_menu: Optional[QMenu] = None
        self.menu_window = self._window
        self._image_io = ImageIO(self._window, self._image_stack, lambda: self._generator)
        self._autosave = AutosaveController(self._image_stack, self._image_io, self._window)
        self._image_viewer = self._window.image_panel.image_viewer
        self._window.generate_signal.connect(self.start_and_manage_inpainting)
        self._window.confirm_close = self._confirm_quit
        if args.window_size is not None:
            width, height = (int(dim) for dim in args.window_size.split('x'))
            self._window.setGeometry(0, 0, width, height)
            self._window.setMaximumSize(width, height)
            self._window.setMinimumSize(width, height)
        else:
            restore_window(self._window, Cache().get(Cache.SAVED_MAIN_WINDOW_GEOMETRY))
        # After the geometry, so the docks fit the restored window:
        self._window.restore_dock_state(Cache().get(Cache.SAVED_MAIN_WINDOW_STATE))
        if args.init_image is not None:
            self.load_image(file_path=args.init_image)
        if not self._image_stack.has_image:
            image = QImage(config.get(AppConfig.DEFAULT_IMAGE_SIZE), QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(color_controller.new_image_color())
            self._image_stack.load_image(image)

        # Set up menus in the expected order, so menus don't need to be shown in the order they're initialized:
        ordered_menus = [
            MENU_FILE,
            MENU_EDIT,
            MENU_VIEW,
            MENU_IMAGE,
            MENU_LAYER,
            MENU_SELECT,
            MENU_FILTERS,
            MENU_GENERATION,
            MENU_WINDOW,
            MENU_HELP
        ]
        for menu_name in ordered_menus:
            self.add_menu(menu_name)

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
        # Generator-specific entries slot in between these when a generator is loaded:
        self.add_menu_separator(MENU_GENERATION, 502)
        self.add_menu_separator(MENU_GENERATION, 520)
        self._make_menu_action_checkable(self.toggle_rulers, AppConfig.SHOW_RULERS)
        self._make_menu_action_checkable(self.toggle_control_hints, AppConfig.SHOW_TOOL_CONTROL_HINTS)
        self._make_menu_action_checkable(self.toggle_selection_overlay, AppConfig.SHOW_SELECTION_OVERLAY)
        full_screen_action = self.get_action_for_method(self.toggle_full_screen)
        full_screen_action.setCheckable(True)
        full_screen_action.setChecked(self._window.isFullScreen())
        self._window.full_screen_changed.connect(full_screen_action.setChecked)
        self.insert_menu_actions(MENU_WINDOW, self._window.dock_toggle_actions())
        self.get_menu(MENU_WINDOW_LAYOUTS).aboutToShow.connect(self._update_layout_menu)
        self._build_recent_files_menu()
        self._window.files_dropped.connect(self.open_dropped_files)
        for edge in DockEdge:
            self.add_menu_action(MENU_WINDOW_MOVE_ALL_PANELS, lambda e=edge: self._window.move_all_docks_to_edge(e),
                                 title=edge_title(edge))

        # Since image filter menus follow a very simple pattern, add them here instead of using @menu_action.
        # At the same time, make sure the filter tool's list of available options contains all filters.
        # The repeat action stays disabled until _record_applied_filter registers it with AppStateTracker.
        self._last_filter: Optional[tuple[ImageFilter, list[Any], bool]] = None
        repeat_action = self.add_menu_action(MENU_FILTERS, self.repeat_last_filter, KeyConfig.REPEAT_FILTER_SHORTCUT)
        assert repeat_action is not None
        repeat_action.setEnabled(False)
        self._repeat_filter_action = repeat_action
        self.get_menu(MENU_FILTERS).addSeparator()
        filter_class_names: list[str] = []
        for filter_class in (RGBColorBalanceFilter,
                             BrightnessContrastFilter,
                             SaturationFilter,
                             PosterizeFilter,
                             InvertFilter,
                             BlurFilter,
                             SharpenFilter):
            image_filter = filter_class(self._image_stack)
            filter_class_names.append(image_filter.get_name())

            def _open_filter_modal(filter_instance=image_filter) -> None:
                modal = filter_instance.get_filter_modal()
                modal.filter_applied.connect(lambda values: self._record_applied_filter(filter_instance, values))
                self._set_alt_window_centered_bounds(modal)
                modal.exec()
                modal.deleteLater()

            config_key = image_filter.get_config_key()
            action = self.add_menu_action(MENU_FILTERS,
                                          _open_filter_modal,
                                          config_key)
            assert action is not None
            AppStateTracker.set_enabled_states(action, [APP_STATE_EDITING])
            if filter_class is BlurFilter:
                self.get_menu(MENU_FILTERS).insertSeparator(action)
        cache.update_options(Cache.FILTER_TOOL_SELECTED_FILTER, filter_class_names)  # type: ignore

        # Because Qt has its own bindings on the cut/copy/clear/paste keyboard events, we need to bind these at the
        # hotkeyFilter to ensure that the menu hotkeys can override the Qt bindings. The goal is to ensure that even
        # when a text field is active, these events will get handled in the context of the ImageStack if they wouldn't
        # do anything to the text. Swap and reset colors have no menu entries, so this is their only binding.
        for binding_key, handler in ((KeyConfig.UNDO_SHORTCUT, self.undo),
                                     (KeyConfig.REDO_SHORTCUT, self.redo),
                                     (KeyConfig.CUT_SHORTCUT, self.cut),
                                     (KeyConfig.COPY_SHORTCUT, self.copy),
                                     (KeyConfig.PASTE_SHORTCUT, self.paste),
                                     (KeyConfig.CLEAR_SHORTCUT, self.clear),
                                     (KeyConfig.SWAP_COLORS_SHORTCUT, self.swap_colors),
                                     (KeyConfig.RESET_COLORS_SHORTCUT, self.reset_colors)):
            HotkeyFilter.instance().register_config_keybinding(f'AppController_{binding_key}', handler,
                                                               binding_key)
        # We'll also want flags for tracking whether cut/copy/paste/clear are currently valid for image content, so
        # that we don't need to recalculate that every time they become invalid for an active text field:
        self._can_copy_image = False
        self._can_paste_image = clipboard_has_image()
        self._can_clear_or_cut_image = False

        # Finally, track active text inputs, so we always know when text-relevant events should be available:
        # The tracker's focus and clipboard connections end with the window the actions belong to:
        self._active_text_field_tracker = ActiveTextFieldTracker(self._window)
        self._active_text_field_tracker.status_changed.connect(self._update_enabled_text_relevant_actions)
        clipboard = QApplication.clipboard()
        clipboard.dataChanged.connect(self._update_clipboard_paste_availability)
        # The clipboard outlives the controller, so the connection ends with the window the actions belong to.
        self._window.destroyed.connect(
            lambda: clipboard.dataChanged.disconnect(self._update_clipboard_paste_availability))

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
        UndoStack().clean_changed.connect(lambda _clean: self._update_window_title())  # type: ignore
        Cache().connect(self._window, Cache.LAST_FILE_PATH, lambda _path: self._update_window_title())
        self._update_window_title()
        # "Reopen last generated options" also needs a stored batch, so `_update_enabled_actions` alone sets whether
        # it is enabled, re-checking whenever either the app state or the batch changes:
        restore_action = self.get_action_for_method(self.restore_previous_image_choices)
        assert restore_action is not None
        AppStateTracker.disconnect_from_state(restore_action)
        self._window.previous_options_available.connect(lambda _available: self._update_enabled_actions())
        AppStateTracker.signal().connect(lambda _state: self._update_enabled_actions())

        # ToolPanel/ToolController: Set up editing tools:
        self._tool_controller = ToolController(self._image_stack, self._image_viewer)
        self._tool_panel = ToolPanel()
        self._generation_area_tool = GenerationAreaTool(self._image_stack, self._image_viewer)
        self._generation_area_tool.control_panel.edit_resolution_requested.connect(self.edit_generation_resolution)
        self._last_active_tool: Optional[BaseTool] = None

        # Fill the lower dock group:
        self._tool_panel_navigation_panel = NavigationWindow(self._image_stack, self._image_viewer,
                                                             include_zoom_controls=False, use_keybindings=False)
        self._tool_panel_navigation_panel.mouse_navigation_enabled = False
        self._tool_panel_color_picker = ColorControlPanel()
        self._layer_dock_panel = LayerPanel(self._image_stack)
        self._window.layers_dock.set_content(self._layer_dock_panel)
        self._window.color_dock.set_content(self._tool_panel_color_picker)
        self._window.navigation_dock.set_content(self._tool_panel_navigation_panel)

        # Add all tools to the panel except for the generation area tool:
        for tool in self._tool_controller.tools:
            self._tool_panel.add_tool_button(tool)

        # Connect signal handlers:
        self._tool_panel.tool_selected.connect(self._tool_controller.set_active_tool)
        self._tool_panel.settings_requested.connect(self.show_settings)
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

        self._window.tools_dock.set_content(self._tool_panel)
        self._window.set_tool_controller(self._tool_controller)
        self._generator_control_panel: Optional[QWidget] = None
        self._wired_generator_panels: WeakSet[QWidget] = WeakSet()

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
            QtExceptHook(recovery_cb=self._autosave.keep_for_recovery,
                         recovery_enabled_cb=lambda: self._autosave.enabled).enable()
        self._window.show()
        self._update_enabled_actions()
        restored = self._autosave.offer_recovery()

        # Discard anything saved to the undo stack during the setup process:
        UndoStack().clear()
        if restored:  # The recovery copy holds work that was never saved.
            UndoStack().mark_modified()

        AppStateTracker.set_app_state(APP_STATE_EDITING if self._image_stack.has_image else APP_STATE_NO_IMAGE)
        app.exec()
        self._autosave.shutdown()
        # Saves scheduled in the last moments before exit never got an event loop to run them:
        for config in (AppConfig(), Cache(), KeyConfig()):
            config.save_pending_changes()

    def _watch_controlnet_badge(self) -> None:
        """Shows the number of enabled ControlNet units as the ControlNet dock's badge, and keeps it current. Outside
        Inpaint mode, enabled inpainting units make it a caution badge, since requests skip them."""
        dock = self._window.controlnet_dock
        generator = self._generator
        keys = generator.get_controlnet_unit_cache_keys() if isinstance(generator, SDGenerator) \
            and generator.get_controlnet_panel() is not None else []
        cache = Cache()

        def _update(*_args) -> None:
            inpainting = cache.get(Cache.EDIT_MODE) == EDIT_MODE_INPAINT
            enabled, skipped = count_enabled_units([cache.get(key) for key in keys], inpainting)
            if enabled == 0:
                dock.set_badge('')
            elif skipped > 0:
                dock.set_badge(CONTROLNET_BADGE_SKIPPED,
                               CONTROLNET_BADGE_TOOLTIP_SKIPPED.format(count=skipped, enabled=enabled), caution=True)
            else:
                dock.set_badge(str(enabled), CONTROLNET_BADGE_TOOLTIP_ONE if enabled == 1
                               else CONTROLNET_BADGE_TOOLTIP_MANY.format(count=enabled))

        for key in [*keys, Cache.EDIT_MODE]:
            cache.connect(dock, key, _update)
        _update()

    def load_image_generator(self, generator: ImageGenerator) -> None:
        """Load an image generator, updating controls and settings."""
        # if not generator.is_available():
        #     show_error_dialog(self._window, GENERATOR_LOAD_ERROR_TITLE,
        #                       GENERATOR_LOAD_ERROR_MESSAGE.format(generator_name=generator.get_display_name()))
        #     return
        # unload last generator:
        last_generator = self._null_generator if self._generator is None else self._generator
        if self._generator is not None:
            self._window.controlnet_dock.set_content(None)
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

        self._generator_control_panel = self._generator.get_control_panel()
        if isinstance(self._generator_control_panel, StableDiffusionPanel):
            # A generator keeps its panel, so each panel's signals connect once:
            if self._generator_control_panel not in self._wired_generator_panels:
                self._wired_generator_panels.add(self._generator_control_panel)
                self._generator_control_panel.setup_requested.connect(self.show_generator_window)
                self._generator_control_panel.settings_requested.connect(
                    lambda: self.show_settings(STABLE_DIFFUSION_CONFIG_CATEGORY))
        self._window.generation_dock.set_content(self._generator_control_panel)
        self._window.controlnet_dock.set_content(self._generator.get_controlnet_panel())
        self._watch_controlnet_badge()
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
        image_panels = (self._window.image_panel, self._tool_panel_navigation_panel)
        for image_panel in image_panels:
            image_panel.set_image_generation_controls_visible(show_image_gen_controls)
        self._generation_area_controller.generation_area_visible = show_image_gen_controls
        # The Stable Diffusion panel owns the resolution, which the generation area panel only summarizes:
        self._generation_area_tool.control_panel.set_resolution_shown(
            isinstance(self._generator_control_panel, StableDiffusionPanel))
        generate_action = self.get_action_for_method(self.start_and_manage_inpainting)
        generate_action.setEnabled(self._generator is not None and not isinstance(self._generator, NullGenerator))
        self._update_enabled_actions()

    def edit_generation_resolution(self) -> None:
        """Opens the Image generation dock in its tab group, and focuses its resolution field."""
        self._window.generation_dock.set_open(True)
        if isinstance(self._generator_control_panel, StableDiffusionPanel):
            self._generator_control_panel.reveal_resolution()

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
        undo_limit_changed = AppConfig.MAX_UNDO in changed_settings \
            and changed_settings[AppConfig.MAX_UNDO] != app_config.get(AppConfig.MAX_UNDO)
        for key, value in changed_settings.items():
            if key in base_keys:
                app_config.set(key, value)
            elif key in key_keys:
                KeyConfig().set(key, value)
        if undo_limit_changed:
            show_warning_dialog(self._window, UNDO_LIMIT_RESTART_TITLE, UNDO_LIMIT_RESTART_MESSAGE, None)
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
            self.merge_group,
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
            self.merge_group,
            self.copy_layer,
            self.delete_layer
        }
        not_flat_methods: set[Callable[..., None]] = {self.flatten_layer}
        layer_group_only_methods: set[Callable[..., None]] = {self.merge_group}
        not_layer_group_methods: set[Callable[..., None]] = {
            self.merge_layer_down,
            self.layer_to_image_size
        }

        not_text_layer_methods: set[Callable[..., None]] = {self.crop_layer_to_content}

        managed_menu_methods = selection_methods | unlocked_layer_methods | not_bottom_layer_methods \
                               | not_top_layer_methods | not_layer_stack_methods | not_layer_group_methods \
                               | layer_group_only_methods

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
                                                  (layer_group_only_methods, not isinstance(active_layer, LayerGroup)),
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
            if next_layer is None or next_layer.locked or next_layer.parent_locked or not next_layer.shown \
                    or not isinstance(next_layer, TransformLayer) \
                    or next_layer.layer_parent != active_layer.layer_parent:
                merge_down_action.setEnabled(False)

        # "Merge group" should also be disabled for empty/flat groups:
        merge_group_action = self.get_action_for_method(self.merge_group)
        if merge_group_action.isEnabled() and self._image_stack.layer_is_flat(active_layer):
            merge_group_action.setEnabled(False)

        # "Merge all visible" needs at least one mergeable visible top-level layer:
        merge_visible_action = self.get_action_for_method(self.merge_all_visible)
        if _test_state(self.merge_all_visible):
            visible_top_layers = [layer for layer in self._image_stack.layer_stack.child_layers if layer.shown]
            can_merge_visible = len(visible_top_layers) > 1 or (len(visible_top_layers) == 1
                                                                and isinstance(visible_top_layers[0], LayerGroup)
                                                                and visible_top_layers[0].count > 0)
            merge_visible_action.setEnabled(can_merge_visible)
        else:
            merge_visible_action.setEnabled(False)

        # "Reopen last generated options" also needs a stored batch that still fits the image:
        restore_action = self.get_action_for_method(self.restore_previous_image_choices)
        restore_action.setEnabled(_test_state(self.restore_previous_image_choices)
                                  and self._window.can_restore_previous_options())

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

    def _update_clipboard_paste_availability(self) -> None:
        """Marks image paste available when the system clipboard gains image content, from any program.

        The flag never reverts to False on clipboard changes: content kept in the copy buffer stays pasteable even
        when the clipboard holds no image.
        """
        if clipboard_has_image() and not self._can_paste_image:
            self._can_paste_image = True
            self._update_enabled_actions()

    # Menu action definitions:

    # File menu:

    @menu_action(MENU_FILE, 'new_image_shortcut', 0,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_NO_IMAGE])
    def new_image(self) -> None:
        """Open a new image creation modal."""
        self.wait_for_pending_save()
        default_size = AppConfig().get(AppConfig.DEFAULT_IMAGE_SIZE)
        generation_area_size = self._image_stack.generation_area.size() if self._image_stack.has_image else None
        clipboard_image = get_clipboard_image()
        image_modal = NewImageModal(default_size.width(), default_size.height(), generation_area_size,
                                    None if clipboard_image is None else clipboard_image.size())
        image_size = image_modal.show_image_modal()
        if image_size and self._image_io.confirm_unsaved_changes(NEW_IMAGE_CONFIRMATION_BUTTON):
            new_image = QImage(image_size, QImage.Format.Format_ARGB32_Premultiplied)
            new_image.fill(color_controller.new_image_color())
            Cache().set(Cache.LAST_FILE_PATH, '')
            self._image_stack.load_image(new_image)
            self._image_io.clear_metadata()
            AppStateTracker.set_app_state(APP_STATE_EDITING)

    @menu_action(MENU_FILE, 'save_shortcut', 10,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_SELECTION, APP_STATE_LOADING], separator_before=True)
    def save_image(self) -> None:
        """Saves the edited image, only opening the save dialog if no previous image path is cached."""
        self._image_io.save()

    def wait_for_pending_save(self) -> None:
        """Returns once any background write has finished, keeping the UI responsive while it runs."""
        self._image_io.wait_for_pending_save()

    @menu_action(MENU_FILE, 'save_as_shortcut', 11,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_SELECTION, APP_STATE_LOADING])
    def save_image_as(self, file_path: Optional[str] = None) -> None:
        """Open a save dialog, and save the edited image to disk, preserving any metadata."""
        self._image_io.save_as(file_path)

    @menu_action(MENU_FILE, 'load_shortcut', 1,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_NO_IMAGE])
    def load_image(self, file_path: Optional[str | list[str]] = None) -> None:
        """Open a loading dialog, then load the selected image for editing."""
        self._image_io.load(file_path)

    @menu_action(MENU_FILE, 'load_layers_shortcut', 3,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_NO_IMAGE])
    def load_image_layers(self) -> None:
        """Open one or more images as layers."""
        self._image_io.load_layers()

    def _make_menu_action_checkable(self, method: Callable[..., None], config_key: str) -> None:
        """Shows a boolean AppConfig value as the checked state of the menu action that toggles it."""
        action = self.get_action_for_method(method)
        config = AppConfig()
        action.setCheckable(True)
        action.setChecked(config.get(config_key))
        # Config.connect inspects the callback's signature, which Python 3.11 and 3.12 can't read for Qt methods:
        config.connect(action, config_key,
                       lambda checked: action.setChecked(checked))  # pylint: disable=unnecessary-lambda

    def _build_recent_files_menu(self) -> None:
        """Adds the Open recent submenu below File > Open..., filled each time it opens."""
        file_menu = self.get_menu(MENU_FILE)
        layers_action = self.get_action_for_method(self.load_image_layers)
        self._recent_files_menu = QMenu(SUBMENU_RECENT_FILES, file_menu)
        file_menu.insertMenu(layers_action, self._recent_files_menu)
        self._recent_files_menu.aboutToShow.connect(self._update_recent_files_menu)

    def _update_recent_files_menu(self) -> None:
        """Lists the remembered files, newest first. Entries whose file no longer exists are disabled."""
        menu = self._recent_files_menu
        assert menu is not None
        menu.clear()
        paths = recent_files()
        can_open = AppStateTracker.app_state() in (APP_STATE_EDITING, APP_STATE_NO_IMAGE)
        for path in paths:
            action = menu.addAction(os.path.basename(path).replace('&', '&&'))
            assert action is not None
            action.setToolTip(path)
            action.setEnabled(can_open and os.path.isfile(path))
            action.triggered.connect(lambda _=False, file_path=path: self.load_image(file_path))
        if len(paths) > 0:
            menu.addSeparator()
        clear_action = menu.addAction(MENU_ACTION_CLEAR_RECENT)
        assert clear_action is not None
        clear_action.setEnabled(len(paths) > 0)
        clear_action.triggered.connect(clear_recent_files)

    def open_dropped_files(self, file_paths: list[str]) -> None:
        """Opens image files dropped on the window, adding them as layers if an image is already open."""
        if AppStateTracker.app_state() not in (APP_STATE_EDITING, APP_STATE_NO_IMAGE) or len(file_paths) == 0:
            return
        if self._image_stack.has_image:
            self._image_io.add_layers_from_files(file_paths)
        else:
            self.load_image(file_paths[0])
            if len(file_paths) > 1:
                self._image_io.add_layers_from_files(file_paths[1:])

    @menu_action(MENU_FILE, 'reload_shortcut', 12, valid_app_states=[APP_STATE_EDITING])
    def reload_image(self) -> None:
        """Reload the edited image from disk after getting confirmation from a confirmation dialog."""
        self._image_io.reload()

    @menu_action(MENU_FILE, 'quit_shortcut', 30, separator_before=True)
    def quit(self, skip_confirmation: bool = False) -> None:
        """Quit the application after getting confirmation from the user."""
        if skip_confirmation:
            self.wait_for_pending_save()
            self._window.close_without_confirmation()
        else:
            self._window.close()  # MainWindow.closeEvent asks through _confirm_quit.

    def _update_window_title(self) -> None:
        """Shows the open file's name in the window title, marked while it has unsaved changes."""
        file_path = Cache().get(Cache.LAST_FILE_PATH)
        self._window.setWindowFilePath(file_path if file_path != '' else UNTITLED_FILE_NAME)
        self._window.setWindowModified(not UndoStack().is_clean())

    def _confirm_quit(self) -> bool:
        """Returns whether closing the main window may proceed, offering to save unsaved changes first."""
        confirmed = self._image_io.confirm_unsaved_changes(CONFIRM_QUIT_BUTTON)
        if confirmed:
            self.wait_for_pending_save()
        return confirmed

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

    @menu_action(MENU_EDIT, 'cut_shortcut', 110, valid_app_states=[APP_STATE_EDITING], separator_before=True)
    def cut(self) -> None:
        """Cut selected content from the active image layer, or selected text in an active text field."""
        if self._active_text_field_tracker.focused_can_cut_or_clear():
            text_field = self._active_text_field_tracker.focused_text_input
            assert text_field is not None
            text_field.cut()
        else:
            cut_image = self._image_stack.cut_selected()
            if cut_image is not None and not cut_image.isNull():
                set_clipboard_image(cut_image)
            if not self._can_paste_image:
                self._can_paste_image = True
                self._update_enabled_actions()

    @menu_action(MENU_EDIT, 'copy_shortcut', 111, valid_app_states=[APP_STATE_EDITING])
    def copy(self) -> None:
        """Copy selected content from the active image layer, or selected text in an active text field."""
        if self._active_text_field_tracker.focused_can_copy():
            text_field = self._active_text_field_tracker.focused_text_input
            assert text_field is not None
            text_field.copy()
        else:
            copied_image = self._image_stack.copy_selected()
            if copied_image is not None and not copied_image.isNull():
                set_clipboard_image(copied_image)
            if not self._can_paste_image:
                self._can_paste_image = True
                self._update_enabled_actions()

    @menu_action(MENU_EDIT, 'paste_shortcut', 112, valid_app_states=[APP_STATE_EDITING])
    def paste(self) -> None:
        """Paste copied image content into a new layer, or copied text in an active text field."""
        if self._active_text_field_tracker.focused_can_paste():
            text_field = self._active_text_field_tracker.focused_text_input
            assert text_field is not None
            text_field.paste()
            return
        clipboard_image = get_clipboard_image()
        if clipboard_image is not None and not clipboard_image_is_own_copy():
            self._paste_image_from_system_clipboard(clipboard_image)
        else:
            self._image_stack.paste()

    def _paste_image_from_system_clipboard(self, image: QImage) -> None:
        """Pastes an image copied in another program into a new layer, centered on the generation area when a
        generator is active, or centered in the visible view otherwise."""
        if self._generator != self._null_generator:
            center = self._image_stack.generation_area.center()
        else:
            center = self._image_viewer.visible_scene_bounds.center().toPoint()
        offset = QTransform.fromTranslate(center.x() - (image.width() - 1) // 2,
                                          center.y() - (image.height() - 1) // 2)
        self._image_stack.paste_image(image, offset)

    @menu_action(MENU_EDIT, 'clear_shortcut', 113, valid_app_states=[APP_STATE_EDITING])
    def clear(self) -> None:
        """Clear selected content from the active image layer, or selected text in an active text field."""
        if self._active_text_field_tracker.focused_can_cut_or_clear():
            self._active_text_field_tracker.clear_selected_in_focused()
        else:
            self._image_stack.clear_selected()

    def swap_colors(self) -> None:
        """Swap the foreground and background colors."""
        color_controller.swap()

    def reset_colors(self) -> None:
        """Set the foreground color to black and the background color to white."""
        color_controller.reset()

    @menu_action(MENU_EDIT, 'keyboard_shortcuts_shortcut', 120, separator_before=True)
    def show_keyboard_shortcuts(self) -> None:
        """Show the settings window at the keybinding settings."""
        self.show_settings(KEYBINDINGS_CATEGORY)

    @menu_action(MENU_EDIT, 'settings_shortcut', 121)
    def show_settings(self, category: Optional[str] = None) -> None:
        """Show the settings window, on the tab named `category` if one is given."""
        if self._settings_modal is None:
            self._settings_modal = SettingsModal(self._window)
            self.init_settings(self._settings_modal)
            self._settings_modal.changes_saved.connect(self.update_settings)
        self.refresh_settings(self._settings_modal)
        self._set_alt_window_fractional_bounds(self._settings_modal)
        self._settings_modal.show_modal(category)

    # View menu:

    @menu_action(MENU_VIEW, 'zoom_in_shortcut', 190, valid_app_states=[APP_STATE_EDITING])
    def zoom_in(self) -> None:
        """Zoom in on the image view by one step."""
        self._image_viewer.zoom_in()

    @menu_action(MENU_VIEW, 'zoom_out_shortcut', 191, valid_app_states=[APP_STATE_EDITING])
    def zoom_out(self) -> None:
        """Zoom out from the image view by one step."""
        self._image_viewer.zoom_out()

    @menu_action(MENU_VIEW, 'zoom_actual_size_shortcut', 193, valid_app_states=[APP_STATE_EDITING])
    def zoom_to_actual_size(self) -> None:
        """Show the image at 100% scale."""
        self._image_viewer.zoom_to_actual_size()

    @menu_action(MENU_VIEW, 'reset_view_shortcut', 192, valid_app_states=[APP_STATE_EDITING])
    def reset_view(self) -> None:
        """Fit the whole image in the view."""
        self._image_viewer.follow_generation_area = False
        self._image_viewer.reset_scale()

    @menu_action(MENU_VIEW, 'zoom_to_gen_area_shortcut', 194, valid_app_states=[APP_STATE_EDITING])
    def zoom_to_generation_area(self) -> None:
        """Center the view on the generation area."""
        self._image_viewer.zoom_to_generation_area()

    @menu_action(MENU_VIEW, 'toggle_control_hints_shortcut', 201, valid_app_states=[APP_STATE_EDITING])
    def toggle_control_hints(self) -> None:
        """Show or hide the active tool's control hints below the image."""
        config = AppConfig()
        config.set(AppConfig.SHOW_TOOL_CONTROL_HINTS, not config.get(AppConfig.SHOW_TOOL_CONTROL_HINTS))

    @menu_action(MENU_VIEW, 'toggle_selection_overlay_shortcut', 202, valid_app_states=[APP_STATE_EDITING])
    def toggle_selection_overlay(self) -> None:
        """Show or hide the selection overlay fill, leaving the selection outline in place."""
        config = AppConfig()
        config.set(AppConfig.SHOW_SELECTION_OVERLAY, not config.get(AppConfig.SHOW_SELECTION_OVERLAY))

    @menu_action(MENU_VIEW, 'toggle_full_screen_shortcut', 203,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_NO_IMAGE])
    def toggle_full_screen(self) -> None:
        """Switch the main window between full screen and its previous size, keeping a maximized state."""
        self._window.setWindowState(self._window.windowState() ^ Qt.WindowState.WindowFullScreen)

    @menu_action(MENU_WINDOW, 'reset_dock_layout_shortcut', 520,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_NO_IMAGE])
    def reset_panel_layout(self) -> None:
        """Put every panel back where it starts on first run, and open it."""
        self._window.reset_dock_layout()

    @menu_action(MENU_WINDOW_LAYOUTS, 'save_dock_layout_shortcut', 510,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_NO_IMAGE])
    def save_panel_layout(self) -> None:
        """Save the current panel arrangement under a name chosen by the user."""
        name = prompt_layout_name(self._window, TITLE_SAVE, saved_layouts.default_layout_name(),
                                  set(saved_layouts.layout_names()))
        if name is not None:
            saved_layouts.save_layout(name, self._window.save_dock_state())

    @menu_action(MENU_WINDOW_LAYOUTS, 'manage_dock_layouts_shortcut', 511,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_NO_IMAGE])
    def manage_panel_layouts(self) -> None:
        """Open the dialog for applying, renaming and deleting saved panel layouts."""
        ManageLayoutsModal(self._apply_saved_layout, self._window).exec()

    def _apply_saved_layout(self, name: str) -> None:
        """Applies a saved layout, showing an error if its text can't be restored."""
        try:
            applied = self._window.apply_dock_state(saved_layouts.get_layout_state(name))
        except KeyError:
            applied = False
        if not applied:
            show_error_dialog(self._window, TITLE_LAYOUT_ERROR, MESSAGE_LAYOUT_ERROR.format(layout_name=name))

    def _update_layout_menu(self) -> None:
        """Lists the saved layouts below the static Layouts actions, rebuilt each time the submenu opens."""
        menu = self.get_menu(MENU_WINDOW_LAYOUTS)
        for action in menu.actions():
            if action.property(LAYOUT_ACTION_PROPERTY):
                menu.removeAction(action)
                action.deleteLater()
        names = saved_layouts.layout_names()
        if len(names) == 0:
            return
        separator = menu.addSeparator()
        assert separator is not None
        separator.setProperty(LAYOUT_ACTION_PROPERTY, True)
        enabled = AppStateTracker.app_state() in (APP_STATE_EDITING, APP_STATE_NO_IMAGE)
        for name in names:
            action = menu.addAction(name.replace('&', '&&'))
            assert action is not None
            action.setProperty(LAYOUT_ACTION_PROPERTY, True)
            action.setEnabled(enabled)
            action.triggered.connect(lambda _=False, layout_name=name: self._apply_saved_layout(layout_name))

    @menu_action(MENU_VIEW, 'toggle_rulers_shortcut', 200, separator_before=True)
    def toggle_rulers(self) -> None:
        """Show or hide the rulers beside the image."""
        AppConfig().set(AppConfig.SHOW_RULERS, not AppConfig().get(AppConfig.SHOW_RULERS))

    # Image menu:

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

    @menu_action(f'{MENU_IMAGE}.{SUBMENU_TRANSFORM}', 'image_flip_horizontal_shortcut', 202,
                 valid_app_states=[APP_STATE_EDITING])
    def image_flip_horizontal(self) -> None:
        """Flip the whole image horizontally."""
        self._image_stack.flip_image(True)

    @menu_action(f'{MENU_IMAGE}.{SUBMENU_TRANSFORM}', 'image_flip_vertical_shortcut', 203,
                 valid_app_states=[APP_STATE_EDITING])
    def image_flip_vertical(self) -> None:
        """Flip the whole image vertically."""
        self._image_stack.flip_image(False)

    @menu_action(f'{MENU_IMAGE}.{SUBMENU_TRANSFORM}', 'image_rotate_cw_shortcut', 204,
                 valid_app_states=[APP_STATE_EDITING])
    def image_rotate_cw(self) -> None:
        """Rotate the whole image 90 degrees clockwise."""
        self._image_stack.rotate_image(90)

    @menu_action(f'{MENU_IMAGE}.{SUBMENU_TRANSFORM}', 'image_rotate_ccw_shortcut', 205,
                 valid_app_states=[APP_STATE_EDITING])
    def image_rotate_ccw(self) -> None:
        """Rotate the whole image 90 degrees counter-clockwise."""
        self._image_stack.rotate_image(-90)

    @menu_action(f'{MENU_IMAGE}.{SUBMENU_TRANSFORM}', 'image_rotate_180_shortcut', 206,
                 valid_app_states=[APP_STATE_EDITING])
    def image_rotate_180(self) -> None:
        """Rotate the whole image 180 degrees."""
        self._image_stack.rotate_image(180)

    @menu_action(MENU_IMAGE, 'crop_image_shortcut', 210, valid_app_states=[APP_STATE_EDITING], separator_before=True)
    def crop_image_to_selection(self) -> None:
        """Crop the image to fit selected content."""
        crop_image_stack_to_selection(self._image_stack)

    @menu_action(MENU_IMAGE, 'crop_image_to_gen_shortcut', 211, valid_app_states=[APP_STATE_EDITING])
    def crop_image_to_gen_area(self) -> None:
        """Crop the image to fit the generation area."""
        crop_image_stack_to_gen_area(self._image_stack)

    @menu_action(MENU_IMAGE, 'image_to_layers_shortcut', 212, valid_app_states=[APP_STATE_EDITING])
    def resize_image_to_content(self) -> None:
        """Update the image size to match all layer content."""
        resize_image_stack_to_content(self._image_stack)

    @menu_action(MENU_IMAGE, 'update_metadata_shortcut', 220,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_SELECTION], separator_before=True)
    def show_metadata_window(self) -> None:
        """Opens the window for viewing and editing the image's metadata, or raises it if it is already open."""
        metadata = self._image_io.metadata
        if self._metadata_window is None:
            self._metadata_window = MetadataWindow(metadata, lambda: Cache().get(Cache.LAST_FILE_PATH))
            self._metadata_window.metadata_applied.connect(self._apply_edited_metadata)
            self._image_io.on_metadata_replaced = self._metadata_window.set_metadata
        else:
            self._metadata_window.set_metadata(metadata)
        self._metadata_window.show()
        self._metadata_window.raise_()
        self._metadata_window.activateWindow()

    def _apply_edited_metadata(self, metadata: ImageMetadata) -> None:
        """Makes the metadata window's applied edits the image's metadata, which the next save writes."""
        self._image_io.metadata = metadata

    @menu_action(MENU_GENERATION, 'generator_select_shortcut', 530)
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

    @menu_action(MENU_GENERATION, 'generate_shortcut', 500, valid_app_states=[APP_STATE_EDITING])
    def start_and_manage_inpainting(self) -> None:
        """Start inpainting/image editing based on the current state of the UI."""
        if AppStateTracker.app_state() != APP_STATE_EDITING:
            return
        if self._generator == self._null_generator:
            self.show_generator_window()
        else:
            assert self._generator is not None
            self._generator.start_and_manage_image_generation()

    @menu_action(MENU_GENERATION, 'restore_choices_shortcut', 501, valid_app_states=[APP_STATE_EDITING])
    def restore_previous_image_choices(self) -> None:
        """Re-open the last batch of generated image options."""
        if self._window.can_restore_previous_options():
            self._window.restore_previous_image_selection_options()

    # Select menu:
    @menu_action(MENU_SELECT, 'select_all_shortcut', 300, valid_app_states=[APP_STATE_EDITING])
    def select_all(self) -> None:
        """Selects the entire image."""
        self._image_stack.selection_layer.image = self._image_stack.qimage(crop_to_image=False)

    @menu_action(MENU_SELECT, 'select_none_shortcut', 301, valid_app_states=[APP_STATE_EDITING])
    def select_none(self) -> None:
        """Clears the selection."""
        self._image_stack.selection_layer.clear()

    @menu_action(MENU_SELECT, 'invert_selection_shortcut', 302,
                 valid_app_states=[APP_STATE_EDITING])
    def invert_selection(self) -> None:
        """Swaps selected and unselected areas."""
        self._image_stack.selection_layer.invert_selection()

    @menu_action(MENU_SELECT, 'select_layer_content_shortcut', 310,
                 valid_app_states=[APP_STATE_EDITING], separator_before=True)
    def select_active_layer_content(self) -> None:
        """Selects all pixels in the active layer that are not fully transparent."""
        self._image_stack.select_layer_content()

    @menu_action(MENU_SELECT, 'grow_selection_shortcut', 320,
                 valid_app_states=[APP_STATE_EDITING], separator_before=True)
    def grow_selection(self, num_pixels=1) -> None:
        """Expand the selection by a given pixel count, 1 by default."""
        self._image_stack.selection_layer.grow_or_shrink_selection(num_pixels)

    @menu_action(MENU_SELECT, 'shrink_selection_shortcut', 321,
                 valid_app_states=[APP_STATE_EDITING])
    def shrink_selection(self, num_pixels=1) -> None:
        """Contract the selection by a given pixel count, 1 by default."""
        self._image_stack.selection_layer.grow_or_shrink_selection(-num_pixels)

    @menu_action(MENU_SELECT, 'clear_context_pins_shortcut', 330,
                 valid_app_states=[APP_STATE_EDITING], separator_before=True)
    def clear_context_pins(self) -> None:
        """Removes all context pins."""
        self._image_stack.selection_layer.clear_context_pins()

    # Layer menu:
    @menu_action(MENU_LAYER, 'rename_layer_shortcut', 410, valid_app_states=[APP_STATE_EDITING], separator_before=True)
    def rename_layer(self) -> None:
        """Edit the active layer's name in the layer panel, opening its dock if it is closed."""
        panel = self._layer_dock_panel
        if panel is not None:
            self._window.layers_dock.open_in_group()
            panel.start_rename()

    @menu_action(f'{MENU_LAYER}.{SUBMENU_STACK}', 'select_previous_layer_shortcut', 420,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_SELECTION])
    def select_previous_layer(self) -> None:
        """Select the layer above the current active layer."""
        self._image_stack.offset_active_selection(-1)

    @menu_action(f'{MENU_LAYER}.{SUBMENU_STACK}', 'select_next_layer_shortcut', 421,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_SELECTION])
    def select_next_layer(self) -> None:
        """Select the layer below the current active layer."""
        self._image_stack.offset_active_selection(1)

    @menu_action(f'{MENU_LAYER}.{SUBMENU_STACK}', 'move_layer_up_shortcut', 422,
                 valid_app_states=[APP_STATE_EDITING], separator_before=True)
    def move_layer_up(self) -> None:
        """Move the active layer up in the image."""
        self._image_stack.move_layer_by_offset(-1)

    @menu_action(f'{MENU_LAYER}.{SUBMENU_STACK}', 'move_layer_down_shortcut', 423,
                 valid_app_states=[APP_STATE_EDITING])
    def move_layer_down(self) -> None:
        """Move the active layer down in the image."""
        self._image_stack.move_layer_by_offset(1)

    @menu_action(f'{MENU_LAYER}.{SUBMENU_STACK}', 'move_layer_to_top_shortcut', 424,
                 valid_app_states=[APP_STATE_EDITING])
    def move_layer_to_top(self) -> None:
        """Move the active layer to the top of the layer stack."""
        self._image_stack.move_layer(self._image_stack.active_layer, self._image_stack.layer_stack, 0)

    def _transform_active_layer(self, change: Callable[[TransformLayer], None]) -> None:
        """Applies a transformation to the active layer, or to every layer in the active layer group."""
        active_layer = self._image_stack.active_layer
        if isinstance(active_layer, TransformLayer):
            change(active_layer)
            return
        assert isinstance(active_layer, LayerGroup)
        transform_group = TransformGroup(active_layer)
        try:
            change(transform_group)
        finally:
            transform_group.remove_all()

    @menu_action(f'{MENU_LAYER}.{SUBMENU_TRANSFORM}', 'layer_mirror_horizontal_shortcut', 430,
                 valid_app_states=[APP_STATE_EDITING])
    def layer_mirror_horizontal(self) -> None:
        """Flip the active layer horizontally."""
        self._transform_active_layer(lambda layer: layer.flip_horizontal())

    @menu_action(f'{MENU_LAYER}.{SUBMENU_TRANSFORM}', 'layer_mirror_vertical_shortcut', 431,
                 valid_app_states=[APP_STATE_EDITING])
    def layer_mirror_vertical(self) -> None:
        """Flip the active layer vertically."""
        self._transform_active_layer(lambda layer: layer.flip_vertical())

    @menu_action(f'{MENU_LAYER}.{SUBMENU_TRANSFORM}', 'layer_rotate_cw_shortcut', 432,
                 valid_app_states=[APP_STATE_EDITING])
    def layer_rotate_cw(self) -> None:
        """Rotate the active layer 90 degrees clockwise."""
        self._transform_active_layer(lambda layer: layer.rotate(90))

    @menu_action(f'{MENU_LAYER}.{SUBMENU_TRANSFORM}', 'layer_rotate_ccw_shortcut', 433,
                 valid_app_states=[APP_STATE_EDITING])
    def layer_rotate_ccw(self) -> None:
        """Rotate the active layer 90 degrees counter-clockwise."""
        self._transform_active_layer(lambda layer: layer.rotate(-90))

    @menu_action(MENU_LAYER, 'new_layer_shortcut', 400,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_SELECTION])
    def new_layer(self) -> None:
        """Create a new image layer above the active layer."""
        self._image_stack.create_layer()

    @menu_action(MENU_LAYER, 'new_layer_group_shortcut', 401,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_SELECTION])
    def new_layer_group(self) -> None:
        """Create a new layer group above the active layer."""
        self._image_stack.create_layer_group()

    @menu_action(MENU_LAYER, 'copy_layer_shortcut', 402,
                 valid_app_states=[APP_STATE_EDITING, APP_STATE_SELECTION])
    def copy_layer(self) -> None:
        """Duplicate the active layer."""
        self._image_stack.copy_layer()

    @menu_action(MENU_LAYER, 'delete_layer_shortcut', 403, valid_app_states=[APP_STATE_EDITING])
    def delete_layer(self) -> None:
        """Delete the active layer."""
        self._image_stack.remove_layer()

    @menu_action(MENU_LAYER, 'merge_layer_down_shortcut', 440,
                 valid_app_states=[APP_STATE_EDITING], separator_before=True)
    def merge_layer_down(self) -> None:
        """Merge the active layer with the one beneath it."""
        self._image_stack.merge_layer_down()

    @menu_action(MENU_LAYER, 'merge_group_shortcut', 441, valid_app_states=[APP_STATE_EDITING])
    def merge_group(self) -> None:
        """Merge the active layer group into a single image layer."""
        self._image_stack.merge_group()

    @menu_action(MENU_LAYER, 'merge_all_visible_shortcut', 442, valid_app_states=[APP_STATE_EDITING])
    def merge_all_visible(self) -> None:
        """Merge all visible layers into a single image layer."""
        self._image_stack.merge_all_visible()

    @menu_action(MENU_LAYER, 'flatten_layer_shortcut', 443, valid_app_states=[APP_STATE_EDITING])
    def flatten_layer(self) -> None:
        """Simplifies the active layer."""
        self._image_stack.flatten_layer()

    @menu_action(MENU_LAYER, 'layer_to_image_size_shortcut', 450,
                 valid_app_states=[APP_STATE_EDITING], separator_before=True)
    def layer_to_image_size(self) -> None:
        """Crop or expand the active layer to match the image size."""
        self._image_stack.layer_to_image_size()

    @menu_action(MENU_LAYER, 'crop_layer_to_selection_shortcut', 451, valid_app_states=[APP_STATE_EDITING])
    def crop_layer_to_selection(self) -> None:
        """Crop the active layer to fit overlapping selection bounds."""
        crop_layer_to_selection(self._image_stack)

    @menu_action(MENU_LAYER, 'crop_to_content_shortcut', 452,
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

    @menu_action(MENU_HELP, 'report_bug_shortcut', 610, separator_before=True)
    def open_issue_tracker(self) -> None:
        """Open the GitHub issue tracker in a browser window."""
        webbrowser.open(ISSUES_LINK)

    @menu_action(MENU_HELP, 'release_notes_shortcut', 611)
    def open_release_notes(self) -> None:
        """Open the GitHub releases page in a browser window."""
        webbrowser.open(RELEASES_LINK)

    @menu_action(MENU_HELP, 'about_shortcut', 620, separator_before=True)
    def show_about(self) -> None:
        """Show IntraPaint's version, license and project links."""
        QMessageBox.about(self._window, ABOUT_TITLE, ABOUT_TEXT.format(version=APP_VERSION, license_link=LICENSE_LINK,
                                                                       project_link=PROJECT_LINK,
                                                                       issues_link=ISSUES_LINK))

    @menu_action(MENU_HELP, 'about_qt_shortcut', 621)
    def show_about_qt(self) -> None:
        """Show Qt's version and license."""
        QMessageBox.aboutQt(self._window)

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

    def repeat_last_filter(self) -> None:
        """Applies the last filter applied from the Filters menu again, with the same values and no dialog."""
        if self._last_filter is None:
            return
        image_filter, param_values, active_layer_only = self._last_filter
        image_filter.active_layer_only = active_layer_only
        image_filter.selection_only = not self._image_stack.selection_layer.empty
        image_filter.apply_filter(param_values)

    def _record_applied_filter(self, image_filter: ImageFilter, param_values: list[Any]) -> None:
        """Saves a filter applied from its dialog for repeat_last_filter, and names it in the repeat action."""
        if self._last_filter is None:
            AppStateTracker.set_enabled_states(self._repeat_filter_action, [APP_STATE_EDITING])
        self._last_filter = (image_filter, list(param_values), image_filter.active_layer_only)
        self._repeat_filter_action.setText(REPEAT_FILTER_TITLE.format(filter_name=image_filter.get_name()))

    def _set_alt_window_centered_bounds(self, alt_window: QWidget) -> None:
        """Set a new window's bounds centered over the main window bounds, scaled to the sizeHint and restricted to
           the screen size, unless the minimum size hint is larger."""
        window_bounds = self._window.geometry()
        center = window_bounds.center()
        size_hint = alt_window.sizeHint()
        minimum_size = alt_window.minimumSizeHint()
        screen_size = get_screen_size(self._window)
        window_bounds.setWidth(max(min(size_hint.width(), screen_size.width()), minimum_size.width()))
        window_bounds.setHeight(max(min(size_hint.height(), screen_size.height()), minimum_size.height()))
        window_bounds.moveCenter(center)
        alt_window.setGeometry(window_bounds)

    def _scale(self, new_size: QSize) -> None:  # Override to allow alternate or external upscalers:
        scaling_mode_name = Cache().get(Cache.SCALING_MODE)
        scaling_mode = PIL_SCALING_MODES.get(scaling_mode_name, None)
        scale_all_layers(self._image_stack, new_size.width(), new_size.height(), scaling_mode)
