"""
ImageIO owns opening and saving image files for the application.

- Shows the open and save dialogs, and the errors and data loss warnings around them.
- Holds the open file's `ImageMetadata`, so a save writes back what a load read.
- Runs file writes on a worker thread, from copies of the edited data.
- Connects the `ImageStack` to image files in every supported format.

`AppController` keeps the File menu actions and delegates each one to the matching method here.
"""
import logging
import os
from typing import Optional, Any, Callable

from PIL import UnidentifiedImageError
from PySide6.QtCore import QSize, QEventLoop
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller.image_generation.image_generator import ImageGenerator
from src.controller.image_generation.null_generator import NullGenerator
from src.image.animation import load_frames_as_image, add_frame_layers, render_frames
from src.image.image_metadata import ImageMetadata, A1111Parameters
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer_group import LayerGroup
from src.image.metadata_cache_fields import LOAD_APPLIED_FIELDS, METADATA_UPDATE_FIELDS, apply_to_cache, \
    update_from_cache
from src.image.metadata_save_rules import MetadataKind, format_name, split_metadata
from src.image.open_raster import capture_ora_image, write_ora_snapshot, read_ora_image, ORA_FILE_EXTENSION
from src.image.recovery_files import RestoredDocument
from src.ui.modal.animation_save_modal import AnimationSaveModal, saved_animation_options
from src.ui.modal.modal_parent import modal_parent
from src.ui.modal.save_loss_modal import SaveLoss, request_save_loss_choice, SAVE_ORA, CANCEL
from src.ui.modal.modal_utils import show_error_dialog, request_confirmation, open_image_file, open_image_layers, \
    show_warning_dialog, request_unsaved_changes_choice, UNSAVED_SAVE, UNSAVED_DISCARD
from src.undo_stack import UndoStack
from src.util.application_state import AppStateTracker, APP_STATE_EDITING
from src.util.async_task import AsyncTask
from src.util.recent_files import add_recent_file
from src.util.visual.image_format_utils import save_image_with_metadata, save_image, load_image, \
    IMAGE_FORMATS_SUPPORTING_METADATA, IMAGE_FORMATS_SUPPORTING_ALPHA, IMAGE_FORMATS_SUPPORTING_PARTIAL_ALPHA, \
    IMAGE_WRITE_FORMATS, IMAGE_READ_FORMATS, IMAGE_FORMATS_WITH_FIXED_SIZE, \
    GREYSCALE_IMAGE_FORMATS, PIL_WRITE_FORMATS, QIMAGE_WRITE_FORMATS, count_image_frames, \
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
RELOAD_CONFIRMATION_BUTTON = _tr('Reload without saving')
UNTITLED_FILE_NAME = _tr('Untitled')
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

# Data loss warnings, shown before a save that would lose the data:
LAYERS_NOT_SAVED_TITLE = _tr('Layers will not be saved')
LAYERS_NOT_SAVED_MESSAGE = _tr('To save layer data, images must be saved in .ora format. To save each layer as an'
                               ' animation frame, use one of the following formats: {animation_formats}')

ALPHA_NOT_SAVED_TITLE = _tr('Transparency will not be fully saved')
ALPHA_NOT_SAVED_MESSAGE = _tr('To preserve transparency, save using one of the following file formats:'
                              ' {alpha_formats}')

METADATA_NOT_SAVED_TITLE = _tr('Image generation metadata will not be saved')
METADATA_NOT_SAVED_MESSAGE = _tr('To preserve image generation metadata, save using one of the following file formats:'
                                 ' {metadata_formats}')

OTHER_METADATA_NOT_SAVED_TITLE = _tr('Some metadata will not be saved')
OTHER_METADATA_NOT_SAVED_MESSAGE = _tr('Saving as {file_format} drops: {dropped}. The .ora format keeps all of it.')
OTHER_METADATA_PART_LABELS = {
    MetadataKind.COMMENT: _tr('comment'),
    MetadataKind.TEXT_ENTRIES: _tr('text entries'),
    MetadataKind.EXIF: _tr('EXIF tags'),
    MetadataKind.XMP: _tr('XMP'),
    MetadataKind.IPTC: _tr('IPTC'),
}
OTHER_METADATA_DETAIL_LINE = _tr('{part}: {items}')

