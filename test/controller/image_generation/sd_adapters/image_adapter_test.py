"""Tests the QImage <-> PIL conversions the Stable Diffusion generators use with sd_backend_client."""
import io
import os

from PIL import Image
from PySide6.QtGui import QImage, QColor

from src.controller.image_generation.sd_adapters.image_adapter import qimage_to_pil, pil_to_qimage
from test.base_test_case import IntraPaintTestCase, TEST_IMAGE_DIR

# Image with partially transparent pixels, used as its own golden image: a lossless round trip must reproduce it.
ALPHA_IMAGE = os.path.join(TEST_IMAGE_DIR, 'rgb_alpha.png')


def _png_round_trip(image: Image.Image) -> Image.Image:
    """Encodes and decodes an image as PNG, normalized to RGBA, the way the library sends and receives images."""
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    decoded = Image.open(io.BytesIO(buffer.getvalue()))
    decoded.load()
    return decoded.convert('RGBA')


class ImageAdapterTest(IntraPaintTestCase):
    """Tests the QImage <-> PIL conversions the Stable Diffusion generators use with sd_backend_client."""

    def test_round_trip_matches_golden(self) -> None:
        """Converting a partial-alpha image to PIL, through PNG and back gives the same premultiplied pixels."""
        source = QImage(ALPHA_IMAGE).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        self.assertFalse(source.isNull())
        restored = pil_to_qimage(_png_round_trip(qimage_to_pil(source)))
        self.assertEqual(restored.format(), QImage.Format.Format_ARGB32_Premultiplied)
        self.assert_image_matches_golden(restored, ALPHA_IMAGE)

    def test_qimage_to_pil_is_straight_alpha_rgba(self) -> None:
        """Premultiplied and opaque QImages both become straight-alpha RGBA."""
        image = QImage(2, 1, QImage.Format.Format_ARGB32_Premultiplied)
        image.setPixelColor(0, 0, QColor(255, 0, 0, 128))
        image.setPixelColor(1, 0, QColor(255, 255, 255, 0))
        converted = qimage_to_pil(image)
        self.assertEqual(converted.mode, 'RGBA')
        self.assertEqual([converted.getpixel((x, 0)) for x in range(2)], [(255, 0, 0, 128), (0, 0, 0, 0)])

        opaque = QImage(1, 1, QImage.Format.Format_RGB32)
        opaque.fill(QColor(10, 20, 30))
        converted = qimage_to_pil(opaque)
        self.assertEqual(converted.mode, 'RGBA')
        self.assertEqual(converted.getpixel((0, 0)), (10, 20, 30, 255))

    def test_pil_to_qimage_is_premultiplied(self) -> None:
        """RGB and straight-alpha PIL images both become premultiplied QImages."""
        for mode, color, expected in (('RGB', (10, 20, 30), QColor(10, 20, 30)),
                                      ('RGBA', (255, 0, 0, 128), QColor(255, 0, 0, 128))):
            converted = pil_to_qimage(Image.new(mode, (1, 1), color))
            self.assertEqual(converted.format(), QImage.Format.Format_ARGB32_Premultiplied, mode)
            self.assertEqual(converted.pixelColor(0, 0), expected, mode)
