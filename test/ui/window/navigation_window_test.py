"""Tests the navigation panel's layout and mode toggle, the floating window's zoom controls as it resizes, and the
zoom tool's context pin editing and viewport gestures."""
import os
from unittest import mock

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.image.layers.image_stack import ImageStack
from src.tools.generation_area_tool import GenerationAreaTool
from src.ui.image_viewer import ImageViewer
from src.ui.input_fields.segmented_control import DisplayMode
from src.ui.layout.panel_fit import Orientation
from src.ui.window.navigation_window import (ZoomTool, NavigationWindow, ZOOM_LABEL, IMAGE_GEN_LABEL,
                                             IMAGE_GEN_LABEL_SHORT, VIEW_HINT_LINES, GEN_AREA_HINT_LINES,
                                             CONTEXT_PIN_HINT)
from src.undo_stack import UndoStack
from test.base_test_case import IntraPaintTestCase
from test.tools.tool_test_case import ToolTestCase

RIGHT = Qt.MouseButton.RightButton


class ZoomToolTest(ToolTestCase):
    """Drives ZoomTool in a navigation-sized viewer with synthetic mouse input at 1:1 scale."""

    IMAGE_SIZE = QSize(128, 96)

    def setUp(self) -> None:
        super().setUp()
        self.image_stack.create_layer()
        self.main_viewer = ImageViewer(None, self.image_stack, use_keybindings=False)
        self.tool = self.activate_tool(ZoomTool(self.image_stack, self.main_viewer, self.image_viewer))
        self.selection_layer = self.image_stack.selection_layer
        UndoStack().clear()

    def tearDown(self) -> None:
        self.main_viewer.deleteLater()
        super().tearDown()

    def test_right_click_adds_and_removes_pin(self) -> None:
        """A right-click adds a pin, and a second right-click on it removes the pin, each as one undo step."""
        self.mouse_drag([QPoint(40, 30)], RIGHT)
        self.assertEqual(self.selection_layer.context_pins, [QPoint(40, 30)])
        self.mouse_drag([QPoint(40, 30)], RIGHT)
        self.assertEqual(self.selection_layer.context_pins, [])
        self.assertEqual(UndoStack().undo_count(), 2)

    def test_right_drag_moves_pin_and_dropping_outside_deletes_it(self) -> None:
        """A right-drag moves a pin, and releasing it outside the image deletes it."""
        self.selection_layer.set_context_pins([QPoint(40, 30)], False)
        self.mouse_drag([QPoint(40, 30), QPoint(60, 50)], RIGHT)
        self.assertEqual(self.selection_layer.context_pins, [QPoint(60, 50)])
        self.mouse_drag([QPoint(60, 50), QPoint(-20, 50)], RIGHT)
        self.assertEqual(self.selection_layer.context_pins, [])

    def test_left_drag_pans_without_touching_pins(self) -> None:
        """A plain left-button drag moves the main view and leaves pins alone."""
        self.selection_layer.set_context_pins([QPoint(40, 30)], False)
        with mock.patch.object(self.tool, '_move_view') as move_view:
            self.mouse_drag([QPoint(40, 30), QPoint(50, 40)])
        self.assertEqual(move_view.call_count, 2)
        self.assertEqual(self.selection_layer.context_pins, [QPoint(40, 30)])
        self.assertEqual(UndoStack().undo_count(), 0)

    def test_shift_left_drag_zooms_to_viewport(self) -> None:
        """A Shift + left-drag draws a viewport instead of panning, and zooms the main view to it."""
        with mock.patch.object(QApplication, 'keyboardModifiers', return_value=Qt.KeyboardModifier.ShiftModifier), \
                mock.patch.object(self.tool, '_move_view') as move_view, \
                mock.patch.object(self.main_viewer, 'zoom_to_bounds') as zoom_to_bounds:
            self.mouse_drag([QPoint(10, 10), QPoint(50, 40)])
        move_view.assert_not_called()
        zoom_to_bounds.assert_called_once()


