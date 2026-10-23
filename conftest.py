"""Shared pytest configuration for the IntraPaint test suite.

This file is imported by pytest before any test modules, which makes it the correct place to
prepare the environment that the Qt-based tests rely on:

- Force Qt's "offscreen" platform plugin so tests run headlessly (no display/X server required),
  which is what makes them work identically on a developer machine and in CI. `setdefault` is used
  so a developer can still override the platform (e.g. to watch a test render) with
  `QT_QPA_PLATFORM=xcb pytest ...`.
- Point `INTRAPAINT_DATA_DIR` and `INTRAPAINT_LOG_DIR` at a temporary directory before any `src` import, so test
  runs never create or write files in the developer's real user data and log directories.
- On Linux, point fontconfig at a configuration with no font directories, so Qt sees only the fonts the theme bundles.
  Text then lays out the same whatever fonts a machine has installed. A developer's own `FONTCONFIG_FILE` wins.
- Ensure the project root is importable, so `from src... import ...` works regardless of the
  directory pytest is invoked from.
- Back the config singletons with temporary copies of the `test/resources/*_test.json` fixtures, so
  tests that change settings can't rewrite the committed files.
- Apply the style, theme and font size from the app config fixture, so text metrics and colors match on every
  machine instead of following the platform's default font and palette.
- Fail any test during which `HotkeyFilter` received an event source that isn't a QObject, the sign of a stale PySide
  wrapper. Failing where it is first seen narrows down which test left it.
- Flush C stdio after each test, so output native libraries print is captured with the test.
- Fail any test that opens a modal dialog or menu. Under the offscreen platform nothing can close
  one, so it would block the whole run until the CI job times out.
- On Python 3.12 and up, keep the last few exceptions raised in the project's own code. A failure that says a Qt call "returned
  NULL without setting an exception" gets a report section listing them and the test that ran before it, since
  PySide lost the exception that caused it (issue #283).
- Fail any test that leaves PySide wrappers in a reference cycle, beyond its entry in the baseline
  (`test/qt_cycles.py`).
- Report GC state when a test runs for two minutes, ahead of pytest's thread dump
  (`test/hang_diagnostics.py`, issue #390).
"""
import ctypes
import os
import shutil
import sys
import tempfile
from collections import deque
from types import CodeType
from typing import Callable, Optional

# Must run before PySide6 is imported anywhere (including by test modules at collection time):
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

# Must run before src.util.shared_constants is imported, which reads these to set DATA_DIR and LOG_DIR:
_user_dir_root = tempfile.mkdtemp(prefix='intrapaint-test-user-dirs-')
os.environ['INTRAPAINT_DATA_DIR'] = os.path.join(_user_dir_root, 'data')
os.environ['INTRAPAINT_LOG_DIR'] = os.path.join(_user_dir_root, 'log')

# Must run before PySide6 loads fontconfig:
if sys.platform.startswith('linux') and 'FONTCONFIG_FILE' not in os.environ:
    _fontconfig_path = os.path.join(_user_dir_root, 'fonts.conf')
    _fontconfig_cache = os.path.join(_user_dir_root, 'fontconfig-cache')
    with open(_fontconfig_path, 'w', encoding='utf-8') as _fontconfig_file:
        _fontconfig_file.write('<?xml version="1.0"?>\n<!DOCTYPE fontconfig SYSTEM "fonts.dtd">\n'
                               f'<fontconfig><cachedir>{_fontconfig_cache}</cachedir></fontconfig>\n')
    os.environ['FONTCONFIG_FILE'] = _fontconfig_path

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest
from PySide6.QtWidgets import (QApplication, QColorDialog, QDialog, QFileDialog, QFontDialog, QInputDialog, QMenu,
                               QMessageBox, QWidget)

from test import qt_cycles
from test.hang_diagnostics import HangWatchdog

_hang_watchdog = HangWatchdog()
_CONFIG_FIXTURE_DIR = os.path.join(_PROJECT_ROOT, 'test', 'resources')
_config_copy_dir: Optional[str] = None


