"""Owns the current and previous batch of generated image options for the open document, the edits that
write an option out of a batch, and the background task that produces a batch.

The selection screen shows whichever batch the session holds. The session lives on the main thread and opens no
dialogs: `apply` and `choose` return an outcome for the caller to report, and generation reports through signals.
"""
import logging
from typing import Callable, Optional

from PySide6.QtCore import QObject, QPoint, QRect, QSize, Signal, SignalInstance
from PySide6.QtGui import QImage, QPainter

from src.config.cache import Cache

from src.controller.image_generation.apply_option import apply_generated_image, ApplyOutcome
from src.controller.image_generation.generated_image_batch import GeneratedImageBatch
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.util.application_state import AppStateTracker, APP_STATE_EDITING, APP_STATE_LOADING
from src.util.async_task import AsyncTask
from src.util.visual.image_format_utils import save_image

GenerateAction = Callable[[SignalInstance, QImage, Optional[QImage]], None]
"""The backend's `ImageGenerator.generate`: takes a status signal, the source image and the inpainting mask."""

logger = logging.getLogger(__name__)


class GenerationSession(QObject):
    """Tracks the batch being generated or reviewed, and the last batch that was closed with results.

    `archive_current` stores the current batch for `restore_previous`, until another document is loaded.
    """

    previous_options_available = Signal(bool)
    """Emitted when `can_restore_previous` changes."""

    generation_started = Signal(object)
    """Emitted when `generate` starts a task, with the paste mask (QImage or None) options are applied with."""

    image_ready = Signal(QImage, int)
    """Emitted on the main thread with a generated image and its index (zero is the first generated image)."""

    progress_changed = Signal(str)
    """Emitted with the backend's progress text."""

    generation_finished = Signal()
    """Emitted when the task ends, before `image_ready` delivers the images that arrived."""

    generation_failed = Signal(object)
    """Emitted with the exception when the backend raises, before `generation_finished`."""

    def __init__(self, image_stack: ImageStack) -> None:
        super().__init__()
        self._image_stack = image_stack
        self._current: Optional[GeneratedImageBatch] = None
        self._previous: Optional[GeneratedImageBatch] = None
        self._previous_available = False
        # True once `archive_current` has stored the current batch:
        self._current_archived = False
        # False while a re-opened batch is current, which has no placeholders left to fill:
        self._accepting_results = False
        self._generating = False
        self._results: list[QImage] = []
        image_stack.size_changed.connect(self._on_image_stack_resized)
        image_stack.document_changed.connect(self._on_document_changed)

    @property
    def current(self) -> GeneratedImageBatch:
        """The batch being shown. Raises RuntimeError before the first `begin`."""
        if self._current is None:
            raise RuntimeError('No generation batch has been started.')
        return self._current

    @property
    def previous(self) -> Optional[GeneratedImageBatch]:
        """The stored batch `restore_previous` would re-open, if any."""
        return self._previous

    @property
    def accepting_results(self) -> bool:
        """Whether the current batch still has placeholders for new images to fill."""
        return self._accepting_results

    @property
    def generating(self) -> bool:
        """Whether a task started by `generate` has not finished."""
        return self._generating

    def generate(self, action: GenerateAction, image: QImage, mask: Optional[QImage],
                 paste_mask: Optional[QImage]) -> bool:
        """Runs `action(status_signal, image, mask)` in a background task and reports through the session's signals.

        `action` passes each image it produces to `store_result` from the worker thread, then `deliver_result` on the
        main thread. In inpainting mode, `paste_mask` clips the previews shown and the options applied. Returns False
        without starting anything if a task is already running.
        """
        if self._generating:
            logger.error('Caught and ignored duplicate image generation request.')
            return False
        self._results.clear()
        self._generating = True

        # Previews show the unscaled source outside the mask that clips them when applied, so they match the result.
        composite_base: Optional[QImage] = None
        if mask is not None and paste_mask is not None:
            composite_base = image.copy()
            base_painter = QPainter(composite_base)
            base_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
            base_painter.drawImage(QRect(QPoint(), composite_base.size()), paste_mask)
            base_painter.end()

        class _AsyncInpaintTask(AsyncTask):
            status_signal = Signal(dict)
            error_signal = Signal(Exception)

            def signals(self) -> list[SignalInstance]:
                return [self.status_signal, self.error_signal]

        def _do_inpaint(status_signal: SignalInstance, error_signal: SignalInstance) -> None:
            try:
                action(status_signal, image, mask)
            except (IOError, ValueError, RuntimeError) as err:
                error_signal.emit(err)
            except Exception as unexpected_err:
                logger.error(f'Unexpected error: {unexpected_err}')
                error_signal.emit(unexpected_err)

        inpaint_task = _AsyncInpaintTask(_do_inpaint)

        def _handle_error(err: BaseException) -> None:
            self._generating = False
            self.generation_failed.emit(err)

        def _finished() -> None:
            self._generating = False
            self.generation_finished.emit()
            # Disconnecting by slot would make this closure refer to itself, a cycle that holds the task:
            for signal in (inpaint_task.error_signal, inpaint_task.status_signal, inpaint_task.finish_signal):
                signal.disconnect()
            expected_count = Cache().get(Cache.BATCH_COUNT) * Cache().get(Cache.BATCH_SIZE)
            for idx, result in enumerate(self._results):
                if result.isNull() or idx >= expected_count:
                    continue
                if composite_base is not None and composite_base.size() == result.size():
                    painter = QPainter(result)
                    painter.drawImage(QPoint(), composite_base)
                    painter.end()
                self.image_ready.emit(result, idx)

        inpaint_task.error_signal.connect(_handle_error)
        inpaint_task.status_signal.connect(self._apply_status_update)
        inpaint_task.finish_signal.connect(_finished)

        self.generation_started.emit(paste_mask)
        AppStateTracker.set_app_state(APP_STATE_LOADING)
        inpaint_task.start()
        return True

    def store_result(self, image: QImage, index: int) -> None:
        """Stores a generated image at `index`, padding skipped indices with null images. Safe on any thread."""
        while len(self._results) < index:
            self._results.append(QImage())
        if len(self._results) > index:
            self._results.pop(index)
        self._results.insert(index, image)

    def result(self, index: int) -> QImage:
        """Returns the image stored at `index` by `store_result`. Raises IndexError if there is none."""
        return self._results[index]

    def deliver_result(self, index: int) -> None:
        """Emits `image_ready` for a stored image, unless it is null."""
        image = self._results[index]
        if not image.isNull():
            self.image_ready.emit(image, index)

    def _apply_status_update(self, status_dict: dict[str, str]) -> None:
        """Records the seeds a backend reports and forwards its progress text."""
        if 'seed' in status_dict:
            Cache().set(Cache.LAST_SEED, str(status_dict['seed']))
        if 'subseed' in status_dict:
            Cache().set(Cache.WEBUI_LAST_SUBSEED, str(status_dict['subseed']))
        if 'progress' in status_dict:
            self.progress_changed.emit(status_dict['progress'])

    def begin(self, loading_text: str, paste_mask: Optional[QImage] = None) -> GeneratedImageBatch:
        """Starts a batch from the current image content, with placeholders for the images to come.

        Inpainted options are clipped by `paste_mask` when they are applied, or by the selection if it is None.
        """
        self._accepting_results = True
        self._current_archived = False
        self._current = GeneratedImageBatch(self._image_stack, loading_text, paste_mask)
        return self._current

    def add_image(self, image: QImage, idx: int) -> bool:
        """Stores a generated image in the current batch's slot `idx` (zero is the first generated image).

        Returns False if the batch is a re-opened one that takes no more results.
        """
        if not self._accepting_results:
            logger.info(f'Ignored image option {idx}: the batch showing was re-opened')
            return False
        batch = self.current
        slot = idx + 1  # Original image gets index zero
        if slot == len(batch.option_images):
            batch.option_images.append(image)
        else:
            batch.option_images[slot] = image
        return True

    def archive_current(self) -> Optional[list[int]]:
        """Stores the current batch for `restore_previous` if any of its images arrived.

        Only the first call for each batch stores anything, so every path that closes the selection screen can call
        it. Returns the indices of the options that were kept, from before the placeholders were dropped, or None if
        nothing was stored.
        """
        kept: Optional[list[int]] = None
        batch = self._current
        if batch is not None and not self._current_archived and batch.has_results():
            kept = batch.discard_placeholders()
            self._previous = batch
            self._current_archived = True
        self._report_previous_available()
        return kept

    def can_restore_previous(self) -> bool:
        """Returns whether a batch is stored and its generation area is still within the image."""
        if self._previous is None:
            return False
        return self._image_stack.bounds.contains(self._previous.generation_area)

    def restore_previous(self) -> GeneratedImageBatch:
        """Makes the stored batch current again, with its first option showing the current canvas content."""
        if not self.can_restore_previous():
            raise RuntimeError('No previous options found!')
        batch = self._previous
        assert batch is not None
        self._accepting_results = False
        self._current_archived = False
        batch.option_images[0] = self._image_stack.qimage_generation_area_content()
        self._current = batch
        return batch

    def apply(self, option_index: int, layer: Layer, layer_name: str, clear_context_pins: bool = False) -> ApplyOutcome:
        """Writes an option of the current batch into `layer`, using the batch's own mask, area and edit mode.

        `layer_name` names the layer created if `layer` can't take the content. See `apply_generated_image`.
        """
        batch = self.current
        return apply_generated_image(self._image_stack, batch.edit_image(option_index), layer, batch.generation_area,
                                     batch.edit_mode, batch.mask_image, layer_name, clear_context_pins)

    def choose(self, option_index: int, layer_name: str) -> Optional[ApplyOutcome]:
        """Finishes the selection: applies the option to the active layer unless it is the original content, clears
        context pins per `AppConfig.CLEAR_CONTEXT_PINS_AFTER_GENERATING`, and returns to the editing state.

        Returns None when the original content was chosen and nothing was applied.
        """
        outcome = None
        if option_index != 0:
            outcome = self.apply(option_index, self._image_stack.active_layer, layer_name, True)
        AppStateTracker.set_app_state(APP_STATE_EDITING)
        return outcome

    def send_to_new_layer(self, option_index: int, layer_name: str) -> Layer:
        """Applies an option of the current batch to a new layer and returns that layer."""
        new_layer = self._image_stack.create_layer(layer_name=layer_name)
        return self.apply(option_index, new_layer, layer_name).layer

    def save_to_file(self, option_index: int, path: str) -> None:
        """Saves an option of the current batch to `path` at its largest available resolution."""
        save_image(self.current.full_image(option_index), path)

    def _on_document_changed(self) -> None:
        """Drops the stored batch, which belongs to the replaced document."""
        self._previous = None
        self._report_previous_available()

    def _on_image_stack_resized(self, _size: QSize) -> None:
        """Re-checks `can_restore_previous`, which a resize can change."""
        self._report_previous_available()

    def _report_previous_available(self) -> None:
        available = self.can_restore_previous()
        if available != self._previous_available:
            self._previous_available = available
            self.previous_options_available.emit(available)
