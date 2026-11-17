"""Tests that the app does no work while idle: its layout settles, and nothing animates or polls without a reason.

An idle app that keeps working burns CPU while minimized or in the background, which no functional test notices. Each
check here is deterministic: the app settles in rounds that deliver posted events and fire pending single-shot timers
without running the event loop, and repeating timers and animations are inspected rather than waited on.
"""
import gc
import sys
from collections import Counter
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QAbstractAnimation, QCoreApplication, QEvent, QObject, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from src.controller.app_controller import AppController
from src.hotkey_filter import HotkeyFilter
from src.ui.graphics_items.outline import Outline
from src.ui.window.dock_groups import docked_groups
from src.util.application_state import AppStateTracker, APP_STATE_EDITING
from src.util.arg_parser import build_arg_parser
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

# Rounds the window gets to settle after showing. It settles in under ten.
SETTLE_ROUNDS = 50

# Events that mean the window is still laying out or repainting after it settled.
WORK_EVENTS = {QEvent.Type.LayoutRequest, QEvent.Type.Show, QEvent.Type.Hide, QEvent.Type.Resize, QEvent.Type.Move,
               QEvent.Type.UpdateRequest, QEvent.Type.UpdateLater, QEvent.Type.PolishRequest}

# Repeating timers shorter than this wake the app too often to run while idle, allowed or not.
MIN_IDLE_TIMER_INTERVAL_MS = 50


@dataclass(frozen=True)
class _AllowedTimer:
    """A repeating timer the idle app may run, owned by an object of `owner_type`."""
    owner_type: type
    while_unfocused: bool
    reason: str


ALLOWED_IDLE_TIMERS = [
    _AllowedTimer(HotkeyFilter, False, 'polls modifier keys while an IntraPaint window has focus'),
    _AllowedTimer(Outline, True, 'animates the dashes of an outline drawn in the image view'),
]


class _EventCounter(QObject):
    """Counts the events the application delivers, by event type and receiver class."""

    def __init__(self) -> None:
        super().__init__()
        self.counts: Counter[tuple[str, str]] = Counter()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # pylint: disable=invalid-name
        """Counts work events, without filtering them."""
        if event.type() in WORK_EVENTS:
            self.counts[(event.type().name, type(watched).__name__)] += 1
        return False


def _owner_chain(obj: QObject) -> str:
    """Names an object and its parents, for failure messages."""
    names = []
    current: Optional[QObject] = obj
    while current is not None:
        names.append(type(current).__name__)
        current = current.parent()
    return ' < '.join(names)


def _app_timers_and_animations() -> tuple[list[QTimer], list[QAbstractAnimation]]:
    """Returns every Python-wrapped timer that is active, and every animation that is running.

    Qt's own internal timers have no Python wrapper, so this covers what IntraPaint itself starts. `gc.get_objects`
    only finds objects the running test created, since the cycle check freezes older ones (`qt_cycles.start_test`).
    Objects that outlive every test are added from their owners, so each test checks them.
    """
    timers: list[QTimer] = []
    animations: list[QAbstractAnimation] = []
    long_lived: list[QObject] = HotkeyFilter.instance().findChildren(QObject)
    found: dict[int, object] = {id(obj): obj for obj in gc.get_objects()}
    found.update({id(obj): obj for obj in long_lived})
    for obj in found.values():
        try:
            if isinstance(obj, QTimer) and obj.isActive():
                timers.append(obj)
            elif isinstance(obj, QAbstractAnimation) and obj.state() == QAbstractAnimation.State.Running:
                animations.append(obj)
        except RuntimeError:  # The wrapped C++ object is already deleted.
            continue
    return timers, animations


def _fire_pending_single_shot_timers() -> list[str]:
    """Fires every pending single-shot timer now, as if its interval had passed, and names the timers fired."""
    timers = [timer for timer in _app_timers_and_animations()[0] if timer.isSingleShot()]
    for timer in timers:
        timer.stop()
        timer.timeout.emit()
    return [_owner_chain(timer) for timer in timers]