def pytest_sessionstart(session: pytest.Session) -> None:
    """Create the config singletons from temporary copies of the committed config fixtures, then apply their appearance.

    This runs before test collection. Config classes are singletons, so these are the instances every later
    `AppConfig('test/resources/app_config_test.json')`-style call returns, and the path in those calls is ignored.
    """
    global _config_copy_dir  # pylint: disable=global-statement
    _ = QApplication.instance() or QApplication(sys.argv)
    # Imported here rather than at module level so PySide6 and the QApplication are ready first:
    # pylint: disable=import-outside-toplevel
    from src.config.application_config import AppConfig
    from src.config.cache import Cache
    from src.config.key_config import KeyConfig
    from src.util import shared_constants
    assert shared_constants.DATA_DIR == os.environ['INTRAPAINT_DATA_DIR'], \
        'src.util.shared_constants was imported before conftest.py set INTRAPAINT_DATA_DIR'
    _config_copy_dir = tempfile.mkdtemp(prefix='intrapaint-test-config-')
    for config_class, file_name in ((AppConfig, 'app_config_test.json'), (KeyConfig, 'key_config_test.json'),
                                    (Cache, 'cache_test.json')):
        copy_path = os.path.join(_config_copy_dir, file_name)
        shutil.copyfile(os.path.join(_CONFIG_FIXTURE_DIR, file_name), copy_path)
        config = config_class(copy_path)
        assert config.json_path == copy_path, f'{config_class.__name__} was created before pytest_sessionstart'
    from src.ui.theme import apply_font_point_size, apply_overlay_scroll_bars, apply_rounded_popups, apply_style, \
        apply_theme
    app_config = AppConfig()
    apply_overlay_scroll_bars(app_config.get(AppConfig.OVERLAY_SCROLL_BARS))
    apply_rounded_popups(app_config.get(AppConfig.ROUNDED_POPUPS))
    apply_style(app_config.get(AppConfig.STYLE))
    apply_theme(app_config.get(AppConfig.THEME))
    apply_font_point_size(app_config.get(AppConfig.FONT_POINT_SIZE))


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Write the cycle baseline and report when asked to, and remove the temporary config copies and user directories."""
    qt_cycles.stop()
    qt_cycles.write_baseline()
    qt_cycles.write_report()
    if _config_copy_dir is not None:
        shutil.rmtree(_config_copy_dir, ignore_errors=True)
    shutil.rmtree(_user_dir_root, ignore_errors=True)


@pytest.fixture(scope='session', autouse=True)
def qapplication():
    """Guarantee exactly one QApplication for the whole test session.

    Existing tests each create their own `QApplication.instance() or QApplication(sys.argv)` at import
    time, which is idempotent and remains valid. This fixture makes that instance available as a
    session-scoped fixture so future tests can depend on it explicitly instead of repeating the idiom.
    """
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


class UnexpectedModalDialog(AssertionError):
    """Raised in place of opening a modal dialog or menu during a test."""


# Every modal the current test tried to open, including ones whose exception a Qt slot swallowed:
_blocked_modals: list[str] = []


def _block_modal(description: str) -> None:
    _blocked_modals.append(description)
    raise UnexpectedModalDialog(f'{description} opened during a test, where it would block forever. Mock it, or '
                                'avoid the code path that opens it.')


def _blocked_exec(self, *_args, **_kwargs) -> None:
    if not isinstance(self, QWidget):  # QMenu's static exec(actions, pos) overload
        _block_modal('QMenu.exec')
    text = f': {self.text()}' if isinstance(self, QMessageBox) else ''
    _block_modal(f'{type(self).__name__} "{self.windowTitle()}"{text}')


def _blocked_static(name: str) -> Callable[..., None]:
    def _blocked(*_args, **_kwargs) -> None:
        _block_modal(name)
    return _blocked


@pytest.fixture(scope='session', autouse=True)
def _block_modal_dialogs():
    """Replace every modal entry point the app uses with one that raises UnexpectedModalDialog.

    QDialog subclasses inherit the patched `exec`. The static convenience functions run their own event loop in
    C++, so they are patched individually.
    """
    with pytest.MonkeyPatch.context() as patch:
        for widget_class in (QDialog, QMenu):
            patch.setattr(widget_class, 'exec', _blocked_exec)
            if hasattr(widget_class, 'exec_'):
                patch.setattr(widget_class, 'exec_', _blocked_exec)
        for widget_class, function_names in (
                (QMessageBox, ('critical', 'warning', 'information', 'question', 'about')),
                (QFileDialog, ('getOpenFileName', 'getOpenFileNames', 'getSaveFileName', 'getExistingDirectory')),
                (QInputDialog, ('getText', 'getInt', 'getDouble', 'getItem', 'getMultiLineText')),
                (QColorDialog, ('getColor',)),
                (QFontDialog, ('getFont',))):
            for function_name in function_names:
                patch.setattr(widget_class, function_name,
                              staticmethod(_blocked_static(f'{widget_class.__name__}.{function_name}')))
        yield


_CALL_FAILED = pytest.StashKey[bool]()
_CALL_XFAILED = pytest.StashKey[bool]()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """Record whether each test's body failed, or failed as an xfail marker expected, for the checks that follow it."""
    report = yield
    if report.when == 'call':
        item.stash[_CALL_FAILED] = report.failed
        item.stash[_CALL_XFAILED] = hasattr(report, 'wasxfail')
    return report


