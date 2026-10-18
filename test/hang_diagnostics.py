"""Reports what a hung test was doing, for the CI hangs in issue #390.

`faulthandler_timeout` in pytest.ini already dumps every thread's stack after a test runs too long. A hang seen
under `coverage run` was a main thread blocked acquiring coverage's non-reentrant `data_lock` inside
`HotkeyFilter.eventFilter`, and that dump can't show whether the same thread already held the lock or whether a
garbage collection was running. `HangWatchdog` adds both facts to the log shortly before the faulthandler dump.

The watchdog thread and the GC callback live in `test/`, outside coverage's `source`, so coverage doesn't take
`data_lock` for their frames and they can still run while the main thread is stuck on it.
"""
import gc
import os
import sys
import threading
import time
import traceback
from typing import Optional, TextIO

REPORT_AFTER_SECONDS = 120.0  # Must stay below `faulthandler_timeout` in pytest.ini, so this report comes first.
_POLL_SECONDS = 5.0
_RECENT_GC_LIMIT = 5


def _coverage_lock_state() -> str:
    """Describes whether any active coverage collector's `data_lock` is held."""
    collector_module = sys.modules.get('coverage.collector')
    if collector_module is None:
        return 'coverage not running'
    states = []
    for collector in collector_module.Collector._collectors:  # pylint: disable=protected-access
        lock = getattr(collector, 'data_lock', None)
        states.append('no lock' if lock is None else ('LOCKED' if lock.locked() else 'free'))
    return 'coverage data_lock: ' + (', '.join(states) if states else 'no active collector')


class HangWatchdog:
    """Prints the running test's GC and coverage-lock state if it runs longer than `REPORT_AFTER_SECONDS`."""

    def __init__(self) -> None:
        self._test: Optional[str] = None
        self._started = 0.0
        self._reported = False
        self._gc_running: Optional[int] = None
        self._gc_collections = 0
        self._recent_gc: list[str] = []
        self._thread: Optional[threading.Thread] = None
        self._main_thread_id = threading.main_thread().ident
        self._stream: Optional[TextIO] = None

    def start(self) -> None:
        """Begins watching: installs the GC callback and starts the polling thread.

        Call it while pytest's capture is suspended (`pytest_configure`), so the duplicate of file descriptor 2 it
        keeps for reports is the real stderr. Pytest's default capture redirects descriptor 2 itself, and holds
        anything written to it until the test ends, which a hung test never does.
        """
        try:
            self._stream = os.fdopen(os.dup(2), 'w')
        except OSError:
            self._stream = None
        gc.callbacks.append(self._on_gc)
        self._thread = threading.Thread(target=self._watch, name='hang-watchdog', daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Removes the GC callback. The daemon thread ends with the process."""
        if self._on_gc in gc.callbacks:
            gc.callbacks.remove(self._on_gc)
        if self._stream is not None:
            self._stream.close()
            self._stream = None

    def test_started(self, nodeid: str) -> None:
        """Starts the clock for a test."""
        self._test = nodeid
        self._started = time.monotonic()
        self._reported = False

    def test_finished(self) -> None:
        """Stops the clock."""
        self._test = None

    def _on_gc(self, phase: str, info: dict) -> None:
        generation = info.get('generation')
        if phase == 'start':
            self._gc_running = generation
            return
        self._gc_running = None
        self._gc_collections += 1
        self._recent_gc.append(f'gen {generation}: collected {info.get("collected")}, '
                               f'uncollectable {info.get("uncollectable")}')
        del self._recent_gc[:-_RECENT_GC_LIMIT]

    def _watch(self) -> None:
        while True:
            time.sleep(_POLL_SECONDS)
            test = self._test
            if test is None or self._reported or time.monotonic() - self._started < REPORT_AFTER_SECONDS:
                continue
            self._reported = True
            self._report(test)

    def _report(self, test: str) -> None:
        main_frame = sys._current_frames().get(self._main_thread_id)  # pylint: disable=protected-access
        main_stack = ''.join(traceback.format_stack(main_frame)) if main_frame is not None else '(unavailable)\n'
        gc_state = 'idle' if self._gc_running is None else f'RUNNING generation {self._gc_running}'
        lines = [
            f'--- hang diagnostics (issue #390): {test} has run {time.monotonic() - self._started:.0f}s ---',
            f'cyclic GC: {gc_state}; enabled={gc.isenabled()}; collections so far={self._gc_collections}',
            f'recent collections: {"; ".join(self._recent_gc) or "none"}',
            _coverage_lock_state(),
            'main thread Python stack, innermost last:',
            main_stack,
            '--- end hang diagnostics ---',
        ]
        stream = self._stream or sys.__stderr__ or sys.stderr
        stream.write('\n'.join(lines) + '\n')
        stream.flush()
