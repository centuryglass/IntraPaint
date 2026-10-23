"""Fails a test that leaves PySide wrappers in a reference cycle, so the test that makes a cycle is the one that fails.

A cycle that holds a wrapper waits for the next cyclic collection. That collection can run inside an unrelated Qt call
in a later test and delete C++ objects there, where the crash points at the wrong test. So while a test runs, the
collector saves what it finds in `gc.garbage` (`gc.DEBUG_SAVEALL`) instead of freeing it. `collect` counts the
wrappers in that garbage and then frees all of it, at points the test controls: `IntraPaintTestCase.tearDown`, and
`pytest_runtest_teardown` in `conftest.py` after pytest has dropped the test's instance. A test that checks that a
collection frees something turns `gc.DEBUG_SAVEALL` off around it.

Only wrappers of objects that C++ can point to count (`TRACKED_TYPES`). Value types such as `QColor`, and mocks that
pass `isinstance` checks for a Qt class, are safe to free at any time.

`BASELINE_PATH` lists the tests that already leave such cycles, with the most wrappers each has left. A test fails
when it leaves more than its entry, or none at all, so the entry of a test whose cycles are fixed gets removed. A test
can leave a few fewer wrappers than its entry depending on which tests ran before it, so a count under the entry
passes. Lower entries after a fix by running the full suite with `UPDATE_ENV_VAR=1`, which rewrites the entries of the
tests that ran and passed instead of failing them.

Counts differ between Python versions, since each version leaves different garbage, so they are compared and
recorded only on `BASELINE_PYTHON`. Every version still frees cycles at the fixed points.

Running pytest with `REPORT_ENV_VAR=<path>` also writes a JSON report of every passing test that left wrappers in
cycles: the wrapper types, and the project functions and bound methods found in the cycles, which name the code that
made them.
"""
import gc
import json
import os
import sys
import types
from collections import Counter
from typing import Optional

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QGraphicsItem, QLayoutItem
from shiboken6 import Shiboken

BASELINE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'qt_cycle_baseline.json')
UPDATE_ENV_VAR = 'INTRAPAINT_UPDATE_CYCLE_BASELINE'
REPORT_ENV_VAR = 'INTRAPAINT_CYCLE_REPORT'
BASELINE_PYTHON = (3, 13)
TRACKED_TYPES = (QObject, QGraphicsItem, QLayoutItem)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MAX_LISTED = 8


class _Tally:
    """What the cycles freed during the current test held."""

    def __init__(self) -> None:
        self.wrapper_types: Counter[str] = Counter()
        self.functions: Counter[str] = Counter()
        self.started = False

    @property
    def wrapper_count(self) -> int:
        """Returns the number of PySide wrappers the cycles held."""
        return sum(self.wrapper_types.values())


_tally = _Tally()
_baseline: Optional[dict[str, int]] = None
_updated: dict[str, int] = {}
_report: dict[str, dict] = {}


def _describe_function(obj: object) -> Optional[str]:
    """Names a function or bound method from the project's own code, or returns None for anything else."""
    if isinstance(obj, types.MethodType):
        if not issubclass(type(obj.__self__), Shiboken.Object):
            return None
        return f'{type(obj.__self__).__qualname__}.{obj.__func__.__name__} (bound method)'
    if isinstance(obj, types.FunctionType):
        code = obj.__code__
        if not code.co_filename.startswith(_PROJECT_ROOT + os.sep) or 'site-packages' in code.co_filename:
            return None
        return f'{code.co_qualname} ({os.path.relpath(code.co_filename, _PROJECT_ROOT)}:{code.co_firstlineno})'
    return None


def start_test() -> None:
    """Frees garbage from before the test uncounted, then saves the garbage that collections find during it.

    Everything alive at the start is frozen (`gc.freeze`), so collections during the test only walk objects it
    created. A cycle that includes an object from before the test isn't counted, and is freed when the next test
    starts.
    """
    gc.set_debug(0)
    gc.unfreeze()
    gc.collect()
    gc.garbage.clear()
    gc.freeze()
    gc.set_debug(gc.DEBUG_SAVEALL)
    _tally.__init__()
    _tally.started = True


