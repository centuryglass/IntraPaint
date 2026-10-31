"""Captures IntraPaint's secondary windows: dialogs, message boxes and the windows opened from menus.

`scripts/capture_ui.py --windows` saves these as images for review, and `window_capture_test.py` checks that every
scene builds and renders. Panel and main window captures are in `test/ui/panel_capture.py`.

- Each `WindowScene` builds its window from a mock-mode `AppController`, filled with sample content where the real
  window would show backend data (LoRA models, prompt styles, upscaling models).
- Message boxes come from the `modal_utils` helpers the app calls, with `QMessageBox.exec` patched to hand the box back
  unopened, so each capture shows the box those helpers build. There is one scene per form of message box, not one
  per message.
- A window is captured at the size the app opens it at (`opened`), its minimum size hint where that differs, and for
  resizable windows a large size. A top-level window can't be sized below its minimum, so captures report the size
  they got.
- The Generated image selector, the navigation window and the GLID-3-XL quick edit window are out of scope: the
  first two are covered by panel captures, and the last is legacy.
"""
from contextlib import AbstractContextManager, ExitStack, contextmanager, nullcontext
from dataclasses import dataclass, field
import json
from typing import Callable, Iterator, Optional, TYPE_CHECKING
from unittest.mock import patch

from PySide6.QtCore import QPoint, QSize
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter
from PySide6.QtWidgets import QMessageBox, QScrollArea, QTabWidget, QWidget

from test.ui.panel_capture import WINDOW_SIZES, _settle_layouts

if TYPE_CHECKING:
    from src.controller.app_controller import AppController

# The app opens some windows at a fraction of the main window's size (`AppController._set_alt_window_fractional_bounds`):
ALT_WINDOW_SCALE = 0.8
REFERENCE_MAIN_WINDOW = WINDOW_SIZES['hd']
LARGE_MAIN_WINDOW = WINDOW_SIZES['full_hd']
SAMPLE_IMAGE_SIZE = QSize(512, 384)


def _scaled(size: QSize, scale: float) -> QSize:
    return QSize(round(size.width() * scale), round(size.height() * scale))


def fractional_size() -> QSize:
    """Returns the size the app opens a fractionally sized window at, over the reference main window."""
    return _scaled(REFERENCE_MAIN_WINDOW, ALT_WINDOW_SCALE)


@dataclass(frozen=True)
class WindowScene:
    """A secondary window to capture: its name, and a function that builds it from a mock-mode AppController.

    `opened` returns the size the app opens the window at, by default its size hint. A `resizable` scene is also
    captured at a large size, and a `full_content` scene at the opened width, tall enough that its visible scroll
    area doesn't scroll (`full_content_size`). `build` runs inside the context manager `context` returns, and so does the capture.
    """
    name: str
    build: Callable[['AppController'], QWidget]
    opened: Callable[[QWidget], QSize] = field(default=lambda window: window.sizeHint())
    resizable: bool = False
    full_content: bool = False
    context: Callable[[], AbstractContextManager] = nullcontext

    def sizes(self, window: QWidget) -> dict[str, QSize]:
        """Returns the sizes to capture the window at, by size name, leaving out a minimum size equal to the opened
        size."""
        sizes = {'opened': self.opened(window)}
        minimum = window.minimumSizeHint().expandedTo(QSize(1, 1))
        if minimum != sizes['opened']:
            sizes['minimum'] = minimum
        if self.resizable:
            sizes['large'] = _scaled(LARGE_MAIN_WINDOW, ALT_WINDOW_SCALE)
        if self.full_content:
            sizes['full_content'] = full_content_size(window, sizes['opened'])
        return sizes


def full_content_size(window: QWidget, size: QSize) -> QSize:
    """Returns `size` made tall enough that the window's visible scroll areas show all of their content."""
    capture_window(window, size)
    extra = 0
    for scroll_area in window.findChildren(QScrollArea):
        content = scroll_area.widget()
        if content is not None and scroll_area.isVisibleTo(window):
            extra = max(extra, content.sizeHint().height() - scroll_area.viewport().height())
    return QSize(size.width(), size.height() + max(extra, 0))