class NavigationPanelTest(IntraPaintTestCase):
    """Drives the docked navigation panel beside a main viewer showing a 400x200 image."""

    IMAGE_SIZE = QSize(400, 200)

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(self.IMAGE_SIZE, QSize(256, 256), QSize(8, 8), QSize(2048, 2048))
        self.image_stack.create_layer()
        self.main_viewer = ImageViewer(None, self.image_stack, use_keybindings=False)
        self.main_viewer.resize(600, 400)
        self.main_viewer.show()
        self.panel = self._new_panel()

    def tearDown(self) -> None:
        for widget in (self.panel, self.main_viewer):
            widget.close()
            widget.deleteLater()
        super().tearDown()

    def _new_panel(self) -> NavigationWindow:
        panel = NavigationWindow(self.image_stack, self.main_viewer, include_zoom_controls=False)
        panel.resize(300, 300)
        panel.show()
        return panel

    def test_mode_toggle_round_trips_through_cache(self) -> None:
        """Choosing a mode activates its tool and stores its label, and a new panel restores it."""
        self.assertEqual(self.panel.tool_toggle.value(), ZOOM_LABEL)
        self.panel.tool_toggle.set_value(IMAGE_GEN_LABEL)
        self.assertEqual(Cache().get(Cache.LAST_NAV_PANEL_TOOL), IMAGE_GEN_LABEL)
        restored = self._new_panel()
        try:
            self.assertEqual(restored.tool_toggle.value(), IMAGE_GEN_LABEL)
            # pylint: disable-next=protected-access
            self.assertIsInstance(restored._tool_controller.active_tool, GenerationAreaTool)
        finally:
            restored.close()
            restored.deleteLater()

    def test_hint_follows_mode(self) -> None:
        """The viewer's tooltip describes the controls of the active mode."""
        self.assertEqual(self.panel.image_viewer.toolTip(), '\n'.join((*VIEW_HINT_LINES, CONTEXT_PIN_HINT)))
        self.panel.tool_toggle.set_value(IMAGE_GEN_LABEL)
        self.assertEqual(self.panel.image_viewer.toolTip(), '\n'.join(GEN_AREA_HINT_LINES))

    def test_toggle_hides_without_generator(self) -> None:
        """Hiding generation controls hides the toggle and switches back to moving the view."""
        self.panel.tool_toggle.set_value(IMAGE_GEN_LABEL)
        self.panel.set_image_generation_controls_visible(False)
        self.assertFalse(self.panel.tool_toggle.isVisible())
        self.assertEqual(self.panel.tool_toggle.value(), ZOOM_LABEL)

    def test_highlight_follows_main_view(self) -> None:
        """The viewer highlights the region the main view shows, as the main view pans and zooms."""
        self.main_viewer.scene_scale = 3.0
        self.main_viewer.offset = QPoint(40, 20)
        self.assertEqual(self.panel.image_viewer.viewport_highlight, self.main_viewer.visible_scene_bounds)
        if 'NAV_RENDER_DIR' in os.environ:
            self.panel.grab().save(os.path.join(os.environ['NAV_RENDER_DIR'], 'nav_highlight.png'))

    def test_viewer_fits_image_aspect_ratio(self) -> None:
        """The viewer takes the image's aspect ratio in both orientations."""
        for size in (QSize(300, 400), QSize(700, 160)):
            self.panel.resize(size)
            viewer = self.panel.image_viewer
            self.assertAlmostEqual(viewer.width() / viewer.height(), 2.0, delta=0.05, msg=str(size))
        self.assertEqual(self.panel.orientation, Orientation.STRIP)

    def test_orientation_leaves_the_larger_viewer(self) -> None:
        """A tall panel puts the controls below the viewer, and a wide short one puts them beside it."""
        self.panel.resize(260, 500)
        self.assertEqual(self.panel.orientation, Orientation.SIDE)
        self.panel.resize(900, 180)
        self.assertEqual(self.panel.orientation, Orientation.STRIP)

    def test_toggle_shrinks_to_fit(self) -> None:
        """The toggle shows full labels where they fit, then short labels, then icons only."""
        toggle = self.panel.tool_toggle
        self.panel.resize(0, 500)
        self.assertEqual(toggle.display_mode, DisplayMode.ICON)
        self.panel.resize(400, 500)
        self.assertEqual(toggle.display_mode, DisplayMode.ICON_AND_LABEL)
        self.assertEqual(toggle.segments[1].label, IMAGE_GEN_LABEL)
        minimum_width = self.panel.minimumSizeHint().width()
        short_width = minimum_width + toggle.sizeHint().width()
        for width in range(minimum_width, 400):
            self.panel.resize(width, 500)
            if toggle.display_mode == DisplayMode.ICON_AND_LABEL and toggle.segments[1].label == IMAGE_GEN_LABEL_SHORT:
                short_width = width
                break
        self.assertLess(short_width, 400, 'No width showed the short labels')
        self.assertGreaterEqual(toggle.width(), toggle.minimumSizeHint().width())


class NavigationWindowResizeTest(IntraPaintTestCase):
    """Resizes the floating navigation window, which has the image panel's zoom controls."""

    def test_resize_plans_the_canvas_bar(self) -> None:
        """Resizing the window plans its canvas bar: Reset view shows its label when wide and its glyph when
        narrow."""
        image_stack = ImageStack(QSize(128, 96), QSize(128, 96), QSize(8, 8), QSize(2048, 2048))
        main_viewer = ImageViewer(None, image_stack, use_keybindings=False)
        window = NavigationWindow(image_stack, main_viewer)
        window.show()
        try:
            bar = window.control_bar
            assert bar is not None
            labeled, glyph = bar.reset_buttons
            window.resize(800, 400)
            self.assertTrue(labeled.isVisibleTo(window))
            self.assertFalse(glyph.isVisibleTo(window))
            window.resize(bar.minimumSizeHint().width(), 400)
            self.assertFalse(labeled.isVisibleTo(window))
            self.assertTrue(glyph.isVisibleTo(window))
        finally:
            window.close()
            window.deleteLater()
            main_viewer.deleteLater()
