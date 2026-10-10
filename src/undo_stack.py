"""Global stack for tracking undo/redo state, as a thin wrapper over a QUndoStack."""
import logging
from contextlib import contextmanager
from typing import Callable, Optional, Any, Generator

from PySide6.QtCore import QObject, Signal, SignalInstance, SIGNAL, QCoreApplication, QThread
from PySide6.QtGui import QUndoStack, QUndoCommand

from src.config.application_config import AppConfig
from src.util.singleton import Singleton

logger = logging.getLogger(__name__)


class _CallableCommand(QUndoCommand):
    """A QUndoCommand that runs plain callables.

    PySide6 swallows exceptions raised in virtual overrides, so `redo` and `undo` hand them to `on_error` and the
    owning `UndoStack` re-raises the first one after Qt returns.

    `action_data` and the `redo_fn` / `undo_fn` attributes are what `UndoStack.last_action` callers edit to coalesce a
    continuous change into the previous entry.
    """

    def __init__(self, redo_fn: Callable[[], None], undo_fn: Callable[[], None], action_type: str,
                 action_data: Optional[dict[str, Any]], first_redo_is_noop: bool,
                 on_error: Callable[[BaseException], None]) -> None:
        super().__init__(action_type)
        self.redo_fn = redo_fn
        self.undo_fn = undo_fn
        self.action_type = action_type
        self.action_data = action_data
        self._first_redo_is_noop = first_redo_is_noop
        self._on_error = on_error

    def redo(self) -> None:
        """Re-applies the change, except for a first call that the committer already performed."""
        if self._first_redo_is_noop:
            self._first_redo_is_noop = False
            return
        try:
            self.redo_fn()
        except Exception as err:  # pylint: disable=broad-exception-caught
            self._on_error(err)

    def undo(self) -> None:
        """Reverses the change."""
        try:
            self.undo_fn()
        except Exception as err:  # pylint: disable=broad-exception-caught
            self._on_error(err)


