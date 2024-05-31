"""
BaseController coordinates primary application functionality across all operation modes. Each image generation and
editing method supported by IntraPaint should have its own BaseController subclass.
"""
import os
import sys
import re
from typing import Optional, Callable, Any
from argparse import Namespace
from PIL import Image, ImageFilter, UnidentifiedImageError, PngImagePlugin
from PyQt5.QtWidgets import QApplication, QMessageBox, QMainWindow
from PyQt5.QtCore import QObject, QThread, QSize, pyqtSignal
from PyQt5.QtGui import QScreen, QImage
try:
    import qdarktheme
except ImportError:
    qdarktheme = None
try:
    import qt_material
except ImportError:
    qt_material = None

from src.config.application_config import AppConfig
from src.image.layer_stack import LayerStack

from src.ui.window.main_window import MainWindow
from src.ui.modal.new_image_modal import NewImageModal
from src.ui.modal.resize_canvas_modal import ResizeCanvasModal
from src.ui.modal.image_scale_modal import ImageScaleModal
from src.ui.modal.modal_utils import show_error_dialog, request_confirmation, open_image_file
from src.ui.modal.settings_modal import SettingsModal
from src.ui.util.screen_size import screen_size

from src.util.validation import assert_type
# Optional spacenav support:
try:
    from src.controller.spacenav_manager import SpacenavManager
except ImportError as spacenav_err:
    print(f'spaceMouse support not enabled: {spacenav_err}')
    SpacenavManager = None

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

METADATA_PARAMETER_KEY = 'parameters'
INPAINT_MODE = 'Inpaint'


