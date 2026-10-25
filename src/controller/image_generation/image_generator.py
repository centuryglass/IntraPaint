"""Interface for providing image generation capabilities."""
import logging
from abc import ABC, abstractmethod
from typing import Optional, Any

from PySide6.QtCore import QPoint, QRect, QSize, Signal, QTimer, QObject, SignalInstance
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication, QWidget

from src.config.cache import Cache
from src.image.layers.image_stack import ImageStack
from src.image.layers.image_stack_utils import scale_all_layers
from src.ui.modal.modal_utils import show_error_dialog
from src.ui.modal.settings_modal import SettingsModal
from src.ui.window.main_window import MainWindow
from src.util.application_state import AppStateTracker, APP_STATE_LOADING
from src.util.async_task import AsyncTask
from src.util.menu_builder import MenuBuilder
from src.util.shared_constants import EDIT_MODE_INPAINT, PIL_SCALING_MODES
from src.util.visual.pil_image_utils import pil_image_scaling

# The QCoreApplication.translate context for strings in this file
TR_ID = 'controller.image_generation.image_generator'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


GENERATE_ERROR_TITLE_UNEXPECTED = _tr('Inpainting failure')
GENERATE_ERROR_TITLE_NO_IMAGE = _tr('Save failed')
GENERATE_ERROR_TITLE_EXISTING_OP = _tr('Failed')
GENERATE_ERROR_MESSAGE_EXISTING_OP = _tr('Existing image generation operation not yet finished, wait a little longer.')

logger = logging.getLogger(__name__)


