"""Converts the library's `GenerationProgress` snapshots into IntraPaint's generation status updates.

`progress_status_update` returns the dict `ImageGenerator._apply_status_update` reads. The library calls a
`handle.wait(on_progress=...)` callback on the worker thread, so the callback only emits the result through the task's
status signal.
"""
from typing import Optional

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from sd_backend_client import GenerationProgress, GenerationStatus

from src.controller.image_generation.sd_adapters.image_adapter import pil_to_qimage

# The QCoreApplication.translate context for strings in this file
TR_ID = 'controller.image_generation.sd_adapters.progress_adapter'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


STATUS_QUEUED = _tr('Waiting, position {queue_number} in queue.')
STATUS_WAITING = _tr('Waiting...')
STATUS_GENERATING = _tr('Generating...')
STATUS_BATCH_NUMBER = _tr('Batch {batch_num} of {num_batches}:')
STATUS_ETA_MINUTES = _tr('ETA: {minutes}:{seconds}')
STATUS_ETA_SECONDS = _tr('ETA: {seconds}s')

# Key `ImageGenerator._apply_status_update` reads status text from.
PROGRESS_KEY = 'progress'


def progress_percentage(progress: GenerationProgress, batch_index: int = 0, num_batches: int = 1) -> Optional[float]:
    """Returns how much of a multi-batch request is done, from 0.0 to 100.0, or None if the backend didn't say.

    Parameters
    ----------
    progress: GenerationProgress
        Progress of the batch currently running.
    batch_index: int
        0-based index of that batch.
    num_batches: int
        Number of batches, each one library job.
    """
    if progress.progress is None:
        if num_batches == 1:
            return None
        batch_fraction = 0.0
    else:
        batch_fraction = min(max(progress.progress, 0.0), 1.0)
    return round((batch_index + batch_fraction) / num_batches * 100, ndigits=4)


def _eta_text(eta_seconds: float) -> str:
    minutes = round(eta_seconds // 60)
    seconds = round(eta_seconds % 60)
    if minutes > 0:
        return STATUS_ETA_MINUTES.format(minutes=minutes, seconds=f'{seconds:02d}')
    return STATUS_ETA_SECONDS.format(seconds=seconds)


def progress_status_text(progress: GenerationProgress, batch_index: int = 0, num_batches: int = 1) -> str:
    """Returns loading message text for a progress snapshot: the job state, then the percentage and ETA if known.

    See `progress_percentage` for the parameters.
    """
    if progress.status == GenerationStatus.PENDING:
        status_text = STATUS_WAITING if progress.queue_index is None \
            else STATUS_QUEUED.format(queue_number=progress.queue_index)
    else:
        status_text = STATUS_GENERATING
    if num_batches > 1:
        status_text = f'{STATUS_BATCH_NUMBER.format(batch_num=batch_index + 1, num_batches=num_batches)} {status_text}'
    percentage = progress_percentage(progress, batch_index, num_batches)
    if percentage is not None:
        status_text = f'{status_text}\n{percentage}%'
        if progress.eta_seconds is not None and progress.eta_seconds > 0:
            status_text = f'{status_text} {_eta_text(progress.eta_seconds)}'
    return status_text


def progress_status_update(progress: GenerationProgress, batch_index: int = 0, num_batches: int = 1) -> dict[str, str]:
    """Returns a status update for `ImageGenerator._apply_status_update`. See `progress_percentage` for the parameters.
    """
    return {PROGRESS_KEY: progress_status_text(progress, batch_index, num_batches)}


def progress_preview(progress: GenerationProgress) -> Optional[QImage]:
    """Returns a progress snapshot's live preview image, or None if it has none."""
    if progress.preview is None:
        return None
    return pil_to_qimage(progress.preview)