class BaseInpaintController:
    """Shared base class for managing inpainting.

    At a bare minimum, subclasses will need to implement self._inpaint.
    """

    def __init__(self, args: Namespace) -> None:
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
        self._config = AppConfig()
        self._adjust_config_defaults()
        self._config.apply_args(args)

        self._layer_stack = LayerStack(self._config.get(AppConfig.DEFAULT_IMAGE_SIZE),
                                       self._config.get(AppConfig.EDIT_SIZE),
                                       self._config.get(AppConfig.MIN_EDIT_SIZE),
                                       self._config.get(AppConfig.MAX_EDIT_SIZE),
                                       self._config)
        self._init_image = args.init_image

        self._window: Optional[QMainWindow] = None
        self._nav_manager: Optional[SpacenavManager] = None
        self._worker: Optional[QObject] = None
        self._metadata: Optional[dict[str, Any]] = None

        self._thread = None

    def _adjust_config_defaults(self):
        """no-op, override to adjust config before data initialization."""

    def init_settings(self, unused_settings_modal: SettingsModal) -> bool:
        """ 
        Function to override initialize a SettingsModal with implementation-specific settings. 
        Return
        ------
        bool
            Whether settings were initialized. This will always be False unless overridden.
        """
        return False

    def refresh_settings(self, settings_modal: SettingsModal):
        """
        Unimplemented function used to update a SettingsModal to reflect any changes.  This should only be called in
        a child class instance that previously returned true after init_settings was called.

        Parameters
        ----------
        settings_modal : SettingsModal
        """
        raise NotImplementedError('refresh_settings not implemented!')

    def update_settings(self, changed_settings: dict):
        """
        Unimplemented function used to apply changed settings from a SettingsModal.  This should only be called in
        a child class instance that previously returned true after init_settings was called.

        Parameters
        ----------
        changed_settings : dict
            Set of changes loaded from a SettingsModal.
        """
        raise NotImplementedError('update_settings not implemented!')

    def window_init(self):
        """Initialize and show the main application window."""
        self._window = MainWindow(self._config, self._layer_stack, self)
        if self._fixed_window_size is not None:
            size = self._fixed_window_size
            self._window.setGeometry(0, 0, size.width(), size.height())
            self._window.setMaximumSize(self._fixed_window_size)
            self._window.setMinimumSize(self._fixed_window_size)
        else:
            size = screen_size(self._window)
            self._window.setGeometry(0, 0, size.width(), size.height())
            self._window.setMaximumSize(size)
        self.fix_styles()
        if self._init_image is not None:
            print('loading init image:')
            self.load_image(self._init_image)
        self._window.show()

    def fix_styles(self) -> None:
        """Update application styling based on theme configuration, UI configuration, and available theme modules."""
        self._app.setStyle(self._config.get('style'))
        theme = self._config.get(AppConfig.THEME)
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
            print(f'Failed to load theme {theme}')
        font = self._app.font()
        font.setPointSize(self._config.get(AppConfig.FONT_POINT_SIZE))
        self._app.setFont(font)

    def start_app(self) -> None:
        """Start the application after performing any additional required setup steps."""
        self.window_init()

        # Configure support for spacemouse panning, if relevant:
        if SpacenavManager is not None:
            self._nav_manager = SpacenavManager(self._window, self._layer_stack)
            self._nav_manager.start_thread()

        self._app.exec_()
        sys.exit()

    # File IO handling:
    def new_image(self) -> None:
        """Open a new image creation modal."""
        default_size = self._config.get(AppConfig.DEFAULT_IMAGE_SIZE)
        image_modal = NewImageModal(default_size.width(), default_size.height())
        image_size = image_modal.show_image_modal()
        if image_size and (not self._layer_stack.has_image or request_confirmation(self._window,
                                                                                   NEW_IMAGE_CONFIRMATION_TITLE,
                                                                                   NEW_IMAGE_CONFIRMATION_MESSAGE)):
            new_image = Image.new('RGB', (image_size.width(), image_size.height()), color='white')
            self._layer_stack.set_image(new_image)
            for i in range(1, self._layer_stack.count):
                self._layer_stack.get_layer(i).clear()
            self._metadata = None

    def save_image(self, file_path: Optional[str] = None) -> None:
        """Open a save dialog, and save the edited image to disk, preserving any metadata."""
        if not self._layer_stack.has_image:
            show_error_dialog(self._window, SAVE_ERROR_TITLE, SAVE_ERROR_MESSAGE_NO_IMAGE)
            return
        try:
            if not isinstance(file_path, str):
                file_path, file_selected = open_image_file(self._window, mode='save',
                                                           selected_file=self._config.get(AppConfig.LAST_FILE_PATH))
                if not file_path or not file_selected:
                    return
            assert_type(file_path, str)
            image = self._layer_stack.pil_image(saved_only=True)
            if self._metadata is not None:
                info = PngImagePlugin.PngInfo()
                for key in self._metadata:
                    try:
                        info.add_itxt(key, self._metadata[key])
                    except AttributeError as png_err:
                        # Encountered some sort of image metadata that PIL knows how to read but not how to write.
                        # I've seen this a few times, mostly with images edited in Krita. This data isn't important to
                        # me, so it'll just be discarded. If it's important to you, open a GitHub issue with details or
                        # submit a PR, and I'll take care of it.
                        print(f'failed to preserve "{key}" in metadata: {png_err}')
                image.save(file_path, 'PNG', pnginfo=info)
            else:
                image.save(file_path, 'PNG')
            self._config.set(AppConfig.LAST_FILE_PATH, file_path)
        except (IOError, TypeError) as save_err:
            show_error_dialog(self._window, SAVE_ERROR_TITLE, str(save_err))
            raise save_err

    def load_image(self, file_path: Optional[str] = None) -> None:
        """Open a loading dialog, then load the selected image for editing."""
        if file_path is None:
            file_path, file_selected = open_image_file(self._window)
            if not file_path or not file_selected:
                return
        assert_type(file_path, str)
        try:
            image = Image.open(file_path)
            # try and load metadata:
            if hasattr(image, 'info') and image.info is not None:
                self._metadata = image.info
            else:
                self._metadata = None
            if METADATA_PARAMETER_KEY in self._metadata:
                param_str = self._metadata[METADATA_PARAMETER_KEY]
                match = re.match(r'^(.*\n?.*)\nSteps: (\d+), Sampler: (.*), CFG scale: (.*), Seed: (.+), Size.*',
                                 param_str)
                if match:
                    prompt = match.group(1)
                    negative = ''
                    steps = int(match.group(2))
                    sampler = match.group(3)
                    cfg_scale = float(match.group(4))
                    seed = int(match.group(5))
                    divider_match = re.match('^(.*)\nNegative prompt: (.*)$', prompt)
                    if divider_match:
                        prompt = divider_match.group(1)
                        negative = divider_match.group(2)
                    print('Detected saved image gen data, applying to UI')
                    try:
                        self._config.set(AppConfig.PROMPT, prompt)
                        self._config.set(AppConfig.NEGATIVE_PROMPT, negative)
                        self._config.set(AppConfig.SAMPLING_STEPS, steps)
                        self._config.set(AppConfig.SAMPLING_METHOD, sampler)
                        self._config.set(AppConfig.GUIDANCE_SCALE, cfg_scale)
                        self._config.set(AppConfig.SEED, seed)
                    except (TypeError, RuntimeError) as err:
                        print(f'Failed to load image gen data from metadata: {err}')
                else:
                    print('Warning: image parameters do not match expected patterns, cannot be used. '
                          f'parameters:{param_str}')
            image = QImage(file_path)
            self._layer_stack.set_image(image)
            self._config.set(AppConfig.LAST_FILE_PATH, file_path)
        except UnidentifiedImageError as err:
            show_error_dialog(self._window, LOAD_ERROR_TITLE, err)
            return

    def reload_image(self) -> None:
        """Reload the edited image from disk after getting confirmation from a confirmation dialog."""
        file_path = self._config.get(AppConfig.LAST_FILE_PATH)
        if file_path == '':
            show_error_dialog(self._window, RELOAD_ERROR_TITLE, RELOAD_ERROR_MESSAGE_NO_IMAGE)
            return
        if not os.path.isfile(file_path):
            show_error_dialog(self._window, RELOAD_ERROR_TITLE, f'Image path "{file_path}" is not a valid file.')
            return
        if not self._layer_stack.has_image or request_confirmation(self._window,
                                                                   RELOAD_CONFIRMATION_TITLE,
                                                                   RELOAD_CONFIRMATION_MESSAGE):
            self.load_image(file_path)

    def update_metadata(self, show_messagebox: bool = True) -> None:
        """
        Adds image editing parameters from config to the image metadata, in a format compatible with the A1111
        stable-diffusion webui. Parameters will be applied to the image file when save_image is called.

        Parameters
        ----------
        show_messagebox: bool
            If true, show a messagebox after the update to let the user know what happened.
        """
        prompt = self._config.get(AppConfig.PROMPT)
        negative = self._config.get(AppConfig.NEGATIVE_PROMPT)
        steps = self._config.get(AppConfig.SAMPLING_STEPS)
        sampler = self._config.get(AppConfig.SAMPLING_METHOD)
        cfg_scale = self._config.get(AppConfig.GUIDANCE_SCALE)
        seed = self._config.get(AppConfig.SEED)
        params = f'{prompt}\nNegative prompt: {negative}\nSteps: {steps}, Sampler: {sampler}, CFG scale:' + \
                 f'{cfg_scale}, Seed: {seed}, Size: 512x512'
        if self._metadata is None:
            self._metadata = {}
        self._metadata[METADATA_PARAMETER_KEY] = params
        if show_messagebox:
            message_box = QMessageBox(self)
            message_box.setWindowTitle(METADATA_UPDATE_TITLE)
            message_box.setText(METADATA_UPDATE_MESSAGE)
            message_box.setStandardButtons(QMessageBox.Ok)
            message_box.exec()

    def resize_canvas(self) -> None:
        """Crop or extend the edited image without scaling its contents based on user input into a popup modal."""
        if not self._layer_stack.has_image:
            show_error_dialog(self._window, RESIZE_ERROR_TITLE, RESIZE_ERROR_MESSAGE_NO_IMAGE)
            return
        resize_modal = ResizeCanvasModal(self._layer_stack.q_image())
        new_size, offset = resize_modal.show_resize_modal()
        if new_size is None:
            return
        self._layer_stack.resize_canvas(new_size, offset.x(), offset.y())

    def scale_image(self) -> None:
        """Scale the edited image based on user input into a popup modal."""
        if not self._layer_stack.has_image:
            show_error_dialog(self._window, SCALING_ERROR_TITLE, SCALING_ERROR_MESSAGE_NO_IMAGE)
            return
        width = self._layer_stack.width
        height = self._layer_stack.height
        scale_modal = ImageScaleModal(width, height, self._config)
        new_size = scale_modal.show_image_modal()
        if new_size is not None:
            self._scale(new_size)

    def _scale(self, new_size: QSize) -> None:  # Override to allow alternate or external upscalers:
        width = self._layer_stack.width
        height = self._layer_stack.height
        if new_size is None or (new_size.width() == width and new_size.height() == height):
            return
        image = self._layer_stack.pil_image()
        if new_size.width() <= width and new_size.height() <= height:  # downscaling
            scale_mode = self._config.get(AppConfig.DOWNSCALE_MODE)
        else:
            scale_mode = self._config.get(AppConfig.UPSCALE_MODE)
        scaled_image = image.resize((new_size.width(), new_size.height()), scale_mode)
        self._layer_stack.set_image(scaled_image)

    def _start_thread(self, thread_worker: QObject, loading_text: Optional[str] = None) -> None:
        if self._thread is not None:
            raise RuntimeError('Tried to start a new async operation while the previous one is still running')
        self._window.set_is_loading(True, loading_text)
        self._thread = QThread()
        self._worker = thread_worker
        self._worker.moveToThread(self._thread)

        def clear_worker() -> None:
            """Clean up thread worker object on finish."""
            self._thread.quit()
            self._window.set_is_loading(False)
            self._worker.deleteLater()
            self._worker = None

        self._worker.finished.connect(clear_worker)
        self._thread.started.connect(self._worker.run)

        def clear_old_thread() -> None:
            """Cleanup async task thread on finish."""
            self._thread.deleteLater()
            self._thread = None

        self._thread.finished.connect(clear_old_thread)
        self._thread.start()

    # Image generation handling:
    def _inpaint(self,
                 selection: Optional[Image.Image],
                 mask: Optional[Image.Image],
                 save_image: Callable[[Image.Image, int], None],
                 status_signal: pyqtSignal) -> None:
        """Unimplemented method for handling image inpainting.

        Parameters
        ----------
        selection : PIL Image, optional
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

    def start_and_manage_inpainting(self) -> None:
        """Start inpainting/image editing based on the current state of the UI."""
        if not self._layer_stack.has_image:
            show_error_dialog(self._window, GENERATE_ERROR_TITLE_NO_IMAGE, GENERATE_ERROR_MESSAGE_NO_IMAGE)
            return
        if self._thread is not None:
            show_error_dialog(self._window, GENERATE_ERROR_TITLE_EXISTING_OP, GENERATE_ERROR_MESSAGE_EXISTING_OP)
            return
        upscale_mode = self._config.get(AppConfig.UPSCALE_MODE)
        downscale_mode = self._config.get(AppConfig.DOWNSCALE_MODE)

        def resize_image(pil_image: Image.Image, width: int, height: int) -> Image.Image:
            """Resize a PIL image using the appropriate scaling mode:"""
            if width == pil_image.width and height == pil_image.height:
                return pil_image
            if width > pil_image.width or height > pil_image.height:
                return pil_image.resize((width, height), upscale_mode)
            return pil_image.resize((width, height), downscale_mode)

        selection = self._layer_stack.pil_image_selection_content()

        # If sketch mode was used, write the sketch onto the image selection:
        inpaint_image = selection.copy()
        inpaint_mask = self._layer_stack.mask_layer.pil_mask_image

        # If necessary, scale image and mask to match the image generation size.
        generation_size = self._config.get(AppConfig.GENERATION_SIZE)
        if inpaint_image.width != generation_size.width() or inpaint_image.height != generation_size.height():
            inpaint_image = resize_image(inpaint_image, generation_size.width(), generation_size.height())
        if inpaint_mask.width != generation_size.width() or inpaint_mask.height != generation_size.height():
            inpaint_mask = resize_image(inpaint_mask, generation_size.width(), generation_size.height())

        do_inpaint = self._inpaint
        config = self._config

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
            self._window.set_sample_selector_visible(False)
            show_error_dialog(self._window, GENERATE_ERROR_TITLE_UNEXPECTED, err)

        worker.error_signal.connect(handle_error)
        worker.status_signal.connect(self._apply_status_update)

        def load_sample_preview(img: Image.Image, idx: int) -> None:
            """Apply image mask to inpainting results."""
            if config.get(AppConfig.EDIT_MODE) == INPAINT_MODE:
                def point_fn(p: int) -> int:
                    """Convert pixel to 1-bit."""
                    return 255 if p < 1 else 0

                mask_alpha = inpaint_mask.convert('L').point(point_fn).filter(ImageFilter.GaussianBlur())
                img = resize_image(img, selection.width, selection.height)
                mask_alpha = resize_image(mask_alpha, selection.width, selection.height)
                img = Image.composite(selection, img, mask_alpha)
            self._window.load_sample_preview(img, idx)

        worker.image_ready.connect(load_sample_preview)
        self._window.set_sample_selector_visible(True)
        self._start_thread(worker)

    def select_and_apply_sample(self, sample_image: Image.Image) -> None:
        """Apply an AI-generated image change to the edited image.

        Parameters
        ----------
        sample_image : PIL Image
            Data to be inserted into the edited image selection bounds.
        """
        if sample_image is not None and isinstance(sample_image, Image.Image):
            self._layer_stack.set_selection_content(sample_image)