def capture_window(window: QWidget, size: QSize) -> QImage:
    """Resizes and shows a window without entering its event loop, settles its layouts and returns a render of it.

    Showing a modal dialog with `show` doesn't block, unlike `exec`.
    """
    window.resize(size)
    window.show()
    _settle_layouts(window)
    return window.grab().toImage()


def release_window(window: QWidget) -> None:
    """Hides a captured window and schedules it for deletion, unless it is the controller's own."""
    window.hide()
    if window.parentWidget() is None and not getattr(window, '_capture_keep', False):
        window.deleteLater()


# ---------------------------------------------------------------------------------------------------------------------
# Message boxes
# ---------------------------------------------------------------------------------------------------------------------


def _message_box(show: Callable[[], object]) -> QMessageBox:
    """Runs a `modal_utils` helper with `QMessageBox.exec` patched to keep the box, and returns the box it built."""
    boxes: list[QMessageBox] = []

    def _keep(box: QMessageBox, *_args) -> int:
        boxes.append(box)
        return QMessageBox.StandardButton.Cancel.value

    with patch.object(QMessageBox, 'exec', _keep):
        show()
    assert len(boxes) == 1, f'expected one message box, got {len(boxes)}'
    return boxes[0]


def _error_box(_controller: 'AppController') -> QWidget:
    # pylint: disable=import-outside-toplevel
    from src.image.layers.image_stack import ERROR_MESSAGE_GROUP_MERGE_BLOCKED, ERROR_TITLE_MERGE_FAILED
    from src.ui.modal.modal_utils import show_error_dialog
    return _message_box(lambda: show_error_dialog(None, ERROR_TITLE_MERGE_FAILED, ERROR_MESSAGE_GROUP_MERGE_BLOCKED))


def _warning_box(_controller: 'AppController') -> QWidget:
    # pylint: disable=import-outside-toplevel
    from src.config.application_config import AppConfig
    from src.controller.app_controller import ALPHA_NOT_SAVED_MESSAGE, ALPHA_NOT_SAVED_TITLE
    from src.ui.modal.modal_utils import show_warning_dialog
    message = ALPHA_NOT_SAVED_MESSAGE.format(alpha_formats='PNG, WEBP, ORA, TIFF')
    return _message_box(lambda: show_warning_dialog(None, ALPHA_NOT_SAVED_TITLE, message,
                                                    AppConfig.WARN_BEFORE_RGB_SAVE))


def _confirm_box(_controller: 'AppController') -> QWidget:
    # pylint: disable=import-outside-toplevel
    from src.controller.app_controller import LARGE_ANIMATION_BUTTON, LARGE_ANIMATION_MESSAGE, LARGE_ANIMATION_TITLE
    from src.ui.modal.modal_utils import request_confirmation
    message = LARGE_ANIMATION_MESSAGE.format(file_name='walk_cycle.gif', frame_count=480, size_gb=1.4)
    return _message_box(lambda: request_confirmation(None, LARGE_ANIMATION_TITLE, message, None,
                                                     QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No,
                                                     confirm_label=LARGE_ANIMATION_BUTTON))


def _confirm_remember_box(_controller: 'AppController') -> QWidget:
    # pylint: disable=import-outside-toplevel
    from src.config.application_config import AppConfig
    from src.controller.app_controller import MESSAGE_CONFIRM_METADATA_INIT, TITLE_CONFIRM_METADATA_INIT
    from src.ui.modal.modal_utils import request_confirmation
    return _message_box(lambda: request_confirmation(None, TITLE_CONFIRM_METADATA_INIT, MESSAGE_CONFIRM_METADATA_INIT,
                                                     AppConfig.ALWAYS_INIT_METADATA_ON_SAVE,
                                                     QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No))


def _discard_box(_controller: 'AppController') -> QWidget:
    # pylint: disable=import-outside-toplevel
    from src.controller.app_controller import CONFIRM_QUIT_BUTTON, CONFIRM_QUIT_MESSAGE, CONFIRM_QUIT_TITLE
    from src.ui.modal.modal_utils import request_confirmation
    return _message_box(lambda: request_confirmation(None, CONFIRM_QUIT_TITLE, CONFIRM_QUIT_MESSAGE,
                                                     discards_work=True, confirm_label=CONFIRM_QUIT_BUTTON))


