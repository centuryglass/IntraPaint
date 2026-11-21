"""Test image utility functions."""
import base64
import gc
import io
import sys
import weakref

import numpy as np
from PIL import Image, UnidentifiedImageError
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication

from src.util.visual.image_utils import qimage_from_base64, BASE_64_PREFIX, image_to_base64, \
    image_data_as_numpy_8bit, image_data_as_numpy_8bit_readonly, div_255, np_composite_with_mask, \
    ARGB32_RED, ARGB32_GREEN, ARGB32_BLUE, ARGB32_ALPHA, ARGB32_COLOR
from src.util.visual.pil_image_utils import pil_image_to_qimage, qimage_to_pil_image, pil_image_from_base64
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

TEST_ARGB_IMAGE_PATH = 'test/resources/test_images/png-with-transparency.png'
TEST_RGB_IMAGE_PATH = 'test/resources/test_images/source.png'

class TestImageUtils(IntraPaintTestCase):
    """Test image utility functions."""

    def setUp(self) -> None:
        super().setUp()
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
        # Premultiplied alpha can't round-trip exactly, so partially transparent pixels may be off by one:
        channel_difference = np.abs(np.asarray(converted, dtype=np.int16)
                                    - np.asarray(self.pil_image_argb.convert('RGBA'), dtype=np.int16))
        self.assertLessEqual(channel_difference.max(), 1)

    def test_argb32_channel_indexes_match_pixel_layout(self) -> None:
        """Test that the ARGB32 channel constants index each channel of a QImage's pixel buffer."""
        image = QImage(QSize(2, 2), QImage.Format.Format_ARGB32)
        image.fill(QColor(10, 20, 30, 40))
        pixel = image_data_as_numpy_8bit(image)[0, 0]
        self.assertEqual(pixel[ARGB32_RED], 10)
        self.assertEqual(pixel[ARGB32_GREEN], 20)
        self.assertEqual(pixel[ARGB32_BLUE], 30)
        self.assertEqual(pixel[ARGB32_ALPHA], 40)
        self.assertEqual(sorted(pixel[ARGB32_COLOR].tolist()), [10, 20, 30])

    def test_numpy_view_keeps_image_alive(self) -> None:
        """A numpy view of a QImage's pixels stays valid after the caller drops its QImage reference."""
        for get_view in (image_data_as_numpy_8bit, image_data_as_numpy_8bit_readonly):
            image = QImage(QSize(512, 512), QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.red)
            image_ref = weakref.ref(image)
            alpha = get_view(image)[:, :, 3]
            del image
            gc.collect()
            # Checked before reading the view, since reading freed memory can crash the test run:
            self.assertIsNotNone(image_ref(), f'{get_view.__name__} let the QImage be freed')
            self.assertEqual(alpha.max(), 255)

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

    def test_pil_image_from_base64_rejects_postscript(self) -> None:
        """Base64 image data isn't decoded as PostScript, which Pillow would run in Ghostscript."""
        eps_data = io.BytesIO()
        Image.new('RGB', (8, 8)).save(eps_data, 'EPS')
        with self.assertRaises(UnidentifiedImageError):
            pil_image_from_base64(base64.b64encode(eps_data.getvalue()).decode())

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

    def test_div_255_is_exact(self) -> None:
        """div_255 matches floor division by 255 for every value a blend of two channels can produce."""
        values = np.arange(255 * 255 + 1, dtype=np.uint32)
        np.testing.assert_array_equal(div_255(values.astype(np.uint16)), values // 255)

    def test_composite_with_mask_matches_exact_blend(self) -> None:
        """np_composite_with_mask gives floor((s * a + d * (255 - a)) / 255) for every source, destination and alpha."""
        levels = np.arange(256, dtype=np.uint8)
        # One row per alpha value, one column per (source, destination) pair:
        source_values, destination_values = (pair.ravel() for pair in np.meshgrid(levels, levels))
        width = source_values.size
        source = np.repeat(source_values[None, :, None], 4, axis=2)
        for alpha in range(256):
            destination = np.repeat(destination_values[None, :, None], 4, axis=2)
            mask = np.full((1, width, 4), alpha, dtype=np.uint8)
            expected = (source.astype(np.uint32) * alpha + destination.astype(np.uint32) * (255 - alpha)) // 255
            np_composite_with_mask(source, destination, mask)
            np.testing.assert_array_equal(destination, expected, err_msg=f'alpha {alpha}')

    def test_composite_with_mask_keeps_premultiplied_pixels_valid(self) -> None:
        """Blending two valid premultiplied pixels never leaves a color channel above alpha."""
        rng = np.random.default_rng(114)
        alpha_channels = rng.integers(0, 256, size=(2, 64, 64), dtype=np.uint8)
        source, destination = (np.concatenate([(rng.random((64, 64, 3)) * alpha[:, :, None]).astype(np.uint8),
                                               alpha[:, :, None]], axis=2) for alpha in alpha_channels)
        mask = rng.integers(0, 256, size=(64, 64, 4), dtype=np.uint8)
        np_composite_with_mask(source, destination, mask)
        self.assertTrue(np.all(destination[:, :, :3] <= destination[:, :, 3:4]))
