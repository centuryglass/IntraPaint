"""Tests that a floating `PanelDock` shows its outline."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow

from src.ui.window.floating_edge import FloatingEdge
from src.ui.window.panel_dock import PanelDock
from test.base_test_case import IntraPaintTestCase


class FloatingEdgeTest(IntraPaintTestCase):
    """Checks the outline over a floating dock's content."""

    def setUp(self) -> None:
        super().setUp()
        self.window = QMainWindow()
        self.dock = PanelDock('Edge', 'edge', self.window)
        content = QLabel('content')
        content.setStyleSheet('background: white')
        self.dock.set_content(content)
        self.window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock)
        self.window.show()

    def tearDown(self) -> None:
        self.window.close()
        super().tearDown()

    def test_floating_dock_outline_covers_content(self) -> None:
        """A floating dock's border pixels differ from its content."""
        self.dock.setFloating(True)
        self.dock.show()
        self.dock.resize(200, 150)
        image = self.dock.grab().toImage()
        for x, y in ((0, 75), (199, 75), (100, 0), (100, 149)):
            self.assertNotEqual(image.pixelColor(x, y).name(), '#ffffff', f'({x}, {y}) has no outline')
        self.assertEqual(image.pixelColor(100, 20).name(), '#ffffff')

    def test_docked_dock_has_no_outline(self) -> None:
        """The outline hides when the dock is docked."""
        self.dock.setFloating(True)
        self.dock.setFloating(False)
        self.assertFalse(self.dock.isFloating())
        edge = self.dock.findChild(FloatingEdge)
        assert edge is not None
        self.assertTrue(edge.isHidden())
