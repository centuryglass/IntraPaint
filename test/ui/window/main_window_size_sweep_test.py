"""Builds the main window (from a mock-mode AppController, so it has its default docks) at a matrix of sizes and checks
that layout never fails or overflows."""
import sys
from unittest.mock import patch

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication

from src.ui.layout.reactive_layout_widget import ReactiveLayoutWidget
from src.ui.window.main_window import MainWindow, MIN_CANVAS_SIZE
from test.base_test_case import IntraPaintTestCase
from test.ui.ui_capture import mock_app_controller

app = QApplication.instance() or QApplication(sys.argv)

TARGET_SIZE = QSize(1024, 600)
LARGE_WINDOW = QSize(1920, 1080)
LARGE_SCREEN = QSize(4000, 4000)
DOCK_AREAS = (Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea,
              Qt.DockWidgetArea.TopDockWidgetArea, Qt.DockWidgetArea.BottomDockWidgetArea)


def _sweep_sizes() -> list[QSize]:
    """The smallest supported window size and a large one. Panels change layout with their dock's grid size, which
    `test/ui/layout/panel_size_class_test.py` covers."""
    return [TARGET_SIZE, LARGE_WINDOW]


class MainWindowSizeSweepTest(IntraPaintTestCase):
    """Resizes the controller's MainWindow offscreen across every size in `_sweep_sizes`."""

    def setUp(self) -> None:
        super().setUp()
        screen_patch = patch('src.ui.window.main_window.get_screen_size', return_value=LARGE_SCREEN)
        screen_patch.start()
        self.addCleanup(screen_patch.stop)
        self.controller = mock_app_controller()
        self.window: MainWindow = self.controller._window  # pylint: disable=protected-access
        self.window.show()

    def tearDown(self) -> None:
        self.window.hide()
        super().tearDown()

    def test_minimum_size_hint_fits_target(self) -> None:
        """The default layout fits 1024x600."""
        hint = self.window.minimumSizeHint()
        self.assertLessEqual(hint.width(), TARGET_SIZE.width())
        self.assertLessEqual(hint.height(), TARGET_SIZE.height())

    def test_every_reactive_widget_resolves_a_mode(self) -> None:
        """No size logs a missing-mode error, and every widget with sized modes has an active mode."""
        for size in _sweep_sizes():
            with self.subTest(size=size):
                with self.assertNoLogs('src.ui.layout.reactive_layout_widget', level='ERROR'):
                    self.window.resize(size)
                    for widget in self.window.findChildren(ReactiveLayoutWidget):
                        widget.resizeEvent(None)
                        if widget._layout_modes:  # pylint: disable=protected-access
                            self.assertIsNotNone(widget._active_mode)  # pylint: disable=protected-access

    def _move_docks_to(self, area: Qt.DockWidgetArea) -> None:
        """Tabifies every dock in one area and opens each one that has content."""
        first = self.window.docks[0]
        for dock in self.window.docks:
            self.window.removeDockWidget(dock)
            self.window.addDockWidget(area, dock)
            if dock is not first:
                self.window.tabifyDockWidget(first, dock)
            if dock.is_available:
                dock.show()

    def _assert_canvas_fits(self) -> None:
        """Asserts the canvas is at least `MIN_CANVAS_SIZE`."""
        canvas = self.window.centralWidget().size()
        self.assertGreaterEqual(canvas.width(), MIN_CANVAS_SIZE.width())
        self.assertGreaterEqual(canvas.height(), MIN_CANVAS_SIZE.height())

    def test_every_dock_area_fits_the_window(self) -> None:
        """With the docks in any one area, the window's minimum size stays within the window."""
        for size in _sweep_sizes():
            for area in DOCK_AREAS:
                with self.subTest(size=size, area=area):
                    self.window.resize(size)
                    self._move_docks_to(area)
                    hint = self.window.minimumSizeHint()
                    self.assertLessEqual(hint.height(), self.window.height())
                    self.assertLessEqual(hint.width(), self.window.width())

    def test_opening_every_dock_keeps_the_canvas(self) -> None:
        """At the target size, opening every dock in the first-run layout closes none and leaves the canvas at its
        minimum size or larger."""
        self.window.resize(TARGET_SIZE)
        self.window.reset_dock_layout()
        available = [dock for dock in self.window.docks if dock.is_available]
        for dock in available:
            dock.show()
        self.window.layout().activate()
        for dock in available:
            self.assertFalse(dock.isHidden(), dock.objectName())
        self._assert_canvas_fits()

    def test_oversized_dock_leaves_the_canvas(self) -> None:
        """A dock sized past the window in any area stops at the canvas's minimum size."""
        for area in DOCK_AREAS:
            with self.subTest(area=area):
                self._move_docks_to(area)
                self.window.resize(TARGET_SIZE)
                vertical = area in (Qt.DockWidgetArea.TopDockWidgetArea, Qt.DockWidgetArea.BottomDockWidgetArea)
                orientation = Qt.Orientation.Vertical if vertical else Qt.Orientation.Horizontal
                self.window.resizeDocks([self.window.docks[0]], [5000], orientation)
                self.window.layout().activate()
                self.assertEqual(self.window.size(), TARGET_SIZE)
                self._assert_canvas_fits()
