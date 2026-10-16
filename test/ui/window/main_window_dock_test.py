"""Tests MainWindow's docks: the first-run layout, docks without content, keys, saved layouts, the image selector,
and the orientation and size class each dock reports to its panel."""
import sys
from unittest.mock import patch

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QApplication, QLabel, QTabBar

from src.config.cache import Cache
from src.image.layers.image_stack import ImageStack
from src.ui.layout.dock_panel import DockPanel, P1, PanelLayout
from src.ui.layout.panel_size_class import Orientation, SizeClass
from src.ui.window.main_window import MainWindow, DEFAULT_SIDE_DOCK_WIDTH, DOCK_STATE_VERSION
from src.ui.window.panel_dock import PanelDock
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

LANDSCAPE_SCREEN = QSize(4000, 3000)
PORTRAIT_SCREEN = QSize(3000, 4000)
Area = Qt.DockWidgetArea


class _OrientedContent(QLabel):
    """Content with an unmigrated panel's `set_orientation`, recording each call."""

    def __init__(self) -> None:
        super().__init__('content')
        self.orientations: list[Qt.Orientation] = []

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        """Records the orientation."""
        self.orientations.append(orientation)


class _SamplePanel(DockPanel):
    """A migrated panel with one control."""

    def build(self, ui: PanelLayout) -> None:
        ui.section('Sample').add(QLabel('control'), P1)