class ImageGenerator(MenuBuilder, ABC):
    """Interface for providing image generation capabilities."""

    # Used to emit additional information when anything goes wrong with an active generator.

    def __init__(self, window: MainWindow, image_stack: ImageStack) -> None:
        super().__init__()
        self._window = window
        self._image_stack = image_stack
        self._generated_images: list[QImage] = []
        self._generating = False

        class _SignalObject(QObject):
            status_signal = Signal(str)
        self._signal_object = _SignalObject()

    @property
    def status_signal(self) -> SignalInstance:
        """Used to emit additional information when anything goes wrong with an active generator."""
        return self._signal_object.status_signal

    @abstractmethod
    def get_display_name(self) -> str:
        """Returns a display name identifying the generator."""

    @abstractmethod
    def get_description(self) -> str:
        """Returns an extended description of this generator."""

    @abstractmethod
    def get_preview_image(self) -> QImage:
        """Returns a preview image for this generator."""

    @abstractmethod
    def get_setup_text(self) -> str:
        """Returns a rich text description of how to set up this generator."""

    @abstractmethod
    def is_available(self) -> bool:
        """Returns whether the generator is supported on the current system."""


    @abstractmethod
    def configure_or_connect(self) -> bool:
        """Handles any required steps necessary to configure the generator, install required components, and/or
           connect to required external services, returning whether the process completed correctly."""

    def get_controlnet_panel(self) -> Optional[QWidget]:
        """Returns the panel the main window's ControlNet dock shows, or None if the generator has no ControlNet."""
        return None

    @abstractmethod
    def disconnect_or_disable(self) -> None:
        """Closes any connections, unloads models, or otherwise turns off this generator."""

    @abstractmethod
    def init_settings(self, settings_modal: SettingsModal) -> None:
        """Updates a settings modal to add settings relevant to this generator."""

    @abstractmethod
    def refresh_settings(self, settings_modal: SettingsModal) -> None:
        """Reloads current values for this generator's settings, and updates them in the settings modal."""

    @abstractmethod
    def update_settings(self, changed_settings: dict[str, Any]) -> None:
        """Applies any changed settings from a SettingsModal that are relevant to the image generator and require
           special handling."""

    @abstractmethod
    def unload_settings(self, settings_modal: SettingsModal) -> None:
        """Unloads this generator's settings from the settings modal."""

    @abstractmethod
    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a widget with inputs for controlling this generator."""

    def upscale(self, new_size: QSize) -> bool:
        """Optionally upscale using a custom upscaler, returning whether upscaling was attempted."""
        upscale_mode = Cache().get(Cache.SCALING_MODE)
        if upscale_mode in PIL_SCALING_MODES:
            scale_all_layers(self._image_stack, new_size.width(), new_size.height(), PIL_SCALING_MODES[upscale_mode])
        else:
            scale_all_layers(self._image_stack, new_size.width(), new_size.height())
        return True


    @abstractmethod
    def generate(self,
                 status_signal: SignalInstance,
                 source_image: QImage,
                 mask_image: Optional[QImage] = None) -> None:
        """Generates new images. Image size, image count, prompts, etc. should be loaded from AppConfig as needed.
        Implementations should call self._cache_generated_image to pass back each generated image.

        Parameters
        ----------
        status_signal : SignalInstance[dict]
            Signal to emit when status updates are available. Expected keys are 'seed' and 'progress'.
        source_image : QImage
            Image to potentially use as a basis for the created or edited image.  This will be ignored if the editing
            mode is text-to-image and there are no ControlNet units using the image generation area.
        mask_image : QImage, optional
            Mask marking the edited image region.
        """

    def get_generation_inputs(self) -> tuple[QImage, Optional[QImage]]:
        """Returns the image and inpainting mask that image generation passes to `generate`.

        Both are taken from the generation area and scaled to the generation size. The mask is None outside of
        inpainting mode.
        """
        generation_size = Cache().get(Cache.GENERATION_SIZE)
        image = self._image_stack.qimage_generation_area_content().copy()
        if image.size() != generation_size:
            image = pil_image_scaling(image, generation_size)
        if Cache().get(Cache.EDIT_MODE) != EDIT_MODE_INPAINT:
            return image, None
        mask = self._image_stack.selection_layer.mask_image
        if mask.size() != generation_size:
            mask = pil_image_scaling(mask, generation_size)
        return image, mask

    def start_and_manage_image_generation(self) -> None:
        """Start inpainting/image editing based on the current state of the UI."""
        if self._generating:
            logger.error('Caught and ignored duplicate image generation request.')
            return
        assert self._window is not None
        cache = Cache()
        self._generated_images.clear()
        self._generating = True

        inpaint_image, inpaint_mask = self.get_generation_inputs()
        # Previews show the unscaled source outside the mask that clips them when applied, so they match the result.
        paste_mask = self.get_paste_mask() if inpaint_mask is not None else None
        if paste_mask is not None:
            composite_base = inpaint_image.copy()
            base_painter = QPainter(composite_base)
            base_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
            base_painter.drawImage(QRect(QPoint(), composite_base.size()), paste_mask)
            base_painter.end()
        else:
            composite_base = None

        class _AsyncInpaintTask(AsyncTask):
            status_signal = Signal(dict)
            error_signal = Signal(Exception)

            def signals(self) -> list[SignalInstance]:
                return [self.status_signal, self.error_signal]

        def _do_inpaint(status_signal: SignalInstance, error_signal: SignalInstance,
                        image=inpaint_image,
                        mask=inpaint_mask) -> None:
            try:
                self.generate(status_signal, image, mask)
            except (IOError, ValueError, RuntimeError) as err:
                error_signal.emit(err)
            except Exception as unexpected_err:
                logger.error(f'Unexpected error: {unexpected_err}')
                error_signal.emit(unexpected_err)

        inpaint_task = _AsyncInpaintTask(_do_inpaint)

        def handle_error(err: BaseException) -> None:
            """Close sample selector and show an error popup if anything goes wrong."""
            assert self._window is not None
            self._window.set_image_selector_visible(False)
            self._window.set_is_loading(False)
            self._generating = False
            show_error_dialog(self._window, GENERATE_ERROR_TITLE_UNEXPECTED, err)

        def _finished():
            assert self._window is not None
            self._window.set_is_loading(False)
            self._generating = False
            # Disconnecting by slot would make this closure refer to itself, a cycle that holds the task:
            for signal in (inpaint_task.error_signal, inpaint_task.status_signal, inpaint_task.finish_signal):
                signal.disconnect()
            expected_count = Cache().get(Cache.BATCH_COUNT) * Cache().get(Cache.BATCH_SIZE)
            for idx, image in enumerate(self._generated_images):
                if image.isNull() or idx >= expected_count:
                    continue
                if cache.get(Cache.EDIT_MODE) == EDIT_MODE_INPAINT:
                    assert composite_base is not None
                    if composite_base.size() == image.size():
                        painter = QPainter(image)
                        painter.drawImage(QPoint(), composite_base)
                        painter.end()
                self._window.load_sample_preview(image, idx)

        inpaint_task.error_signal.connect(handle_error)
        inpaint_task.status_signal.connect(self._apply_status_update)
        inpaint_task.finish_signal.connect(_finished)

        self._window.show_generated_options(paste_mask)
        AppStateTracker.set_app_state(APP_STATE_LOADING)
        inpaint_task.start()

    def get_paste_mask(self) -> QImage:
        """Returns the generation-area mask whose alpha clips a generated image when it is applied.

        Generators whose backend blends results through a blurred mask override this to cover the blur's reach.
        """
        return self._image_stack.selection_layer.mask_image

    def _load_generated_image_for_selection(self, index: int) -> None:
        assert len(self._generated_images) > index
        image = self._generated_images[index]
        if not image.isNull():
            self._window.load_sample_preview(image, index)

    def _cache_generated_image(self, image: QImage, index: int) -> None:
        while len(self._generated_images) < index:
            self._generated_images.append(QImage())
        if len(self._generated_images) > index:
            self._generated_images.pop(index)
        self._generated_images.insert(index, image)
        # Load in main thread:
        QTimer.singleShot(0, self._window, lambda: self._load_generated_image_for_selection(index))

    def _apply_status_update(self, status_dict: dict[str, str]) -> None:
        """Show status updates in the UI."""
        assert self._window is not None
        if 'seed' in status_dict:
            Cache().set(Cache.LAST_SEED, str(status_dict['seed']))
        if 'subseed' in status_dict:
            Cache().set(Cache.WEBUI_LAST_SUBSEED, str(status_dict['subseed']))
        if 'progress' in status_dict:
            self._window.set_loading_message(status_dict['progress'])
