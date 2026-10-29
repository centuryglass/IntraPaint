"""Tests a floating dock's title bar: its rail button, which leaves the rails while the dock floats open, its title
note, its dock and close buttons, its menu, and dragging the dock by it."""
import sys
from unittest.mock import patch

from PySide6.QtCore import QEvent, QPoint, QPointF, QSize, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from src.image.layers.image_stack import ImageStack
from src.ui.layout.dock_panel import DockPanel
from src.ui.window.floating_title_bar import FloatingTitleBar
from src.ui.window.main_window import MainWindow
from src.ui.window.panel_dock import PanelDock
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

Area = Qt.DockWidgetArea
LEFT = Qt.MouseButton.LeftButton


def _send(widget: QWidget, event_type: QEvent.Type, local: QPoint, button: Qt.MouseButton,
          buttons: Qt.MouseButton) -> None:
    QApplication.sendEvent(widget, QMouseEvent(event_type, QPointF(local), QPointF(widget.mapToGlobal(local)), button,
                                               buttons, Qt.KeyboardModifier.NoModifier))


class FloatingTitleBarTest(IntraPaintTestCase):
    """Builds a MainWindow without AppController, with content in every dock but ControlNet, and floats Layers."""

    def setUp(self) -> None:
        super().setUp()
        screen_patch = patch('src.ui.window.main_window.get_screen_size', new=lambda *_: QSize(4000, 3000))
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
        self.dock.setFloating(True)
        self._activate()

    def tearDown(self) -> None:
        for dock in self.window.docks:
            dock.setFloating(False)
        self.window.hide()
        super().tearDown()

    def _activate(self) -> None:
        layout = self.window.layout()
        assert layout is not None
        layout.activate()

    def _title_bar(self) -> FloatingTitleBar:
        title_bar = self.dock.titleBarWidget()
        assert isinstance(title_bar, FloatingTitleBar)
        return title_bar

    def _rail_docks(self) -> list[PanelDock]:
        docks = []
        for area in (Area.LeftDockWidgetArea, Area.RightDockWidgetArea, Area.TopDockWidgetArea,
                     Area.BottomDockWidgetArea):
            docks += [button.dock for button in self.window.rails.rail(area).buttons]
        return docks

    def test_floating_dock_shows_its_button_in_its_title_bar(self) -> None:
        """The title bar shows the dock's rail button above the content, and the button leaves the rails."""
        title_bar = self._title_bar()
        self.assertIs(title_bar.rail_button.dock, self.dock)
        self.assertFalse(title_bar.rail_button.isHidden())
        assert self.dock.content is not None
        self.assertGreaterEqual(self.dock.content.geometry().top(), title_bar.geometry().bottom())
        self.assertNotIn(self.dock, self._rail_docks())

    def test_title_bar_shows_the_panel_title_note(self) -> None:
        """The title bar shows the panel's title note right of the rail button, follows changes to it, and hides it for
        content with no note."""
        title_bar = self._title_bar()
        self.assertTrue(title_bar.note_label.isHidden())
        panel = DockPanel('Layers')
        panel.set_title_note('3 layers')
        self.dock.set_content(panel)
        self._activate()
        self.assertEqual(title_bar.note_label.text(), '3 layers')
        self.assertFalse(title_bar.note_label.isHidden())
        self.assertGreaterEqual(title_bar.note_label.geometry().left(), title_bar.rail_button.geometry().right())
        self.assertTrue(title_bar.note_label.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents))
        panel.set_title_note('4 layers')
        self.assertEqual(title_bar.note_label.text(), '4 layers')
        self.dock.set_content(QLabel())
        self.assertTrue(title_bar.note_label.isHidden())
        panel.set_title_note('5 layers')
        self.assertTrue(title_bar.note_label.isHidden())

    def test_closed_floating_dock_returns_to_its_rail(self) -> None:
        """Closing a floating dock puts its button back in the rail of the area it was docked in, and clicking it there
        reopens the dock floating."""
        self._title_bar().close_button.click()
        self.assertTrue(self.dock.isHidden())
        rail = self.window.rails.rail_for(self.dock)
        self.assertEqual(rail.area, Area.RightDockWidgetArea)
        button = next(button for button in rail.buttons if button.dock is self.dock)
        self.assertFalse(button.isHidden())
        button.click()
        self.assertFalse(self.dock.isHidden())
        self.assertTrue(self.dock.isFloating())
        self.assertNotIn(self.dock, self._rail_docks())

    def test_dock_button_docks_the_dock(self) -> None:
        """The dock button docks the dock back in its group, hiding the title bar and returning its rail button."""
        self._title_bar().dock_button.click()
        self._activate()
        self.assertFalse(self.dock.isFloating())
        self.assertIsNot(self.dock.titleBarWidget(), self._title_bar_or_none())
        self.assertIn(self.dock, self._rail_docks())
        self.assertIn(self.window.color_dock, self.dock.group_mates())

    def _title_bar_or_none(self):
        title_bar = self.dock.titleBarWidget()
        return title_bar if isinstance(title_bar, FloatingTitleBar) else None

    def test_right_click_opens_the_dock_menu(self) -> None:
        """Right-clicking the title bar opens the dock's menu at the click."""
        title_bar = self._title_bar()
        point = QPoint(title_bar.width() // 2, title_bar.height() // 2)
        with patch.object(MainWindow, '_show_dock_menu') as show_menu:
            title_bar.customContextMenuRequested.emit(point)
        show_menu.assert_called_once_with(self.dock, title_bar.mapToGlobal(point))

    def test_dragging_the_title_bar_moves_the_dock(self) -> None:
        """A press on the title bar's empty space, or on its rail button, drags the floating dock. The drags go up and
        left, since Qt keeps a floating dock on screen."""
        title_bar = self._title_bar()
        self.assertTrue(title_bar.rail_button.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents))
        offset = QPoint(-60, -40)
        for start in (QPoint(title_bar.rail_button.geometry().center()),
                      QPoint(title_bar.dock_button.geometry().left() - 4, title_bar.height() // 2)):
            with self.subTest(start=start):
                before = self.dock.pos()
                # The rail button ignores the mouse, so a press over it reaches the bar:
                _send(title_bar, QEvent.Type.MouseButtonPress, start, LEFT, LEFT)
                _send(title_bar, QEvent.Type.MouseMove, start + offset, Qt.MouseButton.NoButton, LEFT)
                _send(title_bar, QEvent.Type.MouseButtonRelease, start + offset, LEFT, Qt.MouseButton.NoButton)
                self.assertNotEqual(self.dock.pos(), before)
                self.assertTrue(self.dock.isFloating())