def _bug_report_box(_controller: 'AppController') -> QWidget:
    # pylint: disable=import-outside-toplevel,protected-access
    from src.util.qtexcepthook import QtExceptHook
    hook = QtExceptHook()
    box = hook._dialog
    box.setDetailedText('Traceback (most recent call last):\n  File "example.py", line 1, in <module>\n'
                        'ValueError: example')
    return box


# ---------------------------------------------------------------------------------------------------------------------
# Dialogs and windows
# ---------------------------------------------------------------------------------------------------------------------


def _sample_image(size: QSize = SAMPLE_IMAGE_SIZE) -> QImage:
    """Returns a colorful gradient, so filter and canvas previews show what they change."""
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(image)
    horizontal = QLinearGradient(QPoint(0, 0), QPoint(size.width(), 0))
    for stop, color in ((0.0, '#d04040'), (0.33, '#e0c040'), (0.66, '#40a060'), (1.0, '#4060d0')):
        horizontal.setColorAt(stop, QColor(color))
    painter.fillRect(image.rect(), horizontal)
    vertical = QLinearGradient(QPoint(0, 0), QPoint(0, size.height()))
    vertical.setColorAt(0.0, QColor(255, 255, 255, 0))
    vertical.setColorAt(1.0, QColor(0, 0, 0, 200))
    painter.fillRect(image.rect(), vertical)
    painter.end()
    return image


def _with_sample_image(controller: 'AppController') -> None:
    """Gives the controller's active layer the sample image, once per controller."""
    # pylint: disable=protected-access
    layer = controller._image_stack.active_layer
    if getattr(controller, '_capture_has_sample_image', False) or not hasattr(layer, 'set_image'):
        return
    layer.set_image(_sample_image(controller._image_stack.size))
    setattr(controller, '_capture_has_sample_image', True)


def _settings_modal(controller: 'AppController', tab_index: int) -> QWidget:
    """Returns the controller's settings modal on one tab, with the Stable Diffusion settings a generator adds."""
    # pylint: disable=import-outside-toplevel,protected-access
    from src.config.application_config import AppConfig
    from src.controller.image_generation.sd_generator import STABLE_DIFFUSION_CONFIG_CATEGORY
    modal = controller._settings_modal
    assert modal is not None
    if not getattr(modal, '_capture_has_sd', False):
        modal.load_from_config(AppConfig(), [STABLE_DIFFUSION_CONFIG_CATEGORY])
        setattr(modal, '_capture_has_sd', True)
    controller.refresh_settings(modal)
    tabs = modal.findChild(QTabWidget)
    assert tabs is not None
    tabs.setCurrentIndex(tab_index)
    setattr(modal, '_capture_keep', True)
    return modal


def _settings_scenes(controller: 'AppController') -> list[WindowScene]:
    # pylint: disable=protected-access
    modal = _settings_modal(controller, 0)
    tabs = modal.findChild(QTabWidget)
    assert tabs is not None
    scenes = []
    for index in range(tabs.count()):
        name = 'settings_' + ''.join(char if char.isalnum() else '_' for char in tabs.tabText(index).lower())
        scenes.append(WindowScene(name, lambda c, i=index: _settings_modal(c, i), lambda _w: fractional_size(),
                                  resizable=True, full_content=True))
    return scenes


def _generator_setup(controller: 'AppController') -> QWidget:
    """Returns the generator window built as `AppController.show_generator_window` builds it, with the WebUI
    generator selected and unavailable, since its description and setup text are the longest."""
    # pylint: disable=import-outside-toplevel,protected-access
    from src.ui.window.generator_setup_window import GeneratorSetupWindow
    window = GeneratorSetupWindow()
    for generator in (controller._sd_webui_generator, controller._sd_comfyui_generator, controller._glid_web_generator,
                      controller._test_generator, controller._null_generator):
        window.add_generator(generator)
    window.mark_active_generator(controller._null_generator)
    with patch.object(controller._sd_webui_generator, 'is_available', return_value=False):
        window.select_generator(controller._sd_webui_generator)
    return window


