"""Tests recoloring line icons for a dark palette."""
import os
import re

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QImage, QImageReader, QPalette
from PySide6.QtWidgets import QApplication

from src.ui.theme import THEME_INK, apply_theme
from src.util.visual.palette_icon import recolor_neutral_pixels, palette_icon, palette_rich_text_image
from src.util.visual.text_drawing_utils import ICON_LMB
from test.base_test_case import IntraPaintTestCase

TEXT_COLOR = QColor('#e5e5e2')
INK_COLOR = QColor('#0d0e10')


def _image_source(rich_text: str) -> str:
    match = re.search(r'src="([^"]*)"', rich_text)
    assert match is not None
    return match.group(1)


def _natural_image(icon_path: str) -> QImage:
    reader = QImageReader(icon_path)
    reader.setScaledSize(reader.size())
    return reader.read()


def _image_with_pixels(*colors: QColor) -> QImage:
    image = QImage(QSize(len(colors), 1), QImage.Format.Format_ARGB32)
    for x, color in enumerate(colors):
        image.setPixelColor(x, 0, color)
    return image


class RecolorNeutralPixelsTest(IntraPaintTestCase):
    """Tests recolor_neutral_pixels."""

    def test_black_and_white_map_to_new_range(self) -> None:
        """Black takes the first color and white the second."""
        result = recolor_neutral_pixels(_image_with_pixels(QColor('black'), QColor('white')), TEXT_COLOR, INK_COLOR)
        self.assertEqual(result.pixelColor(0, 0).name(), TEXT_COLOR.name())
        self.assertEqual(result.pixelColor(1, 0).name(), INK_COLOR.name())

    def test_alpha_unchanged(self) -> None:
        """A translucent neutral pixel is recolored and keeps its alpha."""
        result = recolor_neutral_pixels(_image_with_pixels(QColor(0, 0, 0, 100)), TEXT_COLOR, INK_COLOR)
        color = result.pixelColor(0, 0)
        self.assertEqual(color.alpha(), 100)
        self.assertEqual(color.rgb(), TEXT_COLOR.rgb())

    def test_saturated_colors_unchanged(self) -> None:
        """A saturated pixel keeps its color."""
        blue = QColor(Qt.GlobalColor.blue)
        result = recolor_neutral_pixels(_image_with_pixels(blue), TEXT_COLOR, INK_COLOR)
        self.assertEqual(result.pixelColor(0, 0).name(), blue.name())

    def test_source_unchanged(self) -> None:
        """The source image is left as it was."""
        source = _image_with_pixels(QColor('black'))
        recolor_neutral_pixels(source, TEXT_COLOR, INK_COLOR)
        self.assertEqual(source.pixelColor(0, 0).name(), QColor('black').name())


class PaletteIconTest(IntraPaintTestCase):
    """Tests loading icons through the application palette. The test session applies THEME_INK in conftest.py."""

    def tearDown(self) -> None:
        apply_theme(THEME_INK)
        super().tearDown()

    def test_dark_palette_recolors_icon(self) -> None:
        """Under the dark Ink palette, an icon's black glyph takes the text color and nothing stays black."""
        image = palette_icon(ICON_LMB).pixmap(QSize(64, 64)).toImage()
        text_color = QApplication.palette().color(QPalette.ColorRole.Text)
        colors = [image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height())]
        self.assertTrue(any(color.rgb() == text_color.rgb() for color in colors))
        self.assertFalse(any(color.alpha() == 255 and color.rgb() == QColor('black').rgb() for color in colors))

    def test_dark_palette_rich_text_writes_scaled_images(self) -> None:
        """Under a dark palette, rich-text images point to recolored files at 1x and 2x scale."""
        image_path = _image_source(palette_rich_text_image(ICON_LMB))
        base_path, extension = os.path.splitext(image_path)
        image = QImage(image_path)
        image_2x = QImage(f'{base_path}@2x{extension}')
        self.assertFalse(image.isNull())
        self.assertEqual(image.size(), QImageReader(ICON_LMB).size())
        self.assertEqual(image_2x.size(), image.size() * 2)
        self.assertNotEqual(image, _natural_image(ICON_LMB))

    def test_rich_text_image_height(self) -> None:
        """A requested height scales the image to that height, keeping the icon's aspect ratio."""
        natural_size = QImageReader(ICON_LMB).size()
        image = QImage(_image_source(palette_rich_text_image(ICON_LMB, natural_size.height() * 3)))
        self.assertEqual(image.size(), natural_size * 3)

    def test_rich_text_image_centered(self) -> None:
        """Rich-text images are centered vertically on the surrounding text."""
        self.assertIn('vertical-align: middle', palette_rich_text_image(ICON_LMB))

    def test_light_palette_loads_unchanged(self) -> None:
        """Under a light palette, rich-text images keep the icon's original colors."""
        palette = QPalette(QApplication.palette())
        palette.setColor(QPalette.ColorRole.Window, QColor('#eff0f1'))
        QApplication.setPalette(palette)
        image = QImage(_image_source(palette_rich_text_image(ICON_LMB)))
        self.assertEqual(image.convertToFormat(QImage.Format.Format_ARGB32),
                         _natural_image(ICON_LMB).convertToFormat(QImage.Format.Format_ARGB32))