def stop() -> None:
    """Frees any saved garbage and lets the collector walk and free all objects as usual."""
    gc.set_debug(0)
    gc.garbage.clear()
    gc.unfreeze()
    gc.collect()


def collect() -> None:
    """Collects cycles, counts the PySide wrappers they hold, and frees them.

    Wrappers in the garbage are still alive until this returns, so code that counts live wrappers runs after it.
    """
    debug_flags = gc.get_debug()
    gc.collect()
    gc.set_debug(0)
    for obj in gc.garbage:
        # type() rather than isinstance, which a mock with a Qt spec passes:
        if issubclass(type(obj), TRACKED_TYPES):
            _tally.wrapper_types[type(obj).__qualname__] += 1
        else:
            name = _describe_function(obj)
            if name is not None:
                _tally.functions[name] += 1
    if gc.garbage:
        gc.garbage.clear()
        gc.collect()
    gc.set_debug(debug_flags)


def finish_test(test_id: str, test_failed: bool) -> Optional[str]:
    """Frees what the test left, stops saving garbage, and returns a failure message if its wrapper count is off.

    A failed test, or one whose setup failed, is never reported or recorded, since its traceback can hold objects that
    a passing run frees.
    """
    collect()
    gc.set_debug(0)
    count = _tally.wrapper_count
    started = _tally.started
    wrapper_types, functions = _tally.wrapper_types, _tally.functions
    _tally.__init__()
    if test_failed or not started:
        return None
    if sys.version_info[:2] != BASELINE_PYTHON:
        return None
    if count and os.environ.get(REPORT_ENV_VAR):
        _report[test_id] = {'wrappers': count, 'wrapper_types': dict(wrapper_types.most_common()),
                            'functions': dict(functions.most_common())}
    if os.environ.get(UPDATE_ENV_VAR):
        _updated[test_id] = count
        return None
    expected = _load_baseline().get(test_id, 0)
    if count == 0 and expected > 0:
        return (f'This test left no PySide wrappers in reference cycles, but has an entry in '
                f'{os.path.relpath(BASELINE_PATH, _PROJECT_ROOT)}. Remove the entry, or rerun the full suite with '
                f'{UPDATE_ENV_VAR}=1.')
    if count <= expected:
        return None
    types_listed = ', '.join(f'{name} x{n}' for name, n in wrapper_types.most_common(_MAX_LISTED))
    lines = [f'This test left {count} PySide wrappers in reference cycles (baseline {expected}), which the garbage '
             f'collector would delete at an unpredictable time. See test/qt_cycles.py.',
             f'Wrappers: {types_listed}']
    if functions:
        lines.append('Functions in the cycles: ' + '; '.join(name for name, _ in functions.most_common(_MAX_LISTED)))
    return '\n'.join(lines)


def _load_baseline() -> dict[str, int]:
    global _baseline  # pylint: disable=global-statement
    if _baseline is None:
        try:
            with open(BASELINE_PATH, encoding='utf-8') as baseline_file:
                _baseline = json.load(baseline_file)
        except FileNotFoundError:
            _baseline = {}
    return _baseline


def write_baseline() -> None:
    """In update mode, writes the counts recorded this session into the baseline, keeping entries for tests not run."""
    if not os.environ.get(UPDATE_ENV_VAR):
        return
    if sys.version_info[:2] != BASELINE_PYTHON:
        print(f'\n{UPDATE_ENV_VAR} ignored: the cycle baseline is recorded on Python '
              f'{".".join(map(str, BASELINE_PYTHON))}.', file=sys.stderr)
        return
    baseline = dict(_load_baseline())
    for test_id, count in _updated.items():
        if count:
            baseline[test_id] = count
        else:
            baseline.pop(test_id, None)
    with open(BASELINE_PATH, 'w', encoding='utf-8') as baseline_file:
        json.dump(dict(sorted(baseline.items())), baseline_file, indent=2)
        baseline_file.write('\n')


def write_report() -> None:
    """Writes the report `REPORT_ENV_VAR` names, if it is set. Reports are only recorded on `BASELINE_PYTHON`."""
    report_path = os.environ.get(REPORT_ENV_VAR)
    if not report_path:
        return
    with open(report_path, 'w', encoding='utf-8') as report_file:
        json.dump(dict(sorted(_report.items())), report_file, indent=2)
        report_file.write('\n')
