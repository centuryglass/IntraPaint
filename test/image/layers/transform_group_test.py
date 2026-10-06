"""Tests TransformGroup: its bounds, how its transform reaches the layers it holds, and its undo history."""
import sys
import unittest

import pytest
from PySide6.QtCore import QSize, QRect
from PySide6.QtGui import QTransform
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.image.layers.image_stack import ImageStack
from src.image.layers.transform_group import TransformGroup
from src.undo_stack import UndoStack
from src.util.visual.geometry_utils import transforms_approx_equal, transform_str
from test.base_test_case import IntraPaintTestCase

IMG_SIZE = QSize(512, 512)
GEN_AREA_SIZE = QSize(300, 300)
MIN_GEN_AREA = QSize(8, 8)
MAX_GEN_AREA = QSize(999, 999)
PRECISION = 5
STALE_GROUP_REASON = ('https://github.com/centuryglass/IntraPaint/issues/178: a finished group transform stays '
                      'connected to the group')
app = QApplication.instance() or QApplication(sys.argv)


class TransformGroupTest(IntraPaintTestCase):
    """Tests TransformGroup with a layer group holding two image layers, one nested in a child group."""

    def setUp(self) -> None:
        super().setUp()
        # Without time-based merging, each transform change is its own undo entry:
        AppConfig().set(AppConfig.UNDO_MERGE_INTERVAL, 0.0)
        self.image_stack = ImageStack(IMG_SIZE, GEN_AREA_SIZE, MIN_GEN_AREA, MAX_GEN_AREA)
        self.group = self.image_stack.create_layer_group('group')
        self.first = self.image_stack.create_layer('first', layer_parent=self.group, layer_index=0)
        self.first.set_size(QSize(40, 20))
        self.inner_group = self.image_stack.create_layer_group('inner', layer_parent=self.group, layer_index=1)
        self.second = self.image_stack.create_layer('second', layer_parent=self.inner_group, layer_index=0)
        self.second.set_size(QSize(20, 10))
        self.second.set_transform(QTransform.fromTranslate(60, 30))
        UndoStack().clear()
        self.transform_group = TransformGroup(self.group)
        self.menu_transform_groups: list[TransformGroup] = []

    def tearDown(self) -> None:
        # The layer group's lock_changed connection keeps each TransformGroup alive until the layer group is
        # deleted, and TransformGroup.__del__ then fails to disconnect. Disconnecting here avoids that:
        for transform_group in (self.transform_group, *self.menu_transform_groups):
            transform_group.remove_all()
        super().tearDown()

    def assert_transforms_equal(self, actual: QTransform, expected: QTransform, msg: str = '') -> None:
        """Asserts that two matrices match to PRECISION decimal places."""
        self.assertTrue(transforms_approx_equal(actual, expected, PRECISION),
                        f'{msg}\nexpected:{transform_str(expected)}actual:{transform_str(actual)}')

    def _menu_flip(self) -> None:
        """Flips the group the way the layer menu does, through a new TransformGroup that's discarded after use."""
        transform_group = TransformGroup(self.group)
        transform_group.flip_horizontal()
        self.menu_transform_groups.append(transform_group)

    def test_bounds_cover_layers(self) -> None:
        """A new group's bounds are the union of its layers' transformed bounds, at any nesting depth."""
        self.assertEqual(self.transform_group.bounds, QRect(0, 0, 80, 40))
        self.assertEqual(self.transform_group.transformed_bounds, QRect(0, 0, 80, 40))
        self.assertTrue(self.transform_group.has_layers)

    def test_set_transform_reaches_layers(self) -> None:
        """set_transform applies the change on top of each layer's own transform, and the group's bounds stay in
        its own untransformed space."""
        scale = QTransform.fromScale(2.0, 0.5)
        self.transform_group.set_transform(scale)
        self.assertEqual(self.first.transform, scale)
        # Translated by (60, 30), then scaled to (120, 15):
        self.assert_transforms_equal(self.second.transform, QTransform(2.0, 0.0, 0.0, 0.5, 120.0, 15.0))
        self.assertEqual(self.transform_group.bounds, QRect(0, 0, 80, 40))
        self.assertEqual(self.transform_group.transformed_bounds, QRect(0, 0, 160, 20))

    def test_set_transform_replaces_previous(self) -> None:
        """A second set_transform replaces the first on each layer instead of stacking on it."""
        self.transform_group.set_transform(QTransform.fromScale(2.0, 2.0))
        translate = QTransform.fromTranslate(5, 5)
        self.transform_group.set_transform(translate)
        self.assert_transforms_equal(self.first.transform, translate)
        self.assert_transforms_equal(self.second.transform, QTransform.fromTranslate(65, 35))

    def test_flip_mirrors_group_in_place(self) -> None:
        """Flipping the group mirrors every layer across the group's center, keeping the group's bounds."""
        self.transform_group.flip_horizontal()
        self.assertEqual(self.transform_group.transformed_bounds, QRect(0, 0, 80, 40))
        self.assertEqual(self.first.transformed_bounds, QRect(40, 0, 40, 20))
        self.assertEqual(self.second.transformed_bounds, QRect(0, 30, 20, 10))

    def test_rotate_about_group_center(self) -> None:
        """Rotating the group turns every layer clockwise about the group's center."""
        self.transform_group.rotate(90)
        # The 80x40 group turns about (40, 20) to cover x 20-60 and y -20-60.
        self.assertEqual(self.transform_group.transformed_bounds, QRect(20, -20, 40, 80))
        self.assertEqual(self.first.transformed_bounds, QRect(40, -20, 20, 40))
        self.assertEqual(self.second.transformed_bounds, QRect(20, 40, 10, 20))

    def test_transform_undo_redo(self) -> None:
        """The transform property change is one undo entry covering every layer."""
        self.transform_group.transform = QTransform.fromScale(2.0, 2.0)
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assert_transforms_equal(self.first.transform, QTransform())
        self.assert_transforms_equal(self.second.transform, QTransform.fromTranslate(60, 30))
        UndoStack().redo()
        self.assert_transforms_equal(self.first.transform, QTransform.fromScale(2.0, 2.0))
        self.assert_transforms_equal(self.second.transform, QTransform(2.0, 0.0, 0.0, 2.0, 120.0, 60.0))

    def test_added_layer_joins_transform(self) -> None:
        """While the group is connected, a layer added to the layer group takes on the group's transform."""
        scale = QTransform.fromScale(2.0, 2.0)
        self.transform_group.set_transform(scale)
        added = self.image_stack.create_layer('added', layer_parent=self.inner_group, layer_index=1)
        self.assertEqual(added.transform, scale)

    def test_removed_layer_leaves_transform(self) -> None:
        """While the group is connected, a layer removed from the layer group drops the group's transform."""
        self.transform_group.set_transform(QTransform.fromScale(2.0, 2.0))
        self.image_stack.move_layer(self.second, self.image_stack.layer_stack, 0)
        self.assert_transforms_equal(self.second.transform, QTransform.fromTranslate(60, 30))
        self.assertEqual(self.transform_group.bounds, QRect(0, 0, 40, 20))

    def test_bounds_follow_layer_changes(self) -> None:
        """The group's bounds update when one of its layers moves or resizes."""
        self.second.set_transform(QTransform.fromTranslate(100, 0))
        self.assertEqual(self.transform_group.bounds, QRect(0, 0, 120, 20))
        self.first.set_size(QSize(40, 50))
        self.assertEqual(self.transform_group.bounds, QRect(0, 0, 120, 50))

    def test_remove_all_keeps_transforms(self) -> None:
        """remove_all disconnects every layer and leaves each one's transform in place."""
        scale = QTransform.fromScale(2.0, 2.0)
        self.transform_group.set_transform(scale)
        self.transform_group.remove_all()
        self.assertFalse(self.transform_group.has_layers)
        self.assertEqual(self.first.transform, scale)
        added = self.image_stack.create_layer('added', layer_parent=self.group, layer_index=0)
        self.assertEqual(added.transform, QTransform())

    def test_locked_layer_locks_group(self) -> None:
        """The group is locked while any layer it holds is locked."""
        self.assertFalse(self.transform_group.locked)
        self.second.set_locked(True)
        self.assertTrue(self.transform_group.locked)
        self.second.set_locked(False)
        self.assertFalse(self.transform_group.locked)

    @pytest.mark.xfail(strict=True, reason=STALE_GROUP_REASON)
    def test_finished_group_transform_ignores_added_layer(self) -> None:
        """A layer added after a menu flip of its group is not flipped."""
        self.transform_group.remove_all()
        self._menu_flip()
        added = self.image_stack.create_layer('added', layer_parent=self.group, layer_index=0)
        self.assertEqual(added.transform, QTransform())

    @pytest.mark.xfail(strict=True, reason=STALE_GROUP_REASON)
    def test_finished_group_transform_ignores_removed_layer(self) -> None:
        """A layer moved out of a group after a menu flip of that group stays flipped."""
        self.transform_group.remove_all()
        self._menu_flip()
        flipped = self.first.transform
        self.image_stack.move_layer(self.first, self.image_stack.layer_stack, 0)
        self.assertEqual(self.first.transform, flipped)


if __name__ == '__main__':
    unittest.main()
