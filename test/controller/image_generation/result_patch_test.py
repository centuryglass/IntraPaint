"""Tests `make_result_patch`: a patch drawn Normal over the sent image reproduces the result."""
import sys

import numpy as np
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from src.controller.image_generation.result_patch import make_result_patch
from src.util.visual.image_utils import image_data_as_numpy_8bit
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

SIZE = QSize(16, 16)


def _gradient(seed: int) -> QImage:
    rng = np.random.default_rng(seed)
    pixels = rng.integers(0, 256, size=(SIZE.height(), SIZE.width(), 4), dtype=np.uint8)
    pixels[:, :, 3] = 255
    return QImage(pixels.data, SIZE.width(), SIZE.height(), QImage.Format.Format_ARGB32).copy() \
        .convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)


def _alpha_image(value: float) -> QImage:
    image = QImage(SIZE, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(0, 0, 0, round(value * 255)))
    return image


def _drawn_over(base: QImage, patch: QImage) -> QImage:
    result = base.copy()
    painter = QPainter(result)
    painter.drawImage(0, 0, patch)
    painter.end()
    return result


class ResultPatchTest(IntraPaintTestCase):
    """Tests patch exactness and alpha choices."""

    def _assert_reproduces(self, result: QImage, sent: QImage, patch: QImage, tolerance: int = 2) -> None:
        drawn = image_data_as_numpy_8bit(_drawn_over(sent, patch)).astype(int)
        expected = image_data_as_numpy_8bit(result).astype(int)
        self.assertLessEqual(int(np.abs(drawn - expected).max()), tolerance)

    def test_reproduces_result_without_estimates(self) -> None:
        """Alpha at its minimum is enough to reproduce any result."""
        sent, result = _gradient(1), _gradient(2)
        self._assert_reproduces(result, sent, make_result_patch(result, sent))

    def test_reproduces_result_with_wrong_estimate(self) -> None:
        """A blend estimate far from the real blend changes the patch alpha, not the result."""
        sent, result = _gradient(3), _gradient(4)
        for value in (0.0, 0.3, 1.0):
            patch = make_result_patch(result, sent, _alpha_image(value))
            self._assert_reproduces(result, sent, patch)

    def test_unchanged_pixels_are_transparent(self) -> None:
        """Where the result equals the sent image and the estimate is zero, the patch adds nothing."""
        sent = _gradient(5)
        patch = make_result_patch(sent.copy(), sent, _alpha_image(0.0))
        self.assertTrue((image_data_as_numpy_8bit(patch)[:, :, 3] == 0).all())

    def test_estimate_is_a_floor_over_opaque_source(self) -> None:
        """Over an opaque source, the patch alpha is at least the estimate."""
        sent = _gradient(6)
        patch = make_result_patch(sent.copy(), sent, _alpha_image(0.5), _alpha_image(1.0))
        self.assertTrue((image_data_as_numpy_8bit(patch)[:, :, 3] >= 127).all())

    def test_estimate_floor_drops_over_transparent_source(self) -> None:
        """Where the source was transparent, a result that only repaints the backdrop leaves the patch transparent."""
        sent = _gradient(7)
        patch = make_result_patch(sent.copy(), sent, _alpha_image(1.0), _alpha_image(0.0))
        self.assertTrue((image_data_as_numpy_8bit(patch)[:, :, 3] == 0).all())

    def test_size_mismatch_raises(self) -> None:
        """Images of different sizes can't be compared pixel for pixel."""
        with self.assertRaises(ValueError):
            make_result_patch(QImage(QSize(4, 4), QImage.Format.Format_ARGB32), _gradient(8))
