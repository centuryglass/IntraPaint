"""Test conversion between QImage and libmypaint image data formats."""
import os
import sys
import unittest

import numpy as np
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from src.image.mypaint.numpy_image_utils import numpy_8bit_to_16bit, numpy_16bit_to_8bit
from src.util.image_utils import image_data_as_numpy_8bit, numpy_8bit_to_qimage

app = QApplication.instance() or QApplication(sys.argv)

TEST_IMAGE_PATH = 'test/resources/test_images/layer_move_test.png'

class NumpyImageUtilsTest(unittest.TestCase):
    """Test conversion between QImage and libmypaint image data formats."""

    def setUp(self) -> None:
        while os.path.basename(os.getcwd()) not in ('IntraPaint', ''):
            os.chdir('..')
        assert os.path.basename(os.getcwd()) == 'IntraPaint'

    def test_lossless_conversion(self) -> None:
        """Converting from 8bit to 16bit should be possible without color corruption."""
        test_image = QImage(TEST_IMAGE_PATH).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)

        np_image = image_data_as_numpy_8bit(test_image)
        # Fairly sure QImage->numpy->QImage conversion is flawless, but let's check anyway
        self.assertEqual(numpy_8bit_to_qimage(np_image), test_image,
                         'QImage->numpy->QImage conversion changes image data')

        # Check that 8bit->16bit->8bit conversion doesn't corrupt colors
        np_image16 = numpy_8bit_to_16bit(np_image)
        np_image8 = numpy_16bit_to_8bit(np_image16)

        count = 0
        max_diff = 0
        min_nonzero_diff = 99999
        total = 0

        def color_difference(color1, color2):
            """Calculate the color difference between two RGB colors."""
            return np.linalg.norm(color1 - color2)

        for y in range(test_image.height()):
            for x in range(test_image.width()):
                count += 1
                diff = color_difference(np_image[y, x, :], np_image8[y, x, :])
                max_diff = max(max_diff, diff)
                if diff > 0:
                    min_nonzero_diff = min(min_nonzero_diff, diff)
                total += diff

        average = total / count
        self.assertEqual(max_diff, 0, (f'color data distorted: max change={max_diff},'
                                       f' min nonzero={min_nonzero_diff}, average: {average}'))