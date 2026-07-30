"""Shared pytest configuration for the IntraPaint test suite.

This file is imported by pytest before any test modules, which makes it the correct place to
prepare the environment that the Qt-based tests rely on:

- Force Qt's "offscreen" platform plugin so tests run headlessly (no display/X server required),
  which is what makes them work identically on a developer machine and in CI. `setdefault` is used
  so a developer can still override the platform (e.g. to watch a test render) with
  `QT_QPA_PLATFORM=xcb pytest ...`.
- Ensure the project root is importable, so `from src... import ...` works regardless of the
  directory pytest is invoked from.
"""
import os
import sys

# Must run before PySide6 is imported anywhere (including by test modules at collection time):
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope='session', autouse=True)
def qapplication():
    """Guarantee exactly one QApplication for the whole test session.

    Existing tests each create their own `QApplication.instance() or QApplication(sys.argv)` at import
    time, which is idempotent and remains valid. This fixture makes that instance available as a
    session-scoped fixture so future tests can depend on it explicitly instead of repeating the idiom.
    """
    app = QApplication.instance() or QApplication(sys.argv)
    yield app
