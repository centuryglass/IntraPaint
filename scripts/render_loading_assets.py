"""Renders the starting assets for the asset-backed loading designs, to use as they are or as restyle templates.

Writes `diffusion_ring/color_wheel.png` and `pixel_orbit/ember.png` under the output directory, in the formats
`resources/loading/README.md` describes. The committed copies came from this script; rerunning it overwrites them.

Usage: python scripts/render_loading_assets.py [--output DIR]
"""
import argparse
import colorsys
import math
import os
import random
import sys

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# pylint: disable=wrong-import-position
from PySide6.QtGui import QImage

FRAME_SIZE = 72

RING_INNER = 0.31
RING_OUTER = 0.478
RING_FADE = 0.022

PIXEL_GRID = 24
PIXEL_CELL = FRAME_SIZE // PIXEL_GRID
PIXEL_STEPS = 32
PIXEL_COLUMNS = 8
PIXEL_RING_INNER = 8.5
PIXEL_RING_OUTER = 10.35
PIXEL_TRAIL_LENGTH = 22
# Hot to cold, one entry per trail cell from the head back.
PIXEL_RAMP = ((255, 241, 232), (255, 236, 39), (255, 163, 0), (255, 0, 77), (255, 0, 77), (126, 37, 83),
              (126, 37, 83), (29, 43, 83))
# Unlit cells are a translucent neutral, so the ring shows on light and dark themes alike.
PIXEL_UNLIT = (128, 132, 140, 90)


