"""Interface for providing image generation capabilities."""
from typing import List, Dict, Optional, Any

from PIL import Image, ImageFilter
from PySide6.QtCore import QPoint, QRect, QSize, Signal, QTimer, QObject
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.image.layers.image_stack import ImageStack
from src.ui.layout.draggable_tabs.tab import Tab
from src.ui.modal.modal_utils import show_error_dialog
from src.ui.modal.settings_modal import SettingsModal
from src.ui.panel.generators.generator_panel import GeneratorPanel
from src.ui.window.main_window import MainWindow
from src.util.application_state import AppStateTracker, APP_STATE_LOADING, APP_STATE_EDITING
from src.util.async_task import AsyncTask
from src.util.menu_builder import MenuBuilder
from src.util.shared_constants import EDIT_MODE_INPAINT
from src.util.visual.pil_image_utils import pil_image_to_qimage, qimage_to_pil_image, pil_image_scaling

# The QCoreApplication.translate context for strings in this file
TR_ID = 'controller.image_generation.image_generator'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


GENERATE_ERROR_TITLE_UNEXPECTED = _tr('Inpainting failure')
GENERATE_ERROR_TITLE_NO_IMAGE = _tr('Save failed')
GENERATE_ERROR_TITLE_EXISTING_OP = _tr('Failed')
GENERATE_ERROR_MESSAGE_EXISTING_OP = _tr('Existing image generation operation not yet finished, wait a little longer.')


