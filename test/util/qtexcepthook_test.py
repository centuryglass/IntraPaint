"""Tests that the exception hook shows one dialog at a time and still logs every exception."""
from unittest.mock import patch

from src.util.qtexcepthook import QtExceptHook
from test.base_test_case import IntraPaintTestCase


def _exc_info() -> tuple:
    """Returns exception info for an exception that was never raised, so it has no traceback.

    A raised exception's traceback keeps the frame that raised it alive, and that frame keeps the calling test's frame
    alive. The test holds the hook and its dialog, so the patched `sys.__excepthook__` recording the arguments would
    leave them in a reference cycle.
    """
    return ValueError, ValueError('test error'), None


class QtExceptHookTest(IntraPaintTestCase):
    """Covers re-entrant exceptions raised while the bug dialog is open."""

    def test_nested_exception_does_not_reopen_dialog(self) -> None:
        """An exception raised while the dialog is open is logged and doesn't call exec again."""
        hook = QtExceptHook()
        exec_calls = []

        def _fake_exec() -> int:
            exec_calls.append(hook._dialog.detailedText())  # pylint: disable=protected-access
            hook._excepthook(*_exc_info())  # pylint: disable=protected-access
            return 0

        with patch.object(hook._dialog, 'exec', _fake_exec), \
                patch('sys.__excepthook__') as logged:
            hook._excepthook(*_exc_info())  # pylint: disable=protected-access
        self.assertEqual(len(exec_calls), 1)
        self.assertEqual(logged.call_count, 2)

    def test_dialog_available_after_close(self) -> None:
        """A new exception after the dialog closes shows it again."""
        hook = QtExceptHook()
        with patch.object(hook._dialog, 'exec', return_value=0) as exec_mock, \
                patch('sys.__excepthook__'):
            hook._excepthook(*_exc_info())  # pylint: disable=protected-access
            hook._excepthook(*_exc_info())  # pylint: disable=protected-access
        self.assertEqual(exec_mock.call_count, 2)