WRITE_ONLY_SAVE_TITLE = _tr('This format cannot be opened again')
WRITE_ONLY_SAVE_MESSAGE = _tr('IntraPaint can write images in the {file_format} format, but cannot load them. Use '
                              'another file format if you want to be able to load this image in IntraPaint again.')

FIXED_SIZE_SAVE_TITLE = _tr('This format will change the image size')
FIXED_SIZE_SAVE_MESSAGE = _tr('The image is {width_px}x{height_px}, but the {file_format} format saves all images at'
                              ' {saved_width_px}x{saved_height_px} resolution. Use another file format if you want'
                              ' to preserve the original image size.')

NO_COLOR_SAVE_TITLE = _tr('Color will not be saved')
NO_COLOR_SAVE_MESSAGE = _tr('The {file_format} format saves the image without color. Use another format if you want'
                            ' to preserve image colors.')


def _extension_str(extensions: tuple[str, ...]) -> str:
    return ', '.join((f'.{ext.lower()}' for ext in extensions))


def _other_metadata_loss(metadata: ImageMetadata, file_format: str, is_animation: bool) -> Optional[SaveLoss]:
    """Returns the loss for everything but generation parameters that a save drops, or None if it drops nothing.

    Generation parameters have their own warning, see `METADATA_NOT_SAVED_TITLE`. The item names go in the loss's
    details, because an image can carry hundreds of EXIF tags.
    """
    dropped = split_metadata(metadata, file_format, is_animation, frozenset({MetadataKind.PARAMETERS})).dropped
    if len(dropped) == 0:
        return None
    labels = ', '.join(OTHER_METADATA_PART_LABELS[part.kind] for part in dropped)
    details = '\n'.join(OTHER_METADATA_DETAIL_LINE.format(
        part=OTHER_METADATA_PART_LABELS[part.kind], items=', '.join(part.details)) for part in dropped
                        if len(part.details) > 0)
    return SaveLoss(OTHER_METADATA_NOT_SAVED_TITLE, OTHER_METADATA_NOT_SAVED_MESSAGE.format(
        file_format=format_name(file_format), dropped=labels), AppConfig.WARN_BEFORE_METADATA_LOSS, details)


