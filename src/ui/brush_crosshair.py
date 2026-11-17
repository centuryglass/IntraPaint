"""Fixed-size crosshair cursors for the variable-size brush tools.

The crosshair marks where the brush lands. `BrushOutline` shows the brush's size, so the crosshair stays the same size
at every brush size and zoom level. Each `CrosshairVariant` is a pixel pattern drawn as a dark core over a light halo,
so it reads on any background, and is pixel-doubled on high-density screens.
"""
import math
from enum import Enum
from functools import cache
from typing import Sequence

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QCursor, QImage, QPainter, QPixmap

# Patterns are square grids of this size with an odd side, so the hotspot is the centre pixel:
CROSSHAIR_GRID_SIZE = 15

# Halo width around the core, in logical pixels. BrushOutline draws its halo at the same width.
HALO_WIDTH = 2

# Halo pixels within this many pixels (Chebyshev distance) of the hotspot are left out, keeping the target pixel
# visible. A pattern keeps its own core pixels out of this area unless it marks the centre.
CENTER_CUTOUT = 1

# Logical size of a generated crosshair, halo included:
CROSSHAIR_SIZE = CROSSHAIR_GRID_SIZE + 2 * HALO_WIDTH

CORE_COLOR = QColor(0, 0, 0)
HALO_COLOR = QColor(255, 255, 255, 220)


class CrosshairVariant(Enum):
    """Crosshair designs. Adding one means adding its pattern to `_PATTERNS`."""
    PLAIN = 'plain'
    SELECTION_BRUSH = 'selection brush'
    BRUSH = 'brush'
    DRAW = 'draw'
    FILTER = 'filter'
    SMUDGE = 'smudge'
    CLONE = 'clone'
    CLONE_SOURCE = 'clone source'
    ERASER = 'eraser'


# '#' marks a core pixel. Rows run top to bottom.
_PATTERNS: dict[CrosshairVariant, tuple[str, ...]] = {
    CrosshairVariant.PLAIN: (
        '.......#.......',
        '.......#.......',
        '.......#.......',
        '.......#.......',
        '.......#.......',
        '...............',
        '...............',
        '#####.....#####',
        '...............',
        '...............',
        '.......#.......',
        '.......#.......',
        '.......#.......',
        '.......#.......',
        '.......#.......',
    ),
    CrosshairVariant.SELECTION_BRUSH: (
        '###.........###',
        '##...........##',
        '#.............#',
        '.......#.......',
        '....#.....#....',
        '...............',
        '...............',
        '...#.......#...',
        '...............',
        '...............',
        '....#.....#....',
        '.......#.......',
        '#.............#',
        '##...........##',
        '###.........###',
    ),
    CrosshairVariant.BRUSH: (
        '##...........##',
        '###.........###',
        '.##.........##.',
        '...#.......#...',
        '......###......',
        '.......#.......',
        '....#.....#....',
        '....##...##....',
        '....#.....#....',
        '.......#.......',
        '......###......',
        '...#.......#...',
        '.##.........##.',
        '###.........###',
        '##...........##',
    ),
    CrosshairVariant.DRAW: (
        '....#######....',
        '......###......',
        '.......#.......',
        '.......#.......',
        '#......#......#',
        '#.............#',
        '##...........##',
        '#####.....#####',
        '##...........##',
        '#.............#',
        '#......#......#',
        '.......#.......',
        '.......#.......',
        '......###......',
        '....#######....',
    ),
    CrosshairVariant.FILTER: (
        '##.....#.....##',
        '#......#......#',
        '...............',
        '...............',
        '...............',
        '...............',
        '...............',
        '##...........##',
        '...............',
        '...............',
        '...............',
        '...............',
        '...............',
        '#......#......#',
        '##.....#.....##',
    ),
    CrosshairVariant.SMUDGE: (
        '....#.#.#.#....',
        '.....#.#.#.....',
        '......#.#......',
        '...............',
        '#.............#',
        '.#...........#.',
        '#.#.........#.#',
        '.#...........#.',
        '#.#.........#.#',
        '.#...........#.',
        '#.............#',
        '...............',
        '......#.#......',
        '.....#.#.#.....',
        '....#.#.#.#....',
    ),
    CrosshairVariant.CLONE: (
        '#.............#',
        '##...........##',
        '#.#.........#.#',
        '#......#......#',
        '#......#......#',
        '#......#......#',
        '##...........##',
        '.###.......###.',
        '##...........##',
        '#......#......#',
        '#......#......#',
        '#......#......#',
        '#.#.........#.#',
        '##...........##',
        '#.............#',
    ),
    CrosshairVariant.CLONE_SOURCE: (
        '#######.#######',
        '.#....###....#.',
        '..#....#....#..',
        '.......#.......',
        '...............',
        '...............',
        '...............',
        '...###...###...',
        '...............',
        '...............',
        '...............',
        '.......#.......',
        '..#....#....#..',
        '.#....###....#.',
        '#######.#######',
    ),
    CrosshairVariant.ERASER: (
        '##...........##',
        '##...........##',
        '............#..',
        '...........#...',
        '....#.....#....',
        '.....#.........',
        '...............',
        '...............',
        '...............',
        '.........#.....',
        '....#.....#....',
        '...#...........',
        '..#............',
        '##...........##',
        '##...........##',
    )
}


