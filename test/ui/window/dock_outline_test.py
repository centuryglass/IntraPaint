"""Tests the 1px outline around a `PanelDock`: all four edges while floating, and every edge but the rail's while docked."""
import sys
from unittest.mock import patch

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QPalette
from PySide6.QtWidgets import QApplication, QLabel

from src.image.layers.image_stack import ImageStack
from src.ui.window.main_window import MainWindow
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

Area = Qt.DockWidgetArea


class DockOutlineTest(IntraPaintTestCase):
    """Builds a MainWindow without AppController, with content in every dock but ControlNet."""

    def setUp(self) -> None:
        super().setUp()
        screen_patch = patch('src.ui.window.main_window.get_screen_size', return_value=QSize(4000, 3000))
        screen_patch.start()
        self.addCleanup(screen_patch.stop)
        size = QSize(64, 64)
        self.window = MainWindow(ImageStack(size, size, size, size))
        for dock in self.window.docks:
            if dock is not self.window.controlnet_dock:
                dock.set_content(QLabel(dock.windowTitle()))
        self.window.resize(1600, 1000)
        self.window.show()
        self.dock = self.window.layers_dock

    def tearDown(self) -> None:
        for dock in self.window.docks:
            dock.setFloating(False)
        self.window.hide()
        super().tearDown()

    def _activate(self) -> None:
        layout = self.window.layout()
        assert layout is not None
        layout.activate()

    def _outlined_edges(self) -> set[Qt.Edge]:
        """Returns the edges whose midpoint pixel is the outline color in a render of the dock."""
        color = self.dock.palette().color(QPalette.ColorRole.Shadow).rgb()
        image: QImage = self.dock.grab().toImage()
        mid_x, mid_y = image.width() // 2, image.height() // 2
        probes = {
            Qt.Edge.LeftEdge: (0, mid_y),
            Qt.Edge.RightEdge: (image.width() - 1, mid_y),
            Qt.Edge.TopEdge: (mid_x, 0),
            Qt.Edge.BottomEdge: (mid_x, image.height() - 1),
        }
        return {edge for edge, (x, y) in probes.items() if image.pixel(x, y) == color}

    def test_floating_dock_outlines_every_edge(self) -> None:
        """A floating dock is outlined on all four edges."""
        self.dock.setFloating(True)
        self._activate()
        self.assertIsNone(self.dock.outline.skipped_edge)
        self.assertEqual(self._outlined_edges(), {Qt.Edge.LeftEdge, Qt.Edge.RightEdge, Qt.Edge.TopEdge,
                                                  Qt.Edge.BottomEdge})

    def test_docked_dock_leaves_out_its_rail_side(self) -> None:
        """A dock on the right has no outline on its right edge, where the right rail's line is."""
        self.window.addDockWidget(Area.RightDockWidgetArea, self.dock)
        self.dock.setFloating(False)
        self.window.resizeDocks([self.dock], [400], Qt.Orientation.Vertical)
        self._activate()
        self.assertEqual(self.window.dockWidgetArea(self.dock), Area.RightDockWidgetArea)
        self.assertEqual(self.dock.outline.skipped_edge, Qt.Edge.RightEdge)
        self.assertEqual(self._outlined_edges(), {Qt.Edge.LeftEdge, Qt.Edge.TopEdge, Qt.Edge.BottomEdge})

    def test_outline_does_not_take_mouse_events(self) -> None:
        """Presses reach the dock's content through the outline."""
        self.assertTrue(self.dock.outline.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents))
