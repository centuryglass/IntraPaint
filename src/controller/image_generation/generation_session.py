"""Owns the current and previous batch of generated image options for the open document.

The selection screen shows whichever batch the session holds. The session lives on the main thread.
"""
import logging
from typing import Optional

from PySide6.QtCore import QObject, QSize, Signal
from PySide6.QtGui import QImage

from src.controller.image_generation.generated_image_batch import GeneratedImageBatch
from src.image.layers.image_stack import ImageStack

logger = logging.getLogger(__name__)


class GenerationSession(QObject):
    """Tracks the batch being generated or reviewed, and the last batch that was closed with results.

    `archive_current` stores the current batch for `restore_previous`, until another document is loaded.
    """

    previous_options_available = Signal(bool)
    """Emitted when `can_restore_previous` changes."""

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
