"""Tests LayerPanel and its layer widgets against changes to the layer stack.

Each structural test checks the whole widget tree with `assert_panel_matches_stack`: one widget per layer, in layer
order, shown only under expanded groups, and laid out without overlap or squeezing.
"""
import sys
from typing import Callable
from unittest.mock import MagicMock

from PySide6 import QtTest
from PySide6.QtCore import QSize, QEvent, Qt, QPoint, QPointF
from PySide6.QtWidgets import QApplication, QWidget

from src.image.composite_mode import CompositeMode
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.ui.input_fields.editable_label import EditableLabel
from src.ui.panel.layer_ui.layer_alpha_lock_button import LayerAlphaLockButton
from src.ui.panel.layer_ui.layer_group_widget import LayerGroupWidget
from src.ui.panel.layer_ui.layer_isolate_button import LayerIsolateButton
from src.ui.panel.layer_ui.layer_lock_button import LayerLockButton
from src.ui.panel.layer_ui.layer_panel import LayerPanel
from src.ui.panel.layer_ui.layer_visibility_button import LayerVisibilityButton
from src.ui.panel.layer_ui.layer_widget import LayerWidget, MENU_OPTION_MOVE_UP, MENU_OPTION_MOVE_DOWN, \
    MENU_OPTION_DELETE, MENU_OPTION_MERGE_DOWN
from src.undo_stack import UndoStack
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

IMAGE_SIZE = QSize(64, 64)
PANEL_SIZE = QSize(400, 1200)


def flush_layouts() -> None:
    """Applies pending layout changes. This dispatches already-posted layout requests and never waits."""
    QApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)


