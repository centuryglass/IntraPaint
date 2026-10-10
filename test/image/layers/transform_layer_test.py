"""Tests TransformLayer's bounds math, menu rotate and flip, transform undo, and the matrix-to-parameters round trip.

Expected bounds and matrices are worked out by hand from the layer's corners, so a change to the shared geometry
helpers can't move the expectation along with the result.
"""
import sys
import unittest
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QSize, QRect, QPoint, QPointF
from PySide6.QtGui import QTransform, QImage, QColor, QPainter, Qt
from PySide6.QtWidgets import QApplication

from src.image.layers.image_layer import ImageLayer
from src.undo_stack import UndoStack
from src.util.visual.geometry_utils import (extract_transform_parameters, combine_transform_parameters,
                                            transforms_approx_equal, transform_str)
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

LAYER_SIZE = QSize(100, 50)
LAYER_CENTER = QPointF(50.0, 25.0)
PRECISION = 5


def _about_center(transform: QTransform) -> QTransform:
    """Returns a transform that applies the given one about the test layer's center."""
    return (QTransform.fromTranslate(-LAYER_CENTER.x(), -LAYER_CENTER.y()) * transform
            * QTransform.fromTranslate(LAYER_CENTER.x(), LAYER_CENTER.y()))


# Transforms the layer transform tool and menu actions can produce, as (label, matrix) pairs. Each is a scale,
# a rotation and a translation applied in that order about some origin, which is the form
# extract_transform_parameters decomposes.
TOOL_TRANSFORMS = [
    ('identity', QTransform()),
    ('translate', QTransform.fromTranslate(30.0, -12.5)),
    ('uniform scale', QTransform.fromScale(2.0, 2.0)),
    ('uneven scale', QTransform.fromScale(0.25, 3.0)),
    ('rotate 45', QTransform().rotate(45.0)),
    ('rotate 90', QTransform().rotate(90.0)),
    ('rotate 180', QTransform().rotate(180.0)),
    ('rotate 270', QTransform().rotate(270.0)),
    ('rotate -30', QTransform().rotate(-30.0)),
    ('flip horizontal', QTransform.fromScale(-1.0, 1.0)),
    ('flip vertical', QTransform.fromScale(1.0, -1.0)),
    ('flip both', QTransform.fromScale(-1.0, -1.0)),
    ('flip horizontal, rotate 200', QTransform.fromScale(-1.0, 1.0) * QTransform().rotate(200.0)),
    ('scale, rotate, translate', QTransform.fromScale(1.5, 0.5) * QTransform().rotate(37.0)
     * QTransform.fromTranslate(80.0, 40.0)),
    ('flip, scale, rotate about center, translate', _about_center(QTransform.fromScale(-0.75, 2.0)
                                                                  * QTransform().rotate(123.0))
     * QTransform.fromTranslate(-15.0, 7.0)),
]

# The transform tool lets the origin sit anywhere inside the layer bounds.
ORIGINS = [QPointF(), LAYER_CENTER, QPointF(100.0, 50.0), QPointF(12.5, 40.0)]


