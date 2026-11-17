"""Fails a test that leaves PySide wrappers in a reference cycle, so the test that makes a cycle is the one that fails.

A cycle that holds a wrapper waits for the next cyclic collection. That collection can run inside an unrelated Qt call
in a later test and delete C++ objects there, where the crash points at the wrong test. So while a test runs, the
collector saves what it finds in `gc.garbage` (`gc.DEBUG_SAVEALL`) instead of freeing it. `collect` counts the
wrappers in that garbage and then frees all of it, at points the test controls: `IntraPaintTestCase.tearDown`, and
`pytest_runtest_teardown` in `conftest.py` after pytest has dropped the test's instance. A test that checks that a
collection frees something turns `gc.DEBUG_SAVEALL` off around it.

Only wrappers of objects that C++ can point to count (`TRACKED_TYPES`). Value types such as `QColor`, and mocks that
pass `isinstance` checks for a Qt class, are safe to free at any time.

A test fails when it leaves any such wrappers in cycles.

Counts differ between Python versions, since each version leaves different garbage, so they are checked only on
`CHECK_PYTHON`. Every version still frees cycles at the fixed points.

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

REPORT_ENV_VAR = 'INTRAPAINT_CYCLE_REPORT'
CHECK_PYTHON = (3, 13)
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
_report: dict[str, dict] = {}
_module_path: Optional[str] = None


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


def start_test(module_path: str) -> None:
    """Frees garbage from before the test uncounted, then saves the garbage that collections find during it.

    Everything alive at the start is frozen (`gc.freeze`), so collections during the test only walk objects it
    created. A cycle that includes an object from before the test isn't counted.

    Only the first test of each module unfreezes and collects the whole heap, which grows over the run. Other tests
    collect only what was created since the last freeze. A cycle that includes a frozen object is freed at the next
    module's first test. Collecting the whole heap less often leaves that garbage alive across more tests, where it
    can break them.
    """
    global _module_path  # pylint: disable=global-statement
    gc.set_debug(0)
    if module_path != _module_path:
        _module_path = module_path
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
    if sys.version_info[:2] != CHECK_PYTHON:
        return None
    if count and os.environ.get(REPORT_ENV_VAR):
        _report[test_id] = {'wrappers': count, 'wrapper_types': dict(wrapper_types.most_common()),
                            'functions': dict(functions.most_common())}
    if count == 0:
        return None
    types_listed = ', '.join(f'{name} x{n}' for name, n in wrapper_types.most_common(_MAX_LISTED))
    lines = [f'This test left {count} PySide wrappers in reference cycles, which the garbage '
             f'collector would delete at an unpredictable time. See test/qt_cycles.py.',
             f'Wrappers: {types_listed}']
    if functions:
        lines.append('Functions in the cycles: ' + '; '.join(name for name, _ in functions.most_common(_MAX_LISTED)))
    return '\n'.join(lines)


def write_report() -> None:
    """Writes the report `REPORT_ENV_VAR` names, if it is set. Reports are only recorded on `CHECK_PYTHON`."""
    report_path = os.environ.get(REPORT_ENV_VAR)
    if not report_path:
        return
    with open(report_path, 'w', encoding='utf-8') as report_file:
        json.dump(dict(sorted(_report.items())), report_file, indent=2)
        report_file.write('\n')