@pytest.fixture(autouse=True)
def _fail_on_swallowed_modal(request: pytest.FixtureRequest):
    """Fail a test that tried to open a modal dialog even if the exception never reached it.

    PySide prints and discards exceptions raised inside Qt slots, so a dialog opened from a signal handler would
    otherwise pass silently with its slot cut short. A test whose body already failed is left alone, so the failure
    is reported once.
    """
    _blocked_modals.clear()
    yield
    if _blocked_modals and not request.node.stash.get(_CALL_FAILED, False):
        pytest.fail(f'Modal dialog blocked during the test: {"; ".join(_blocked_modals)}', pytrace=False)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item: pytest.Item):
    """Start counting the PySide wrappers in reference cycles once the test's fixtures are set up (test/qt_cycles.py)."""
    result = yield
    qt_cycles.start_test()
    return result


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(item: pytest.Item, nextitem: Optional[pytest.Item]):
    """Fail a test whose count of PySide wrappers left in reference cycles doesn't fit its baseline entry.

    This runs after teardown, when pytest has dropped a unittest test's instance and the objects its attributes held.
    A test whose body failed, even as an xfail marker expected, is left alone: its traceback can hold objects that a
    passing run frees.
    """
    result = yield
    message = qt_cycles.finish_test(item.nodeid, item.stash.get(_CALL_FAILED, False)
                                    or item.stash.get(_CALL_XFAILED, False))
    if message is not None:
        pytest.fail(message, pytrace=False)
    return result


@pytest.fixture(autouse=True)
def _fail_on_stale_hotkey_source(request: pytest.FixtureRequest):
    """Fail a test during which `HotkeyFilter.eventFilter` received a source that isn't a QObject.

    The filter returns False for such a source, and PySide would discard an exception raised there, so the hook only
    records the source's type. A test whose body already failed is left alone, so the failure is reported once.
    """
    from src.hotkey_filter import HotkeyFilter  # pylint: disable=import-outside-toplevel
    stale_types: list[str] = []
    HotkeyFilter.stale_source_hook = lambda source: stale_types.append(type(source).__qualname__)
    try:
        yield
    finally:
        HotkeyFilter.stale_source_hook = None
    if stale_types and not request.node.stash.get(_CALL_FAILED, False):
        pytest.fail(f'HotkeyFilter received non-QObject event sources, stale PySide wrappers: '
                    f'{", ".join(sorted(set(stale_types)))}', pytrace=False)


# The C runtime libmypaint writes through. The Windows libmypaint build links msvcrt, not Python's own C runtime.
_libc = ctypes.cdll.msvcrt if sys.platform == 'win32' else ctypes.CDLL(None)


@pytest.fixture(autouse=True)
def _flush_c_stdout():
    """Flush C stdio after each test, so pytest captures native libraries' output with the test that caused it.

    libmypaint prints "Time is running backwards!" during some strokes, from rounding in its own dab interpolation.
    C stdout is block-buffered when piped, so unflushed lines would otherwise appear after pytest's summary.
    """
    yield
    _libc.fflush(None)


