"""Tests dragging rail buttons: tabbing and splitting docks within a rail, handing off to Qt's dock drag, and the
title bars that drag uses."""
import sys
from unittest.mock import patch

from PySide6.QtCore import QEvent, QPoint, QPointF, QSize, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from src.image.layers.image_stack import ImageStack
from src.ui.window.dock_rail import RailButton
from src.ui.window.floating_title_bar import FloatingTitleBar
from src.ui.window.main_window import MainWindow
from src.ui.window.panel_dock import PanelDock
from src.ui.window.qt_dock_drag import TITLE_PRESS_INSET, TITLE_PRESS_Y
from src.ui.window.rail_drag import DRAG_DISTANCE
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

Area = Qt.DockWidgetArea
LEFT = Qt.MouseButton.LeftButton
NO_BUTTON = Qt.MouseButton.NoButton


def _send(widget: QWidget, event_type: QEvent.Type, global_pos: QPoint, button: Qt.MouseButton,
          buttons: Qt.MouseButton) -> None:
    local = widget.mapFromGlobal(global_pos)
    QApplication.sendEvent(widget, QMouseEvent(event_type, QPointF(local), QPointF(global_pos), button, buttons,
                                               Qt.KeyboardModifier.NoModifier))


class RailDragTest(IntraPaintTestCase):
    """Builds a MainWindow without AppController, with content in every dock but ControlNet."""

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
        self._activate()
        self.rail = self.window.rails.rail(Area.RightDockWidgetArea)

    def tearDown(self) -> None:
        for dock in self.window.docks:
            dock.setFloating(False)
        self.window.hide()
        super().tearDown()

    def _activate(self) -> None:
        layout = self.window.layout()
        assert layout is not None
        layout.activate()

    def _button(self, dock: PanelDock) -> RailButton:
        return next(button for button in self.window.rails.rail_for(dock).buttons if button.dock is dock)

    def _center(self, widget: QWidget) -> QPoint:
        return widget.mapToGlobal(widget.rect().center())

    def _press_and_move(self, button: RailButton, *points: QPoint) -> None:
        _send(button, QEvent.Type.MouseButtonPress, self._center(button), LEFT, LEFT)
        for point in points:
            _send(button, QEvent.Type.MouseMove, point, NO_BUTTON, LEFT)

    def _drag(self, button: RailButton, *points: QPoint) -> None:
        """Presses a button, moves through each point, and releases at the last one."""
        self._press_and_move(button, *points)
        _send(button, QEvent.Type.MouseButtonRelease, points[-1], LEFT, NO_BUTTON)
        self._activate()

    def _rail_point(self, along: int) -> QPoint:
        """Returns the screen position `along` px down the right rail's content, at its middle."""
        content = self.rail.content
        return content.mapToGlobal(QPoint(content.width() // 2, along))

    def _group_end(self, group_index: int) -> int:
        group = [button for button in self.rail.groups[group_index] if not button.isHidden()]
        return group[-1].geometry().bottom()

    @staticmethod
    def _group(dock: PanelDock) -> set[PanelDock]:
        return {dock, *dock.group_mates()}

    def test_docked_docks_have_no_title_bar_and_floating_docks_do(self) -> None:
        """A docked dock's content starts at its top edge. Floating shows its floating title bar, and docking hides it
        again."""
        dock = self.window.layers_dock
        assert dock.content is not None
        self.assertEqual(dock.content.geometry().top(), 0)
        dock.setFloating(True)
        self.assertIsInstance(dock.titleBarWidget(), FloatingTitleBar)
        dock.setFloating(False)
        self._activate()
        self.assertEqual(dock.content.geometry().top(), 0)

    def test_notch_shows_only_while_docked_and_above_the_content(self) -> None:
        """A docked dock shows its notch in the upper-left corner above the content. Floating hides it."""
        dock = self.window.layers_dock
        notch = dock.notch
        self.assertTrue(notch.isVisible())
        self.assertEqual(notch.pos(), QPoint(0, 0))
        children = dock.children()
        self.assertGreater(children.index(notch), children.index(dock.content))
        dock.setFloating(True)
        self.assertFalse(notch.isVisible())
        dock.setFloating(False)
        self._activate()
        self.assertTrue(notch.isVisible())

    def test_dragging_the_notch_floats_the_dock_under_the_pointer(self) -> None:
        """Dragging the notch out of the dock hands off to Qt's dock drag, as a rail button drag does."""
        dock = self.window.layers_dock
        notch = dock.notch
        start = notch.mapToGlobal(QPoint(2, 2))
        outside = self.window.mapToGlobal(QPoint(300, 300))
        _send(notch, QEvent.Type.MouseButtonPress, start, LEFT, LEFT)
        _send(notch, QEvent.Type.MouseMove, start + QPoint(DRAG_DISTANCE, DRAG_DISTANCE), NO_BUTTON, LEFT)
        self.assertTrue(dock.isFloating())
        _send(dock, QEvent.Type.MouseMove, outside, NO_BUTTON, LEFT)
        _send(dock, QEvent.Type.MouseButtonRelease, outside, LEFT, NO_BUTTON)
        self.assertTrue(dock.isFloating())

    def test_short_notch_press_does_not_drag(self) -> None:
        """A press that moves less than the drag distance leaves the dock docked."""
        dock = self.window.layers_dock
        start = dock.notch.mapToGlobal(QPoint(2, 2))
        _send(dock.notch, QEvent.Type.MouseButtonPress, start, LEFT, LEFT)
        _send(dock.notch, QEvent.Type.MouseMove, start + QPoint(1, 0), NO_BUTTON, LEFT)
        _send(dock.notch, QEvent.Type.MouseButtonRelease, start, LEFT, NO_BUTTON)
        self.assertFalse(dock.isFloating())

    def test_notch_press_off_the_triangle_is_ignored(self) -> None:
        """The corner of the notch's square opposite the triangle does not start a drag."""
        dock = self.window.layers_dock
        corner = dock.notch.mapToGlobal(QPoint(14, 14))
        _send(dock.notch, QEvent.Type.MouseButtonPress, corner, LEFT, LEFT)
        _send(dock.notch, QEvent.Type.MouseMove, corner + QPoint(DRAG_DISTANCE * 3, 0), NO_BUTTON, LEFT)
        self.assertFalse(dock.isFloating())

    def test_short_press_is_a_click(self) -> None:
        """Moving less than the drag distance before release still toggles the dock."""
        button = self._button(self.window.layers_dock)
        start = self._center(button)
        self._drag(button, start + QPoint(DRAG_DISTANCE - 2, 0))
        self.assertTrue(self.window.layers_dock.isHidden())

    def test_drag_onto_another_group_tabs_the_dock_there(self) -> None:
        """Dropping a button on another group's buttons tabs its dock into that group, open, and the rail regroups."""
        window = self.window
        tools_button = self._button(window.tools_dock)
        target = self._center(self._button(window.color_dock))
        self._drag(tools_button, self._center(tools_button) + QPoint(0, DRAG_DISTANCE), target)
        self.assertIn(window.tools_dock, self._group(window.layers_dock))
        self.assertTrue(window.tools_dock.is_showing)
        self.assertTrue(window.layers_dock.isHidden())
        self.assertIn(tools_button, self.rail.groups[1])
        self.assertFalse(window.rail_drag.marker.isVisible())

    def test_drag_past_the_last_group_splits_below_it(self) -> None:
        """Dropping a closed dock's button past the last group puts the dock below that group, open, alone."""
        window = self.window
        color_button = self._button(window.color_dock)
        self._drag(color_button, self._center(color_button) + QPoint(0, DRAG_DISTANCE),
                   self._rail_point(self._group_end(1) + 20))
        self.assertEqual(self._group(window.color_dock), {window.color_dock})
        self.assertTrue(window.color_dock.is_showing)
        self.assertGreater(window.color_dock.geometry().top(), window.layers_dock.geometry().bottom())

    def test_drag_between_groups_splits_beside_the_nearer_group(self) -> None:
        """Just after the upper group's buttons, the drop puts the dock below the upper group."""
        window = self.window
        nav_button = self._button(window.navigation_dock)
        self._drag(nav_button, self._center(nav_button) + QPoint(0, -DRAG_DISTANCE),
                   self._rail_point(self._group_end(0) + 4))
        self.assertGreater(window.navigation_dock.geometry().top(), window.tools_dock.geometry().bottom())
        self.assertLess(window.navigation_dock.geometry().bottom(), window.layers_dock.geometry().top())
        self.assertEqual(self._group(window.navigation_dock), {window.navigation_dock})

    def _rail_order(self, group_index: int) -> list[PanelDock]:
        return [button.dock for button in self.rail.groups[group_index] if not button.isHidden()]

    def test_drop_in_its_own_place_does_nothing(self) -> None:
        """Dropping a button where it already is in its group changes nothing, and shows no marker on the way."""
        window = self.window
        color_button = self._button(window.color_dock)
        start = self._center(color_button)
        self._press_and_move(color_button, start + QPoint(0, DRAG_DISTANCE), start + QPoint(0, -DRAG_DISTANCE))
        self.assertFalse(window.rail_drag.marker.isVisible())
        _send(color_button, QEvent.Type.MouseButtonRelease, start, LEFT, NO_BUTTON)
        self.assertTrue(window.color_dock.isHidden())
        self.assertEqual(self._rail_order(1), window.lower_docks)

    def test_drag_within_its_group_reorders_it_and_opens_the_new_first_dock(self) -> None:
        """Dragging the open first dock's button just past the second one's middle swaps them, and the second dock
        opens in its place, at its size."""
        window = self.window
        layers, color, navigation = window.lower_docks
        layers_geometry = layers.geometry()
        layers_button = self._button(layers)
        past_color = self._center(self._button(color)) + QPoint(0, 2)
        self._press_and_move(layers_button, self._center(layers_button) + QPoint(0, DRAG_DISTANCE), past_color)
        marker = window.rail_drag.marker
        self.assertTrue(marker.isVisible())
        self.assertGreater(marker.geometry().top(), self._button(color).geometry().center().y())
        _send(layers_button, QEvent.Type.MouseButtonRelease, past_color, LEFT, NO_BUTTON)
        self._activate()
        self.assertEqual(self._rail_order(1), [color, layers, navigation])
        self.assertTrue(color.is_showing)
        self.assertTrue(layers.isHidden())
        self.assertEqual(color.geometry(), layers_geometry)
        self.assertFalse(marker.isVisible())

    def test_drag_to_the_front_of_its_group_opens_the_dock(self) -> None:
        """A closed dock's button dragged before its group's first button moves to the front and opens."""
        window = self.window
        layers, color, navigation = window.lower_docks
        navigation_button = self._button(navigation)
        before_layers = self._button(layers).mapToGlobal(QPoint(self._button(layers).width() // 2, 1))
        self._drag(navigation_button, self._center(navigation_button) + QPoint(0, -DRAG_DISTANCE), before_layers)
        self.assertEqual(self._rail_order(1), [navigation, layers, color])
        self.assertTrue(navigation.is_showing)
        self.assertTrue(layers.isHidden())

    def test_clicking_a_closed_dock_moves_its_button_to_the_front_of_its_group(self) -> None:
        """Opening a closed dock from its button puts the button first in its group, ahead of the closed dock."""
        window = self.window
        layers, color, navigation = window.lower_docks
        self._button(navigation).click()
        self._activate()
        self.assertEqual(self._rail_order(1), [navigation, layers, color])
        self.assertTrue(navigation.is_showing)
        self._button(color).click()
        self.assertEqual(self._rail_order(1), [color, navigation, layers])

    def test_marker_outlines_the_target_group(self) -> None:
        """While over another group, the marker covers that group's buttons."""
        window = self.window
        tools_button = self._button(window.tools_dock)
        layers_button = self._button(window.layers_dock)
        self._press_and_move(tools_button, self._center(tools_button) + QPoint(0, DRAG_DISTANCE),
                             self._center(layers_button))
        marker = window.rail_drag.marker
        self.assertTrue(marker.isVisible())
        self.assertTrue(marker.geometry().contains(layers_button.geometry()))
        _send(tools_button, QEvent.Type.MouseButtonRelease, self._center(layers_button), LEFT, NO_BUTTON)

    def test_leaving_the_rail_hands_off_to_qt_dock_drag(self) -> None:
        """Dragging a button out of its rail floats its dock under the pointer through Qt's own dock drag."""
        window = self.window
        dock = window.layers_dock
        button = self._button(dock)
        outside = window.mapToGlobal(QPoint(300, 300))
        self._press_and_move(button, self._center(button) + QPoint(0, DRAG_DISTANCE), outside)
        self.assertTrue(dock.isFloating())
        self.assertIsInstance(dock.titleBarWidget(), FloatingTitleBar)
        _send(dock, QEvent.Type.MouseButtonRelease, outside, LEFT, NO_BUTTON)
        self.assertTrue(dock.isFloating())
        self.assertTrue(dock.geometry().contains(outside) or dock.frameGeometry().contains(outside))

    def _hand_off(self, dock: PanelDock, outside: QPoint) -> None:
        button = self._button(dock)
        self._press_and_move(button, self._center(button) + QPoint(0, DRAG_DISTANCE), outside)

    def test_handing_off_the_open_dock_opens_the_next_dock_in_its_place(self) -> None:
        """Dragging the open dock's button out of the rail leaves its group open at the same size, with the next dock
        in front."""
        window = self.window
        # Qt animates docks into place on the event loop, which tests don't run:
        window.setAnimated(False)
        layers, color, navigation = window.lower_docks
        layers_geometry = layers.geometry()
        outside = window.mapToGlobal(QPoint(300, 300))
        self._hand_off(layers, outside)
        _send(layers, QEvent.Type.MouseButtonRelease, outside, LEFT, NO_BUTTON)
        self._activate()
        self.assertTrue(layers.isFloating())
        self.assertTrue(color.is_showing)
        self.assertEqual(color.geometry(), layers_geometry)
        self.assertTrue(navigation.isHidden())
        self.assertEqual(self._rail_order(1), [color, navigation])

    def test_handing_off_a_closed_dock_leaves_its_group_as_it_was(self) -> None:
        """Dragging a closed dock's button out of the rail floats it, and its group's open dock stays open in place."""
        window = self.window
        # Qt animates docks into place on the event loop, which tests don't run:
        window.setAnimated(False)
        layers, color, _navigation = window.lower_docks
        layers_geometry = layers.geometry()
        outside = window.mapToGlobal(QPoint(300, 300))
        self._hand_off(color, outside)
        self.assertTrue(color.isFloating())
        self.assertTrue(layers.is_showing)
        _send(color, QEvent.Type.MouseButtonRelease, outside, LEFT, NO_BUTTON)
        self._activate()
        self.assertTrue(color.isFloating())
        self.assertTrue(layers.is_showing)
        self.assertEqual(layers.geometry(), layers_geometry)

    def test_hand_off_holds_the_dock_by_its_upper_left(self) -> None:
        """The handed-off dock floats with the pointer near its upper-left corner, give or take Qt's frame offset."""
        dock = self.window.layers_dock
        outside = self.window.mapToGlobal(QPoint(300, 300))
        self._hand_off(dock, outside)
        held = dock.mapFromGlobal(outside)
        self.assertLessEqual(abs(held.x() - TITLE_PRESS_INSET), 4)
        self.assertLessEqual(abs(held.y() - TITLE_PRESS_Y), 4)
        _send(dock, QEvent.Type.MouseButtonRelease, outside, LEFT, NO_BUTTON)

    def test_handed_off_drag_back_over_the_rail_places_the_dock_there(self) -> None:
        """Dragging a handed-off dock back over its rail shows the marker, and releasing there places it as a rail
        drop would."""
        window = self.window
        dock = window.tools_dock
        self._hand_off(dock, window.mapToGlobal(QPoint(300, 300)))
        self.assertTrue(dock.isFloating())
        target = self._center(self._button(window.color_dock))
        _send(dock, QEvent.Type.MouseMove, target, NO_BUTTON, LEFT)
        self.assertTrue(window.rail_drag.marker.isVisible())
        _send(dock, QEvent.Type.MouseButtonRelease, target, LEFT, NO_BUTTON)
        self._activate()
        self.assertFalse(dock.isFloating())
        self.assertIn(dock, self._group(window.layers_dock))
        self.assertTrue(dock.is_showing)
        self.assertFalse(window.rail_drag.marker.isVisible())

    def test_floating_dock_dragged_onto_a_rail_is_placed_there(self) -> None:
        """A floating dock dragged by its own title bar and released on another group's buttons is tabbed into that
        group, open."""
        window = self.window
        dock = window.navigation_dock
        dock.open_in_group()
        dock.setFloating(True)
        target = self._center(self._button(window.tools_dock))
        _send(dock, QEvent.Type.MouseMove, target, NO_BUTTON, LEFT)
        _send(dock, QEvent.Type.MouseButtonRelease, target, LEFT, NO_BUTTON)
        self._activate()
        self.assertFalse(dock.isFloating())
        self.assertIn(dock, self._group(window.tools_dock))
        self.assertTrue(dock.is_showing)

    def test_floating_dock_released_off_the_rails_stays_floating(self) -> None:
        """Leaving the rail hides the marker, and a release elsewhere leaves the dock to Qt."""
        window = self.window
        dock = window.navigation_dock
        dock.open_in_group()
        dock.setFloating(True)
        _send(dock, QEvent.Type.MouseMove, self._rail_point(self._group_end(1) + 20), NO_BUTTON, LEFT)
        away = window.mapToGlobal(QPoint(300, 300))
        _send(dock, QEvent.Type.MouseMove, away, NO_BUTTON, LEFT)
        self.assertFalse(window.rail_drag.marker.isVisible())
        _send(dock, QEvent.Type.MouseButtonRelease, away, LEFT, NO_BUTTON)
        self.assertTrue(dock.isFloating())
