"""A loading design that plays the frames of one sprite sheet in a loop."""
from typing import Optional

from PySide6.QtCore import QRect, QRectF
from PySide6.QtGui import QPainter, QImage

from src.ui.loading.loading_design import LoadingDesign


class SpriteSheetDesign(LoadingDesign):
    """Plays square frames read from a grid, left to right and then top to bottom."""

    def __init__(self, name: str, variant: str, sheet: QImage, frame_size: int, frame_count: Optional[int],
                 duration_ms: int) -> None:
        """
        Parameters
        ----------
            name: str
                The design's display name.
            variant: str
                The variant's name.
            sheet: QImage
                The sprite sheet. Its width and height must be multiples of frame_size.
            frame_size: int
                The side of each square frame, in pixels.
            frame_count: Optional[int]
                Number of frames to play, for a sheet whose last row isn't full. None plays every grid cell.
            duration_ms: int
                Length of one loop through every frame.
        """
        super().__init__(name, variant, duration_ms)
        if frame_size <= 0 or sheet.isNull() or sheet.width() % frame_size != 0 \
                or sheet.height() % frame_size != 0:
            raise ValueError(f'{sheet.width()}x{sheet.height()} sprite sheet does not divide into {frame_size}px'
                             ' frames')
        self._columns = sheet.width() // frame_size
        cell_count = self._columns * (sheet.height() // frame_size)
        if frame_count is None:
            frame_count = cell_count
        if not 0 < frame_count <= cell_count:
            raise ValueError(f'Sprite sheet has {cell_count} frames, but frame_count is {frame_count}')
        self._sheet = sheet
        self._frame_size = frame_size
        self.frame_count = frame_count

    @property
    def native_size(self) -> Optional[int]:
        """Returns the frame side."""
        return self._frame_size

    def frame_index(self, phase: float) -> int:
        """Returns the index of the frame shown at a phase."""
        return int(phase * self.frame_count) % self.frame_count

    def frame_rect(self, index: int) -> QRect:
        """Returns a frame's bounds within the sprite sheet."""
        return QRect((index % self._columns) * self._frame_size, (index // self._columns) * self._frame_size,
                     self._frame_size, self._frame_size)

    def paint(self, painter: QPainter, bounds: QRectF, phase: float, dark: bool) -> None:
        """Draws the current frame scaled up without smoothing."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawImage(bounds, self._sheet, QRectF(self.frame_rect(self.frame_index(phase))))
        painter.restore()