# Text of the SystemError PySide raises when a Python override it called raised and the exception was lost:
_LOST_EXCEPTION_TEXT = 'without setting an exception'
_RECENT_RAISE_LIMIT = 20
_MAX_RAISE_MESSAGE_LENGTH = 300
# (code, bytecode offset, message) for each recent exception raised in the project's own code, oldest first:
_recent_raises: deque[tuple[CodeType, int, str]] = deque(maxlen=_RECENT_RAISE_LIMIT)
# The raises before the latest lost-exception SystemError, until a failed test report takes them:
_raises_before_lost_exception: Optional[list[str]] = None
_monitoring_tool_id: Optional[int] = None
_current_test: Optional[str] = None
_previous_test: Optional[str] = None


def _describe_raise(code: CodeType, offset: int, message: str) -> str:
    line = next((line for start, end, line in code.co_lines() if start <= offset < end), None)
    return f'{code.co_filename}:{line} in {code.co_qualname}: {message}'


def _is_project_code(code: CodeType) -> bool:
    filename = code.co_filename
    return filename.startswith(_PROJECT_ROOT + os.sep) and 'site-packages' not in filename


def _record_raise(code: CodeType, offset: int, exception: BaseException) -> None:
    """A `sys.monitoring` RAISE callback. It keeps no reference to the exception, so no frames or widgets stay alive.

    Exceptions raised outside the project, as by pytest, aren't recorded. A lost-exception SystemError always is.
    """
    global _raises_before_lost_exception
    if not isinstance(exception, SystemError) and not _is_project_code(code):
        return
    try:
        message = f'{type(exception).__qualname__}: {exception}'
    except Exception:  # pylint: disable=broad-exception-caught
        message = type(exception).__qualname__
    if _LOST_EXCEPTION_TEXT in message and _raises_before_lost_exception is None:
        _raises_before_lost_exception = [_describe_raise(*entry) for entry in _recent_raises]
    _recent_raises.append((code, offset, message[:_MAX_RAISE_MESSAGE_LENGTH]))


def pytest_configure(config: pytest.Config) -> None:
    """Starts recording raised exceptions, using the first free `sys.monitoring` tool ID."""
    global _monitoring_tool_id
    _hang_watchdog.start()
    monitoring = getattr(sys, 'monitoring', None)
    if monitoring is None:
        return
    for tool_id in range(6):
        if monitoring.get_tool(tool_id) is None:
            monitoring.use_tool_id(tool_id, 'intrapaint-test-raises')
            monitoring.register_callback(tool_id, monitoring.events.RAISE, _record_raise)
            monitoring.set_events(tool_id, monitoring.events.RAISE)
            _monitoring_tool_id = tool_id
            return


def pytest_unconfigure(config: pytest.Config) -> None:
    """Stops recording raised exceptions."""
    global _monitoring_tool_id
    _hang_watchdog.stop()
    if _monitoring_tool_id is not None:
        sys.monitoring.set_events(_monitoring_tool_id, sys.monitoring.events.NO_EVENTS)
        sys.monitoring.free_tool_id(_monitoring_tool_id)
        _monitoring_tool_id = None


def pytest_runtest_logstart(nodeid: str, location: tuple) -> None:
    """Tracks the test that ran before the current one, and drops raises recorded for an earlier test."""
    global _current_test, _previous_test, _raises_before_lost_exception
    _previous_test = _current_test
    _current_test = nodeid
    _hang_watchdog.test_started(nodeid)
    _raises_before_lost_exception = None


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Adds the raises recorded before a lost-exception SystemError to the failure that reports it."""
    global _raises_before_lost_exception
    if not report.failed or _raises_before_lost_exception is None \
            or _LOST_EXCEPTION_TEXT not in str(report.longrepr):
        return
    lines = [f'Previous test: {_previous_test}', 'Exceptions raised in project code before it, oldest first:',
             *_raises_before_lost_exception]
    report.sections.append(('Raises before the lost exception (issue #283)', '\n'.join(lines)))
    _raises_before_lost_exception = None


def pytest_runtest_logfinish(nodeid: str, location: tuple) -> None:
    """Stops the hang watchdog's clock once a test and its fixtures have finished."""
    _hang_watchdog.test_finished()
