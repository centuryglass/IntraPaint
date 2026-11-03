"""Keeps a crash recovery copy of the open document, and offers to restore one left by a session that crashed.

The copy lives in this session's folder under `recovery_root()`, in the layout `src/image/recovery_files.py`
describes. Saves run only after the document changes, once input pauses for `AppConfig.AUTOSAVE_IDLE_SECONDS` or
after `AppConfig.AUTOSAVE_MAX_INTERVAL_SECONDS` of constant editing, and never during a brush stroke or a generation.

Each autosave copies only the layers whose content changed since the last one, on the GUI thread, and writes them on a
worker. Quitting normally deletes the folder. Opening or creating a document deletes it too, and a successful save
removes its manifest, so neither is offered for recovery.

Not saved: undo history, and generated images that haven't been added to the document.
"""
import dataclasses
import logging
import threading
import weakref
from dataclasses import dataclass
from typing import Optional, Callable, Any

from PySide6.QtCore import QObject, QTimer, QRect, QSize, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QWidget

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller.image_io import ImageIO
from src.image.brush.layer_brush import LayerBrush
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.image.layers.transform_layer import TransformLayer
from src.image.open_raster import OraSnapshot, capture_ora_image, ora_xml_files
from src.image.recovery_files import (RecoveryWrite, RecoverableSession, plan_recovery_write, write_recovery,
                                      create_session_dir, delete_session, clear_manifest, find_recoverable_sessions,
                                      restore_session)
from src.ui.modal.modal_utils import (request_recovery_choice, show_error_dialog, RECOVERY_RESTORE,
                                      RECOVERY_DISCARD)
from src.undo_stack import UndoStack
from src.util.application_state import AppStateTracker, APP_STATE_LOADING
from src.util.async_task import AsyncTask

logger = logging.getLogger(__name__)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'controller.autosave_controller'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


RESTORE_ERROR_TITLE = _tr('Restore failed')
RESTORE_ERROR_MESSAGE = _tr('The recovery copy could not be opened: {error}')

# Delay before trying again when an autosave comes due during a stroke, a generation or another autosave's write:
BUSY_RETRY_MS = 1000

# The thumbnail shown when offering a recovery copy fits within this size:
THUMBNAIL_SIZE = QSize(256, 256)

# What decides whether a layer's pixels changed: its content timestamp, transform and size.
_LayerKey = tuple[float, tuple[float, ...], tuple[int, int]]

# Asks what to do with a crashed session: returns `RECOVERY_RESTORE`, `RECOVERY_DISCARD` or `RECOVERY_LATER`.
RecoveryPrompt = Callable[[Optional[QWidget], RecoverableSession], str]


def _prompt_for_recovery(parent: Optional[QWidget], session: RecoverableSession) -> str:
    return request_recovery_choice(parent, session.original_path, session.saved_at, session.thumbnail())


def _layer_key(layer: TransformLayer) -> _LayerKey:
    transform = layer.transform
    return (layer.content_change_timestamp,
            (transform.m11(), transform.m12(), transform.m13(), transform.m21(), transform.m22(), transform.m23(),
             transform.m31(), transform.m32(), transform.m33()),
            (layer.size.width(), layer.size.height()))


@dataclass(frozen=True)
class _DocumentState:
    """What an autosave compares to decide whether the document changed since the copy it last wrote.

    Leaves out the metadata, EXIF data and original path, which `ImageIO` sets after a load replaces the document.
    Every copy still holds their current values.
    """
    layer_keys: dict[int, _LayerKey]
    xml_files: dict[str, bytes]
    generation_area: QRect


