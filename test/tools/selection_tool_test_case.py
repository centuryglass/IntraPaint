"""Shared base class for tests of the tools that edit the selection layer by shape or by color."""
from typing import Optional

import numpy as np
from PySide6.QtCore import QRect, QRectF, QSize
from PySide6.QtGui import QImage

from src.config.application_config import AppConfig
from src.undo_stack import UndoStack
from src.util.visual.image_utils import image_data_as_numpy_8bit
from test.tools.tool_test_case import ToolTestCase


def rect_mask(size: QSize, rect: QRect) -> np.ndarray:
    """Returns a boolean height x width mask that is True inside rect, clipped to size."""
    mask = np.zeros((size.height(), size.width()), dtype=bool)
    clipped = rect.intersected(QRect(0, 0, size.width(), size.height()))
    if not clipped.isEmpty():
        mask[clipped.y():clipped.y() + clipped.height(), clipped.x():clipped.x() + clipped.width()] = True
    return mask


def mask_bounds(mask: np.ndarray) -> Optional[QRect]:
    """Returns the smallest rectangle holding every True pixel in a mask, or None if the mask is empty."""
    rows = np.flatnonzero(mask.any(axis=1))
    columns = np.flatnonzero(mask.any(axis=0))
    if len(rows) == 0:
        return None
    return QRect(int(columns[0]), int(rows[0]), int(columns[-1] - columns[0] + 1), int(rows[-1] - rows[0] + 1))


def _outline_points(polygons) -> list[list[tuple[float, float]]]:
    return [[point.toTuple() for point in polygon.toList()] for polygon in polygons]


class SelectionToolTestCase(ToolTestCase):
    """Base class for selection tool tests, on a small image with one layer and an empty undo history.

    Undo merging by elapsed time is off, so each committed action is its own undo step unless the tool groups it.
    The selection layer covers the whole image at the origin, so its pixels are image pixels.
    """

    IMAGE_SIZE = QSize(64, 48)

    def setUp(self) -> None:
        super().setUp()
        AppConfig().set(AppConfig.UNDO_MERGE_INTERVAL, 0.0)
        self.layer = self.image_stack.create_layer()
        self.selection_layer = self.image_stack.selection_layer
        assert self.selection_layer.position.isNull()
        assert self.selection_layer.size == self.IMAGE_SIZE
        UndoStack().clear()

    def selection_mask(self) -> np.ndarray:
        """Returns the selection layer as a boolean height x width mask of selected pixels."""
        image = self.selection_layer.image.convertToFormat(QImage.Format.Format_ARGB32)
        return image_data_as_numpy_8bit(image)[:, :, 3] > 0

    def set_selection_outside_history(self, mask: np.ndarray) -> None:
        """Replaces the selection with a boolean mask, leaving the undo history empty."""
        image = QImage(self.IMAGE_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
        np_image = image_data_as_numpy_8bit(image)
        np_image[:, :, :] = 0
        np_image[mask] = (0, 0, 255, 255)  # BGRA red
        self.selection_layer.image = image
        UndoStack().clear()
        self.assert_masks_equal(self.selection_mask(), mask)

    def assert_masks_equal(self, actual: np.ndarray, expected: np.ndarray) -> None:
        """Asserts two boolean masks match, describing where they differ."""
        self.assertEqual(actual.shape, expected.shape)
        extra = actual & ~expected
        missing = expected & ~actual
        if np.any(extra) or np.any(missing):
            self.fail(f'{np.count_nonzero(extra)} pixels unexpectedly selected (bounds {mask_bounds(extra)}), '
                      f'{np.count_nonzero(missing)} expected pixels unselected (bounds {mask_bounds(missing)})')

    def assert_selection(self, expected: np.ndarray) -> None:
        """Asserts the selection matches a boolean mask, every pixel is fully selected or unselected, and the
           selection and outline bounds both match the mask's bounds."""
        self.assert_masks_equal(self.selection_mask(), expected)
        alpha = image_data_as_numpy_8bit(self.selection_layer.image.convertToFormat(
            QImage.Format.Format_ARGB32))[:, :, 3]
        partial = (alpha != 0) & (alpha != 255)
        self.assertFalse(np.any(partial), f'{np.count_nonzero(partial)} pixels are partially selected')
        expected_bounds = mask_bounds(expected)
        self.assertEqual(self.selection_layer.get_selection_bounds(), expected_bounds)
        outline = self.selection_layer.outline
        if expected_bounds is None:
            self.assertEqual(outline, [])
            self.assertTrue(self.selection_layer.is_empty())
            return
        outline_bounds = QRectF()
        for polygon in outline:
            outline_bounds = outline_bounds.united(polygon.boundingRect())
        self.assertEqual(outline_bounds, QRectF(expected_bounds))

    def assert_one_undo_step(self, before: np.ndarray, after: np.ndarray) -> None:
        """Asserts the selection is `after`, that one undo step restores `before`, and that redo restores `after`
           and its outline."""
        self.assert_selection(after)
        outline = _outline_points(self.selection_layer.outline)
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assert_selection(before)
        UndoStack().redo()
        self.assert_selection(after)
        self.assertCountEqual(_outline_points(self.selection_layer.outline), outline)
