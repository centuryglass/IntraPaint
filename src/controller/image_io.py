"""
ImageIO owns opening and saving image files for the application.

- Shows the open and save dialogs, and the errors and data loss warnings around them.
- Holds the metadata and EXIF data of the open file, so a save writes back what a load read.
- Runs file writes on a worker thread, from copies of the edited data.
- Connects the `ImageStack` to image files in every supported format.

`AppController` keeps the File menu actions and delegates each one to the matching method here.
"""
import copy
import json
import logging
import os
import re
from typing import Optional, Any, Callable

from PIL import Image, UnidentifiedImageError, ExifTags
from PIL.ExifTags import IFD
from PySide6.QtCore import QSize, QEventLoop
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller.image_generation.image_generator import ImageGenerator
from src.controller.image_generation.null_generator import NullGenerator
from src.image.animation import load_frames_as_image, add_frame_layers, render_frames
from src.image.layers.image_stack import ImageStack
from src.image.open_raster import capture_ora_image, write_ora_snapshot, read_ora_image, ORA_FILE_EXTENSION
from src.image.recovery_files import RestoredDocument
from src.ui.modal.animation_save_modal import AnimationSaveModal, saved_animation_options
from src.ui.modal.modal_parent import modal_parent
from src.ui.modal.modal_utils import show_error_dialog, request_confirmation, open_image_file, open_image_layers, \
    show_warning_dialog
from src.util.application_state import AppStateTracker, APP_STATE_EDITING
from src.util.async_task import AsyncTask
from src.util.recent_files import add_recent_file
from src.util.visual.image_format_utils import save_image_with_metadata, save_image, load_image, \
    IMAGE_FORMATS_SUPPORTING_METADATA, IMAGE_FORMATS_SUPPORTING_ALPHA, IMAGE_FORMATS_SUPPORTING_PARTIAL_ALPHA, \
    METADATA_PARAMETER_KEY, IMAGE_WRITE_FORMATS, IMAGE_READ_FORMATS, IMAGE_FORMATS_WITH_FIXED_SIZE, \
    GREYSCALE_IMAGE_FORMATS, METADATA_COMMENT_KEY, PIL_WRITE_FORMATS, QIMAGE_WRITE_FORMATS, count_image_frames, \
    load_image_frames, ImageFrame, save_animation, AnimationSaveOptions, ANIMATION_WRITE_FORMATS, \
    ANIMATION_ONLY_FORMATS
from src.util.visual.image_utils import image_is_fully_opaque, image_has_partial_alpha, create_transparent_image

logger = logging.getLogger(__name__)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'controller.image_io'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


