"""Tests that the exception hook shows one dialog at a time and still logs every exception."""
import threading
import traceback
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

    def test_quit_keeps_recovery_copy(self) -> None:
        """Clicking Quit asks the recovery callback to keep the work before quitting."""
        calls: list[str] = []
        hook = QtExceptHook(recovery_cb=lambda: calls.append('recover') or True, recovery_enabled_cb=lambda: True)

        def _click_quit() -> int:
            hook.b_quit.click()
            return 0

        with patch.object(hook._dialog, 'exec', _click_quit), \
                patch('src.util.qtexcepthook.QApplication.quit', lambda *_: calls.append('quit')), \
                patch('sys.__excepthook__'):
            hook._excepthook(*_exc_info())  # pylint: disable=protected-access
        self.assertEqual(['recover', 'quit'], calls)
        self.assertIn('recovered', hook.b_quit.text())

    def test_quit_label_without_recovery(self) -> None:
        """The Quit button warns about lost changes when recovery is unavailable."""
        hook = QtExceptHook(recovery_cb=lambda: False, recovery_enabled_cb=lambda: False)
        with patch.object(hook._dialog, 'exec', return_value=0), patch('sys.__excepthook__'):
            hook._excepthook(*_exc_info())  # pylint: disable=protected-access
        self.assertIn('lost', hook.b_quit.text())

    def test_dialog_available_after_close(self) -> None:
        """A new exception after the dialog closes shows it again."""
        hook = QtExceptHook()
        with patch.object(hook._dialog, 'exec', return_value=0) as exec_mock, \
                patch('sys.__excepthook__'):
            hook._excepthook(*_exc_info())  # pylint: disable=protected-access
            hook._excepthook(*_exc_info())  # pylint: disable=protected-access
        self.assertEqual(exec_mock.call_count, 2)

    def test_main_thread_exception_logged_with_traceback(self) -> None:
        """An exception on the main thread is logged with its exc_info, so IntraPaint.log gets the traceback."""
        hook = QtExceptHook()
        exc_info = _exc_info()
        with patch.object(hook._dialog, 'exec', return_value=0), patch('sys.__excepthook__'), \
                self.assertLogs('src.util.qtexcepthook', 'ERROR') as logs:
            hook._excepthook(*exc_info)  # pylint: disable=protected-access
        self.assertEqual(1, len(logs.records))
        self.assertEqual(exc_info, logs.records[0].exc_info)

    def test_worker_thread_exception_logged_and_queued(self) -> None:
        """An exception on a worker thread is logged there and shown through the main thread, not on the worker."""
        hook = QtExceptHook()
        queued: list = []
        exc_info = _exc_info()

        def _worker() -> None:
            hook._excepthook(*exc_info)  # pylint: disable=protected-access

        with patch.object(hook._dialog, 'exec', return_value=0) as exec_mock, patch('sys.__excepthook__'), \
                patch('src.util.qtexcepthook.run_on_main_thread', queued.append), \
                self.assertLogs('src.util.qtexcepthook', 'ERROR') as logs:
            thread = threading.Thread(target=_worker)
            thread.start()
            thread.join()
            exec_mock.assert_not_called()
            self.assertEqual(1, len(queued))
            queued[0]()
            exec_mock.assert_called_once()
        self.assertEqual(exc_info, logs.records[0].exc_info)

    def test_report_has_no_locals_and_includes_extra_info(self) -> None:
        """The report is a plain traceback without local variable values, followed by the environment details."""
        hook = QtExceptHook(extra_info_cb=lambda: 'IntraPaint version: test')

        def _raise() -> None:
            secret = 'secret-local-value'  # pylint: disable=unused-variable
            raise ValueError('boom')

        try:
            _raise()
        except ValueError as err:
            report = hook._report_text(type(err), err, err.__traceback__)  # pylint: disable=protected-access
            traceback.clear_frames(err.__traceback__)
            err.__traceback__ = None
        self.assertNotIn('secret-local-value', report)
        self.assertIn('ValueError: boom', report)
        self.assertNotIn('\n\n', report.split('\n\nIntraPaint version')[0])
        self.assertTrue(report.endswith('IntraPaint version: test'))