class MainWindowDockTest(IntraPaintTestCase):
    """Builds MainWindows without AppController, on a screen large enough for any window size used."""

    def setUp(self) -> None:
        super().setUp()
        self._screen_size = LANDSCAPE_SCREEN
        screen_patch = patch('src.ui.window.main_window.get_screen_size', side_effect=lambda *_: self._screen_size)
        screen_patch.start()
        self.addCleanup(screen_patch.stop)
        test_size = QSize(64, 64)
        self.image_stack = ImageStack(test_size, test_size, test_size, test_size)
        self.windows: list[MainWindow] = []
        self.window = self._new_window()

    def tearDown(self) -> None:
        for window in self.windows:
            window.hide()
        super().tearDown()

    def _new_window(self, size: QSize = QSize(1280, 720), fill: bool = True) -> MainWindow:
        window = MainWindow(self.image_stack)
        self.windows.append(window)
        if fill:
            window.tools_dock.set_content(QLabel('tools'))
            window.generation_dock.set_content(QLabel('generation'))
            window.layers_dock.set_content(QLabel('layers'))
            window.color_dock.set_content(QLabel('color'))
            window.navigation_dock.set_content(QLabel('navigation'))
        window.resize(size)
        window.show()
        window.layout().activate()
        return window

    @staticmethod
    def _group(dock: PanelDock) -> set[str]:
        """Returns the object names of a dock and every dock tabified with it, open or closed."""
        return {dock.objectName(), *(other.objectName() for other in dock.group_mates())}

    @staticmethod
    def _shown_tab_bars(window: MainWindow) -> list[QTabBar]:
        """Returns the window's dock tab bars that aren't hidden."""
        return [tab_bar for tab_bar in window.findChildren(QTabBar, options=Qt.FindChildOption.FindDirectChildrenOnly)
                if not tab_bar.isHidden()]

    @staticmethod
    def _open_docks(window: MainWindow) -> set[str]:
        return {dock.objectName() for dock in window.docks if not dock.isHidden()}

    def test_first_run_layout(self) -> None:
        """Every dock starts in the right area. Tools and Layers are the open docks of the upper and lower groups, and
        Tools shows at its default width above Layers, with no tab bar drawn."""
        window = self.window
        for dock in window.docks:
            self.assertEqual(window.dockWidgetArea(dock), Area.RightDockWidgetArea)
        self.assertEqual(self._group(window.layers_dock), {dock.objectName() for dock in window.lower_docks})
        self.assertEqual(self._group(window.tools_dock), {dock.objectName() for dock in window.upper_docks})
        self.assertEqual(self._open_docks(window), {window.tools_dock.objectName(), window.layers_dock.objectName()})
        self.assertTrue(window.layers_dock.is_showing)
        self.assertTrue(window.tools_dock.is_showing)
        self.assertLess(window.tools_dock.geometry().bottom(), window.layers_dock.geometry().top())
        self.assertGreaterEqual(window.tools_dock.width(), DEFAULT_SIDE_DOCK_WIDTH)
        self.assertEqual(self._shown_tab_bars(window), [])

    def test_first_run_layout_on_portrait_screen(self) -> None:
        """On a screen taller than wide, the first-run layout uses the bottom area."""
        self._screen_size = PORTRAIT_SCREEN
        window = self._new_window(QSize(1080, 1700))
        for dock in window.docks:
            self.assertEqual(window.dockWidgetArea(dock), Area.BottomDockWidgetArea)

    def test_empty_dock_is_hidden_and_stays_closed_behind_its_group(self) -> None:
        """A dock without content hides with its toggle action. Content arriving while another dock of its group is
        open leaves it closed in that group."""
        controlnet = self.window.controlnet_dock
        self.assertTrue(controlnet.isHidden())
        self.assertFalse(controlnet.toggleViewAction().isVisible())
        controlnet.set_open(True)
        controlnet.set_content(QLabel('controlnet'))
        self.assertTrue(controlnet.isHidden())
        self.assertFalse(controlnet.open_when_available)
        self.assertTrue(controlnet.toggleViewAction().isVisible())
        self.assertIn(controlnet.objectName(), self._group(self.window.tools_dock))
        self.assertTrue(self.window.tools_dock.is_showing)

    def test_empty_dock_opens_when_its_group_has_no_open_dock(self) -> None:
        """Content arriving for a dock that should open, in a group with no open dock, opens it."""
        controlnet = self.window.controlnet_dock
        self.window.tools_dock.hide()
        controlnet.set_open(True)
        controlnet.set_content(QLabel('controlnet'))
        self.assertTrue(controlnet.is_showing)

    def test_opening_a_dock_closes_the_rest_of_its_group(self) -> None:
        """Opening a closed dock by key, toggle action or `set_open` takes the place of its group's open dock, at the
        same size, and leaves the other group alone."""
        window = self.window
        tools, generation = window.tools_dock, window.generation_dock
        tools_geometry = tools.geometry()
        openers = {
            'key': lambda dock: dock.toggle_from_key(),
            'toggle action': lambda dock: dock.toggleViewAction().trigger(),
            'set_open': lambda dock: dock.set_open(True)
        }
        for name, open_dock in openers.items():
            with self.subTest(opener=name):
                open_dock(generation)
                window.layout().activate()
                self.assertEqual(self._open_docks(window), {generation.objectName(), window.layers_dock.objectName()})
                self.assertEqual(generation.geometry(), tools_geometry)
                self.assertEqual(self._shown_tab_bars(window), [])
                open_dock(tools)
                window.layout().activate()
                self.assertEqual(self._open_docks(window), {tools.objectName(), window.layers_dock.objectName()})

    def test_docking_a_floating_dock_into_its_group_closes_the_rest(self) -> None:
        """A floating dock that docks back into its tab group, as after a mouse drop, is the group's open dock."""
        window = self.window
        window.generation_dock.toggle_from_key()
        window.generation_dock.setFloating(True)
        window.tools_dock.toggle_from_key()
        self.assertFalse(window.tools_dock.isHidden())
        window.generation_dock.setFloating(False)
        self.assertTrue(window.tools_dock.isHidden())
        self.assertFalse(window.generation_dock.isHidden())

    def test_closed_dock_stays_closed_across_content_changes(self) -> None:
        """Losing and regaining content keeps a closed dock closed, and an open dock open."""
        generation = self.window.generation_dock
        generation.hide()
        generation.set_content(None)
        generation.set_content(QLabel('other generator'))
        self.assertTrue(generation.isHidden())
        generation.open_in_group()
        generation.set_content(None)
        self.assertTrue(generation.isHidden())
        generation.set_content(QLabel('third generator'))
        self.assertFalse(generation.isHidden())

    def test_replaced_content_is_detached(self) -> None:
        """Replacing content takes the old panel out of the dock without deleting it."""
        old_content = self.window.generation_dock.content
        assert old_content is not None
        new_content = QLabel('new')
        self.window.generation_dock.set_content(new_content)
        self.assertIsNone(old_content.parentWidget())
        self.assertIs(self.window.generation_dock.widget(), new_content)
        old_content.deleteLater()

    def test_key_toggles_dock(self) -> None:
        """The dock key opens a closed dock in place of its group's open dock, and closes the dock that is showing."""
        generation = self.window.generation_dock
        self.assertFalse(generation.is_showing)
        self.assertTrue(generation.toggle_from_key())
        self.assertTrue(generation.is_showing)
        self.assertTrue(self.window.tools_dock.isHidden())
        self.assertTrue(generation.toggle_from_key())
        self.assertTrue(generation.isHidden())
        self.assertTrue(generation.toggle_from_key())
        self.assertTrue(generation.is_showing)

    def test_key_does_nothing_without_content(self) -> None:
        """An empty dock leaves its key unused, so the key event can go elsewhere."""
        self.assertFalse(self.window.controlnet_dock.toggle_from_key())
        self.assertTrue(self.window.controlnet_dock.isHidden())

    def test_saved_layout_round_trip(self) -> None:
        """A layout saved from one window restores the same areas, groups and dock sizes in another."""
        source = self.window
        source.removeDockWidget(source.generation_dock)
        source.addDockWidget(Area.LeftDockWidgetArea, source.generation_dock)
        source.generation_dock.show()
        source.removeDockWidget(source.tools_dock)
        source.addDockWidget(Area.BottomDockWidgetArea, source.tools_dock)
        source.tools_dock.show()
        source.controlnet_dock.set_content(QLabel('controlnet'))
        source.layout().activate()
        saved = source.save_dock_state()

        restored = self._new_window()
        restored.controlnet_dock.set_content(QLabel('controlnet'))
        self.assertTrue(restored.restore_dock_state(saved))
        restored.layout().activate()
        for source_dock, restored_dock in zip(source.docks, restored.docks):
            with self.subTest(dock=source_dock.objectName()):
                self.assertEqual(restored.dockWidgetArea(restored_dock), source.dockWidgetArea(source_dock))
                self.assertEqual(restored_dock.isHidden(), source_dock.isHidden())
                if not source_dock.isHidden():
                    self.assertEqual(restored_dock.geometry(), source_dock.geometry())

    def test_restored_front_tab_survives_late_content(self) -> None:
        """The dock open in its tab group when the layout was saved opens again once a restored window gets content,
        in the order AppController provides it."""
        self.window.generation_dock.open_in_group()
        saved = self.window.save_dock_state()
        restored = MainWindow(self.image_stack)
        self.windows.append(restored)
        restored.restore_dock_state(saved)
        restored.tools_dock.set_content(QLabel('tools'))
        restored.generation_dock.set_content(QLabel('generation'))
        restored.resize(1280, 720)
        restored.show()
        restored.layout().activate()
        self.assertTrue(restored.generation_dock.is_showing)
        self.assertTrue(restored.tools_dock.isHidden())
        self.assertEqual(self._shown_tab_bars(restored), [])

    def test_restoring_a_group_with_two_open_docks_keeps_its_front_dock(self) -> None:
        """A saved layout with more than one open dock in a group, as older versions saved, restores with only the
        group's front dock open, whether the docks have content yet or not."""
        window = self.window
        with PanelDock.placing_docks():
            window.generation_dock.show()
            window.color_dock.show()
        window.generation_dock.raise_()
        window.color_dock.raise_()
        saved = window.saveState(DOCK_STATE_VERSION).toBase64().data().decode()
        expected = {window.generation_dock.objectName(), window.color_dock.objectName()}

        filled = self._new_window()
        self.assertTrue(filled.restore_dock_state(saved))
        self.assertEqual(self._open_docks(filled), expected)

        late = MainWindow(self.image_stack)
        self.windows.append(late)
        late.restore_dock_state(saved)
        for dock in late.docks:
            dock.set_content(QLabel(dock.windowTitle()))
        self.assertEqual(self._open_docks(late), expected)

    def test_invalid_saved_layout_uses_first_run_layout(self) -> None:
        """Garbage text, an empty state and a state with another version restore nothing and keep the default."""
        self.window.removeDockWidget(self.window.tools_dock)
        self.window.addDockWidget(Area.LeftDockWidgetArea, self.window.tools_dock)
        wrong_version = self.window.saveState(99).toBase64().data().decode()
        for saved in ('', 'not a saved state', wrong_version):
            with self.subTest(saved=saved[:12]):
                window = MainWindow(self.image_stack)
                self.windows.append(window)
                self.assertFalse(window.restore_dock_state(saved))
                window.tools_dock.set_content(QLabel('tools'))
                window.show()
                self.assertEqual(window.dockWidgetArea(window.tools_dock), Area.RightDockWidgetArea)
                self.assertFalse(window.tools_dock.isHidden())

    def test_large_layout_restores_inside_small_window(self) -> None:
        """A layout saved in a 2400x1400 window keeps every dock inside a 1024x600 window, leaving the canvas room."""
        large = self._new_window(QSize(2400, 1400))
        large.removeDockWidget(large.generation_dock)
        large.addDockWidget(Area.BottomDockWidgetArea, large.generation_dock)
        large.generation_dock.show()
        large.resizeDocks([large.tools_dock], [1200], Qt.Orientation.Horizontal)
        large.resizeDocks([large.generation_dock], [700], Qt.Orientation.Vertical)
        large.layout().activate()
        saved = large.save_dock_state()

        small = self._new_window(QSize(1024, 600))
        self.assertTrue(small.restore_dock_state(saved))
        small.layout().activate()
        window_rect = small.rect()
        for dock in small.docks:
            if dock.is_showing:
                self.assertTrue(window_rect.contains(dock.geometry()), dock.objectName())
        self.assertFalse(small.centralWidget().geometry().isEmpty())

    def test_empty_dock_open_at_exit_reopens_after_restore(self) -> None:
        """A dock that was open but empty when the layout was saved opens once a restored window gives it content."""
        self.window.tools_dock.hide()
        self.window.controlnet_dock.set_open(True)
        saved = self.window.save_dock_state()
        self.assertTrue(self.window.controlnet_dock.isHidden())

        restored = self._new_window()
        restored.restore_dock_state(saved)
        self.assertTrue(restored.controlnet_dock.isHidden())
        restored.controlnet_dock.set_content(QLabel('controlnet'))
        self.assertFalse(restored.controlnet_dock.isHidden())

    def test_image_selector_hides_docks_and_restores_layout(self) -> None:
        """The image selector hides every dock, and closing it brings back the layout from before."""
        window = self.window
        window.generation_dock.open_in_group()
        window.layout().activate()
        showing_geometry = window.generation_dock.geometry()
        window.set_image_selector_visible(True)
        for dock in window.docks:
            self.assertTrue(dock.isHidden(), dock.objectName())
        self.assertTrue(window.controlnet_dock.isHidden())
        window.set_image_selector_visible(False)
        window.layout().activate()
        self.assertEqual(self._open_docks(window),
                         {window.generation_dock.objectName(), window.layers_dock.objectName()})
        self.assertTrue(window.generation_dock.is_showing)
        self.assertEqual(window.generation_dock.geometry(), showing_geometry)

    def test_closing_image_selector_draws_no_tab_bars(self) -> None:
        """No dock tab bar is drawn after the image selector opens and closes, however many times."""
        window = self.window
        for _ in range(2):
            window.set_image_selector_visible(True)
            window.set_image_selector_visible(False)
            window.layout().activate()
            self.assertEqual(self._shown_tab_bars(window), [])

    def test_failed_restore_keeps_layout(self) -> None:
        """A saved layout of another version is refused, and the open docks stay open."""
        window = self.window
        expected = self._open_docks(window)
        state = window.saveState(DOCK_STATE_VERSION + 1).toBase64().data().decode()
        self.assertFalse(window.restore_dock_state(state))
        self.assertEqual(self._open_docks(window), expected)

    def test_saving_while_selector_shows_saves_previous_layout(self) -> None:
        """Saving while the image selector hides the docks saves the layout from before it opened."""
        before = self.window.save_dock_state()
        self.window.set_image_selector_visible(True)
        self.assertEqual(self.window.save_dock_state(), before)
        self.window.set_image_selector_visible(False)

    def test_reset_layout_brings_back_moved_and_closed_docks(self) -> None:
        """Reset docks a floating dock, returns every dock to the right, and opens only Tools and Layers."""
        window = self.window
        window.generation_dock.setFloating(True)
        window.tools_dock.hide()
        window.layers_dock.hide()
        window.reset_dock_layout()
        for dock in (window.tools_dock, window.generation_dock):
            self.assertFalse(dock.isFloating())
            self.assertEqual(window.dockWidgetArea(dock), Area.RightDockWidgetArea)
        self.assertEqual(self._open_docks(window), {window.tools_dock.objectName(), window.layers_dock.objectName()})
        self.assertTrue(window.tools_dock.is_showing)

    def test_no_tab_bars_after_reset(self) -> None:
        """After moving docks around and resetting, no dock tab bar is drawn."""
        window = self.window
        window.removeDockWidget(window.generation_dock)
        window.addDockWidget(Area.LeftDockWidgetArea, window.generation_dock)
        window.generation_dock.show()
        window.layout().activate()
        window.reset_dock_layout()
        window.reset_dock_layout()
        window.layout().activate()
        self.assertEqual(self._shown_tab_bars(window), [])

    def test_offscreen_floating_dock_moves_on_screen(self) -> None:
        """A restored floating dock that no display shows moves onto the window's display."""
        window = self.window
        window.generation_dock.setFloating(True)
        window.generation_dock.setGeometry(QRect(QPoint(-20000, -20000), QSize(300, 200)))
        self.assertFalse(window.screen().availableGeometry().intersects(window.generation_dock.frameGeometry()))
        saved = window.save_dock_state()
        restored = self._new_window()
        restored.restore_dock_state(saved)
        screen = restored.screen().availableGeometry()
        self.assertTrue(screen.intersects(restored.generation_dock.frameGeometry()))

    def test_unmigrated_content_gets_orientation_from_area(self) -> None:
        """Content with `set_orientation` gets vertical in a side area and horizontal in a strip area."""
        window = self._new_window(fill=False)
        content = _OrientedContent()
        window.tools_dock.set_content(content)
        self.assertEqual(content.orientations[-1], Qt.Orientation.Vertical)
        window.removeDockWidget(window.tools_dock)
        window.addDockWidget(Area.BottomDockWidgetArea, window.tools_dock)
        window.tools_dock.show()
        self.assertEqual(content.orientations[-1], Qt.Orientation.Horizontal)
        calls = len(content.orientations)
        window.tools_dock.resize(window.tools_dock.width() - 10, window.tools_dock.height())
        self.assertEqual(len(content.orientations), calls, 'a resize in the same area repeats no orientation')

    def test_dock_panel_gets_orientation_and_size_class(self) -> None:
        """A DockPanel gets its dock's orientation and a size class from the dock's own size."""
        window = self._new_window(fill=False)
        panel = _SamplePanel()
        window.tools_dock.set_content(panel)
        window.resizeDocks([window.tools_dock], [200], Qt.Orientation.Horizontal)
        window.layout().activate()
        self.assertEqual(panel.orientation, Orientation.SIDE)
        self.assertEqual(panel.size_class, SizeClass.COMPACT)
        window.resizeDocks([window.tools_dock], [500], Qt.Orientation.Horizontal)
        window.layout().activate()
        self.assertEqual(panel.size_class, SizeClass.WIDE)
        window.removeDockWidget(window.tools_dock)
        window.addDockWidget(Area.TopDockWidgetArea, window.tools_dock)
        window.tools_dock.show()
        window.resizeDocks([window.tools_dock], [240], Qt.Orientation.Vertical)
        window.layout().activate()
        self.assertEqual(panel.orientation, Orientation.STRIP)
        self.assertEqual(panel.size_class, SizeClass.REGULAR)

    def test_close_saves_dock_layout(self) -> None:
        """Closing the window stores the dock layout next to the window geometry."""
        with patch('src.ui.window.main_window.QApplication.exit'):
            self.window.close_without_confirmation()
        saved = Cache().get(Cache.SAVED_MAIN_WINDOW_STATE)
        self.assertNotEqual(saved, '')
        restored = self._new_window()
        self.assertTrue(restored.restore_dock_state(saved))
