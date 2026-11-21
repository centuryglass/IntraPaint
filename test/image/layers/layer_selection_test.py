"""Tests ImageStack's layer selection rules and the bulk commands in `layer_selection_ops`."""
from unittest.mock import patch

from PySide6.QtCore import QPoint, QSize

from src.image.layers import layer_selection_ops
from src.image.layers.layer_selection_ops import delete_selected_layers, duplicate_selected_layers, \
    extend_layer_selection, move_selected_layers, select_all_layers
from src.undo_stack import UndoStack
from test.image.layers.image_stack_state import ImageStackOpTestCase


class LayerSelectionTest(ImageStackOpTestCase):
    """Builds [top, group [inner a, inner b], bottom], with top active."""

    def setUp(self) -> None:
        super().setUp()
        self.top, self.group, self.inner_a, self.inner_b, self.bottom = self.add_nested_layers()
        self.image_stack.active_layer = self.top
        self.stack = self.image_stack.layer_stack
        UndoStack().clear()

    def assert_selection(self, expected: list, active) -> None:
        """Checks the selected layers in stack order, and the active layer."""
        self.assertEqual([layer.name for layer in expected],
                         [layer.name for layer in self.image_stack.selected_layers_in_order()])
        self.assertIs(active, self.image_stack.active_layer)

    # Selection model:

    def test_selection_holds_the_active_layer(self) -> None:
        """The selection starts as the active layer, and follows it when the active layer changes."""
        self.assert_selection([self.top], self.top)
        self.image_stack.active_layer = self.inner_b
        self.assert_selection([self.inner_b], self.inner_b)

    def test_select_layers_keeps_the_active_layer_selected(self) -> None:
        """An active layer missing from the requested set joins it, and the default active layer is the current one
        when selected, and otherwise the topmost."""
        self.image_stack.select_layers([self.bottom], self.inner_a)
        self.assert_selection([self.inner_a, self.bottom], self.inner_a)
        self.image_stack.select_layers([self.top, self.inner_a])
        self.assert_selection([self.top, self.inner_a], self.inner_a)
        self.image_stack.select_layers([self.bottom, self.inner_b])
        self.assert_selection([self.inner_b, self.bottom], self.inner_b)

    def test_selecting_extra_layers_is_not_an_undo_step(self) -> None:
        """Only the active layer change is undoable, and undoing it collapses the selection."""
        self.image_stack.select_layers([self.top, self.bottom], self.top)
        self.assertEqual(0, UndoStack().undo_count())
        self.image_stack.select_layers([self.top, self.bottom], self.bottom)
        self.assertEqual(1, UndoStack().undo_count())
        UndoStack().undo()
        self.assert_selection([self.top], self.top)

    def test_setting_the_active_layer_collapses_the_selection(self) -> None:
        """Setting the active layer from anywhere else, even to the layer already active, selects it alone."""
        self.image_stack.select_layers([self.top, self.inner_a, self.bottom], self.inner_a)
        self.image_stack.offset_active_selection(1)
        self.assert_selection([self.inner_b], self.inner_b)
        self.image_stack.select_layers([self.top, self.inner_b], self.inner_b)
        self.image_stack.active_layer = self.inner_b
        self.assert_selection([self.inner_b], self.inner_b)

    def test_removal_prunes_the_selection(self) -> None:
        """Removing a selected layer, or a group holding one, drops it from the selection, also by undo and redo."""
        self.image_stack.select_layers([self.top, self.inner_a, self.bottom], self.top)
        self.image_stack.remove_layer(self.group)
        self.assert_selection([self.top, self.bottom], self.top)
        UndoStack().undo()
        new_layer = self.image_stack.create_layer('new', layer_parent=self.stack, layer_index=0)
        self.image_stack.select_layers([new_layer, self.top], new_layer)
        UndoStack().undo()
        self.assertFalse(self.image_stack.is_layer_selected(new_layer))
        self.assertTrue(self.image_stack.is_layer_selected(self.top))

    def test_root_is_selected_only_alone(self) -> None:
        """The root drops out of a multi-selection, and making it active collapses the selection to it."""
        self.image_stack.select_layers([self.stack, self.top, self.bottom], self.top)
        self.assert_selection([self.top, self.bottom], self.top)
        self.image_stack.active_layer = self.stack
        self.assert_selection([self.stack], self.stack)

    def test_effective_selection_skips_descendants_of_selected_groups(self) -> None:
        """A layer inside a selected group is left out of the set bulk commands act on."""
        self.image_stack.select_layers([self.group, self.inner_b, self.bottom], self.inner_b)
        self.assertEqual([self.group, self.bottom], self.image_stack.effective_selected_layers())

    def test_selection_signal(self) -> None:
        """`selected_layers_changed` fires once per change, and not for a request that changes nothing."""
        emitted: list[None] = []
        self.image_stack.selected_layers_changed.connect(lambda: emitted.append(None))
        self.image_stack.select_layers([self.top, self.bottom])
        self.image_stack.select_layers([self.top, self.bottom])
        self.assertEqual(1, len(emitted))

    # Duplicate:

    def test_duplicate_one_layer_matches_copy_layer(self) -> None:
        """With one layer selected, duplicating copies it above itself and keeps it active."""
        duplicate_selected_layers(self.image_stack)
        self.assertEqual(['top copy', 'top', 'group', 'bottom'], [layer.name for layer in self.stack.child_layers])
        self.assert_selection([self.top], self.top)

    def test_duplicate_selection(self) -> None:
        """Each selected layer is copied just above its original, and the copies become the selection with the topmost
        active. Undo restores the selection it acted on."""
        self.image_stack.select_layers([self.top, self.inner_b, self.bottom], self.inner_b)
        self.assert_undo_redo(lambda: duplicate_selected_layers(self.image_stack))
        self.assertEqual(['top copy', 'top', 'group', 'bottom copy', 'bottom'],
                         [layer.name for layer in self.stack.child_layers])
        self.assertEqual(['inner a', 'inner b copy', 'inner b'], [layer.name for layer in self.group.child_layers])
        copies = [self.stack.child_layers[0], self.group.child_layers[1], self.stack.child_layers[3]]
        self.assert_selection(copies, copies[0])
        UndoStack().undo()
        self.assert_selection([self.top, self.inner_b, self.bottom], self.inner_b)

    def test_duplicate_selected_group_copies_it_once(self) -> None:
        """A group selected with a layer inside it is copied once, with its contents."""
        self.image_stack.select_layers([self.top, self.group, self.inner_a], self.top)
        duplicate_selected_layers(self.image_stack)
        self.assertEqual(['top copy', 'top', 'group copy', 'group', 'bottom'],
                         [layer.name for layer in self.stack.child_layers])
        self.assertEqual(2, self.stack.child_layers[2].count)

    # Delete:

    def test_delete_selection(self) -> None:
        """The selected layers go in one undo step, the layer below the lowest one becomes active, and undo restores
        the selection."""
        self.image_stack.select_layers([self.top, self.inner_a], self.inner_a)
        self.assert_undo_redo(lambda: delete_selected_layers(self.image_stack))
        self.assertEqual(['group', 'bottom'], [layer.name for layer in self.stack.child_layers])
        self.assertEqual([self.inner_b], self.group.child_layers)
        self.assert_selection([self.inner_b], self.inner_b)
        UndoStack().undo()
        self.assert_selection([self.top, self.inner_a], self.inner_a)

    def test_delete_at_the_bottom_activates_the_layer_above(self) -> None:
        """With nothing below the deleted layers, the one above the topmost becomes active, and then the root."""
        self.image_stack.select_layers([self.inner_b, self.bottom], self.bottom)
        delete_selected_layers(self.image_stack)
        self.assert_selection([self.inner_a], self.inner_a)
        self.image_stack.select_layers(self.stack.recursive_child_layers, self.top)
        delete_selected_layers(self.image_stack)
        self.assertEqual(0, self.stack.count)
        self.assert_selection([self.stack], self.stack)

    def test_delete_with_a_locked_layer_changes_nothing(self) -> None:
        """A locked layer in the selection refuses the whole delete and shows the locked-layer error."""
        self.inner_a.locked = True
        UndoStack().clear()
        self.image_stack.select_layers([self.top, self.inner_a], self.top)
        before = self.capture()
        with patch('src.image.layers.image_stack.show_error_dialog') as error_dialog:
            delete_selected_layers(self.image_stack)
        error_dialog.assert_called_once()
        self.capture().assert_matches(before, 'refused delete')
        self.assertEqual(0, UndoStack().undo_count())
        self.assert_selection([self.top, self.inner_a], self.top)

    # Move:

    def test_move_selection_keeps_its_order(self) -> None:
        """The selected layers move together to the drop spot in stack order, as one undo step, and stay selected."""
        self.image_stack.select_layers([self.top, self.inner_b], self.inner_b)
        self.assert_undo_redo(lambda: move_selected_layers(self.image_stack, self.stack, self.stack.count))
        self.assertEqual(['group', 'bottom', 'top', 'inner b'], [layer.name for layer in self.stack.child_layers])
        self.assert_selection([self.top, self.inner_b], self.inner_b)
        UndoStack().undo()
        self.assert_selection([self.top, self.inner_b], self.inner_b)

    def test_move_selection_into_a_group(self) -> None:
        """Layers from different parents land together inside a group, at an index counted before the move."""
        self.image_stack.select_layers([self.top, self.bottom], self.top)
        move_selected_layers(self.image_stack, self.group, 1)
        self.assertEqual(['inner a', 'top', 'bottom', 'inner b'], [layer.name for layer in self.group.child_layers])
        self.assertEqual([self.group], self.stack.child_layers)

    def test_move_within_a_group_counts_moved_siblings(self) -> None:
        """Moving siblings down past each other lands them above the layer at the drop index."""
        middle = self.add_layer('middle', 5, QSize(4, 4), QPoint(), self.stack)
        self.stack.move_layer(middle, 1)
        # [top, middle, group, bottom]: move top and group below bottom's slot, above nothing.
        self.image_stack.select_layers([self.top, self.group], self.top)
        move_selected_layers(self.image_stack, self.stack, 3)
        self.assertEqual(['middle', 'top', 'group', 'bottom'], [layer.name for layer in self.stack.child_layers])

    def test_move_in_place_does_nothing(self) -> None:
        """A drop that leaves the layers where they are adds no undo step."""
        self.image_stack.select_layers([self.inner_a, self.inner_b], self.inner_a)
        UndoStack().clear()
        move_selected_layers(self.image_stack, self.group, 2)
        move_selected_layers(self.image_stack, self.group, 0)
        self.assertEqual(0, UndoStack().undo_count())

    def test_drop_into_a_dragged_group_is_refused(self) -> None:
        """Dragged groups and the groups inside them can't take the drop."""
        inner_group = self.add_group('inner group', self.group)
        self.image_stack.select_layers([self.top, self.group], self.top)
        for target in (self.group, inner_group):
            self.assertFalse(layer_selection_ops.selected_layers_can_move_into(self.image_stack, self.top, target))
        self.assertTrue(layer_selection_ops.selected_layers_can_move_into(self.image_stack, self.top, self.stack))

    # Select all and extend:

    def test_select_all_layers(self) -> None:
        """Every layer under the root is selected, and the active layer stays active."""
        self.image_stack.active_layer = self.inner_a
        select_all_layers(self.image_stack)
        self.assert_selection(self.stack.recursive_child_layers, self.inner_a)
        self.image_stack.active_layer = self.stack
        select_all_layers(self.image_stack)
        self.assert_selection(self.stack.recursive_child_layers, self.top)

    def test_extend_selection(self) -> None:
        """Extending adds the next layer up or down and makes it active, and stops at the root."""
        extend_layer_selection(self.image_stack, 1)
        self.assert_selection([self.top, self.group], self.group)
        extend_layer_selection(self.image_stack, 1)
        self.assert_selection([self.top, self.group, self.inner_a], self.inner_a)
        self.image_stack.active_layer = self.top
        extend_layer_selection(self.image_stack, -1)
        self.assert_selection([self.top], self.top)

    def test_select_contents_of_several_layers(self) -> None:
        """Selecting several layers' contents selects their union."""
        self.image_stack.select_layers_content([self.top, self.inner_b])
        image = self.image_stack.selection_layer.image
        self.assertGreater(image.pixelColor(3, 3).alpha(), 0)
        self.assertGreater(image.pixelColor(20, 15).alpha(), 0)
        self.assertEqual(image.pixelColor(30, 1).alpha(), 0)