def _pattern_core_pixels(pattern: Sequence[str]) -> set[tuple[int, int]]:
    """Returns the (x, y) core pixels of a pattern, in pattern coordinates."""
    assert len(pattern) == CROSSHAIR_GRID_SIZE and all(len(row) == CROSSHAIR_GRID_SIZE for row in pattern), \
        f'pattern is not {CROSSHAIR_GRID_SIZE}x{CROSSHAIR_GRID_SIZE}'
    return {(x, y) for y, row in enumerate(pattern) for x, char in enumerate(row) if char == '#'}


def crosshair_pattern_image(pattern: Sequence[str], pixel_scale: int = 1) -> QImage:
    """Draws a crosshair from a '#'/'.' pixel pattern, CROSSHAIR_SIZE logical pixels square, with each logical pixel
    `pixel_scale` image pixels wide."""
    core = {(x + HALO_WIDTH, y + HALO_WIDTH) for x, y in _pattern_core_pixels(pattern)}
    center = CROSSHAIR_SIZE // 2
    halo = set()
    for x, y in core:
        for dy in range(-HALO_WIDTH, HALO_WIDTH + 1):
            for dx in range(-HALO_WIDTH, HALO_WIDTH + 1):
                point = (x + dx, y + dy)
                if max(abs(point[0] - center), abs(point[1] - center)) > CENTER_CUTOUT:
                    halo.add(point)
    image = QImage(CROSSHAIR_SIZE * pixel_scale, CROSSHAIR_SIZE * pixel_scale,
                   QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    for pixels, color in ((halo - core, HALO_COLOR), (core, CORE_COLOR)):
        for x, y in pixels:
            painter.fillRect(QRect(x * pixel_scale, y * pixel_scale, pixel_scale, pixel_scale), color)
    painter.end()
    return image


def crosshair_image(variant: CrosshairVariant, pixel_scale: int = 1) -> QImage:
    """Draws a variant's crosshair, CROSSHAIR_SIZE logical pixels square, with each logical pixel `pixel_scale` image
    pixels wide."""
    return crosshair_pattern_image(_PATTERNS[variant], pixel_scale)


def crosshair_pixel_scale(device_pixel_ratio: float) -> int:
    """Returns the whole-number pixel scale for crosshairs on a screen with the given device pixel ratio.

    Fractional ratios round up, except those at most 0.25 above a whole number, which round down.
    """
    return max(1, math.ceil(device_pixel_ratio - 0.25))


@cache
def _cached_pixmap(variant: CrosshairVariant, pixel_scale: int) -> QPixmap:
    pixmap = QPixmap.fromImage(crosshair_image(variant, pixel_scale))
    pixmap.setDevicePixelRatio(pixel_scale)
    return pixmap


def crosshair_pixmap(variant: CrosshairVariant, device_pixel_ratio: float) -> QPixmap:
    """Returns a variant's crosshair as a pixmap CROSSHAIR_SIZE logical pixels square. Callers must not modify it."""
    return _cached_pixmap(variant, crosshair_pixel_scale(device_pixel_ratio))


@cache
def _cached_cursor(variant: CrosshairVariant, pixel_scale: int) -> QCursor:
    center = CROSSHAIR_SIZE // 2
    return QCursor(_cached_pixmap(variant, pixel_scale), center, center)


def crosshair_cursor(variant: CrosshairVariant, device_pixel_ratio: float) -> QCursor:
    """Returns the cursor for a crosshair variant, with its hotspot on the centre pixel."""
    return _cached_cursor(variant, crosshair_pixel_scale(device_pixel_ratio))