class TransformLayerTest(IntraPaintTestCase):
    """Tests TransformLayer through ImageLayer, its simplest concrete subclass."""

    def setUp(self) -> None:
        super().setUp()
        self.layer = ImageLayer(LAYER_SIZE, 'transform test layer')

    def assert_transforms_equal(self, actual: QTransform, expected: QTransform, msg: str = '') -> None:
        """Asserts that two matrices match to PRECISION decimal places."""
        self.assertTrue(transforms_approx_equal(actual, expected, PRECISION),
                        f'{msg}\nexpected:{transform_str(expected)}actual:{transform_str(actual)}')

    def assert_points_equal(self, actual: QPointF, expected: QPointF, msg: str = '') -> None:
        """Asserts that two points match to PRECISION decimal places."""
        self.assertAlmostEqual(actual.x(), expected.x(), PRECISION, msg)
        self.assertAlmostEqual(actual.y(), expected.y(), PRECISION, msg)

    def _canvas_center(self) -> QPointF:
        """Returns where the layer's center lands on the canvas."""
        return self.layer.transform.map(LAYER_CENTER)

    # Bounds:

    def test_transformed_bounds(self) -> None:
        """transformed_bounds is the smallest integer rect covering the layer's mapped corners."""
        cases = [
            ('identity', QTransform(), QRect(0, 0, 100, 50)),
            ('translate', QTransform.fromTranslate(10, 20), QRect(10, 20, 100, 50)),
            # Fractional edges widen the rect outward to cover them: x 10.5-110.5, y 20.25-70.25.
            ('fractional translate', QTransform.fromTranslate(10.5, 20.25), QRect(10, 20, 101, 51)),
            ('scale', QTransform.fromScale(2.0, 0.5), QRect(0, 0, 200, 25)),
            ('flip horizontal', QTransform.fromScale(-1.0, 1.0), QRect(-100, 0, 100, 50)),
            ('flip vertical', QTransform.fromScale(1.0, -1.0), QRect(0, -50, 100, 50)),
            # (x, y) -> (-y, x): corners land at (0, 0), (0, 100), (-50, 0) and (-50, 100).
            ('rotate 90', QTransform().rotate(90.0), QRect(-50, 0, 50, 100)),
            ('rotate 180', QTransform().rotate(180.0), QRect(-100, -50, 100, 50)),
            # Corners land at (0, 0), (70.71, 70.71), (-35.36, 35.36) and (35.36, 106.07).
            ('rotate 45', QTransform().rotate(45.0), QRect(-36, 0, 107, 107)),
            # Scaled to 200x50, rotated to x -50-0 and y 0-200, then moved by (100, 100).
            ('scale, rotate, translate', QTransform.fromScale(2.0, 1.0) * QTransform().rotate(90.0)
             * QTransform.fromTranslate(100, 100), QRect(50, 100, 50, 200)),
            # y gains 0.3 * x, so the right edge spans y 30-80.
            ('shear', QTransform(1.0, 0.3, 0.0, 1.0, 50.0, 50.0), QRect(50, 50, 100, 80)),
        ]
        for label, transform, expected in cases:
            with self.subTest(label):
                self.layer.set_transform(transform)
                self.assertEqual(self.layer.bounds, QRect(QPoint(), LAYER_SIZE))
                self.assertEqual(self.layer.transformed_bounds, expected)
                self.assertEqual(self.layer.map_rect_to_image(self.layer.bounds), expected)

    def test_map_points(self) -> None:
        """map_to_image and map_from_image apply the transform and its inverse."""
        self.layer.set_transform(QTransform.fromScale(2.0, 1.0) * QTransform().rotate(90.0)
                                 * QTransform.fromTranslate(100, 100))
        # (100, 0) scales to (200, 0), rotates to (0, 200), then moves to (100, 300).
        self.assertEqual(self.layer.map_to_image(QPoint(100, 0)), QPoint(100, 300))
        self.assert_points_equal(self.layer.map_from_image(QPointF(100.0, 300.0)), QPointF(100.0, 0.0))
        self.assert_points_equal(self.layer.map_from_image(QPointF(75.0, 140.0)), QPointF(20.0, 25.0))

    def test_map_rect_from_image(self) -> None:
        """map_rect_from_image covers every layer pixel under the given canvas rect."""
        self.layer.set_transform(QTransform.fromScale(2.0, 2.0) * QTransform.fromTranslate(10, 10))
        self.assertEqual(self.layer.map_rect_from_image(QRect(10, 10, 200, 100)), QRect(0, 0, 100, 50))
        # Canvas x 11-15 is layer x 0.5-2.5, which touches layer pixels 0-2.
        self.assertEqual(self.layer.map_rect_from_image(QRect(11, 11, 4, 4)), QRect(0, 0, 3, 3))

    def test_transformed_image_translation_only(self) -> None:
        """With only a translation, transformed_image returns the layer image and transform unchanged."""
        transform = QTransform.fromTranslate(7, -3)
        self.layer.set_transform(transform)
        image, final_transform = self.layer.transformed_image()
        self.assertEqual(final_transform, transform)
        self.assert_images_equal(image, self.layer.image)

    def test_transformed_image_rotation(self) -> None:
        """transformed_image paints the rotation into a new image and returns only the remaining translation."""
        image = QImage(LAYER_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.blue)
        painter = QPainter(image)
        painter.fillRect(QRect(0, 0, 50, 50), Qt.GlobalColor.red)
        painter.end()
        self.layer.image = image
        self.layer.set_transform(QTransform().rotate(90.0) * QTransform.fromTranslate(60, 10))
        rendered, final_transform = self.layer.transformed_image()
        self.assertEqual(final_transform, QTransform.fromTranslate(10, 10))
        self.assertEqual(rendered.size(), QSize(50, 100))
        # Rotating 90 degrees clockwise turns the left (red) half into the top half.
        self.assertEqual(rendered.pixelColor(25, 25), QColor(Qt.GlobalColor.red))
        self.assertEqual(rendered.pixelColor(25, 75), QColor(Qt.GlobalColor.blue))

    # Menu rotate and flip:

    def test_rotate_about_center(self) -> None:
        """rotate turns the layer clockwise on the canvas about its center."""
        self.layer.rotate(90)
        self.assert_transforms_equal(self.layer.transform, _about_center(QTransform().rotate(90.0)))
        self.assertEqual(self.layer.transformed_bounds, QRect(25, -25, 50, 100))
        self.assert_points_equal(self._canvas_center(), LAYER_CENTER)

    def test_rotate_four_times_is_identity(self) -> None:
        """Four quarter turns return the layer to its starting transform."""
        start = QTransform.fromScale(1.5, 0.5) * QTransform.fromTranslate(20, 30)
        self.layer.set_transform(start)
        for _ in range(4):
            self.layer.rotate(90)
        self.assert_transforms_equal(self.layer.transform, start)

    def test_rotate_stacks_on_transform(self) -> None:
        """rotate applies after the existing transform, about where the layer's center sits on the canvas."""
        start = QTransform.fromScale(2.0, 0.5) * QTransform().rotate(30.0) * QTransform.fromTranslate(40, 60)
        self.layer.set_transform(start)
        center = self._canvas_center()
        self.layer.rotate(-90)
        expected = (start * QTransform.fromTranslate(-center.x(), -center.y()) * QTransform().rotate(-90.0)
                    * QTransform.fromTranslate(center.x(), center.y()))
        self.assert_transforms_equal(self.layer.transform, expected)

    def test_rotate_flipped_layer_turns_clockwise(self) -> None:
        """rotate on a flipped layer still turns it clockwise on the canvas."""
        for label, flip in (('horizontal', self.layer.flip_horizontal), ('vertical', self.layer.flip_vertical)):
            with self.subTest(label):
                self.layer.set_transform(QTransform())
                flip()
                flipped = self.layer.transform
                self.layer.rotate(90)
                self.assert_transforms_equal(self.layer.transform, flipped * _about_center(QTransform().rotate(90.0)))

    def test_flip_keeps_bounds(self) -> None:
        """Flipping mirrors the layer about its center, so its canvas bounds stay in place."""
        self.layer.flip_horizontal()
        self.assert_transforms_equal(self.layer.transform, QTransform(-1.0, 0.0, 0.0, 1.0, 100.0, 0.0))
        self.assertEqual(self.layer.transformed_bounds, QRect(0, 0, 100, 50))
        self.layer.set_transform(QTransform())
        self.layer.flip_vertical()
        self.assert_transforms_equal(self.layer.transform, QTransform(1.0, 0.0, 0.0, -1.0, 0.0, 50.0))
        self.assertEqual(self.layer.transformed_bounds, QRect(0, 0, 100, 50))

    def test_flip_twice_is_identity(self) -> None:
        """Flipping twice on the same axis restores the starting transform."""
        start = QTransform.fromScale(1.5, 0.5) * QTransform().rotate(30.0) * QTransform.fromTranslate(20, 30)
        for label, flip in (('horizontal', self.layer.flip_horizontal), ('vertical', self.layer.flip_vertical)):
            with self.subTest(label):
                self.layer.set_transform(start)
                flip()
                self.assertFalse(transforms_approx_equal(self.layer.transform, start, PRECISION))
                flip()
                self.assert_transforms_equal(self.layer.transform, start)

    def test_flip_rotated_layer_mirrors_layer_axis(self) -> None:
        """Flipping a rotated layer mirrors it across its own axis, keeping its canvas center in place."""
        rotation = _about_center(QTransform().rotate(30.0))
        self.layer.set_transform(rotation)
        self.layer.flip_horizontal()
        self.assert_transforms_equal(self.layer.transform, _about_center(QTransform.fromScale(-1.0, 1.0)) * rotation)
        self.assert_points_equal(self._canvas_center(), LAYER_CENTER)

    # Matrix to parameters round trip:

    def test_parameter_round_trip(self) -> None:
        """extract_transform_parameters then combine_transform_parameters returns the same matrix, at any origin."""
        for label, transform in TOOL_TRANSFORMS:
            for origin in ORIGINS:
                with self.subTest(f'{label} about ({origin.x()}, {origin.y()})'):
                    params = extract_transform_parameters(transform, origin)
                    self.assert_transforms_equal(combine_transform_parameters(*params, origin), transform)

    def test_parameter_round_trip_after_menu_actions(self) -> None:
        """Every transform a sequence of menu rotates and flips leaves on the layer survives the round trip."""
        self.layer.set_transform(QTransform.fromScale(1.25, 0.8) * QTransform.fromTranslate(5, 5))
        for action in (lambda: self.layer.rotate(90), self.layer.flip_horizontal, lambda: self.layer.rotate(-90),
                       self.layer.flip_vertical, lambda: self.layer.rotate(90), lambda: self.layer.rotate(90)):
            action()
            for origin in ORIGINS:
                params = extract_transform_parameters(self.layer.transform, origin)
                self.assert_transforms_equal(combine_transform_parameters(*params, origin), self.layer.transform)

    @pytest.mark.xfail(strict=True, reason='https://github.com/centuryglass/IntraPaint/issues/119: transform '
                                           'parameters have no room for shear')
    def test_parameter_round_trip_with_shear(self) -> None:
        """A sheared matrix survives the round trip."""
        transform = QTransform(1.0, 0.3, 0.0, 1.0, 50.0, 50.0)
        params = extract_transform_parameters(transform, LAYER_CENTER)
        self.assert_transforms_equal(combine_transform_parameters(*params, LAYER_CENTER), transform)

    # Transform changes and undo:

    def test_transform_returns_copy(self) -> None:
        """Changing the matrix the transform property returns leaves the layer unchanged."""
        transform = self.layer.transform
        transform.translate(5, 5)
        self.assertEqual(self.layer.transform, QTransform())

    def test_set_transform_signals(self) -> None:
        """set_transform emits transform_changed, and content_changed only while the layer is visible."""
        transform_changed = MagicMock()
        content_changed = MagicMock()
        self.layer.transform_changed.connect(transform_changed)
        self.layer.content_changed.connect(content_changed)
        transform = QTransform.fromTranslate(4, 2)
        self.layer.set_transform(transform)
        transform_changed.assert_called_once_with(self.layer, transform)
        content_changed.assert_called_once()

        transform_changed.reset_mock()
        content_changed.reset_mock()
        self.layer.set_transform(QTransform.fromTranslate(4, 2))
        transform_changed.assert_not_called()
        content_changed.assert_not_called()

        self.layer.set_visible(False)
        transform_changed.reset_mock()
        content_changed.reset_mock()
        self.layer.set_transform(QTransform())
        transform_changed.assert_called_once_with(self.layer, QTransform())
        content_changed.assert_not_called()

    def test_set_transform_rejects_non_invertible(self) -> None:
        """set_transform rejects a matrix that can't be inverted."""
        with self.assertRaises(AssertionError):
            self.layer.set_transform(QTransform.fromScale(0.0, 1.0))
        self.assertEqual(self.layer.transform, QTransform())

    def test_set_transform_skips_undo(self) -> None:
        """set_transform changes the layer without adding an undo entry."""
        self.layer.set_transform(QTransform.fromTranslate(4, 2))
        self.assertEqual(UndoStack().undo_count(), 0)

    def test_transform_undo_redo(self) -> None:
        """Each transform property change is one undo entry that undo and redo reverse and reapply."""
        first = QTransform.fromTranslate(10, 0)
        second = first * _about_center(QTransform().rotate(45.0))
        self.layer.transform = first
        self.layer.transform = second
        self.assertEqual(UndoStack().undo_count(), 2)
        UndoStack().undo()
        self.assertEqual(self.layer.transform, first)
        UndoStack().undo()
        self.assertEqual(self.layer.transform, QTransform())
        UndoStack().redo()
        self.assertEqual(self.layer.transform, first)
        UndoStack().redo()
        self.assertEqual(self.layer.transform, second)

    def test_menu_actions_undo(self) -> None:
        """rotate and flip each add one undo entry."""
        self.layer.rotate(90)
        rotated = self.layer.transform
        self.layer.flip_horizontal()
        self.assertEqual(UndoStack().undo_count(), 2)
        UndoStack().undo()
        self.assertEqual(self.layer.transform, rotated)
        UndoStack().undo()
        self.assertEqual(self.layer.transform, QTransform())

    def test_transform_changes_merge_inside_gesture(self) -> None:
        """Transform changes inside one gesture merge into one entry that restores the transform from before the
        first."""
        UndoStack().begin_gesture('test.drag')
        for x in range(1, 4):
            self.layer.transform = QTransform.fromTranslate(x, 0)
        UndoStack().end_gesture()
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assertEqual(self.layer.transform, QTransform())
        UndoStack().redo()
        self.assertEqual(self.layer.transform, QTransform.fromTranslate(3, 0))

    def test_locked_layer_rejects_transform(self) -> None:
        """Changing a locked layer's transform through the property fails and leaves it unchanged."""
        self.layer.set_locked(True)
        with self.assertRaises(AssertionError):
            self.layer.transform = QTransform.fromTranslate(4, 2)
        with self.assertRaises(AssertionError):
            self.layer.rotate(90)
        self.assertEqual(self.layer.transform, QTransform())
        self.assertEqual(UndoStack().undo_count(), 0)


if __name__ == '__main__':
    unittest.main()