class AutosaveController(QObject):
    """Writes recovery copies of the open document, and restores them after a crash.

    All methods run on the GUI thread. Only `write_recovery` runs on a worker.
    """

    def __init__(self, image_stack: ImageStack, image_io: ImageIO, window: Optional[QWidget],
                 root: Optional[str] = None) -> None:
        """Starts tracking changes to the document.

        Parameters
        ----------
        image_stack: ImageStack
            The document to autosave.
        image_io: ImageIO
            Supplies the metadata saved with the document, and reports finished saves.
        window: Optional[QWidget]
            Parent of the recovery prompt.
        root: Optional[str]
            Directory for session folders, `recovery_root()` if None.
        """
        super().__init__()
        self._image_stack = image_stack
        self._image_io = image_io
        self._window = window
        self._root = root
        self._session_dir: Optional[str] = None
        self._generation = 0
        self._dirty = False
        self._change_count = 0
        # What the session folder holds, for the next autosave to reuse:
        self._written_keys: dict[int, _LayerKey] = {}
        self._layer_files: dict[tuple[int, str], str] = {}
        # The document as of the last autosave, open or save. None if unknown, which makes the next autosave write.
        self._clean_state: Optional[_DocumentState] = None
        self._pending_write: Optional[AsyncTask] = None
        self._pending_done: Optional[threading.Event] = None
        self._pending_finish: Optional[Callable[[], None]] = None
        self._running_tasks: set[AsyncTask] = set()
        self._clear_after_write = False
        self._shut_down = False

        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self.autosave_now)
        self._max_timer = QTimer(self)
        self._max_timer.setSingleShot(True)
        self._max_timer.timeout.connect(self.autosave_now)

        for signal in (image_stack.content_changed, image_stack.size_changed, image_stack.layer_added,
                       image_stack.layer_removed, image_stack.active_layer_changed, image_stack.layer_order_changed,
                       image_stack.generation_area_bounds_changed, UndoStack().undo_count_changed,
                       UndoStack().redo_count_changed):
            signal.connect(self._document_edited)
        image_stack.document_changed.connect(self._document_replaced)
        weak_self = weakref.ref(self)  # ImageIO outlives nothing here, and a bound method would form a cycle.

        def _on_save_started() -> Callable[[], None]:
            controller = weak_self()
            return (lambda: None) if controller is None else controller.save_started()

        image_io.on_save_started = _on_save_started
        config = AppConfig()
        config.connect(self, AppConfig.AUTOSAVE_ENABLED, self._enabled_changed)
        self._document_replaced()

    @property
    def enabled(self) -> bool:
        """Returns whether autosave is turned on in settings."""
        return bool(AppConfig().get(AppConfig.AUTOSAVE_ENABLED))

    @property
    def session_dir(self) -> Optional[str]:
        """Returns this session's recovery folder, or None if nothing has been autosaved."""
        return self._session_dir

    @property
    def dirty(self) -> bool:
        """Returns whether the document may have changed since the last autosave, open or save."""
        return self._dirty

    def autosave_now(self, synchronous: bool = False) -> bool:
        """Writes a recovery copy if the document changed, returning whether a write started.

        Puts the save off for `BUSY_RETRY_MS` during a stroke, a generation or another autosave's write. With
        `synchronous` set, it waits for any earlier write, writes on this thread, and returns whether that write
        succeeded.
        """
        if self._shut_down or not self.enabled or not self._dirty or not self._image_stack.has_image:
            return False
        if synchronous:
            self._wait_for_write()
        elif self._busy():
            self._idle_timer.start(BUSY_RETRY_MS)
            return False
        self._idle_timer.stop()
        self._max_timer.stop()
        self._dirty = False
        try:
            capture = self._capture()
        except (ValueError, TypeError, OSError) as err:
            logger.error(f'Autosave failed: {err}')
            return False
        if capture is None:
            return False
        write, state = capture
        return self._start_write(write, state, synchronous)

    def offer_recovery(self, prompt: RecoveryPrompt = _prompt_for_recovery) -> bool:
        """Offers each crashed session's recovery copy, newest first, returning whether one was restored.

        Restoring stops the offers, leaving older sessions for the next launch. A restored copy replaces the open
        document, takes its original path as the save path, and becomes this session's first autosave.
        """
        for session in find_recoverable_sessions(self._root):
            choice = prompt(self._window, session)
            if choice == RECOVERY_DISCARD:
                delete_session(session.session_dir)
            elif choice == RECOVERY_RESTORE:
                try:
                    restored = restore_session(self._image_stack, session)
                except (OSError, ValueError, KeyError, TypeError, AssertionError) as err:
                    logger.error(f'Restoring {session.session_dir} failed: {err}')
                    show_error_dialog(self._window, RESTORE_ERROR_TITLE, RESTORE_ERROR_MESSAGE.format(error=err))
                    continue
                self._image_io.apply_restored_document(restored)
                self._clean_state = None
                self._dirty = True
                # The crashed session's copy is the only one until this session's first write succeeds:
                if self.autosave_now(synchronous=True) or not self.enabled:
                    delete_session(session.session_dir)
                return True
        return False

    def shutdown(self) -> None:
        """Deletes this session's recovery folder after any write finishes, for a normal quit."""
        AppConfig().disconnect(self, AppConfig.AUTOSAVE_ENABLED)
        self._discard_session()
        self._shut_down = True

    def _busy(self) -> bool:
        return (LayerBrush.any_stroke_in_progress()
                or QApplication.mouseButtons() != Qt.MouseButton.NoButton
                or AppStateTracker.app_state() == APP_STATE_LOADING
                or self._pending_write is not None)

    def _document_edited(self, *_args: Any) -> None:
        if self._shut_down or not self.enabled:
            return
        self._change_count += 1
        self._dirty = True
        self._idle_timer.start(AppConfig().get(AppConfig.AUTOSAVE_IDLE_SECONDS) * 1000)
        if not self._max_timer.isActive():
            self._max_timer.start(AppConfig().get(AppConfig.AUTOSAVE_MAX_INTERVAL_SECONDS) * 1000)

    def _document_replaced(self) -> None:
        """Deletes the copy of the replaced document. The new one matches its file, or is blank."""
        self._discard_session()
        if self.enabled and self._image_stack.has_image:
            try:
                self._clean_state = self._current_state(self._capture_snapshot(lambda _layer: False))
            except (ValueError, TypeError) as err:
                logger.error(f'Autosave can\'t read the document: {err}')

    def save_started(self) -> Callable[[], None]:
        """Returns what to run if the save that's reading the document succeeds."""
        change_count = self._change_count

        def _saved() -> None:
            if change_count != self._change_count or not self.enabled:
                return  # The document changed after the save read it, so the copy is still needed.
            self._dirty = False
            self._idle_timer.stop()
            self._max_timer.stop()
            self._clean_state = self._current_state(self._capture_snapshot(lambda _layer: False))
            if self._pending_write is not None:
                self._clear_after_write = True
            elif self._session_dir is not None:
                clear_manifest(self._session_dir)
        return _saved

    def _enabled_changed(self, enabled: bool) -> None:
        if enabled:
            self._clean_state = None
            self._document_edited()
        else:
            self._discard_session()

    def _discard_session(self) -> None:
        """Stops pending autosaves and deletes the session folder, after any write into it finishes."""
        self._idle_timer.stop()
        self._max_timer.stop()
        self._dirty = False
        self._clear_after_write = False
        self._wait_for_write()
        if self._session_dir is not None:
            delete_session(self._session_dir)
            self._session_dir = None
        self._written_keys = {}
        self._layer_files = {}
        self._clean_state = None

    def _wait_for_write(self) -> None:
        """Blocks until a pending write finishes, then applies its result.

        The result has to be applied before the next write: a finished write deletes files the previous one named.
        """
        if self._pending_done is None or self._pending_finish is None:
            return
        self._pending_done.wait()
        finish = self._pending_finish
        self._pending_write = None
        self._pending_done = None
        self._pending_finish = None
        finish()

    def _layer_keys(self) -> dict[int, _LayerKey]:
        return {layer.id: _layer_key(layer) for layer in self._image_stack.layer_stack.recursive_child_layers
                if isinstance(layer, TransformLayer) and not isinstance(layer, LayerGroup)}

    def _capture_snapshot(self, capture_pixels: Callable[[Layer], bool]) -> OraSnapshot:
        return capture_ora_image(self._image_stack, 'recovered.ora', self._image_io.metadata_json(),
                                 capture_pixels=capture_pixels, include_merged_image=False)

    def _current_state(self, snapshot: OraSnapshot) -> _DocumentState:
        return _DocumentState(self._layer_keys(), ora_xml_files(dataclasses.replace(snapshot, metadata=None)),
                              self._image_stack.generation_area)

    def _capture(self) -> Optional[tuple[RecoveryWrite, _DocumentState]]:
        """Reads what changed since the last autosave. Returns None if nothing did."""
        layer_keys = self._layer_keys()
        if self._clean_state is not None and layer_keys == self._clean_state.layer_keys:
            # Pixels match the clean state, so check everything else before copying any:
            state = self._current_state(self._capture_snapshot(lambda _layer: False))
            if state == self._clean_state:
                return None
        forced_ids: set[int] = set()

        def _capture_pixels(layer: Layer) -> bool:
            return (layer.id in forced_ids or layer.id not in self._written_keys
                    or self._written_keys[layer.id] != layer_keys.get(layer.id))

        if self._session_dir is None:
            self._session_dir = create_session_dir(self._root)
        thumbnail = self._thumbnail()
        for _ in range(2):
            snapshot = self._capture_snapshot(_capture_pixels)
            write, missing = plan_recovery_write(snapshot, self._session_dir, self._generation, self._layer_files,
                                                 Cache().get(Cache.LAST_FILE_PATH),
                                                 self._image_stack.generation_area, self._image_io.exif_bytes(),
                                                 thumbnail)
            if len(missing) == 0:
                self._generation += 1
                return write, self._current_state(snapshot)
            # A layer with no file yet that `_capture_pixels` skipped. Copy it too:
            forced_ids.update(missing)
        raise ValueError(f'Layers {sorted(missing)} could not be captured')

    def _thumbnail(self) -> QImage:
        image = self._image_stack.qimage()
        # A fast scale to twice the size first, so the smooth scale only reads a small image:
        image = image.scaled(THUMBNAIL_SIZE * 2, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.FastTransformation)
        return image.scaled(THUMBNAIL_SIZE, Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)

    def _start_write(self, write: RecoveryWrite, state: _DocumentState, synchronous: bool) -> bool:
        errors: list[str] = []  # Messages only: a held exception's traceback would keep this frame in a cycle.
        done = threading.Event()

        def _write() -> None:
            try:
                write_recovery(write)
            except Exception as err:  # pylint: disable=broad-exception-caught
                errors.append(str(err))
            finally:
                done.set()

        def _finished() -> None:
            if errors:
                logger.error(f'Autosave failed: {errors[0]}')
                self._dirty = True  # Retried after the next change.
                return
            self._written_keys = {layer_id: state.layer_keys[layer_id] for layer_id, _ in write.layer_files
                                  if layer_id in state.layer_keys}
            self._layer_files = dict(write.layer_files)
            if self._clear_after_write:
                self._clear_after_write = False
                clear_manifest(write.session_dir)
            else:
                self._clean_state = state

        if synchronous:
            _write()
            _finished()
            return len(errors) == 0
        task = AsyncTask(_write)
        self._pending_write = task
        self._pending_done = done
        self._pending_finish = _finished
        self._running_tasks.add(task)

        def _task_finished() -> None:
            self._running_tasks.discard(task)
            if self._pending_write is task:  # Otherwise `_wait_for_write` already applied the result.
                self._wait_for_write()

        task.finish_signal.connect(_task_finished)
        task.start()
        return True
