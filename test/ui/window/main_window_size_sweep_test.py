"""Builds the main window (from a mock-mode AppController, so it has its default tabs) at a matrix of sizes and checks that layout never fails or overflows."""
import sys
from unittest.mock import patch

import pytest
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QLabel

from src.ui.layout.draggable_tabs.tab import Tab
from src.ui.layout.reactive_layout_widget import ReactiveLayoutWidget
from src.ui.panel.tool_panel import MIN_SIZE_FOR_TOOL_LABEL
from src.ui.window.main_window import MainWindow, TabBoxID, AUTO_TAB_MOVE_THRESHOLD, USE_LOWER_CONTROL_TAB_THRESHOLD
from test.base_test_case import IntraPaintTestCase
from test.ui.ui_capture import mock_app_controller

app = QApplication.instance() or QApplication(sys.argv)

TARGET_SIZE = QSize(1024, 600)
LARGE_SCREEN = QSize(4000, 4000)


def _sweep_sizes() -> list[QSize]:
    """The target size, plus sizes just below, at and above every threshold that changes the layout."""
    sizes = [TARGET_SIZE]
    for height in (AUTO_TAB_MOVE_THRESHOLD, USE_LOWER_CONTROL_TAB_THRESHOLD):
        sizes.extend(QSize(TARGET_SIZE.width(), height + offset) for offset in (-1, 0, 1))
    for offset in (-1, 0, 1):
        sizes.append(QSize(MIN_SIZE_FOR_TOOL_LABEL.width() + offset + TARGET_SIZE.width(), TARGET_SIZE.height()))
    return sizes


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

    @pytest.mark.xfail(strict=True, reason='default layout needs 752 px of height until the icon rail lands, '
                                           'https://github.com/centuryglass/IntraPaint/issues/13')
    def test_minimum_size_hint_fits_target(self) -> None:
        """The default layout should fit 1024x600; it needs more height until the icon rail lands (#13)."""
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

    def test_opening_a_tab_box_fits_the_window(self) -> None:
        """Opening any tab box never leaves the window's minimum size larger than the window."""
        for size in _sweep_sizes():
            for box_id in TabBoxID:
                with self.subTest(size=size, box=box_id):
                    self.window.resize(size)
                    box = self.window._get_tab_box(box_id)  # pylint: disable=protected-access
                    content = QLabel('content')
                    content.setMinimumSize(100, 100)
                    tab = Tab('tab', content)
                    self.window.add_tab(tab, box_id)
                    box._tab_bar._finish_tab_open()  # pylint: disable=protected-access
                    hint = self.window.minimumSizeHint()
                    self.assertLessEqual(hint.height(), self.window.height())
                    self.assertLessEqual(hint.width(), self.window.width())
                    box._tab_bar._tab_open_timer.stop()  # pylint: disable=protected-access
                    self.window.remove_tab(tab)
