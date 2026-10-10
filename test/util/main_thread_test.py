"""Tests the main-thread rule helpers and the `AsyncTask` construction check."""
import threading

from src.util.async_task import AsyncTask
from src.util.main_thread import is_main_thread, assert_main_thread
from test.base_test_case import IntraPaintTestCase

JOIN_TIMEOUT_SECONDS = 10


class MainThreadTest(IntraPaintTestCase):
    """Tests `is_main_thread`, `assert_main_thread` and the `AsyncTask` constructor check."""

    def _run_on_worker(self, fn) -> list[BaseException]:
        errors: list[BaseException] = []

        def run() -> None:
            try:
                fn()
            except BaseException as err:  # pylint: disable=broad-exception-caught
                errors.append(err)

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        worker.join(JOIN_TIMEOUT_SECONDS)
        self.assertFalse(worker.is_alive())
        return errors

    def test_main_thread_detection(self) -> None:
        """The test thread is the main thread, and a plain worker thread is not."""
        self.assertTrue(is_main_thread())
        assert_main_thread('test')
        results: list[bool] = []
        self.assertEqual([], self._run_on_worker(lambda: results.append(is_main_thread())))
        self.assertEqual([False], results)

    def test_async_task_requires_main_thread(self) -> None:
        """Constructing an AsyncTask on a worker thread raises RuntimeError."""
        errors = self._run_on_worker(lambda: AsyncTask(lambda: None))
        self.assertEqual(1, len(errors))
        self.assertIsInstance(errors[0], RuntimeError)
        AsyncTask(lambda: None)  # Main thread construction works.