def _filter_modal(controller: 'AppController', filter_name: str) -> QWidget:
    # pylint: disable=import-outside-toplevel,protected-access
    from src.image.filter.blur import BlurFilter
    from src.image.filter.rgb_color_balance import RGBColorBalanceFilter
    from src.image.filter.invert import InvertFilter
    _with_sample_image(controller)
    filter_class = {'blur': BlurFilter, 'rgb_color_balance': RGBColorBalanceFilter, 'invert': InvertFilter}[filter_name]
    return filter_class(controller._image_stack).get_filter_modal()


def _resize_canvas(controller: 'AppController') -> QWidget:
    # pylint: disable=import-outside-toplevel,protected-access
    from src.ui.modal.resize_canvas_modal import ResizeCanvasModal
    _with_sample_image(controller)
    return ResizeCanvasModal(controller._image_stack)


@contextmanager
def _sd_upscaling_cache() -> Iterator[None]:
    """Sets the Cache values a WebUI backend with ControlNet tile upscaling leaves, and restores them afterwards."""
    # pylint: disable=import-outside-toplevel
    from sd_backend_client import CONTROLNET_MODEL_NONE, ControlNetModel, ControlNetPreprocessor, ControlNetUnit, \
        PreprocessorParams
    from src.config.cache import Cache
    from src.controller.image_generation.sd_adapters.controlnet_adapter import SavedControlNetUnit
    tile_model = 'control_v11f1e_sd15_tile'
    preprocessor = ControlNetPreprocessor(name='tile_resample')
    tile_unit = ControlNetUnit(model=ControlNetModel(tile_model),
                               preprocessor=PreprocessorParams(typedef=preprocessor, parameter_values={}),
                               control_strength=0.75, control_start=0.1, control_end=0.9)
    values = {Cache.SD_UPSCALING_AVAILABLE: True, Cache.USE_STABLE_DIFFUSION_UPSCALING: True,
              Cache.ULTIMATE_UPSCALE_SCRIPT_AVAILABLE: True,
              Cache.GENERATOR_SCALING_MODES: ['ESRGAN_4x', 'R-ESRGAN 4x+', 'SwinIR_4x'],
              Cache.SD_UPSCALING_CONTROLNET_TILE_MODELS: [tile_model, CONTROLNET_MODEL_NONE],
              Cache.SD_UPSCALING_CONTROLNET_TILE_PREPROCESSORS: [preprocessor.model_dump_json()],
              Cache.SD_UPSCALING_CONTROLNET_TILE_SETTINGS: SavedControlNetUnit(True, '', tile_unit).to_json()}
    cache = Cache()
    saved = {key: cache.get(key) for key in values}
    with ExitStack() as stack:
        for key, value in values.items():
            cache.set(key, value)
            stack.callback(cache.set, key, saved[key])
        yield


def _image_scale(controller: 'AppController', multi_layer: bool) -> QWidget:
    # pylint: disable=import-outside-toplevel,protected-access
    from src.ui.modal.image_scale_modal import ImageScaleModal
    size = controller._image_stack.size
    return ImageScaleModal(size.width(), size.height(), multi_layer)


def _lora_window(_controller: 'AppController') -> QWidget:
    # pylint: disable=import-outside-toplevel
    from src.ui.window.extra_network_window import ExtraNetworkWindow
    names = ('add_detail', 'lcm_lora_sdxl', 'watercolor_style_v2', 'film_grain', 'detail_tweaker_xl')
    loras = [{'name': name, 'alias': name, 'path': f'/models/Lora/{name}.safetensors', 'metadata': '{}'}
             for name in names]
    images: dict[str, Optional[QImage]] = {names[0]: _sample_image(QSize(150, 150)),
                                           names[2]: _sample_image(QSize(150, 100))}
    return ExtraNetworkWindow(loras, images)


@contextmanager
def _prompt_styles_cache() -> Iterator[None]:
    # pylint: disable=import-outside-toplevel
    from src.config.cache import Cache
    styles = [{'name': 'Cinematic', 'prompt': '{prompt}, cinematic lighting, shallow depth of field, film grain',
               'negative_prompt': 'cartoon, flat colors'},
              {'name': 'Watercolor', 'prompt': 'watercolor painting, soft edges, paper texture',
               'negative_prompt': 'photo, sharp'},
              {'name': 'Line art', 'prompt': 'clean line art, monochrome', 'negative_prompt': 'shading, color'}]
    cache = Cache()
    saved = cache.get(Cache.STYLES)
    cache.set(Cache.STYLES, [json.dumps(style) for style in styles])
    try:
        yield
    finally:
        cache.set(Cache.STYLES, saved)