class UndoStack(metaclass=Singleton):
    """Manages the application's shared undo history."""

    def __init__(self) -> None:
        self._stack = QUndoStack()
        self._open_group_depth = 0
        self._group_started = False
        self._group_type = ''
        self._busy_change = ''
        self._undo_in_progress = False
        self._redo_in_progress = False
        self._errors: list[BaseException] = []
        self._last_undo_count = 0
        self._last_redo_count = 0
        self._apply_undo_limit()

        class _SignalManager(QObject):
            undo_count_changed = Signal(int)
            redo_count_changed = Signal(int)
        self._signal_manager = _SignalManager()
        self._stack.indexChanged.connect(self._emit_count_changes)

    @property
    def undo_in_progress(self) -> bool:
        """Returns whether an undo action is currently in progress."""
        return self._undo_in_progress

    @property
    def redo_in_progress(self) -> bool:
        """Returns whether a redo action is currently in progress."""
        return self._redo_in_progress

    @property
    def undo_count_changed(self) -> SignalInstance:
        """Returns the signal emitted whenever undo action count changes."""
        return self._signal_manager.undo_count_changed

    @property
    def redo_count_changed(self) -> SignalInstance:
        """Returns the signal emitted whenever redo action count changes."""
        return self._signal_manager.redo_count_changed

    def undo_count(self) -> int:
        """Returns the number of saved actions in the undo stack."""
        return self._stack.index()

    def redo_count(self) -> int:
        """Returns the number of saved actions in the redo stack."""
        return self._stack.count() - self._stack.index()

    def commit_action(self, action: Callable[[], None], undo_action: Callable[[], None], action_type: str,
                      action_data: Optional[dict[str, Any]] = None, skip_initial_call=False) -> bool:
        """Performs an action, then commits it to the undo stack.

        Each commit outside `combining_actions` is its own undo entry. The parameter functions must not call
        `commit_action`, `combining_actions`, `undo` or `redo`.

        Parameters
        ----------
        action: Callable
            Some action function to run, accepting zero parameters.
        undo_action: Callable
            A function that completely reverses the changes caused by the `action` function.

            These parameters should be designed to leave the application in the same state if the following code runs,
            for any value n:
            ```
            for i in range(n):
                action()
                undo_action()
        action_type: str
            An arbitrary label used to identify the action, to be used when attempting to merge actions in the stack.
        action_data: dict
            Arbitrary data to use for merging actions.
        skip_initial_call: bool, default=False
            If true, skip the initial action() call.
        """
        self._assert_idle(action_type)
        logger.info(f'ADD ACTION:{action_type}, UNDO_COUNT={self.undo_count()}, REDO_COUNT={self.redo_count()}')
        self._busy_change = action_type
        try:
            if not skip_initial_call:
                action()
            if self._open_group_depth > 0 and not self._group_started:
                self._stack.beginMacro(self._group_type)
                self._group_started = True
            self._stack.push(_CallableCommand(action, undo_action, action_type, action_data, True, self._errors.append))
        finally:
            self._busy_change = ''
        return True

    @contextmanager
    def last_action(self, action_type: str) -> Generator[Optional[_CallableCommand], None, None]:
        """Access the most recent action, potentially updating it to combine actions.

        Yields None when the history is empty, the most recent entry is a group, or a group is open."""
        self._assert_idle(action_type)
        top_command = None
        if self._open_group_depth == 0 and self._stack.index() > 0 and self._stack.index() == self._stack.count():
            command = self._stack.command(self._stack.index() - 1)
            if isinstance(command, _CallableCommand):
                top_command = command
        yield top_command

    @contextmanager
    def combining_actions(self, action_type: str) -> Generator[None, None, None]:
        """Combines all actions added with commit_action until the context is exited.

        Groups nest: an inner group joins the outer one. If the block raises, the actions it already committed still go
        into the history as one entry, and the group closes so that later actions are recorded normally. A group with
        no commits adds nothing.

        Combine with other context managers as `with A, B:` or nested `with` blocks. `with A and B:` enters only B, so
        the actions are silently left ungrouped."""
        self._assert_idle(action_type)
        if self._open_group_depth == 0:
            self._group_type = action_type
            self._group_started = False
        self._open_group_depth += 1
        try:
            yield
        finally:
            self._open_group_depth -= 1
            if self._open_group_depth == 0 and self._group_started:
                self._group_started = False
                self._stack.endMacro()

    def undo(self) -> None:
        """Reverses the most recent action taken."""
        self._assert_idle('undo')
        if not self._stack.canUndo():
            return
        logger.info(f'UNDO ACTION:{self._stack.undoText()}, UNDO_COUNT={self.undo_count()},'
                    f' REDO_COUNT={self.redo_count()}')
        self._busy_change = 'undo'
        # ImageLayer skips alpha lock enforcement while this is set, so it must never outlive the undo:
        self._undo_in_progress = True
        try:
            self._stack.undo()
        finally:
            self._undo_in_progress = False
            self._busy_change = ''
        self._raise_recorded_error()

    def redo(self) -> None:
        """Re-applies the last undone action as long as no new actions were registered after the last undo."""
        self._assert_idle('redo')
        if not self._stack.canRedo():
            return
        logger.info(f'REDO ACTION:{self._stack.redoText()}, UNDO_COUNT={self.undo_count()},'
                    f' REDO_COUNT={self.redo_count()}')
        self._busy_change = 'redo'
        self._redo_in_progress = True
        try:
            self._stack.redo()
        finally:
            self._redo_in_progress = False
            self._busy_change = ''
        self._raise_recorded_error()

    def clear(self) -> None:
        """Clears the entire undo/redo history.

        This is also the only point where a changed `AppConfig.MAX_UNDO` takes effect, since QUndoStack accepts a new
        limit only while empty."""
        assert self._open_group_depth == 0
        self._stack.clear()
        self._apply_undo_limit()
        self._emit_count_changes()

    def _reset(self) -> None:
        """Disconnects everything connected to the count signals, then clears the undo/redo history.

        Tests call this between cases. A connected slot that captures its owner keeps it alive for as long as the
        connection exists, so connections left behind would keep every earlier test's widgets alive.
        """
        for signal, signature in ((self.undo_count_changed, 'undo_count_changed(int)'),
                                  (self.redo_count_changed, 'redo_count_changed(int)')):
            if self._signal_manager.receivers(SIGNAL(signature)) > 0:
                signal.disconnect()
        self._open_group_depth = 0
        self._group_started = False
        self._errors.clear()
        self.clear()

    def _apply_undo_limit(self) -> None:
        # QUndoStack treats a limit of 0 as unlimited, so the smallest history is one entry.
        self._stack.setUndoLimit(max(AppConfig().get(AppConfig.MAX_UNDO), 1))

    def _emit_count_changes(self, *_args) -> None:
        undo_count = self.undo_count()
        redo_count = self.redo_count()
        undo_changed = undo_count != self._last_undo_count
        redo_changed = redo_count != self._last_redo_count
        self._last_undo_count = undo_count
        self._last_redo_count = redo_count
        if undo_changed:
            self.undo_count_changed.emit(undo_count)
        if redo_changed:
            self.redo_count_changed.emit(redo_count)

    def _assert_idle(self, action_type: str) -> None:
        app = QCoreApplication.instance()
        assert app is None or QThread.currentThread() == app.thread(), \
            f'Undo history changes must happen on the main thread, attempted: {action_type}'
        if self._busy_change:
            raise RuntimeError(f'Concurrent undo history changes detected! Attempted: {action_type}, '
                               f'in-progress: {self._busy_change}')

    def _raise_recorded_error(self) -> None:
        if self._errors:
            error = self._errors[0]
            self._errors.clear()
            raise error
