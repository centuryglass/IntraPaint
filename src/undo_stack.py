"""Global stack for tracking undo/redo state."""
import logging
from contextlib import contextmanager
from typing import Callable, Optional, Dict, Any, List, ContextManager
from threading import Lock

logger = logging.getLogger(__name__)
MAX_UNDO = 50


class _UndoAction:
    def __init__(self, undo_action: Callable[[], None],
                 redo_action: Callable[[], None],
                 action_type: Optional[str],
                 action_data: Optional[Dict[str, Any]]) -> None:
        self.undo = undo_action
        self.redo = redo_action
        self.type = action_type
        self.action_data = action_data


_undo_stack: List[_UndoAction] = []
_redo_stack: List[_UndoAction] = []
_access_lock = Lock()


def commit_action(action: Callable[[], None], undo_action: Callable[[], None], action_type: str,
                  action_data: Optional[Dict[str, Any]] = None) -> bool:
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
    action_type: str
        An arbitrary label used to identify the action, to be used when attempting to merge actions in the stack.
    action_data: Dict
        Arbitrary data to use for merging actions.
    """
    global _undo_stack, _redo_stack, _access_lock
    if _access_lock.locked():
        raise RuntimeError('Concurrent undo history changes detected!')
    with _access_lock:
        logger.info(f'ADD ACTION:{action_type}, UNDO_COUNT={len(_undo_stack)}, REDO_COUNT={len(_redo_stack)}')
        action()
        undo_entry = _UndoAction(undo_action, action, action_type, action_data)
        _undo_stack.append(undo_entry)
        if len(_undo_stack) > MAX_UNDO:
            _undo_stack = _undo_stack[:-MAX_UNDO]
        _redo_stack.clear()
    return True


@contextmanager
def last_action() -> ContextManager[Optional[_UndoAction]]:
    """Access the most recent action, potentially updating it to combine actions."""
    global _undo_stack, _access_lock
    if _access_lock.locked():
        raise RuntimeError('Concurrent undo history changes detected!')
    with _access_lock:
        yield None if len(_undo_stack) == 0 else _undo_stack[-1]


def undo() -> None:
    """Reverses the most recent action taken."""
    global _undo_stack, _redo_stack, _access_lock
    with _access_lock:
        if len(_undo_stack) == 0:
            return
        last_action_object = _undo_stack.pop()
        logger.info(f'UNDO ACTION:{last_action_object.type}, UNDO_COUNT={len(_undo_stack)},'
                    f' REDO_COUNT={len(_redo_stack)}')
        last_action_object.undo()
        _redo_stack.append(last_action_object)


def redo() -> None:
    """Re-applies the last undone action as long as no new actions were registered after the last undo."""
    global _undo_stack, _redo_stack, _access_lock
    with _access_lock:
        if len(_redo_stack) == 0:
            return
        last_action_object = _redo_stack.pop()
        logger.info(f'REDO ACTION:{last_action_object.type}, UNDO_COUNT={len(_undo_stack)},'
                    f' REDO_COUNT={len(_redo_stack)}')
        last_action_object.redo()
        _undo_stack.append(last_action_object)
        if len(_undo_stack) > MAX_UNDO:
            _undo_stack = _undo_stack[:-MAX_UNDO]
