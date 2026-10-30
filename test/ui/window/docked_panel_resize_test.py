"""Drags the separators around a docked generation panel in a `QMainWindow`, and checks that the dock stays in its slot.

A dock whose panel reports a minimum size larger than its slot overlaps the canvas or docks beside it. The panel sweep
(`test/ui/panel_sweep_test.py`) sizes panels in a plain host, so it can't see what a main window does with a panel's
size hints while the panel plans. A separator drag sizes docks differently from `QMainWindow.resizeDocks`, which these
tests use only to set up: only a drag shows a panel's mid-plan size hints reaching the main window.
"""
import sys

from PySide6.QtCore import QEvent, QEventLoop, QPoint, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QSizePolicy, QWidget

from src.ui.layout.panel_fit import Orientation
from src.ui.window.panel_dock import PanelDock
from test.base_test_case import IntraPaintTestCase
from test.ui.panel_capture import stable_diffusion_panel

app = QApplication.instance() or QApplication(sys.argv)

WINDOW_SIZE = QSize(1600, 1000)
DRAG_STEP = 10
SETTLE_PASSES = 4
# How far past the dock's edge a press lands on the separator:
SEPARATOR_OFFSET = 2


class DockedPanelResizeTest(IntraPaintTestCase):
    """Docks the WebUI generation panel above a second dock in the left area of a plain main window."""

    def setUp(self) -> None:
        super().setUp()
        self.window = QMainWindow()
        canvas = QWidget()
        canvas.setMinimumSize(100, 100)
        self.window.setCentralWidget(canvas)
        self.dock = PanelDock('Generation', 'generation', self.window)
        self.below = PanelDock('Below', 'below', self.window)
        for dock in (self.dock, self.below):
            self.window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock, Qt.Orientation.Vertical)
        # Expanding like the panel, so the area splits its height as `resizeDocks` asks:
        below = QLabel('below')
        below.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.below.set_content(below)
        self.panel = stable_diffusion_panel(True)
        self.dock.set_content(self.panel)
        self.window.resize(WINDOW_SIZE)
        self.window.show()
        self._settle()

    def tearDown(self) -> None:
        self.window.close()
        super().tearDown()

    @staticmethod
    def _settle() -> None:
        """Applies pending dock layout changes.

        `QMainWindow` applies a separator move, and docks resized with `resizeDocks`, on a zero-length timer that no
        posted event delivers, so this processes events once. A zero-length timer is due at once, so no wall-clock
        time decides what runs. Posted layout requests then apply the size hints that changed.
        """
        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        for _ in range(SETTLE_PASSES):
            QApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)

    def _place(self, size: QSize, orientation: Orientation) -> None:
        self.window.resizeDocks([self.dock], [size.width()], Qt.Orientation.Horizontal)
        self._settle()
        # The area spreads any difference from its height over the docks by these sizes' ratio:
        self.window.resizeDocks([self.dock, self.below], [size.height(), WINDOW_SIZE.height() - size.height()],
                                Qt.Orientation.Vertical)
        self._settle()
        self.panel.plan_in(orientation, self.panel.size())
        self._settle()
        self.assertEqual(orientation, self.panel.orientation)

    def _mouse(self, event_type: QEvent.Type, pos: QPoint, buttons: Qt.MouseButton) -> None:
        event = QMouseEvent(event_type, QPointF(pos), QPointF(self.window.mapToGlobal(pos)),
                            Qt.MouseButton.LeftButton, buttons, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(self.window, event)

    def _assert_drag_shrinks_in_place(self, axis: Qt.Orientation) -> None:
        """Drags the separator after the dock along `axis` toward it, `DRAG_STEP` at a time, until the next step would
        pass the panel's minimum size. Asserts at each step that the dock follows the separator, and overlaps neither
        the canvas nor the dock below."""
        horizontal = axis == Qt.Orientation.Horizontal
        step = QPoint(DRAG_STEP, 0) if horizontal else QPoint(0, DRAG_STEP)
        geometry = self.dock.geometry()
        pos = QPoint(geometry.right() + SEPARATOR_OFFSET, geometry.center().y()) if horizontal \
            else QPoint(geometry.center().x(), geometry.bottom() + SEPARATOR_OFFSET)
        extent = geometry.width() if horizontal else geometry.height()
        steps = 0
        self._mouse(QEvent.Type.MouseButtonPress, pos, Qt.MouseButton.LeftButton)
        try:
            while True:
                minimum = self.panel.minimumSizeHint()
                if extent - DRAG_STEP < (minimum.width() if horizontal else minimum.height()):
                    break
                extent -= DRAG_STEP
                pos -= step
                steps += 1
                self._mouse(QEvent.Type.MouseMove, pos, Qt.MouseButton.LeftButton)
                self._settle()
                geometry = self.dock.geometry()
                where = (f'{self.panel.orientation.value} dock at {geometry.width()}x{geometry.height()}, dragged to '
                         f'{extent}')
                # A panel raises its minimum size where its content would escape, which can stop the dock short:
                minimum = self.panel.minimumSizeHint()
                expected = max(extent, minimum.width() if horizontal else minimum.height())
                self.assertEqual(expected, geometry.width() if horizontal else geometry.height(), where)
                for neighbor in (self.window.centralWidget(), self.below):
                    self.assertFalse(geometry.intersects(neighbor.geometry()),
                                     f'{where}: overlaps {type(neighbor).__name__}')
                self.assertTrue(QRect(QPoint(), geometry.size()).contains(self.panel.geometry()), where)
        finally:
            self._mouse(QEvent.Type.MouseButtonRelease, pos, Qt.MouseButton.NoButton)
        self.assertGreater(steps, 0)

    def test_side_panel_narrows_in_its_slot(self) -> None:
        """A side panel narrows to its minimum width without leaving its slot."""
        self._place(QSize(600, 600), Orientation.SIDE)
        self._assert_drag_shrinks_in_place(Qt.Orientation.Horizontal)

    def test_strip_narrows_in_its_slot(self) -> None:
        """A strip narrowing until it plans as a side panel stays in its slot."""
        self._place(QSize(620, 635), Orientation.STRIP)
        self._assert_drag_shrinks_in_place(Qt.Orientation.Horizontal)

    def test_strip_shortens_in_its_slot(self) -> None:
        """A wide strip shortens to its minimum height without leaving its slot."""
        self._place(QSize(920, 450), Orientation.STRIP)
        self._assert_drag_shrinks_in_place(Qt.Orientation.Vertical)
