"""Saves and restores top-level window geometry without letting saved values outrank the current displays.

`plan_restore` is a pure function over `ScreenInfo` lists, so display layouts can be faked in tests. The Qt-facing
helpers (`current_screens`, `capture_geometry`, `apply_plan`) wrap it.
"""
import json
import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Optional

from PySide6.QtCore import QRect, QPoint, QSize, Qt
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_SIZE = QSize(1024, 600)


class WindowState(StrEnum):
    """Window states that are saved and restored."""
    NORMAL = 'normal'
    MAXIMIZED = 'maximized'
    FULL_SCREEN = 'full_screen'


@dataclass(frozen=True)
class ScreenInfo:
    """The parts of a QScreen that placement depends on."""
    name: str
    geometry: QRect
    available: QRect


@dataclass(frozen=True)
class SavedGeometry:
    """A window's normal (not maximized) bounds, its state, and the screen it was on."""
    bounds: QRect
    state: WindowState
    screen_name: str
    screen_geometry: QRect

    def to_json(self) -> str:
        """Serializes to the string stored in the cache."""
        return json.dumps({'bounds': _rect_to_list(self.bounds), 'state': str(self.state),
                           'screen_name': self.screen_name, 'screen_geometry': _rect_to_list(self.screen_geometry)})

    @staticmethod
    def from_json(text: str) -> Optional['SavedGeometry']:
        """Parses a cached string, returning None if it is empty or malformed."""
        if not text:
            return None
        try:
            data = json.loads(text)
            return SavedGeometry(_rect_from_list(data['bounds']), WindowState(data['state']),
                                 str(data['screen_name']), _rect_from_list(data['screen_geometry']))
        except (ValueError, KeyError, TypeError):
            return None


@dataclass(frozen=True)
class RestorePlan:
    """Where and how to show a window: always inside `screen`'s available geometry."""
    bounds: QRect
    state: WindowState
    screen: ScreenInfo


def _rect_to_list(rect: QRect) -> list[int]:
    return [rect.x(), rect.y(), rect.width(), rect.height()]


def _rect_from_list(values: list[int]) -> QRect:
    x, y, width, height = (int(value) for value in values)
    if width <= 0 or height <= 0:
        raise ValueError('empty rect')
    return QRect(x, y, width, height)


def _clamp_into(bounds: QRect, area: QRect) -> QRect:
    """Shrinks `bounds` to fit `area`, then moves it inside."""
    width = min(bounds.width(), area.width())
    height = min(bounds.height(), area.height())
    x = max(area.left(), min(bounds.x(), area.right() + 1 - width))
    y = max(area.top(), min(bounds.y(), area.bottom() + 1 - height))
    return QRect(x, y, width, height)


def _centered_default(area: QRect) -> QRect:
    width = min(DEFAULT_WINDOW_SIZE.width(), area.width())
    height = min(DEFAULT_WINDOW_SIZE.height(), area.height())
    return QRect(area.x() + (area.width() - width) // 2, area.y() + (area.height() - height) // 2, width, height)


def plan_restore(saved: Optional[SavedGeometry], screens: list[ScreenInfo], fallback: ScreenInfo) -> RestorePlan:
    """Chooses placement for a window on the displays that exist now.

    With no saved geometry, the window gets a default size centered on `fallback`. If the saved screen is still
    present it is reused, shifted by however far that screen's origin moved. Otherwise `fallback` is used and the
    saved size is kept only as far as it fits. Bounds are always clamped to the chosen screen's available geometry,
    and maximized or full-screen windows keep that state with clamped normal bounds.
    """
    if saved is None:
        return RestorePlan(_centered_default(fallback.available), WindowState.NORMAL, fallback)
    screen = next((candidate for candidate in screens if candidate.name == saved.screen_name), None)
    if screen is not None:
        offset = screen.geometry.topLeft() - saved.screen_geometry.topLeft()
        bounds = saved.bounds.translated(offset)
    else:
        screen = fallback
        bounds = QRect(saved.bounds)
        bounds.moveCenter(screen.available.center())
    return RestorePlan(_clamp_into(bounds, screen.available), saved.state, screen)


def current_screens() -> list[ScreenInfo]:
    """Returns the displays Qt currently reports."""
    return [ScreenInfo(screen.name(), screen.geometry(), screen.availableGeometry())
            for screen in QGuiApplication.screens()]


def fallback_screen(screens: list[ScreenInfo]) -> ScreenInfo:
    """Returns the screen under the cursor, or the primary screen, or the first screen."""
    cursor = QCursor.pos()
    for screen in screens:
        if screen.geometry.contains(cursor):
            return screen
    primary = QGuiApplication.primaryScreen()
    if primary is not None:
        for screen in screens:
            if screen.name == primary.name():
                return screen
    if screens:
        return screens[0]
    return ScreenInfo('', QRect(QPoint(0, 0), DEFAULT_WINDOW_SIZE), QRect(QPoint(0, 0), DEFAULT_WINDOW_SIZE))


def capture_geometry(window: QWidget) -> SavedGeometry:
    """Reads a window's current normal bounds, state and screen."""
    if window.isFullScreen():
        state = WindowState.FULL_SCREEN
    elif window.isMaximized():
        state = WindowState.MAXIMIZED
    else:
        state = WindowState.NORMAL
    bounds = window.geometry() if state == WindowState.NORMAL else window.normalGeometry()
    if bounds.isEmpty():
        bounds = window.geometry()
    screen = window.screen()
    return SavedGeometry(bounds, state, screen.name(), screen.geometry())


def apply_plan(window: QWidget, plan: RestorePlan) -> None:
    """Applies placement to a window that has not been shown yet."""
    window.setGeometry(plan.bounds)
    states = Qt.WindowState.WindowNoState
    if plan.state == WindowState.MAXIMIZED:
        states = Qt.WindowState.WindowMaximized
    elif plan.state == WindowState.FULL_SCREEN:
        states = Qt.WindowState.WindowFullScreen
    window.setWindowState(states)


def restore_window(window: QWidget, saved_text: str) -> None:
    """Places `window` from a cached string, falling back to defaults for empty or invalid values."""
    screens = current_screens()
    apply_plan(window, plan_restore(SavedGeometry.from_json(saved_text), screens, fallback_screen(screens)))
