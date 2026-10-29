"""Interface for providing image generation capabilities."""
import logging
from abc import ABC, abstractmethod
from typing import Optional, Any

from PySide6.QtCore import QSize, Signal, QTimer, QObject, SignalInstance
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWidget

from src.config.cache import Cache
from src.controller.image_generation.generation_session import GenerationSession
from src.image.layers.image_stack import ImageStack
from src.image.layers.image_stack_utils import scale_all_layers
from src.ui.modal.settings_modal import SettingsModal
from src.ui.window.main_window import MainWindow
from src.util.menu_builder import MenuBuilder
from src.util.shared_constants import EDIT_MODE_INPAINT, PIL_SCALING_MODES
from src.util.visual.pil_image_utils import pil_image_scaling

logger = logging.getLogger(__name__)


class ImageGenerator(MenuBuilder, ABC):
    """Interface for providing image generation capabilities."""

    # Used to emit additional information when anything goes wrong with an active generator.

    def __init__(self, window: MainWindow, image_stack: ImageStack) -> None:
        super().__init__()
        self._window = window
        self._image_stack = image_stack

        class _SignalObject(QObject):
            status_signal = Signal(str)
        self._signal_object = _SignalObject()

    @property
    def _session(self) -> GenerationSession:
        return self._window.generation_session

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
            mode is text-to-image and there are no ControlNet units using the generation area.
        mask_image : QImage, optional
            Mask marking the edited image region.
        """

    def get_generation_inputs(self) -> tuple[QImage, Optional[QImage]]:
        """Returns the image and inpainting mask that image generation passes to `generate`.

        Both are taken from the generation area and scaled to the generation resolution. The mask is None outside of
        inpainting mode.
        """
        generation_resolution = Cache().get(Cache.GENERATION_SIZE)
        image = self._image_stack.qimage_generation_area_content().copy()
        if image.size() != generation_resolution:
            image = pil_image_scaling(image, generation_resolution)
        if Cache().get(Cache.EDIT_MODE) != EDIT_MODE_INPAINT:
            return image, None
        mask = self._image_stack.selection_layer.mask_image
        if mask.size() != generation_resolution:
            mask = pil_image_scaling(mask, generation_resolution)
        return image, mask

    def start_and_manage_image_generation(self) -> None:
        """Start inpainting/image editing based on the current state of the UI."""
        if self._session.generating:
            logger.error('Caught and ignored duplicate image generation request.')
            return
        image, mask = self.get_generation_inputs()
        paste_mask = self.get_paste_mask() if mask is not None else None
        self._session.generate(self.generate, image, mask, paste_mask)

    def get_paste_mask(self) -> QImage:
        """Returns the generation-area mask whose alpha clips a generated image when it is applied.

        Generators whose backend blends results through a blurred mask override this to cover the blur's reach.
        """
        return self._image_stack.selection_layer.mask_image

    def _load_generated_image_for_selection(self, index: int) -> None:
        """Shows the generated image at `index` once it arrives. Backends route extra results here by index."""
        self._session.deliver_result(index)

    def _cache_generated_image(self, image: QImage, index: int) -> None:
        self._session.store_result(image, index)
        # Load in main thread:
        QTimer.singleShot(0, self._session, lambda: self._load_generated_image_for_selection(index))