def smoothstep(edge0: float, edge1: float, x: np.ndarray) -> np.ndarray:
    """Hermite step from 0 at edge0 to 1 at edge1."""
    t = np.clip((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def lattice_hash(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Returns a repeatable value in [0, 1) for each integer lattice point."""
    h = (x.astype(np.int64) * 374761393 + y.astype(np.int64) * 668265263 + z.astype(np.int64) * 1274126177) \
        & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    h ^= h >> 16
    return h.astype(np.float64) / 2 ** 32


def value_noise(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Smoothly interpolated 3D value noise in [0, 1)."""
    xi, yi, zi = np.floor(x), np.floor(y), np.floor(z)
    u, v, w = (smoothstep(0, 1, t) for t in (x - xi, y - yi, z - zi))

    def corner(dx: int, dy: int, dz: int) -> np.ndarray:
        return lattice_hash(xi + dx, yi + dy, zi + dz)

    def lerp(a: np.ndarray, b: np.ndarray, t: np.ndarray) -> np.ndarray:
        return a + (b - a) * t

    near = lerp(lerp(corner(0, 0, 0), corner(1, 0, 0), u), lerp(corner(0, 1, 0), corner(1, 1, 0), u), v)
    far = lerp(lerp(corner(0, 0, 1), corner(1, 0, 1), u), lerp(corner(0, 1, 1), corner(1, 1, 1), u), v)
    return lerp(near, far, w)


def fbm(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Three octaves of value noise, normalized to [0, 1)."""
    total = np.zeros_like(x)
    amplitude, frequency = 0.5, 1.0
    for _ in range(3):
        total += amplitude * value_noise(x * frequency, y * frequency, z * frequency)
        amplitude *= 0.5
        frequency *= 2
    return total / 0.875


def to_qimage(rgba: np.ndarray) -> QImage:
    """Copies an RGBA uint8 array into a new QImage."""
    height, width = rgba.shape[:2]
    data = np.ascontiguousarray(rgba, dtype=np.uint8)
    return QImage(data.data, width, height, width * 4, QImage.Format.Format_RGBA8888).copy()


def render_color_wheel() -> QImage:
    """Renders the clean Diffusion Ring: a brushed color wheel with streaks running around the ring."""
    centers = (np.arange(FRAME_SIZE) + 0.5) / FRAME_SIZE - 0.5
    dx, dy = np.meshgrid(centers, centers)
    radius = np.hypot(dx, dy)
    angle = np.arctan2(dy, dx)
    edge = smoothstep(RING_INNER, RING_INNER + 0.02, radius) * (1 - smoothstep(RING_OUTER - RING_FADE, RING_OUTER,
                                                                               radius))
    streak = fbm(np.cos(angle) * 2.5 + 3, np.sin(angle) * 2.5 + 3, radius * 55)
    rgba = np.zeros((FRAME_SIZE, FRAME_SIZE, 4), dtype=np.uint8)
    for row in range(FRAME_SIZE):
        for col in range(FRAME_SIZE):
            if edge[row, col] <= 0:
                continue
            hue = (angle[row, col] / (2 * math.pi)) % 1.0
            rgb = colorsys.hls_to_rgb(hue, 0.3 + 0.36 * streak[row, col], 0.78)
            rgba[row, col, :3] = [round(channel * 255) for channel in rgb]
            rgba[row, col, 3] = round(edge[row, col] * 255)
    return to_qimage(rgba)


def render_ember_sheet() -> QImage:
    """Renders the Pixel Orbit sprite sheet: a comet stepping around a pixel ring, cooling from white to blue."""
    rows = PIXEL_STEPS // PIXEL_COLUMNS
    sheet = np.zeros((rows * FRAME_SIZE, PIXEL_COLUMNS * FRAME_SIZE, 4), dtype=np.uint8)
    cells = []
    for y in range(PIXEL_GRID):
        for x in range(PIXEL_GRID):
            dx, dy = x + 0.5 - PIXEL_GRID / 2, y + 0.5 - PIXEL_GRID / 2
            if PIXEL_RING_INNER <= math.hypot(dx, dy) < PIXEL_RING_OUTER:
                cells.append((x, y, math.atan2(dy, dx)))
    for step in range(PIXEL_STEPS):
        frame = np.zeros((PIXEL_GRID, PIXEL_GRID, 4), dtype=np.uint8)
        head = -math.pi / 2 + 2 * math.pi * step / PIXEL_STEPS
        for x, y, cell_angle in cells:
            age = ((head - cell_angle) / (2 * math.pi)) % 1.0
            ramp_index = int(age * PIXEL_TRAIL_LENGTH)
            frame[y, x] = (*PIXEL_RAMP[ramp_index], 255) if ramp_index < len(PIXEL_RAMP) else PIXEL_UNLIT
        sparks = random.Random(step * 7 + 3)
        for spark in range(3):
            angle = head + (sparks.random() - 0.5) * 0.5
            distance = 10.7 + sparks.random() * 1.5
            x = math.floor(PIXEL_GRID / 2 + math.cos(angle) * distance)
            y = math.floor(PIXEL_GRID / 2 + math.sin(angle) * distance)
            if step % 2 == spark % 2 and 0 <= x < PIXEL_GRID and 0 <= y < PIXEL_GRID:
                frame[y, x] = (*PIXEL_RAMP[0], 255)
        top, left = (step // PIXEL_COLUMNS) * FRAME_SIZE, (step % PIXEL_COLUMNS) * FRAME_SIZE
        sheet[top:top + FRAME_SIZE, left:left + FRAME_SIZE] = np.repeat(np.repeat(frame, PIXEL_CELL, axis=0),
                                                                         PIXEL_CELL, axis=1)
    return to_qimage(sheet)


def main() -> None:
    """Renders both assets into the output directory."""
    parser = argparse.ArgumentParser(description=__doc__.split('\n', maxsplit=1)[0])
    parser.add_argument('--output', default=os.path.join(PROJECT_ROOT, 'resources', 'loading'),
                        help='Directory to write the design folders into.')
    args = parser.parse_args()
    for folder, file_name, image in (('diffusion_ring', 'color_wheel.png', render_color_wheel()),
                                     ('pixel_orbit', 'ember.png', render_ember_sheet())):
        os.makedirs(os.path.join(args.output, folder), exist_ok=True)
        path = os.path.join(args.output, folder, file_name)
        if not image.save(path):
            raise RuntimeError(f'Failed to save {path}')
        print(f'Saved {path}')


if __name__ == '__main__':
    main()