class ImageGenerator(MenuBuilder):
    """Interface for providing image generation capabilities."""

    # Used to emit additional information when anything goes wrong with an active generator.

    def __init__(self, window: MainWindow, image_stack: ImageStack) -> None:
        super().__init__()
        self._window = window
        self._image_stack = image_stack
        self._generated_images: List[QImage] = []

        class _SignalObject(QObject):
            status_signal = Signal(str)
        self._signal_object = _SignalObject()

    @property
    def status_signal(self) -> Signal:
        """Used to emit additional information when anything goes wrong with an active generator."""
        return self._signal_object.status_signal

    def get_display_name(self) -> str:
        """Returns a display name identifying the generator."""
        raise NotImplementedError()

    def get_description(self) -> str:
        """Returns an extended description of this generator."""
        raise NotImplementedError()

    def get_preview_image(self) -> QImage:
        """Returns a preview image for this generator."""
        raise NotImplementedError()

    def get_setup_text(self) -> str:
        """Returns a rich text description of how to set up this generator."""
        raise NotImplementedError()

    def is_available(self) -> bool:
        """Returns whether the generator is supported on the current system."""
        raise NotImplementedError()

    def configure_or_connect(self) -> bool:
        """Handles any required steps necessary to configure the generator, install required components, and/or
           connect to required external services, returning whether the process completed correctly."""
        raise NotImplementedError()

    def get_extra_tabs(self) -> List[Tab]:
        """Returns any extra tabs that the generator will add to the main window."""
        return []

    def disconnect_or_disable(self) -> None:
        """Closes any connections, unloads models, or otherwise turns off this generator."""
        raise NotImplementedError()

    def init_settings(self, settings_modal: SettingsModal) -> None:
        """Updates a settings modal to add settings relevant to this generator."""

    def refresh_settings(self, settings_modal: SettingsModal) -> None:
        """Reloads current values for this generator's settings, and updates them in the settings modal."""

    def update_settings(self, changed_settings: dict[str, Any]) -> None:
        """Applies any changed settings from a SettingsModal that are relevant to the image generator and require
           special handling."""

    def unload_settings(self, settings_modal: SettingsModal) -> None:
        """Unloads this generator's settings from the settings modal."""

    def get_control_panel(self) -> Optional[GeneratorPanel]:
        """Returns a widget with inputs for controlling this generator."""
        raise NotImplementedError()

    def upscale(self, new_size: QSize) -> bool:
        """Optionally upscale using a custom upscaler, returning whether upscaling was attempted."""
        return False

    def generate(self,
                 status_signal: Signal,
                 source_image: Optional[QImage] = None,
                 mask_image: Optional[QImage] = None) -> None:
        """Generates new images. Image size, image count, prompts, etc. should be loaded from AppConfig as needed.
        Implementations should call self._cache_generated_image to pass back each generated image.

        Parameters
        ----------
        status_signal : Signal[dict]
            Signal to emit when status updates are available. Expected keys are 'seed' and 'progress'.
        source_image : QImage, optional
            Image used as a basis for the edited image.
        mask_image : QImage, optional
            Mask marking edited image region.
        """
        raise NotImplementedError()

    def start_and_manage_image_generation(self) -> None:
        """Start inpainting/image editing based on the current state of the UI."""
        assert self._window is not None
        cache = Cache()
        self._generated_images.clear()

        source_selection = self._image_stack.qimage_generation_area_content()
        inpaint_image = source_selection.copy()

        # If necessary, scale image and mask to match the image generation size.
        generation_size = cache.get(Cache.GENERATION_SIZE)
        if inpaint_image.size() != generation_size:
            inpaint_image = pil_image_scaling(inpaint_image, generation_size)

        if cache.get(Cache.EDIT_MODE) == EDIT_MODE_INPAINT:
            inpaint_mask = self._image_stack.selection_layer.mask_image
            if inpaint_mask.size() != generation_size:
                inpaint_mask = pil_image_scaling(inpaint_mask, generation_size)

            blurred_mask = qimage_to_pil_image(inpaint_mask).filter(ImageFilter.GaussianBlur())
            blurred_alpha_mask = pil_image_to_qimage(blurred_mask)
            composite_base = inpaint_image.copy()
            base_painter = QPainter(composite_base)
            base_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
            base_painter.drawImage(QPoint(), blurred_alpha_mask)
            base_painter.end()
        else:
            inpaint_mask = None
            composite_base = None

        class _AsyncInpaintTask(AsyncTask):
            status_signal = Signal(dict)
            error_signal = Signal(Exception)

            def signals(self) -> List[Signal]:
                return [self.status_signal, self.error_signal]

        def _do_inpaint(status_signal: Signal, error_signal: Signal,
                        image=inpaint_image,
                        mask=inpaint_mask) -> None:
            try:
                self.generate(status_signal, image, mask)
            except (IOError, ValueError, RuntimeError) as err:
                error_signal.emit(err)

        inpaint_task = _AsyncInpaintTask(_do_inpaint)

        def handle_error(err: BaseException) -> None:
            """Close sample selector and show an error popup if anything goes wrong."""
            assert self._window is not None
            self._window.set_image_selector_visible(False)
            show_error_dialog(self._window, GENERATE_ERROR_TITLE_UNEXPECTED, err)

        def _finished():
            assert self._window is not None
            self._window.set_is_loading(False)
            inpaint_task.error_signal.disconnect(handle_error)
            inpaint_task.status_signal.disconnect(self._apply_status_update)
            inpaint_task.finish_signal.disconnect(_finished)
            for idx, image in enumerate(self._generated_images):
                if image.isNull():
                    continue
                if cache.get(Cache.EDIT_MODE) == EDIT_MODE_INPAINT:
                    assert composite_base is not None
                    assert composite_base.size() == image.size()
                    painter = QPainter(image)
                    painter.drawImage(QPoint(), composite_base)
                    painter.end()
                self._window.load_sample_preview(image, idx)

        inpaint_task.error_signal.connect(handle_error)
        inpaint_task.status_signal.connect(self._apply_status_update)
        inpaint_task.finish_signal.connect(_finished)

        self._window.set_image_selector_visible(True)
        AppStateTracker.set_app_state(APP_STATE_LOADING)
        inpaint_task.start()

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
            if Cache().get(Cache.EDIT_MODE) == 'Inpaint':
                inpaint_mask = self._image_stack.selection_layer.mask_image
                painter = QPainter(image)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
                painter.drawImage(QRect(QPoint(0, 0), image.size()), inpaint_mask)
                painter.end()
            layer = self._image_stack.active_layer
            self._image_stack.set_generation_area_content(image, layer)
            AppStateTracker.set_app_state(APP_STATE_EDITING)

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

    def _apply_status_update(self, status_dict: Dict[str, str]) -> None:
        """Show status updates in the UI."""
        assert self._window is not None
        if 'seed' in status_dict:
            Cache().set(Cache.LAST_SEED, str(status_dict['seed']))
        if 'progress' in status_dict:
            self._window.set_loading_message(status_dict['progress'])
