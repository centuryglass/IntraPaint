"""Tests the navigation window's zoom controls as it resizes, and its zoom tool's right-button context pin editing and
viewport gestures."""
from unittest import mock

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtWidgets import QApplication

from src.image.layers.image_stack import ImageStack
from src.ui.image_viewer import ImageViewer
from src.ui.panel.image_panel import MIN_WIDTH_SHOWING_SCALE_SLIDER
from src.ui.window.navigation_window import NavigationWindow, ZoomTool
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


class NavigationWindowResizeTest(IntraPaintTestCase):
    """Resizes the floating navigation window, which has the image panel's zoom controls."""

    def test_resize_hides_scale_slider_that_does_not_fit(self) -> None:
        """Resizing the window runs the image panel's visibility checks, so the scale slider hides when narrow."""
        image_stack = ImageStack(QSize(128, 96), QSize(128, 96), QSize(8, 8), QSize(2048, 2048))
        main_viewer = ImageViewer(None, image_stack, use_keybindings=False)
        window = NavigationWindow(image_stack, main_viewer)
        window.show()
        try:
            # pylint: disable-next=protected-access
            slider = window._image_scale_slider
            assert slider is not None
            window.resize(MIN_WIDTH_SHOWING_SCALE_SLIDER + 100, 400)
            self.assertTrue(slider.isVisibleTo(window))
            window.resize(MIN_WIDTH_SHOWING_SCALE_SLIDER - 100, 400)
            self.assertFalse(slider.isVisibleTo(window))
        finally:
            window.close()
            window.deleteLater()
            main_viewer.deleteLater()
