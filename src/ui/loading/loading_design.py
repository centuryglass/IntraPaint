"""The interface every loading indicator design implements.

A design is a seamless loop drawn as a pure function of `phase`, so any frame can be pinned without a timer. Designs
never draw inside `MESSAGE_ZONE`, where `LoadingWidget` writes the loading message.
"""
from abc import ABC, abstractmethod
from typing import Optional

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter

# Width and height of the message rectangle, as fractions of the indicator's side, centered in the indicator.
MESSAGE_ZONE = (0.54, 0.26)


class LoadingDesign(ABC):
    """One loading animation option: a design, plus the variant of its assets it draws."""

    def __init__(self, name: str, variant: str, duration_ms: int) -> None:
        """
        Parameters
        ----------
            name: str
                The design's display name, shared by all its variants.
            variant: str
                The variant's name, usually its asset's file name. Procedural designs use an empty string.
            duration_ms: int
                Length of one loop of the animation, in milliseconds.
        """
        self.name = name
        self.variant = variant
        self.duration_ms = duration_ms

    @property
    def label(self) -> str:
        """Returns the design name, with the variant name when there is one."""
        return f'{self.name}: {self.variant}' if self.variant else self.name

    @property
    def rest_phase(self) -> float:
        """The phase shown while the animation is paused, chosen as a readable still frame."""
        return 0.0

    @property
    def native_size(self) -> Optional[int]:
        """The side of the design's bitmap frames in pixels, or None for designs drawn at any size.

        Designs with a native size are drawn at a whole-number multiple of it, without smoothing.
        """
        return None

    def next_loop(self) -> None:
        """Called each time a loop starts, at phase 0.0, so a design can vary what it draws from loop to loop."""

    def fit(self, bounds: QRectF) -> QRectF:
        """Returns the square the design should draw into, centered within a square bounds rectangle."""
        side = min(bounds.width(), bounds.height())
        center = bounds.center()
        native = self.native_size
        if native is None:
            return QRectF(center.x() - side / 2, center.y() - side / 2, side, side)
        if side >= native:
            side = (side // native) * native
        # Whole-pixel corners keep every source pixel the same size on screen.
        return QRectF(round(center.x() - side / 2), round(center.y() - side / 2), side, side)

    @abstractmethod
    def paint(self, painter: QPainter, bounds: QRectF, phase: float, dark: bool) -> None:
        """Draws one frame of the design.

        Parameters
        ----------
            painter: QPainter
                Painter to draw with. Implementations restore any painter state they change.
            bounds: QRectF
                The square to fill, as returned by `fit`.
            phase: float
                Position in the loop, from 0.0 to 1.0. Phase 1.0 looks the same as 0.0.
            dark: bool
                Whether the design is shown over a dark theme.
        """
