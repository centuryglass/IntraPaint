"""Global stack for tracking undo/redo state."""
from typing import Callable
from threading import Lock

MAX_UNDO = 50

_undo_stack = []
_redo_stack = []
_access_lock = Lock()


class _UndoAction:
    def __init__(self, undo_action: Callable[[], None], redo_action: Callable[[], None]) -> None:
        self.undo = undo_action
        self.redo = redo_action


def commit_action(action: Callable[[], None], undo_action: Callable[[], None]) -> None:
    """Performs an action, then commits it to the undo stack.

    The undo stack is lock-protected.  Make sure that the function parameters provided don't also call commit_action.

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
    """
    global _undo_stack, _redo_stack, _access_lock
    with _access_lock:
        action()
        undo_action = _UndoAction(undo_action, action)
        _undo_stack.append(undo_action)
        if len(_undo_stack) > MAX_UNDO:
            _undo_stack = _undo_stack[:-MAX_UNDO]
        _redo_stack.clear()


def undo() -> None:
    """Reverses the most recent action taken."""
    global _undo_stack, _redo_stack, _access_lock
    with _access_lock:
        if len(_undo_stack) == 0:
            return
        last_action = _undo_stack.pop()
        last_action.undo()
        _redo_stack.append(last_action)


def redo() -> None:
    """Re-applies the last undone action as long as no new actions were registered after the last undo."""
    global _undo_stack, _redo_stack, _access_lock
    with _access_lock:
        if len(_redo_stack) == 0:
            return
        last_action = _redo_stack.pop()
        last_action.redo()
        _undo_stack.append(last_action)
        if len(_undo_stack) > MAX_UNDO:
            _undo_stack = _undo_stack[:-MAX_UNDO]
