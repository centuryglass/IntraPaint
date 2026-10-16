"""Tests editing saved dock layouts: moving a dock to the start of its area, and refusing layouts of another shape."""
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDockWidget, QLabel, QMainWindow

from src.ui.window.dock_state import move_dock_to_area_start
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

LEFT = Qt.DockWidgetArea.LeftDockWidgetArea
HORIZONTAL = Qt.Orientation.Horizontal


class DockStateTest(IntraPaintTestCase):
    """Builds a plain QMainWindow with a column of two docks in the left area."""

    def setUp(self) -> None:
        super().setUp()
        self.window = QMainWindow()
        self.window.setDockNestingEnabled(True)
        self.window.setCentralWidget(QLabel('center'))
        self.docks = {}
        for name in ('first', 'second', 'moved'):
            dock = QDockWidget(name, self.window)
            dock.setObjectName(name)
            dock.setWidget(QLabel(name))
            self.docks[name] = dock
        self.window.addDockWidget(LEFT, self.docks['first'])
        self.window.addDockWidget(LEFT, self.docks['second'], Qt.Orientation.Vertical)
        self.window.addDockWidget(LEFT, self.docks['moved'], HORIZONTAL)
        self.window.resize(1000, 800)
        self.window.show()
        self._activate()

    def tearDown(self) -> None:
        self.window.hide()
        self.window.deleteLater()
        super().tearDown()

    def _activate(self) -> None:
        layout = self.window.layout()
        assert layout is not None
        layout.activate()

    def test_moves_dock_to_area_start(self) -> None:
        """The appended column moves to the outer side, and the other docks keep their column."""
        self.assertGreater(self.docks['moved'].x(), self.docks['first'].x())
        state = move_dock_to_area_start(self.window.saveState().data(), LEFT, HORIZONTAL, 'moved')
        assert state is not None
        self.assertTrue(self.window.restoreState(state))
        self._activate()
        self.assertLess(self.docks['moved'].x(), self.docks['first'].x())
        self.assertEqual(self.docks['first'].x(), self.docks['second'].x())
        self.assertLess(self.docks['first'].y(), self.docks['second'].y())

    def test_refuses_other_shapes(self) -> None:
        """A dock that isn't last in its area, a different orientation, or broken bytes give None."""
        state = self.window.saveState().data()
        self.assertIsNone(move_dock_to_area_start(state, LEFT, HORIZONTAL, 'first'))
        self.assertIsNone(move_dock_to_area_start(state, LEFT, Qt.Orientation.Vertical, 'moved'))
        self.assertIsNone(move_dock_to_area_start(state, Qt.DockWidgetArea.TopDockWidgetArea, HORIZONTAL, 'moved'))
        self.assertIsNone(move_dock_to_area_start(state[:40], LEFT, HORIZONTAL, 'moved'))
        self.assertIsNone(move_dock_to_area_start(b'', LEFT, HORIZONTAL, 'moved'))

    def test_only_dock_in_area_is_unchanged(self) -> None:
        """A dock alone in its area is already at the start."""
        window = self.window
        top = Qt.DockWidgetArea.TopDockWidgetArea
        window.addDockWidget(top, self.docks['moved'], Qt.Orientation.Vertical)
        self._activate()
        state = window.saveState().data()
        self.assertEqual(move_dock_to_area_start(state, top, Qt.Orientation.Vertical, 'moved'), state)
