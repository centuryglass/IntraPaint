"""Test image utility functions."""
import os
import sys
import unittest

from PIL import Image
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from src.util.image_utils import pil_image_to_qimage, qimage_to_pil_image, qimage_from_base64, pil_image_from_base64, \
    BASE_64_PREFIX, image_to_base64

app = QApplication.instance() or QApplication(sys.argv)

TEST_ARGB_IMAGE_PATH = 'test/resources/test_images/png-with-transparency.png'
TEST_RGB_IMAGE_PATH = 'test/resources/test_images/source.png'

class TestImageUtils(unittest.TestCase):
    """Test image utility functions."""

    def setUp(self) -> None:
        while os.path.basename(os.getcwd()) not in ('IntraPaint', ''):
            os.chdir('..')
        assert os.path.basename(os.getcwd()) == 'IntraPaint'
        self.qimage_argb = QImage(TEST_ARGB_IMAGE_PATH).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        self.pil_image_argb = Image.open(TEST_ARGB_IMAGE_PATH)
        self.qimage_rgb = QImage(TEST_RGB_IMAGE_PATH).convertToFormat(QImage.Format.Format_RGB888)
        self.pil_image_rgb = Image.open(TEST_RGB_IMAGE_PATH)
        self.pil_image_l = Image.new('L', (64, 64), 0)
        with open(TEST_RGB_IMAGE_PATH + '.base64.txt', 'r') as rgb_text:
            self.base64_rgb = rgb_text.read().strip('\n')
        with open(TEST_ARGB_IMAGE_PATH + '.base64.txt', 'r') as rgba_text:
            self.base64_rgba = rgba_text.read().strip('\n')

    def test_pil_image_to_qimage(self) -> None:
        """Test that PIL -> QImage conversion preserves image contents and handles invalid input correctly."""
        self.assertRaises(TypeError, lambda: pil_image_to_qimage(self.qimage_argb))
        self.assertRaises(ValueError, lambda: pil_image_to_qimage(self.pil_image_l))
        converted = pil_image_to_qimage(self.pil_image_rgb)
        self.assertEqual(converted, self.qimage_rgb)
        converted = pil_image_to_qimage(self.pil_image_argb)
        self.assertEqual(converted, self.qimage_argb)

    def test_qimage_to_pil_image(self) -> None:
        """Test that QImage -> PIL conversion preserves image contents and handles invalid input correctly."""
        self.assertRaises(TypeError, lambda: qimage_to_pil_image(self.pil_image_argb))
        converted = qimage_to_pil_image(self.qimage_rgb)
        self.assertEqual(converted.tobytes(), self.pil_image_rgb.tobytes())
        converted = qimage_to_pil_image(self.qimage_argb)
        self.assertEqual(converted.tobytes(), self.pil_image_argb.tobytes())

    def test_qimage_from_base64(self) -> None:
        """Test loading a QImage from base64 image data"""
        self.assertRaises(ValueError, lambda: qimage_from_base64('👽'))
        decoded = qimage_from_base64(self.base64_rgb)
        self.assertEqual(decoded, self.qimage_rgb)
        decoded = qimage_from_base64(BASE_64_PREFIX + self.base64_rgb)
        self.assertEqual(decoded, self.qimage_rgb)
        decoded = qimage_from_base64(self.base64_rgba)
        self.assertEqual(decoded, self.qimage_argb)

    def test_pil_image_from_base64(self) -> None:
        """Test loading a PIL image from base64 image data"""
        self.assertRaises(ValueError, lambda: pil_image_from_base64('👽'))
        decoded = pil_image_from_base64(self.base64_rgb)
        self.assertEqual(decoded.tobytes(), self.pil_image_rgb.tobytes())
        decoded = pil_image_from_base64(BASE_64_PREFIX + self.base64_rgb)
        self.assertEqual(decoded.tobytes(), self.pil_image_rgb.tobytes())
        decoded = pil_image_from_base64(self.base64_rgba)
        self.assertEqual(decoded.tobytes(), self.pil_image_argb.tobytes())

    def test_image_to_base64(self) -> None:
        """Test converting various image formats to base64"""
        self.assertEqual(image_to_base64(TEST_RGB_IMAGE_PATH), self.base64_rgb)
        self.assertEqual(image_to_base64(TEST_RGB_IMAGE_PATH, True), BASE_64_PREFIX + self.base64_rgb)
        self.assertEqual(image_to_base64(self.pil_image_rgb), self.base64_rgb)
        self.assertEqual(image_to_base64(TEST_ARGB_IMAGE_PATH), self.base64_rgba)
        self.assertEqual(image_to_base64(self.pil_image_argb), self.base64_rgba)
        # QImage does something slightly different with image encoding that prevents direct string comparison, so just
        # make sure the image is the same when re-loaded from the output:
        str64 = image_to_base64(self.qimage_rgb)
        img = qimage_from_base64(str64)
        self.assertEqual(img, self.qimage_rgb)
        str64 = image_to_base64(self.qimage_argb)
        img = qimage_from_base64(str64)
        self.assertEqual(img, self.qimage_argb)