SAVE_ERROR_TITLE = _tr('Save failed')
LOAD_ERROR_TITLE = _tr('Open failed')
SAVE_ERROR_MESSAGE_UNKNOWN_ISSUE = _tr('Saving as "{file_path}" failed due to an unknown error, try saving in a'
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
RELOAD_CONFIRMATION_BUTTON = _tr('Discard and reload')
METADATA_UPDATE_TITLE = _tr('Metadata updated')
METADATA_UPDATE_MESSAGE = _tr('On save, current image generation parameters will be stored within the image')
LOAD_LAYER_ERROR_TITLE = _tr('Opening layers failed')
LOAD_LAYER_ERROR_MESSAGE = _tr('Could not open the following images: ')
LARGE_ANIMATION_TITLE = _tr('Open every frame?')
LARGE_ANIMATION_MESSAGE = _tr('{file_name} has {frame_count} frames. Opening each one as a layer will use about'
                              ' {size_gb:.1f} GB of memory.\n\nChoose "No" to open only the first frame.')
LARGE_ANIMATION_BUTTON = _tr('Open all frames')

# Decoded frame data, in bytes, above which opening an animation asks before loading every frame.
LARGE_ANIMATION_BYTES = 1024 ** 3
TITLE_CONFIRM_METADATA_INIT = _tr('Save image generation metadata?')
MESSAGE_CONFIRM_METADATA_INIT = _tr('No image metadata is cached, would you like to save image generation parameters to'
                                    ' this image?')
TITLE_CONFIRM_METADATA_UPDATE = _tr('Update image generation metadata?')
MESSAGE_CONFIRM_METADATA_UPDATE = _tr('Image generation parameters have changed, would you like this image to be saved'
                                      ' with the most recent values?')

# Upper limits of the animation save option ranges in cache_value_definitions.json:
ANIMATION_MAX_FRAME_MS = 60000
ANIMATION_MAX_LOOP_COUNT = 65535

# Warnings when saving images cause data loss:
LAYERS_NOT_SAVED_TITLE = _tr('Image saved without layer data')
LAYERS_NOT_SAVED_MESSAGE = _tr('To save layer data, images must be saved in .ora format. To save each layer as an'
                               ' animation frame, use one of the following formats: {animation_formats}')

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


class _MetadataEncoder(json.JSONEncoder):

    def default(self, o):
        """Convert byte strings to ASCII when serializing."""
        if isinstance(o, bytes):
            return o.decode()
        return super().default(o)


class ImageIO:
    """Opens and saves image files, and tracks the metadata of the open file.

    Everything here runs on the GUI thread. The only code that runs elsewhere is the file write that `_start_save`
    hands to a worker, which uses copies made beforehand.
    """

    def __init__(self, window: QWidget, image_stack: ImageStack,
                 get_generator: Callable[[], Optional[ImageGenerator]]) -> None:
        """Creates the helper.

        Parameters
        ----------
        window: QWidget
            Parent of every dialog, and the widget repainted around file dialogs.
        image_stack: ImageStack
            The image data to load into and save from.
        get_generator: Callable[[], Optional[ImageGenerator]]
            Returns the active image generator, which decides whether saving offers to store generation metadata.
        """
        self._window = window
        self._image_stack = image_stack
        self._get_generator = get_generator
        self.metadata: Optional[dict[str, Any]] = None
        self.exif: Optional[Image.Exif] = None
        self._pending_save: Optional[AsyncTask] = None
        self._save_wait_loop: Optional[QEventLoop] = None
        self.on_save_started: Optional[Callable[[], Callable[[], None]]] = None
        """Called just before a save reads the document. A save that succeeds then calls the function it returned."""

    def clear_metadata(self) -> None:
        """Forgets the metadata and EXIF data of the previously open file."""
        self.metadata = None
        self.exif = None

    def metadata_json(self) -> str:
        """Returns the metadata as the JSON that .ora files store."""
        return json.dumps(self.metadata, cls=_MetadataEncoder)

    def exif_bytes(self) -> Optional[bytes]:
        """Returns the EXIF data of the open file, encoded, or None if there is none."""
        return None if self.exif is None else self.exif.tobytes()

    def apply_restored_document(self, restored: RestoredDocument) -> None:
        """Takes the metadata, EXIF data and file path of a document restored from a recovery copy.

        Save then writes to the path the document came from.
        """
        self.metadata = None if restored.metadata is None else json.loads(restored.metadata)
        self.exif = Image.Exif()
        if restored.exif is not None:
            self.exif.load(restored.exif)
        Cache().set(Cache.LAST_FILE_PATH, restored.original_path)
        AppStateTracker.set_app_state(APP_STATE_EDITING)

    def save(self) -> None:
        """Saves the edited image, only opening the save dialog if no previous image path is cached."""
        image_path = Cache().get(Cache.LAST_FILE_PATH)
        if not os.path.isfile(image_path):
            image_path = None
        self.save_as(file_path=image_path)

    def wait_for_pending_save(self) -> None:
        """Returns once any background write has finished, keeping the UI responsive while it runs."""
        if self._pending_save is None:
            return
        loop = QEventLoop()
        self._save_wait_loop = loop  # `_finished` quits it, and runs after this call whatever the write's progress.
        loop.exec()
        self._save_wait_loop = None

    def _start_save(self, file_path: str, write: Callable[[], None], on_saved: Optional[Callable[[], None]],
                    on_success: Optional[Callable[[], None]] = None) -> None:
        """Runs `write` on a worker thread, then reports the result on the GUI thread.

        `write` may only use data captured beforehand, never `Layer`, `ImageStack` or widget objects. On success,
        `file_path` becomes the last saved path, then `on_saved` (from `on_save_started`) and `on_success` run.
        Failure shows an error dialog.
        """
        self.wait_for_pending_save()
        errors: list[Exception] = []

        def _write() -> None:
            try:
                write()
            except Exception as err:  # pylint: disable=broad-exception-caught
                errors.append(err)

        task = AsyncTask(_write)
        self._pending_save = task

        def _finished() -> None:
            if self._pending_save is task:
                self._pending_save = None
            if len(errors) == 0 and os.path.isfile(file_path):
                Cache().set(Cache.LAST_FILE_PATH, file_path)
                add_recent_file(file_path)
                if on_saved is not None:
                    on_saved()
                if on_success is not None:
                    on_success()
            else:
                message = (str(errors[0]) if len(errors) > 0
                           else SAVE_ERROR_MESSAGE_UNKNOWN_ISSUE.format(file_path=file_path))
                logger.error(f'save failed: {message}')
                show_error_dialog(self._window, SAVE_ERROR_TITLE, message)
            if self._save_wait_loop is not None:
                self._save_wait_loop.quit()

        task.finish_signal.connect(_finished)
        task.start()


    def save_as(self, file_path: Optional[str] = None) -> None:
        """Open a save dialog, and save the edited image to disk, preserving any metadata."""
        cache = Cache()
        config = AppConfig()
        error_handled = False
        # Plain saves reuse the remembered animation options, Save As asks:
        ask_about_animation = not isinstance(file_path, str)
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

            animation_options: Optional[AnimationSaveOptions] = None
            if file_format in ANIMATION_WRITE_FORMATS and self._image_stack.layer_stack.count > 1:
                animation_only = file_format in ANIMATION_ONLY_FORMATS
                if ask_about_animation:
                    confirmed, animation_options = AnimationSaveModal(
                        self._window, allow_flattened=not animation_only).show_animation_save_modal()
                    if not confirmed:
                        error_handled = True  # Nothing was written, and canceling isn't an error.
                        return
                elif animation_only or cache.get(Cache.ANIMATION_SAVE_AS_ANIMATION):
                    animation_options = saved_animation_options()

            # Check if metadata is out of date, ask if it should update:
            generator = self._get_generator()
            if file_format in IMAGE_FORMATS_SUPPORTING_METADATA and generator is not None \
                    and not isinstance(generator, NullGenerator):
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

            on_saved = None if self.on_save_started is None else self.on_save_started()
            if file_path.lower().endswith(ORA_FILE_EXTENSION):
                snapshot = capture_ora_image(self._image_stack, file_path, self.metadata_json())
                self._start_save(snapshot.file_path, lambda: write_ora_snapshot(snapshot), on_saved)
                error_handled = True  # The write's own handler reports any failure.
                return
            image = self._image_stack.qimage()
            animation_frames: Optional[list[ImageFrame]] = None
            if animation_options is not None:
                animation_frames = render_frames(self._image_stack)
            saved_images = [image] if animation_frames is None else [frame.image for frame in animation_frames]

            # Check for data loss conditions that should be mentioned:
            warn_save_discards_layers = (config.get(AppConfig.WARN_BEFORE_LAYERLESS_SAVE)
                                         and animation_options is None
                                         and self._image_stack.layer_stack.count > 1)
            warn_save_discards_alpha = (config.get(AppConfig.WARN_BEFORE_RGB_SAVE)
                                        and ((file_format not in IMAGE_FORMATS_SUPPORTING_ALPHA
                                              and not all(image_is_fully_opaque(saved) for saved in saved_images))
                                             or (file_format in IMAGE_FORMATS_SUPPORTING_PARTIAL_ALPHA
                                                 and any(image_has_partial_alpha(saved)
                                                         for saved in saved_images))))
            warn_save_discards_metadata = (config.get(AppConfig.WARN_BEFORE_SAVE_WITHOUT_METADATA)
                                           and self.metadata is not None
                                           and METADATA_PARAMETER_KEY in self.metadata
                                           and file_format not in IMAGE_FORMATS_SUPPORTING_METADATA)
            warn_save_is_write_only = (config.get(AppConfig.WARN_BEFORE_WRITE_ONLY_SAVE)
                                       and file_format in IMAGE_WRITE_FORMATS
                                       and file_format not in IMAGE_READ_FORMATS)
            warn_save_changes_size = (config.get(AppConfig.WARN_BEFORE_FIXED_SIZE_SAVE)
                                      and file_format in IMAGE_FORMATS_WITH_FIXED_SIZE
                                      and image.size() != IMAGE_FORMATS_WITH_FIXED_SIZE[file_format])
            warn_save_removes_color = (config.get(AppConfig.WARN_BEFORE_COLOR_LOSS)
                                       and file_format in GREYSCALE_IMAGE_FORMATS)
            # The worker writes from copies, so edits made while it runs don't reach the file:
            saved_image = image.copy()
            saved_metadata = copy.deepcopy(self.metadata)
            saved_exif = copy.deepcopy(self.exif)
            metadata_fallback_used: list[bool] = []

            def _write_flat_image() -> None:
                if animation_frames is not None:
                    assert animation_options is not None
                    save_animation(animation_frames, file_path, animation_options, saved_metadata, saved_exif)
                elif file_format in IMAGE_FORMATS_SUPPORTING_METADATA:
                    try:
                        save_image_with_metadata(saved_image, file_path, saved_metadata, saved_exif)
                    except ValueError:
                        logger.error(f'Format {file_format} should support metadata, but saving with metadata'
                                     ' failed.')
                        metadata_fallback_used.append(True)
                        save_image(saved_image, file_path, saved_exif)
                else:
                    save_image(saved_image, file_path, saved_exif)

            def _show_data_loss_warnings() -> None:
                """Shows the data loss warnings that apply to the finished save, unless disabled."""
                nonlocal warn_save_discards_metadata
                if len(metadata_fallback_used) > 0:
                    warn_save_discards_metadata = config.get(AppConfig.WARN_BEFORE_SAVE_WITHOUT_METADATA)
                alpha_loss_message = ALPHA_NOT_SAVED_MESSAGE
                metadata_loss_message = METADATA_NOT_SAVED_MESSAGE
                fixed_size_message = FIXED_SIZE_SAVE_MESSAGE
                color_loss_message = NO_COLOR_SAVE_MESSAGE
                write_only_message = WRITE_ONLY_SAVE_MESSAGE

                def _extension_str(extensions: tuple[str, ...]) -> str:
                    return ', '.join((f'.{ext.lower()}' for ext in extensions))

                format_str = f'.{file_format.lower()}'
                layers_loss_message = LAYERS_NOT_SAVED_MESSAGE.format(
                    animation_formats=_extension_str(tuple(sorted(ANIMATION_WRITE_FORMATS))))

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
                         layers_loss_message),
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

            self._start_save(file_path, _write_flat_image, on_saved, _show_data_loss_warnings)
            error_handled = True  # The write's own handler reports any failure.
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

    def load(self, file_path: Optional[str | list[str]] = None) -> None:
        """Open a loading dialog, then load the selected image for editing."""
        self.wait_for_pending_save()
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
        self.exif = Image.Exif()
        self.metadata = None
        try:
            assert file_path is not None
            if file_path.lower().endswith('.ora'):
                metadata = read_ora_image(self._image_stack, file_path)
                if metadata is not None and len(metadata) > 0:
                    self.metadata = json.loads(metadata)
            else:
                image, exif, image_info = load_image(file_path)
                # try and load metadata:
                if image_info is not None:
                    if METADATA_COMMENT_KEY in image_info and METADATA_PARAMETER_KEY not in image_info:
                        # noinspection PyTypeChecker
                        image_info[METADATA_PARAMETER_KEY] = image_info[METADATA_COMMENT_KEY]
                    self.metadata = image_info
                if exif is not None:
                    if isinstance(exif, Image.Exif):
                        self.exif = exif
                    elif (self.metadata is None or METADATA_PARAMETER_KEY
                          not in self.metadata) and isinstance(exif, dict):
                        self.metadata = exif
                        if 'exif' in exif:
                            self.exif.load(exif['exif'])
                if (self.metadata is None or METADATA_PARAMETER_KEY not in self.metadata) and self.exif is not None:
                    exif_tags = self.exif.get_ifd(IFD.Exif)
                    description = exif_tags.get(ExifTags.Base.ImageDescription)
                    if description is None:
                        description = self.exif.get(ExifTags.Base.ImageDescription)
                    if description is not None:
                        if self.metadata is None:
                            self.metadata = {}
                        self.metadata[METADATA_PARAMETER_KEY] = description
                if self._should_load_frames(file_path, image.size()):
                    frames = load_image_frames(file_path)
                    load_frames_as_image(self._image_stack, frames)
                    self._remember_animation_options(frames, self.metadata)
                else:
                    self._image_stack.load_image(image)
            cache.set(Cache.LAST_FILE_PATH, file_path)
            add_recent_file(file_path)

            # File loaded, attempt to apply metadata:
            if self.metadata is not None and METADATA_PARAMETER_KEY in self.metadata:
                param_str = self.metadata[METADATA_PARAMETER_KEY]
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

    def load_layers(self) -> None:
        """Open one or more images as layers."""
        layer_paths, layers_selected = open_image_layers(self._window)
        if not layers_selected or not layer_paths or len(layer_paths) == 0:
            return
        self.add_layers_from_files(layer_paths)

    def add_layers_from_files(self, layer_paths: list[str]) -> None:
        """Adds image files as new layers, creating a blank image to hold them if none is open."""
        layers: list[tuple[QImage, str, Optional[list[ImageFrame]]]] = []
        errors: list[str] = []
        for layer_path in layer_paths:
            try:
                image, _, _ = load_image(layer_path)
                frames = load_image_frames(layer_path) if self._should_load_frames(layer_path, image.size()) else None
                layers.append((image, layer_path, frames))
            except IOError:
                errors.append(layer_path)
        if not self._image_stack.has_image:
            width = 0
            height = 0
            for image, _, frames in layers:
                for frame_image in [image] if frames is None else [frame.image for frame in frames]:
                    width = max(width, frame_image.width())
                    height = max(height, frame_image.height())
            base_layer = create_transparent_image(QSize(width, height))
            self._image_stack.load_image(base_layer)
        for image, image_path, frames in layers:
            name = os.path.basename(image_path)
            if frames is None:
                self._image_stack.create_layer(name, image)
            else:
                add_frame_layers(self._image_stack, frames, f'{name}: ')
        if len(errors) > 0:
            show_error_dialog(self._window, LOAD_LAYER_ERROR_TITLE, LOAD_LAYER_ERROR_MESSAGE + ','.join(errors))
        if self._image_stack.has_image:
            AppStateTracker.set_app_state(APP_STATE_EDITING)

    @staticmethod
    def _remember_animation_options(frames: list[ImageFrame], file_info: Optional[dict[str, Any]]) -> None:
        """Fills the animation save options from an opened animation's first frame duration and loop count."""
        cache = Cache()
        cache.set(Cache.ANIMATION_SAVE_AS_ANIMATION, True)
        if frames[0].duration_ms is not None:
            cache.set(Cache.ANIMATION_FRAME_DURATION, min(frames[0].duration_ms, ANIMATION_MAX_FRAME_MS))
        loop = None if file_info is None else file_info.get('loop')
        if isinstance(loop, int):
            cache.set(Cache.ANIMATION_LOOP_FOREVER, loop == 0)
            if loop > 0:
                cache.set(Cache.ANIMATION_LOOP_COUNT, min(loop, ANIMATION_MAX_LOOP_COUNT))

    def _should_load_frames(self, file_path: str, frame_size: QSize) -> bool:
        """Returns whether to open each frame of a file as a layer, asking first if that would use a lot of memory."""
        frame_count = count_image_frames(file_path)
        if frame_count < 2:
            return False
        frame_bytes = frame_count * frame_size.width() * frame_size.height() * 4  # ARGB32 pixels
        if frame_bytes <= LARGE_ANIMATION_BYTES:
            return True
        message = LARGE_ANIMATION_MESSAGE.format(file_name=os.path.basename(file_path), frame_count=frame_count,
                                                 size_gb=frame_bytes / 1024 ** 3)
        return request_confirmation(self._window, LARGE_ANIMATION_TITLE, message, None,
                                    QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No,
                                    confirm_label=LARGE_ANIMATION_BUTTON)

    def reload(self) -> None:
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
                                                                   RELOAD_CONFIRMATION_MESSAGE,
                                                                   discards_work=True,
                                                                   confirm_label=RELOAD_CONFIRMATION_BUTTON):
            self.load(file_path=file_path)

    def _metadata_will_be_saved(self) -> bool:
        return self.metadata is not None and METADATA_PARAMETER_KEY in self.metadata

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
        return self.metadata is not None and self._updated_metadata_params() == self.metadata[METADATA_PARAMETER_KEY]

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
        if self.metadata is None:
            self.metadata = {}
        self.metadata[METADATA_PARAMETER_KEY] = params
        if self.exif is None:
            self.exif = Image.Exif()
        exif_tags = self.exif.get_ifd(IFD.Exif)
        exif_tags[ExifTags.Base.ImageDescription.value] = params
        if show_messagebox:
            message_box = QMessageBox(modal_parent())
            message_box.setWindowTitle(METADATA_UPDATE_TITLE)
            message_box.setText(METADATA_UPDATE_MESSAGE)
            message_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            message_box.exec()
            message_box.deleteLater()
