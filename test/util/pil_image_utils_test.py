"""Test PIL conversion edge cases and PIL scaling in pil_image_utils.

image_utils_test covers round trips of the committed test images and base64 loading.
"""
import gc

from PIL import Image
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage, QColor

from src.config.application_config import AppConfig
from src.util.shared_constants import PIL_SCALING_MODES
from src.util.visual.pil_image_utils import pil_image_to_qimage, qimage_to_pil_image, pil_qsize, pil_image_scaling
from test.base_test_case import IntraPaintTestCase


def _two_pixel_image() -> QImage:
    """Returns a 2x1 image, red on the left and blue on the right."""
    image = QImage(2, 1, QImage.Format.Format_ARGB32_Premultiplied)
    image.setPixelColor(0, 0, QColor(255, 0, 0))
    image.setPixelColor(1, 0, QColor(0, 0, 255))
    return image


class TestPilImageUtils(IntraPaintTestCase):
    """Test PIL conversion edge cases and PIL scaling in pil_image_utils."""

    def test_pil_to_qimage_formats(self) -> None:
        """RGB stays RGB888, and every other mode converts through RGBA to premultiplied ARGB32."""
        rgb = pil_image_to_qimage(Image.new('RGB', (2, 1), (10, 20, 30)))
        self.assertEqual(rgb.format(), QImage.Format.Format_RGB888)
        self.assertEqual(rgb.pixelColor(1, 0), QColor(10, 20, 30))
        for mode, color, expected in (('RGBA', (10, 20, 30, 255), QColor(10, 20, 30)),
                                      ('L', 100, QColor(100, 100, 100)),
                                      ('LA', (100, 255), QColor(100, 100, 100)),
                                      ('1', 1, QColor(255, 255, 255))):
            converted = pil_image_to_qimage(Image.new(mode, (2, 1), color))
            self.assertEqual(converted.format(), QImage.Format.Format_ARGB32_Premultiplied, mode)
            self.assertEqual(converted.pixelColor(1, 0), expected, mode)

    def test_pil_to_qimage_outlives_source(self) -> None:
        """The converted image stays valid after the PIL image and its byte buffer are released."""
        pil_image = Image.new('RGB', (64, 64), (10, 20, 30))
        converted = pil_image_to_qimage(pil_image)
        del pil_image
        gc.collect()
        self.assertEqual(converted.pixelColor(63, 63), QColor(10, 20, 30))

    def test_qimage_to_pil_unpremultiplies(self) -> None:
        """Premultiplied input comes out as straight-alpha RGBA, with zero color in fully transparent pixels.

        Filters that work on this output treat transparent pixels as black (#161).
        """
        image = QImage(3, 1, QImage.Format.Format_ARGB32_Premultiplied)
        image.setPixelColor(0, 0, QColor(255, 0, 0, 128))
        image.setPixelColor(1, 0, QColor(0, 255, 0))
        image.setPixelColor(2, 0, QColor(255, 255, 255, 0))
        converted = qimage_to_pil_image(image)
        self.assertEqual(converted.mode, 'RGBA')
        self.assertEqual([converted.getpixel((x, 0)) for x in range(3)],
                         [(255, 0, 0, 128), (0, 255, 0, 255), (0, 0, 0, 0)])

    def test_qimage_to_pil_without_alpha(self) -> None:
        """Images without an alpha channel convert to RGB mode."""
        image = QImage(1, 1, QImage.Format.Format_RGB32)
        image.fill(QColor(10, 20, 30))
        converted = qimage_to_pil_image(image)
        self.assertEqual(converted.mode, 'RGB')
        self.assertEqual(converted.getpixel((0, 0)), (10, 20, 30))

    def test_pil_qsize(self) -> None:
        """PIL image dimensions convert to a QSize."""
        self.assertEqual(pil_qsize(Image.new('RGB', (3, 7))), QSize(3, 7))

    def test_scaling_to_same_size(self) -> None:
        """A QImage already at the target size is returned as-is, and a PIL image is only converted."""
        image = _two_pixel_image()
        self.assertIs(pil_image_scaling(image, QSize(2, 1)), image)
        converted = pil_image_scaling(Image.new('RGB', (2, 1), (10, 20, 30)), QSize(2, 1))
        self.assertIsInstance(converted, QImage)
        self.assertEqual(converted.pixelColor(0, 0), QColor(10, 20, 30))

    def test_scaling_with_explicit_mode(self) -> None:
        """An explicit resampling mode is used for both QImage and PIL input."""
        scaled = pil_image_scaling(_two_pixel_image(), QSize(4, 2), Image.Resampling.NEAREST)
        self.assertEqual(scaled.size(), QSize(4, 2))
        self.assertEqual([scaled.pixelColor(x, 1) for x in range(4)],
                         [QColor(255, 0, 0)] * 2 + [QColor(0, 0, 255)] * 2)
        pil_scaled = pil_image_scaling(Image.new('RGB', (4, 4), (10, 20, 30)), QSize(2, 2), Image.Resampling.BOX)
        self.assertEqual(pil_scaled.size(), QSize(2, 2))
        self.assertEqual(pil_scaled.pixelColor(1, 1), QColor(10, 20, 30))

    def test_scaling_uses_configured_modes(self) -> None:
        """Without a mode, upscaling uses PIL_UPSCALE_MODE and downscaling uses PIL_DOWNSCALE_MODE."""
        for key in (AppConfig.PIL_UPSCALE_MODE, AppConfig.PIL_DOWNSCALE_MODE):
            AppConfig().update_options(key, list(PIL_SCALING_MODES.keys()))
        AppConfig().set(AppConfig.PIL_UPSCALE_MODE, 'Nearest')
        AppConfig().set(AppConfig.PIL_DOWNSCALE_MODE, 'Nearest')
        upscaled = pil_image_scaling(_two_pixel_image(), QSize(4, 1))
        self.assertEqual([upscaled.pixelColor(x, 0) for x in range(4)],
                         [QColor(255, 0, 0)] * 2 + [QColor(0, 0, 255)] * 2)

        AppConfig().set(AppConfig.PIL_UPSCALE_MODE, 'Bilinear')
        blended = pil_image_scaling(_two_pixel_image(), QSize(4, 1))
        self.assertNotEqual(blended.pixelColor(1, 0), QColor(255, 0, 0))

        alternating = QImage(4, 1, QImage.Format.Format_ARGB32_Premultiplied)
        for x in range(4):
            alternating.setPixelColor(x, 0, QColor(255, 0, 0) if x % 2 == 0 else QColor(0, 0, 255))
        sampled = pil_image_scaling(alternating, QSize(2, 1))
        self.assertEqual([sampled.pixelColor(x, 0) for x in range(2)], [QColor(0, 0, 255)] * 2)
        AppConfig().set(AppConfig.PIL_DOWNSCALE_MODE, 'Box')
        averaged = pil_image_scaling(alternating, QSize(2, 1))
        self.assertEqual(averaged.pixelColor(0, 0), QColor(128, 0, 128))