class IdleActivityTest(IntraPaintTestCase):
    """Shows the main window, lets it settle, then checks that nothing keeps it busy."""

    def setUp(self) -> None:
        super().setUp()
        args = build_arg_parser(include_edit_params=False).parse_args(['--window_size', '800x600', '--mode', 'mock'])
        args.mode = 'mock'
        args.server_url = ''
        args.fast_ngrok_connection = False
        self.controller = AppController(args)
        self.window = self.controller._window
        self.window.show()
        AppStateTracker.set_app_state(APP_STATE_EDITING)

    def tearDown(self) -> None:
        self.window.hide()
        super().tearDown()

    @staticmethod
    def _settle_round() -> list[str]:
        """Delivers posted events, then fires pending single-shot timers, returning the timers fired."""
        QCoreApplication.sendPostedEvents()
        return _fire_pending_single_shot_timers()

    def _settle(self) -> tuple[Counter[tuple[str, str]], list[str]]:
        """Settles the window in rounds until it should be idle, then returns one more round's events and timers."""
        for _ in range(SETTLE_ROUNDS):
            self._settle_round()
        counter = _EventCounter()
        app.installEventFilter(counter)
        try:
            fired = self._settle_round()
        finally:
            app.removeEventFilter(counter)
        return counter.counts, fired

    def _assert_settled(self) -> None:
        events, fired = self._settle()
        self.assertEqual(events, Counter(), 'the window keeps laying itself out or repainting while idle, receiving '
                                            f'these events every round: {dict(events)}')
        self.assertEqual(fired, [], 'single-shot timers keep restarting while idle, so whatever they trigger repeats '
                                    'forever')

    def _assert_only_allowed_timers(self, focused: bool) -> None:
        timers, animations = _app_timers_and_animations()
        timers = [timer for timer in timers if not timer.isSingleShot()]
        self.assertEqual([_owner_chain(anim) for anim in animations], [],
                         'animations run while idle: Qt ticks every running animation at the full frame rate. Use a '
                         'low-rate QTimer, and stop it while the item is hidden.')
        unexpected = []
        for timer in timers:
            owner = timer.parent()
            allowed = next((entry for entry in ALLOWED_IDLE_TIMERS if isinstance(owner, entry.owner_type)), None)
            if allowed is None or (not focused and not allowed.while_unfocused) \
                    or timer.interval() < MIN_IDLE_TIMER_INTERVAL_MS:
                unexpected.append(f'{_owner_chain(timer)}, every {timer.interval()}ms')
        self.assertEqual(unexpected, [], 'repeating timers run while idle. Stop them while they have nothing to do, '
                                         'or add them to ALLOWED_IDLE_TIMERS with a reason.')

    def test_window_layout_settles(self) -> None:
        """The window stops laying itself out once shown."""
        self._assert_settled()

    def test_window_layout_settles_with_tab_groups_open(self) -> None:
        """The window settles with every dock of each tab group open, as a restored layout can leave them.

        Qt shows a group's tab bar while several of its docks are open, so this covers the tab bars staying out of the
        layout without relaying it out forever (`hide_dock_tab_bars`).
        """
        for group in docked_groups(self.window, self.window.docks):
            for dock in group:
                dock.show()
        self._assert_settled()

    def test_idle_app_runs_only_allowed_timers(self) -> None:
        """Once settled, the focused app runs no animations, and only the repeating timers it needs."""
        self._settle()
        self._assert_only_allowed_timers(focused=True)

    def test_unfocused_app_runs_only_allowed_timers(self) -> None:
        """With no IntraPaint window focused, the app stops the timers it only needs while focused."""
        self._settle()
        focus_window = QGuiApplication.focusWindow()
        app.focusWindowChanged.emit(None)
        try:
            self._assert_only_allowed_timers(focused=False)
        finally:
            # HotkeyFilter is shared by every test, so it goes back to watching the focused window:
            app.focusWindowChanged.emit(focus_window)
