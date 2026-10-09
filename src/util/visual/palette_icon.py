"""Loads black-on-white line icons recolored to match a dark application palette.

Some icons are black glyphs with a white halo, drawn for light backgrounds. On a dark palette, the loaders here map
their neutral pixels from black-to-white onto `Text`-to-`Dark`, so the glyph takes the text color and the halo becomes
an ink outline. Colored pixels keep their color. On a light palette the icons load unchanged.

Icons loaded as signal icons map all their pixels, colored or not, from the signal color to the ink color, and load
unchanged under styles with no signal color.

Recolored icons and images take the application palette when they first load, and keep those colors.
"""
import os
from typing import Optional

import numpy as np
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QIcon, QImage, QImageReader, QPalette, QPixmap
from PySide6.QtWidgets import QApplication

from src.ui.ink_style import signal_color
from src.util.visual.contrast_color import relative_luminance, LUMINANCE_THRESHOLD
from src.util.visual.image_utils import image_data_as_numpy_8bit, temp_image_path

# Pixels at or above this HSV saturation keep their color. Less saturated pixels blend toward the recolored value,
# so antialiased edges between neutral and colored areas stay smooth:
COLOR_SATURATION_THRESHOLD = 0.3

# Pixmap sizes rasterized for each recolored icon. QIcon scales the nearest one to the requested size:
ICON_PIXMAP_SIZES = (16, 24, 32, 48, 64, 96, 128)

_icon_cache: dict[tuple[str, int, int, bool], QIcon] = {}


def _palette_colors() -> Optional[tuple[QColor, QColor]]:
    """Returns the colors black and white map to, or None if the application palette isn't dark."""
    palette = QApplication.palette()
    if relative_luminance(palette.color(QPalette.ColorRole.Window)) >= LUMINANCE_THRESHOLD:
        return None
    return palette.color(QPalette.ColorRole.Text), palette.color(QPalette.ColorRole.Dark)


def recolor_neutral_pixels(image: QImage, black_color: QColor, white_color: QColor,
                           keep_colored: bool = True) -> QImage:
    """Returns a copy of an image with its neutral pixels mapped from black-to-white onto black_color-to-white_color.

    Each pixel's luminance picks its point on the new range. Alpha is unchanged. Pixels at or above
    COLOR_SATURATION_THRESHOLD keep their color, unless keep_colored is false and they are mapped too.
    """
    recolored = image.convertToFormat(QImage.Format.Format_ARGB32)
    pixels = image_data_as_numpy_8bit(recolored)
    rgb = pixels[..., 2::-1].astype(np.float32) / 255
    max_channel = rgb.max(axis=-1)
    min_channel = rgb.min(axis=-1)
    saturation = np.where(max_channel > 0, (max_channel - min_channel) / np.maximum(max_channel, 1e-6), 0.0)
    if keep_colored:
        neutral_weight = np.clip(1.0 - saturation / COLOR_SATURATION_THRESHOLD, 0.0, 1.0)[..., np.newaxis]
    else:
        neutral_weight = np.ones_like(saturation)[..., np.newaxis]
    luminance = (rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32))[..., np.newaxis]
    black_rgb = np.array(black_color.getRgbF()[:3], dtype=np.float32)
    white_rgb = np.array(white_color.getRgbF()[:3], dtype=np.float32)
    mapped = black_rgb + luminance * (white_rgb - black_rgb)
    result = neutral_weight * mapped + (1.0 - neutral_weight) * rgb
    pixels[..., 2::-1] = np.round(np.clip(result, 0.0, 1.0) * 255).astype(np.uint8)
    return recolored


def palette_icon(icon_path: str, signal: bool = False) -> QIcon:
    """Loads an icon, recolored for the application palette if it is dark.

    With signal set, a dark palette's icon is drawn in the signal color instead of the text color, if the application
    style has one.
    """
    colors = _palette_colors()
    if colors is None:
        return QIcon(icon_path)
    black_color, white_color = colors
    keep_colored = True
    if signal:
        red = signal_color()
        if red is not None:
            black_color, keep_colored = red, False
    cache_key = (icon_path, black_color.rgba(), white_color.rgba(), keep_colored)
    if cache_key not in _icon_cache:
        source = QIcon(icon_path)
        icon = QIcon()
        for size in ICON_PIXMAP_SIZES:
            pixmap_image = source.pixmap(QSize(size, size)).toImage()
            recolored = recolor_neutral_pixels(pixmap_image, black_color, white_color, keep_colored)
            icon.addPixmap(QPixmap.fromImage(recolored))
        _icon_cache[cache_key] = icon
    return QIcon(_icon_cache[cache_key])


def palette_rich_text_image(image_path: str) -> str:
    """Returns a rich-text inline image of an icon at its natural size, recolored for the application palette if it
    is dark.

    Recolored images are written to temporary files at 1x and 2x scale. Qt's rich text loads the `@2x` file on
    high-density screens.
    """
    colors = _palette_colors()
    if colors is not None:
        black_color, white_color = colors
        name = (f'{os.path.splitext(os.path.basename(image_path))[0]}_{black_color.name()[1:]}'
                f'_{white_color.name()[1:]}')
        natural_size = QImageReader(image_path).size()

        def _draw_scaled(scale: int) -> QImage:
            reader = QImageReader(image_path)
            reader.setScaledSize(natural_size * scale)
            return recolor_neutral_pixels(reader.read(), black_color, white_color)
        temp_image_path(f'{name}@2x', lambda: _draw_scaled(2))
        image_path = temp_image_path(name, lambda: _draw_scaled(1))
    return f'<img src="{image_path}"/>'
