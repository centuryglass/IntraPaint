"""Halftone Press: three screened ink layers at print angles, with a rotating wave that swells the dots.

Procedural, with no assets, so it is always available as a loading design.
"""
import math

import numpy as np
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QImage, QColor

from src.ui.loading.loading_design import LoadingDesign

DESIGN_NAME = 'Halftone Press'
DURATION_MS = 4000

# Dot spacing, and the ring's inner and outer radius, in units of the indicator's side.
GRID_SPACING = 0.027
INNER_RADIUS = 0.3
OUTER_RADIUS = 0.49
FADE_WIDTH = 0.04
MAX_DOT_RADIUS = GRID_SPACING * 0.62
MIN_DOT_RADIUS = 0.002

# (screen angle in degrees, wave phase offset, ink color on light themes, ink color on dark themes)
INK_LAYERS = (
    (15, 0.0, '#00a4d6', '#00e5ff'),
    (75, 2.1, '#e0007a', '#ff3fd0'),
    (0, 4.2, '#f2c500', '#ffe600'),
)


def _smoothstep(edge0: float, edge1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


class _ScreenLayer:
    """Dot centers of one ink layer, relative to the indicator's center, with each dot's fixed wave inputs."""

    def __init__(self, angle_degrees: float, wave_offset: float, light_color: str, dark_color: str) -> None:
        self.light_color = QColor(light_color)
        self.dark_color = QColor(dark_color)
        steps = np.arange(-20, 21) * GRID_SPACING
        u, v = np.meshgrid(steps, steps)
        angle = math.radians(angle_degrees)
        x = u * math.cos(angle) - v * math.sin(angle)
        y = u * math.sin(angle) + v * math.cos(angle)
        radius = np.hypot(x, y)
        in_ring = (radius >= INNER_RADIUS) & (radius <= OUTER_RADIUS)
        self.x = x[in_ring]
        self.y = y[in_ring]
        radius = radius[in_ring]
        self.window = (_smoothstep(INNER_RADIUS, INNER_RADIUS + FADE_WIDTH, radius)
                       * (1 - _smoothstep(OUTER_RADIUS - FADE_WIDTH, OUTER_RADIUS, radius)))
        self.wave_base = 3 * np.arctan2(self.y, self.x) + wave_offset + radius * 14

    def dot_radii(self, phase: float) -> np.ndarray:
        """Returns each dot's radius at a phase."""
        value = (0.5 + 0.5 * np.cos(self.wave_base - 2 * math.pi * phase)) * self.window
        return MAX_DOT_RADIUS * np.sqrt(value)


class HalftonePress(LoadingDesign):
    """Draws overlapping cyan, magenta and yellow halftone screens that mix like printed ink."""

    def __init__(self) -> None:
        super().__init__(DESIGN_NAME, '', DURATION_MS)
        self._layers = [_ScreenLayer(*layer) for layer in INK_LAYERS]
        self._buffer = QImage()

    def paint(self, painter: QPainter, bounds: QRectF, phase: float, dark: bool) -> None:
        """Draws the three screens into a transparent buffer, so their overlaps mix without touching the backdrop."""
        size = bounds.size().toSize()
        if size.isEmpty():
            return
        if self._buffer.size() != size:
            self._buffer = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
        self._buffer.fill(Qt.GlobalColor.transparent)
        side = min(size.width(), size.height())
        buffer_painter = QPainter(self._buffer)
        buffer_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        buffer_painter.setPen(Qt.PenStyle.NoPen)
        # Light themes mix inks the way paper does; dark themes mix them as light.
        buffer_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus if dark
                                          else QPainter.CompositionMode.CompositionMode_Multiply)
        # Dots are drawn one at a time in device pixels: a scaled transform or one large path renders far slower.
        for layer in self._layers:
            buffer_painter.setBrush(layer.dark_color if dark else layer.light_color)
            radii = layer.dot_radii(phase)
            visible = radii >= MIN_DOT_RADIUS
            radii = radii[visible] * side
            left = layer.x[visible] * side + size.width() / 2 - radii
            top = layer.y[visible] * side + size.height() / 2 - radii
            for x, y, diameter in zip(left.tolist(), top.tolist(), (radii * 2).tolist()):
                buffer_painter.drawEllipse(QRectF(x, y, diameter, diameter))
        buffer_painter.end()
        painter.drawImage(bounds.topLeft(), self._buffer)