def _prompt_styles(_controller: 'AppController') -> QWidget:
    # pylint: disable=import-outside-toplevel,protected-access
    from src.ui.window.prompt_style_window import PromptStyleWindow
    window = PromptStyleWindow(save_enabled=True)
    window._style_list.setCurrentRow(0)
    return window


def _login(_controller: 'AppController') -> QWidget:
    # pylint: disable=import-outside-toplevel
    from src.ui.modal.login_modal import LoginModal
    return LoginModal(lambda _user, _password: None)


def _new_image(_controller: 'AppController') -> QWidget:
    # pylint: disable=import-outside-toplevel
    from src.ui.modal.new_image_modal import NewImageModal
    return NewImageModal(512, 512)


def _animation_save(_controller: 'AppController') -> QWidget:
    # pylint: disable=import-outside-toplevel
    from src.ui.modal.animation_save_modal import AnimationSaveModal
    return AnimationSaveModal()


def _color_dialog(_controller: 'AppController') -> QWidget:
    # pylint: disable=import-outside-toplevel
    from src.ui.modal.color_dialog import ColorDialog
    dialog = ColorDialog()
    start = QColor('#3a7bd5')
    dialog.selected_color = QColor('#e07a3a')
    dialog.comparison.set_original(start)
    dialog.comparison.set_color(dialog.selected_color)
    return dialog


def _layout_name(_controller: 'AppController') -> QWidget:
    # pylint: disable=import-outside-toplevel
    from src.ui.modal.layout_name_modal import LayoutNameModal
    return LayoutNameModal('Save layout', 'Layout 1')


@contextmanager
def _saved_layouts() -> Iterator[None]:
    # pylint: disable=import-outside-toplevel
    from src.ui.window import saved_layouts
    names = ('Inpainting', 'Painting', 'Wide monitor')
    existing = set(saved_layouts.layout_names())
    for name in names:
        if name not in existing:
            saved_layouts.save_layout(name, '')
    try:
        yield
    finally:
        for name in names:
            if name not in existing:
                saved_layouts.delete_layout(name)


def _manage_layouts(_controller: 'AppController') -> QWidget:
    # pylint: disable=import-outside-toplevel
    from src.ui.modal.manage_layouts_modal import ManageLayoutsModal
    return ManageLayoutsModal(lambda _name: None)


def window_scenes(controller: 'AppController') -> list[WindowScene]:
    """Returns every secondary window scene for a mock-mode AppController, in capture order."""
    return [
        WindowScene('message_error', _error_box),
        WindowScene('message_warning_reminder', _warning_box),
        WindowScene('message_confirm', _confirm_box),
        WindowScene('message_confirm_remember', _confirm_remember_box),
        WindowScene('message_confirm_discard', _discard_box),
        WindowScene('message_bug_report', _bug_report_box),
        WindowScene('new_image', _new_image),
        WindowScene('resize_canvas', _resize_canvas, resizable=True),
        WindowScene('image_scale_basic', lambda c: _image_scale(c, False)),
        WindowScene('image_scale_sd_upscaling', lambda c: _image_scale(c, True), context=_sd_upscaling_cache),
        WindowScene('animation_save', _animation_save),
        WindowScene('filter_blur', lambda c: _filter_modal(c, 'blur'), resizable=True),
        WindowScene('filter_rgb_color_balance', lambda c: _filter_modal(c, 'rgb_color_balance'), resizable=True),
        WindowScene('filter_invert', lambda c: _filter_modal(c, 'invert'), resizable=True),
        WindowScene('color_dialog', _color_dialog, resizable=True),
        WindowScene('layout_name', _layout_name),
        WindowScene('manage_layouts', _manage_layouts, context=_saved_layouts),
        WindowScene('generator_setup', _generator_setup, lambda _w: fractional_size(), resizable=True),
        WindowScene('lora_models', _lora_window, resizable=True, full_content=True),
        WindowScene('prompt_styles', _prompt_styles, resizable=True, context=_prompt_styles_cache),
        WindowScene('login', _login),
        *_settings_scenes(controller),
    ]

