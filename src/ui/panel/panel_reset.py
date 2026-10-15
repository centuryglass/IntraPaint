"""Restores a panel's or active tool's config values to the defaults in their definition files.

A panel declares the keys it resets and connects `PanelHeader.reset_requested` to `reset_config_keys`. Values are
visible in the panel, so the reset asks for no confirmation.
"""
from typing import Any, Optional, Sequence

from src.config.config import Config
from src.undo_stack import UndoStack

RESET_ACTION_TYPE = 'reset_panel_defaults'


def reset_config_keys(config: Config, keys: Sequence[str], undo_stack: Optional[UndoStack] = None) -> bool:
    """Sets each key to its definition default. Keys already at their default, and keys with no default, are skipped.

    With an `undo_stack`, all changed keys are restored by one undo step. Pass one when the keys' normal edits are
    undoable, and omit it when they aren't.

    Returns
    -------
    bool
        Whether any value changed.

    Raises
    ------
    KeyError
        If a key isn't tracked by `config`.
    """
    changes: dict[str, tuple[Any, Any]] = {}
    for key in keys:
        default = config.get_default(key)
        current = config.get(key)
        if default is not None and default != current:
            changes[key] = (current, default)
    if len(changes) == 0:
        return False

    def _apply(index: int) -> None:
        for key, values in changes.items():
            config.set(key, values[index], add_missing_options=True)

    if undo_stack is None:
        _apply(1)
    else:
        undo_stack.commit_action(lambda: _apply(1), lambda: _apply(0), RESET_ACTION_TYPE)
    return True
