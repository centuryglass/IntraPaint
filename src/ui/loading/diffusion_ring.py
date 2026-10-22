"""Diffusion Ring: a clean ring image that dissolves into noise and resolves back, the way diffusion sampling does.

The design holds several clean images and resolves a different one on each loop, in random order. The noise is mixed
in at draw time with the forward diffusion formula, so any restyled ring resolves the same way and needs no frames of
its own.
"""
import math
import random
from typing import Optional

import numpy as np
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QImage

from src.ui.loading.loading_design import LoadingDesign
from src.util.visual.image_utils import image_data_as_numpy_8bit

DESIGN_NAME = 'Diffusion Ring'
DEFAULT_DURATION_MS = 5000

# Distinct noise patterns per loop. The pattern holds between steps, so noise boils instead of flickering per frame.
NOISE_STEPS = 48
# Scales a sum of three uniform samples to roughly match the clean image's [-1, 1] color range.
NOISE_SCALE = 1.6


def _hash_uniform(index: np.ndarray, step: int, channel: int) -> np.ndarray:
    """Returns a repeatable uniform value in [0, 1) for each pixel index, noise step and channel."""
    x = (index * np.uint32(0x9E3779B1)) ^ np.uint32((step * 0x85EBCA77) & 0xFFFFFFFF) \
        ^ np.uint32((channel * 0xC2B2AE3D) & 0xFFFFFFFF)
    x ^= x >> np.uint32(16)
    x *= np.uint32(0x7FEB352D)
    x ^= x >> np.uint32(15)
    x *= np.uint32(0x846CA68B)
    x ^= x >> np.uint32(16)
    return x.astype(np.float32) / np.float32(2 ** 32)


def signal_level(phase: float) -> float:
    """Returns how much of the clean image shows at a phase: 0.0 is pure noise at phase 0, 1.0 is clean at 0.5."""
    t = 0.5 - 0.5 * math.cos(2 * math.pi * phase)
    return t * t * (3 - 2 * t)


class DiffusionRing(LoadingDesign):
    """Draws one of several clean ring images mixed with stepped noise.

    Every image is drawn through the first image's alpha, so the image can change while the signal level is 0.0
    without any visible jump. Call `next_loop` at the start of a loop to switch images.
    """

    def __init__(self, images: list[QImage], duration_ms: int = DEFAULT_DURATION_MS,
                 rng: Optional[random.Random] = None) -> None:
        """
        Parameters
        ----------
            images: list[QImage]
                The clean rings, all square and the same size, on a transparent background. The first one is shown
                until the first call to `next_loop`, and its alpha channel is used for all of them.
            duration_ms: int
                Length of one loop, from noise to clean and back.
            rng: Optional[random.Random]
                Source of randomness for the image order, defaulting to the `random` module's.
        """
        super().__init__(DESIGN_NAME, '', duration_ms)
        if len(images) == 0:
            raise ValueError('Diffusion ring needs at least one image')
        self._size = images[0].width()
        self._colors: list[np.ndarray] = []
        for image in images:
            if image.isNull() or image.width() != image.height() or image.width() != self._size:
                raise ValueError(f'Diffusion ring images must be square and the same size, got {image.width()}x'
                                 f'{image.height()} with a {self._size}px first image')
            pixels = image_data_as_numpy_8bit(image.convertToFormat(QImage.Format.Format_ARGB32)).astype(np.float32)
            self._colors.append(pixels[:, :, :3] / 127.5 - 1)
            if len(self._colors) == 1:
                self._alpha = pixels[:, :, 3] / 255
        self._rng = rng if rng is not None else random
        self._current = 0
        self._queue: list[int] = []
        self._index = np.arange(self._size * self._size, dtype=np.uint32).reshape(self._size, self._size)
        self._frame_phase: Optional[float] = None
        self._frame = QImage()

    @property
    def image_count(self) -> int:
        """Returns the number of clean images the design cycles through."""
        return len(self._colors)

    @property
    def current_image(self) -> int:
        """Returns the index of the image being drawn."""
        return self._current

    def next_loop(self) -> None:
        """Switches to the next image in a random order that shows each image once before any repeats, and never
        repeats an image back to back. Call only when the signal level is 0.0, where the switch can't be seen."""
        if len(self._colors) == 1:
            return
        if len(self._queue) == 0:
            self._queue = list(range(len(self._colors)))
            self._rng.shuffle(self._queue)
            if self._queue[-1] == self._current:
                self._queue[0], self._queue[-1] = self._queue[-1], self._queue[0]
        self._current = self._queue.pop()
        self._frame_phase = None

    @property
    def rest_phase(self) -> float:
        """Rests on the clean ring."""
        return 0.5

    @property
    def native_size(self) -> Optional[int]:
        """Returns the clean image's side."""
        return self._size

    def frame(self, phase: float) -> QImage:
        """Returns the native-size frame for a phase."""
        if phase == self._frame_phase:
            return self._frame
        signal = signal_level(phase)
        step = int(phase * NOISE_STEPS) % NOISE_STEPS
        pixels = np.empty((self._size, self._size, 4), dtype=np.uint8)
        for channel in range(3):
            noise = (_hash_uniform(self._index, step, channel) + _hash_uniform(self._index, step, channel + 3)
                     + _hash_uniform(self._index, step, channel + 6) - 1.5) * NOISE_SCALE
            mixed = math.sqrt(signal) * self._colors[self._current][:, :, channel] + math.sqrt(1 - signal) * noise
            pixels[:, :, channel] = np.clip(np.rint((mixed + 1) * 127.5), 0, 255)
        alpha_jitter = 0.5 + 0.5 * _hash_uniform(self._index, step, 9)
        alpha = self._alpha * (signal + (1 - signal) * alpha_jitter)
        pixels[:, :, 3] = np.clip(np.rint(alpha * 255), 0, 255)
        self._frame = QImage(pixels.data, self._size, self._size, QImage.Format.Format_ARGB32).copy()
        self._frame_phase = phase
        return self._frame

    def paint(self, painter: QPainter, bounds: QRectF, phase: float, dark: bool) -> None:
        """Draws the frame scaled up without smoothing, so noise stays as crisp pixels."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawImage(bounds, self.frame(phase))
        painter.restore()
