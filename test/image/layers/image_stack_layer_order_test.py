"""Tests ImageStack layer reordering, group moves, deletion and duplication, with undo and redo."""
import unittest

from PySide6.QtGui import QTransform

from src.image.composite_mode import CompositeMode
from src.image.layers.image_layer import ImageLayer
from src.image.layers.layer_group import LayerGroup
from test.image.layers.image_stack_state import ImageStackOpTestCase
from test.render_assertions import full_render


class LayerOrderTest(ImageStackOpTestCase):
    """Builds [top, group [inner a, inner b], bottom], with top active."""

    def setUp(self) -> None:
        super().setUp()
        self.top, self.group, self.inner_a, self.inner_b, self.bottom = self.add_nested_layers()
        self.image_stack.active_layer = self.top
        self.stack = self.image_stack.layer_stack

    def test_reorder_within_group(self) -> None:
        """Moving a layer within its parent swaps the render order."""
        self.assert_undo_redo(lambda: self.image_stack.move_layer(self.inner_b, self.group, 0))
        self.assertEqual([self.inner_b, self.inner_a], self.group.child_layers)
        self.assertGreater(self.inner_b.z_value, self.inner_a.z_value)

    def test_reorder_top_level(self) -> None:
        """Moving the top layer to the bottom changes the composite to the new order."""
        _, after = self.assert_undo_redo(lambda: self.image_stack.move_layer(self.top, self.stack, 2))
        self.assertEqual([self.group, self.bottom, self.top], self.stack.child_layers)
        self.assertIs(self.top, after.active_layer)

    def test_move_into_group(self) -> None:
        """Moving a layer into a group keeps it active, and puts it in the group's render order."""
        _, after = self.assert_undo_redo(lambda: self.image_stack.move_layer(self.top, self.group, 1))
        self.assertEqual([self.inner_a, self.top, self.inner_b], self.group.child_layers)
        self.assertIs(self.group, self.top.layer_parent)
        self.assertIs(self.top, after.active_layer)

    def test_move_out_of_group(self) -> None:
        """Moving a layer out of a group to the top of the stack."""
        self.image_stack.active_layer = self.inner_b
        _, after = self.assert_undo_redo(lambda: self.image_stack.move_layer(self.inner_b, self.stack, 0))
        self.assertEqual([self.inner_b, self.top, self.group, self.bottom], self.stack.child_layers)
        self.assertIs(self.inner_b, after.active_layer)

    def test_move_group(self) -> None:
        """Moving a group moves its children with it."""
        self.assert_undo_redo(lambda: self.image_stack.move_layer(self.group, self.stack, 2))
        self.assertEqual([self.top, self.bottom, self.group], self.stack.child_layers)
        self.assertEqual([self.inner_a, self.inner_b], self.group.child_layers)

    def test_move_by_offset_enters_group(self) -> None:
        """Moving the layer above a group down by one puts it at the top of the group, in one undo step."""
        self.assert_undo_redo(lambda: self.image_stack.move_layer_by_offset(1, self.top))
        self.assertEqual([self.top, self.inner_a, self.inner_b], self.group.child_layers)

    def test_move_by_offset_leaves_group(self) -> None:
        """Moving a group's bottom layer down by one puts it below the group."""
        self.assert_undo_redo(lambda: self.image_stack.move_layer_by_offset(1, self.inner_b))
        self.assertEqual([self.top, self.group, self.inner_b, self.bottom], self.stack.child_layers)

    def test_remove_active_layer(self) -> None:
        """Removing the active layer activates the layer below it."""
        _, after = self.assert_undo_redo(lambda: self.image_stack.remove_layer(self.top))
        self.assertEqual([self.group, self.bottom], self.stack.child_layers)
        self.assertIs(self.group, after.active_layer)

    def test_remove_inactive_layer(self) -> None:
        """Removing another layer keeps the active layer."""
        _, after = self.assert_undo_redo(lambda: self.image_stack.remove_layer(self.inner_a))
        self.assertEqual([self.inner_b], self.group.child_layers)
        self.assertIs(self.top, after.active_layer)

    def test_remove_group(self) -> None:
        """Removing a group removes its children from the composite."""
        _, after = self.assert_undo_redo(lambda: self.image_stack.remove_layer(self.group))
        self.assertEqual([self.top, self.bottom], self.stack.child_layers)
        self.assertEqual([self.top, self.bottom], [state.layer for state in after.layers])

    def test_create_layer_with_transform(self) -> None:
        """Creating a layer with an initial transform is one undo step."""
        transform = QTransform().rotate(90) * QTransform.fromTranslate(20, 1)
        self.assert_undo_redo(lambda: self.image_stack.create_layer('created', layer_parent=self.stack,
                                                                    layer_index=0, transform=transform))
        created = self.stack.child_layers[0]
        assert isinstance(created, ImageLayer)
        self.assertEqual(transform, created.transform)

    def test_duplicate_layer_properties(self) -> None:
        """A duplicate copies the layer's pixels, transform, opacity, mode and visibility."""
        self.top.set_transform(QTransform().rotate(90) * QTransform.fromTranslate(20, 1))
        self.top.set_opacity(0.5)
        self.top.set_composition_mode(CompositeMode.SCREEN)
        self.image_stack.copy_layer(self.top)
        duplicate = self.stack.child_layers[0]
        assert isinstance(duplicate, ImageLayer)
        self.assertEqual('top copy', duplicate.name)
        self.assertEqual(self.top.transform, duplicate.transform)
        self.assertEqual(0.5, duplicate.opacity)
        self.assertEqual(CompositeMode.SCREEN, duplicate.composition_mode)
        self.assert_images_equal(duplicate.image, self.top.image)
        self.assertIsNot(duplicate.image, self.top.image)

    def test_duplicate_top_layer(self) -> None:
        """Duplicating the top layer puts the copy above it, and leaves the original active."""
        _, after = self.assert_undo_redo(lambda: self.image_stack.copy_layer(self.top))
        duplicate = self.stack.child_layers[0]
        self.assertEqual([duplicate, self.top, self.group, self.bottom], self.stack.child_layers)
        self.assertIs(self.top, after.active_layer)

    def test_duplicate_lower_layer(self) -> None:
        """Duplicating a layer below the top puts the copy directly above the original."""
        self.image_stack.copy_layer(self.inner_b)
        self.assertEqual(3, self.group.count)
        self.assertIs(self.inner_b, self.group.child_layers[2])
        self.assertEqual('inner b copy', self.group.child_layers[1].name)

    def test_duplicate_group(self) -> None:
        """A duplicated group holds copies of every child, and renders the same pixels."""
        self.group.set_opacity(0.6)
        self.inner_a.set_composition_mode(CompositeMode.MULTIPLY)
        self.image_stack.active_layer = self.group
        self.assert_undo_redo(lambda: self.image_stack.copy_layer(self.group))
        duplicate = self.stack.child_layers[1]
        assert isinstance(duplicate, LayerGroup)
        self.assertEqual('group copy', duplicate.name)
        self.assertEqual(['inner a copy', 'inner b copy'], [child.name for child in duplicate.child_layers])
        self.assertTrue(all(child not in self.group.child_layers for child in duplicate.child_layers))
        self.assertEqual(CompositeMode.MULTIPLY, duplicate.child_layers[0].composition_mode)
        self.top.set_visible(False)
        self.bottom.set_visible(False)
        self.group.set_visible(False)
        copy_render = full_render(self.image_stack)
        self.group.set_visible(True)
        duplicate.set_visible(False)
        self.assert_images_equal(copy_render, full_render(self.image_stack))

    def test_duplicate_group_keeps_isolate_and_visibility(self) -> None:
        """A duplicated group keeps the original's isolate flag and visibility, like a duplicated image layer."""
        self.group.set_isolate(True)
        self.group.set_visible(False)
        self.image_stack.copy_layer(self.group)
        duplicate = self.stack.child_layers[1]
        assert isinstance(duplicate, LayerGroup)
        self.assertEqual((True, False), (duplicate.isolate, duplicate.visible))


if __name__ == '__main__':
    unittest.main()
