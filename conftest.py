"""Shared pytest configuration for the IntraPaint test suite.

This file is imported by pytest before any test modules, which makes it the correct place to
prepare the environment that the Qt-based tests rely on:

- Force Qt's "offscreen" platform plugin so tests run headlessly (no display/X server required),
  which is what makes them work identically on a developer machine and in CI. `setdefault` is used
  so a developer can still override the platform (e.g. to watch a test render) with
  `QT_QPA_PLATFORM=xcb pytest ...`.
- Ensure the project root is importable, so `from src... import ...` works regardless of the
  directory pytest is invoked from.
- Back the config singletons with temporary copies of the `test/resources/*_test.json` fixtures, so
  tests that change settings can't rewrite the committed files.
- Fail any test that opens a modal dialog or menu. Under the offscreen platform nothing can close
  one, so it would block the whole run until the CI job times out.
"""
import os
import shutil
import sys
import tempfile
from typing import Callable, Optional

# Must run before PySide6 is imported anywhere (including by test modules at collection time):
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest
from PySide6.QtWidgets import (QApplication, QColorDialog, QDialog, QFileDialog, QFontDialog, QInputDialog, QMenu,
                               QMessageBox, QWidget)

_CONFIG_FIXTURE_DIR = os.path.join(_PROJECT_ROOT, 'test', 'resources')
_config_copy_dir: Optional[str] = None


def pytest_sessionstart(session: pytest.Session) -> None:
    """Create the config singletons from temporary copies of the committed config fixtures.

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
    _config_copy_dir = tempfile.mkdtemp(prefix='intrapaint-test-config-')
    for config_class, file_name in ((AppConfig, 'app_config_test.json'), (KeyConfig, 'key_config_test.json'),
                                    (Cache, 'cache_test.json')):
        copy_path = os.path.join(_config_copy_dir, file_name)
        shutil.copyfile(os.path.join(_CONFIG_FIXTURE_DIR, file_name), copy_path)
        config = config_class(copy_path)
        assert config.json_path == copy_path, f'{config_class.__name__} was created before pytest_sessionstart'


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Remove the temporary config copies."""
    if _config_copy_dir is not None:
        shutil.rmtree(_config_copy_dir, ignore_errors=True)


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


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """Record whether each test's body failed, for _fail_on_swallowed_modal."""
    report = yield
    if report.when == 'call':
        item.stash[_CALL_FAILED] = report.failed
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
