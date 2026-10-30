"""Tests named dock layouts: the layout store, and capturing and applying a layout on a MainWindow."""
import sys
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication, QLabel

from src.image.layers.image_stack import ImageStack
from src.ui.window import saved_layouts
from src.ui.window.dock_state import read_dock_groups
from src.ui.window.main_window import MainWindow, DOCK_STATE_VERSION
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

Area = Qt.DockWidgetArea


class SavedLayoutsStoreTest(IntraPaintTestCase):
    """Tests the functions over `Cache.SAVED_LAYOUTS`."""

    def test_default_name_skips_used_numbers(self) -> None:
        """The default name is the first "Layout N" nobody uses."""
        self.assertEqual(saved_layouts.default_layout_name(), 'Layout 1')
        saved_layouts.save_layout('Layout 1', 'a')
        saved_layouts.save_layout('Layout 3', 'b')
        self.assertEqual(saved_layouts.default_layout_name(), 'Layout 2')

    def test_names_sorted_case_insensitively(self) -> None:
        """Names list without regard to case."""
        for name in ('beta', 'Alpha', 'carbon'):
            saved_layouts.save_layout(name, 'x')
        self.assertEqual(saved_layouts.layout_names(), ['Alpha', 'beta', 'carbon'])

    def test_save_overwrites_and_trims(self) -> None:
        """Saving under an existing name replaces its state, and names are trimmed."""
        saved_layouts.save_layout('  mine ', 'first')
        saved_layouts.save_layout('mine', 'second')
        self.assertEqual(saved_layouts.layout_names(), ['mine'])
        self.assertEqual(saved_layouts.get_layout_state('mine'), 'second')
        self.assertTrue(saved_layouts.has_layout(' mine'))

    def test_empty_names_rejected(self) -> None:
        """Empty and whitespace-only names raise ValueError and save nothing."""
        for name in ('', '   '):
            with self.assertRaises(ValueError):
                saved_layouts.save_layout(name, 'x')
        saved_layouts.save_layout('real', 'x')
        with self.assertRaises(ValueError):
            saved_layouts.rename_layout('real', ' ')
        self.assertEqual(saved_layouts.layout_names(), ['real'])

    def test_rename_re_keys(self) -> None:
        """Rename moves the state to the new name without duplicating it, and refuses a missing source."""
        saved_layouts.save_layout('old', 'state')
        saved_layouts.rename_layout('old', ' new ')
        self.assertEqual(saved_layouts.layout_names(), ['new'])
        self.assertEqual(saved_layouts.get_layout_state('new'), 'state')
        with self.assertRaises(KeyError):
            saved_layouts.rename_layout('missing', 'other')
        self.assertEqual(saved_layouts.layout_names(), ['new'])

    def test_delete_removes_only_that_name(self) -> None:
        """Delete leaves the other layouts, and a missing name is a no-op."""
        saved_layouts.save_layout('a', '1')
        saved_layouts.save_layout('b', '2')
        saved_layouts.delete_layout('a')
        saved_layouts.delete_layout('missing')
        self.assertEqual(saved_layouts.layout_names(), ['b'])
        with self.assertRaises(KeyError):
            saved_layouts.get_layout_state('a')


class ApplyDockStateTest(IntraPaintTestCase):
    """Captures and applies layouts on a MainWindow built without AppController."""

    def setUp(self) -> None:
        super().setUp()
        screen = SimpleNamespace(size=QSize(4000, 3000))
        screen_patch = patch('src.ui.window.main_window.get_screen_size', new=lambda *_: screen.size)
        screen_patch.start()
        self.addCleanup(screen_patch.stop)
        test_size = QSize(64, 64)
        self.image_stack = ImageStack(test_size, test_size, test_size, test_size)
        self.window = MainWindow(self.image_stack)
        for dock in (self.window.tools_dock, self.window.generation_dock, self.window.layers_dock,
                     self.window.color_dock, self.window.navigation_dock):
            dock.set_content(QLabel(dock.windowTitle()))
        self.window.resize(1280, 720)
        self.window.show()
        self.window.layout().activate()

    def tearDown(self) -> None:
        self.window.hide()
        super().tearDown()

    def _arrangement(self) -> list[tuple[list[tuple[str, bool, bool]], int]]:
        groups = read_dock_groups(self.window.saveState(DOCK_STATE_VERSION).data())
        assert groups is not None
        return [([(dock.name, dock.visible, dock.floating) for dock in group.docks], group.current)
                for group in groups]

    def _rearrange(self) -> None:
        window = self.window
        window.removeDockWidget(window.tools_dock)
        window.addDockWidget(Area.LeftDockWidgetArea, window.tools_dock)
        window.tools_dock.show()
        window.color_dock.setFloating(True)
        window.navigation_dock.hide()
        window.layout().activate()

    def test_apply_restores_arrangement(self) -> None:
        """Applying a saved layout brings back the saved tab groups, areas, floating docks and closed docks."""
        self._rearrange()
        saved = self.window.save_dock_state()
        expected = self._arrangement()
        expected_area = self.window.dockWidgetArea(self.window.tools_dock)

        self.window.reset_dock_layout()
        self.window.layout().activate()
        self.assertNotEqual(self._arrangement(), expected)
        self.assertTrue(self.window.apply_dock_state(saved))
        self.assertEqual(self._arrangement(), expected)
        self.assertEqual(self.window.dockWidgetArea(self.window.tools_dock), expected_area)
        self.assertTrue(self.window.color_dock.isFloating())

    def test_waiting_dock_survives_round_trip(self) -> None:
        """A closed dock that opens once its content arrives is saved shown, and opens when applied and filled."""
        self.window.tools_dock.hide()
        self.window.controlnet_dock.set_open(True)
        saved = self.window.save_dock_state()
        self.window.reset_dock_layout()
        self.assertTrue(self.window.apply_dock_state(saved))
        self.assertTrue(self.window.controlnet_dock.isHidden())
        self.window.controlnet_dock.set_content(QLabel('controlnet'))
        self.assertFalse(self.window.controlnet_dock.isHidden())

    def test_invalid_state_leaves_layout_unchanged(self) -> None:
        """Empty, corrupt and wrong-version text is rejected and the live layout is kept."""
        self._rearrange()
        before = self._arrangement()
        wrong_version = self.window.saveState(99).toBase64().data().decode()
        for saved in ('', 'not a saved state', wrong_version):
            with self.subTest(saved=saved[:12]):
                self.assertFalse(self.window.apply_dock_state(saved))
                self.assertEqual(self._arrangement(), before)

    def test_apply_closes_image_selector(self) -> None:
        """Applying with the image selector showing closes it first."""
        saved = self.window.save_dock_state()
        self.window.set_image_selector_visible(True)
        self.assertTrue(self.window.is_image_selector_visible())
        self.assertTrue(self.window.apply_dock_state(saved))
        self.assertFalse(self.window.is_image_selector_visible())