def _metadata_loss_message() -> str:
    return METADATA_NOT_SAVED_MESSAGE.format(metadata_formats=_extension_str(tuple(IMAGE_FORMATS_SUPPORTING_METADATA)))


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
        self._metadata = ImageMetadata()
        self._pending_save: Optional[AsyncTask] = None
        self._saves_succeeded = 0
        self._save_wait_loop: Optional[QEventLoop] = None
        self.on_metadata_replaced: Optional[Callable[[ImageMetadata], None]] = None
        """Called with the new `ImageMetadata` whenever a load or new image replaces `metadata`."""
        self.on_save_started: Optional[Callable[[], Callable[[], None]]] = None
        """Called just before a save reads the document. A save that succeeds then calls the function it returned."""

    @property
    def metadata(self) -> ImageMetadata:
        """The open file's metadata."""
        return self._metadata

    @metadata.setter
    def metadata(self, metadata: ImageMetadata) -> None:
        self._metadata = metadata
        if self.on_metadata_replaced is not None:
            self.on_metadata_replaced(metadata)

    def clear_metadata(self) -> None:
        """Forgets the metadata of the previously open file."""
        self.metadata = ImageMetadata()

    def apply_restored_document(self, restored: RestoredDocument) -> None:
        """Takes the metadata and file path of a document restored from a recovery copy.

        Save then writes to the path the document came from.
        """
        self.metadata = restored.metadata
        Cache().set(Cache.LAST_FILE_PATH, restored.original_path)
        AppStateTracker.set_app_state(APP_STATE_EDITING)

    @staticmethod
    def file_name() -> str:
        """Returns the name of the open file, or `UNTITLED_FILE_NAME` if it was never saved."""
        file_path = Cache().get(Cache.LAST_FILE_PATH)
        return UNTITLED_FILE_NAME if file_path == '' else os.path.basename(file_path)

    def confirm_unsaved_changes(self, discard_label: str) -> bool:
        """Returns whether an action that replaces the document may proceed, asking first if it has unsaved changes.

        The user can save, discard or cancel. Saving waits for the write, and a cancelled or failed save stops the
        action. `discard_label` names the action on the discard button ("Quit without saving").
        """
        if not self._image_stack.has_image or UndoStack().is_clean():
            return True
        choice = request_unsaved_changes_choice(self._window, self.file_name(), discard_label)
        if choice == UNSAVED_SAVE:
            return self.save_and_wait()
        return choice == UNSAVED_DISCARD

    def save_and_wait(self) -> bool:
        """Saves like `save`, waits for the write to finish, and returns whether it succeeded."""
        succeeded_before = self._saves_succeeded
        self.save()
        self.wait_for_pending_save()
        return self._saves_succeeded > succeeded_before

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
        `file_path` becomes the last saved path, then `on_saved` and `on_success` run. Failure shows an error dialog.
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
                self._saves_succeeded += 1
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


    def _save_started(self, keeps_layers: bool) -> Callable[[], None]:
        """Called just before a save reads the document, returning what to run if the save succeeds.

        A successful save makes the history state it read clean, unless it flattened layers (the condition
        `LAYERS_NOT_SAVED_MESSAGE` warns about). Then the file holds no state of the document, and no state is clean.
        """
        mark_saved = UndoStack().save_point() if keeps_layers else UndoStack().mark_modified
        autosave_saved = None if self.on_save_started is None else self.on_save_started()

        def _on_saved() -> None:
            mark_saved()
            if autosave_saved is not None:
                autosave_saved()
        return _on_saved

    def _ora_save_path(self, file_path: str) -> Optional[str]:
        """Returns the .ora path that replaces `file_path` in "Save as .ora", asking where if that file exists."""
        ora_path = os.path.splitext(file_path)[0] + ORA_FILE_EXTENSION
        if not os.path.exists(ora_path):
            return ora_path
        selected_path = open_image_file(self._window, mode='save', selected_file=ora_path)
        return selected_path if isinstance(selected_path, str) else None

    def _has_layers_to_lose(self) -> bool:
        """Returns whether a flat save would discard layer structure: several root layers, or a lone layer group."""
        layer_stack = self._image_stack.layer_stack
        return layer_stack.count > 1 or (layer_stack.count == 1
                                         and isinstance(layer_stack.get_layer_by_index(0), LayerGroup))

    def _save_losses(self, file_format: str, image: QImage, saved_images: list[QImage],
                     is_animation: bool) -> list[SaveLoss]:
        """Lists what saving as `file_format` loses, for the losses whose warning is enabled."""
        config = AppConfig()
        format_str = f'.{file_format.lower()}'
        losses: list[SaveLoss] = []
        if (config.get(AppConfig.WARN_BEFORE_LAYERLESS_SAVE) and not is_animation
                and self._has_layers_to_lose()):
            losses.append(SaveLoss(LAYERS_NOT_SAVED_TITLE, LAYERS_NOT_SAVED_MESSAGE.format(
                animation_formats=_extension_str(tuple(sorted(ANIMATION_WRITE_FORMATS)))),
                AppConfig.WARN_BEFORE_LAYERLESS_SAVE))
        if (config.get(AppConfig.WARN_BEFORE_RGB_SAVE)
                and ((file_format not in IMAGE_FORMATS_SUPPORTING_ALPHA
                      and not all(image_is_fully_opaque(saved) for saved in saved_images))
                     or (file_format in IMAGE_FORMATS_SUPPORTING_PARTIAL_ALPHA
                         and any(image_has_partial_alpha(saved) for saved in saved_images)))):
            losses.append(SaveLoss(ALPHA_NOT_SAVED_TITLE, ALPHA_NOT_SAVED_MESSAGE.format(
                alpha_formats=_extension_str(IMAGE_FORMATS_SUPPORTING_ALPHA)), AppConfig.WARN_BEFORE_RGB_SAVE))
        if (config.get(AppConfig.WARN_BEFORE_SAVE_WITHOUT_METADATA) and self.metadata.parameters is not None
                and file_format not in IMAGE_FORMATS_SUPPORTING_METADATA):
            losses.append(SaveLoss(METADATA_NOT_SAVED_TITLE, _metadata_loss_message(),
                                   AppConfig.WARN_BEFORE_SAVE_WITHOUT_METADATA))
        if config.get(AppConfig.WARN_BEFORE_METADATA_LOSS):
            metadata_loss = _other_metadata_loss(self.metadata, file_format, is_animation)
            if metadata_loss is not None:
                losses.append(metadata_loss)
        if (config.get(AppConfig.WARN_BEFORE_WRITE_ONLY_SAVE) and file_format in IMAGE_WRITE_FORMATS
                and file_format not in IMAGE_READ_FORMATS):
            losses.append(SaveLoss(WRITE_ONLY_SAVE_TITLE, WRITE_ONLY_SAVE_MESSAGE.format(file_format=format_str),
                                   AppConfig.WARN_BEFORE_WRITE_ONLY_SAVE))
        if (config.get(AppConfig.WARN_BEFORE_FIXED_SIZE_SAVE) and file_format in IMAGE_FORMATS_WITH_FIXED_SIZE
                and image.size() != IMAGE_FORMATS_WITH_FIXED_SIZE[file_format]):
            final_size = IMAGE_FORMATS_WITH_FIXED_SIZE[file_format]
            losses.append(SaveLoss(FIXED_SIZE_SAVE_TITLE, FIXED_SIZE_SAVE_MESSAGE.format(
                width_px=image.width(), height_px=image.height(), file_format=format_str,
                saved_width_px=final_size.width(), saved_height_px=final_size.height()),
                AppConfig.WARN_BEFORE_FIXED_SIZE_SAVE))
        if config.get(AppConfig.WARN_BEFORE_COLOR_LOSS) and file_format in GREYSCALE_IMAGE_FORMATS:
            losses.append(SaveLoss(NO_COLOR_SAVE_TITLE, NO_COLOR_SAVE_MESSAGE.format(file_format=format_str),
                                   AppConfig.WARN_BEFORE_COLOR_LOSS))
        return losses

    def save_as(self, file_path: Optional[str] = None) -> None:
        """Open a save dialog, and save the edited image to disk, preserving any metadata."""
        cache = Cache()
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

            is_ora = file_path.lower().endswith(ORA_FILE_EXTENSION)
            image = QImage()
            animation_frames: Optional[list[ImageFrame]] = None
            if not is_ora:
                image = self._image_stack.qimage()
                if animation_options is not None:
                    animation_frames = render_frames(self._image_stack)
                saved_images = [image] if animation_frames is None else [frame.image for frame in animation_frames]
                losses = self._save_losses(file_format, image, saved_images, animation_options is not None)
                choice = request_save_loss_choice(self._window, losses, offer_ora=animation_options is None)
                if choice == CANCEL:
                    error_handled = True  # Nothing was written, and canceling isn't an error.
                    return
                if choice == SAVE_ORA:
                    error_handled = True  # The nested save reports its own failures.
                    ora_path = self._ora_save_path(file_path)
                    if ora_path is not None:
                        self.save_as(ora_path)
                    return

            on_saved = self._save_started(keeps_layers=is_ora or animation_options is not None
                                          or not self._has_layers_to_lose())
            if is_ora:
                snapshot = capture_ora_image(self._image_stack, file_path, self.metadata)
                self._start_save(snapshot.file_path, lambda: write_ora_snapshot(snapshot), on_saved)
                error_handled = True  # The write's own handler reports any failure.
                return
            # The worker writes from copies, so edits made while it runs don't reach the file:
            saved_image = image.copy()
            saved_metadata = self.metadata.copy()
            metadata_fallback_used: list[bool] = []

            def _write_flat_image() -> None:
                if animation_frames is not None:
                    assert animation_options is not None
                    save_animation(animation_frames, file_path, animation_options, saved_metadata)
                elif file_format in IMAGE_FORMATS_SUPPORTING_METADATA:
                    try:
                        save_image_with_metadata(saved_image, file_path, saved_metadata)
                    except ValueError:
                        logger.error(f'Format {file_format} should support metadata, but saving with metadata'
                                     ' failed.')
                        metadata_fallback_used.append(True)
                        save_image(saved_image, file_path, saved_metadata.exif)
                else:
                    save_image(saved_image, file_path, saved_metadata.exif)

            def _warn_if_metadata_fallback_used() -> None:
                """Warns after the write about metadata loss that only the write itself can discover."""
                if len(metadata_fallback_used) > 0:
                    show_warning_dialog(self._window, METADATA_NOT_SAVED_TITLE, _metadata_loss_message(),
                                        AppConfig.WARN_BEFORE_SAVE_WITHOUT_METADATA)

            self._start_save(file_path, _write_flat_image, on_saved, _warn_if_metadata_fallback_used)
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
        self.metadata = ImageMetadata()
        try:
            assert file_path is not None
            if file_path.lower().endswith('.ora'):
                self.metadata = read_ora_image(self._image_stack, file_path)
            else:
                image, self.metadata = load_image(file_path)
                if self._should_load_frames(file_path, image.size()):
                    frames = load_image_frames(file_path)
                    load_frames_as_image(self._image_stack, frames)
                    self._remember_animation_options(frames, self.metadata.format_info)
                else:
                    self._image_stack.load_image(image)
            cache.set(Cache.LAST_FILE_PATH, file_path)
            add_recent_file(file_path)
            self._apply_loaded_parameters()
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
                image, _ = load_image(layer_path)
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

    def _apply_loaded_parameters(self) -> None:
        """Applies the `LOAD_APPLIED_FIELDS` of the loaded image's A1111 parameters to the editor, if it has any."""
        params = self.metadata.a1111_parameters()
        if params is None:
            return
        if not params.has_generation_fields:
            logger.warning(f'image parameters do not match expected patterns, cannot be used. parameters:{params}')
            return
        logger.info('Detected saved image gen data, applying to UI')
        apply_to_cache(params, LOAD_APPLIED_FIELDS)

    @staticmethod
    def _remember_animation_options(frames: list[ImageFrame], file_info: dict[str, Any]) -> None:
        """Fills the animation save options from an opened animation's first frame duration and loop count."""
        cache = Cache()
        cache.set(Cache.ANIMATION_SAVE_AS_ANIMATION, True)
        if frames[0].duration_ms is not None:
            cache.set(Cache.ANIMATION_FRAME_DURATION, min(frames[0].duration_ms, ANIMATION_MAX_FRAME_MS))
        loop = file_info.get('loop')
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
        """Reload the edited image from disk, first offering to save unsaved changes."""
        file_path = Cache().get(Cache.LAST_FILE_PATH)
        if file_path == '':
            show_error_dialog(self._window, RELOAD_ERROR_TITLE, RELOAD_ERROR_MESSAGE_NO_IMAGE)
            return
        if not os.path.isfile(file_path):
            show_error_dialog(self._window, RELOAD_ERROR_TITLE,
                              RELOAD_ERROR_MESSAGE_INVALID_FILE.format(file_path=file_path))
            return
        if self.confirm_unsaved_changes(RELOAD_CONFIRMATION_BUTTON):
            self.load(file_path=file_path)

    def _metadata_will_be_saved(self) -> bool:
        return self.metadata.parameters is not None

    def _updated_metadata_params(self) -> str:
        """Returns the parameters text with the `METADATA_UPDATE_FIELDS` replaced by the editor's values.

        Other fields keep their saved text.
        """
        params = self.metadata.a1111_parameters()
        if params is None:
            params = A1111Parameters()
        update_from_cache(params, METADATA_UPDATE_FIELDS)
        return params.serialize()

    def _metadata_is_latest(self) -> bool:
        return self._metadata_will_be_saved() and self._updated_metadata_params() == self.metadata.parameters

    def update_metadata(self, show_messagebox: bool = True) -> None:
        """
        Writes the editor's generation settings into the image's A1111 parameters, to be saved with the image.

        Only the `METADATA_UPDATE_FIELDS` change: other fields in the saved parameters are kept.

        Parameters
        ----------
        show_messagebox: bool
            If true, show a messagebox after the update to let the user know what happened.
        """
        self.metadata.set_parameters(self._updated_metadata_params())
        if show_messagebox:
            message_box = QMessageBox(modal_parent())
            message_box.setWindowTitle(METADATA_UPDATE_TITLE)
            message_box.setText(METADATA_UPDATE_MESSAGE)
            message_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            message_box.exec()
            message_box.deleteLater()
