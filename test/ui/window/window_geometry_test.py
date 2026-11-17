"""Tests window geometry restore against fake display layouts."""
import sys

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication, QWidget

from src.ui.window.window_geometry import capture_geometry, restore_window, SavedGeometry, ScreenInfo, WindowState, plan_restore, DEFAULT_WINDOW_SIZE
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

BIG = ScreenInfo('big', QRect(0, 0, 3840, 2160), QRect(0, 0, 3840, 2120))
SMALL = ScreenInfo('small', QRect(0, 0, 1366, 768), QRect(0, 0, 1366, 728))
SECOND = ScreenInfo('second', QRect(3840, 0, 1920, 1080), QRect(3840, 0, 1920, 1040))


def _saved(screen: ScreenInfo, bounds: QRect, state: WindowState = WindowState.NORMAL) -> SavedGeometry:
    return SavedGeometry(bounds, state, screen.name, screen.geometry)


class WindowGeometryTest(IntraPaintTestCase):
    """Checks `plan_restore` and the saved-geometry JSON format."""

    def test_json_round_trip(self) -> None:
        """Saved geometry survives serialization."""
        saved = _saved(BIG, QRect(10, 20, 800, 600), WindowState.MAXIMIZED)
        self.assertEqual(SavedGeometry.from_json(saved.to_json()), saved)

    def test_invalid_json_is_ignored(self) -> None:
        """Empty, malformed or degenerate values load as no saved geometry."""
        for text in ('', 'x', '{}', '{"bounds": [0, 0, 0, 0], "state": "normal", "screen_name": "a", '
                                    '"screen_geometry": [0, 0, 10, 10]}'):
            self.assertIsNone(SavedGeometry.from_json(text), text)

    def test_no_saved_geometry_uses_default_size(self) -> None:
        """Without saved geometry the window gets about 1024x600, centered on the fallback screen."""
        plan = plan_restore(None, [BIG], BIG)
        self.assertEqual(plan.bounds.size(), DEFAULT_WINDOW_SIZE)
        self.assertEqual(plan.bounds.center(), BIG.available.center())
        self.assertEqual(plan.state, WindowState.NORMAL)

    def test_same_screen_restores_bounds(self) -> None:
        """A saved window on a screen that still exists keeps its bounds."""
        saved = _saved(BIG, QRect(100, 200, 1500, 900))
        plan = plan_restore(saved, [BIG, SECOND], SECOND)
        self.assertEqual(plan.bounds, saved.bounds)
        self.assertEqual(plan.screen, BIG)

    def test_missing_screen_uses_fallback_and_clamps(self) -> None:
        """A full-screen-sized window from a vanished 4K monitor shrinks to the fallback screen."""
        saved = _saved(BIG, QRect(0, 0, 3840, 2120), WindowState.NORMAL)
        plan = plan_restore(saved, [SMALL], SMALL)
        self.assertEqual(plan.screen, SMALL)
        self.assertEqual(plan.bounds, SMALL.available)

    def test_smaller_current_screen_clamps(self) -> None:
        """A screen with the same name but a smaller resolution limits the size and position."""
        saved = _saved(BIG, QRect(2000, 1000, 1800, 1000))
        shrunk = ScreenInfo('big', SMALL.geometry, SMALL.available)
        plan = plan_restore(saved, [shrunk], shrunk)
        self.assertTrue(shrunk.available.contains(plan.bounds))

    def test_moved_screen_shifts_bounds(self) -> None:
        """When a screen's origin moves, the window moves with it."""
        saved = _saved(SECOND, QRect(3900, 100, 800, 600))
        moved = ScreenInfo('second', QRect(0, 1080, 1920, 1080), QRect(0, 1080, 1920, 1040))
        plan = plan_restore(saved, [moved], BIG)
        self.assertEqual(plan.bounds, QRect(60, 1180, 800, 600))

    def test_maximized_state_restores_on_new_screen(self) -> None:
        """A maximized window stays maximized on the fallback screen, with normal bounds that fit it."""
        saved = _saved(BIG, QRect(500, 500, 3000, 1800), WindowState.MAXIMIZED)
        plan = plan_restore(saved, [SMALL], SMALL)
        self.assertEqual(plan.state, WindowState.MAXIMIZED)
        self.assertTrue(SMALL.available.contains(plan.bounds))

    def test_full_screen_state_is_kept(self) -> None:
        """Full-screen state survives the plan."""
        plan = plan_restore(_saved(BIG, QRect(0, 0, 800, 600), WindowState.FULL_SCREEN), [BIG], BIG)
        self.assertEqual(plan.state, WindowState.FULL_SCREEN)

    def test_capture_and_restore_round_trip_on_a_widget(self) -> None:
        """A widget's captured geometry restores to the same bounds on the current screens."""
        source = QWidget()
        source.setGeometry(20, 30, 400, 300)
        source.show()
        saved = capture_geometry(source)
        source.close()
        target = QWidget()
        restore_window(target, saved.to_json())
        self.assertEqual(target.geometry().size(), saved.bounds.size())
        target.close()