class LayerPanelTest(IntraPaintTestCase):
    """Drives LayerPanel through layer stack changes, panel controls and layer widget input."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(IMAGE_SIZE, IMAGE_SIZE, IMAGE_SIZE, IMAGE_SIZE)
        root = self.image_stack.layer_stack
        # Layer order, top to bottom: group [inner_top, nested [nested_child], inner_bottom], bottom
        self.bottom = self.image_stack.create_layer('bottom', layer_parent=root, layer_index=0)
        self.group = self.image_stack.create_layer_group('group', layer_parent=root, layer_index=0)
        self.inner_bottom = self.image_stack.create_layer('inner_bottom', layer_parent=self.group, layer_index=0)
        self.nested = self.image_stack.create_layer_group('nested', layer_parent=self.group, layer_index=0)
        self.nested_child = self.image_stack.create_layer('nested_child', layer_parent=self.nested, layer_index=0)
        self.inner_top = self.image_stack.create_layer('inner_top', layer_parent=self.group, layer_index=0)
        self.image_stack.active_layer = self.bottom
        UndoStack().clear()
        self.panel = LayerPanel(self.image_stack)
        self.panel.resize(PANEL_SIZE)
        self.panel.show()
        flush_layouts()

    def tearDown(self) -> None:
        self.panel.close()
        super().tearDown()

    @property
    def root_widget(self) -> LayerGroupWidget:
        """The widget for the root layer group."""
        return self.panel._parent_group_item

    def widget_for(self, layer: Layer) -> LayerWidget:
        """Returns the LayerWidget showing a layer: the group's own layer widget, for a group."""
        group_widget = self.root_widget
        parents: list[Layer] = []
        parent = layer.layer_parent
        while parent is not None and parent != self.image_stack.layer_stack:
            assert isinstance(parent, Layer)
            parents.insert(0, parent)
            parent = parent.layer_parent
        for parent_layer in parents:
            child = group_widget.get_child_item(parent_layer)
            assert isinstance(child, LayerGroupWidget)
            group_widget = child
        if layer == self.image_stack.layer_stack:
            return group_widget.layer_item
        item = group_widget.get_child_item(layer)
        return item.layer_item if isinstance(item, LayerGroupWidget) else item

    def group_widget_for(self, group: LayerGroup) -> LayerGroupWidget:
        """Returns the LayerGroupWidget showing a layer group."""
        group_widget = self.widget_for(group).parentWidget()
        assert group_widget is not None
        group_widget = group_widget.parentWidget()
        assert isinstance(group_widget, LayerGroupWidget)
        return group_widget

    def assert_panel_matches_stack(self) -> None:
        """Checks the whole widget tree against the layer stack, after applying pending layout changes."""
        flush_layouts()
        self._assert_group_widget_matches(self.root_widget, True)

    def _assert_group_widget_matches(self, group_widget: LayerGroupWidget, shown: bool) -> None:
        group = group_widget.layer
        child_layers = group.child_layers
        name = group.name
        self.assertEqual({layer.name for layer in child_layers},
                         {widget.layer.name for widget in group_widget.child_items}, f'{name}: widget layers')
        children_shown = shown and group_widget.is_expanded()
        child_widgets = [group_widget.get_child_item(layer) for layer in child_layers]
        for widget in child_widgets:
            self.assertIs(widget.parentWidget(), group_widget, f'{widget.layer.name}: parent widget')
            self.assertEqual(widget.isVisible(), children_shown, f'{widget.layer.name}: visibility')
        if shown:
            self.assertGreaterEqual(group_widget.height(), group_widget.minimumSizeHint().height(),
                                    f'{name}: group height')
        if children_shown:
            last_bottom = group_widget.layer_item.parentWidget().geometry().bottom()
            for widget in child_widgets:
                self.assertGreater(widget.y(), last_bottom, f'{widget.layer.name}: overlaps the widget above it')
                self.assertGreaterEqual(widget.height(), widget.minimumSizeHint().height(),
                                        f'{widget.layer.name}: height')
                last_bottom = widget.geometry().bottom()
            self.assertLessEqual(last_bottom, group_widget.height(), f'{name}: children extend past the group')
            self.assertEqual(len({widget.x() for widget in child_widgets}), min(1, len(child_widgets)),
                             f'{name}: child indent')
        for widget in child_widgets:
            if isinstance(widget, LayerGroupWidget):
                self._assert_group_widget_matches(widget, children_shown)

    def assert_change_tracked_with_undo(self, change: Callable[[], None]) -> None:
        """Checks the panel after a change, its undo, and its redo."""
        change()
        self.assert_panel_matches_stack()
        UndoStack().undo()
        self.assert_panel_matches_stack()
        UndoStack().redo()
        self.assert_panel_matches_stack()

    # Widget tree structure:

    def test_delete_button_is_right_of_the_other_buttons(self) -> None:
        """The delete button sits alone at the bar's right end, with the other buttons clustered at the left."""
        panel = self.panel
        others = (panel._add_button, panel._add_group_button, panel._move_up_button, panel._move_down_button,
                  panel._merge_down_button)
        lefts = [button.geometry().left() for button in others]
        self.assertEqual(sorted(lefts), lefts, 'buttons are in order')
        cluster_right = others[-1].geometry().right()
        delete_geometry = panel._delete_button.geometry()
        self.assertGreater(delete_geometry.left(), cluster_right + 20)
        self.assertEqual(panel._button_bar.width(), delete_geometry.right() + 1)

    def test_initial_tree_matches_stack(self) -> None:
        """The panel starts with a widget for every layer, nested like the layer stack."""
        self.assert_panel_matches_stack()

    def test_add_layers_tracked_with_undo(self) -> None:
        """New layers and groups appear at their index in their group, including mid-group inserts."""
        self.assert_change_tracked_with_undo(lambda: self.image_stack.create_layer('new', layer_parent=self.group,
                                                                                   layer_index=1))
        self.assert_change_tracked_with_undo(lambda: self.image_stack.create_layer_group('new_group',
                                                                                         layer_parent=self.nested,
                                                                                         layer_index=0))
        self.assert_change_tracked_with_undo(lambda: self.image_stack.create_layer('new_top'))

    def test_remove_layers_tracked_with_undo(self) -> None:
        """Removed layers and groups disappear, and undo restores them in place."""
        self.assert_change_tracked_with_undo(lambda: self.image_stack.remove_layer(self.inner_top))
        self.assert_change_tracked_with_undo(lambda: self.image_stack.remove_layer(self.nested))
        self.assert_change_tracked_with_undo(lambda: self.image_stack.remove_layer(self.group))

    def test_removing_groups_logs_no_warnings(self) -> None:
        """Removing a group also signals the removal of its children, which the panel expects."""
        with self.assertNoLogs('src.ui.panel.layer_ui', level='WARNING'):
            self.image_stack.remove_layer(self.group)
            UndoStack().undo()

    def test_move_layers_tracked_with_undo(self) -> None:
        """Layers moved within, into and out of groups move to the matching widget row."""
        root = self.image_stack.layer_stack
        self.assert_change_tracked_with_undo(lambda: self.image_stack.move_layer(self.inner_top, self.group, 2))
        self.assert_change_tracked_with_undo(lambda: self.image_stack.move_layer(self.bottom, self.nested, 0))
        self.assert_change_tracked_with_undo(lambda: self.image_stack.move_layer(self.nested_child, root, 0))
        self.assert_change_tracked_with_undo(lambda: self.image_stack.move_layer(self.nested, root, 2))

    def test_move_by_offset_through_nested_groups(self) -> None:
        """Moving a layer up one step at a time passes it into and out of each group without breaking the layout."""
        self.image_stack.create_layer_group('empty', layer_parent=self.nested, layer_index=1)
        root = self.image_stack.layer_stack
        move_count = 0
        while root.get_layer_index(self.bottom) != 0:
            self.image_stack.move_layer_by_offset(-1, self.bottom)
            move_count += 1
            self.assertLess(move_count, 20)
            self.assert_panel_matches_stack()
        for _ in range(move_count):
            UndoStack().undo()
            self.assert_panel_matches_stack()
        self.assertEqual(root.get_layer_index(self.bottom), 1)

    def test_move_into_last_nested_group(self) -> None:
        """Moving a layer into a nested group at the end of its parent group grows both groups to fit it."""
        self.image_stack.move_layer(self.inner_bottom, self.image_stack.layer_stack, 0)
        self.assert_panel_matches_stack()
        self.image_stack.move_layer_by_offset(-1, self.bottom)
        self.assert_panel_matches_stack()
        self.image_stack.move_layer_by_offset(-1, self.bottom)
        self.assertEqual(self.bottom.layer_parent, self.nested)
        self.assert_panel_matches_stack()

    def test_merge_and_flatten_tracked_with_undo(self) -> None:
        """Merging or flattening a group replaces its widget, and undo brings back the group's children."""
        self.assert_change_tracked_with_undo(lambda: self.image_stack.merge_group(self.nested))
        self.assert_change_tracked_with_undo(lambda: self.image_stack.flatten_layer(self.group))
        self.assert_change_tracked_with_undo(self.image_stack.merge_all_visible)

    def test_collapse_and_expand_nested_groups(self) -> None:
        """Collapsing a group hides all its descendants, and expanding it restores each nested group's own state."""
        group_widget = self.group_widget_for(self.group)
        nested_widget = self.group_widget_for(self.nested)
        nested_widget.set_expanded(False)
        self.assert_panel_matches_stack()
        group_widget.set_expanded(False)
        self.assert_panel_matches_stack()
        self.assertFalse(self.widget_for(self.inner_top).isVisible())
        group_widget.set_expanded(True)
        self.assert_panel_matches_stack()
        self.assertFalse(nested_widget.is_expanded())
        self.assertFalse(self.widget_for(self.nested_child).isVisible())

    def test_collapsed_group_shrinks(self) -> None:
        """Collapsing a group shrinks it to its own layer widget, and expanding it grows it back."""
        group_widget = self.group_widget_for(self.group)
        expanded_height = group_widget.height()
        group_widget.set_expanded(False)
        flush_layouts()
        self.assertLess(group_widget.height(), expanded_height)
        self.assertLess(self.widget_for(self.bottom).y(), group_widget.geometry().bottom() + 20)
        group_widget.set_expanded(True)
        flush_layouts()
        self.assertEqual(group_widget.height(), expanded_height)

    def test_toggle_button_collapses_group(self) -> None:
        """The group's arrow button collapses and expands it."""
        group_widget = self.group_widget_for(self.group)
        group_widget._toggle_button.click()
        self.assertFalse(group_widget.is_expanded())
        self.assert_panel_matches_stack()
        group_widget._toggle_button.click()
        self.assertTrue(group_widget.is_expanded())
        self.assert_panel_matches_stack()

    def test_adding_to_collapsed_group(self) -> None:
        """Adding a layer to a collapsed group expands the groups above it, so the new layer is shown."""
        self.group_widget_for(self.nested).set_expanded(False)
        self.group_widget_for(self.group).set_expanded(False)
        new_layer = self.image_stack.create_layer('new', layer_parent=self.nested, layer_index=0)
        self.assert_panel_matches_stack()
        self.assertTrue(self.widget_for(new_layer).isVisible())

    def test_locking_group_collapses_it(self) -> None:
        """Locking a group collapses it and its nested groups."""
        self.group.locked = True
        self.assertFalse(self.group_widget_for(self.group).is_expanded())
        self.assertFalse(self.group_widget_for(self.nested).is_expanded())
        self.assert_panel_matches_stack()

    # Active layer:

    def test_active_layer_highlighted(self) -> None:
        """Exactly one layer widget is highlighted, including when the active layer is nested."""
        for layer in (self.nested_child, self.group, self.image_stack.layer_stack, self.inner_bottom, self.bottom):
            self.image_stack.active_layer = layer
            for other_layer in self.image_stack.all_layers():
                self.assertEqual(self.widget_for(other_layer).active, other_layer == layer,
                                 f'{other_layer.name} with {layer.name} active')

    def test_new_widget_for_active_layer_is_highlighted(self) -> None:
        """A widget created for the active layer starts highlighted, as when undo restores a deleted group."""
        self.image_stack.active_layer = self.nested_child
        self.image_stack.remove_layer(self.group)
        UndoStack().undo()
        self.assertEqual(self.image_stack.active_layer, self.nested_child)
        self.assertTrue(self.widget_for(self.nested_child).active)

    def test_activation_keeps_widget_size(self) -> None:
        """Highlighting a layer widget doesn't change its size, so the list doesn't shift on click."""
        flush_layouts()
        widget = self.widget_for(self.inner_top)
        inactive_size = widget.size()
        self.image_stack.active_layer = self.inner_top
        flush_layouts()
        self.assertEqual(widget.size(), inactive_size)
        self.image_stack.active_layer = self.bottom
        flush_layouts()
        self.assertEqual(widget.size(), inactive_size)

    def test_click_activates_layer(self) -> None:
        """Clicking a layer widget makes its layer active."""
        widget = self.widget_for(self.nested_child)
        QtTest.QTest.mouseClick(widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(5, 5))
        self.assertEqual(self.image_stack.active_layer, self.nested_child)
        self.assertTrue(widget.active)

    def test_activating_layer_expands_parent_groups(self) -> None:
        """Activating a layer in a collapsed group expands every group above it."""
        self.group_widget_for(self.nested).set_expanded(False)
        self.group_widget_for(self.group).set_expanded(False)
        self.image_stack.active_layer = self.nested_child
        self.assertTrue(self.group_widget_for(self.group).is_expanded())
        self.assertTrue(self.group_widget_for(self.nested).is_expanded())
        self.assert_panel_matches_stack()

    # Panel controls:

    def test_opacity_controls(self) -> None:
        """The opacity slider and spin box set the active layer's opacity and follow each other."""
        self.panel._opacity_slider.setValue(40)
        self.assertAlmostEqual(self.bottom.opacity, 0.4)
        self.assertAlmostEqual(self.panel._opacity_spinbox.value(), 0.4)
        self.panel._opacity_spinbox.setValue(0.75)
        self.assertAlmostEqual(self.bottom.opacity, 0.75)
        self.assertEqual(self.panel._opacity_slider.value(), 75)

    def test_opacity_controls_follow_layer(self) -> None:
        """Opacity changes from outside the panel, such as undo, update the controls."""
        self.bottom.opacity = 0.5
        self.assertEqual(self.panel._opacity_slider.value(), 50)
        UndoStack().undo()
        self.assertEqual(self.bottom.opacity, 1.0)
        self.assertEqual(self.panel._opacity_slider.value(), 100)
        self.assertAlmostEqual(self.panel._opacity_spinbox.value(), 1.0)

    def test_opacity_controls_show_active_layer(self) -> None:
        """Switching the active layer shows its opacity, without changing either layer."""
        self.inner_top.opacity = 0.25
        self.image_stack.active_layer = self.inner_top
        self.assertEqual(self.panel._opacity_slider.value(), 25)
        self.assertEqual(self.bottom.opacity, 1.0)
        self.assertEqual(self.inner_top.opacity, 0.25)

    def test_mode_controls(self) -> None:
        """The mode box sets the active layer's composition mode, and follows changes from outside the panel."""
        mode_box = self.panel._mode_box
        mode_box.setCurrentIndex(mode_box.findText(CompositeMode.MULTIPLY))
        self.assertEqual(self.bottom.composition_mode, CompositeMode.MULTIPLY)
        UndoStack().undo()
        self.assertEqual(self.bottom.composition_mode, CompositeMode.NORMAL)
        self.assertEqual(mode_box.currentText(), CompositeMode.NORMAL)
        self.inner_top.composition_mode = CompositeMode.SCREEN
        self.image_stack.active_layer = self.inner_top
        self.assertEqual(mode_box.currentText(), CompositeMode.SCREEN)

    def test_locked_layer_disables_controls(self) -> None:
        """Locking the active layer or one of its groups disables the controls that would change it."""
        controls: list[QWidget] = [self.panel._opacity_slider, self.panel._opacity_spinbox, self.panel._mode_box,
                                   self.panel._delete_button, self.panel._merge_down_button]
        self.image_stack.active_layer = self.nested_child
        self.assertTrue(all(control.isEnabled() for control in controls))
        self.nested_child.locked = True
        self.assertFalse(any(control.isEnabled() for control in controls))
        self.group.locked = True
        self.nested_child.locked = False
        self.assertFalse(any(control.isEnabled() for control in controls))
        self.group.locked = False
        self.assertTrue(all(control.isEnabled() for control in controls))

    def test_root_layer_disables_controls(self) -> None:
        """The root group can't be moved, deleted, merged or given a blend mode."""
        self.image_stack.active_layer = self.image_stack.layer_stack
        for control in (self.panel._mode_box, self.panel._delete_button, self.panel._merge_down_button,
                        self.panel._move_up_button, self.panel._move_down_button):
            self.assertFalse(control.isEnabled())
        self.assertTrue(self.panel._opacity_slider.isEnabled())

    def test_add_buttons(self) -> None:
        """The add buttons create a layer or group above the active layer."""
        self.image_stack.active_layer = self.inner_bottom
        self.panel._add_button.click()
        self.assertIsInstance(self.group.get_layer_by_index(2), ImageLayer)
        self.panel._add_group_button.click()
        self.assertIsInstance(self.group.get_layer_by_index(3), LayerGroup)
        self.assertEqual(self.group.get_layer_index(self.inner_bottom), 4)
        self.assert_panel_matches_stack()

    def test_delete_button(self) -> None:
        """The delete button removes the active layer."""
        self.image_stack.active_layer = self.inner_top
        self.panel._delete_button.click()
        self.assertFalse(self.group.contains(self.inner_top))
        self.assert_panel_matches_stack()

    def test_move_buttons(self) -> None:
        """The move buttons move the active layer up or down by one step."""
        self.image_stack.active_layer = self.inner_bottom
        self.panel._move_up_button.click()
        self.assertEqual(self.nested.get_layer_index(self.inner_bottom), 1)
        self.panel._move_down_button.click()
        self.panel._move_down_button.click()
        self.assertEqual(self.image_stack.layer_stack.get_layer_index(self.inner_bottom), 1)
        self.assert_panel_matches_stack()

    def test_merge_down_button(self) -> None:
        """The merge button merges the active layer into the layer below it."""
        upper = self.image_stack.create_layer('upper', layer_parent=self.image_stack.layer_stack, layer_index=1)
        self.image_stack.active_layer = upper
        self.panel._merge_down_button.click()
        self.assertFalse(self.image_stack.layer_stack.contains(upper))
        self.assertEqual(self.image_stack.layer_stack.count, 2)
        self.assert_panel_matches_stack()

    # Layer widget controls:

    def _button(self, layer: Layer, button_type: type) -> QWidget:
        buttons = [child for child in self.widget_for(layer).findChildren(button_type)]
        self.assertEqual(len(buttons), 1, f'{layer.name}: {button_type.__name__} count')
        return buttons[0]

    def test_layer_buttons_present(self) -> None:
        """Image layers get alpha lock, groups get isolate, and every layer but the root gets lock and visibility."""
        self._button(self.bottom, LayerAlphaLockButton)
        self._button(self.group, LayerIsolateButton)
        for layer in (self.bottom, self.group, self.nested_child):
            self._button(layer, LayerLockButton)
            self._button(layer, LayerVisibilityButton)
        root_widget = self.widget_for(self.image_stack.layer_stack)
        self.assertEqual(root_widget.findChildren(LayerLockButton), [])
        self.assertEqual(root_widget.findChildren(LayerIsolateButton), [])

    def test_layer_buttons_toggle_layer(self) -> None:
        """Each layer button toggles its property, and the icon follows changes from outside the button."""
        for layer, button_type, getter in ((self.nested_child, LayerVisibilityButton, lambda: self.nested_child.visible),
                                           (self.nested_child, LayerLockButton, lambda: self.nested_child.locked),
                                           (self.inner_top, LayerAlphaLockButton, lambda: self.inner_top.alpha_locked),
                                           (self.nested, LayerIsolateButton, lambda: self.nested.isolate)):
            button = self._button(layer, button_type)
            initial_value = getter()
            initial_icon_key = button.icon().cacheKey()
            QtTest.QTest.mouseClick(button, Qt.MouseButton.LeftButton)
            self.assertEqual(getter(), not initial_value, button_type.__name__)
            self.assertNotEqual(button.icon().cacheKey(), initial_icon_key, button_type.__name__)
            UndoStack().undo()
            self.assertEqual(getter(), initial_value, button_type.__name__)
            self.assertEqual(button.icon().cacheKey(), initial_icon_key, button_type.__name__)

    def test_lock_disables_alpha_lock_button(self) -> None:
        """A layer's own lock or a group lock disables its alpha lock button, until every lock is released."""
        button = self._button(self.nested_child, LayerAlphaLockButton)
        self.nested_child.locked = True
        self.assertFalse(button.isEnabled())
        self.group.locked = True
        self.nested_child.locked = False
        self.assertFalse(button.isEnabled())
        self.group.locked = False
        self.assertTrue(button.isEnabled())

    def test_isolate_button_shows_forced_isolation(self) -> None:
        """Below full opacity or outside Normal mode, the isolate button shows isolation on and can't be toggled."""
        button = self._button(self.nested, LayerIsolateButton)
        self.assertFalse(self.nested.isolate)
        off_icon_key = button.icon().cacheKey()
        for force, restore in ((lambda: self.nested.set_opacity(0.5), lambda: self.nested.set_opacity(1.0)),
                               (lambda: self.nested.set_composition_mode(CompositeMode.MULTIPLY),
                                lambda: self.nested.set_composition_mode(CompositeMode.NORMAL))):
            force()
            self.assertFalse(button.isEnabled())
            self.assertNotEqual(button.icon().cacheKey(), off_icon_key)
            self.assertFalse(self.nested.isolate)
            restore()
            self.assertTrue(button.isEnabled())
            self.assertEqual(button.icon().cacheKey(), off_icon_key)

    def test_rename(self) -> None:
        """Editing a layer widget's label renames the layer, and renaming the layer updates the label."""
        label = self.widget_for(self.inner_top)._label
        assert isinstance(label, EditableLabel)
        label.activate_input_mode()
        label._field.setText('renamed')
        label.apply_changes()
        self.assertEqual(self.inner_top.name, 'renamed')
        UndoStack().undo()
        self.assertEqual(label.text(), 'inner_top')

    def test_lock_blocks_rename(self) -> None:
        """A layer under a locked group can't be renamed, even after its own lock is released."""
        label = self.widget_for(self.nested_child)._label
        assert isinstance(label, EditableLabel)
        self.group.locked = True
        self.nested_child.locked = True
        self.nested_child.locked = False
        # Locking collapses the groups, and the label only enters input mode while shown:
        self.image_stack.active_layer = self.nested_child
        label.activate_input_mode()
        self.assertFalse(label.is_requesting_input())
        self.group.locked = False
        self.image_stack.active_layer = self.bottom
        self.image_stack.active_layer = self.nested_child
        label.activate_input_mode()
        self.assertTrue(label.is_requesting_input())

    # Context menu:

    def _menu_actions(self, layer: Layer) -> dict[str, bool]:
        """Returns the layer's context menu options, mapped to whether each is enabled."""
        menu = self.widget_for(layer).build_menu()
        return {action.text(): action.isEnabled() for action in menu.actions()}

    def test_menu_move_options(self) -> None:
        """Move options are offered wherever a move would change something: anywhere but the ends of the stack."""
        top_actions = self._menu_actions(self.group)
        self.assertNotIn(MENU_OPTION_MOVE_UP, top_actions)
        self.assertIn(MENU_OPTION_MOVE_DOWN, top_actions)
        bottom_actions = self._menu_actions(self.bottom)
        self.assertIn(MENU_OPTION_MOVE_UP, bottom_actions)
        self.assertNotIn(MENU_OPTION_MOVE_DOWN, bottom_actions)
        for layer in (self.inner_top, self.inner_bottom, self.nested_child):
            actions = self._menu_actions(layer)
            self.assertIn(MENU_OPTION_MOVE_UP, actions, layer.name)
            self.assertIn(MENU_OPTION_MOVE_DOWN, actions, layer.name)

    def test_menu_merge_down_option(self) -> None:
        """Merge down is enabled only for a layer with an image layer below it."""
        self.assertTrue(self._menu_actions(self.inner_bottom)[MENU_OPTION_MERGE_DOWN])
        self.assertFalse(self._menu_actions(self.inner_top)[MENU_OPTION_MERGE_DOWN])
        self.assertFalse(self._menu_actions(self.bottom)[MENU_OPTION_MERGE_DOWN])

    def test_menu_locked_layer(self) -> None:
        """A locked layer's menu disables delete."""
        self.assertTrue(self._menu_actions(self.inner_top)[MENU_OPTION_DELETE])
        self.inner_top.locked = True
        self.assertFalse(self._menu_actions(self.inner_top)[MENU_OPTION_DELETE])

    # Drag and drop:

    def _drop(self, moved_layer: Layer, target_layer: Layer, below: bool) -> None:
        """Drops a layer widget onto the upper or lower half of an image layer's widget.

        Layer widgets don't accept drops, so Qt delivers the drop to the group widget containing the target."""
        target = self.widget_for(target_layer)
        drop_group = target.parentWidget()
        assert isinstance(drop_group, LayerGroupWidget)
        y_offset = target.height() * 3 // 4 if below else target.height() // 4
        position = QPointF(drop_group.mapFromGlobal(target.mapToGlobal(QPoint(target.width() // 2, y_offset))))
        event = MagicMock()
        event.source.return_value = self.widget_for(moved_layer)
        event.position.return_value = position
        drop_group.dragMoveEvent(event)
        drop_group.dropEvent(event)
        self.panel._layer_drag_end_slot()

    def test_drop_into_nested_group(self) -> None:
        """Dropping a layer below a nested group's child moves it into that group."""
        self._drop(self.bottom, self.nested_child, below=True)
        self.assertEqual(self.nested.get_layer_index(self.bottom), 1)
        self.assert_panel_matches_stack()

    def test_drop_within_group(self) -> None:
        """Dropping a layer above a sibling moves it to the sibling's index."""
        self._drop(self.inner_bottom, self.inner_top, below=False)
        self.assertEqual(self.group.get_layer_index(self.inner_bottom), 0)
        self.assert_panel_matches_stack()

    def test_drop_group_into_itself_ignored(self) -> None:
        """Dropping a group inside itself does nothing."""
        self._drop(self.group, self.nested_child, below=True)
        self.assertEqual(self.image_stack.layer_stack.get_layer_index(self.group), 0)
        self.assertEqual(UndoStack().undo_count(), 0)
        self.assert_panel_matches_stack()
